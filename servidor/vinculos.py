# -*- coding: utf-8 -*-
"""vinculos — entrar, registrarse y VINCULAR el Eñeños ID con Google y Discord (16-nov-2026, Benja). Parte del portero
(Cuenta Eñeños dueña, `R2_CUENTAS_DUENA=1`): sin esa variable, nada de esto existe.

EL CAMINO (el launcher es de escritorio: la página del proveedor se abre en el NAVEGADOR del sistema, porque Google
bloquea su login dentro de ventanas embebidas)

    launcher ──POST /oauth/iniciar {proveedor, modo}────────▶ portero → {sid, url}      (modo «vincular» pide Bearer)
    launcher ──abre `url` en el navegador (= /oauth/ir/<sid>, nuestro dominio)──▶ 302 al proveedor
    proveedor ──vuelve a /oauth/vuelta?code&state=<sid>────▶ portero canjea el código, pregunta QUIÉN es (su id) y:
         · vincular: anota (proveedor, id) → el Eñeños ID de la sesión
         · entrar:   si ese id ya está vinculado → abre una SESIÓN de ese Eñeños ID (la misma que da /entrar)
                     si no → queda «nuevo»: el launcher le pide un nombre de usuario y llama a /oauth/registrar
    launcher ──POST /oauth/estado {sid} (cada 1,5 s)────────▶ {pendiente} | {ok, sesion, uid, usuario, juegos} |
                                                              {nuevo, sugerido} | {ok, vinculado} | {error}
    launcher ──POST /oauth/registrar {sid, usuario}─────────▶ crea la cuenta (SIN contraseña), la vincula y da sesión
    GET /oauth/vinculos + Bearer · POST /oauth/desvincular {proveedor} + Bearer · GET /oauth/proveedores

⛔ El `sid` es de UN uso, vive 10 minutos y sólo sirve desde la IP que lo pidió para leer el resultado con sesión.
⛔ Se guarda el id del proveedor y un nombre para mostrar; NO el mail.
⛔ Una cuenta sin contraseña (nacida con Google/Discord) no puede quedarse sin su último vínculo: no podría entrar.

VARIABLES
    R2_OAUTH_BASE              la dirección pública del portero, ej. https://ensayo.xn--eeos-gqab.link/cuentas
                               (la vuelta registrada en Google/Discord es <base>/oauth/vuelta)
    R2_OAUTH_GOOGLE_ID / R2_OAUTH_GOOGLE_SECRETO     ⛔ el secreto no se imprime ni va al repo
    R2_OAUTH_DISCORD_ID / R2_OAUTH_DISCORD_SECRETO
    Un proveedor sin su ID y su secreto queda APAGADO (el launcher deja el botón en «pronto»).
"""
import base64
import hashlib
import html
import json
import os
import secrets
import threading
import time
import urllib.parse
import urllib.request

SID_VIDA = 10 * 60
CLAVE_SIN = "sinclave$"            # una cuenta nacida con Google/Discord: ninguna contraseña coincide con esto

ESQUEMA = """
CREATE TABLE IF NOT EXISTS vinculos (
    proveedor TEXT NOT NULL,
    externo   TEXT NOT NULL,
    uid       INTEGER NOT NULL,
    nombre    TEXT,
    creado    TEXT NOT NULL,
    PRIMARY KEY (proveedor, externo)
);
CREATE UNIQUE INDEX IF NOT EXISTS vinculos_uid ON vinculos (uid, proveedor);
"""

PROVEEDORES = {
    "google": {
        "nombre": "Google",
        "autorizar": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "yo": "https://openidconnect.googleapis.com/v1/userinfo",
        "alcance": "openid profile",
        "pkce": True,
        "extra": {"prompt": "select_account"},
    },
    "discord": {
        "nombre": "Discord",
        "autorizar": "https://discord.com/oauth2/authorize",
        "token": "https://discord.com/api/oauth2/token",
        "yo": "https://discord.com/api/users/@me",
        "alcance": "identify",
        "pkce": False,
        "extra": {"prompt": "consent"},
    },
}

FRENO_MAX, FRENO_VENTANA = 20, 15 * 60   # flujos por IP (cancelar y volver a probar es normal: más que /entrar)
_por_ip = {}
_flujos = {}                       # sid -> {proveedor, modo, uid, ip, creado, verificador, estado, resultado, externo…}
_lock = threading.Lock()


def _cred(prov):
    p = prov.upper()
    return (os.environ.get(f"R2_OAUTH_{p}_ID") or "").strip(), (os.environ.get(f"R2_OAUTH_{p}_SECRETO") or "").strip()


def base():
    return (os.environ.get("R2_OAUTH_BASE") or "").strip().rstrip("/")


def prendido(prov):
    i, s = _cred(prov)
    return prov in PROVEEDORES and bool(i and s and base())


def proveedores():
    return {p: prendido(p) for p in PROVEEDORES}


def vuelta():
    return base() + "/oauth/vuelta"


def _limpiar(ahora):
    for k in [k for k, v in _flujos.items() if ahora - v["creado"] > SID_VIDA]:
        _flujos.pop(k, None)


def iniciar(P, proveedor, modo, token, ip, ahora=None):
    """-> (código, datos). `P` es el módulo portero (sesiones, freno, base de cuentas)."""
    ahora = time.time() if ahora is None else ahora
    if not P.es_duena():
        return 404, {"error": "no existe"}
    if proveedor not in PROVEEDORES or not prendido(proveedor):
        return 400, {"error": "Ese método de entrada todavía no está disponible."}
    if modo not in ("entrar", "vincular"):
        return 400, {"error": "pedido mal armado"}
    with _lock:
        v = [t for t in _por_ip.get(ip, []) if ahora - t < FRENO_VENTANA]
        if len(v) >= FRENO_MAX:
            return 429, {"error": "Demasiados intentos. Espere unos minutos."}
        if len(_por_ip) > 50_000:
            _por_ip.clear()
        _por_ip[ip] = v + [ahora]
    uid = None
    if modo == "vincular":
        uid = P.sesion_de(token, ahora)
        if not uid:
            return 401, {"error": "Tiene que iniciar sesión."}
    sid = secrets.token_urlsafe(24)
    verificador = secrets.token_urlsafe(48)
    with _lock:
        _limpiar(ahora)
        if len(_flujos) > 5000:
            return 503, {"error": "Demasiados pedidos a la vez. Intente de nuevo en un momento."}
        _flujos[sid] = {"proveedor": proveedor, "modo": modo, "uid": uid, "ip": ip, "creado": ahora,
                        "verificador": verificador, "estado": "pendiente", "resultado": None}
    return 200, {"sid": sid, "url": base() + "/oauth/ir/" + sid}


def url_proveedor(sid):
    """La dirección del proveedor para ese flujo, o None."""
    with _lock:
        f = _flujos.get(sid)
    if not f or f["estado"] != "pendiente":
        return None
    d = PROVEEDORES[f["proveedor"]]
    q = {"client_id": _cred(f["proveedor"])[0], "redirect_uri": vuelta(), "response_type": "code",
         "scope": d["alcance"], "state": sid}
    if d["pkce"]:
        q["code_challenge"] = base64.urlsafe_b64encode(
            hashlib.sha256(f["verificador"].encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        q["code_challenge_method"] = "S256"
    q.update(d["extra"])
    return d["autorizar"] + "?" + urllib.parse.urlencode(q)


def _http_json(url, datos=None, bearer=None, timeout=10):
    cab = {"Accept": "application/json", "User-Agent": "enenos-cuentas"}
    cuerpo = None
    if datos is not None:
        cuerpo = urllib.parse.urlencode(datos).encode("ascii")
        cab["Content-Type"] = "application/x-www-form-urlencoded"
    if bearer:
        cab["Authorization"] = "Bearer " + bearer
    with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=cab), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def identificar(proveedor, codigo, verificador):
    """Canjea el código y pregunta quién es. -> (id_externo, nombre_para_mostrar). Se reemplaza en las pruebas."""
    d = PROVEEDORES[proveedor]
    cid, sec = _cred(proveedor)
    datos = {"client_id": cid, "client_secret": sec, "grant_type": "authorization_code", "code": codigo,
             "redirect_uri": vuelta()}
    if d["pkce"]:
        datos["code_verifier"] = verificador
    tok = _http_json(d["token"], datos)
    yo = _http_json(d["yo"], bearer=tok["access_token"])
    if proveedor == "google":
        return str(yo["sub"]), str(yo.get("name") or yo.get("given_name") or "")[:40]
    return str(yo["id"]), str(yo.get("global_name") or yo.get("username") or "")[:40]


def _sugerido(nombre):
    s = "".join(ch for ch in (nombre or "") if ch.isascii() and (ch.isalnum() or ch == "_"))[:16]
    return s if len(s) >= 3 else ""


def _resolver(P, f, externo, nombre, ahora):
    """Con quién vino (proveedor + su id), decide el resultado del flujo."""
    c = P._cuentas()
    prov = f["proveedor"]
    ya = c.execute("SELECT uid FROM vinculos WHERE proveedor = ? AND externo = ?", (prov, externo)).fetchone()
    if f["modo"] == "vincular":
        if ya and int(ya["uid"]) != int(f["uid"]):
            return {"error": f"Esa cuenta de {PROVEEDORES[prov]['nombre']} ya está vinculada a otro Eñeños ID."}
        if not ya:
            with P._escribir:
                c.execute("DELETE FROM vinculos WHERE uid = ? AND proveedor = ?", (int(f["uid"]), prov))
                c.execute("INSERT INTO vinculos (proveedor, externo, uid, nombre, creado) VALUES (?, ?, ?, ?, ?)",
                          (prov, externo, int(f["uid"]), nombre, P._ahora_txt()))
                c.commit()
            P._log(f"vinculó {prov} uid={f['uid']}")
        return {"ok": True, "vinculado": prov, "nombre": nombre}
    if ya:
        uid = int(ya["uid"])
        est = P.estado_r2beat(uid)
        if est != "ok":
            return {"error": "Esta cuenta está suspendida." if est == "baneada" else "Esta cuenta ya no puede entrar."}
        return _sesion(P, uid, f["ip"], ahora)
    f["externo"], f["nombre"] = externo, nombre
    return {"nuevo": True, "sugerido": _sugerido(nombre), "proveedor": prov}


def _sesion(P, uid, ip, ahora):
    token = P.abrir_sesion(uid, ip, ahora)
    r = P._cuentas().execute("SELECT usuario FROM cuentas WHERE uid = ?", (int(uid),)).fetchone()
    return {"ok": True, "sesion": token, "uid": uid, "usuario": r["usuario"] if r else "",
            "juegos": P.juegos_de(uid)}


def vuelta_de(P, q, ahora=None):
    """GET /oauth/vuelta. -> (código, html). Nunca deja ver el resultado en la página: lo lee el launcher."""
    ahora = time.time() if ahora is None else ahora
    sid = str(q.get("state") or "")
    with _lock:
        f = _flujos.get(sid)
        if not f or f["estado"] != "pendiente" or ahora - f["creado"] > SID_VIDA:
            return 400, pagina("El pedido venció", "Vuelva al launcher e inténtelo de nuevo.")
        f["estado"] = "procesando"
    if q.get("error") or not q.get("code"):
        res = {"error": "Se canceló la entrada."}
    else:
        try:
            externo, nombre = identificar(f["proveedor"], str(q["code"]), f["verificador"])
            res = _resolver(P, f, externo, nombre, ahora)
        except Exception as e:                                      # noqa: BLE001 — el proveedor falló o tardó
            P._log(f"⚠ oauth {f['proveedor']}: {type(e).__name__}")
            res = {"error": f"No se pudo confirmar con {PROVEEDORES[f['proveedor']]['nombre']}. Inténtelo de nuevo."}
    with _lock:
        f["resultado"], f["estado"] = res, "listo"
    if res.get("error"):
        return 200, pagina("No se pudo completar", res["error"] + " Ya puede cerrar esta pestaña.")
    return 200, pagina("Listo", "Ya puede cerrar esta pestaña y volver al launcher.")


def estado(sid, ip, ahora=None):
    """POST /oauth/estado. Un resultado con sesión se entrega UNA vez y sólo a la IP que empezó."""
    ahora = time.time() if ahora is None else ahora
    with _lock:
        f = _flujos.get(str(sid or ""))
        if not f or ahora - f["creado"] > SID_VIDA:
            return 404, {"error": "El pedido venció. Inténtelo de nuevo."}
        if f["estado"] != "listo":
            return 200, {"pendiente": True}
        if f["ip"] != ip:
            return 403, {"error": "pedido no permitido"}
        res = dict(f["resultado"])
        if not res.get("nuevo"):
            _flujos.pop(str(sid), None)
        return 200, res


def registrar(P, sid, usuario, ip, ahora=None):
    """POST /oauth/registrar {sid, usuario}: la cuenta NUEVA de alguien que entró con Google/Discord por primera vez."""
    ahora = time.time() if ahora is None else ahora
    with _lock:
        f = _flujos.get(str(sid or ""))
        ok = bool(f and f["estado"] == "listo" and (f["resultado"] or {}).get("nuevo") and f["ip"] == ip
                  and ahora - f["creado"] <= SID_VIDA)
    if not ok:
        return 404, {"error": "El pedido venció. Inténtelo de nuevo."}
    u = P._usuario_valido(usuario)
    if not u:
        return 400, {"error": "El usuario tiene que tener de 3 a 16 letras, números o «_»."}
    c = P._cuentas()
    with P._escribir:
        if c.execute("SELECT 1 FROM cuentas WHERE usuario = ? COLLATE BINARY", (u,)).fetchone():
            return 409, {"error": "Ese usuario ya existe. Elija otro."}
        if c.execute("SELECT 1 FROM vinculos WHERE proveedor = ? AND externo = ?",
                     (f["proveedor"], f["externo"])).fetchone():
            return 409, {"error": "Esa cuenta ya está vinculada. Vuelva a entrar."}
        uid = P._siguiente_uid(c)
        c.execute("INSERT INTO cuentas (uid, usuario, clave, estado, creada) VALUES (?, ?, ?, 'activa', ?)",
                  (uid, u, CLAVE_SIN + secrets.token_hex(16), P._ahora_txt()))
        c.execute("INSERT INTO vinculos (proveedor, externo, uid, nombre, creado) VALUES (?, ?, ?, ?, ?)",
                  (f["proveedor"], f["externo"], uid, f.get("nombre") or "", P._ahora_txt()))
        c.commit()
    with _lock:
        _flujos.pop(str(sid), None)
    P._log(f"registrada cuenta uid={uid} con {f['proveedor']} desde {ip}")
    return 200, _sesion(P, uid, ip, ahora)


def lista(P, token, ahora=None):
    """GET /oauth/vinculos + Bearer -> {vinculos: [{proveedor, nombre, creado}], proveedores, con_clave}."""
    uid = P.sesion_de(token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    c = P._cuentas()
    v = [{"proveedor": r["proveedor"], "nombre": r["nombre"] or "", "creado": r["creado"]}
         for r in c.execute("SELECT proveedor, nombre, creado FROM vinculos WHERE uid = ? ORDER BY proveedor", (uid,))]
    r = c.execute("SELECT clave FROM cuentas WHERE uid = ?", (uid,)).fetchone()
    return 200, {"vinculos": v, "proveedores": proveedores(),
                 "con_clave": bool(r and not str(r["clave"]).startswith(CLAVE_SIN))}


def desvincular(P, token, proveedor, ahora=None):
    uid = P.sesion_de(token, ahora)
    if not uid:
        return 401, {"error": "Tiene que iniciar sesión."}
    c = P._cuentas()
    with P._escribir:
        r = c.execute("SELECT clave FROM cuentas WHERE uid = ?", (uid,)).fetchone()
        otros = c.execute("SELECT COUNT(*) FROM vinculos WHERE uid = ? AND proveedor != ?", (uid, proveedor)).fetchone()[0]
        if r and str(r["clave"]).startswith(CLAVE_SIN) and otros == 0:
            return 409, {"error": "Es la única forma de entrar a esta cuenta: no se puede quitar."}
        c.execute("DELETE FROM vinculos WHERE uid = ? AND proveedor = ?", (uid, str(proveedor or "")))
        c.commit()
    P._log(f"desvinculó {proveedor} uid={uid}")
    return 200, {"ok": True}


def pagina(titulo, texto):
    t, x = html.escape(titulo), html.escape(texto)
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{t} · Eñeños</title><style>"
            "body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0b0e14;"
            "font:15px/1.5 system-ui,sans-serif;color:#c3cadc}main{max-width:420px;padding:28px 30px;background:#121623;"
            "border:1px solid #252a3c;border-radius:14px;text-align:center}h1{margin:0 0 8px;font-size:20px;color:#f4f3fa}"
            f"</style></head><body><main><h1>{t}</h1><p>{x}</p></main></body></html>").encode("utf-8")
