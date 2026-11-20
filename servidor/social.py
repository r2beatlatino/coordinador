# -*- coding: utf-8 -*-
"""social — AMIGOS, ESTADO y CHAT de la plataforma Eñeños (16-nov-2026, Benja). Parte del portero (Cuenta Eñeños
dueña, `R2_CUENTAS_DUENA=1`): los amigos son de la PERSONA (Eñeños ID), no de un personaje.

QUÉ PIDIÓ BENJA
    «estado de amigos "jugando - r2beat" o X juego, sala, canción, dificultad, lo más compacto posible (tipo rich
    presence de Discord y la mensajería de Riot) · "en launcher", desconectado · los chats se guardan máximo 2 días,
    sólo texto · cargar el estado de otros juegos como EDA o Gunbound según lo que se pueda leer de su contenedor».

EL NOMBRE: un APODO público (lo elige cada uno). ⛔ El nombre de usuario (login) NUNCA sale de acá: es la mitad de lo
    que se usa para entrar. Se agrega a alguien por apodo o por Eñeños ID. Sin apodo, se ve «Eñeños #<id>».

EL ESTADO (de más a menos preciso)
    1. lo que cuenta el SERVIDOR DEL JUEGO (R2_PRESENCIA: «juego=url;…», cada 5 s, con la ficha interna):
       R2Beat → personaje, canal, sala (número, nombre, canción, dificultad, corriendo, ocupantes)
    2. lo que cuenta el LAUNCHER en su latido («estoy jugando eda»): sirve para los juegos que todavía no cuentan más
    3. «en el launcher» (latido de los últimos 75 s) · 4. desconectado («visto hace …»)

LAS RUTAS (Bearer = la sesión de /entrar)
    POST /social/estado   {desde, juego?}  latido + {yo, amigos[], recibidos[], enviados[], mensajes[] (id > desde), ultimo}
    POST /social/apodo    {apodo}
    POST /social/pedir    {quien}   apodo o Eñeños ID (si el otro ya me había pedido, quedan amigos)
    POST /social/responder {uid, aceptar}  ·  POST /social/quitar {uid}  (amigo o pedido)
    POST /social/enviar   {para, texto}    sólo a amigos; 1–500 caracteres; freno 10 cada 10 s
    POST /social/chat     {con}            los mensajes con esa persona (los de los últimos 2 días), y los marca leídos
⛔ Los mensajes de más de 2 días se BORRAN (cada vez que alguien escribe, y una vez por minuto en el latido).
"""
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

CHAT_VIDA = 2 * 86400
TEXTO_MAX = 500
AMIGOS_MAX = 300
VIDA_LAUNCHER = 75          # sin latido en 75 s = desconectado (el launcher late cada 20 s aunque esté minimizado)
VIDA_JUEGO = 20             # lo que contó el juego vale 20 s (lo pide cada 5)
CADA_JUEGO = 5
FRENO_MSG = (10, 10.0)      # 10 mensajes cada 10 s por persona
ESPERA_MAX = 25            # ★ 18-nov: la «espera larga» de mensajes (social.esperar) dura como mucho 25 s
VISTO_CADA = 300            # ★ 18-nov: «visto por última vez» se GUARDA en cuentas.visto, como mucho cada 5 min por persona
#   (Benja: «la marca debe ser la última vez que estuvieron conectados al launcher NUEVO, o al juego: se desconectó
#   cuando»). Sólo eso: el latido del launcher y la presencia que cuenta el juego. NADA sacado de la historia vieja.

NOMBRE_JUEGO = {"r2beat2013": "R2Beat", "r2beat2013-prueba": "R2BeatTS", "eda": "Espada del Alma", "gunbound": "Gunbound", "r2beatnfun": "R2Beat Fun",
                "loveritmo": "Love Ritmo"}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS amistades (
    a       INTEGER NOT NULL,
    b       INTEGER NOT NULL,
    estado  TEXT NOT NULL CHECK (estado IN ('pedido', 'amigos')),
    de      INTEGER NOT NULL,
    creada  TEXT NOT NULL,
    PRIMARY KEY (a, b)
);
CREATE INDEX IF NOT EXISTS amistades_b ON amistades (b);
CREATE TABLE IF NOT EXISTS sincro_amigos (
    juego   TEXT PRIMARY KEY,
    hasta   TEXT NOT NULL             -- «fecha de alta|fila» de la última amistad del juego que se miró
);
CREATE TABLE IF NOT EXISTS mensajes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    de      INTEGER NOT NULL,
    para    INTEGER NOT NULL,
    texto   TEXT NOT NULL,
    cuando  INTEGER NOT NULL,
    leido   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS mensajes_para ON mensajes (para, id);
CREATE INDEX IF NOT EXISTS mensajes_de ON mensajes (de, id);
CREATE INDEX IF NOT EXISTS mensajes_cuando ON mensajes (cuando);
"""


def preparar(c):
    """Las tablas y la columna `apodo` en `cuentas.db` (idempotente; lo llama `portero._cuentas`)."""
    c.executescript(ESQUEMA)
    cols = [r[1] for r in c.execute("PRAGMA table_info(cuentas)")]
    if "apodo" not in cols:
        c.execute("ALTER TABLE cuentas ADD COLUMN apodo TEXT")
    # ★ la CLAVE del apodo (sin mayúsculas, también en «Ñ»/«ñ»: el NOCASE de SQLite sólo pliega el inglés)
    if "apodo_clave" not in cols:
        c.execute("ALTER TABLE cuentas ADD COLUMN apodo_clave TEXT")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS cuentas_apodo_clave ON cuentas (apodo_clave)")
    # ★ 18-nov (Benja: «última vez conectado de los amigos»): antes vivía sólo en memoria y se perdía al reiniciar
    if "visto" not in cols:
        c.execute("ALTER TABLE cuentas ADD COLUMN visto INTEGER")


# ── el estado ──────────────────────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_latidos = {}               # uid -> {"t", "juego"}
_en_juego = {}              # eid -> {"t", "juego", ...lo que contó el juego}
_hilo = {"vivo": False, "purga": 0.0}
_freno = {}                 # uid -> [t, ...]
_visto_escrito = {}         # uid -> cuándo se guardó su `visto` por última vez
_aviso = threading.Condition()   # ★ 18-nov: `enviar` despierta a quien espera (social.esperar)
_buzon = {}                 # uid -> id del último mensaje que le llegó (desde que arrancó el proceso)


def _fuentes():
    """R2_PRESENCIA = «r2beat2013=http://r2beat2013:48190/api/interno/presencia;eda=…»"""
    out = []
    for parte in (os.environ.get("R2_PRESENCIA") or "").split(";"):
        if "=" in parte:
            j, u = parte.split("=", 1)
            if j.strip() and u.strip().startswith(("http://", "https://")):
                out.append((j.strip(), u.strip()))
    return out


def leer_juegos(P, ahora=None):
    """Una vuelta: le pregunta a cada juego quién está y dónde. (El hilo la repite cada 5 s.)"""
    ahora = time.time() if ahora is None else ahora
    ficha = (os.environ.get("R2_CUENTAS_FICHA_INTERNA") or "").strip()
    vistos = []
    for juego, url in _fuentes():
        try:
            req = urllib.request.Request(url, headers={"X-Ficha-Interna": ficha, "User-Agent": "enenos-cuentas"})
            with urllib.request.urlopen(req, timeout=3) as r:
                d = json.loads(r.read().decode("utf-8"))
        except Exception:                                              # noqa: BLE001 — ese juego no contesta: queda el resto
            continue
        try:
            traer_amistades(P, juego, url, ficha)
        except Exception as e:                                         # noqa: BLE001 — sin amistades no se cae la presencia
            P._log(f"⚠ amistades de {juego}: {e!r}")
        with _lock:
            for j in d.get("jugadores") or []:
                try:
                    eid = int(j.get("eid"))
                except (TypeError, ValueError):
                    continue
                _en_juego[eid] = {"t": ahora, "juego": juego, "personaje": str(j.get("personaje") or "")[:24],
                                  "canal": str(j.get("canal") or "")[:16], "sala": j.get("sala")}
                vistos.append(eid)
    anotar_visto(P, vistos, ahora)


def traer_amistades(P, juego, url_presencia, ficha):
    """★ 18-nov (Benja: «agregar amigo desde el juego agrega al amigo también al launcher»; por ahora R2Beat): le pide
    al juego las amistades nuevas desde la última fila que vio (`sincro_amigos`) y las suma como «amigos» (un pedido
    pendiente entre los dos también pasa a amigos). Borrar NO viaja. Devuelve cuántas sumó."""
    url = url_presencia.rsplit("/presencia", 1)[0] + "/amistades"
    c = P._cuentas()
    f = c.execute("SELECT hasta FROM sincro_amigos WHERE juego = ?", (juego,)).fetchone()
    if f is not None:
        url += "?desde=" + urllib.parse.quote(str(f["hasta"]), safe="")
    req = urllib.request.Request(url, headers={"X-Ficha-Interna": ficha, "User-Agent": "enenos-cuentas"})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:          # ese juego todavía no tiene /amistades (o no es R2Beat): nada, sin llenar el log
            return 0
        raise
    hasta = str(d.get("hasta") or "")
    pares = d.get("pares") or []
    if not hasta or (f is not None and hasta == str(f["hasta"]) and not pares):
        return 0
    sumadas = 0
    with P._escribir:
        activas = None
        if pares:
            ids = sorted({int(x) for p in pares for x in p})
            marcas = ",".join("?" * len(ids))
            activas = {int(r[0]) for r in c.execute(f"SELECT uid FROM cuentas WHERE estado = 'activa' AND uid IN ({marcas})", ids)}
        for p in pares:
            a, b = _par(int(p[0]), int(p[1]))
            if a == b or a not in activas or b not in activas:
                continue
            e = c.execute("SELECT estado FROM amistades WHERE a = ? AND b = ?", (a, b)).fetchone()
            if e is None:
                c.execute("INSERT INTO amistades (a, b, estado, de, creada) VALUES (?, ?, 'amigos', ?, ?)",
                          (a, b, a, P._ahora_txt()))
                sumadas += 1
            elif e["estado"] == "pedido":
                c.execute("UPDATE amistades SET estado = 'amigos' WHERE a = ? AND b = ?", (a, b))
                sumadas += 1
        c.execute("INSERT INTO sincro_amigos (juego, hasta) VALUES (?, ?) ON CONFLICT(juego) DO UPDATE SET hasta = excluded.hasta",
                  (juego, hasta))
        c.commit()
    return sumadas


def anotar_visto(P, uids, ahora):
    """Guarda `cuentas.visto` = ahora para esos uids, salvo los que ya se guardaron hace menos de VISTO_CADA (así un
    latido cada 20 s no es una escritura cada 20 s). Nunca lo hace ir para atrás."""
    with _lock:
        toca = [u for u in set(uids) if ahora - _visto_escrito.get(u, 0) >= VISTO_CADA]
        for u in toca:
            _visto_escrito[u] = ahora
    if not toca:
        return 0
    with P._escribir:
        c = P._cuentas()
        c.executemany("UPDATE cuentas SET visto = ? WHERE uid = ? AND (visto IS NULL OR visto < ?)",
                      [(int(ahora), u, int(ahora)) for u in toca])
        c.commit()
    return len(toca)


def con_visto(e, guardado):
    """El estado de un amigo + lo guardado en la base: si está desconectado, «visto» = lo más reciente de los dos."""
    if e.get("tipo") == "desconectado" and guardado and int(guardado) > int(e.get("visto") or 0):
        e = dict(e, visto=int(guardado))
    return e


def _arrancar_hilo(P):
    with _lock:
        if _hilo["vivo"] or not _fuentes():
            return
        _hilo["vivo"] = True

    def bucle():
        while True:
            try:
                leer_juegos(P)
            except Exception as e:                                     # noqa: BLE001
                P._log(f"⚠ presencia: {e!r}")
            time.sleep(CADA_JUEGO)
    threading.Thread(target=bucle, daemon=True, name="presencia").start()


def estado_de(uid, ahora):
    """{tipo: jugando|launcher|desconectado, juego, nombre_juego, personaje, canal, sala, visto}"""
    with _lock:
        g = _en_juego.get(uid)
        lat = _latidos.get(uid)
    if g and ahora - g["t"] <= VIDA_JUEGO:
        return {"tipo": "jugando", "juego": g["juego"], "nombre_juego": NOMBRE_JUEGO.get(g["juego"], g["juego"]),
                "personaje": g["personaje"], "canal": g["canal"], "sala": g["sala"]}
    if lat and ahora - lat["t"] <= VIDA_LAUNCHER:
        if lat.get("juego"):
            return {"tipo": "jugando", "juego": lat["juego"], "nombre_juego": NOMBRE_JUEGO.get(lat["juego"], lat["juego"])}
        return {"tipo": "launcher"}
    visto = max((lat or {}).get("t", 0), (g or {}).get("t", 0))
    return {"tipo": "desconectado", "visto": int(visto) if visto else None}


# ── ayudas ─────────────────────────────────────────────────────────────────────────────────────
def _par(x, y):
    return (x, y) if x < y else (y, x)


def apodo_valido(t):
    t = unicodedata.normalize("NFC", str(t or "")).strip()
    t = re.sub(r"\s+", " ", t)
    if not (3 <= len(t) <= 16):
        return None
    if not all(ch.isalnum() or ch in " _.-" for ch in t) or not any(ch.isalnum() for ch in t):
        return None
    return t


def clave_apodo(t):
    return unicodedata.normalize("NFC", str(t or "")).strip().casefold()


def _apodo(c, uid):
    r = c.execute("SELECT apodo FROM cuentas WHERE uid = ?", (uid,)).fetchone()
    return (r["apodo"] if r and r["apodo"] else None)


def _mostrar(apodo, uid):
    return apodo or f"Eñeños #{uid}"


def _sesion(P, token, ahora):
    uid = P.sesion_de(token, ahora)
    if not uid or P.estado_r2beat(uid) != "ok":
        return None
    return int(uid)


def _purgar(c, ahora):
    if ahora - _hilo["purga"] < 60:            # (una vez por minuto alcanza)
        return
    _hilo["purga"] = ahora
    c.execute("DELETE FROM mensajes WHERE cuando < ?", (int(ahora - CHAT_VIDA),))


# ── las rutas ──────────────────────────────────────────────────────────────────────────────────
def estado(P, token, desde=0, juego=None, ahora=None):
    ahora = time.time() if ahora is None else ahora
    if not P.es_duena():
        return 404, {"error": "no existe"}
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    _arrancar_hilo(P)
    juego = str(juego or "").strip()[:20] or None
    with _lock:
        _latidos[uid] = {"t": ahora, "juego": juego}
    c = P._cuentas()
    with P._escribir:
        _purgar(c, ahora)
        c.commit()
    anotar_visto(P, [uid], ahora)
    filas = c.execute("""SELECT a, b, estado, de FROM amistades WHERE a = ? OR b = ?""", (uid, uid)).fetchall()
    otros = {(r["b"] if r["a"] == uid else r["a"]): r for r in filas}
    apodos, vistos = {}, {}
    if otros:
        marcas = ",".join("?" * len(otros))
        for r in c.execute(f"SELECT uid, apodo, visto FROM cuentas WHERE uid IN ({marcas})", list(otros)):
            apodos[r["uid"]], vistos[r["uid"]] = r["apodo"], r["visto"]
    no_leidos = {r["de"]: r["n"] for r in c.execute(
        "SELECT de, COUNT(*) n FROM mensajes WHERE para = ? AND leido = 0 GROUP BY de", (uid,))}
    amigos, recibidos, enviados = [], [], []
    for o, r in otros.items():
        item = {"uid": o, "apodo": _mostrar(apodos.get(o), o)}
        if r["estado"] == "amigos":
            amigos.append(dict(item, estado=con_visto(estado_de(o, ahora), vistos.get(o)), no_leidos=no_leidos.get(o, 0)))
        elif r["de"] == uid:
            enviados.append(item)
        else:
            recibidos.append(item)
    orden = {"jugando": 0, "launcher": 1, "desconectado": 2}
    amigos.sort(key=lambda a: (orden.get(a["estado"]["tipo"], 3), a["apodo"].lower()))
    # `desde` AUSENTE = la primera vez (sin historial: el chat se abre con /social/chat); un número (aunque sea 0)
    #   = los mensajes que llegaron después de ese id
    try:
        desde = None if desde is None or desde == "" else int(desde)
    except (TypeError, ValueError):
        desde = None
    ultimo = c.execute("SELECT COALESCE(MAX(id), 0) FROM mensajes").fetchone()[0]
    mensajes = []
    if desde is not None:
        mensajes = [dict(r) for r in c.execute(
            "SELECT id, de, para, texto, cuando FROM mensajes WHERE id > ? AND (para = ? OR de = ?) ORDER BY id LIMIT 200",
            (desde, uid, uid))]
    # ★ «yo.estado»: lo que cuenta el juego de UNO MISMO (lo muestra la presencia de Discord del launcher)
    return 200, {"yo": {"uid": uid, "apodo": _apodo(c, uid), "estado": estado_de(uid, ahora)}, "amigos": amigos, "recibidos": recibidos,
                 "enviados": enviados, "mensajes": mensajes, "ultimo": int(ultimo)}


# ── ★ 18-nov: la mudanza de los AMIGOS del R2Beat viejo ──────────────────────────────────────────────────────
# Benja: «haremos la transformación de cuentas viejas a Eñeños ID; quienes estén agregados en el R2Beat viejo deberán
# estar ya agregados como amigos en Eñeños ID». En el R2Beat viejo la amistad es de PERSONAJE (`friends`, uid ↔
# friend_uid, guardada en los dos sentidos); acá es de PERSONA (Eñeños ID). Cada personaje se lleva a su cuenta de HOY
# (`cuenta_personajes` manda: la mudanza de personajes; si no, el casillero 1 `users.uid`), los borrados no cuentan,
# y la cuenta a su Eñeños ID (`cuentas.usuario`, después de `portero importar`). Quedan como «amigos» (sin pedido),
# una sola vez por par; dos personajes de la misma persona no son «amigos» de sí misma. Sólo cuentas activas.

def _dueno_de_personaje(viejo):
    """uid de personaje -> usuario (login) de la cuenta que lo tiene HOY; sin los borrados."""
    tablas = {r[0] for r in viejo.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    dueno = {int(u): str(n) for u, n in viejo.execute("SELECT uid, username FROM users") if n}
    if "cuenta_personajes" in tablas:
        for n, u in viejo.execute("SELECT username, uid FROM cuenta_personajes"):
            if n and u is not None:
                dueno[int(u)] = str(n)
    if "personajes_borrados" in tablas:
        for (u,) in viejo.execute("SELECT uid FROM personajes_borrados"):
            dueno.pop(int(u), None)
    return dueno


def importar_amistades(P, ruta_vieja, apodos=False, ahora_txt=None):
    """Pasa las amistades de una `datos.db` vieja (SÓLO LECTURA) a `amistades` por Eñeños ID. Idempotente.
    `apodos=True`: además, a quien NO tiene Ñ2-ID le pone el apodo de su personaje del casillero 1 (si es válido y
    nadie más lo tiene). Devuelve el resumen."""
    import sqlite3
    ruta_abs = os.path.abspath(str(ruta_vieja or ""))
    if not os.path.isfile(ruta_abs):
        raise SystemExit(f"⛔ no encuentro la base vieja: {ruta_abs}")
    viejo = sqlite3.connect("file:" + urllib.request.pathname2url(ruta_abs) + "?mode=ro", uri=True, timeout=10)
    try:
        viejo.execute("PRAGMA query_only = 1")
        dueno = _dueno_de_personaje(viejo)
        filas = viejo.execute("SELECT uid, friend_uid, added_at FROM friends").fetchall()
        nick_c1 = {}
        if apodos:
            for u, nick in viejo.execute("SELECT u.username, c.nickname FROM users u JOIN chars c ON c.uid = u.uid"):
                if u and nick:
                    nick_c1[str(u)] = str(nick)
    finally:
        viejo.close()
    ahora_txt = ahora_txt or P._ahora_txt()
    r = {"filas_viejas": len(filas), "pares": 0, "nuevas": 0, "ya_estaban": 0, "pedido_a_amigos": 0,
         "sin_cuenta": 0, "inactivas": 0, "misma_persona": 0, "pasan_el_tope": 0, "apodos_puestos": 0, "apodos_salteados": 0}
    with P._escribir:
        c = P._cuentas()
        cuenta = {str(f["usuario"]): (int(f["uid"]), str(f["estado"]))
                  for f in c.execute("SELECT uid, usuario, estado FROM cuentas")}
        pares = {}
        for u, f, cuando in filas:
            du, df = dueno.get(int(u)), dueno.get(int(f))
            if du is None or df is None or du not in cuenta or df not in cuenta:
                r["sin_cuenta"] += 1
                continue
            (a, ea), (b, eb) = cuenta[du], cuenta[df]
            if ea != "activa" or eb != "activa":
                r["inactivas"] += 1
                continue
            if a == b:
                r["misma_persona"] += 1
                continue
            par = _par(a, b)
            if par not in pares or (cuando and str(cuando) < str(pares[par] or "~")):
                pares[par] = cuando
        r["pares"] = len(pares)
        for (a, b), cuando in sorted(pares.items()):
            f = c.execute("SELECT estado FROM amistades WHERE a = ? AND b = ?", (a, b)).fetchone()
            if f is None:
                c.execute("INSERT INTO amistades (a, b, estado, de, creada) VALUES (?, ?, 'amigos', ?, ?)",
                          (a, b, a, str(cuando or ahora_txt)))
                r["nuevas"] += 1
            elif f["estado"] == "pedido":
                c.execute("UPDATE amistades SET estado = 'amigos' WHERE a = ? AND b = ?", (a, b))
                r["pedido_a_amigos"] += 1
            else:
                r["ya_estaban"] += 1
        # (el tope es para PEDIR más; a quien lo pasa con lo que traía no se le borra nada)
        r["pasan_el_tope"] = c.execute(
            "SELECT COUNT(*) FROM (SELECT x, COUNT(*) n FROM (SELECT a x FROM amistades UNION ALL SELECT b FROM amistades) "
            "GROUP BY x HAVING n > ?)", (AMIGOS_MAX,)).fetchone()[0]
        if apodos:
            for f in c.execute("SELECT uid, usuario FROM cuentas WHERE (apodo IS NULL OR apodo = '') AND estado = 'activa'").fetchall():
                a = apodo_valido(nick_c1.get(str(f["usuario"])))
                # ⛔ el login es PRIVADO: un apodo igual al login (quien se llamó como su usuario) no se pone
                if (not a or clave_apodo(a) == clave_apodo(f["usuario"])
                        or c.execute("SELECT 1 FROM cuentas WHERE apodo_clave = ?", (clave_apodo(a),)).fetchone()):
                    r["apodos_salteados"] += 1
                    continue
                c.execute("UPDATE cuentas SET apodo = ?, apodo_clave = ? WHERE uid = ?", (a, clave_apodo(a), int(f["uid"])))
                r["apodos_puestos"] += 1
        c.commit()
    return r


def poner_apodo(P, token, apodo, ahora=None):
    ahora = time.time() if ahora is None else ahora
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    a = apodo_valido(apodo)
    if not a:
        return 400, {"error": "El Ñ2-ID tiene que tener de 3 a 16 letras, números, espacios, «_», «.» o «-»."}
    c = P._cuentas()
    with P._escribir:
        r = c.execute("SELECT uid FROM cuentas WHERE apodo_clave = ?", (clave_apodo(a),)).fetchone()
        if r and int(r["uid"]) != uid:
            return 409, {"error": "Ese Ñ2-ID ya lo tiene otra persona."}
        c.execute("UPDATE cuentas SET apodo = ?, apodo_clave = ? WHERE uid = ?", (a, clave_apodo(a), uid))
        c.commit()
    return 200, {"ok": True, "apodo": a}


def pedir(P, token, quien, ahora=None):
    ahora = time.time() if ahora is None else ahora
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    q = str(quien or "").strip().lstrip("#")
    c = P._cuentas()
    r = None
    if q.isdigit():
        r = c.execute("SELECT uid, estado FROM cuentas WHERE uid = ?", (int(q),)).fetchone()
    if not r and q:
        r = c.execute("SELECT uid, estado FROM cuentas WHERE apodo_clave = ?", (clave_apodo(q),)).fetchone()
    if not r or r["estado"] != "activa":
        return 404, {"error": "No encontramos a nadie con ese Ñ2-ID o Eñeños ID."}
    otro = int(r["uid"])
    if otro == uid:
        return 400, {"error": "No puede agregarse a usted mismo."}
    a, b = _par(uid, otro)
    with P._escribir:
        f = c.execute("SELECT estado, de FROM amistades WHERE a = ? AND b = ?", (a, b)).fetchone()
        if f and f["estado"] == "amigos":
            return 200, {"ok": True, "estado": "amigos"}
        if f and f["de"] != uid:                       # el otro ya me había pedido: quedamos amigos
            c.execute("UPDATE amistades SET estado = 'amigos' WHERE a = ? AND b = ?", (a, b))
            c.commit()
            return 200, {"ok": True, "estado": "amigos"}
        if f:
            return 200, {"ok": True, "estado": "pedido"}
        n = c.execute("SELECT COUNT(*) FROM amistades WHERE a = ? OR b = ?", (uid, uid)).fetchone()[0]
        if n >= AMIGOS_MAX:
            return 409, {"error": f"Llegó al máximo de {AMIGOS_MAX} amigos y pedidos."}
        c.execute("INSERT INTO amistades (a, b, estado, de, creada) VALUES (?, ?, 'pedido', ?, ?)",
                  (a, b, uid, P._ahora_txt()))
        c.commit()
    return 200, {"ok": True, "estado": "pedido"}


def responder(P, token, otro, aceptar, ahora=None):
    ahora = time.time() if ahora is None else ahora
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    try:
        otro = int(otro)
    except (TypeError, ValueError):
        return 400, {"error": "pedido mal armado"}
    a, b = _par(uid, otro)
    c = P._cuentas()
    with P._escribir:
        f = c.execute("SELECT estado, de FROM amistades WHERE a = ? AND b = ?", (a, b)).fetchone()
        if not f or f["estado"] != "pedido" or f["de"] == uid:
            return 404, {"error": "Ese pedido ya no existe."}
        if aceptar:
            c.execute("UPDATE amistades SET estado = 'amigos' WHERE a = ? AND b = ?", (a, b))
        else:
            c.execute("DELETE FROM amistades WHERE a = ? AND b = ?", (a, b))
        c.commit()
    return 200, {"ok": True}


def quitar(P, token, otro, ahora=None):
    ahora = time.time() if ahora is None else ahora
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    try:
        otro = int(otro)
    except (TypeError, ValueError):
        return 400, {"error": "pedido mal armado"}
    a, b = _par(uid, otro)
    c = P._cuentas()
    with P._escribir:
        c.execute("DELETE FROM amistades WHERE a = ? AND b = ?", (a, b))
        c.commit()
    return 200, {"ok": True}


def _son_amigos(c, x, y):
    a, b = _par(x, y)
    f = c.execute("SELECT estado FROM amistades WHERE a = ? AND b = ?", (a, b)).fetchone()
    return bool(f and f["estado"] == "amigos")


def limpiar_texto(t):
    t = unicodedata.normalize("NFC", str(t or ""))
    t = "".join(ch for ch in t if ch in "\n\t" or unicodedata.category(ch)[0] != "C")   # sin caracteres de control
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:TEXTO_MAX]


def enviar(P, token, para, texto, ahora=None):
    ahora = time.time() if ahora is None else ahora
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    try:
        para = int(para)
    except (TypeError, ValueError):
        return 400, {"error": "pedido mal armado"}
    t = limpiar_texto(texto)
    if not t:
        return 400, {"error": "El mensaje está vacío."}
    with _lock:
        v = [x for x in _freno.get(uid, []) if ahora - x < FRENO_MSG[1]]
        if len(v) >= FRENO_MSG[0]:
            return 429, {"error": "Está escribiendo muy rápido. Espere un momento."}
        if len(_freno) > 50_000:
            _freno.clear()
        _freno[uid] = v + [ahora]
    c = P._cuentas()
    if not _son_amigos(c, uid, para):
        return 403, {"error": "Sólo se puede escribir a los amigos."}
    with P._escribir:
        cur = c.execute("INSERT INTO mensajes (de, para, texto, cuando) VALUES (?, ?, ?, ?)", (uid, para, t, int(ahora)))
        c.execute("DELETE FROM mensajes WHERE cuando < ?", (int(ahora - CHAT_VIDA),))
        c.commit()
    _avisar(para, cur.lastrowid)
    return 200, {"ok": True, "mensaje": {"id": cur.lastrowid, "de": uid, "para": para, "texto": t, "cuando": int(ahora)}}


def _avisar(para, mid):
    with _aviso:
        _buzon[para] = max(_buzon.get(para, 0), int(mid))
        if len(_buzon) > 100_000:
            _buzon.clear()
            _buzon[para] = int(mid)
        _aviso.notify_all()


def esperar(P, token, desde, ahora=None, tope=ESPERA_MAX):
    """★ 18-nov (Benja: «los mensajes llegan con algo de delay»): POST /social/esperar {desde} — la ESPERA LARGA.
    Si ya hay un mensaje para mí después de `desde` (el último id que vio el launcher), contesta enseguida; si no,
    se queda esperando hasta `tope` segundos y `enviar` la despierta apenas me escriben. -> {"hay": bool}.
    El launcher deja siempre una abierta: el mensaje llega al instante, sin preguntar cada 4 s (con 500 jugadores
    eso eran 125 pedidos por segundo). Cada espera es un hilo dormido: no gasta CPU."""
    ahora = time.time() if ahora is None else ahora
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    try:
        desde = int(desde)
    except (TypeError, ValueError):
        return 400, {"error": "pedido mal armado"}
    hay = P._cuentas().execute("SELECT 1 FROM mensajes WHERE para = ? AND id > ? LIMIT 1", (uid, desde)).fetchone()
    if hay:
        return 200, {"hay": True}
    fin = time.monotonic() + max(0.0, min(float(tope), ESPERA_MAX))
    with _aviso:
        while _buzon.get(uid, 0) <= desde:
            resto = fin - time.monotonic()
            if resto <= 0:
                return 200, {"hay": False}
            _aviso.wait(resto)
    return 200, {"hay": True}


def leido(P, token, con, ahora=None):
    """POST /social/leido {con}: el chat con esa persona está abierto y se vio lo último."""
    ahora = time.time() if ahora is None else ahora
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    try:
        con = int(con)
    except (TypeError, ValueError):
        return 400, {"error": "pedido mal armado"}
    c = P._cuentas()
    with P._escribir:
        c.execute("UPDATE mensajes SET leido = 1 WHERE para = ? AND de = ? AND leido = 0", (uid, con))
        c.commit()
    return 200, {"ok": True}


def chat(P, token, con, ahora=None):
    ahora = time.time() if ahora is None else ahora
    uid = _sesion(P, token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    try:
        con = int(con)
    except (TypeError, ValueError):
        return 400, {"error": "pedido mal armado"}
    c = P._cuentas()
    if not _son_amigos(c, uid, con):
        return 403, {"error": "Sólo se puede ver el chat con los amigos."}
    filas = [dict(r) for r in c.execute(
        """SELECT id, de, para, texto, cuando FROM mensajes
           WHERE ((de = ? AND para = ?) OR (de = ? AND para = ?)) AND cuando >= ?
           ORDER BY id DESC LIMIT 100""", (uid, con, con, uid, int(ahora - CHAT_VIDA)))]
    with P._escribir:
        c.execute("UPDATE mensajes SET leido = 1 WHERE para = ? AND de = ? AND leido = 0", (uid, con))
        c.commit()
    return 200, {"mensajes": list(reversed(filas))}
