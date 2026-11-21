# -*- coding: utf-8 -*-
"""gestion — ★ 20-nov-2026, FASE C del panel del Coordinador: la GESTIÓN de cada juego (tablero, fichas, acciones).

Benja: *«la gestión de X juego»* · y para los moderadores *«con cupo y permisos asignables para X acción también»*.

CÓMO
- El panel le habla al server del juego por la red de adentro, con la ficha interna: `R2_PANEL_GESTION` =
  «pase=http://…/api/interno/panel;…». En R2Beat esa puerta corre el PANEL VIEJO entero como un actor externo
  (`panel_admin.con_externo`): nada se reescribe, y su auditoría dice «coordinador:<login>».
- ⛔ LISTA CERRADA: sólo pasan las rutas de `RUTAS` (método + forma). Lo demás, 404 — también para un ADMIN.
- QUIÉN PUEDE QUÉ (lo decide el Coordinador, el juego sólo ejecuta):
    · ADMIN: todo lo de la lista, sin cupo.
    · MODERADOR con ese juego asignado: lo de BASE (mirar, avisar, echar, sacar el chat) + las acciones que un ADMIN le
      asignó para ESE juego (`ASIGNABLES`), cada una con su cupo si lo tiene (Rcoin, EXP).
    · moderador de formato viejo (sin juegos) o sin ese juego: nada.
- CUPOS: por moderador y por juego, en `portero.db` (`permisos_juego`). Se RESERVA antes de mandar (atómico: nunca
  pasa del cupo aunque mande dos a la vez) y se DEVUELVE si el juego dice que no. El moderador sólo SUMA o RESTA
  («poner» un valor fijo es de ADMIN: podría saltarse el cupo). Restar no gasta cupo.
- PRIVACIDAD: a un moderador nunca le llega una IP, un login ni con quién comparte IP (`_SIN_PRIVADOS`).
- ★ 20-nov (Benja: «GunBound y EDA… haz ambos a la vez; cuando maduren se editarán sus secciones»): DOS TIPOS de
  servidor. «r2beat» = el panel viejo de R2Beat (`RUTAS`). «contrato1» = el CONTRATO común de los juegos nuevos
  (`documentacion/CONTRATO_PANEL.md`, `RUTAS_CONTRATO1`): capacidades, salud, conectados, buscar, ficha, aviso,
  echar y moneda. En `R2_PANEL_GESTION` el tipo va delante de la URL: «gunbound=contrato1:http://…/interno/panel».
  La acción asignable «moneda» lleva un cupo POR MONEDA (oro, cash…), guardado en `permisos_juego.monedas`.
- ★ 20-nov: la acción asignable «torneos» no tiene ruta acá: la usa `torneos.py` (su propia puerta del juego,
  `R2_PANEL_TORNEOS`). Se asigna como las demás, por moderador y por juego.
- ★ 21-nov (Benja: «quiero el permiso asignable» de restablecer contraseña): los permisos de TODA LA RED (la cuenta
  Eñeños, no un juego) van en la fila `juego = "_red"` de la misma tabla. Hoy: «clave» (portero.admin_restablecer_clave,
  nunca a una cuenta del equipo). `puede_red()` lo consulta.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 10

BASE = ("ver", "aviso", "echar", "mute")
# acción asignable -> (texto para el panel, cupo que gasta o None)
ASIGNABLES = {
    "rcoin": ("Dar o quitar Rcoin", "rcoin"),
    "exp": ("Dar o quitar EXP", "exp"),
    "item/dar": ("Dar ítems", None),
    "item/quitar": ("Quitar ítems", None),
    "apodo": ("Cambiar el apodo", None),
    "gorila": ("Monedas gorila", None),
    "chat": ("Leer el chat público guardado", None),
    "moneda": ("Dar o quitar monedas del juego", "moneda"),     # ★ contrato1: con cupo por moneda
    "torneos": ("Manejar los torneos", None),                     # ★ 20-nov: torneos.py (crear, estados, la llave)
    "clave": ("Restablecer contraseña", None),                    # ★ 21-nov: de TODA LA RED (fila `_red`)
}
RED = "_red"                       # la «fila» de los permisos de toda la red (la cuenta Eñeños, no un juego)
ASIGNABLES_RED = ("clave",)
# lo que se puede asignar en cada tipo de servidor
ASIGNABLES_DE = {"r2beat": ("rcoin", "exp", "item/dar", "item/quitar", "apodo", "gorila", "chat", "torneos"),
                 "contrato1": ("moneda",)}
_MONEDA_ID = re.compile(r"^[a-z0-9_]{1,20}$")
CUPOS = ("rcoin", "exp")
CUPO_MAX = 100_000_000

_N = r"\d{1,12}"
# (método, regex de la ruta) -> acción que pide
RUTAS = [
    ("GET", r"salud", "ver"),
    ("GET", r"conectados", "ver"),
    ("GET", r"salas", "ver"),
    ("GET", r"usuarios", "ver"),
    ("GET", rf"usuario/{_N}", "ver"),
    ("GET", rf"usuario/{_N}/historia", "ver"),
    ("GET", rf"usuario/{_N}/dia", "ver"),
    ("GET", r"catalogo", "ver"),
    ("GET", r"muteos", "ver"),
    ("GET", r"alertas", "ver"),
    ("GET", r"chat", "chat"),
    ("POST", r"aviso", "aviso"),
    ("POST", rf"usuario/{_N}/echar", "echar"),
    ("POST", rf"usuario/{_N}/mute", "mute"),
    ("POST", rf"usuario/{_N}/desmute", "mute"),
    ("POST", rf"usuario/{_N}/rcoin", "rcoin"),
    ("POST", rf"usuario/{_N}/exp", "exp"),
    ("POST", rf"usuario/{_N}/item/dar", "item/dar"),
    ("POST", rf"usuario/{_N}/item/quitar", "item/quitar"),
    ("POST", rf"usuario/{_N}/apodo", "apodo"),
    ("POST", rf"usuario/{_N}/gorila", "gorila"),
]
_RUTAS = [(m, re.compile(r"^" + p + r"$"), a) for m, p, a in RUTAS]
_ID = r"[A-Za-z0-9_.-]{1,40}"
RUTAS_CONTRATO1 = [
    ("GET", r"capacidades", "ver"),
    ("GET", r"salud", "ver"),
    ("GET", r"conectados", "ver"),
    ("GET", r"buscar", "ver"),
    ("GET", rf"ficha/{_ID}", "ver"),
    ("POST", r"aviso", "aviso"),
    ("POST", r"echar", "echar"),
    ("POST", r"moneda", "moneda"),
]
_RUTAS_DE = {"r2beat": _RUTAS, "contrato1": [(m, re.compile(r"^" + p + r"$"), a) for m, p, a in RUTAS_CONTRATO1]}
_SIN_PRIVADOS = frozenset({"ip", "ips", "login", "username", "misma_ip", "comparte_ip", "correo", "email", "geoip"})

ESQUEMA = """
CREATE TABLE IF NOT EXISTS permisos_juego (
    uid        INTEGER NOT NULL,          -- el Eñeños ID del moderador
    juego      TEXT NOT NULL,             -- el id del catálogo (r2beat2013, gunbound…)
    acciones   TEXT NOT NULL DEFAULT '[]',
    cupo_rcoin INTEGER NOT NULL DEFAULT 0,
    cupo_exp   INTEGER NOT NULL DEFAULT 0,
    dado_rcoin INTEGER NOT NULL DEFAULT 0,
    dado_exp   INTEGER NOT NULL DEFAULT 0,
    cambiado   TEXT,
    quien      TEXT,
    monedas    TEXT NOT NULL DEFAULT '{}',   -- ★ contrato1: {"oro": {"cupo": n, "dado": n}, …}
    PRIMARY KEY (uid, juego)
);
"""
_tabla_ok = set()
_lock = threading.Lock()


def _con(P):
    c = P._propia()
    if id(c) not in _tabla_ok:
        c.executescript(ESQUEMA)
        if "monedas" not in {r[1] for r in c.execute("PRAGMA table_info(permisos_juego)")}:   # (la tabla del 20-nov)
            c.execute("ALTER TABLE permisos_juego ADD COLUMN monedas TEXT NOT NULL DEFAULT '{}'")
            c.commit()
        _tabla_ok.add(id(c))
    return c


# ── la red de adentro ─────────────────────────────────────────────────────────────────────────────
def fuentes():
    """{pase: (tipo, url)}. «pase=http://…» = el panel viejo de R2Beat · «pase=contrato1:http://…» = el contrato."""
    out = {}
    for parte in (os.environ.get("R2_PANEL_GESTION") or "").split(";"):
        if "=" in parte:
            p, u = parte.split("=", 1)
            u = u.strip()
            tipo = "r2beat"
            if u.startswith("contrato1:"):
                tipo, u = "contrato1", u[len("contrato1:"):]
            if p.strip() and u.startswith(("http://", "https://")):
                out[p.strip()] = (tipo, u.rstrip("/"))
    return out


def tipo_de(CO, P, jid):
    """El tipo de servidor de ese juego («r2beat» / «contrato1»), o None si ningún servidor suyo se gestiona."""
    for p, (tipo, _u) in fuentes().items():
        if CO.juego_de_pase(P, p) == jid:
            return tipo
    return None


def _http(url, ruta, query, cuerpo, quien, admin):
    ficha = (os.environ.get("R2_CUENTAS_FICHA_INTERNA") or "").strip()
    if not ficha:
        return 503, {"error": "Falta la ficha interna: este servidor no se puede gestionar."}
    cab = {"X-Ficha-Interna": ficha, "X-Coordinador-Quien": quien, "X-Coordinador-Admin": "1" if admin else "0",
           "User-Agent": "enenos-coordinador", "Content-Type": "application/json"}
    datos = None
    if cuerpo is not None:
        cab["X-R2"] = "1"
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    full = url + "/" + ruta + (("?" + urllib.parse.urlencode(query)) if query else "")
    try:
        with urllib.request.urlopen(urllib.request.Request(full, data=datos, headers=cab), timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read(8 << 20).decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read(65536).decode("utf-8") or "{}")
        except ValueError:
            return e.code, {"error": f"El servidor del juego contestó {e.code}."}
    except (OSError, ValueError):
        return 503, {"error": "El servidor del juego no contesta ahora. Pruebe en un rato."}


def echar_de_los_juegos(eid, pases, quien, motivo=""):
    """★ 21-nov (Benja: «banear no desconecta al usuario»): el baneo vive en Cuenta Eñeños (no le da más pases), pero
    el que YA estaba adentro seguía jugando hasta salir. Después de banear, en cada server baneado que se gestiona se
    buscan los personajes de ESA persona (por su Eñeños ID) y se echa a los que están conectados — con el mismo
    «echar» del panel (R2Beat: `usuarios?q=` + `usuario/N/echar`; contrato: `buscar?q=` + `echar {id}`).
    -> {pase: cuántos echó | "no contesta"}. Los pases sin gestión se saltean (nada que echar)."""
    eid = int(eid)
    fu = fuentes()
    out = {}
    for p in pases:
        if p not in fu:
            continue
        tipo, url = fu[p]
        ruta_b = "usuarios" if tipo == "r2beat" else "buscar"
        cod, d = _http(url, ruta_b, {"q": str(eid)}, None, quien, True)
        if cod != 200:
            out[p] = "no contesta"
            continue
        n = 0
        for f in (d.get("filas") or []) if isinstance(d, dict) else []:
            if not isinstance(f, dict) or f.get("enenos_id") != eid or not f.get("conectado"):
                continue
            if tipo == "r2beat":
                c2, _ = _http(url, f"usuario/{int(f.get('uid') or 0)}/echar", None, {"motivo": str(motivo)[:200]}, quien, True)
            else:
                c2, _ = _http(url, "echar", None, {"id": f.get("id"), "motivo": str(motivo)[:200]}, quien, True)
            n += c2 == 200
        out[p] = n
    return out


def _limpiar(v):
    """Saca lo privado (IP, login…) de una respuesta, en cualquier nivel."""
    if isinstance(v, dict):
        return {k: _limpiar(x) for k, x in v.items() if k not in _SIN_PRIVADOS}
    if isinstance(v, list):
        return [_limpiar(x) for x in v]
    return v


# ── permisos ──────────────────────────────────────────────────────────────────────────────────────
def _juego_ok(CO, P, viewer, jid):
    return P.rol_de(viewer) is not None and any(j["id"] == jid for j in CO.visibles(P, viewer))


def _monedas_de(r):
    try:
        m = json.loads(r["monedas"] or "{}") if r is not None else {}
    except (ValueError, IndexError, KeyError):
        m = {}
    return {k: {"cupo": int(v.get("cupo") or 0), "dado": int(v.get("dado") or 0)}
            for k, v in (m.items() if isinstance(m, dict) else []) if _MONEDA_ID.match(str(k)) and isinstance(v, dict)}


def permisos(P, viewer, jid):
    """{rol, acciones: [...], cupos: {rcoin: {cupo, dado, queda}, exp: …, "moneda:oro": …}} de esa cuenta en ese juego."""
    rol = P.rol_de(viewer)
    if rol == "admin":
        return {"rol": "admin", "acciones": list(BASE) + list(ASIGNABLES), "cupos": None, "poner": True}
    mios = P.juegos_de_moderador(viewer) if rol == "moderador" else None
    if rol != "moderador" or mios is None or jid not in mios:
        return {"rol": rol, "acciones": [], "cupos": None, "poner": False}
    r = _con(P).execute("SELECT * FROM permisos_juego WHERE uid = ? AND juego = ?", (int(viewer), jid)).fetchone()
    extra = [a for a in json.loads(r["acciones"]) if a in ASIGNABLES] if r else []
    cupos = {k: {"cupo": int(r[f"cupo_{k}"]) if r else 0, "dado": int(r[f"dado_{k}"]) if r else 0} for k in CUPOS}
    cupos.update({f"moneda:{k}": v for k, v in _monedas_de(r).items()})
    for c in cupos.values():
        c["queda"] = max(0, c["cupo"] - c["dado"])
    return {"rol": "moderador", "acciones": list(BASE) + extra, "cupos": cupos, "poner": False}


def puede_red(P, uid, accion):
    """★ 21-nov: ¿esta cuenta del equipo puede `accion` de toda la red? ADMIN siempre; MODERADOR si se la asignaron."""
    rol = P.rol_de(uid)
    if rol == "admin":
        return True
    if rol != "moderador" or accion not in ASIGNABLES_RED or P.juegos_de_moderador(uid) is None:
        return False
    r = _con(P).execute("SELECT acciones FROM permisos_juego WHERE uid = ? AND juego = ?", (int(uid), RED)).fetchone()
    try:
        return bool(r) and accion in json.loads(r["acciones"])
    except ValueError:
        return False


def _pide(metodo, ruta, tipo="r2beat"):
    for m, rx, accion in _RUTAS_DE.get(tipo, ()):
        if m == metodo and rx.match(ruta):
            return accion
    return None


def _cupo_de(accion, cuerpo):
    """(cupo, cuánto gasta) de ese pedido, o (None, 0). Sólo SUMAR gasta (restar no)."""
    k = (ASIGNABLES.get(accion) or (None, None))[1]
    if not k:
        return None, 0
    if k == "moneda":                                    # ★ contrato1: {id, moneda, cantidad}
        mid = str(cuerpo.get("moneda") or "")
        if not _MONEDA_ID.match(mid):
            return "moneda:?", 0
        k, campo = f"moneda:{mid}", "cantidad"
    else:
        campo = "valor"
    try:
        v = int(cuerpo.get(campo))
    except (TypeError, ValueError, AttributeError):
        return k, 0
    return k, max(0, v)


def _reservar(P, uid, jid, k, n):
    """Suma `n` a lo dado SI entra en el cupo (en una sola sentencia: dos pedidos a la vez no lo pasan)."""
    if k.startswith("moneda:"):
        return _reservar_moneda(P, uid, jid, k[7:], n)
    with _lock:
        c = _con(P)
        cur = c.execute(f"UPDATE permisos_juego SET dado_{k} = dado_{k} + ? WHERE uid = ? AND juego = ? "
                        f"AND dado_{k} + ? <= cupo_{k}", (n, int(uid), jid, n))
        c.commit()
        return cur.rowcount == 1


def _reservar_moneda(P, uid, jid, mid, n, devolver=False):
    """El cupo de UNA moneda vive en JSON: se lee, se mira y se escribe bajo el candado (un solo proceso)."""
    with _lock:
        c = _con(P)
        r = c.execute("SELECT monedas FROM permisos_juego WHERE uid = ? AND juego = ?", (int(uid), jid)).fetchone()
        if r is None:
            return False
        m = _monedas_de(r)
        if mid not in m:
            return False
        if devolver:
            m[mid]["dado"] = max(0, m[mid]["dado"] - n)
        elif m[mid]["dado"] + n > m[mid]["cupo"]:
            return False
        else:
            m[mid]["dado"] += n
        c.execute("UPDATE permisos_juego SET monedas = ? WHERE uid = ? AND juego = ?", (json.dumps(m), int(uid), jid))
        c.commit()
        return True


def _devolver(P, uid, jid, k, n):
    if k.startswith("moneda:"):
        _reservar_moneda(P, uid, jid, k[7:], n, devolver=True)
        return
    with _lock:
        c = _con(P)
        c.execute(f"UPDATE permisos_juego SET dado_{k} = MAX(0, dado_{k} - ?) WHERE uid = ? AND juego = ?", (n, int(uid), jid))
        c.commit()


# ── el pedido ─────────────────────────────────────────────────────────────────────────────────────
def pedir(CO, P, viewer, jid, entorno, metodo, ruta, query=None, cuerpo=None):
    """-> (código, datos). `ruta` = la del panel del juego (`usuario/123/rcoin`)."""
    if not _juego_ok(CO, P, viewer, jid):
        return 404, {"error": "Ese juego no existe o no está asignado a su cuenta."}
    j = next((x for x in CO.catalogo(P) if x["id"] == jid), None)
    pase = ((j or {}).get("pases") or {}).get(entorno) if entorno in ("live", "test") else None
    fuente = fuentes().get(pase or "")
    if not fuente:
        return 404, {"error": "Este servidor todavía no se puede gestionar desde el Coordinador."}
    tipo, url = fuente
    ruta = str(ruta or "").strip("/")
    accion = _pide(metodo, ruta, tipo)
    if not accion:
        return 404, {"error": "no existe"}
    per = permisos(P, viewer, jid)
    if accion not in per["acciones"]:
        return 403, {"error": "Su cuenta no tiene permiso para esto en este juego. Lo asigna un ADMIN."}
    admin = per["rol"] == "admin"
    cuerpo = cuerpo if isinstance(cuerpo, dict) else ({} if metodo == "POST" else None)
    k, n = (None, 0)
    if metodo == "POST" and not admin:
        if accion in ("rcoin", "exp") and str(cuerpo.get("modo") or "") != "sumar":
            return 403, {"error": "Un moderador sólo suma o resta (poner un valor fijo es de un ADMIN)."}
        k, n = _cupo_de(accion, cuerpo)
        if k and n and not _reservar(P, viewer, jid, k, n):
            q = (per["cupos"].get(k) or {}).get("queda", 0)
            nombre = {"rcoin": "Rcoin", "exp": "EXP"}.get(k, k.split(":", 1)[-1])
            if k.startswith("moneda:") and k not in per["cupos"]:
                return 403, {"error": f"No tiene cupo de «{nombre}» en este juego. Lo asigna un ADMIN."}
            return 403, {"error": f"Eso pasa su cupo de {nombre}: le quedan {q:,}.".replace(",", ".")}
    q = {k2: str(v)[:120] for k2, v in (query or {}).items() if k2 not in ("juego", "entorno")} if metodo == "GET" else None
    quien = "coordinador:" + (P._login_de(viewer) or f"uid {viewer}")
    cod, d = _http(url, ruta, q, cuerpo if metodo == "POST" else None, quien, admin)
    if k and n and cod != 200:
        _devolver(P, viewer, jid, k, n)
    if metodo == "POST" and cod == 200:
        P._auditar(viewer, f"gestión · {accion}", None, pase, ruta[:120])
    if not admin:
        d = _limpiar(d)
    if metodo == "POST" and k:
        d = dict(d, cupos=permisos(P, viewer, jid)["cupos"])
    return cod, d


# ── el ADMIN reparte permisos y cupos ─────────────────────────────────────────────────────────────
def ver_permisos(CO, P, viewer):
    """GET /api/gestion/permisos (ADMIN): por moderador y juego, sus acciones y cupos. Más el catálogo de acciones."""
    if P.rol_de(viewer) != "admin":
        return 403, {"error": "Sólo un ADMIN reparte permisos."}
    filas = _con(P).execute("SELECT * FROM permisos_juego").fetchall()
    out = [{"uid": int(r["uid"]), "juego": r["juego"], "acciones": [a for a in json.loads(r["acciones"]) if a in ASIGNABLES],
            "cupo_rcoin": int(r["cupo_rcoin"]), "cupo_exp": int(r["cupo_exp"]), "dado_rcoin": int(r["dado_rcoin"]),
            "dado_exp": int(r["dado_exp"]), "monedas": _monedas_de(r), "cambiado": r["cambiado"] or "",
            "quien": r["quien"] or ""} for r in filas]
    tipos = {}
    for p, (tipo, _u) in fuentes().items():
        jid = CO.juego_de_pase(P, p)
        if jid:
            tipos[jid] = tipo
    return 200, {"permisos": out, "base": list(BASE),
                 "asignables": [{"id": k, "nombre": v[0], "cupo": v[1]} for k, v in ASIGNABLES.items()],
                 "asignables_de": {jid: list(ASIGNABLES_DE[t]) for jid, t in tipos.items()},
                 "asignables_red": [{"id": k, "nombre": ASIGNABLES[k][0]} for k in ASIGNABLES_RED],
                 "gestionables": sorted(tipos)}


def poner_permisos(CO, P, viewer, d):
    """POST /api/gestion/permisos {uid, juego, acciones, cupo_rcoin, cupo_exp, cupos_monedas?: {oro: n}, reiniciar_dado?}
    (ADMIN). Sólo se asigna lo que ese tipo de servidor tiene (`ASIGNABLES_DE`)."""
    if P.rol_de(viewer) != "admin":
        return 403, {"error": "Sólo un ADMIN reparte permisos."}
    d = d if isinstance(d, dict) else {}
    try:
        uid = int(str(d.get("uid")).lstrip("#"))
    except (TypeError, ValueError):
        return 400, {"error": "Cuenta inválida."}
    jid = str(d.get("juego") or "")
    if P.rol_de(uid) != "moderador":
        return 404, {"error": "Esa cuenta no es moderadora."}
    mios = P.juegos_de_moderador(uid)
    if jid == RED:                                   # ★ 21-nov: lo de toda la red (no hace falta un juego asignado)
        if mios is None:
            return 409, {"error": "Es un moderador de formato viejo: asígnele sus juegos primero."}
        acc = d.get("acciones") or []
        if not isinstance(acc, list) or not all(isinstance(a, str) and a in ASIGNABLES_RED for a in acc):
            return 400, {"error": "Acciones de toda la red: " + " · ".join(ASIGNABLES_RED)}
        d = {"acciones": acc}                        # (sin cupos)
    elif mios is None or jid not in mios:
        return 409, {"error": "Primero asígnele ese juego en el equipo."}
    acc = d.get("acciones") or []
    validas = ASIGNABLES_RED if jid == RED else ASIGNABLES_DE.get(tipo_de(CO, P, jid) or "", ())
    if not isinstance(acc, list) or not all(isinstance(a, str) and a in validas for a in acc):
        return 400, {"error": "Acciones de este juego: " + (" · ".join(validas) or "ninguna (todavía no se gestiona)")}
    cm = d.get("cupos_monedas") or {}
    if not isinstance(cm, dict) or len(cm) > 10 or not all(_MONEDA_ID.match(str(k)) for k in cm):
        return 400, {"error": "Cupos de monedas: {moneda: cupo}."}
    cupos_m = {}
    for k, v in cm.items():
        try:
            v = int(v or 0)
        except (TypeError, ValueError):
            return 400, {"error": f"El cupo de {k} tiene que ser un número."}
        if not 0 <= v <= CUPO_MAX:
            return 400, {"error": f"El cupo de {k}: entre 0 y {CUPO_MAX:,}.".replace(",", ".")}
        cupos_m[str(k)] = v
    cupos = {}
    for k in CUPOS:
        try:
            v = int(d.get(f"cupo_{k}") or 0)
        except (TypeError, ValueError):
            return 400, {"error": f"El cupo de {k} tiene que ser un número."}
        if not 0 <= v <= CUPO_MAX:
            return 400, {"error": f"El cupo de {k}: entre 0 y {CUPO_MAX:,}.".replace(",", ".")}
        cupos[k] = v
    reiniciar = bool(d.get("reiniciar_dado"))
    with _lock:
        c = _con(P)
        antes = _monedas_de(c.execute("SELECT monedas FROM permisos_juego WHERE uid = ? AND juego = ?", (uid, jid)).fetchone())
        monedas = {k: {"cupo": v, "dado": 0 if reiniciar else antes.get(k, {}).get("dado", 0)} for k, v in cupos_m.items()}
        c.execute("INSERT INTO permisos_juego (uid, juego, acciones, cupo_rcoin, cupo_exp, cambiado, quien, monedas) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(uid, juego) DO UPDATE SET acciones = excluded.acciones, "
                  "cupo_rcoin = excluded.cupo_rcoin, cupo_exp = excluded.cupo_exp, cambiado = excluded.cambiado, "
                  "quien = excluded.quien, monedas = excluded.monedas" + (", dado_rcoin = 0, dado_exp = 0" if reiniciar else ""),
                  (uid, jid, json.dumps(sorted(set(acc))), cupos["rcoin"], cupos["exp"],
                   time.strftime("%Y-%m-%d %H:%M:%S"), P._login_de(viewer) or "", json.dumps(monedas)))
        c.commit()
    P._auditar(viewer, "equipo: permisos del moderador", uid, jid,
               f"{','.join(sorted(set(acc))) or 'sólo base'} · cupo Rcoin {cupos['rcoin']} · EXP {cupos['exp']}"
               + "".join(f" · {k} {v}" for k, v in sorted(cupos_m.items()))
               + (" · cupo reiniciado" if reiniciar else ""))
    return ver_permisos(CO, P, viewer)
