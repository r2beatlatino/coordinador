# -*- coding: utf-8 -*-
"""probar_portero — el portero de cuentas para los otros juegos (EDA). 11-nov-2026.

Arma una `datos.db` de mentira (4 cuentas: una normal, otra común, una BANNED y una FUSIONADA), levanta el portero en un
puerto al azar y le pega por HTTP como lo haría el launcher. Cada cosa con su CONTROL AL REVÉS:

  · la firma: el vector 1 del RFC 8032 y Node (otra implementación) aceptan nuestra firma ⟲ y rechazan una tocada;
  · la cuenta NO aprobada no recibe pase NI manifest ⟲ la aprobada sí (Benja: «solo las aprobadas podrán descargar / jugar»);
  · el pase lo acepta `comprobar_pase` ⟲ con otro aud, vencido, tocado o con otra clave, no;
  · un ban del juego, uno de R2Beat y una cuenta fusionada cortan;
  · la sesión sobrevive a reiniciar el portero (vive en portero.db) ⟲ `salir` la mata;
  · el freno: 8 fallos ⟲ la novena con la clave buena igual da 429;
  · ⛔ `datos.db` queda con el MISMO md5 ⟲ la conexión del portero a ella REHÚSA escribir.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest().upper()


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


tmp = tempfile.mkdtemp(prefix="portero_")
try:
    import sqlite3
    base_juego = os.path.join(tmp, "datos.db")
    c = sqlite3.connect(base_juego)
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, username TEXT UNIQUE, pass_hash TEXT)")
    c.executemany("INSERT INTO users VALUES (?, ?, ?)", [
        (101, "aprobada", sha("clave1")), (102, "comun", sha("clave2")),
        (103, "baneada", "BANNED:" + sha("clave3")), (104, "fusion", "FUSIONADA:" + sha("clave4")),
        (105, "jefe", sha("clave5")), (110, "mod1", sha("clave10"))])
    c.execute("CREATE TABLE chars (uid INTEGER PRIMARY KEY, nickname TEXT)")
    c.executemany("INSERT INTO chars VALUES (?, ?)", [(101, "jugador1"), (102, "Tito"), (105, "ElJefe"), (110, "Moderita")])
    c.commit()
    c.close()
    md5_antes = md5(base_juego)
    admin_txt = os.path.join(tmp, "admin.txt")
    open(admin_txt, "w").write("# admins" + chr(10) + "jefe" + chr(10))
    os.environ.update(R2_BASE=base_juego, R2_PORTERO_BASE=os.path.join(tmp, "portero.db"),
                      R2_PORTERO_CLAVE=os.path.join(tmp, "portero_clave.json"), R2_ADMIN_ARCHIVO=admin_txt,
                      R2_MODERADOR_ARCHIVO=os.path.join(tmp, "moderadores.txt"))
    os.environ.pop("R2_PORTERO_MANIFIESTOS", None)

    from servidor import firma_ed25519 as ed
    from servidor import portero as pt

    print("1 · la firma")
    s = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    ok(ed.publica(s).hex() == "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "RFC 8032 vector 1: la pública")
    ok(ed.firmar(s, b"").hex() == "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
       "RFC 8032 vector 1: la firma")
    ok(not ed.verificar(ed.publica(s), b"x", ed.firmar(s, b"")), "⟲ la misma firma sobre otro mensaje NO pasa")

    nodo = shutil.which("node")
    if nodo:
        sem = os.urandom(32)
        msg = b"un pase cualquiera"
        firma = ed.firmar(sem, msg)
        js = ("const c=require('crypto');const [x,m,f]=process.argv.slice(1);"
              "const k=c.createPublicKey({key:{kty:'OKP',crv:'Ed25519',x},format:'jwk'});"
              "console.log(c.verify(null,Buffer.from(m,'hex'),k,Buffer.from(f,'hex')))")
        def en_node(f):
            r = subprocess.run([nodo, "-e", js, "--", pt._b64u(ed.publica(sem)), msg.hex(), f.hex()],
                               capture_output=True, text=True, timeout=30)
            return r.stdout.strip()
        ok(en_node(firma) == "true", "Node (otra implementación) acepta nuestra firma")
        tocada = bytes([firma[0] ^ 1]) + firma[1:]
        ok(en_node(tocada) == "false", "⟲ Node rechaza la firma con un bit cambiado")
    else:
        print("  · (sin node: se saltea la comparación con otra implementación)")

    srv = pt.servidor(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    def pedir(metodo, ruta, cuerpo=None, token=None, x_r2=True, ip=None, base=None):
        h = {"Content-Type": "application/json"}
        if x_r2:
            h["X-R2"] = "1"
        if token:
            h["Authorization"] = "Bearer " + token
        if ip:
            h["X-Forwarded-For"] = ip
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else (b"{}" if metodo == "POST" else None)
        req = urllib.request.Request((base or url) + ruta, data=datos, headers=h, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    print("2 · entrar")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "aprobada", "clave": "clave1"}, x_r2=False)[0] == 403,
       "sin X-R2 se rechaza")
    c1, d1 = pedir("POST", "/cuentas/entrar", {"usuario": "aprobada", "clave": "mala"})
    c2, d2 = pedir("POST", "/cuentas/entrar", {"usuario": "noexiste", "clave": "x"})
    ok(c1 == 401 and c2 == 401 and d1 == d2, "clave mala y cuenta inexistente: el MISMO 401")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "baneada", "clave": "clave3"})[0] == 403, "baneada en R2Beat: 403")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "fusion", "clave": "clave4"})[0] == 403, "fusionada: 403")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "Aprobada", "clave": "clave1"})[0] == 401,
       "el usuario se compara exacto (Aprobada ≠ aprobada)")
    c, d = pedir("POST", "/cuentas/entrar", {"usuario": "aprobada", "pass_sha256_upper": sha("clave1")})
    ok(c == 200 and d.get("uid") == 101, "entra con el hash (como manda el launcher)")
    c, d = pedir("POST", "/entrar", {"usuario": "aprobada", "clave": "clave1"})
    ok(c == 200 and d.get("sesion"), "entra con la clave, y la ruta anda también sin el prefijo /cuentas")
    tok = d["sesion"]
    ok(d["juegos"] == [{"id": "eda", "nombre": "Espada del Alma", "permitido": False}], "antes de aprobar: EDA no permitido")

    print("3 · sólo las aprobadas")
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, tok)[0] == 403, "⟲ sin aprobar: NO hay pase")
    ok(pedir("GET", "/cuentas/manifiesto/eda", token=tok)[0] == 403, "⟲ sin aprobar: NO hay manifest")
    pt.consola(["aprobar", "aprobada", "eda"])
    c, d = pedir("POST", "/cuentas/pase", {"juego": "eda"}, tok)
    ok(c == 200 and d.get("pase"), "aprobada: hay pase")
    pase = d["pase"]
    ok(pedir("GET", "/cuentas/yo", token=tok)[1]["juegos"][0]["permitido"] is True, "/yo ya la muestra permitida")
    ok(pedir("GET", "/cuentas/manifiesto/eda", token=tok)[0] == 503, "aprobada pero sin manifest publicado: 503")
    carpeta = os.path.join(tmp, "manifiestos")
    os.makedirs(carpeta)
    man = {"version": "eda_prueba", "base": "https://cdn.ejemplo/files-eda/eda_prueba-secreto/",
           "files": [{"path": "EDA.exe", "size": 3, "md5": "x"}]}
    json.dump(man, open(os.path.join(carpeta, "eda.json"), "w"))
    os.environ["R2_PORTERO_MANIFIESTOS"] = carpeta
    ok(pedir("GET", "/cuentas/manifiesto/eda", token=tok) == (200, man), "aprobada: recibe el manifest")
    tok2 = pedir("POST", "/cuentas/entrar", {"usuario": "comun", "clave": "clave2"})[1]["sesion"]
    ok(pedir("GET", "/cuentas/manifiesto/eda", token=tok2)[0] == 403, "⟲ la común (no aprobada) NO recibe el manifest")
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, tok2)[0] == 403, "⟲ la común NO recibe pase")
    ok(pedir("POST", "/cuentas/pase", {"juego": "otro"}, tok)[0] == 404, "juego desconocido: 404")
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, "inventado")[0] == 401, "sesión inventada: 401")

    print("4 · el pase")
    jw = pedir("GET", "/cuentas/clave-publica")[1]["keys"][0]
    pub = pt._de_b64u(jw["x"])
    carga = pt.comprobar_pase(pase, pub, "eda")
    ok(carga is not None and carga["sub"] == "101" and carga["exp"] - carga["iat"] == 300, "el pase se comprueba con la JWKS")
    ok("aprobada" not in json.dumps(carga), "el pase NO lleva el nombre de login")
    ok(carga.get("nombre") == "jugador1", "★ el pase lleva el NOMBRE visible = el apodo (jugador1), no el login")
    ok(pt.comprobar_pase(pase, pub, "r2beat") is None, "⟲ con otro aud: rechazado")
    ok(pt.comprobar_pase(pase, pub, "eda", ahora=carga["exp"] + 31) is None, "⟲ vencido: rechazado")
    a, b, f = pase.split(".")
    otra = dict(carga, sub="102")
    b2 = pt._b64u(json.dumps(otra, separators=(",", ":")).encode())
    ok(pt.comprobar_pase(f"{a}.{b2}.{f}", pub, "eda") is None, "⟲ con el sub cambiado: rechazado")
    ok(pt.comprobar_pase(pase, ed.publica(os.urandom(32)), "eda") is None, "⟲ con otra clave: rechazado")
    if nodo:
        js = ("const c=require('crypto');const [x,p]=process.argv.slice(1);const [a,b,f]=p.split('.');"
              "const k=c.createPublicKey({key:{kty:'OKP',crv:'Ed25519',x},format:'jwk'});"
              "console.log(c.verify(null,Buffer.from(a+'.'+b),k,Buffer.from(f,'base64url')))")
        r = subprocess.run([nodo, "-e", js, "--", jw["x"], pase], capture_output=True, text=True, timeout=30)
        ok(r.stdout.strip() == "true", "Node comprueba el pase con la JWKS (como lo haría el server de EDA)")

    print("5 · baneos")
    pt.consola(["banear", "aprobada", "eda", "prueba"])
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, tok)[0] == 403, "baneada EN EDA: sin pase (aunque esté aprobada)")
    pt.consola(["desbanear", "aprobada", "eda"])
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, tok)[0] == 200, "⟲ desbaneada: vuelve el pase")

    print("6 · la sesión")
    srv.shutdown()
    srv.server_close()
    srv2 = pt.servidor(0)
    threading.Thread(target=srv2.serve_forever, daemon=True).start()
    url2 = f"http://127.0.0.1:{srv2.server_address[1]}"
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, tok, base=url2)[0] == 200, "la sesión sobrevive a reiniciar el portero")
    pedir("POST", "/cuentas/salir", {}, tok, base=url2)
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, tok, base=url2)[0] == 401, "⟲ después de salir: 401")
    url = url2

    print("7 · el freno")
    for _ in range(8):
        pedir("POST", "/cuentas/entrar", {"usuario": "comun", "clave": "mala"}, ip="10.9.9.9")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "comun", "clave": "clave2"}, ip="10.9.9.9")[0] == 429,
       "8 fallos: la 9.ª, aun con la clave buena, da 429")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "aprobada", "clave": "clave1"}, ip="10.1.1.1")[0] == 200,
       "⟲ otra cuenta desde otra IP entra normal")

    print("9 · ★ el PANEL de aprobaciones (sólo ADMIN)")
    def http(metodo, ruta, cuerpo=None, cookie=None, x_r2=True):
        h = {}
        if cuerpo is not None:
            h["Content-Type"] = "application/json"
        if x_r2:
            h["X-R2"] = "1"
        if cookie:
            h["Cookie"] = cookie
        req = urllib.request.Request(url + ruta, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                     headers=h, method=metodo)
        class SinRedir(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        try:
            r = urllib.request.build_opener(SinRedir).open(req, timeout=10)
        except urllib.error.HTTPError as e:
            r = e
        b = r.read()
        try:
            d = json.loads(b)
        except ValueError:
            d = b
        return r.status if hasattr(r, "status") else r.code, d, r.headers
    st, html, hd = http("GET", "/cuentas/admin")
    ok(st == 200 and b"Aprobaciones" in html and "frame-ancestors 'none'" in hd.get("Content-Security-Policy", "")
       and hd.get("X-Frame-Options") == "DENY", "la página sale con CSP y sin poder meterse en un iframe")
    ok(http("GET", "/admin/panel.js")[0] == 200, "el .js (también sin el prefijo /cuentas, para eñeños.link/admin)")
    st, _d, hd = http("GET", "/cuentas/admin/")
    ok(st == 301 and hd.get("Location") == "/cuentas/admin", "«/admin/» redirige a «/admin» (las rutas del .js son relativas)")
    ok(http("GET", "/cuentas/admin/lista")[0] == 401, "⟲ sin sesión: la lista NO se ve")
    st_n, d_n, _h = http("POST", "/cuentas/admin/entrar", {"usuario": "comun", "clave": "clave2"})
    st_m, d_m, _h = http("POST", "/cuentas/admin/entrar", {"usuario": "jefe", "clave": "mala"})
    ok(st_n == 401 and d_n == d_m, "⟲ una cuenta NO admin, con su clave buena, da el MISMO 401 que una clave mala")
    ok(http("POST", "/cuentas/admin/entrar", {"usuario": "jefe", "clave": "clave5"}, x_r2=False)[0] == 403, "⟲ sin X-R2: 403")
    st, d, hd = http("POST", "/cuentas/admin/entrar", {"usuario": "jefe", "clave": "clave5"})
    galleta = hd.get("Set-Cookie", "")
    ok(st == 200 and all(x in galleta for x in ("HttpOnly", "Secure", "SameSite=Strict")), "el ADMIN entra: cookie HttpOnly · Secure · SameSite=Strict")
    ck = galleta.split(";", 1)[0]
    ok(http("GET", "/cuentas/admin/yo", cookie=ck)[1].get("admin") == "jefe", "/admin/yo dice quién es")
    st, d, _h = http("GET", "/cuentas/admin/buscar?q=apr", cookie=ck)
    ok(st == 200 and [c["uid"] for c in d["cuentas"]] == [101] and d["cuentas"][0]["aprobada"], "buscar por login («apr» -> aprobada, ya aprobada)")
    st, d, _h = http("GET", "/cuentas/admin/buscar?q=tit", cookie=ck)
    ok(st == 200 and [c["uid"] for c in d["cuentas"]] == [102] and d["cuentas"][0]["apodo"] == "Tito", "buscar por apodo («tit» -> Tito)")
    ok(http("GET", "/cuentas/admin/buscar?q=a", cookie=ck)[0] == 400, "⟲ 1 letra: no busca")
    ok(not pt.permitido(102, "eda"), "⟲ antes de aprobar: comun NO puede entrar a EDA")
    st, d, _h = http("POST", "/cuentas/admin/aprobar", {"uid": 102, "juego": "eda"}, cookie=ck)
    ok(st == 200 and pt.permitido(102, "eda"), "el panel APRUEBA: comun ya puede")
    ok(http("POST", "/cuentas/admin/aprobar", {"uid": 102, "juego": "eda"}, cookie=ck, x_r2=False)[0] == 403, "⟲ aprobar sin X-R2: 403")
    st, d, _h = http("POST", "/cuentas/admin/banear", {"uid": 102, "juego": "eda", "detalle": "prueba"}, cookie=ck)
    ok(st == 200 and not pt.permitido(102, "eda"), "el panel BANEA de EDA: comun ya no puede (aunque siga aprobada)")
    st, d, _h = http("GET", "/cuentas/admin/lista", cookie=ck)
    ok(st == 200 and [a["accion"] for a in d["auditoria"][:3]] == ["banear", "aprobar", "entrar al panel"]
       and d["auditoria"][0]["quien"] == "jefe" and d["auditoria"][0]["detalle"] == "prueba", "la auditoría anota quién hizo qué")
    ok("pass_hash" not in json.dumps(d) and sha("clave2") not in json.dumps(d), "la lista no trae hashes")
    ok(http("POST", "/cuentas/admin/aprobar", {"uid": 99999, "juego": "eda"}, cookie=ck)[0] == 404, "una cuenta inexistente: 404")
    open(admin_txt, "w").write("# ya no hay admins" + chr(10))
    os.utime(admin_txt, (time.time() + 5, time.time() + 5))
    ok(http("GET", "/cuentas/admin/lista", cookie=ck)[0] == 401, "⟲ sacado de admin.txt: la MISMA cookie deja de servir al instante")
    open(admin_txt, "w").write("jefe" + chr(10))
    os.utime(admin_txt, (time.time() + 10, time.time() + 10))
    ok(http("GET", "/cuentas/admin/lista", cookie=ck)[0] == 200, "…y vuelto a poner, vuelve a servir")
    http("POST", "/cuentas/admin/salir", {}, cookie=ck)
    ok(http("GET", "/cuentas/admin/lista", cookie=ck)[0] == 401, "⟲ después de Salir: 401")

    print("11 · ★ los MODERADORES (sólo aprueban y quitan)")
    mod_txt = os.environ["R2_MODERADOR_ARCHIVO"]
    st_x, d_x, _h = http("POST", "/cuentas/admin/entrar", {"usuario": "mod1", "clave": "clave10"})
    ok(st_x == 401 and d_x == d_m, "⟲ sin moderadores.txt: mod1 NO entra (el mismo 401 que una clave mala)")
    open(mod_txt, "w").write("# moderadores" + chr(10) + "110  # mod1" + chr(10))
    st, d, hd = http("POST", "/cuentas/admin/entrar", {"usuario": "mod1", "clave": "clave10"})
    ok(st == 200 and d.get("rol") == "moderador", "con su uid en moderadores.txt entra, como MODERADOR")
    cm = hd.get("Set-Cookie", "").split(";", 1)[0]
    ok(http("GET", "/cuentas/admin/yo", cookie=cm)[1].get("rol") == "moderador", "/admin/yo dice rol moderador")
    st, d, _h = http("GET", "/cuentas/admin/buscar?q=tit", cookie=cm)
    ok(st == 200 and [c["uid"] for c in d["cuentas"]] == [102], "busca cuentas (tit -> Tito)")
    st, d, _h = http("GET", "/cuentas/admin/buscar?q=jef", cookie=cm)
    ok(st == 200 and d["cuentas"] == [], "⟲ buscando «jef» NO le aparece la cuenta del ADMIN")
    ok(http("GET", "/cuentas/admin/buscar?q=jef", cookie=ck2)[1]["cuentas"][0]["uid"] == 105 if (ck2 := http("POST", "/cuentas/admin/entrar", {"usuario": "jefe", "clave": "clave5"})[2].get("Set-Cookie", "").split(";", 1)[0]) else False,
       "control: al ADMIN sí le aparece")
    ok(http("POST", "/cuentas/admin/quitar", {"uid": 102, "juego": "eda"}, cookie=cm)[0] == 200 and not pt.permitido(102, "eda"), "QUITA")
    ok(http("POST", "/cuentas/admin/aprobar", {"uid": 101, "juego": "eda"}, cookie=cm)[0] == 200, "APRUEBA")
    st_b, d_b, _h = http("POST", "/cuentas/admin/banear", {"uid": 101, "juego": "eda", "detalle": "x"}, cookie=cm)
    ok(st_b == 403 and pt.permitido(101, "eda"), "⟲ BANEAR: 403, y la cuenta sigue igual")
    ok(http("POST", "/cuentas/admin/desbanear", {"uid": 102, "juego": "eda"}, cookie=cm)[0] == 403, "⟲ DESBANEAR: 403")
    ok(http("POST", "/cuentas/admin/quitar", {"uid": 105, "juego": "eda"}, cookie=cm)[0] == 403, "⟲ tocar la cuenta del ADMIN: 403")
    st, d, _h = http("GET", "/cuentas/admin/lista", cookie=cm)
    txt = json.dumps(d, ensure_ascii=False)
    ok(st == 200 and "jefe" not in txt and any(x["quien"] == "ADMIN" for x in d["baneadas"]),
       "en su lista el login del ADMIN NO aparece: sale «ADMIN»")
    ok(all(a["accion"] in ("aprobar", "quitar", "banear", "desbanear") for a in d["auditoria"])
       and d["auditoria"][0]["quien"] == "mod1" and d["auditoria"][0]["accion"] == "aprobar",
       "su auditoría: sólo movimientos de cuentas, y lo suyo anotado con SU nombre")
    ok("jefe" in json.dumps(http("GET", "/cuentas/admin/lista", cookie=ck2)[1]), "control: el ADMIN sí ve los nombres")
    open(mod_txt, "w").write("# sin moderadores" + chr(10))
    os.utime(mod_txt, (time.time() + 5, time.time() + 5))
    ok(http("GET", "/cuentas/admin/lista", cookie=cm)[0] == 401, "⟲ sacado de moderadores.txt: su cookie deja de servir al instante")
    http("POST", "/cuentas/admin/salir", {}, cookie=ck2)

    print("10 · el pase de prueba por consola")
    import io, contextlib
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        pt.consola(["pase", "aprobada", "eda", "1200"])
    pp = salida.getvalue().strip()
    k = pt.comprobar_pase(pp, pub, "eda", ahora=time.time() + 1000)
    ok(k is not None and k["sub"] == "101" and k["iat"] <= time.time() + 1 and k["exp"] - k["iat"] == 1200,
       "pase de 20 min: vale a los ~17 min y NO nace en el futuro")
    ok(pt.comprobar_pase(pp, pub, "eda", ahora=time.time() + 1300) is None, "⟲ a los 21 min ya no vale")
    try:
        pt.consola(["pase", "comun", "eda"])
        sin_pase = False
    except SystemExit:
        sin_pase = True
    ok(sin_pase, "⟲ a una cuenta baneada en EDA no se le da pase de prueba")
    c2 = sqlite3.connect(base_juego)
    c2.execute("INSERT INTO users VALUES (106, 'sinapodo', ?)", (sha("clave6"),))
    c2.commit(); c2.close()
    pt.consola(["aprobar", "sinapodo", "eda"])
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        pt.consola(["pase", "sinapodo", "eda"])
    k6 = pt.comprobar_pase(salida.getvalue().strip(), pub, "eda")
    ok(k6 is not None and "nombre" not in k6, "⟲ una cuenta SIN personaje: el pase va sin «nombre» (el otro juego usa el suyo)")

    print("8 · ⛔ datos.db no se toca")
    try:
        pt._juego().execute("UPDATE users SET pass_hash = 'x' WHERE uid = 101")
        rehusa = False
    except sqlite3.OperationalError:
        rehusa = True
    ok(rehusa, "⟲ la conexión del portero a datos.db REHÚSA escribir")
    srv2.shutdown()
    srv2.server_close()
    pt.cerrar_conexiones()
    ok(md5(base_juego) == md5_antes, "datos.db sale con el MISMO md5")
finally:
    try:
        from servidor import portero as _p
        _p.cerrar_conexiones()
    except Exception:                                            # noqa: BLE001
        pass
    shutil.rmtree(tmp, ignore_errors=True)

print()
if fallos:
    print(f"✘ {len(fallos)} FALLAS")
    sys.exit(1)
print("✔ el portero: todo bien")
