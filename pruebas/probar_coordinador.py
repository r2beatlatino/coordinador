# -*- coding: utf-8 -*-
"""probar_coordinador — el panel del Coordinador Eñeños, fase A (servidor/coordinador.py). 19-nov-2026.

Se levanta el portero de verdad (HTTP, puerto libre, `R2_CUENTAS_DUENA=1`, bases temporales). El único reemplazo es
`vinculos.identificar` (canjear el código con Google/Discord): devuelve el id que diga la prueba. Cada regla con su
CONTROL AL REVÉS (⟲):
  · la LISTA BLANCA: un destino de afuera da 400 ⟲ el de la lista, 200; la vuelta va SIEMPRE al destino guardado (un
    `destino` metido en la vuelta no cambia nada); si el destino sale de la lista entre ida y vuelta, no hay 302
  · el TICKET: un solo uso (el 2.º canje falla ⟲ el 1.º anda), vence a los 60 s (61 s falla ⟲ 59 s anda), sirve sólo en
    el navegador que empezó (otra cookie falla ⟲ la suya anda) y se guarda sólo su huella
  · sin vínculo / sin rol / suspendida / rol quitado entre la vuelta y el canje -> sin sesión ⟲ el admin, con sesión
  · la COOKIE: HttpOnly · Secure · SameSite=Strict · Path=/ · 8 h ⟲ sin cookie, 401; el rol se mira en CADA pedido
  · el MODERADOR con juegos: ve sólo los suyos (tarjetas, personas, invitaciones, lanzamientos, auditoría), banea en
    los suyos ⟲ no en otro (403), y el ADMIN sí; el moderador SIN lista (formato viejo) sigue como antes (no banea)
  · ⛔ a un moderador no le llega un login, ni el nombre de Google/Discord, ni una cuenta con rol ⟲ al admin sí
  · el EQUIPO: sólo admin (403 al moderador); agregar / juegos / quitar escriben moderadores.txt sin tocar el resto y
    quedan en la auditoría; quitar corta la sesión al instante
  · el ESTADO de los servidores sale de un /salud de verdad ⟲ sin fuente no se muestra nada (ni un 0)
  · la página: CSP y sin `..` ⟲ un archivo que existe se sirve
  · ★ 20-nov: index.html, panel.js y panel.css no traen nada que su CSP bloquee (onclick=, <script> en línea, http,
    eval) ⟲ cada trampa se caza, y un <script src> o un xmlns de SVG no dan falso positivo
"""
import contextlib
import hashlib
import http.server
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
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


PANEL = "https://coordinador.prueba"
tmp = tempfile.mkdtemp(prefix="coordinador_")
os.makedirs(os.path.join(tmp, "config"))
os.makedirs(os.path.join(tmp, "arte"))
with open(os.path.join(tmp, "arte", "fondo-gunbound.jpg"), "wb") as f:
    f.write(b"\xff\xd8\xff\xe0 arte de prueba")
# los lanzamientos lejos en el futuro: la prueba no depende de la fecha de hoy
with open(os.path.join(tmp, "config", "lanzamientos.json"), "w", encoding="utf-8") as f:
    json.dump({"eda": {"desde": "2099-01-01T19:00:00-05:00"}, "gunbound": {"desde": "2099-01-02T12:00:00-05:00"},
               "r2beat-moderno": {"desde": "2099-01-03T19:00:00-05:00"}}, f)
os.environ.update({
    "R2_CUENTAS_DUENA": "1",
    "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"),
    "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe_datos.db"),
    "R2_ADMIN_ARCHIVO": os.path.join(tmp, "config", "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "config", "moderadores.txt"),
    "R2_PORTERO_PUERTO": "0",
    "R2_OAUTH_BASE": "https://auth.prueba/cuentas",
    "R2_OAUTH_GOOGLE_ID": "gid", "R2_OAUTH_GOOGLE_SECRETO": "x",
    "R2_OAUTH_DISCORD_ID": "did", "R2_OAUTH_DISCORD_SECRETO": "y",
    "R2_PANEL_URL": PANEL + ", javascript:alert(1), https://mal.prueba/?x=1",
    "R2_PANEL_ARTE": os.path.join(tmp, "arte"),
})
for k in ("R2_PANEL_SALUD", "R2_PRESENCIA", "R2_DISCORD_EVENTOS_WEBHOOK", "R2_JUEGOS_CATALOGO"):
    os.environ.pop(k, None)

from servidor import portero as P          # noqa: E402
from servidor import vinculos as V         # noqa: E402
from servidor import coordinador as CO     # noqa: E402

QUIEN = {}                                   # código -> (id externo, nombre)
V.identificar = lambda prov, codigo, verif: QUIEN[codigo]

# ── las cuentas ─────────────────────────────────────────────────────────────────────────────────
with contextlib.redirect_stdout(io.StringIO()):
    UID = {}
    for i, u in enumerate(["jefa", "modgb", "modviejo", "sinrol", "jugadora", "suspend", "nueva"]):
        UID[u] = P.registrar(u, clave_txt=f"clave-{u}", ip=f"10.0.0.{i}")[1]["uid"]
c = P._cuentas()
for u, apodo in (("jefa", "LaJefa"), ("modgb", "Artillera"), ("jugadora", "Pixelia"), ("nueva", "Novata")):
    c.execute("UPDATE cuentas SET apodo = ?, apodo_clave = ? WHERE uid = ?", (apodo, apodo.casefold(), UID[u]))
for prov, ext, u, nom in (("discord", "d-jefa", "jefa", "jefa#1"), ("google", "g-modgb", "modgb", "Ana Real Apellido"),
                          ("discord", "d-viejo", "modviejo", "viejo"), ("discord", "d-sinrol", "sinrol", "sinrol"),
                          ("discord", "d-susp", "suspend", "susp"), ("google", "g-jugadora", "jugadora", "Pía Nombre Real")):
    c.execute("INSERT INTO vinculos (proveedor, externo, uid, nombre, creado) VALUES (?, ?, ?, ?, 'hoy')",
              (prov, ext, UID[u], nom))
c.execute("UPDATE cuentas SET estado = 'baneada' WHERE uid = ?", (UID["suspend"],))
c.commit()
ADMIN_TXT, MOD_TXT = os.environ["R2_ADMIN_ARCHIVO"], os.environ["R2_MODERADOR_ARCHIVO"]
open(ADMIN_TXT, "w", encoding="utf-8").write(f"{UID['jefa']}  # la admin\n")
MODS_BASE = f"# moderadores de prueba\n{UID['modgb']} gunbound  # la de GunBound\nmodviejo\n{UID['suspend']}\n"
open(MOD_TXT, "w", encoding="utf-8").write(MODS_BASE)
QUIEN.update({"c-jefa": ("d-jefa", "jefa#1"), "c-modgb": ("g-modgb", "Ana Real Apellido"),
              "c-viejo": ("d-viejo", "viejo"), "c-sinrol": ("d-sinrol", "sinrol"), "c-susp": ("d-susp", "susp"),
              "c-nadie": ("d-nadie", "kai_ritmo"), "c-nueva": ("d-nueva", "nueva")})

# ── el servidor (y un /salud de mentira, de otro juego, por la «red de adentro») ──────────────────────
with contextlib.redirect_stdout(io.StringIO()):
    srv = P.servidor(0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/cuentas"


class Salud(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        cuerpo = json.dumps({"ok": True, "entorno": "prod", "juego": "gunbound", "en_linea": 7}).encode()
        if self.path == "/interno/panel/salud":                   # ★ el CONTRATO (EDA): sólo con la ficha interna
            if self.headers.get("X-Ficha-Interna") != "ficha-de-prueba-salud":
                self.send_response(404)
                self.end_headers()
                return
            cuerpo = json.dumps({"en_linea": True, "jugando": 3, "detalle": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass


salud = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Salud)
threading.Thread(target=salud.serve_forever, daemon=True).start()


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


abrir = urllib.request.build_opener(SinRedireccion).open


def pedir(metodo, ruta, datos=None, cookies=None, xr2=True):
    """-> (código, cuerpo (dict o bytes), cabeceras)."""
    cab = {"Content-Type": "application/json"}
    if xr2:
        cab["X-R2"] = "1"
    if cookies:
        cab["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    r = urllib.request.Request(URL + ruta, data=None if datos is None else json.dumps(datos).encode(), headers=cab,
                               method=metodo)
    try:
        x = abrir(r, timeout=10)
        cod, cuerpo, h = x.status, x.read(), x.headers
    except urllib.error.HTTPError as e:
        cod, cuerpo, h = e.code, e.read(), e.headers
    try:
        return cod, json.loads(cuerpo), h
    except ValueError:
        return cod, cuerpo, h


def galletas(h):
    """{nombre: (valor, atributos)} de los Set-Cookie."""
    out = {}
    for linea in h.get_all("Set-Cookie") or []:
        partes = [p.strip() for p in linea.split(";")]
        k, _, v = partes[0].partition("=")
        out[k] = (v, partes[1:])
    return out


def ida(prov="discord", destino=None):
    """POST /coordinador/api/oauth -> (código, datos, cookie del flujo, sid)."""
    V._por_ip.clear()
    cod, d, h = pedir("POST", "/coordinador/api/oauth", {"proveedor": prov, **({"destino": destino} if destino else {})})
    nav = galletas(h).get(CO.COOKIE_FLUJO, ("", []))[0]
    sid = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(d.get("url", "")).query)).get("state")
    return cod, d, nav, sid


def vuelta(sid, codigo, extra=None):
    q = {"state": sid, "code": codigo, **(extra or {})}
    cod, _, h = pedir("GET", "/oauth/vuelta?" + urllib.parse.urlencode(q))
    return cod, h.get("Location") or ""


def ticket_de(loc):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(loc).query)).get("ticket")


def entrar(codigo, prov="discord"):
    """El ingreso entero, como el navegador. -> (código del canje, datos, cookies de la sesión, Set-Cookie)."""
    _c, _d, nav, sid = ida(prov)
    _c, loc = vuelta(sid, codigo)
    cod, d, h = pedir("POST", "/coordinador/api/canjear", {"ticket": ticket_de(loc)}, {CO.COOKIE_FLUJO: nav})
    g = galletas(h)
    ses = {CO.COOKIE: g[CO.COOKIE][0]} if CO.COOKIE in g and g[CO.COOKIE][0] else None
    return cod, d, ses, g


try:
    print("· las líneas de moderadores.txt (compatibles con las de antes)")
    casos = {"110": ("110", None), "110 eda,gunbound": ("110", frozenset({"eda", "gunbound"})),
             "110   eda , gunbound  # dos": ("110", frozenset({"eda", "gunbound"})), "mod1 -": ("mod1", frozenset()),
             "110  # mod1": ("110", None), "@Nick Con Espacios": ("@Nick Con Espacios", None), "# nada": ("", None)}
    for linea, esperado in casos.items():
        ok(P.partir_linea_rol(linea) == esperado, f"«{linea}» -> {esperado}")

    print("· la lista blanca de destinos")
    ok(CO.destinos() == [PANEL], f"de R2_PANEL_URL sólo queda el origen bien formado ({CO.destinos()})")
    cod, d, nav, sid = ida(destino="https://mal.prueba")
    ok(cod == 400 and not nav, f"⟲ un destino de afuera: 400 y sin cookie (dio {cod})")
    cod, d, nav, sid = ida(destino="javascript:alert(1)")
    ok(cod == 400, f"⟲ «javascript:…»: 400 (dio {cod})")
    cod, d, nav, sid = ida(destino=PANEL + "/")
    ok(cod == 200 and nav and sid and d["url"].startswith("https://discord.com/"),
       "el destino de la lista: 200, cookie del flujo y la dirección de Discord")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(d["url"]).query))
    ok(q.get("redirect_uri") == "https://auth.prueba/cuentas/oauth/vuelta",
       "la vuelta es la YA registrada en Discord (el dominio de auth), no la del panel")
    cod, loc = vuelta(sid, "c-jefa", {"destino": "https://mal.prueba"})
    ok(cod == 302 and loc.startswith(PANEL + "/entrar?ticket="),
       f"la vuelta va al destino GUARDADO aunque el pedido traiga otro ({loc[:40]}…)")
    cod, d, nav, sid = ida()
    os.environ["R2_PANEL_URL"] = "https://otro.prueba"
    cod, loc = vuelta(sid, "c-jefa")
    ok(cod == 400 and not loc, f"⟲ si el destino salió de la lista entre ida y vuelta: 400 sin redirección (dio {cod})")
    os.environ["R2_PANEL_URL"] = ""
    cod, d, nav, sid = ida()
    ok(cod == 503, f"sin R2_PANEL_URL el panel no deja empezar (503, dio {cod})")
    os.environ["R2_PANEL_URL"] = PANEL

    print("· el ingreso del ADMIN y la cookie")
    cod, d, ses, g = entrar("c-jefa")
    ok(cod == 200 and d.get("rol") == "admin" and ses, f"la admin entra con Discord (canje {cod})")
    attrs = g.get(CO.COOKIE, ("", []))[1]
    ok({"HttpOnly", "Secure", "SameSite=Strict", "Path=/", f"Max-Age={8 * 3600}"} <= set(attrs),
       f"la cookie: HttpOnly · Secure · SameSite=Strict · Path=/ · 8 h ({attrs})")
    ok(g.get(CO.COOKIE_FLUJO, ("x",))[0] == "", "la cookie del flujo se borra al canjear")
    S_JEFA = ses
    cod, d, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_JEFA)
    ok(cod == 200 and [j["id"] for j in d["juegos"]] == ["r2beat2013", "gunbound", "eda", "r2beat-moderno", "wolfteam"],
       "con la cookie, la admin ve los 5 juegos del catálogo")
    cod, d, _ = pedir("GET", "/coordinador/api/juegos")
    ok(cod == 401, f"⟲ sin cookie: 401 (dio {cod})")
    cod, d, _ = pedir("GET", "/coordinador/api/juegos", cookies={CO.COOKIE: "inventada"})
    ok(cod == 401, f"⟲ con una cookie inventada: 401 (dio {cod})")
    cod, d, _ = pedir("GET", "/coordinador/api/estado", cookies=S_JEFA)
    ok(cod == 200 and d["sesion"]["rol"] == "admin" and d["proveedores"] == {"google": True, "discord": True},
       "/api/estado dice quién es y qué proveedores andan")

    print("· el TICKET")
    _c, _d, nav, sid = ida()
    _c, loc = vuelta(sid, "c-jefa")
    t = ticket_de(loc)
    cod1, _, h1 = pedir("POST", "/coordinador/api/canjear", {"ticket": t}, {CO.COOKIE_FLUJO: nav})
    cod2, d2, h2 = pedir("POST", "/coordinador/api/canjear", {"ticket": t}, {CO.COOKIE_FLUJO: nav})
    ok(cod1 == 200, "el 1.º canje anda")
    ok(cod2 == 400 and d2.get("error") == "vencido" and not galletas(h2).get(CO.COOKIE, ("",))[0],
       f"⟲ el 2.º canje del MISMO ticket falla ({cod2}) y no da sesión")
    crudo = open(os.path.join(tmp, "portero.db"), "rb").read() + (open(os.path.join(tmp, "portero.db-wal"), "rb").read()
                                                                 if os.path.isfile(os.path.join(tmp, "portero.db-wal")) else b"")
    ok(t.encode() not in crudo and P._propia().execute("SELECT 1 FROM tickets_panel WHERE huella = ?",
                                                       (CO._sha(t),)).fetchone(),
       "en la base queda SÓLO la huella del ticket, nunca el ticket")
    t0 = time.time()
    tv = CO.emitir_ticket(P, "sesion", UID["jefa"], "discord", "", None, t0)
    cod, d, tok = CO.canjear(P, tv, None, "1.2.3.4", t0 + 61)
    ok(cod == 400 and d["error"] == "vencido" and not tok, f"⟲ un ticket de hace 61 s está vencido ({cod})")
    tv = CO.emitir_ticket(P, "sesion", UID["jefa"], "discord", "", None, t0)
    cod, d, tok = CO.canjear(P, tv, None, "1.2.3.5", t0 + 59)
    ok(cod == 200 and tok, f"el mismo, a los 59 s, anda ({cod})")
    ok(CO.TICKET_SEG <= 60, f"el ticket vive {CO.TICKET_SEG} s (≤ 60)")
    _c, _d, nav, sid = ida()
    _c, loc = vuelta(sid, "c-jefa")
    cod, d, h = pedir("POST", "/coordinador/api/canjear", {"ticket": ticket_de(loc)}, {CO.COOKIE_FLUJO: "otro-navegador"})
    ok(cod == 400 and d.get("error") == "otro_navegador", f"⟲ el ticket en OTRO navegador (otra cookie del flujo) no sirve ({cod})")
    cod, d, h = pedir("POST", "/coordinador/api/canjear", {"ticket": ticket_de(loc)}, {CO.COOKIE_FLUJO: nav})
    ok(cod == 400, "⟲ y ese intento ya lo gastó: tampoco sirve después en el bueno")
    cod, d, h = pedir("POST", "/coordinador/api/canjear", {"ticket": "a" * 43})
    ok(cod == 400 and d.get("error") == "vencido", f"⟲ un ticket inventado: 400 ({cod})")
    cod, d, h = pedir("POST", "/coordinador/api/canjear", {"ticket": t}, {CO.COOKIE_FLUJO: nav}, xr2=False)
    ok(cod == 403, f"⟲ un POST sin X-R2 (otro sitio) no llega ni al canje ({cod})")
    P._fallos.clear()

    print("· sin vínculo, sin rol, suspendida")
    cod, d, ses, g = entrar("c-nadie")
    ok(cod == 403 and d.get("error") == "no_vinculada" and d.get("nombre") == "kai_ritmo" and not ses,
       f"un Discord SIN vincular: no_vinculada, sin sesión ({cod})")
    cod, d, ses, g = entrar("c-sinrol")
    ok(cod == 403 and d.get("error") == "sin_permisos" and d.get("eid") == UID["sinrol"] and not ses,
       f"un Eñeños-ID vinculado pero SIN rol: sin_permisos con su Eñeños-ID, sin sesión ({cod})")
    cod, d, ses, g = entrar("c-susp")
    ok(cod == 403 and d.get("error") == "suspendida" and not ses, f"una cuenta del equipo SUSPENDIDA: sin sesión ({cod})")
    _c, _d, nav, sid = ida()
    _c, loc = vuelta(sid, "c-viejo")
    open(MOD_TXT, "w", encoding="utf-8").write(f"{UID['modgb']} gunbound\n")
    cod, d, h = pedir("POST", "/coordinador/api/canjear", {"ticket": ticket_de(loc)}, {CO.COOKIE_FLUJO: nav})
    ok(cod == 403 and d.get("error") == "sin_permisos", f"⟲ el rol se le quitó ENTRE la vuelta y el canje: sin sesión ({cod})")
    open(MOD_TXT, "w", encoding="utf-8").write(MODS_BASE)
    P._moderadores["fecha"] = None
    _c, _d, nav, sid = ida()
    cod, loc = vuelta(sid, "", {"error": "access_denied"})
    cod, d, h = pedir("POST", "/coordinador/api/canjear", {"ticket": ticket_de(loc)}, {CO.COOKIE_FLUJO: nav})
    ok(cod == 400 and d.get("error") == "cancelada", f"cancelar en Discord: cancelada, sin sesión ({cod})")

    print("· el MODERADOR con juegos asignados (gunbound)")
    cod, d, S_MOD, g = entrar("c-modgb", "google")
    ok(cod == 200 and d.get("rol") == "moderador" and S_MOD, f"la moderadora entra con Google ({cod})")
    cod, d, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_MOD)
    ok([j["id"] for j in d["juegos"]] == ["gunbound"], f"ve SÓLO GunBound ({[j['id'] for j in d['juegos']]})")
    cod, d, _ = pedir("GET", "/coordinador/api/estado", cookies=S_MOD)
    ok(d["sesion"]["juegos"] == ["gunbound"] and not d["sesion"]["lista_vieja"], "/api/estado: sus juegos = [gunbound]")
    J = UID["jugadora"]
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "banear", "uid": J, "pase": "eda", "detalle": "x"}, S_MOD)
    ok(cod == 403, f"⟲ NO puede banear en EDA (no asignado): {cod}")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "aprobar", "uid": J, "pase": "r2beat2013-subir"}, S_MOD)
    ok(cod == 403, f"⟲ ni aprobar en un pase de R2Beat: {cod}")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "banear", "uid": J, "pase": "gunbound", "detalle": "trampa", "horas": 2}, S_MOD)
    ok(cod == 200 and P._propia().execute("SELECT 1 FROM baneos WHERE uid = ? AND juego = 'gunbound'", (J,)).fetchone(),
       f"en GunBound SÍ banea ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "banear", "uid": J, "pase": "gunbound-prueba", "motivo": "trampa", "dias": 1}, S_MOD)
    ok(cod == 200, f"y en el servidor de prueba de GunBound (es del mismo juego) ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "banear", "uid": J, "pase": "eda", "detalle": "x"}, S_JEFA)
    ok(cod == 200, f"la ADMIN sí banea en EDA ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "banear", "uid": UID["jefa"], "pase": "gunbound"}, S_MOD)
    ok(cod == 403, f"⟲ la moderadora no toca una cuenta del equipo ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "borrar", "uid": J, "pase": "gunbound"}, S_MOD)
    ok(cod == 400, f"⟲ una acción inventada: 400 ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "aprobar", "uid": "1 OR 1=1", "pase": "gunbound"}, S_MOD)
    ok(cod == 400, f"⟲ un uid que no es número: 400 ({cod})")

    print("· el moderador del formato VIEJO (sin lista) sigue como antes")
    cod, d, S_VIEJO, g = entrar("c-viejo")
    cod, d, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_VIEJO)
    ok(cod == 200 and len(d["juegos"]) == 5, "ve todos los juegos")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "aprobar", "uid": J, "pase": "eda"}, S_VIEJO)
    ok(cod == 200, f"aprueba en EDA ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/accion", {"accion": "banear", "uid": J, "pase": "gunbound"}, S_VIEJO)
    ok(cod == 403, f"⟲ pero NO banea (Benja, 12-nov: «sin banear») ({cod})")

    print("· lo que ve cada uno de una persona")
    cod, dm, _ = pedir("GET", f"/coordinador/api/persona/{J}", cookies=S_MOD)
    cod2, da, _ = pedir("GET", f"/coordinador/api/persona/{J}", cookies=S_JEFA)
    pm, pa = dm.get("persona", {}), da.get("persona", {})
    ok([j["id"] for j in pm.get("juegos", [])] == ["gunbound"] and len(pa.get("juegos", [])) == 5,
       "la moderadora ve sus permisos SÓLO en GunBound ⟲ la admin, en los 5")
    gb = next(j for j in pm["juegos"] if j["id"] == "gunbound")
    ok({x["pase"] for x in gb["pases"]} == {"gunbound", "gunbound-prueba"} and all(x["baneada"] for x in gb["pases"]),
       "GunBound con sus dos servidores (PROD y TEST), los dos baneados")
    ok("usuario" not in pm and "jugadora" not in json.dumps(dm) and "Pía" not in json.dumps(dm, ensure_ascii=False),
       "⛔ a la moderadora no le llega el login ni el nombre de Google de la persona")
    ok(pa.get("usuario") == "jugadora" and pa["vinculos"][0].get("nombre") == "Pía Nombre Real",
       "⟲ a la admin sí")
    cod, d, _ = pedir("GET", f"/coordinador/api/persona/{UID['jefa']}", cookies=S_MOD)
    ok(cod == 403, f"⟲ la moderadora no abre una cuenta del equipo ({cod})")
    cod, d, _ = pedir("GET", f"/coordinador/api/persona/{UID['jefa']}", cookies=S_JEFA)
    ok(cod == 200, "la admin sí")
    cod, d, _ = pedir("GET", "/coordinador/api/personas?q=jug", cookies=S_MOD)
    ok(cod == 200 and d["personas"] == [], "⛔ la moderadora no encuentra por el COMIENZO de un login")
    cod, d, _ = pedir("GET", "/coordinador/api/personas?q=jugadora", cookies=S_MOD)
    ok([p["uid"] for p in d["personas"]] == [J] and "usuario" not in d["personas"][0],
       "con el login EXACTO sí, pero la respuesta no lo trae")
    cod, d, _ = pedir("GET", "/coordinador/api/personas?q=pixel", cookies=S_MOD)
    ok([p["uid"] for p in d["personas"]] == [J], "por el Ñ2-ID (apodo) la encuentra")
    cod, d, _ = pedir("GET", f"/coordinador/api/personas?q=%23{J}", cookies=S_MOD)
    ok([p["uid"] for p in d["personas"]] == [J], "y por el Eñeños-ID (#número)")
    cod, d, _ = pedir("GET", "/coordinador/api/personas?q=jef", cookies=S_MOD)
    cod2, d2, _ = pedir("GET", "/coordinador/api/personas?q=laje", cookies=S_MOD)
    ok(d["personas"] == [] and d2["personas"] == [], "⛔ las cuentas del equipo no salen en su buscador")
    cod, d, _ = pedir("GET", "/coordinador/api/personas?q=jug", cookies=S_JEFA)
    ok([p["uid"] for p in d["personas"]] == [J] and d["personas"][0].get("usuario") == "jugadora",
       "⟲ la admin encuentra por el comienzo del login, y lo ve")

    print("· invitaciones y lanzamientos, por juego")
    tok = P.abrir_sesion(J)
    import servidor.lanzamientos as LZ
    LZ._discord_en_hilo = lambda *_a: None
    P._propia().execute("DELETE FROM aprobados WHERE uid = ?", (J,))
    P._propia().commit()
    for jj in ("eda", "gunbound"):
        LZ.pedir(P, tok, jj)
    cod, d, _ = pedir("GET", "/coordinador/api/invitaciones", cookies=S_MOD)
    cod2, d2, _ = pedir("GET", "/coordinador/api/invitaciones", cookies=S_JEFA)
    ok([v["juego"] for v in d["invitaciones"]] == ["gunbound"] and "usuario" not in d["invitaciones"][0],
       "la moderadora ve SÓLO la invitación de GunBound (sin el login)")
    ok(sorted(v["juego"] for v in d2["invitaciones"]) == ["eda", "gunbound"], "⟲ la admin ve las dos")
    id_eda = next(v["id"] for v in d2["invitaciones"] if v["juego"] == "eda")
    id_gb = next(v["id"] for v in d2["invitaciones"] if v["juego"] == "gunbound")
    cod, d, _ = pedir("POST", "/coordinador/api/invitacion", {"id": id_eda, "accion": "rechazar"}, S_MOD)
    ok(cod == 403, f"⟲ no decide la de EDA ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/invitacion", {"id": id_gb, "accion": "rechazar"}, S_MOD)
    ok(cod == 200 and d["invitacion"]["estado"] == "rechazada" and d["invitacion"]["quien"] == "Artillera",
       f"la de GunBound sí (quién decidió sale con su Ñ2-ID, no con el login) ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/invitacion", {"id": id_eda, "accion": "aprobar"}, S_JEFA)
    ok(cod == 200 and d["invitacion"]["estado"] == "aprobada" and P._propia().execute(
        "SELECT 1 FROM aprobados WHERE uid = ? AND juego = 'eda'", (J,)).fetchone(),
       "la admin aprueba la de EDA y la persona queda aprobada")
    cod, d, _ = pedir("GET", "/coordinador/api/lanzamientos", cookies=S_MOD)
    ok([l["clave"] for l in d["lanzamientos"]] == ["gunbound"], "lanzamientos: la moderadora ve SÓLO el de GunBound")
    cod, d, _ = pedir("GET", "/coordinador/api/lanzamientos", cookies=S_JEFA)
    ok([l["clave"] for l in d["lanzamientos"]] == ["eda", "gunbound", "r2beat-moderno"], "⟲ la admin, los tres")

    print("· la auditoría")
    cod, d, _ = pedir("GET", "/coordinador/api/auditoria", cookies=S_MOD)
    txt = json.dumps(d, ensure_ascii=False)
    ok(cod == 200 and d["auditoria"] and all(a["juego"] == "gunbound" for a in d["auditoria"]),
       f"la moderadora ve SÓLO movimientos de GunBound ({len(d['auditoria'])})")
    ok("jefa" not in txt and "jugadora" not in txt and "modgb" not in txt and "127.0.0.1" not in txt,
       "⛔ ni un login ni una IP en su auditoría")
    ok(any(a["accion"] == "rechazar invitación" for a in d["auditoria"]), "el rechazo de la invitación quedó")
    cod, d, _ = pedir("GET", "/coordinador/api/auditoria", cookies=S_JEFA)
    ok(any(a["accion"] == "entrar al Coordinador" and a["quien"] == "jefa" for a in d["auditoria"])
       and any(a["juego"] == "eda" for a in d["auditoria"]), "⟲ la admin ve todo: los ingresos (con su login) y EDA")

    print("· MODERADORES Y PERMISOS (sólo admin)")
    cod, d, _ = pedir("GET", "/coordinador/api/equipo", cookies=S_MOD)
    ok(cod == 403, f"⟲ la moderadora no ve el equipo ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/equipo", {"accion": "juegos", "uid": UID["modgb"], "juegos": ["eda"]}, S_MOD)
    ok(cod == 403 and P.juegos_de_moderador(UID["modgb"]) == {"gunbound"}, f"⟲ ni se asigna juegos ({cod})")
    cod, d, _ = pedir("GET", "/coordinador/api/equipo", cookies=S_JEFA)
    mods = {m["uid"]: m for m in d.get("moderadores", [])}
    ok(cod == 200 and mods[UID["modgb"]]["juegos"] == ["gunbound"] and mods[UID["modviejo"]]["juegos"] is None,
       "la admin ve el equipo: la de GunBound y el del formato viejo (sin lista)")
    cod, d, _ = pedir("POST", "/coordinador/api/equipo", {"accion": "agregar", "uid": str(UID["nueva"]), "juegos": []}, S_JEFA)
    ok(cod == 200 and "aviso" in d, f"agrega a una cuenta sin Discord ni Google (y avisa que no podrá entrar) ({cod})")
    txt = open(MOD_TXT, encoding="utf-8").read()
    ok(f"{UID['nueva']} -" in txt and "# la de GunBound" in txt and "# moderadores de prueba" in txt,
       "moderadores.txt: la línea nueva con «-» (ninguno), y el resto y los comentarios intactos")
    c = P._cuentas()
    c.execute("INSERT INTO vinculos (proveedor, externo, uid, nombre, creado) VALUES ('discord', 'd-nueva', ?, 'n', 'hoy')",
              (UID["nueva"],))
    c.commit()
    cod, d, S_NUEVA, g = entrar("c-nueva")
    cod2, d2, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_NUEVA)
    ok(cod == 200 and d2["juegos"] == [], "ya vinculada, entra, pero sin juegos asignados no ve ninguno")
    cod, d, _ = pedir("POST", "/coordinador/api/equipo", {"accion": "juegos", "uid": UID["nueva"], "juegos": ["eda", "inventado"]}, S_JEFA)
    ok(cod == 400, f"⟲ un juego que no está en el catálogo: 400 ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/equipo", {"accion": "juegos", "uid": UID["nueva"], "juegos": ["eda"]}, S_JEFA)
    cod2, d2, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_NUEVA)
    ok(cod == 200 and [j["id"] for j in d2["juegos"]] == ["eda"], "la admin le asigna EDA y desde el próximo pedido lo ve")
    cod, d, _ = pedir("POST", "/coordinador/api/equipo", {"accion": "agregar", "uid": UID["jefa"], "juegos": []}, S_JEFA)
    ok(cod == 409, f"⟲ una ADMIN no se agrega como moderadora ({cod})")
    cod, d, _ = pedir("POST", "/coordinador/api/equipo", {"accion": "quitar", "uid": UID["nueva"]}, S_JEFA)
    cod2, _, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_NUEVA)
    ok(cod == 200 and cod2 == 401 and str(UID["nueva"]) not in open(MOD_TXT, encoding="utf-8").read(),
       f"sacarla del equipo le corta la sesión al instante ({cod2}) y borra su línea")
    cod, d, _ = pedir("GET", "/coordinador/api/auditoria", cookies=S_JEFA)
    acc = [a["accion"] for a in d["auditoria"]]
    ok(all(x in acc for x in ("equipo: agregar moderador", "equipo: juegos del moderador", "equipo: quitar moderador")),
       "los tres cambios del equipo quedaron en la auditoría")
    open(MOD_TXT, "w", encoding="utf-8").write(f"{UID['modviejo']}\n")
    cod, _, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_MOD)
    ok(cod == 401, f"⟲ editar moderadores.txt a mano también corta al instante ({cod})")
    open(MOD_TXT, "w", encoding="utf-8").write(MODS_BASE)

    print("· el estado de los servidores: sólo con fuente")
    os.environ["R2_PANEL_SALUD"] = (f"gunbound=http://127.0.0.1:{salud.server_address[1]}/salud;"
                                    "eda=http://127.0.0.1:9/salud")
    CO._salud.clear()
    cod, d, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_JEFA)
    js = {j["id"]: j for j in d["juegos"]}
    ok(js["gunbound"]["servidores"]["live"] == {"estado": "en_linea", "jugando": 7},
       "GunBound PROD: «en línea · 7 jugando», del /salud de verdad")
    ok(js["gunbound"]["servidores"]["test"] is None and js["r2beat2013"]["servidores"] == {"live": None, "test": None},
       "⟲ sin fuente (GunBound TEST, R2Beat): NADA, ni un 0")
    ok(js["eda"]["servidores"]["live"] == {"estado": "sin_respuesta", "jugando": None},
       "una fuente que no contesta: «sin respuesta» y sin número")
    ok(js["wolfteam"]["tiene_servidor"] is False and js["wolfteam"]["servidores"] == {"live": None, "test": None},
       "Wolf Team (sin servidor): sin estado")
    os.environ.pop("R2_PANEL_SALUD")

    print("· ★ 21-nov el estado de un servidor con el CONTRATO (EDA): su salud, con la ficha interna")
    base = f"http://127.0.0.1:{salud.server_address[1]}"
    os.environ["R2_PANEL_GESTION"] = f"eda=contrato1:{base}/interno/panel"
    os.environ["R2_CUENTAS_FICHA_INTERNA"] = "ficha-de-prueba-salud"
    CO._salud.clear()
    js = {j["id"]: j for j in pedir("GET", "/coordinador/api/juegos", cookies=S_JEFA)[1]["juegos"]}
    ok(js["eda"]["servidores"]["live"] == {"estado": "en_linea", "jugando": 3},
       "EDA PROD: «en línea · 3», de su `salud` del contrato (antes: «sin datos»)")
    ok(js["eda"]["servidores"]["test"] is None, "⟲ EDA TEST, sin servidor gestionado: nada")
    os.environ["R2_CUENTAS_FICHA_INTERNA"] = "otra-ficha"
    CO._salud.clear()
    js = {j["id"]: j for j in pedir("GET", "/coordinador/api/juegos", cookies=S_JEFA)[1]["juegos"]}
    ok(js["eda"]["servidores"]["live"] == {"estado": "sin_respuesta", "jugando": None},
       "⟲ con otra ficha el servidor dice 404: «sin respuesta», sin número")
    os.environ["R2_CUENTAS_FICHA_INTERNA"] = "ficha-de-prueba-salud"
    os.environ["R2_PANEL_SALUD"] = f"eda={base}/salud"
    CO._salud.clear()
    js = {j["id"]: j for j in pedir("GET", "/coordinador/api/juegos", cookies=S_JEFA)[1]["juegos"]}
    ok(js["eda"]["servidores"]["live"]["jugando"] == 7, "⟲ si R2_PANEL_SALUD lo nombra, manda ése (7, no 3)")
    for k in ("R2_PANEL_SALUD", "R2_PANEL_GESTION", "R2_CUENTAS_FICHA_INTERNA"):
        os.environ.pop(k)
    CO._salud.clear()

    print("· la página")
    cod, d, h = pedir("GET", "/coordinador/api/catalogo")
    gb = next(j for j in d["juegos"] if j["id"] == "gunbound")
    eda = next(j for j in d["juegos"] if j["id"] == "eda")
    ok(cod == 200 and gb["arte"] == "arte/fondo-gunbound.jpg" and eda["arte"] is None and gb["nombre"] == "GunBound"
       and eda["nombre"] == "EDA", "el catálogo (sin sesión): arte sólo si el archivo está en la carpeta; si no, null")
    ok("servidores" not in gb and "invitaciones" not in gb, "⟲ sin sesión no trae ni servidores ni invitaciones")
    cod, cuerpo, h = pedir("GET", "/coordinador/")
    ok(cod == 200 and b"panel.js" in cuerpo and "script-src 'self'" in (h.get("Content-Security-Policy") or "")
       and h.get("X-Frame-Options") == "DENY" and h.get("Referrer-Policy") == "no-referrer",
       "la página: CSP sin scripts de afuera, sin marcos y sin referer (el ticket no se filtra)")
    cod, cuerpo, h = pedir("GET", "/coordinador/entrar?ticket=x")
    ok(cod == 200 and b"panel.js" in cuerpo and h.get("Cache-Control") == "no-store", "/entrar también la sirve, sin caché")
    cod, _, h = pedir("GET", "/coordinador")
    ok(cod == 301 and h.get("Location") == "/cuentas/coordinador/", "sin la barra final: 301 a la carpeta")
    for ruta in ("/coordinador/assets/..%2F..%2Fportero.py", "/coordinador/assets/../coordinador.py",
                 "/coordinador/arte/..%2Fportero.db", "/coordinador/arte/nada.jpg", "/coordinador/assets/x.py"):
        cod, _, _ = pedir("GET", ruta)
        ok(cod == 404, f"⟲ {ruta}: 404 ({cod})")
    cod, cuerpo, h = pedir("GET", "/coordinador/arte/fondo-gunbound.jpg")
    ok(cod == 200 and h.get("Content-Type") == "image/jpeg", "el arte que sí está: 200 image/jpeg")
    cod, cuerpo, h = pedir("GET", "/coordinador/assets/enenos-team.png")
    ok(cod == 200 and h.get("Content-Type") == "image/png", "el logo de la marca (en el repo): 200")
    os.environ["R2_CUENTAS_DUENA"] = ""
    cod, _, _ = pedir("GET", "/coordinador/api/estado")
    os.environ["R2_CUENTAS_DUENA"] = "1"
    cod2, _, _ = pedir("GET", "/coordinador/api/estado")
    ok(cod == 404 and cod2 == 200, f"⟲ sin Cuenta Eñeños dueña el panel no existe (404) ({cod} / {cod2})")

    print("· la página cumple su CSP (★ 20-nov fase B: el panel creció; que no se cuele nada que la CSP bloquee)")
    import re as _re

    def fuera_de_csp(texto):
        """Lo que la CSP del panel (script-src 'self', img-src 'self' data:, sin inline) rompería o dejaría pasar."""
        malos = []
        if _re.search(r"""\son[a-z]+\s*=\s*["'\\]""", texto):
            malos.append("un manejador en línea (onclick=…)")
        if _re.search(r"<script(?![^>]*\bsrc=)[^>]*>", texto):
            malos.append("un <script> en línea")
        sin_ns = _re.sub(r"xmlns(:\w+)?=['\"]http://www\.w3\.org/[^'\"]*['\"]", "", texto)
        if _re.search(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//|url\(\s*["']?\s*(?:https?:)?//""", sin_ns):
            malos.append("algo de afuera (src/href/url con http)")
        if _re.search(r"\beval\s*\(|new Function\s*\(", texto):
            malos.append("eval / new Function")
        return malos

    panel = os.path.join(RAIZ, "servidor", "panel")
    for nombre in ("index.html", "panel.js", "panel.css"):
        with open(os.path.join(panel, nombre), encoding="utf-8") as f:
            malos = fuera_de_csp(f.read())
        ok(not malos, f"{nombre}: nada que la CSP bloquee ({', '.join(malos) or 'limpio'})")
    for trampa in ('<button onclick="x()">', "`<img src=x onerror='y'>`", "<script>alert(1)</script>",
                   '<img src="https://afuera.com/a.png">', "background: url(//cdn.afuera/x.png)", "eval('1')"):
        ok(bool(fuera_de_csp(trampa)), f"⟲ la revisión caza {trampa!r}")
    ok(not fuera_de_csp('<script src="panel.js"></script><svg xmlns="http://www.w3.org/2000/svg"></svg>'),
       "⟲ y no confunde un <script src> ni un xmlns de SVG")

    print("· salir")
    cod, d, h = pedir("POST", "/coordinador/api/salir", {}, S_JEFA)
    cod2, _, _ = pedir("GET", "/coordinador/api/juegos", cookies=S_JEFA)
    ok(cod == 200 and cod2 == 401 and galletas(h)[CO.COOKIE][0] == "", f"salir mata la sesión ({cod2})")
finally:
    srv.shutdown()
    salud.shutdown()
    P.cerrar_conexiones()
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\nprobar_coordinador: {'VERDE' if not fallos else 'ROJO'} · {len(fallos)} mal")
for f in fallos:
    print("  ✘ " + f)
sys.exit(1 if fallos else 0)
