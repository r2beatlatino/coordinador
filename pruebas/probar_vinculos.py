# -*- coding: utf-8 -*-
"""probar_vinculos — entrar, registrarse y vincular el Eñeños ID con Google/Discord (servidor/vinculos.py). 16-nov-2026.

Se levanta el portero de verdad (HTTP, en un puerto libre, con `R2_CUENTAS_DUENA=1` y bases temporales). El único
reemplazo es `vinculos.identificar` (canjear el código con Google/Discord): devuelve el id que diga la prueba.
Cada chequeo con su CONTROL AL REVÉS (⟲):
  · sin ID/secreto el proveedor está APAGADO ⟲ con los dos, prendido; `iniciar` en uno apagado da 400
  · `/oauth/ir/<sid>` manda (302) a Google con `state`, PKCE S256 y la vuelta registrada ⟲ un sid inventado da 400
  · entrar con un Google NUEVO → `nuevo` + nombre sugerido → `registrar` crea la cuenta SIN contraseña, vinculada,
    con sesión que sirve para pedir pases ⟲ esa cuenta no entra por /entrar con ninguna clave; el usuario repetido da 409
  · la segunda vez, el mismo Google entra DIRECTO a esa cuenta ⟲ otro Google (otro id) cae en `nuevo`
  · una cuenta EXISTENTE con contraseña vincula Discord desde su sesión y después entra con Discord ⟲ sin sesión no
    vincula (401); un Discord ya vinculado a OTRO Eñeños ID no se puede vincular (error)
  · el resultado con sesión se entrega UNA vez y sólo a la IP que empezó ⟲ otra IP: 403; leerlo de nuevo: 404
  · desvincular: la cuenta con contraseña puede ⟲ la nacida con Google NO puede quitar su único vínculo (409)
  · una cuenta baneada no entra por Google ⟲ (la misma, activa, sí)
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest().upper()


tmp = tempfile.mkdtemp(prefix="vinculos_")
os.environ.update({
    "R2_CUENTAS_DUENA": "1",
    "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"),
    "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe_datos.db"),
    "R2_ADMIN_ARCHIVO": os.path.join(tmp, "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "moderadores.txt"),
    "R2_PORTERO_PUERTO": "0",
    "R2_OAUTH_BASE": "https://cuentas.prueba/cuentas",
})
for k in ("R2_OAUTH_GOOGLE_ID", "R2_OAUTH_GOOGLE_SECRETO", "R2_OAUTH_DISCORD_ID", "R2_OAUTH_DISCORD_SECRETO"):
    os.environ.pop(k, None)

from servidor import portero as P          # noqa: E402
from servidor import vinculos as V         # noqa: E402

print("· proveedores")
ok(V.proveedores() == {"google": False, "discord": False}, "⟲ sin ID ni secreto: los dos APAGADOS")
c0, d0 = V.iniciar(P, "google", "entrar", "", "1.1.1.1")
ok(c0 == 400, f"⟲ iniciar con Google apagado: 400 (dio {c0})")
os.environ.update({"R2_OAUTH_GOOGLE_ID": "gid-prueba", "R2_OAUTH_GOOGLE_SECRETO": "x",
                   "R2_OAUTH_DISCORD_ID": "did-prueba", "R2_OAUTH_DISCORD_SECRETO": "y"})
ok(V.proveedores() == {"google": True, "discord": True}, "con ID y secreto: prendidos")

QUIEN = {}                                   # código -> (id externo, nombre)
V.identificar = lambda prov, codigo, verif: QUIEN[codigo]

with contextlib.redirect_stdout(io.StringIO()):
    srv = P.servidor(0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/cuentas"


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


abrir = urllib.request.build_opener(SinRedireccion).open


def pedir(metodo, ruta, datos=None, token=None):
    cab = {"X-R2": "1", "Content-Type": "application/json"}
    if token:
        cab["Authorization"] = "Bearer " + token
    r = urllib.request.Request(URL + ruta, data=None if datos is None else json.dumps(datos).encode(), headers=cab,
                               method=metodo)
    try:
        with abrir(r, timeout=10) as x:
            cuerpo = x.read()
            return x.status, (json.loads(cuerpo) if x.headers.get_content_type() == "application/json" else cuerpo), x.headers
    except urllib.error.HTTPError as e:
        cuerpo = e.read()
        try:
            return e.code, json.loads(cuerpo), e.headers
        except ValueError:
            return e.code, cuerpo, e.headers


def flujo(prov, modo, codigo, token=None):
    """iniciar → (el navegador) ir → vuelta con `codigo` → estado. -> (sid, resultado)."""
    c, d, _ = pedir("POST", "/oauth/iniciar", {"proveedor": prov, "modo": modo}, token)
    if c != 200:
        return None, {"_codigo": c, **d}
    sid = d["sid"]
    pedir("GET", "/oauth/vuelta?" + urllib.parse.urlencode({"state": sid, "code": codigo}))
    c, d, _ = pedir("POST", "/oauth/estado", {"sid": sid})
    return sid, d


P._fallos.clear()
print("· ir al proveedor")
c, d, _ = pedir("POST", "/oauth/iniciar", {"proveedor": "google", "modo": "entrar"})
ok(c == 200 and d["url"].endswith("/oauth/ir/" + d["sid"]), "iniciar da un sid y la dirección /oauth/ir/<sid>")
c, _, h = pedir("GET", "/oauth/ir/" + d["sid"])
loc = urllib.parse.urlsplit(h.get("Location") or "")
q = dict(urllib.parse.parse_qsl(loc.query))
ok(c == 302 and loc.netloc == "accounts.google.com" and q.get("state") == d["sid"]
   and q.get("code_challenge_method") == "S256" and q.get("redirect_uri") == "https://cuentas.prueba/cuentas/oauth/vuelta"
   and q.get("client_id") == "gid-prueba", "302 a Google con state, PKCE S256, client_id y la vuelta registrada")
c, _, _ = pedir("GET", "/oauth/ir/inventado")
ok(c == 400, f"⟲ un sid inventado: 400 (dio {c})")

print("· registrarse con Google")
QUIEN.update({"g1": ("G-111", "Ana Pérez"), "g2": ("G-222", "Bo"), "d1": ("D-900", "conejo_99"), "d2": ("D-900", "x")})
sid, r = flujo("google", "entrar", "g1")
ok(r.get("nuevo") and r.get("sugerido") == "AnaPrez", f"un Google nuevo: «nuevo», sugerido {r.get('sugerido')!r}")
c, d, _ = pedir("POST", "/oauth/registrar", {"sid": sid, "usuario": "ana_g"})
ok(c == 200 and d.get("sesion") and d.get("usuario") == "ana_g" and d["uid"] >= 10_000_000,
   f"registrar crea la cuenta con sesión (uid {d.get('uid')})")
uid_ana, ses_ana = d.get("uid"), d.get("sesion")
c, d, _ = pedir("POST", "/pase", {"juego": "r2beat2013"}, ses_ana)
ok(c == 200 and d.get("pase"), "con esa sesión se pide un pase de R2Beat")
for cl in ("", "ana_g", "x"):
    c, _, _ = pedir("POST", "/entrar", {"usuario": "ana_g", "pass_sha256_upper": sha(cl)})
    ok(c == 401, f"⟲ la cuenta nacida con Google NO entra por contraseña («{cl}»: {c})")
sid, r = flujo("google", "entrar", "g2")
c, d, _ = pedir("POST", "/oauth/registrar", {"sid": sid, "usuario": "ana_g"})
ok(c == 409, f"⟲ usuario repetido: 409 (dio {c})")
c, d, _ = pedir("POST", "/oauth/registrar", {"sid": sid, "usuario": "a!"})
ok(c == 400, f"⟲ usuario mal formado: 400 (dio {c})")

print("· la segunda vez entra directo")
sid, r = flujo("google", "entrar", "g1")
ok(r.get("ok") and r.get("uid") == uid_ana and r.get("usuario") == "ana_g" and r.get("sesion"),
   "el mismo Google entra DIRECTO a su cuenta")
c, d, _ = pedir("POST", "/oauth/estado", {"sid": sid})
ok(c == 404, f"⟲ el resultado con sesión se entrega UNA vez (otra lectura: {c})")
sid, r = flujo("google", "entrar", "g2")
ok(r.get("nuevo"), "⟲ otro Google (otro id) cae en «nuevo»")

print("· una cuenta existente vincula Discord")
c, d, _ = pedir("POST", "/registrar", {"usuario": "beto", "pass_sha256_upper": sha("clave1")})
uid_beto = d.get("uid")
c, d, _ = pedir("POST", "/entrar", {"usuario": "beto", "pass_sha256_upper": sha("clave1")})
ses_beto = d.get("sesion")
c, d, _ = pedir("POST", "/oauth/iniciar", {"proveedor": "discord", "modo": "vincular"})
ok(c == 401, f"⟲ vincular sin sesión: 401 (dio {c})")
sid, r = flujo("discord", "vincular", "d1", ses_beto)
ok(r.get("ok") and r.get("vinculado") == "discord", "beto vincula su Discord")
c, d, _ = pedir("GET", "/oauth/vinculos", token=ses_beto)
ok(c == 200 and [v["proveedor"] for v in d["vinculos"]] == ["discord"] and d["con_clave"], "la lista lo muestra")
sid, r = flujo("discord", "entrar", "d1")
ok(r.get("ok") and r.get("uid") == uid_beto, "y después entra con Discord a SU cuenta")
sid, r = flujo("discord", "vincular", "d2", ses_ana)
ok(bool(r.get("error")), "⟲ ese Discord no se puede vincular a OTRO Eñeños ID")

print("· la IP que empezó")
V._por_ip.clear()
c, d, _ = pedir("POST", "/oauth/iniciar", {"proveedor": "google", "modo": "entrar"})
sid = d["sid"]
pedir("GET", "/oauth/vuelta?" + urllib.parse.urlencode({"state": sid, "code": "g1"}))
c, d = V.estado(sid, "9.9.9.9")
ok(c == 403, f"⟲ otra IP no recibe la sesión (dio {c})")
c, d = V.estado(sid, "127.0.0.1")
ok(c == 200 and d.get("sesion"), "la que empezó, sí")

print("· desvincular")
for _ in range(V.FRENO_MAX):
    V.iniciar(P, "google", "entrar", "", "5.5.5.5")
c, _ = V.iniciar(P, "google", "entrar", "", "5.5.5.5")
ok(c == 429, f"⟲ el freno: más de {V.FRENO_MAX} flujos por IP en 15 min dan 429 (dio {c})")
c, _ = V.iniciar(P, "google", "entrar", "", "6.6.6.6")
ok(c == 200, "(otra IP sigue pudiendo)")
V._por_ip.clear()
c, d, _ = pedir("POST", "/oauth/desvincular", {"proveedor": "google"}, ses_ana)
ok(c == 409, f"⟲ la nacida con Google no puede quitar su ÚNICO vínculo (dio {c})")
c, d, _ = pedir("POST", "/oauth/desvincular", {"proveedor": "discord"}, ses_beto)
ok(c == 200, "la que tiene contraseña puede")
sid, r = flujo("discord", "entrar", "d1")
ok(r.get("nuevo"), "⟲ y ese Discord ya no entra a beto")

print("· baneada")
with P._escribir:
    P._cuentas().execute("UPDATE cuentas SET estado = 'baneada' WHERE uid = ?", (uid_ana,))
    P._cuentas().commit()
sid, r = flujo("google", "entrar", "g1")
ok(bool(r.get("error")) and not r.get("sesion"), "⟲ una cuenta baneada no entra por Google")
with P._escribir:
    P._cuentas().execute("UPDATE cuentas SET estado = 'activa' WHERE uid = ?", (uid_ana,))
    P._cuentas().commit()
sid, r = flujo("google", "entrar", "g1")
ok(r.get("ok"), "(la misma, activa, sí)")

srv.shutdown()
P.cerrar_conexiones()
shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'OK' if not fallos else 'FALLAN ' + str(len(fallos))} · vínculos con Google y Discord")
sys.exit(1 if fallos else 0)
