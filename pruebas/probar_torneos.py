# -*- coding: utf-8 -*-
"""probar_torneos — los TORNEOS desde el panel del Coordinador (servidor/torneos.py), 20-nov-2026. El server del juego
es uno DE MENTIRA (habla como la puerta `/api/interno/torneos` de documentacion/TORNEOS.md del R2Beat 2013: la ficha,
GET todos, POST {accion, …}); el Coordinador y el portero son los de verdad.

Cada regla con su control al revés (⟲):
  1 · ver: la ADMIN y los moderadores de R2Beat ven ⟲ el de GunBound no (404) ⟲ una cuenta sin rol tampoco
      ⟲ a un moderador no le llega nada privado (el login que mandó el juego, ni el de quien cambió algo)
  2 · sin fuente / sin versión / caído: «todavía no tiene torneos» y no se rompe nada ⟲ un 404 CON su porqué
      («Ese torneo no existe.») NO se confunde con «sin versión»: llega tal cual
  3 · manejar: viaja con la ficha, X-R2 y «coordinador:<login>» ⟲ moderador sin «torneos»: 403 y no viaja nada
      ⟲ moderador de otro juego: 404 ⟲ el de formato viejo: 403
  4 · «torneos» es una acción ASIGNABLE de R2Beat: el ADMIN se la da y se la saca ⟲ en GunBound (contrato) no existe
  5 · la auditoría: cada cambio en la del Coordinador, y el moderador la ve en SUS juegos ⟲ lo que el juego rechazó
      no se anota ⟲ el moderador de GunBound no la ve
  6 · el porqué del juego llega tal cual (400, y el 409 de «reiniciar» con su `forzar`)
  7 · acción desconocida: 400 y no viaja ⟲ las diez del contrato sí viajan
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


# ── el server del juego, DE MENTIRA ────────────────────────────────────────────────────────────────
FICHA = "ficha-de-prueba"
TORNEOS = [{"id": 1, "nombre": "Copa de Navidad", "modo": "solo", "estado": "inscripcion", "cupo": 8,
            "horas": [{"t": 1798000000, "votos": 3}], "fecha": 1798000000, "info": "",
            "inscritos": [{"id": 11, "nombre": "Kairo", "login": "kairo_secreto", "semilla": None}],
            "cruces": [], "podio": {"primero": None, "segundo": None, "tercero": None},
            "quien": "coordinador:jefa", "cambiado": 1797000000}]
VISTO = []          # cada POST: {"cab": {...}, "cuerpo": {...}}


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

    def do_GET(self):
        if self.headers.get("X-Ficha-Interna") != FICHA:
            return self._mandar(404, {"error": "no existe"})
        return self._mandar(200, {"torneos": TORNEOS})

    def do_POST(self):
        if self.headers.get("X-Ficha-Interna") != FICHA or self.headers.get("X-R2") != "1":
            return self._mandar(404, {"error": "no existe"})
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        VISTO.append({"cab": {k: self.headers.get(k) for k in ("X-Ficha-Interna", "X-R2", "X-Coordinador-Quien")},
                      "cuerpo": d})
        if d.get("torneo") == 99:
            return self._mandar(404, {"error": "Ese torneo no existe."})
        if d.get("accion") == "resultado" and d.get("ganador") not in ("a", "b"):
            return self._mandar(400, {"error": "El ganador tiene que ser «a» o «b»."})
        if d.get("accion") == "reiniciar" and not d.get("forzar"):
            return self._mandar(409, {"error": "Ese cruce ya tiene resultados más adelante.", "forzar": True})
        return self._mandar(200, {"ok": True, "torneos": TORNEOS})


juego_srv = ThreadingHTTPServer(("127.0.0.1", 0), Juego)
threading.Thread(target=juego_srv.serve_forever, daemon=True).start()
URL_JUEGO = f"http://127.0.0.1:{juego_srv.server_address[1]}/api/interno/torneos"

# ── el portero y el Coordinador, de verdad ─────────────────────────────────────────────────────────
tmp = tempfile.mkdtemp(prefix="torneos_")
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
    # PROD con su fuente · TEST con una fuente CAÍDA · GunBound sin fuente de torneos
    "R2_PANEL_TORNEOS": f"r2beat2013={URL_JUEGO};r2beat2013-prueba=http://127.0.0.1:9/api/interno/torneos",
    # (la gestión sólo hace falta para saber el TIPO de cada juego al asignar permisos: nadie la llama acá)
    "R2_PANEL_GESTION": "r2beat2013=http://127.0.0.1:9/api/interno/panel;gunbound=contrato1:http://127.0.0.1:9/interno/panel",
})
for k in ("R2_PANEL_SALUD", "R2_PRESENCIA", "R2_DISCORD_EVENTOS_WEBHOOK", "R2_JUEGOS_CATALOGO", "R2_UID_NUEVAS_DESDE",
          "R2_PANEL_CONTENIDO"):
    os.environ.pop(k, None)

from servidor import portero as P          # noqa: E402
from servidor import coordinador as CO     # noqa: E402
from servidor import gestion as GE         # noqa: E402
from servidor import torneos as TO         # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    UID = {}
    for i, u in enumerate(["jefa", "modr2", "modr2b", "modgb", "modviejo", "jugadora"]):
        UID[u] = P.registrar(u, clave_txt=f"clave-{u}", ip=f"10.3.0.{i}")[1]["uid"]
open(os.environ["R2_ADMIN_ARCHIVO"], "w", encoding="utf-8").write(f"{UID['jefa']}\n")
open(os.environ["R2_MODERADOR_ARCHIVO"], "w", encoding="utf-8").write(
    f"{UID['modr2']} r2beat2013\n{UID['modr2b']} r2beat2013\n{UID['modgb']} gunbound\n{UID['modviejo']}\n")
JEFA, MR2, MR2B, MGB, VIEJO, J = (UID[k] for k in ("jefa", "modr2", "modr2b", "modgb", "modviejo", "jugadora"))


def callado(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return f(*a, **k)


def mandar(viewer, **d):
    return callado(TO.accion, CO, P, viewer, dict({"juego": "r2beat2013", "entorno": "live"}, **d))


def asignar(acciones):
    return callado(GE.poner_permisos, CO, P, JEFA, {"uid": MR2, "juego": "r2beat2013", "acciones": acciones})


cod, _ = asignar(["torneos"])
ok(cod == 200, f"(preparación) la ADMIN le asigna «torneos» a modr2 ({cod})")

print("1 · ver los torneos")
cod, d = callado(TO.leer, CO, P, JEFA, "r2beat2013", "live")
ok(cod == 200 and d["con_fuente"] and d["puede"] and d["es_admin"] and d["servidor"]["torneos"][0]["id"] == 1,
   f"la ADMIN ve los torneos de R2Beat PROD y puede manejarlos ({cod})")
ok(d["servidor"]["torneos"][0]["inscritos"][0].get("login") == "kairo_secreto"
   and d["servidor"]["torneos"][0]["quien"] == "coordinador:jefa", "a la ADMIN le llega todo (también el «quien» tal cual)")
cod, d = callado(TO.leer, CO, P, MR2, "r2beat2013", "live")
ok(cod == 200 and d["puede"] and d["servidor"]["torneos"][0]["inscritos"][0]["nombre"] == "Kairo",
   f"el moderador de R2Beat con «torneos» los ve y puede manejarlos ({cod})")
ok("login" not in d["servidor"]["torneos"][0]["inscritos"][0], "⟲ pero no le llega el login que mandó el juego")
ok(d["servidor"]["torneos"][0]["quien"] == "ADMIN" and "jefa" not in json.dumps(d),
   f"⟲ ni el login de quien cambió el torneo: «coordinador:jefa» le llega «{d['servidor']['torneos'][0]['quien']}»")
cod, d = callado(TO.leer, CO, P, MR2B, "r2beat2013", "live")
ok(cod == 200 and d["servidor"] and d["puede"] is False, f"el moderador de R2Beat SIN «torneos» sólo mira ({cod})")
cod, d = callado(TO.leer, CO, P, MGB, "r2beat2013", "live")
ok(cod == 404 and not d.get("servidor"), f"⟲ el moderador de GunBound NO ve los torneos de R2Beat ({cod})")
cod, d = callado(TO.leer, CO, P, J, "r2beat2013", "live")
ok(cod == 404, f"⟲ una cuenta sin rol: nada ({cod})")

print("2 · sin fuente, sin versión o caído")
cod, d = callado(TO.leer, CO, P, MGB, "gunbound", "live")
ok(cod == 200 and d["con_fuente"] is False and d["servidor"] is None and "todavía no tiene torneos" in d["sin_servidor"],
   f"GunBound sin fuente: «{d['sin_servidor']}»")
cod, d = callado(TO.leer, CO, P, JEFA, "r2beat2013", "test")
ok(cod == 200 and d["con_fuente"] and d["servidor"] is None and "no contesta" in d["sin_servidor"],
   f"R2Beat TEST con la fuente caída: «{d['sin_servidor']}»")
ficha_buena = os.environ["R2_CUENTAS_FICHA_INTERNA"]
os.environ["R2_CUENTAS_FICHA_INTERNA"] = "otra"
cod, d = callado(TO.leer, CO, P, JEFA, "r2beat2013", "live")
ok(cod == 200 and d["servidor"] is None and "versión" in (d["sin_servidor"] or ""),
   f"⟲ con otra ficha el juego contesta 404 «no existe» y se lee como «sin versión»: «{d['sin_servidor']}»")
os.environ["R2_CUENTAS_FICHA_INTERNA"] = ficha_buena
n = len(VISTO)
cod, d = callado(TO.accion, CO, P, MGB, {"juego": "gunbound", "entorno": "live", "accion": "crear", "nombre": "x"})
ok(cod in (403, 404) and len(VISTO) == n, f"⟲ manejar GunBound (sin fuente, y él sin «torneos»): {cod} y nada viaja")
cod, d = callado(TO.accion, CO, P, JEFA, {"juego": "gunbound", "entorno": "live", "accion": "crear", "nombre": "x"})
ok(cod == 404 and "todavía no tiene torneos" in d.get("error", "") and len(VISTO) == n,
   f"la ADMIN en GunBound: 404 «{d.get('error')}»")
cod, d = mandar(JEFA, entorno="test", accion="crear", nombre="x")
ok(cod == 503 and "no contesta" in d.get("error", ""), f"R2Beat TEST caído: 503 «{d.get('error')}»")
cod, d = mandar(JEFA, accion="estado", torneo=99, estado="votando")
ok(cod == 404 and d.get("error") == "Ese torneo no existe.",
   f"⟲ un 404 CON su porqué no se confunde con «sin versión»: llega tal cual («{d.get('error')}»)")

print("3 · manejar: quién y cómo viaja")
VISTO.clear()
nuevo = {"accion": "crear", "nombre": "Copa Año Nuevo", "modo": "pareja", "cupo": 16, "horas": [1798100000, 1798200000],
         "info": "Canciones de nivel 6 a 8"}
cod, d = mandar(JEFA, **nuevo)
v = VISTO[-1] if VISTO else {"cab": {}, "cuerpo": {}}
ok(cod == 200 and d.get("ok") and v["cuerpo"] == nuevo, f"la ADMIN crea un torneo: llega al juego tal cual ({cod})")
ok(v["cab"] == {"X-Ficha-Interna": FICHA, "X-R2": "1", "X-Coordinador-Quien": "coordinador:jefa"},
   f"con la ficha, X-R2 y «coordinador:jefa» ({v['cab']})")
cod, d = mandar(JEFA, accion="editar", torneo=1, nombre="x", quien="coordinador:otro", juego_extra=1)
ok(cod == 200 and "quien" not in VISTO[-1]["cuerpo"] and VISTO[-1]["cab"]["X-Coordinador-Quien"] == "coordinador:jefa",
   "⟲ un «quien» metido en el pedido NO viaja: el autor lo pone el Coordinador")
cod, d = mandar(MR2, accion="estado", torneo=1, estado="en_curso")
ok(cod == 200 and VISTO[-1]["cab"]["X-Coordinador-Quien"] == "coordinador:modr2",
   f"el moderador con «torneos» cierra la inscripción, a su nombre ({cod})")
n = len(VISTO)
cod, d = mandar(MR2B, accion="estado", torneo=1, estado="cancelado")
ok(cod == 403 and len(VISTO) == n and "ADMIN" in d.get("error", ""),
   f"⟲ el moderador SIN «torneos»: 403 y no viaja nada («{d.get('error')}»)")
cod, d = mandar(MGB, accion="estado", torneo=1, estado="cancelado")
ok(cod == 404 and len(VISTO) == n, f"⟲ el moderador de GunBound en R2Beat: 404 ({cod})")
cod, d = mandar(VIEJO, accion="estado", torneo=1, estado="cancelado")
ok(cod == 403 and len(VISTO) == n, f"⟲ el moderador de formato viejo sólo mira: 403 ({cod})")
cod, d = mandar(J, accion="estado", torneo=1, estado="cancelado")
ok(cod == 404 and len(VISTO) == n, f"⟲ una cuenta sin rol: 404 ({cod})")
cod, d = mandar(JEFA, entorno="extra", accion="estado", torneo=1, estado="cancelado")
ok(cod == 404 and len(VISTO) == n, f"⟲ un entorno que no existe: 404 y no viaja ({cod})")

print("4 · «torneos» es una acción asignable de R2Beat")
cod, d = asignar([])
ok(cod == 200 and "torneos" in d["asignables_de"]["r2beat2013"] and any(a["id"] == "torneos" for a in d["asignables"]),
   "la lista de asignables de R2Beat la trae (con su nombre para el panel)")
cod, _ = mandar(MR2, accion="jugando", torneo=1, ronda=0, idx=0, si=True)
ok(cod == 403, f"⟲ la ADMIN se la sacó: modr2 ya no maneja torneos ({cod})")
cod, _ = callado(TO.leer, CO, P, MR2, "r2beat2013", "live")
ok(cod == 200 and _["puede"] is False, "⟲ y la pestaña le queda de sólo lectura")
cod, _ = asignar(["torneos", "rcoin"])
cod2, _ = mandar(MR2, accion="jugando", torneo=1, ronda=0, idx=0, si=True)
ok(cod == 200 and cod2 == 200, f"se la vuelve a dar: puede otra vez ({cod}, {cod2})")
ok("torneos" not in GE.ASIGNABLES_DE["contrato1"], "⟲ los juegos del contrato común no la tienen")
cod, d = callado(GE.poner_permisos, CO, P, JEFA, {"uid": MGB, "juego": "gunbound", "acciones": ["torneos"]})
ok(cod == 400, f"⟲ asignar «torneos» en GunBound: 400 ({cod}: {d.get('error')})")

print("5 · la auditoría")
filas = P._propia().execute("SELECT accion, juego, detalle, quien FROM auditoria WHERE accion LIKE 'torneos · %' "
                            "ORDER BY id").fetchall()
acc = [f["accion"] for f in filas]
ok(acc[:4] == ["torneos · crear", "torneos · editar", "torneos · estado", "torneos · jugando"]
   and all(f["juego"] == "r2beat2013" for f in filas),
   f"cada cambio que el juego aceptó, en la del Coordinador ({acc})")
ok(filas[2]["detalle"] == "torneo 1 · → en_curso" and filas[0]["detalle"] == "Copa Año Nuevo",
   f"con lo justo para entenderlo («{filas[2]['detalle']}», «{filas[0]['detalle']}»)")
antes = P._propia().execute("SELECT COUNT(*) FROM auditoria").fetchone()[0]
mandar(JEFA, accion="resultado", torneo=1, ronda=0, idx=0, ganador="c")
mandar(JEFA, accion="reiniciar", torneo=1, ronda=0, idx=0)
ok(P._propia().execute("SELECT COUNT(*) FROM auditoria").fetchone()[0] == antes,
   "⟲ lo que el juego rechazó (400, 409) NO se anota")
cod, d = callado(CO.auditoria, P, MR2)
ok(cod == 200 and any(a["accion"].startswith("torneos · ") for a in d["auditoria"]),
   "el moderador de R2Beat ve en «La red» lo que se hizo con los torneos de su juego")
cod, d = callado(CO.auditoria, P, MGB)
ok(cod == 200 and not any(a["accion"].startswith("torneos · ") for a in d["auditoria"]),
   "⟲ el de GunBound no ve los de R2Beat")

print("6 · el porqué del juego llega tal cual")
cod, d = mandar(JEFA, accion="resultado", torneo=1, ronda=0, idx=0, ganador="c")
ok(cod == 400 and d.get("error") == "El ganador tiene que ser «a» o «b».", f"400 con su porqué («{d.get('error')}»)")
cod, d = mandar(JEFA, accion="reiniciar", torneo=1, ronda=0, idx=0)
ok(cod == 409 and d.get("forzar") is True, f"409 con su `forzar` (el panel pregunta y reenvía) ({cod})")
cod, d = mandar(JEFA, accion="reiniciar", torneo=1, ronda=0, idx=0, forzar=True)
ok(cod == 200 and VISTO[-1]["cuerpo"].get("forzar") is True, f"⟲ con forzar el juego lo hace ({cod})")

print("7 · las acciones")
n = len(VISTO)
for mala in ("borrar_todo", "", None, "CREAR"):
    cod, d = mandar(JEFA, accion=mala, torneo=1)
    ok(cod == 400 and len(VISTO) == n, f"⟲ accion {mala!r}: 400 y no viaja ({cod})")
for a in TO.ACCIONES:
    mandar(JEFA, accion=a, torneo=1, ronda=0, idx=0, ganador="a", forzar=True)
ok([v["cuerpo"]["accion"] for v in VISTO[n:]] == list(TO.ACCIONES), f"las {len(TO.ACCIONES)} del contrato viajan")

juego_srv.shutdown()
P.cerrar_conexiones()
print()
print(("✘ %d FALLAS" % len(fallos)) if fallos else "✔ todo bien")
sys.exit(1 if fallos else 0)
