# -*- coding: utf-8 -*-
"""probar_gestion — la FASE C del panel del Coordinador (servidor/gestion.py), 20-nov-2026: la gestión de cada juego,
con permisos asignables por acción y CUPOS por moderador y juego (Benja: «con cupo y permisos asignables para X
acción también»). El panel del juego es uno DE MENTIRA (habla como `/api/interno/panel/…` de R2Beat y devuelve IPs y
logins a propósito); el Coordinador y el portero son los de verdad.

Cada regla con su control al revés (⟲):
  1 · la ADMIN ve todo, con IPs; ⟲ al moderador NUNCA le llega una IP ni un login
  2 · BASE del moderador: mirar, avisar, echar ⟲ dar Rcoin sin permiso: 403 y no viaja nada
  3 · ⟲ lista cerrada: respaldo, ip/…, ban… dan 404 aunque sea ADMIN
  4 · repartir permisos: sólo ADMIN ⟲ un juego no asignado: 409 ⟲ una acción inventada: 400
  5 · el CUPO: se gasta al sumar ⟲ pasarse: 403 y no viaja ⟲ restar no gasta ⟲ «poner» no (es de ADMIN)
      ⟲ si el juego dice que no, se devuelve ⟲ dos a la vez no pasan el cupo
  6 · ⟲ el moderador de otro juego: 404 · ⟲ el de formato viejo: 403
  7 · cada acción queda en la auditoría del Coordinador
"""
import contextlib
import io
import json
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
        return self._mandar(200, {"filas": [{"uid": 5, "nick": "Jugador5", "ip": "190.7.7.7", "login": "cuenta5",
                                             "misma_ip": 2, "pais": "PE", "datos": {"ips": ["190.7.7.7"]}}],
                                  "total": 1})

    def do_POST(self):
        if self.headers.get("X-Ficha-Interna") != FICHA or self.headers.get("X-R2") != "1":
            return self._mandar(404, {"error": "no existe"})
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        self._anotar(d)
        if d.get("valor") == 333:
            return self._mandar(400, {"error": "ese uid no tiene personaje"})
        return self._mandar(200, {"ok": True})


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


def pedir(viewer, metodo, ruta, cuerpo=None, entorno="live", juego="r2beat2013"):
    return callado(GE.pedir, CO, P, viewer, juego, entorno, metodo, ruta, query={"q": "x"} if metodo == "GET" else None,
                   cuerpo=cuerpo)


def dado(uid, k="rcoin"):
    r = P._propia().execute(f"SELECT dado_{k} FROM permisos_juego WHERE uid = ? AND juego = 'r2beat2013'", (uid,)).fetchone()
    return r[0] if r else None


print("1 · la ADMIN ve todo; al moderador no le llega nada privado")
cod, d = pedir(JEFA, "GET", "conectados")
ok(cod == 200 and d["filas"][0]["ip"] == "190.7.7.7" and VISTO[-1]["admin"] == "1" and VISTO[-1]["quien"] == "coordinador:jefa",
   f"la ADMIN: con IP, firmada «coordinador:jefa» ({cod})")
cod, d = pedir(MR2, "GET", "conectados")
txt = json.dumps(d)
ok(cod == 200 and d["filas"][0]["nick"] == "Jugador5" and d["filas"][0]["pais"] == "PE", f"el moderador de R2Beat mira ({cod})")
ok("190.7.7.7" not in txt and "cuenta5" not in txt and "misma_ip" not in txt and VISTO[-1]["admin"] == "0",
   "⟲ y no le llega ni una IP ni un login (tampoco anidados)")

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

juego_srv.shutdown()
P.cerrar_conexiones()
print()
print(("✘ %d FALLAS" % len(fallos)) if fallos else "✔ todo bien")
sys.exit(1 if fallos else 0)
