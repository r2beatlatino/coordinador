# -*- coding: utf-8 -*-
"""lanzamientos — el «CONTENIDO DINÁMICO» de Cuenta Eñeños: cuándo se abre cada juego y las invitaciones anticipadas.
18-nov-2026.

Benja: «su botón para jugar / descargar estará cerrado y se liberará en estas fechas: EDA sábado 21, 7 pm Perú (8 pm
Bolivia); GunBound domingo 12 del mediodía (Perú); Eñeñosbit 2027 lunes, misma hora que EDA. Una cuenta atrás a cada
uno. EDA = beta, GunBound = beta, Eñeñosbit 2027 = alpha. Y un botón para solicitar invitación anticipada, que haga que
un bot en Discord, en el canal de eventos, mande la solicitud con el Ñ2-ID y botones aprobar / rechazar.»

QUÉ HACE
- `LANZAMIENTOS`: por juego, la fecha, la etiqueta (BETA / ALPHA) y qué pases cubre. Se pueden cambiar SIN publicar
  nada: `config/lanzamientos.json` al lado de `portero.db` pisa lo de acá (se lee en cada pedido, por fecha del archivo).
- `cerrado_para(uid, pase)` (lo usa `portero.permitido`): ANTES de la fecha sólo entran los admins / moderadores y los
  APROBADOS (por invitación o a mano en el panel); DESPUÉS, toda cuenta activa (Benja: «EDA se abre a todas las cuentas»).
- `GET /lanzamientos` (sesión opcional) -> {ahora, juegos: {clave: {nombre, etiqueta, desde, libre, permitido,
  invitacion}}}: lo que pinta el launcher (la cuenta atrás la calcula él con `ahora` del server, no con su reloj).
- `POST /invitacion {juego}` (con sesión): pide la invitación anticipada. Una pendiente por juego; si la rechazaron,
  se puede volver a pedir a las 24 h. Avisa en Discord.
- Discord: un WEBHOOK del canal de eventos (`R2_DISCORD_EVENTOS_WEBHOOK`; Benja eligió «lo más fácil»). El mensaje
  trae el Ñ2-ID y los enlaces ✅ Aprobar / ❌ Rechazar, que abren el PANEL (`/cuentas/admin#invitacion=…`).
  ⛔ El enlace NO aprueba solo: Discord abre los enlaces para la vista previa, y la cookie del panel es SameSite=Strict
  (no viaja desde Discord). Se decide en el panel, con la sesión de admin / moderador (Benja: «admins y moderadores»),
  por POST. Al decidir, el mensaje de Discord se EDITA («✅ Aprobada por …»).
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

# clave -> {nombre, etiqueta, desde (ISO con huso), pases: los juegos del portero que cierra}
LANZAMIENTOS = {
    "eda": {"nombre": "EDA", "etiqueta": "BETA", "desde": "2026-11-21T19:00:00-05:00", "pases": ["eda"]},
    "gunbound": {"nombre": "GunBound", "etiqueta": "BETA", "desde": "2026-11-22T12:00:00-05:00",
                 "pases": ["gunbound", "gunbound-prueba"]},
    "r2beat-moderno": {"nombre": "Eñeñosbit 2027", "etiqueta": "ALPHA", "desde": "2026-11-23T19:00:00-05:00",
                       "pases": ["r2beat-moderno"]},
}
REPEDIR_SEG = 24 * 3600          # una rechazada se puede volver a pedir a las 24 h
ESQUEMA = """
CREATE TABLE IF NOT EXISTS invitaciones (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    uid       INTEGER NOT NULL,
    juego     TEXT NOT NULL,
    estado    TEXT NOT NULL CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
    creada    INTEGER NOT NULL,
    decidida  INTEGER,
    quien     TEXT,
    discord   TEXT                -- id del mensaje del webhook (para editarlo al decidir)
);
CREATE INDEX IF NOT EXISTS invitaciones_uid ON invitaciones (uid, juego);
"""
_cache = {"ruta": None, "fecha": None, "datos": None}
_lock = threading.Lock()


def _epoch(iso):
    return int(datetime.fromisoformat(str(iso)).timestamp())


def tabla(P):
    """Los lanzamientos vigentes: los de acá, pisados por `config/lanzamientos.json` si existe."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(P.ruta_base_portero())), "config", "lanzamientos.json")
    try:
        fecha = os.path.getmtime(ruta)
    except OSError:
        fecha = None
    with _lock:
        if _cache["ruta"] == ruta and _cache["fecha"] == fecha and _cache["datos"] is not None:
            return _cache["datos"]
        datos = {k: dict(v) for k, v in LANZAMIENTOS.items()}
        if fecha is not None:
            try:
                extra = json.load(open(ruta, encoding="utf-8"))
                for k, v in (extra or {}).items():
                    datos[k] = dict(datos.get(k, {"pases": [k]}), **v)
            except (OSError, ValueError) as e:
                P._log(f"⚠ lanzamientos.json ilegible ({e}); quedan los de fábrica")
        for v in datos.values():
            v["desde_t"] = _epoch(v["desde"])
        _cache.update(ruta=ruta, fecha=fecha, datos=datos)
        return datos


def de_pase(P, pase):
    """(clave, momento de apertura) del lanzamiento que cierra ese pase, o None."""
    for k, v in tabla(P).items():
        if pase in v.get("pases", [k]):
            return k, v["desde_t"]
    return None


def cerrado_para(P, uid, pase, ahora=None):
    """None = este lanzamiento no decide (el portero sigue con lo suyo). True / False = permitido o no.
    Sólo con Cuenta Eñeños DUEÑA (el sistema nuevo): el portero viejo (el de Chile) sigue como estaba."""
    if not P.es_duena():
        return None
    lz = de_pase(P, pase)
    if lz is None:
        return None
    clave, desde = lz
    ahora = time.time() if ahora is None else ahora
    if ahora >= desde:
        return True                                          # ya se abrió: toda cuenta activa
    if P.rol_de(uid) is not None:
        return True                                          # admins y moderadores, siempre
    return bool(P._propia().execute("SELECT 1 FROM aprobados WHERE uid = ? AND juego = ?", (int(uid), clave)).fetchone())


def _ultima(P, uid, clave):
    return P._propia().execute("SELECT * FROM invitaciones WHERE uid = ? AND juego = ? ORDER BY id DESC LIMIT 1",
                               (int(uid), clave)).fetchone()


def lista(P, token, ahora=None):
    """GET /lanzamientos — con sesión, además: si puede entrar ya y cómo va su invitación."""
    from . import social as SO
    ahora = time.time() if ahora is None else ahora
    uid = SO._sesion(P, token, ahora) if token else None
    out = {}
    for k, v in tabla(P).items():
        d = {"nombre": v["nombre"], "etiqueta": v.get("etiqueta", ""), "desde": v["desde_t"], "libre": ahora >= v["desde_t"]}
        if uid:
            d["permitido"] = bool(cerrado_para(P, uid, v.get("pases", [k])[0], ahora))
            f = _ultima(P, uid, k)
            d["invitacion"] = f["estado"] if f else None
        out[k] = d
    return 200, {"ahora": int(ahora), "juegos": out}


def pedir(P, token, juego, ahora=None):
    """POST /invitacion {juego}: la invitación anticipada. -> {estado}"""
    from . import social as SO
    ahora = time.time() if ahora is None else ahora
    uid = SO._sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    t = tabla(P)
    clave = str(juego or "")
    if clave not in t:
        return 404, {"error": "Ese juego no existe."}
    if ahora >= t[clave]["desde_t"]:
        return 200, {"estado": "libre"}
    if cerrado_para(P, uid, t[clave].get("pases", [clave])[0], ahora):
        return 200, {"estado": "aprobada"}
    with P._escribir:
        c = P._propia()
        f = _ultima(P, uid, clave)
        if f and f["estado"] == "pendiente":
            return 200, {"estado": "pendiente"}
        if f and f["estado"] == "rechazada" and ahora - (f["decidida"] or f["creada"]) < REPEDIR_SEG:
            return 429, {"estado": "rechazada", "error": "La solicitud fue rechazada. Puede volver a pedirla mañana."}
        cur = c.execute("INSERT INTO invitaciones (uid, juego, estado, creada) VALUES (?, ?, 'pendiente', ?)",
                        (int(uid), clave, int(ahora)))
        c.commit()
        iid = cur.lastrowid
    P._log(f"invitación #{iid}: uid={uid} pide {clave}")
    _discord_en_hilo(P, iid)
    return 200, {"estado": "pendiente"}


def ficha(P, iid):
    """La invitación para el panel: {id, juego, nombre_juego, etiqueta, uid, apodo, usuario, estado, creada, quien}."""
    f = P._propia().execute("SELECT * FROM invitaciones WHERE id = ?", (int(iid),)).fetchone()
    if not f:
        return None
    t = tabla(P).get(f["juego"], {})
    r = P._cuentas().execute("SELECT apodo FROM cuentas WHERE uid = ?", (int(f["uid"]),)).fetchone()
    return {"id": int(f["id"]), "juego": f["juego"], "nombre_juego": t.get("nombre", f["juego"]), "etiqueta": t.get("etiqueta", ""),
            "uid": int(f["uid"]), "apodo": (r["apodo"] if r and r["apodo"] else None), "usuario": P._login_de(int(f["uid"])),
            "estado": f["estado"], "creada": int(f["creada"]), "quien": f["quien"]}


def pendientes(P, limite=200):
    """★ 18-nov (Benja: «pedí acceso a los tres, pero en el panel sólo me salió uno»): TODAS las pendientes, para
    decidirlas desde el panel sin abrir un enlace por cada una. Las más viejas primero."""
    filas = P._propia().execute("SELECT id FROM invitaciones WHERE estado = 'pendiente' ORDER BY id LIMIT ?", (int(limite),)).fetchall()
    return [f for f in (ficha(P, r["id"]) for r in filas) if f]


def decidir(P, uid_admin, iid, accion, ahora=None):
    """POST /admin/invitacion {id, accion: aprobar|rechazar} — con la sesión del PANEL (admin o moderador)."""
    ahora = time.time() if ahora is None else ahora
    if P.rol_de(uid_admin) is None:
        return 401, {"error": "Tiene que entrar con una cuenta ADMIN o MODERADOR."}
    if accion not in ("aprobar", "rechazar"):
        return 400, {"error": "Acción desconocida."}
    try:
        iid = int(iid)
    except (TypeError, ValueError):
        return 400, {"error": "Solicitud inválida."}
    f = ficha(P, iid)
    if not f:
        return 404, {"error": "Esa solicitud no existe."}
    # ★ 19-nov (Coordinador): un moderador con juegos asignados sólo decide las de SUS juegos
    if not P.puede_en(uid_admin, f["juego"]):
        return 403, {"error": "Ese juego no está asignado a tu cuenta."}
    if f["estado"] != "pendiente":
        return 409, {"error": f"Esa solicitud ya está {f['estado']} (por {f['quien'] or '—'}).", "invitacion": f}
    quien = P._login_de(uid_admin) or f"uid {uid_admin}"
    if accion == "aprobar":
        codigo, datos = P.admin_accion(uid_admin, "aprobar", f["uid"], f["juego"], f"invitación anticipada #{iid}")
        if codigo != 200:
            return codigo, datos
    with P._escribir:
        c = P._propia()
        c.execute("UPDATE invitaciones SET estado = ?, decidida = ?, quien = ? WHERE id = ? AND estado = 'pendiente'",
                  ("aprobada" if accion == "aprobar" else "rechazada", int(ahora), quien, iid))
        c.commit()
    if accion == "rechazar":                                  # ★ 19-nov: la aprobada ya queda por `admin_accion`
        P._auditar(uid_admin, "rechazar invitación", f["uid"], f["juego"], f"invitación anticipada #{iid}")
    P._log(f"invitación #{iid}: {accion} por {quien}")
    _discord_en_hilo(P, iid)
    return 200, {"ok": True, "invitacion": ficha(P, iid)}


# ── Discord (webhook del canal de eventos) ───────────────────────────────────────────────────────────────────
def _webhook():
    return (os.environ.get("R2_DISCORD_EVENTOS_WEBHOOK") or "").strip()


def _panel_url():
    return (os.environ.get("R2_CUENTAS_URL_PUBLICA") or "https://auth.xn--eeos-gqab.link").rstrip("/") + "/cuentas/admin"


def mensaje_discord(P, f):
    """El mensaje (embed) de una invitación, según su estado. Sin el login: sólo el Ñ2-ID y el Eñeños ID."""
    t = tabla(P).get(f["juego"], {})
    quien = f["apodo"] or "Sin Ñ2-ID"
    fecha = datetime.fromtimestamp(t.get("desde_t", 0)).strftime("%d/%m %H:%M")
    base = f"**{quien}** · Eñeños ID {f['uid']}\nJuego: **{f['nombre_juego']}** ({f['etiqueta']}) · se abre el {fecha} (hora de Perú)"
    if f["estado"] == "pendiente":
        url = _panel_url() + f"#invitacion={f['id']}"
        return {"embeds": [{"title": "🎟️ Solicitud de invitación anticipada", "color": 0xF5C451,
                            "description": base + f"\n\n[✅ Aprobar]({url}&accion=aprobar)  ·  [❌ Rechazar]({url}&accion=rechazar)",
                            "footer": {"text": f"Solicitud #{f['id']} · se decide en el panel (admins y moderadores)"}}]}
    ok = f["estado"] == "aprobada"
    return {"embeds": [{"title": ("✅ Aprobada" if ok else "❌ Rechazada") + f" por {f['quien'] or '—'}",
                        "color": 0x55DAB0 if ok else 0xFF6AA9, "description": base,
                        "footer": {"text": f"Solicitud #{f['id']}"}}]}


def _http(metodo, url, cuerpo):
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), method=metodo,
                                 headers={"Content-Type": "application/json", "User-Agent": "EnenosCuentas (enenos.link, 1.0)"})
    with urllib.request.urlopen(req, timeout=8) as r:
        t = r.read().decode("utf-8") or "{}"
        return json.loads(t)


def avisar_discord(P, iid):
    """Publica (pendiente) o EDITA (decidida) el mensaje de la invitación. Sin webhook configurado, no hace nada."""
    w = _webhook()
    if not w:
        return None
    f = ficha(P, iid)
    if not f:
        return None
    msg = dict(mensaje_discord(P, f), allowed_mentions={"parse": []})
    fila = P._propia().execute("SELECT discord FROM invitaciones WHERE id = ?", (iid,)).fetchone()
    try:
        if fila and fila["discord"]:
            _http("PATCH", f"{w}/messages/{fila['discord']}", msg)
            return fila["discord"]
        if f["estado"] != "pendiente":
            return None
        r = _http("POST", w + ("&" if "?" in w else "?") + "wait=true", dict(msg, username="Eñeños"))
        mid = str(r.get("id") or "")
        if mid:
            with P._escribir:
                c = P._propia()
                c.execute("UPDATE invitaciones SET discord = ? WHERE id = ?", (mid, iid))
                c.commit()
        return mid
    except (urllib.error.URLError, OSError, ValueError) as e:
        P._log(f"⚠ Discord (invitación #{iid}): {e!r}")
        return None


def _discord_en_hilo(P, iid):
    threading.Thread(target=avisar_discord, args=(P, iid), daemon=True, name="discord").start()
