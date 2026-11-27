# -*- coding: utf-8 -*-
"""probar_gestion — la FASE C del panel del Coordinador (servidor/gestion.py), 20-nov-2026: la gestión de cada juego,
con permisos asignables por acción y CUPOS por moderador y juego (Eñeños: «con cupo y permisos asignables para X
acción también»). El panel del juego es uno DE MENTIRA (habla como `/api/interno/panel/…` de R2Beat y devuelve IPs y
logins a propósito); el Coordinador y el portero son los de verdad.

Cada regla con su control al revés (⟲):
  1 · sólo ADMIN en R2_VEN_IPS ve las IP (el resto de los ADMIN ve el login, sin IP); ⟲ lista vacía/ausente: nadie;
      ⟲ moderador listado tampoco (y nunca un login)
  2 · BASE del moderador: mirar, avisar, echar ⟲ dar Rcoin sin permiso: 403 y no viaja nada
  3 · ⟲ lista cerrada: respaldo, ip/…, ban… dan 404 aunque sea ADMIN
  4 · repartir permisos: sólo ADMIN ⟲ un juego no asignado: 409 ⟲ una acción inventada: 400
  5 · el CUPO: se gasta al sumar ⟲ pasarse: 403 y no viaja ⟲ restar no gasta ⟲ «poner» no (es de ADMIN)
      ⟲ si el juego dice que no, se devuelve ⟲ dos a la vez no pasan el cupo
  6 · ⟲ el moderador de otro juego: 404 · ⟲ el de formato viejo: 403
  7 · cada acción queda en la auditoría del Coordinador
  8 · ★ el CONTRATO común (GunBound/EDA, «contrato1:»): sus rutas, y la moneda con cupo POR MONEDA
      ⟲ las rutas del panel viejo de R2Beat no pasan ⟲ «rcoin» no se le asigna a un juego del contrato
      ⟲ una moneda sin cupo asignado: 403 ⟲ pasarse del cupo de oro: 403 y no viaja ⟲ el cash no gasta el del oro
"""
import contextlib
import io
import copy
import json
import urllib.parse
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


FICHA = "ficha-de-prueba"
VISTO = []
LOCK = threading.Lock()
PRIVADOS = {"ip": "192.0.2.5", "ips": [{"ip": "192.0.2.5", "pais": "PE"}], "login": "cuenta5",
            "username": "cuenta5", "geoip": {"pais": "PE"}, "misma_ip": [{"uid": 7, "nick": "Jugador7"}],
            "comparte_ip": 2, "misma_ip_total": 2, "comparten_ip": 2}


# ★ 27-nov · el catálogo del juego falso: una PRENDA (7 / 30 días o permanente), una CAMPANA (se gasta) y un ítem sin plazos
CATALOGO = [{"id": 30220852, "nombre": "Pelo Amor Milenario (M)", "familia": "wardrobe_hair", "cargas": False,
             "duraciones": ["P7", "P30", "PI"]},
            {"id": 1000200, "nombre": "Campana", "familia": "etc", "cargas": True, "duraciones": []},
            {"id": 777, "nombre": "Un pack", "familia": "etc", "cargas": False, "duraciones": []},
            {"id": 1000961, "nombre": "Pose de Pareja", "familia": "dance_emote", "cargas": False, "duraciones": ["P7", "P30"]},
            # ★ 27-nov · collab: una tarjeta (7/30 días), un anillo de uso único (PN), y una tarjeta que NO es collab
            {"id": 1000995, "nombre": "Slot para Game id Sakura Galaxia", "familia": "namecard", "cargas": False,
             "duraciones": ["P7", "P30"]},
            {"id": 30868, "nombre": "Anillo Crucero del Cielo", "familia": "ring_couple", "cargas": False, "duraciones": ["PN"]},
            {"id": 1000123, "nombre": "Tarjeta de fábrica", "familia": "namecard", "cargas": False, "duraciones": ["P30"]},
            {"id": 1000265, "nombre": "Ceremonia Justa", "familia": "dance_emote", "cargas": False, "duraciones": ["P1"]}]


# ★ 27-nov · los cupones del juego falso: de modr2 (por canjear, usado, apagado, vencido) y uno de la jefa
CUPONES_JUEGO = [
    {"codigo": "MIOABCDEF12", "creador": "coordinador:modr2", "usos": 1, "usados": 0, "activo": True, "vence": None, "nota": "mío"},
    {"codigo": "AJENO9876543", "creador": "coordinador:jefa", "usos": 1, "usados": 0, "activo": True, "vence": None, "nota": "de ella"},
    {"codigo": "USADOXYZ0001", "creador": "coordinador:modr2", "usos": 1, "usados": 1, "activo": True, "vence": None, "nota": ""},
    {"codigo": "APAGADO00001", "creador": "coordinador:modr2", "usos": 2, "usados": 0, "activo": False, "vence": None, "nota": ""},
    {"codigo": "VIEJO0000001", "creador": "coordinador:modr2", "usos": 1, "usados": 0, "activo": False, "vence": 1.0, "nota": ""}]


def respuesta():
    return {"filas": [{"uid": 5, "nick": "Jugador5", "pais": "PE", **PRIVADOS,
                       "datos": dict(PRIVADOS), "sesiones": [dict(PRIVADOS, inicio=1)]}], "total": 1,
            "campos": [{"nombre": "IP", "valor": PRIVADOS["ip"]}, {"nombre": "Login", "valor": "cuenta5"},
                       {"nombre": "Comparten su IP", "valor": 2}, {"nombre": "País", "valor": "PE"}],
            "detalle": [{"nombre": "IPs", "valor": [PRIVADOS["ip"]]}]}


class Juego(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _mandar(self, cod, d):
        b = json.dumps(d).encode()
        self.send_response(cod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _anotar(self, cuerpo=None):
        with LOCK:
            VISTO.append({"ruta": self.path, "quien": self.headers.get("X-Coordinador-Quien"),
                          "admin": self.headers.get("X-Coordinador-Admin"), "cuerpo": cuerpo})

    def do_GET(self):
        if self.headers.get("X-Ficha-Interna") != FICHA:
            return self._mandar(404, {"error": "no existe"})
        self._anotar()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q", [""])[0]
        if self.path.split("?")[0].endswith("/catalogo") and q.isdigit():   # ★ 27-nov: lo que mira `_cupon_de_ropa`
            return self._mandar(200, {"filas": [f for f in CATALOGO if str(f["id"]) == q]})
        if self.path.split("?")[0].endswith("/cupones"):                    # ★ 27-nov: la lista de cupones
            return self._mandar(200, dict(respuesta(), cupones=copy.deepcopy(CUPONES_JUEGO)))
        if self.path.split("?")[0].endswith("/cupones/canjes"):
            return self._mandar(200, dict(respuesta(), canjes=[{"uid": 5, "apodo": "Jugador5", "cuando": 1}]))
        return self._mandar(200, respuesta())

    def do_POST(self):
        if self.headers.get("X-Ficha-Interna") != FICHA or self.headers.get("X-R2") != "1":
            return self._mandar(404, {"error": "no existe"})
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        self._anotar(d)
        if d.get("valor") == 333 or d.get("cantidad") == 222:
            return self._mandar(400, dict(respuesta(), error="ese uid no tiene personaje"))
        if self.path.split("?")[0].endswith("/gmnpc") and d.get("npc"):      # ★ 27-nov: la GM NPC recién creada
            return self._mandar(200, dict(respuesta(), ok=True, usuario="gmnpc_ab12cd34", clave="Cl4ve-de-1-uso", nick="GM-King"))
        return self._mandar(200, dict(respuesta(), ok=True, antes="luna", despues=d.get("licencia", "luna")))


juego_srv = ThreadingHTTPServer(("127.0.0.1", 0), Juego)
threading.Thread(target=juego_srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{juego_srv.server_address[1]}/api/interno/panel"

tmp = tempfile.mkdtemp(prefix="gestion_")
os.makedirs(os.path.join(tmp, "config"))
os.environ.update({
    "R2_CUENTAS_DUENA": "1",
    "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"),
    "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe_datos.db"),
    "R2_ADMIN_ARCHIVO": os.path.join(tmp, "config", "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "config", "moderadores.txt"),
    "R2_PORTERO_PUERTO": "0",
    "R2_CUENTAS_UID_DESDE": "10000000",
    "R2_CUENTAS_FICHA_INTERNA": FICHA,
    "R2_PANEL_GESTION": f"r2beat2013={URL}",
    "R2_VEN_IPS": "",
})
for k in ("R2_PANEL_SALUD", "R2_PRESENCIA", "R2_DISCORD_EVENTOS_WEBHOOK", "R2_JUEGOS_CATALOGO", "R2_UID_NUEVAS_DESDE"):
    os.environ.pop(k, None)

from servidor import portero as P          # noqa: E402
from servidor import coordinador as CO     # noqa: E402
from servidor import gestion as GE         # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    UID = {}
    for i, u in enumerate(["jefa", "modr2", "modgb", "modviejo"]):
        UID[u] = P.registrar(u, clave_txt=f"clave-{u}", ip=f"10.3.0.{i}")[1]["uid"]
open(os.environ["R2_ADMIN_ARCHIVO"], "w", encoding="utf-8").write(f"{UID['jefa']}\n")
open(os.environ["R2_MODERADOR_ARCHIVO"], "w", encoding="utf-8").write(
    f"{UID['modr2']} r2beat2013\n{UID['modgb']} gunbound\n{UID['modviejo']}\n")
JEFA, MR2, MGB, VIEJO = (UID[k] for k in ("jefa", "modr2", "modgb", "modviejo"))


def callado(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return f(*a, **k)


def pedir(viewer, metodo, ruta, cuerpo=None, entorno="live", juego="r2beat2013", query=None):
    return callado(GE.pedir, CO, P, viewer, juego, entorno, metodo, ruta,
                   query=query if query is not None else ({"q": "x"} if metodo == "GET" else None), cuerpo=cuerpo)


def dado(uid, k="rcoin"):
    r = P._propia().execute(f"SELECT dado_{k} FROM permisos_juego WHERE uid = ? AND juego = 'r2beat2013'", (uid,)).fetchone()
    return r[0] if r else None


print("1 · IPs sólo para ADMIN de la lista; al moderador no le llega nada privado")
cod, d = pedir(JEFA, "GET", "conectados")
ok(cod == 200 and "ip" not in d["filas"][0] and VISTO[-1]["admin"] == "1" and VISTO[-1]["quien"] == "coordinador:jefa",
   f"lista vacía: la ADMIN sin IP, firmada «coordinador:jefa» ({cod})")
ok(d["filas"][0].get("login") == "cuenta5" and "comparten_ip" not in d["filas"][0] and "misma_ip_total" not in d["filas"][0],
   "⟲ la ADMIN sin IP sigue viendo el login (sólo se ocultan las IP y lo que sale de ellas)")
os.environ["R2_VEN_IPS"] = str(JEFA)
cod, d = pedir(JEFA, "GET", "conectados")
ok(cod == 200 and all(d["filas"][0].get(k) == v for k, v in PRIVADOS.items()), "⟲ ADMIN listado sí recibe los privados")
os.environ["R2_VEN_IPS"] = str(MR2)
cod, d = pedir(MR2, "GET", "conectados")
txt = json.dumps(d)
ok(cod == 200 and d["filas"][0]["nick"] == "Jugador5" and d["filas"][0]["pais"] == "PE", f"el moderador de R2Beat mira ({cod})")
ok("192.0.2.5" not in txt and "cuenta5" not in txt and "misma_ip" not in txt and VISTO[-1]["admin"] == "0",
   "⟲ aunque esté en la lista no le llega ni una IP ni un login (tampoco anidados)")

print("1b · licencia: ruta, asignación y auditoría")
cod, d = pedir(JEFA, "POST", "usuario/5/licencia", {"licencia": "sol"})
ok(cod == 200 and d.get("antes") == "luna" and d.get("despues") == "sol"
   and VISTO[-1]["cuerpo"] == {"licencia": "sol"}, "ADMIN cambia Luna a Sol con el contrato del juego")
n = len(VISTO)
cod, _ = pedir(MR2, "POST", "usuario/5/licencia", {"licencia": "estrella"})
ok(cod == 403 and len(VISTO) == n, "⟲ moderador sin licencia: 403 y no viaja")
cod, d = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013", "acciones": ["licencia"]})
ok(cod == 200 and "licencia" in d["asignables_de"]["r2beat2013"]
   and any(x["id"] == "licencia" and x["nombre"] == "Cambiar la licencia" for x in d["asignables"]),
   "licencia asignable con su texto para el panel")
for licencia in ("ninguna", "estrella", "luna", "sol"):
    cod, d = pedir(MR2, "POST", "usuario/5/licencia", {"licencia": licencia})
    ok(cod == 200 and d.get("despues") == licencia, f"moderador con licencia: {licencia} pasa")
ok(P._propia().execute("SELECT COUNT(*) FROM auditoria WHERE accion = 'gestión · licencia'").fetchone()[0] == 5,
   "las cinco licencias cambiadas quedan en gestión · licencia")

# ★ 26-nov · la SEGURIDAD de R2Beat 2013 (lo de Hysteria): «seguridad» se asigna; los interruptores, SÓLO ADMIN
EV = "ab" * 16
n = len(VISTO)
cod, _ = pedir(MR2, "GET", "seguridad")
ok(cod == 403 and len(VISTO) == n, "⟲ seguridad sin el permiso: 403 y no viaja")
cod, d = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013", "acciones": ["licencia", "seguridad"]})
ok(cod == 200 and "seguridad" in d["asignables_de"]["r2beat2013"] and "seguridad" not in GE.ASIGNABLES_DE["contrato1"],
   "«seguridad» se asigna en R2Beat (no en GunBound, que no la tiene)")
for metodo, ruta in (("GET", "seguridad"), ("GET", "seguridad/eventos"), ("GET", "usuario/5/maquinas"),
                     ("POST", f"seguridad/evento/{EV}"), ("POST", "usuario/5/maquina/perdonar")):
    cod, _ = pedir(MR2, metodo, ruta, {} if metodo == "POST" else None)
    ok(cod == 200 and VISTO[-1]["ruta"].split("?")[0].endswith(ruta), f"moderador con seguridad: {metodo} {ruta} pasa")
n = len(VISTO)
cod, _ = pedir(MR2, "POST", "seguridad/ajustes", {"max_cuentas_maquina": 2})
ok(cod == 403 and len(VISTO) == n, "⟲ los interruptores: un moderador (aun con seguridad) 403 y no viaja")
cod, _ = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013", "acciones": ["seguridad/ajustes"]})
ok(cod == 400, f"⟲ «seguridad/ajustes» no se puede asignar: 400 ({cod})")
ok("seguridad/ajustes" in GE.permisos(P, JEFA, "r2beat2013")["acciones"]
   and "seguridad/ajustes" not in GE.permisos(P, MR2, "r2beat2013")["acciones"], "el ADMIN lo tiene; el moderador no")
cod, _ = pedir(JEFA, "POST", "seguridad/ajustes", {"max_cuentas_maquina": 2})
ok(cod == 200 and VISTO[-1]["ruta"].endswith("seguridad/ajustes") and VISTO[-1]["cuerpo"] == {"max_cuentas_maquina": 2},
   "el ADMIN cambia los interruptores (viaja tal cual)")
n = len(VISTO)
cod, _ = pedir(JEFA, "POST", "seguridad/evento/NO-ES-UN-ID", {})
ok(cod == 404 and len(VISTO) == n, "⟲ un id de evento con otra forma: 404 y no viaja")

# ★ 27-nov · los CUPONES DE ROPA: «cupones» se asigna; el pedido lo REARMA el Coordinador (una prenda, sin Rcoin)
print("1c · cupones de ropa")
GE._COLAB.update(ruta=os.path.join(tmp, "sin_colab.json"), fecha=None)   # ★ 27-nov: acá, SÓLO ropa (lo collab es la 1f)
posts = lambda: [v for v in VISTO if v["cuerpo"] is not None]                      # noqa: E731
n = len(VISTO)
cod, _ = pedir(MR2, "GET", "cupones")
ok(cod == 403 and len(VISTO) == n, "⟲ cupones sin el permiso: 403 y no viaja")
cod, _ = pedir(MR2, "POST", "cupones", {"item": 30220852, "dias": 0, "cantidad": 1, "usos": 1})
ok(cod == 403 and len(VISTO) == n, "⟲ generar sin el permiso: 403 y no viaja")
cod, d = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013", "acciones": ["licencia", "seguridad", "cupones"]})
ok(cod == 200 and "cupones" in d["asignables_de"]["r2beat2013"] and "cupones" not in GE.ASIGNABLES_DE["contrato1"],
   "«cupones» se asigna en R2Beat (no en GunBound)")
cod, _ = pedir(MR2, "GET", "cupones")
ok(cod == 200 and VISTO[-1]["ruta"].split("?")[0].endswith("/cupones"), "con el permiso: la lista pasa")
np_ = len(posts())
cod, _ = pedir(MR2, "POST", "cupones", {"item": 30220852, "dias": 0, "cantidad": 3, "usos": 2, "nota": "sorteo",
                                        "rcoin": 50000, "modo": "uno", "codigo": "GRATIS",
                                        "premios": [{"item": 1000200, "dias": 0, "cant": 999}]})
ok(cod == 200 and len(posts()) == np_ + 1 and posts()[-1]["ruta"].endswith("/cupones")
   and posts()[-1]["cuerpo"] == {"modo": "generar", "cantidad": 3, "usos": 2, "rcoin": 0, "nota": "sorteo",
                                 "premios": [{"item": 30220852, "dias": 0, "cant": 1}]},
   "el pedido viaja REARMADO: sin Rcoin, una prenda, modo generar (lo que mande el navegador no pasa)")
for nombre, cuerpo in (("una campana (no es ropa)", {"item": 1000200, "dias": 0, "cantidad": 1, "usos": 1}),
                       ("un ítem sin plazos", {"item": 777, "dias": 0, "cantidad": 1, "usos": 1}),
                       ("algo con plazo que NO es ropa (una pose)", {"item": 1000961, "dias": 7, "cantidad": 1, "usos": 1}),
                       ("un plazo que la tienda no tiene (365)", {"item": 30220852, "dias": 365, "cantidad": 1, "usos": 1}),
                       ("un ítem que no existe", {"item": 123456, "dias": 0, "cantidad": 1, "usos": 1}),
                       ("0 cupones", {"item": 30220852, "dias": 0, "cantidad": 0, "usos": 1}),
                       (f"{GE.CUPONES_MAX + 1} cupones", {"item": 30220852, "dias": 0, "cantidad": GE.CUPONES_MAX + 1, "usos": 1}),
                       ("0 usos", {"item": 30220852, "dias": 0, "cantidad": 1, "usos": 0}),
                       ("letras en vez de números", {"item": "abc", "dias": 0, "cantidad": 1, "usos": 1})):
    np_ = len(posts())
    cod, d = pedir(MR2, "POST", "cupones", cuerpo)
    ok(cod == 400 and len(posts()) == np_ and d.get("error"), f"⟲ {nombre}: 400 y no se genera ({cod})")
cod, _ = pedir(JEFA, "POST", "cupones", {"item": 30220852, "dias": 7, "cantidad": 1, "usos": 1, "rcoin": 9})
ok(cod == 200 and posts()[-1]["cuerpo"]["rcoin"] == 0 and posts()[-1]["cuerpo"]["premios"][0]["dias"] == 7,
   "un ADMIN también pasa por el rearmado (sin Rcoin; el plazo elegido, 7 días)")

# ★ 27-nov · las cuentas GM NPC: «gm_npc» se asigna; el pedido lo REARMA el Coordinador (sólo el NPC / sólo el usn)
print("1d · cuentas GM NPC")
n = len(VISTO)
cod, _ = pedir(MR2, "GET", "gmnpc")
ok(cod == 403 and len(VISTO) == n, "⟲ GM NPC sin el permiso: 403 y no viaja")
cod, _ = pedir(MR2, "POST", "gmnpc", {"npc": "king"})
ok(cod == 403 and len(VISTO) == n, "⟲ crear sin el permiso: 403 y no viaja")
cod, d = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013",
                                                  "acciones": ["licencia", "seguridad", "cupones", "gm_npc"]})
ok(cod == 200 and "gm_npc" in d["asignables_de"]["r2beat2013"] and "gm_npc" not in GE.ASIGNABLES_DE["contrato1"],
   "«gm_npc» se asigna en R2Beat (no en GunBound)")
cod, _ = pedir(MR2, "GET", "gmnpc")
ok(cod == 200 and VISTO[-1]["ruta"].split("?")[0].endswith("/gmnpc"), "con el permiso: la lista pasa")
np_ = len(posts())
cod, d = pedir(MR2, "POST", "gmnpc", {"npc": " King ", "usn": 5, "rcoin": 999999, "comandos": ["sanciones"]})
ok(cod == 200 and len(posts()) == np_ + 1 and posts()[-1]["ruta"].endswith("/gmnpc") and posts()[-1]["cuerpo"] == {"npc": "king"},
   "crear viaja REARMADO: sólo el NPC (lo demás que mande el navegador no pasa)")
ok(d.get("usuario") == "gmnpc_ab12cd34" and d.get("clave") == "Cl4ve-de-1-uso",
   "al moderador le llegan el usuario y la clave (la limpieza de privados no se los come)")
np_ = len(posts())
cod, _ = pedir(MR2, "POST", "gmnpc/cerrar", {"usn": 7, "npc": "king"})
ok(cod == 200 and len(posts()) == np_ + 1 and posts()[-1]["ruta"].endswith("/gmnpc/cerrar") and posts()[-1]["cuerpo"] == {"usn": 7},
   "cerrar viaja REARMADO: sólo el usn")
for ruta, nombre, cuerpo in (("gmnpc", "un NPC que no está en la lista", {"npc": "dragon"}),
                             ("gmnpc", "sin NPC", {}),
                             ("gmnpc/cerrar", "cerrar sin usn", {}),
                             ("gmnpc/cerrar", "cerrar con el usn en texto", {"usn": "7"}),
                             ("gmnpc/cerrar", "cerrar con un usn negativo", {"usn": -1}),
                             ("gmnpc/cerrar", "cerrar con true", {"usn": True})):
    np_ = len(posts())
    cod, d = pedir(MR2, "POST", ruta, cuerpo)
    ok(cod == 400 and len(posts()) == np_ and d.get("error"), f"⟲ {nombre}: 400 y no viaja ({cod})")
n = len(VISTO)
cod, _ = pedir(MR2, "POST", "gmnpc/otra", {"npc": "king"})
ok(cod == 404 and len(VISTO) == n, "⟲ una sub-ruta que no está en la lista cerrada: 404 y no viaja")

# ★ 27-nov · los cupones: quién los creó, el código TAPADO para los demás, quién los canjeó y CANCELAR (sólo los suyos)
print("1e · cupones: dueño, código tapado, canjes y cancelar")
R = {c["codigo"]: GE._cupon_ref(c["codigo"]) for c in CUPONES_JUEGO}
cod, d = pedir(MR2, "GET", "cupones")
L = {c["ref"]: c for c in d.get("cupones", [])}
mio, ajeno = L.get(R["MIOABCDEF12"], {}), L.get(R["AJENO9876543"], {})
ok(cod == 200 and mio.get("codigo") == "MIOABCDEF12" and mio.get("mio") and mio.get("ve_codigo"),
   "el moderador ve ENTERO el código de SU cupón")
ok(ajeno.get("codigo", "").startswith("AJE") and "•" in ajeno.get("codigo", "") and not ajeno.get("ve_codigo")
   and not ajeno.get("mio") and ajeno.get("nota") == "de ella" and ajeno.get("creador") == "coordinador:jefa",
   "el de OTRO lo ve tapado, con su creador y su nota")
ok("AJENO9876543" not in json.dumps(d), "⟲ el código ajeno no viaja en ninguna parte de la respuesta")
ok([L[R[k]]["estado"] for k in ("MIOABCDEF12", "USADOXYZ0001", "APAGADO00001", "VIEJO0000001")]
   == ["por_canjear", "usado", "cancelado", "cancelado"], "cada uno con su estado (por canjear · usado · cancelado/vencido)")
ok("q=" not in VISTO[-1]["ruta"], "⟲ el moderador no busca por pedazos del código (el `q` no viaja)")
cod, d = pedir(JEFA, "GET", "cupones")
ok(cod == 200 and {c["codigo"] for c in d["cupones"]} == set(R) and "q=" in VISTO[-1]["ruta"],
   "un ADMIN ve todos los códigos enteros (y puede buscar)")
n = len(VISTO)
cod, d = pedir(MR2, "GET", "cupones/canjes", query={"ref": R["AJENO9876543"]})
ok(cod == 200 and d.get("canjes") and "codigo=AJENO9876543" in VISTO[-1]["ruta"] and "AJENO9876543" not in json.dumps(d),
   "quién canjeó uno AJENO: por su ref (el Coordinador pide con el código; al moderador no le llega)")
for nombre, qq in (("una ref que no existe", {"ref": "0" * 16}), ("sin ref", {})):
    n = len(VISTO)
    cod, d = pedir(MR2, "GET", "cupones/canjes", query=qq)
    ok(cod == 404 and not any(v["ruta"].split("?")[0].endswith("/canjes") for v in VISTO[n:]), f"⟲ canjes con {nombre}: 404")
np_ = len(posts())
cod, _ = pedir(MR2, "POST", "cupones/cancelar", {"refs": [R["MIOABCDEF12"]], "accion": "cancelar"})
ok(cod == 200 and len(posts()) == np_ + 1 and posts()[-1]["ruta"].endswith("/cupones/cambiar")
   and posts()[-1]["cuerpo"] == {"codigos": ["MIOABCDEF12"], "accion": "apagar"},
   "cancelar el suyo: viaja como `apagar` (no se borra)")
cod, _ = pedir(MR2, "POST", "cupones/cancelar", {"refs": [R["APAGADO00001"]], "accion": "reactivar"})
ok(cod == 200 and posts()[-1]["cuerpo"] == {"codigos": ["APAGADO00001"], "accion": "prender"}, "reactivar uno suyo cancelado")
for nombre, cuerpo, esperado in (
        ("cancelar uno AJENO", {"refs": [R["AJENO9876543"]], "accion": "cancelar"}, 403),
        ("cancelar uno ya USADO", {"refs": [R["USADOXYZ0001"]], "accion": "cancelar"}, 400),
        ("cancelar uno ya cancelado", {"refs": [R["APAGADO00001"]], "accion": "cancelar"}, 400),
        ("reactivar uno VENCIDO", {"refs": [R["VIEJO0000001"]], "accion": "reactivar"}, 400),
        ("borrar (no existe la acción)", {"refs": [R["MIOABCDEF12"]], "accion": "borrar"}, 400),
        ("una ref mal formada", {"refs": ["MIOABCDEF12"], "accion": "cancelar"}, 400),
        ("una ref que no está", {"refs": ["f" * 16], "accion": "cancelar"}, 404)):
    np_ = len(posts())
    cod, d = pedir(MR2, "POST", "cupones/cancelar", cuerpo)
    ok(cod == esperado and len(posts()) == np_ and d.get("error"), f"⟲ {nombre}: {esperado} y no viaja ({cod})")
cod, _ = pedir(JEFA, "POST", "cupones/cancelar", {"refs": [R["AJENO9876543"], R["MIOABCDEF12"]], "accion": "cancelar"})
ok(cod == 200 and sorted(posts()[-1]["cuerpo"]["codigos"]) == ["AJENO9876543", "MIOABCDEF12"], "un ADMIN cancela cualquiera")
cod, _ = pedir(MGB, "POST", "cupones/cancelar", {"refs": [R["MIOABCDEF12"]], "accion": "cancelar"})
ok(cod in (403, 404), f"⟲ sin el permiso «cupones» en R2Beat, no cancela ({cod})")

# ★ 27-nov · los ítems COLLAB del Excel: además de la ropa, por SUS plazos; los de uso único, una unidad
print("1f · cupones de ítems collab")
_colab_tmp = os.path.join(tmp, "cupones_colab.json")
json.dump({"ids": [1000995, 30868, 1000200, 1000265]}, open(_colab_tmp, "w", encoding="utf-8"))   # (la campana, para el ⟲ de las cargas)
GE._COLAB.update(ruta=_colab_tmp, fecha=None)
ok(GE.colab_ids() == {1000995, 30868, 1000200, 1000265}, "la lista collab se lee del archivo")
cod, d = pedir(MR2, "GET", "catalogo", query={"q": "1000995"})
ok(cod == 200 and d["filas"] and d["filas"][0]["id"] == 1000995 and d["filas"][0]["colab"] is True, "el catálogo marca el collab")
cod, d = pedir(MR2, "GET", "catalogo", query={"q": "1000123"})
ok(cod == 200 and d["filas"][0]["colab"] is False, "⟲ una tarjeta que no es del Excel no sale marcada")
np_ = len(posts())
cod, _ = pedir(MR2, "POST", "cupones", {"item": 1000995, "dias": 30, "cantidad": 2, "usos": 1})
ok(cod == 200 and posts()[-1]["cuerpo"]["premios"] == [{"item": 1000995, "dias": 30, "cant": 1}],
   "una tarjeta collab, por 30 días (uno de SUS plazos)")
cod, _ = pedir(MR2, "POST", "cupones", {"item": 30868, "dias": 0, "cantidad": 1, "usos": 1})
ok(cod == 200 and posts()[-1]["cuerpo"]["premios"] == [{"item": 30868, "dias": 0, "cant": 1}],
   "un anillo collab de uso único: una unidad, no vence")
for nombre, cuerpo in (("la tarjeta collab por un plazo que no tiene (365)", {"item": 1000995, "dias": 365, "cantidad": 1, "usos": 1}),
                       ("el anillo por 30 días (sólo es de uso único)", {"item": 30868, "dias": 30, "cantidad": 1, "usos": 1}),
                       ("una tarjeta que NO es collab", {"item": 1000123, "dias": 30, "cantidad": 1, "usos": 1}),
                       ("la campana aunque esté en la lista (se gasta por cargas)", {"item": 1000200, "dias": 0, "cantidad": 1, "usos": 1}),
                       ("una pose collab de «1 día» (P1: se daría permanente)", {"item": 1000265, "dias": 0, "cantidad": 1, "usos": 1})):
    np_ = len(posts())
    cod, d = pedir(MR2, "POST", "cupones", cuerpo)
    ok(cod == 400 and len(posts()) == np_ and d.get("error"), f"⟲ {nombre}: 400 y no se genera ({cod})")
os.remove(_colab_tmp)
ok(GE.colab_ids() == frozenset(), "⟲ sin el archivo: ningún collab (sólo ropa, como antes)")
cod, d = pedir(MR2, "POST", "cupones", {"item": 1000995, "dias": 30, "cantidad": 1, "usos": 1})
ok(cod == 400, "⟲ sin la lista, la tarjeta vuelve a no poder darse")
GE._COLAB.update(ruta=os.path.join(os.path.dirname(GE.__file__), "cupones_colab.json"), fecha=None)
ok(len(GE.colab_ids()) > 100 and "servidor/cupones_colab.json" in open(
    os.path.join(os.path.dirname(os.path.dirname(GE.__file__)), "herramientas", "contenedores", "cuentas.Dockerfile"),
    encoding="utf-8").read(), "la lista de verdad está, y la imagen la copia (si no, en el aire no habría collab)")

print("2 · lo de BASE del moderador")
for ruta in ("aviso", "usuario/5/echar", "usuario/5/mute"):
    cod, _ = pedir(MR2, "POST", ruta, {"texto": "hola", "horas": 1})
    ok(cod == 200, f"{ruta}: 200 ({cod})")
n = len(VISTO)
cod, _ = pedir(MR2, "POST", "usuario/5/rcoin", {"modo": "sumar", "valor": 10})
ok(cod == 403 and len(VISTO) == n, f"⟲ dar Rcoin sin permiso: 403 y no viaja ({cod})")
cod, _ = pedir(MR2, "GET", "chat")
ok(cod == 403, f"⟲ leer el chat sin permiso: 403 ({cod})")

print("3 · lista cerrada")
for metodo, ruta in (("GET", "respaldo"), ("GET", "ip/190.7.7.7"), ("POST", "usuario/5/ban"), ("GET", "permisos"),
                     ("POST", "cuentas/fusionar"), ("GET", "usuario/5/../respaldo"), ("GET", "logs")):
    cod, _ = pedir(JEFA, metodo, ruta, {} if metodo == "POST" else None)
    ok(cod == 404, f"⟲ {metodo} {ruta}: 404 aunque sea ADMIN ({cod})")

print("4 · repartir permisos")
cod, _ = callado(GE.poner_permisos, CO, P, MR2, {"uid": MR2, "juego": "r2beat2013", "acciones": ["rcoin"], "cupo_rcoin": 10**6})
ok(cod == 403, f"⟲ un moderador no se da permisos: 403 ({cod})")
cod, _ = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MGB, "juego": "r2beat2013", "acciones": ["rcoin"]})
ok(cod == 409, f"⟲ a un moderador que no tiene R2Beat: 409 ({cod})")
cod, _ = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013", "acciones": ["ban"]})
ok(cod == 400, f"⟲ una acción que no es asignable (ban): 400 ({cod})")
cod, d = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013", "acciones": ["rcoin", "chat"],
                                                  "cupo_rcoin": 1000})
fila = next((x for x in d.get("permisos", []) if x["uid"] == MR2), {})
ok(cod == 200 and fila.get("acciones") == ["chat", "rcoin"] and fila.get("cupo_rcoin") == 1000,
   f"la ADMIN le da Rcoin (cupo 1.000) y chat ({cod})")
per = GE.permisos(P, MR2, "r2beat2013")
ok("rcoin" in per["acciones"] and "exp" not in per["acciones"] and per["cupos"]["rcoin"]["queda"] == 1000,
   "el moderador lo ve: rcoin sí, exp no, le quedan 1.000")
cod, _ = pedir(MR2, "GET", "chat")
ok(cod == 200, f"ahora sí lee el chat ({cod})")

print("5 · el cupo")
cod, d = pedir(MR2, "POST", "usuario/5/rcoin", {"modo": "sumar", "valor": 600})
ok(cod == 200 and dado(MR2) == 600 and d.get("cupos", {}).get("rcoin", {}).get("queda") == 400,
   f"+600: pasa, le quedan 400 ({cod}, dado {dado(MR2)})")
n = len(VISTO)
cod, d = pedir(MR2, "POST", "usuario/5/rcoin", {"modo": "sumar", "valor": 500})
ok(cod == 403 and dado(MR2) == 600 and len(VISTO) == n and "400" in d.get("error", ""),
   f"⟲ +500: pasa el cupo, 403 y no viaja ({d.get('error')})")
cod, _ = pedir(MR2, "POST", "usuario/5/rcoin", {"modo": "sumar", "valor": -300})
ok(cod == 200 and dado(MR2) == 600, f"⟲ restar 300 no gasta cupo ({cod}, dado {dado(MR2)})")
cod, _ = pedir(MR2, "POST", "usuario/5/rcoin", {"modo": "poner", "valor": 1})
ok(cod == 403 and dado(MR2) == 600, f"⟲ «poner» es de ADMIN: 403 ({cod})")
cod, _ = pedir(MR2, "POST", "usuario/5/rcoin", {"modo": "sumar", "valor": 333})
ok(cod == 400 and dado(MR2) == 600, f"⟲ +333 (entra en el cupo) que el juego rechaza: se devuelve (dado {dado(MR2)}) ({cod})")
cod, _ = pedir(MR2, "POST", "usuario/5/rcoin", {"modo": "sumar", "valor": 400})
ok(cod == 200 and dado(MR2) == 1000, f"+400 justo hasta el cupo ({cod}, dado {dado(MR2)})")
callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013", "acciones": ["rcoin"], "cupo_rcoin": 1000,
                                        "reiniciar_dado": True})
ok(dado(MR2) == 0, "la ADMIN reinicia lo dado")
res = []
# (sin `callado`: redirect_stdout es de TODO el proceso y, desde varios hilos, deja la consola apuntando a la nada)
hilos = [threading.Thread(target=lambda: res.append(GE.pedir(CO, P, MR2, "r2beat2013", "live", "POST", "usuario/5/rcoin",
                                                             cuerpo={"modo": "sumar", "valor": 600})[0]))
         for _ in range(4)]
for h in hilos:
    h.start()
for h in hilos:
    h.join()
ok(sorted(res) == [200, 403, 403, 403] and dado(MR2) == 600, f"⟲ cuatro +600 a la vez: pasa UNO ({sorted(res)}, dado {dado(MR2)})")
cod, _ = pedir(JEFA, "POST", "usuario/5/rcoin", {"modo": "poner", "valor": 5_000_000})
ok(cod == 200, f"la ADMIN pone lo que quiera, sin cupo ({cod})")

print("6 · otros moderadores")
cod, _ = pedir(MGB, "GET", "conectados")
ok(cod == 404, f"⟲ el moderador de GunBound en R2Beat: 404 ({cod})")
cod, _ = pedir(VIEJO, "GET", "conectados")
ok(cod == 403, f"⟲ el de formato viejo: 403 ({cod})")
cod, _ = pedir(JEFA, "GET", "conectados", entorno="test")
ok(cod == 404, f"⟲ R2Beat TEST sin fuente: 404 ({cod})")

print("7 · la auditoría")
filas = P._propia().execute("SELECT accion, juego FROM auditoria WHERE accion LIKE 'gestión ·%' OR accion LIKE 'equipo: permisos%'").fetchall()
acc = [f["accion"] for f in filas]
ok("gestión · aviso" in acc and "gestión · rcoin" in acc and "equipo: permisos del moderador" in acc
   and all(f["juego"] in ("r2beat2013", None) for f in filas if f["accion"].startswith("gestión")),
   f"avisos, Rcoin y permisos quedan anotados ({len(acc)})")
ok(not any(a == "gestión · ver" for a in acc), "⟲ mirar no se anota (sólo lo que cambia algo)")
cod, d = callado(CO.auditoria, P, MR2)
vio = {x["accion"] for x in d["auditoria"]}
ok(cod == 200 and "gestión · rcoin" in vio and "gestión · aviso" in vio,
   "el moderador de R2Beat ve en la auditoría lo hecho desde la gestión de SU juego")
cod, d = callado(CO.auditoria, P, MGB)
ok(cod == 200 and not any(x["accion"].startswith("gestión") for x in d["auditoria"]),
   "⟲ el de GunBound no ve lo de R2Beat")

print("8 · el contrato común (GunBound)")
os.environ["R2_PANEL_GESTION"] = f"r2beat2013={URL};gunbound=contrato1:{URL.replace('/api/interno/panel', '/interno/panel')}"
ok(GE.tipo_de(CO, P, "gunbound") == "contrato1" and GE.tipo_de(CO, P, "r2beat2013") == "r2beat", "cada juego con su tipo")
cod, _ = pedir(MGB, "GET", "capacidades", juego="gunbound")
ok(cod == 200 and VISTO[-1]["ruta"].startswith("/interno/panel/capacidades"), f"el moderador de GunBound mira sus capacidades ({cod})")
for metodo, ruta in (("GET", "usuario/5"), ("POST", "usuario/5/rcoin"), ("GET", "conectados/../x"), ("POST", "mute")):
    cod, _ = pedir(JEFA, metodo, ruta, {} if metodo == "POST" else None, juego="gunbound")
    ok(cod == 404, f"⟲ {metodo} {ruta} (del panel viejo) en GunBound: 404 ({cod})")
cod, _ = pedir(JEFA, "GET", "ficha/abc-12", juego="gunbound")
ok(cod == 200, f"una ficha con id de texto ({cod})")
cod, _ = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MGB, "juego": "gunbound", "acciones": ["rcoin"]})
ok(cod == 400, f"⟲ «rcoin» no es de GunBound: 400 ({cod})")
cod, d = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MGB, "juego": "gunbound", "acciones": ["moneda"],
                                                  "cupos_monedas": {"oro": 1000}})
fila = next((x for x in d.get("permisos", []) if x["uid"] == MGB), {})
ok(cod == 200 and fila.get("monedas") == {"oro": {"cupo": 1000, "dado": 0}}, f"la ADMIN le da monedas: oro con cupo 1.000 ({cod})")
n = len(VISTO)
cod, d = pedir(MGB, "POST", "moneda", {"id": "7", "moneda": "cash", "cantidad": 5}, juego="gunbound")
ok(cod == 403 and "cash" in d.get("error", "") and len(VISTO) == n, f"⟲ cash sin cupo asignado: 403 y no viaja ({d.get('error')})")
cod, d = pedir(MGB, "POST", "moneda", {"id": "7", "moneda": "oro", "cantidad": 700}, juego="gunbound")
ok(cod == 200 and d.get("cupos", {}).get("moneda:oro", {}).get("queda") == 300, f"+700 de oro: le quedan 300 ({cod})")
n = len(VISTO)
cod, d = pedir(MGB, "POST", "moneda", {"id": "7", "moneda": "oro", "cantidad": 301}, juego="gunbound")
ok(cod == 403 and len(VISTO) == n, f"⟲ +301 pasa el cupo de oro: 403 y no viaja ({d.get('error')})")
cod, _ = pedir(MGB, "POST", "moneda", {"id": "7", "moneda": "oro", "cantidad": 222}, juego="gunbound")
per = GE.permisos(P, MGB, "gunbound")
ok(cod == 400 and per["cupos"]["moneda:oro"]["dado"] == 700, f"⟲ +222 (entra) que el juego rechaza: se devuelve (dado {per['cupos']['moneda:oro']['dado']})")
cod, _ = pedir(MGB, "POST", "moneda", {"id": "7", "moneda": "oro", "cantidad": -50}, juego="gunbound")
ok(cod == 200 and GE.permisos(P, MGB, "gunbound")["cupos"]["moneda:oro"]["dado"] == 700, "⟲ restar no gasta cupo")
cod, d = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MGB, "juego": "gunbound", "acciones": ["moneda"],
                                                  "cupos_monedas": {"oro": 1000, "cash": 10}})
ok(GE.permisos(P, MGB, "gunbound")["cupos"]["moneda:oro"]["dado"] == 700, "⟲ agregar el cash no le borra lo dado de oro")
res = []
hilos = [threading.Thread(target=lambda: res.append(GE.pedir(CO, P, MGB, "gunbound", "live", "POST", "moneda",
                                                             cuerpo={"id": "7", "moneda": "oro", "cantidad": 200})[0]))
         for _ in range(4)]
for h in hilos:
    h.start()
for h in hilos:
    h.join()
ok(sorted(res) == [200, 403, 403, 403], f"⟲ cuatro +200 de oro a la vez con 300 libres: pasa UNO ({sorted(res)})")
cod, _ = pedir(MR2, "GET", "capacidades", juego="gunbound")
ok(cod == 404, f"⟲ el moderador de R2Beat en GunBound: 404 ({cod})")
cod, d = callado(GE.ver_permisos, CO, P, JEFA)
ok(d.get("asignables_de", {}).get("gunbound") == ["moneda"] and "rcoin" in d["asignables_de"]["r2beat2013"],
   "el panel sabe qué se asigna en cada juego")

print("9 · privacidad en TODAS las rutas de ambos tipos, también POST y errores")


def sin_ips(v):
    if isinstance(v, dict):
        return not any(GE._campo_privado(k, GE._SOLO_IPS) for k in v) and all(sin_ips(x) for x in v.values())
    return all(sin_ips(x) for x in v) if isinstance(v, list) else True


def sin_privados(v):
    if isinstance(v, dict):
        return not any(k in PRIVADOS for k in v) and all(sin_privados(x) for x in v.values())
    return all(sin_privados(x) for x in v) if isinstance(v, list) else True


for lista in (None, "", "inválido", str(MR2), f" {JEFA + 1}, 00{JEFA}, {MR2} "):
    if lista is None:
        os.environ.pop("R2_VEN_IPS", None)
    else:
        os.environ["R2_VEN_IPS"] = lista
    autorizado = lista is not None and f"00{JEFA}" in lista
    for jid, rutas in (("r2beat2013", GE.RUTAS), ("gunbound", GE.RUTAS_CONTRATO1)):
        for metodo, patron, _ in rutas:
            ruta = patron.replace(GE._N, "5").replace(GE._ID, "abc-12").replace(GE._EV, "ab" * 16)
            # (★ 27-nov: a «cupones» un `{}` se le rechaza antes de viajar —eso lo controla la sección 1c—: acá uno válido)
            vale = {("r2beat2013", "POST", "cupones/cancelar"): {"refs": [GE._cupon_ref("MIOABCDEF12")], "accion": "cancelar"},
                    ("r2beat2013", "POST", "cupones"): {"item": 30220852, "dias": 0, "cantidad": 1, "usos": 1},
                    ("r2beat2013", "POST", "gmnpc"): {"npc": "king"},                      # ★ 27-nov: ídem GM NPC
                    ("r2beat2013", "POST", "gmnpc/cerrar"): {"usn": 5}}.get((jid, metodo, ruta), {})
            qq = {"ref": GE._cupon_ref("MIOABCDEF12")} if (jid, ruta) == ("r2beat2013", "cupones/canjes") else None
            cod, d = pedir(JEFA, metodo, ruta, vale if metodo == "POST" else None, juego=jid, query=qq)
            ok(cod == 200 and (d["filas"][0].get("ip") == PRIVADOS["ip"] and len(d["campos"]) == 4 if autorizado
                              else sin_ips(d) and d["campos"] == [{"nombre": "Login", "valor": "cuenta5"},
                                                                    {"nombre": "País", "valor": "PE"}]
                              and d["detalle"] == [] and "192.0.2.5" not in json.dumps(d)
                              and d["filas"][0].get("login") == "cuenta5"),
               f"{jid} {metodo} {ruta}: {'con' if autorizado else 'sin'} privados (lista {lista!r})")
        ruta = "usuario/5/rcoin" if jid == "r2beat2013" else "moneda"
        cod, d = pedir(JEFA, "POST", ruta, {"valor": 333}, juego=jid)
        ok(cod == 400 and (d["filas"][0].get("ip") == PRIVADOS["ip"] if autorizado else sin_ips(d) and "192.0.2.5" not in json.dumps(d)),
           f"⟲ {jid}: el error del juego también respeta la lista")
    for viewer, jid in ((MR2, "r2beat2013"), (MGB, "gunbound")):
        cod, d = pedir(viewer, "GET", "conectados", juego=jid)
        ok(cod == 200 and sin_privados(d), f"⟲ {jid}: moderador siempre sin privados")

cod, _ = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MGB, "juego": "gunbound", "acciones": ["licencia"]})
ok(cod == 400, "⟲ licencia no se asigna a contrato1")

juego_srv.shutdown()
P.cerrar_conexiones()
print()
print(("✘ %d FALLAS" % len(fallos)) if fallos else "✔ todo bien")
sys.exit(1 if fallos else 0)
