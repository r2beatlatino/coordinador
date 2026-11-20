# -*- coding: utf-8 -*-
"""coordinador — el PANEL REAL del «Coordinador Eñeños», fase A (19-nov-2026). Parte del portero (Cuenta Eñeños
dueña, `R2_CUENTAS_DUENA=1`): sin esa variable, nada de esto existe (404).

QUÉ HAY EN LA FASE A (el diseño es el prototipo aprobado por Benja; acá NADA de datos inventados)
    · ENTRAR (#/entrar): sólo con Discord o Google, y sólo si ese Discord/Google está VINCULADO a un Eñeños ID con rol
      (admin.txt / moderadores.txt). Nada de usuario y clave.
    · ELEGIR JUEGO (#/juegos): las tarjetas salen de `juegos.json`. «Jugando ahora» y el estado de cada servidor SÓLO
      si hay de dónde sacarlo sin tocar los juegos (la presencia que ya lee social.py, o un `/salud`); si no, no se
      muestra el número.
    · LA RED (#/red): personas (Eñeños ID, vínculos, estado y permisos por juego), invitaciones por aprobar,
      lanzamientos, moderadores y permisos (sólo admin), auditoría.
    · Lo de adentro de cada juego (resumen, conectados, fichas, gráficos, contenido dinámico, novedades) es de las
      fases B y C: el panel lo muestra como «Próximamente».

EL INGRESO (Google y Discord sólo aceptan las vueltas YA registradas: las de vinculos.py, en el dominio de auth)
    panel ──POST /coordinador/api/oauth {proveedor, destino?}──▶ portero → {url del proveedor}  + cookie del flujo
         (destino: SÓLO uno de la lista blanca `R2_PANEL_URL`; nunca una dirección que venga en el pedido)
    proveedor ──vuelve a <auth>/oauth/vuelta?code&state──▶ portero: ¿quién es? (vinculos.py, modo «panel») →
         `al_volver` decide (vinculada / con rol / activa) y guarda un TICKET (un uso, 60 s, del lado del server, atado
         al uid y al navegador) → 302 a <destino>/entrar?ticket=…
    panel ──POST /coordinador/api/canjear {ticket}──▶ cookie `coordinador` (HttpOnly · Secure · SameSite=Strict · 8 h)
         o el porqué: no_vinculada · sin_permisos · suspendida · cancelada · vencido · otro_navegador
    Cada pedido re-chequea el rol (sacarlo de admin.txt / moderadores.txt lo deja afuera al instante).

LAS RUTAS (en el portero, con o sin `/cuentas`; Caddy del dominio del panel les antepone `/coordinador`)
    GET  /coordinador/  · /coordinador/entrar          la página (panel/index.html)
    GET  /coordinador/panel.js · panel.css · assets/…  lo de la página (en el repo, sin datos)
    GET  /coordinador/arte/<archivo>                   el ARTE de los juegos: carpeta FUERA del repo (`R2_PANEL_ARTE`)
    GET  /coordinador/api/estado                       {proveedores, sesion|null}                 (sin sesión)
    GET  /coordinador/api/catalogo                     las tarjetas del login (sólo lo visual)    (sin sesión)
    GET  /coordinador/api/juegos                       las tarjetas con servidores, lanzamiento e invitaciones
    GET  /coordinador/api/personas?q=                  buscar (Eñeños ID, apodo; login: ADMIN por prefijo, moderador exacto)
    GET  /coordinador/api/persona/<uid>                la ficha: vínculos, estado y permisos en cada juego
    GET  /coordinador/api/invitaciones · lanzamientos · auditoria
    GET  /coordinador/api/baneos                       ★ 20-nov: los baneos vigentes de sus juegos («vence en …»)
    GET  /coordinador/api/equipo                       admins y moderadores con sus juegos (sólo ADMIN)
    POST /coordinador/api/oauth {proveedor, destino?}  · canjear {ticket} · salir
    POST /coordinador/api/accion {accion, uid, pase, detalle}   aprobar | quitar | banear | desbanear (por pase)
         ★ 20-nov banear / desbanear: además `pases: [...]`, `juegos: [...]` (con todos sus servidores), `red: true`
         (sólo ADMIN), y para banear `horas: n` | `dias: n` | `permanente: true` (sólo ADMIN) + `motivo` (obligatorio,
         ≤ 200). Un moderador: sólo en sus juegos y hasta portero.BANEO_TOPE_MODERADOR_SEG.
    POST /coordinador/api/invitacion {id, accion}      aprobar | rechazar
    POST /coordinador/api/equipo {accion, uid, juegos} juegos | agregar | quitar (sólo ADMIN; escribe moderadores.txt)
⛔ Todo POST pide `X-R2: 1` (lo mira el portero antes de llegar acá). ⛔ A un moderador nunca le llega un login, un
   correo, una IP ni nada de la contraseña; tampoco las cuentas con rol, ni los juegos que no tiene asignados.

VARIABLES
    R2_PANEL_URL        la LISTA BLANCA de a dónde vuelve el ingreso (origen, coma entre varios). La primera es la de
                        siempre. Ej.: https://coordinador.xn--eeos-gqab.link . Vacía = el panel no deja entrar.
    R2_PANEL_ARTE       la carpeta con el arte de los juegos (por omisión `panel_arte/` al lado de portero.db). ⛔ El
                        arte de los juegos (Softnyx, etc.) NO va al repo público: sin el archivo, la tarjeta usa su color.
    R2_PANEL_SALUD      «pase=url;…» el `/salud` de cada servidor por la red de adentro (ej. GunBound: {"en_linea": n}).
    R2_JUEGOS_CATALOGO  otro `juegos.json` (por omisión, el de la raíz del repo / de la imagen).
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
import urllib.request

from . import lanzamientos as LZ
from . import social as SO
from . import vinculos as V

PREFIJO = "coordinador"
COOKIE = "coordinador"
COOKIE_FLUJO = "coordinador_flujo"
TICKET_SEG = 60
SALUD_CACHE_SEG = 15
SALUD_TIMEOUT = 2.0
ACCIONES = ("aprobar", "quitar", "banear", "desbanear")
MOVIMIENTOS = ACCIONES + ("rechazar invitación",)
_DIR_PANEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS tickets_panel (
    huella     TEXT PRIMARY KEY,          -- sha256 del ticket (el ticket en sí no se guarda)
    uid        INTEGER,                   -- el Eñeños ID (NULL si la cuenta de Google/Discord no está vinculada)
    resultado  TEXT NOT NULL,             -- sesion | sin_permisos | no_vinculada | suspendida | cancelada
    proveedor  TEXT,
    nombre     TEXT,                      -- el nombre para mostrar del proveedor (nunca el correo)
    navegador  TEXT,                      -- sha256 de la cookie del flujo: el ticket sirve SÓLO en ese navegador
    creado     INTEGER NOT NULL,
    vence      INTEGER NOT NULL,
    usado      INTEGER
);
"""

_SEGURIDAD = (("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"),
              ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                          "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                                          "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"))
_TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
          ".woff2": "font/woff2"}
_NOMBRE_ARCHIVO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_ORIGEN = re.compile(r"^(?:https://[a-z0-9]([a-z0-9.-]*[a-z0-9])?(?::\d{1,5})?"
                     r"|http://(?:localhost|127\.0\.0\.1|[a-z0-9-]+\.localhost)(?::\d{1,5})?)(?:/[a-z0-9_-]+)*$")
_TICKET = re.compile(r"^[A-Za-z0-9_-]{30,80}$")
ETIQUETAS = {"produccion": "", "beta": "BETA", "alpha": "ALPHA", "en_preparacion": "EN PREPARACIÓN",
             "en_planes": "EN PLANES"}
PROVEEDOR_TXT = {"google": "Google", "discord": "Discord"}


def _sha(t):
    return hashlib.sha256(str(t).encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  El catálogo (`juegos.json`) y a qué juego pertenece cada pase
# ══════════════════════════════════════════════════════════════════════════════════════════════
_cat = {"ruta": None, "fecha": None, "juegos": []}
_cat_lock = threading.Lock()


def ruta_catalogo(P):
    return os.environ.get("R2_JUEGOS_CATALOGO") or os.path.join(P.RAIZ, "juegos.json")


def catalogo(P):
    """Los juegos de `juegos.json` (releído si cambia). Ilegible o ausente = lista vacía (el panel no inventa)."""
    ruta = ruta_catalogo(P)
    try:
        fecha = os.path.getmtime(ruta)
    except OSError:
        fecha = None
    with _cat_lock:
        if _cat["ruta"] != ruta or _cat["fecha"] != fecha:
            juegos = []
            if fecha is not None:
                try:
                    with open(ruta, encoding="utf-8") as f:
                        juegos = [j for j in json.load(f).get("juegos", []) if isinstance(j, dict) and j.get("id")]
                except (OSError, ValueError, AttributeError) as e:
                    P._log(f"⚠ coordinador: juegos.json ilegible ({e!r})")
            _cat.update(ruta=ruta, fecha=fecha, juegos=juegos)
        return list(_cat["juegos"])


def juego_de_pase(P, pase):
    """El id del catálogo al que pertenece un pase (`aud`) o una clave de lanzamiento: el live, el test, o uno que
    empiece con «<live>-» (r2beat2013-subir es de r2beat2013). None si no es de ninguno."""
    pase = str(pase or "")
    for j in catalogo(P):
        ps = j.get("pases") or {}
        live, test = ps.get("live"), ps.get("test")
        if pase in (j["id"], live, test) or (live and pase.startswith(live + "-")):
            return j["id"]
    return None


def pases_de(P, jid):
    """[(pase, entorno)] de un juego del catálogo, SÓLO los que el portero conoce (los demás no tienen qué tocar)."""
    j = next((x for x in catalogo(P) if x["id"] == jid), None)
    if not j:
        return []
    conocidos = P._juegos()
    ps = j.get("pases") or {}
    out = [(ps[e], e) for e in ("live", "test") if ps.get(e) and ps[e] in conocidos]
    live = ps.get("live")
    if live:
        out += [(p, "extra") for p in conocidos if p.startswith(live + "-") and p not in (ps.get("test"),)]
    return out


def visibles(P, uid):
    """Los juegos del catálogo que esa cuenta del equipo ve (ADMIN y moderador sin lista: todos)."""
    permitidos = P.juegos_de_rol(uid)
    return [j for j in catalogo(P) if permitidos is None or j["id"] in permitidos]


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  El ingreso: lista blanca, flujo, ticket y canje
# ══════════════════════════════════════════════════════════════════════════════════════════════
def destinos():
    """La lista blanca de a dónde vuelve el ingreso (`R2_PANEL_URL`). Lo que no tiene forma de origen se IGNORA."""
    out = []
    for t in (os.environ.get("R2_PANEL_URL") or "").split(","):
        t = t.strip().rstrip("/").lower()
        if t and _ORIGEN.match(t) and t not in out:
            out.append(t)
    return out


def iniciar(P, proveedor, destino, ip, ahora=None):
    """POST /api/oauth -> (código, datos, cookie del navegador o None)."""
    if proveedor not in V.PROVEEDORES:
        return 400, {"error": "Ese método de entrada no existe."}, None
    lista = destinos()
    if not lista:
        return 503, {"error": "El panel todavía no está configurado para entrar (falta R2_PANEL_URL)."}, None
    if destino in (None, ""):
        destino = lista[0]
    destino = str(destino).strip().rstrip("/").lower()
    if destino not in lista:
        P._log(f"⚠ coordinador: destino fuera de la lista blanca, desde {ip}")
        return 400, {"error": "Ese destino no está permitido."}, None
    nav = secrets.token_urlsafe(24)
    codigo, datos = V.iniciar(P, proveedor, "panel", "", ip, ahora, extra={"destino": destino, "nav": _sha(nav)})
    if codigo != 200:
        return codigo, datos, None
    return 200, {"url": V.url_proveedor(datos["sid"])}, nav


def al_volver(P, f, res, ahora=None):
    """La vuelta de Google/Discord en modo «panel» (la llama vinculos.vuelta_de): decide, guarda el ticket y devuelve la
    dirección de vuelta, o None si el destino ya no está en la lista blanca."""
    ahora = time.time() if ahora is None else ahora
    extra = f.get("extra") or {}
    destino = extra.get("destino")
    if destino not in destinos():
        return None
    uid = res.get("uid")
    if res.get("error") or not res.get("panel"):
        resultado, uid = "cancelada", None
    elif uid is None:
        resultado = "no_vinculada"
    elif P.estado_r2beat(uid) != "ok":
        resultado = "suspendida"
    elif P.rol_de(uid) is None:
        resultado = "sin_permisos"
    else:
        resultado = "sesion"
    ticket = emitir_ticket(P, resultado, uid, f.get("proveedor"), res.get("nombre") or "", extra.get("nav"), ahora)
    P._log(f"coordinador: vuelta de {f.get('proveedor')} -> {resultado}" + (f" uid={uid}" if uid else ""))
    return f"{destino}/entrar?ticket={ticket}"


def emitir_ticket(P, resultado, uid, proveedor, nombre, navegador, ahora=None):
    """Un ticket de UN uso que vive TICKET_SEG segundos. Se guarda sólo su huella. -> el ticket."""
    ahora = int(time.time() if ahora is None else ahora)
    ticket = secrets.token_urlsafe(32)
    with P._escribir:
        c = P._propia()
        c.execute("DELETE FROM tickets_panel WHERE vence < ?", (ahora - 3600,))
        c.execute("INSERT INTO tickets_panel (huella, uid, resultado, proveedor, nombre, navegador, creado, vence) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (_sha(ticket), int(uid) if uid is not None else None, resultado, str(proveedor or "")[:16],
                   str(nombre or "")[:40], navegador, ahora, ahora + TICKET_SEG))
        c.commit()
    return ticket


def canjear(P, ticket, nav, ip="", ahora=None):
    """POST /api/canjear {ticket} -> (código, datos, token de sesión o None). El ticket se GASTA en el primer intento,
    salga bien o mal."""
    ahora = time.time() if ahora is None else ahora
    claves = [f"coord-ip:{ip}"]
    if P._frenado(claves, ahora):
        return 429, {"error": "demasiados", "texto": "Demasiados intentos. Espere unos minutos."}, None
    t = str(ticket or "")
    vencido = (400, {"error": "vencido", "texto": "El ingreso venció o ya se usó. Vuelva a intentarlo."}, None)
    if not _TICKET.match(t):
        P._anotar_fallo(claves, ahora)
        return vencido
    with P._escribir:
        c = P._propia()
        r = c.execute("SELECT * FROM tickets_panel WHERE huella = ?", (_sha(t),)).fetchone()
        if not r or r["usado"] is not None or r["vence"] < ahora:
            P._anotar_fallo(claves, ahora)
            return vencido
        cur = c.execute("UPDATE tickets_panel SET usado = ? WHERE huella = ? AND usado IS NULL", (int(ahora), r["huella"]))
        c.commit()
        if cur.rowcount != 1:                                       # otro pedido lo gastó al mismo tiempo
            return vencido
    if r["navegador"] and not (nav and hmac.compare_digest(_sha(nav), str(r["navegador"]))):
        P._anotar_fallo(claves, ahora)
        return 400, {"error": "otro_navegador", "texto": "El ingreso empezó en otro navegador. Vuelva a intentarlo aquí."}, None
    prov = PROVEEDOR_TXT.get(r["proveedor"], r["proveedor"] or "")
    uid = r["uid"]
    res = r["resultado"]
    if res == "sesion":                                             # ⛔ se vuelve a mirar: pudo cambiar en estos segundos
        if P.estado_r2beat(uid) != "ok":
            res = "suspendida"
        elif P.rol_de(uid) is None:
            res = "sin_permisos"
    if res == "no_vinculada":
        return 403, {"error": "no_vinculada", "proveedor": r["proveedor"], "nombre": r["nombre"] or ""}, None
    if res == "sin_permisos":
        return 403, {"error": "sin_permisos", "proveedor": r["proveedor"], "eid": int(uid),
                     "nombre": _nombre(P, uid)}, None
    if res == "suspendida":
        return 403, {"error": "suspendida", "texto": "Esta cuenta está suspendida."}, None
    if res != "sesion":
        return 400, {"error": "cancelada", "texto": f"No se completó la entrada con {prov or 'el proveedor'}."}, None
    token = P.abrir_sesion_admin(uid, ip, ahora)
    rol = P.rol_de(uid)
    P._auditar(uid, "entrar al Coordinador", None, None, f"con {prov}")
    P._log(f"coordinador: entró el {rol} uid={uid} con {prov}")
    return 200, {"ok": True, "rol": rol, "uid": int(uid), "nombre": _nombre(P, uid), "via": r["proveedor"]}, token


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  Los datos
# ══════════════════════════════════════════════════════════════════════════════════════════════
def _apodo(P, uid):
    r = P._cuentas().execute("SELECT apodo FROM cuentas WHERE uid = ?", (int(uid),)).fetchone()
    return (r["apodo"] or "") if r else ""


def _nombre(P, uid):
    """Lo que se muestra de una persona: su Ñ2-ID (apodo) o «Eñeños #<id>». ⛔ Nunca el login."""
    return _apodo(P, uid) or f"Eñeños #{int(uid)}"


def _vias(P, uid):
    return [r["proveedor"] for r in P._cuentas().execute(
        "SELECT proveedor FROM vinculos WHERE uid = ? ORDER BY proveedor", (int(uid),))]


def sesion_info(P, uid):
    rol = P.rol_de(uid)
    asignados = P.juegos_de_rol(uid)
    return {"uid": int(uid), "nombre": _nombre(P, uid), "rol": rol,
            "juegos": None if asignados is None else sorted(asignados),
            "lista_vieja": rol == "moderador" and asignados is None,
            "vias": _vias(P, uid)}


def ruta_arte():
    return os.environ.get("R2_PANEL_ARTE") or ""


def _dir_arte(P):
    return ruta_arte() or os.path.join(os.path.dirname(os.path.abspath(P.ruta_base_portero())), "panel_arte")


def _arte(P, nombre):
    """`arte/<nombre>` si ese archivo está en la carpeta del arte; si no, None (la tarjeta usa su color)."""
    if not nombre or not _NOMBRE_ARCHIVO.match(str(nombre)):
        return None
    return "arte/" + nombre if os.path.isfile(os.path.join(_dir_arte(P), nombre)) else None


def tarjeta(P, j, ahora=None):
    """Lo VISUAL de un juego (sale de `juegos.json`; el login también lo ve)."""
    pan = j.get("panel") or {}
    lz = LZ.tabla(P).get(j["id"])
    etq = ETIQUETAS.get(j.get("estado"), "")
    if lz and j.get("estado") != "produccion":
        etq = lz.get("etiqueta") or etq
    return {"id": j["id"], "nombre": j.get("corto") or j.get("nombre") or j["id"], "nombre_largo": j.get("nombre") or "",
            "estado": j.get("estado") or "", "etiqueta": etq, "color": pan.get("color") or "81,216,229",
            "arte": _arte(P, pan.get("arte")), "pos": pan.get("pos") or "50% 50%", "logo": _arte(P, pan.get("logo")),
            "genero": pan.get("genero") or "", "desc": pan.get("desc") or "",
            "tiene_servidor": bool((j.get("pases") or {}).get("live"))}


_salud = {}
_salud_lock = threading.Lock()


def _fuentes_salud():
    out = {}
    for parte in (os.environ.get("R2_PANEL_SALUD") or "").split(";"):
        if "=" in parte:
            p, u = parte.split("=", 1)
            if p.strip() and u.strip().startswith(("http://", "https://")):
                out[p.strip()] = u.strip()
    return out


def _leer_salud(pase, url, ahora):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "enenos-coordinador"})
        with urllib.request.urlopen(req, timeout=SALUD_TIMEOUT) as r:
            d = json.loads(r.read(65536).decode("utf-8"))
        n = d.get("en_linea", d.get("jugando"))
        res = {"estado": "en_linea" if d.get("ok", True) else "sin_respuesta",
               "jugando": int(n) if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else None}
    except Exception:                                               # noqa: BLE001 — no contesta = «sin respuesta»
        res = {"estado": "sin_respuesta", "jugando": None}
    with _salud_lock:
        _salud[pase] = (ahora, res)


def servidores(P, pases, ahora=None):
    """{pase: {estado: en_linea|sin_respuesta, jugando: n|None}} SÓLO de los pases con fuente. Sin fuente: no está."""
    ahora = time.time() if ahora is None else ahora
    fuentes = _fuentes_salud()
    out, hilos = {}, []
    for p in pases:
        if p in fuentes:
            with _salud_lock:
                hay = _salud.get(p)
            if not hay or ahora - hay[0] > SALUD_CACHE_SEG:
                h = threading.Thread(target=_leer_salud, args=(p, fuentes[p], ahora), daemon=True)
                h.start()
                hilos.append(h)
    for h in hilos:
        h.join(SALUD_TIMEOUT + 0.5)
    presencia = SO.jugando_por_juego(P, ahora) if any(p in SO.presencia_configurada() for p in pases) else {}
    configurada = SO.presencia_configurada()
    for p in pases:
        if p in fuentes:
            with _salud_lock:
                hay = _salud.get(p)
            if hay:
                out[p] = dict(hay[1])
        if p in configurada:                                        # la presencia cuenta mejor quién está
            if p in presencia:
                out[p] = {"estado": "en_linea", "jugando": presencia[p]}
            elif p not in out:
                out[p] = {"estado": "sin_respuesta", "jugando": None}
    return out


def juegos(P, uid, ahora=None):
    ahora = time.time() if ahora is None else ahora
    vis = visibles(P, uid)
    pases = [x for j in vis for x in ((j.get("pases") or {}).get("live"), (j.get("pases") or {}).get("test")) if x]
    srv = servidores(P, pases, ahora)
    tabla = LZ.tabla(P)
    pend = {}
    for f in LZ.pendientes(P):
        cat = juego_de_pase(P, f["juego"])
        pend[cat] = pend.get(cat, 0) + 1
    out = []
    for j in vis:
        t = tarjeta(P, j, ahora)
        ps = j.get("pases") or {}
        t["servidores"] = {e: (srv.get(ps[e]) if ps.get(e) else None) for e in ("live", "test")}
        t["pases"] = {e: ps.get(e) for e in ("live", "test")}
        lz = tabla.get(j["id"])
        t["lanzamiento"] = {"desde": lz["desde_t"], "libre": ahora >= lz["desde_t"]} if lz else None
        t["invitaciones"] = pend.get(j["id"], 0)
        out.append(t)
    return 200, {"ahora": int(ahora), "juegos": out}


def _es_admin(P, uid):
    return P.rol_de(uid) == "admin"


def resumen_persona(P, viewer, r):
    admin = _es_admin(P, viewer)
    d = {"uid": int(r["uid"]), "nombre": r["apodo"] or f"Eñeños #{int(r['uid'])}", "apodo": r["apodo"] or "",
         "estado": r["estado"], "vias": _vias(P, r["uid"])}
    if admin:
        d["usuario"] = r["usuario"]
        d["rol"] = P.rol_de(r["uid"])
    return d


def buscar(P, viewer, q):
    """Hasta 20 personas. ADMIN: Eñeños ID, apodo (contiene) o login (empieza). MODERADOR: Eñeños ID, apodo o login
    EXACTO, y nunca una cuenta con rol ni un login en la respuesta."""
    q = str(q or "").strip()[:40]
    admin = _es_admin(P, viewer)
    num = q.lstrip("#").strip()
    if len(q) < 2 and not num.isdigit():
        return 400, {"error": "Escriba al menos 2 letras, o el Eñeños ID."}
    c = P._cuentas()
    uids = []

    def suma(filas):
        for f in filas:
            if int(f[0]) not in uids:
                uids.append(int(f[0]))

    if num.isdigit() and len(num) <= 12:
        suma(c.execute("SELECT uid FROM cuentas WHERE uid = ?", (int(num),)))
    patron = SO.clave_apodo(q).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    suma(c.execute("SELECT uid FROM cuentas WHERE apodo_clave LIKE ? ESCAPE '\\' ORDER BY apodo_clave LIMIT 20",
                   ("%" + patron + "%",)))
    if admin:
        pl = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        suma(c.execute("SELECT uid FROM cuentas WHERE usuario LIKE ? ESCAPE '\\' ORDER BY usuario LIMIT 20", (pl + "%",)))
    else:
        suma(c.execute("SELECT uid FROM cuentas WHERE usuario = ? COLLATE BINARY", (q,)))
        uids = [u for u in uids if P.rol_de(u) is None]
    filas = []
    for u in uids[:20]:
        r = c.execute("SELECT uid, usuario, estado, apodo FROM cuentas WHERE uid = ?", (u,)).fetchone()
        if r:
            filas.append(resumen_persona(P, viewer, r))
    return 200, {"personas": filas}


def _acciones_de(P, viewer):
    if _es_admin(P, viewer):
        return list(ACCIONES)
    return list(P.ACCIONES_MODERADOR if P.juegos_de_moderador(viewer) is None else P.ACCIONES_MODERADOR_ASIGNADO)


def persona(P, viewer, uid, ahora=None):
    ahora = int(time.time() if ahora is None else ahora)
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return 400, {"error": "Eñeños ID inválido."}
    c = P._cuentas()
    r = c.execute("SELECT uid, usuario, estado, creada, apodo, visto FROM cuentas WHERE uid = ?", (uid,)).fetchone()
    if not r:
        return 404, {"error": "Esa persona no existe."}
    admin = _es_admin(P, viewer)
    if not admin and P.rol_de(uid) is not None:
        return 403, {"error": "Esa cuenta la maneja un ADMIN."}
    d = resumen_persona(P, viewer, r)
    d.update(creada=r["creada"], visto=r["visto"])
    vins = c.execute("SELECT proveedor, nombre, creado FROM vinculos WHERE uid = ? ORDER BY proveedor", (uid,)).fetchall()
    # ⛔ al moderador, sólo QUÉ tiene vinculado (el nombre de Google suele ser el nombre real de la persona)
    d["vinculos"] = [dict(proveedor=v["proveedor"], creado=v["creado"], **({"nombre": v["nombre"] or ""} if admin else {}))
                     for v in vins]
    p = P._propia()
    tabla = LZ.tabla(P)
    acciones = _acciones_de(P, viewer)
    js = []
    for j in visibles(P, viewer):
        pases = []
        for pase, entorno in pases_de(P, j["id"]):
            ban = P.baneo_vigente(uid, pase, ahora)                 # ★ 20-nov: sólo el que HOY cuenta
            apr = p.execute("SELECT desde FROM aprobados WHERE uid = ? AND juego = ?", (uid, pase)).fetchone()
            pases.append({"pase": pase, "entorno": entorno, "nombre": P._juegos()[pase]["nombre"],
                          "abierto": bool(P._juegos()[pase]["abierto"]), "aprobada": bool(apr), "baneada": bool(ban),
                          "motivo": (ban["motivo"] or "") if ban else "", "permitido": P.permitido(uid, pase, ahora),
                          **({"hasta": P.datos_baneo(ban, ahora)["hasta"],
                              "restante_seg": P.datos_baneo(ban, ahora)["restante_seg"]} if ban else {})})
        inv = None
        if j["id"] in tabla:
            f = LZ._ultima(P, uid, j["id"])
            inv = f["estado"] if f else None
        js.append({"id": j["id"], "nombre": j.get("corto") or j.get("nombre"), "pases": pases, "invitacion": inv})
    d["juegos"] = js
    d["acciones"] = acciones
    d["sancion"] = limites_sancion(P, viewer)
    return 200, {"persona": d}


def limites_sancion(P, viewer):
    """★ 20-nov: lo que ESTA cuenta del equipo puede poner en un baneo (el formulario lo respeta; el server lo exige)."""
    admin = _es_admin(P, viewer)
    return {"permanente": admin, "red": admin, "tope_seg": None if admin else P.BANEO_TOPE_MODERADOR_SEG,
            "motivo_max": P.BANEO_MOTIVO_MAX}


def pases_pedidos(P, viewer, d):
    """★ 20-nov: los pases de un banear / desbanear: `pase` (uno, como antes), `pases` (lista) y/o `juegos` (ids del
    catálogo: cada uno con TODOS sus servidores — PROD, TEST y los extra). -> (lista, error)."""
    out = []
    if d.get("pase"):
        out.append(str(d["pase"]))
    for k in ("pases", "juegos"):
        v = d.get(k)
        if v is None:
            continue
        if not isinstance(v, list) or len(v) > 40 or not all(isinstance(x, str) for x in v):
            return None, "Esa lista de juegos no sirve."
        for x in v:
            if k == "pases":
                out.append(x)
            else:
                ps = [p for p, _e in pases_de(P, x)]
                if not ps:
                    return None, "Ese juego no tiene servidor con pase."
                out += ps
    return list(dict.fromkeys(out)), None


def accion(P, viewer, d):
    acc = str(d.get("accion") or "")
    if acc not in ACCIONES:
        return 400, {"error": "Acción desconocida."}
    uid = d.get("uid")
    if isinstance(uid, bool) or not isinstance(uid, (int, str)) or not str(uid).isdigit():
        return 400, {"error": "Eñeños ID inválido."}
    if acc in ("banear", "desbanear"):
        red = d.get("red") is True
        pases, err = pases_pedidos(P, viewer, d)
        if err:
            return 400, {"error": err}
        if not red and not pases:
            return 400, {"error": "Elija al menos un juego."}
        if not red and any(x not in P._juegos() for x in pases):
            return 404, {"error": "Ese juego no existe."}
        motivo = d.get("motivo") if d.get("motivo") is not None else d.get("detalle")
        if acc == "banear":
            codigo, datos = P.admin_banear(viewer, int(uid), pases, str(motivo or ""), d, red=red)
        else:
            codigo, datos = P.admin_desbanear(viewer, int(uid), P.pases_de_la_red() if red else pases)
        if codigo != 200:
            return codigo, datos
        return persona(P, viewer, int(uid))
    pase = str(d.get("pase") or "")
    if pase not in P._juegos():
        return 404, {"error": "Ese juego no existe."}
    codigo, datos = P.admin_accion(viewer, acc, int(uid), pase, str(d.get("detalle") or "")[:200])
    if codigo != 200:
        return codigo, datos
    return persona(P, viewer, int(uid))


def baneos(P, viewer, ahora=None):
    """★ 20-nov: GET /api/baneos — los baneos VIGENTES de los juegos que esa cuenta ve (permanentes y con fecha),
    los que vencen antes primero. ⛔ Al moderador: ni logins ni cuentas con rol (como en todo el panel)."""
    ahora = int(time.time() if ahora is None else ahora)
    admin = _es_admin(P, viewer)
    admins_login = {P._login_de(u) for u in P.admins()} - {None}
    filas = P._propia().execute("SELECT uid, juego, desde, quien, motivo, hasta FROM baneos "
                                "WHERE hasta IS NULL OR hasta > ? ORDER BY hasta IS NULL, hasta, desde DESC LIMIT 500",
                                (ahora,)).fetchall()
    out = []
    for f in filas:
        if not P.puede_en(viewer, f["juego"]):
            continue
        if not admin and P.rol_de(f["uid"]) is not None:
            continue
        g = dict({"uid": int(f["uid"]), "persona": _nombre(P, f["uid"]), "pase": f["juego"],
                  "juego": juego_de_pase(P, f["juego"]), "nombre": P._juegos().get(f["juego"], {}).get("nombre", f["juego"]),
                  "desde": f["desde"], "quien": _quien_para(P, f["quien"], admin, admins_login)}, **P.datos_baneo(f, ahora))
        if admin:
            g["usuario"] = P._login_de(f["uid"]) or ""
        out.append(g)
    return 200, {"ahora": ahora, "baneos": out}


def invitaciones(P, viewer):
    admin = _es_admin(P, viewer)
    out = []
    for f in LZ.pendientes(P):
        if not P.puede_en(viewer, f["juego"]):
            continue
        g = {"id": f["id"], "juego": juego_de_pase(P, f["juego"]), "clave": f["juego"], "nombre_juego": f["nombre_juego"],
             "etiqueta": f["etiqueta"], "uid": f["uid"], "nombre": f["apodo"] or f"Eñeños #{f['uid']}",
             "creada": f["creada"], "vias": _vias(P, f["uid"])}
        if admin:
            g["usuario"] = f["usuario"]
        out.append(g)
    return 200, {"invitaciones": out}


def decidir(P, viewer, d):
    codigo, datos = LZ.decidir(P, viewer, d.get("id"), str(d.get("accion") or ""))
    inv = datos.get("invitacion")
    if isinstance(inv, dict) and not _es_admin(P, viewer):         # ⛔ al moderador, ni el login ni el de quien decidió
        inv.pop("usuario", None)
        admins_login = {P._login_de(u) for u in P.admins()} - {None}
        if inv.get("quien"):
            inv["quien"] = _quien_para(P, inv["quien"], False, admins_login)
    if codigo == 409 and isinstance(datos.get("error"), str) and not _es_admin(P, viewer):
        datos["error"] = "Esa solicitud ya fue decidida."
    return codigo, datos


def lanzamientos(P, viewer, ahora=None):
    ahora = time.time() if ahora is None else ahora
    pend = {}
    for f in LZ.pendientes(P):
        pend[f["juego"]] = pend.get(f["juego"], 0) + 1
    out = []
    for k, v in LZ.tabla(P).items():
        if not P.puede_en(viewer, k):
            continue
        cat = juego_de_pase(P, k)
        j = next((x for x in catalogo(P) if x["id"] == cat), None)
        out.append({"clave": k, "juego": cat, "nombre": (j.get("corto") or j.get("nombre")) if j else v["nombre"],
                    "etiqueta": v.get("etiqueta", ""), "desde": v["desde_t"], "libre": ahora >= v["desde_t"],
                    "pendientes": pend.get(k, 0), "arte": tarjeta(P, j)["arte"] if j else None,
                    "pos": ((j or {}).get("panel") or {}).get("pos") or "50% 50%",
                    "color": ((j or {}).get("panel") or {}).get("color") or "81,216,229"})
    out.sort(key=lambda x: x["desde"])
    return 200, {"ahora": int(ahora), "lanzamientos": out}


def _quien_para(P, quien, admin, admins_login):
    """El autor de una línea de la auditoría, como lo ve cada uno. ⛔ Al moderador: nunca el login (sale el Ñ2-ID o
    «Eñeños #id») y los ADMIN, la consola y lo interno salen «ADMIN»."""
    q = str(quien or "")
    if admin:
        return q
    if q in admins_login or q.startswith(("consola", "interno", "uid ")):
        return "ADMIN"
    r = P._cuentas().execute("SELECT uid FROM cuentas WHERE usuario = ? COLLATE BINARY", (q,)).fetchone()
    return _nombre(P, r["uid"]) if r else "—"


def auditoria(P, viewer, limite=60):
    admin = _es_admin(P, viewer)
    admins_login = {P._login_de(u) for u in P.admins()} - {None}
    filas = P._propia().execute("SELECT id, cuando, quien, accion, uid, juego, detalle FROM auditoria "
                                "ORDER BY id DESC LIMIT ?", (500 if not admin else int(limite),)).fetchall()
    out = []
    for f in filas:
        if not admin:
            if f["accion"] not in MOVIMIENTOS or not f["juego"] or not P.puede_en(viewer, f["juego"]):
                continue
            if f["uid"] and P.rol_de(f["uid"]) is not None:
                continue
        g = {"id": f["id"], "cuando": f["cuando"], "quien": _quien_para(P, f["quien"], admin, admins_login),
             "accion": f["accion"], "uid": f["uid"], "persona": _nombre(P, f["uid"]) if f["uid"] else "",
             "juego": juego_de_pase(P, f["juego"]) if f["juego"] else None, "pase": f["juego"],
             "detalle": f["detalle"] or ""}
        if admin and f["uid"]:
            g["usuario"] = P._login_de(f["uid"]) or ""
        out.append(g)
        if len(out) >= limite:
            break
    return 200, {"auditoria": out}


def equipo(P, viewer):
    if not _es_admin(P, viewer):
        return 403, {"error": "Sólo un ADMIN maneja el equipo."}
    P.moderadores()
    mapa = dict(P._moderadores.get("mapa", {}))

    def ficha(u, **extra):
        return dict({"uid": int(u), "nombre": _nombre(P, u), "usuario": P._login_de(u) or "", "vias": _vias(P, u),
                     "yo": int(u) == int(viewer)}, **extra)
    adm = [ficha(u, rol="admin") for u in sorted(P.admins())]
    mods = [ficha(u, rol="moderador", juegos=None if js is None else sorted(js))
            for u, js in sorted(mapa.items()) if u not in P.admins()]
    return 200, {"admins": adm, "moderadores": mods,
                 "juegos": [{"id": j["id"], "nombre": j.get("corto") or j.get("nombre"),
                             "color": (j.get("panel") or {}).get("color") or "81,216,229"} for j in catalogo(P)]}


def cambiar_equipo(P, viewer, d):
    """POST /api/equipo {accion: juegos | agregar | quitar, uid, juegos: [...]} — sólo ADMIN, todo a la auditoría."""
    if not _es_admin(P, viewer):
        return 403, {"error": "Sólo un ADMIN maneja el equipo."}
    acc = str(d.get("accion") or "")
    crudo = str(d.get("uid") if d.get("uid") is not None and not isinstance(d.get("uid"), bool) else "").strip().lstrip("#")
    if not crudo.isdigit() or len(crudo) > 12:
        return 400, {"error": "Escriba el Eñeños ID (el número)."}
    uid = int(crudo)
    ids = {j["id"] for j in catalogo(P)}
    js = d.get("juegos") if d.get("juegos") is not None else []
    if not isinstance(js, list) or len(js) > 30 or not all(isinstance(x, str) and x in ids for x in js):
        return 400, {"error": "Esos juegos no están en el catálogo."}
    r = P._cuentas().execute("SELECT estado FROM cuentas WHERE uid = ?", (uid,)).fetchone()
    if not r:
        return 404, {"error": "Esa persona no existe."}
    if uid in P.admins():
        return 409, {"error": "Esa cuenta es ADMIN (se maneja en admin.txt, a mano)."}
    es_mod = uid in P.moderadores()
    aviso = ""
    if acc == "agregar":
        if es_mod:
            return 409, {"error": "Ya está en el equipo: cambie sus juegos."}
        if r["estado"] != "activa":
            return 409, {"error": "Esa cuenta no está activa."}
        P.escribir_moderador(uid, js, P._login_de(viewer) or "")
        P._auditar(viewer, "equipo: agregar moderador", uid, None, ",".join(sorted(js)) or "sin juegos")
        if not _vias(P, uid):
            aviso = "Todavía no tiene Discord ni Google vinculado: no podrá entrar hasta vincular uno."
    elif acc == "juegos":
        if not es_mod:
            return 404, {"error": "Esa cuenta no es moderadora."}
        P.escribir_moderador(uid, js, P._login_de(viewer) or "")
        P._auditar(viewer, "equipo: juegos del moderador", uid, None, ",".join(sorted(js)) or "ninguno")
    elif acc == "quitar":
        if not es_mod:
            return 404, {"error": "Esa cuenta no es moderadora."}
        P.escribir_moderador(uid, False, P._login_de(viewer) or "")
        P._auditar(viewer, "equipo: quitar moderador", uid, None, "")
    else:
        return 400, {"error": "Acción desconocida."}
    codigo, datos = equipo(P, viewer)
    if aviso:
        datos["aviso"] = aviso
    return codigo, datos


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  HTTP (lo llama el manejador del portero: `H` es el pedido, con `_mandar` e `_ip`)
# ══════════════════════════════════════════════════════════════════════════════════════════════
def _cookie(H, nombre):
    for trozo in (H.headers.get("Cookie") or "").split(";"):
        k, _, v = trozo.strip().partition("=")
        if k == nombre:
            return v.strip()
    return ""


def poner_cookie(nombre, valor, segundos):
    return ("Set-Cookie", f"{nombre}={valor}; Path=/; Max-Age={int(segundos)}; HttpOnly; Secure; SameSite=Strict")


def _archivo(H, ruta, cache):
    ext = os.path.splitext(ruta)[1].lower()
    if ext not in _TIPOS or not os.path.isfile(ruta):
        return H._mandar(404, {"error": "no existe"})
    with open(ruta, "rb") as f:
        datos = f.read()
    return H._mandar(200, datos, cache=cache, tipo=_TIPOS[ext], extra=_SEGURIDAD)


def _estatico(P, H, p):
    """La página y lo suyo. ⛔ Sólo nombres simples (sin `..`, sin `/` raros) y sólo los tipos de `_TIPOS`."""
    if p in ([], ["entrar"]):
        if not p and not H.path.split("?", 1)[0].endswith("/"):
            return H._mandar(301, b"", extra=(("Location", H.path.split("?", 1)[0] + "/"),))
        return _archivo(H, os.path.join(_DIR_PANEL, "index.html"), "no-store")
    if p in (["panel.js"], ["panel.css"]):
        return _archivo(H, os.path.join(_DIR_PANEL, p[0]), "no-cache")
    if not all(_NOMBRE_ARCHIVO.match(x) for x in p[1:]) or len(p) < 2:
        return H._mandar(404, {"error": "no existe"})
    if p[0] == "assets" and len(p) <= 3:
        return _archivo(H, os.path.join(_DIR_PANEL, "assets", *p[1:]), "public, max-age=86400")
    if p[0] == "arte" and len(p) == 2:
        return _archivo(H, os.path.join(_dir_arte(P), p[1]), "public, max-age=3600")
    return H._mandar(404, {"error": "no existe"})


def atender(P, H, metodo, p, d):
    """Todo `/coordinador/…`. `p` = las partes de la ruta después de `coordinador`."""
    if not P.es_duena():
        return H._mandar(404, {"error": "no existe"})
    if not p or p[0] != "api":
        if metodo != "GET":
            return H._mandar(404, {"error": "no existe"})
        return _estatico(P, H, p)
    api = p[1:]
    q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(H.path).query).items()}
    ip = H._ip()
    if metodo == "GET" and api == ["estado"]:
        uid = P.admin_de(_cookie(H, COOKIE))
        return H._mandar(200, {"proveedores": V.proveedores(), "configurado": bool(destinos()),
                               "sesion": sesion_info(P, uid) if uid else None})
    if metodo == "GET" and api == ["catalogo"]:
        return H._mandar(200, {"juegos": [tarjeta(P, j) for j in catalogo(P)]})
    if metodo == "POST" and api == ["oauth"]:
        codigo, datos, nav = iniciar(P, str(d.get("proveedor") or ""), d.get("destino"), ip)
        extra = (poner_cookie(COOKIE_FLUJO, nav, V.SID_VIDA),) if nav else ()
        return H._mandar(codigo, datos, extra=extra)
    if metodo == "POST" and api == ["canjear"]:
        codigo, datos, token = canjear(P, d.get("ticket"), _cookie(H, COOKIE_FLUJO), ip)
        extra = [poner_cookie(COOKIE_FLUJO, "", 0)]
        if token:
            extra.append(poner_cookie(COOKIE, token, P.ADMIN_HORAS * 3600))
        return H._mandar(codigo, datos, extra=tuple(extra))
    if metodo == "POST" and api == ["salir"]:
        P.admin_salir(_cookie(H, COOKIE))
        return H._mandar(200, {"ok": True}, extra=(poner_cookie(COOKIE, "", 0),))
    viewer = P.admin_de(_cookie(H, COOKIE))                          # ⛔ re-chequea el rol en CADA pedido
    if not viewer:
        return H._mandar(401, {"error": "Tiene que entrar con Discord o Google."})
    if metodo == "GET":
        if api == ["juegos"]:
            return H._mandar(*juegos(P, viewer))
        if api == ["personas"]:
            return H._mandar(*buscar(P, viewer, q.get("q")))
        if len(api) == 2 and api[0] == "persona":
            return H._mandar(*persona(P, viewer, api[1]))
        if api == ["invitaciones"]:
            return H._mandar(*invitaciones(P, viewer))
        if api == ["lanzamientos"]:
            return H._mandar(*lanzamientos(P, viewer))
        if api == ["auditoria"]:
            return H._mandar(*auditoria(P, viewer))
        if api == ["baneos"]:
            return H._mandar(*baneos(P, viewer))
        if api == ["equipo"]:
            return H._mandar(*equipo(P, viewer))
        return H._mandar(404, {"error": "no existe"})
    if api == ["accion"]:
        return H._mandar(*accion(P, viewer, d))
    if api == ["invitacion"]:
        return H._mandar(*decidir(P, viewer, d))
    if api == ["equipo"]:
        return H._mandar(*cambiar_equipo(P, viewer, d))
    return H._mandar(404, {"error": "no existe"})
