# -*- coding: utf-8 -*-
"""probar_contenido — la FASE B del panel del Coordinador (servidor/contenido.py), 20-nov-2026: NOVEDADES y el
CONTENIDO DINÁMICO de cada juego. El server del juego es uno DE MENTIRA (habla como `contenido_interno.py` de R2Beat:
la ficha, GET/POST, /previa, /items); el Coordinador y el portero son los de verdad.

Cada regla con su control al revés (⟲):
  1 · leer: la ADMIN y el moderador de GunBound ven; ⟲ el moderador no ve un juego que no es suyo
  2 · sin fuente / sin versión / caído: «todavía no tiene contenido dinámico» y no se rompe nada
  3 · guardar en el juego: viaja con la ficha y «coordinador:<login>»; ⟲ el moderador de formato viejo sólo mira
  4 · novedades: el moderador sólo toca las de SU juego ⟲ manda una de EDA o una general: 403 y no se toca nada
      ⟲ intenta «borrar» las de otros juegos mandando su lista sola: las de otros quedan
  5 · novedades: dos editando a la vez ⟲ la base vieja da 409 y no pisa
  6 · lanzamiento: sólo ADMIN; escribe config/lanzamientos.json y el portero lo lee ⟲ moderador 403 ⟲ fecha mala 400
  7 · el error del server del juego llega tal cual (400 con su porqué)
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import time
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
JUEGO = {"noticias": [
    {"titulo": "Ropa de Halloween", "etiqueta": "ropa", "juego": "r2beat", "fecha": "2026-10-25", "activo": True},
    {"titulo": "Parche GB 1.0", "etiqueta": "parche", "juego": "gunbound", "fecha": "2026-11-19", "activo": True},
    {"titulo": "Parche EDA", "etiqueta": "parche", "juego": "eda", "fecha": "2026-11-18", "activo": True},
    {"titulo": "Mantenimiento", "etiqueta": "mantenimiento", "juego": "general", "fecha": "2026-11-17", "activo": True},
], "asistencia": {"base": {"premios": [{"rcoin": 2000}]}}, "ruleta": {"casillas": []}, "tira": []}
VISTO = {"posts": []}


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

    def _todo(self):
        return dict(JUEGO, version=1, etiquetas=["parche", "ropa", "mantenimiento"], etiquetas_general=["mantenimiento"],
                    cambiado={}, asistencia_mes={"dias": []}, ruleta_resumen={}, ruleta_mayor_total=60,
                    tira_texto_max=120, tira_total_max=900)

    def do_GET(self):
        if self.headers.get("X-Ficha-Interna") != FICHA:
            return self._mandar(404, {"error": "no existe"})
        if self.path.startswith("/api/interno/contenido/items"):
            return self._mandar(200, {"items": [{"item": 297, "nombre": "Campana de plata"}]})
        return self._mandar(200, self._todo())

    def do_POST(self):
        if self.headers.get("X-Ficha-Interna") != FICHA or self.headers.get("X-R2") != "1":
            return self._mandar(404, {"error": "no existe"})
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        VISTO["posts"].append(d)
        if self.path.endswith("/previa"):
            return self._mandar(200, {"ok": True, "valor": d.get("valor")})
        if d.get("clave") == "noticias" and any(n.get("juego") not in ("r2beat", "eda", "gunbound", "general", "love")
                                                for n in d.get("valor") or []):
            return self._mandar(400, {"error": "noticia: juego desconocido"})
        if d.get("clave") == "tira" and not isinstance(d.get("valor"), list):
            return self._mandar(400, {"error": "filas: una lista (hasta 50)"})
        JUEGO[d["clave"]] = d["valor"]
        return self._mandar(200, dict(self._todo(), ok=True))


juego_srv = ThreadingHTTPServer(("127.0.0.1", 0), Juego)
threading.Thread(target=juego_srv.serve_forever, daemon=True).start()
URL_JUEGO = f"http://127.0.0.1:{juego_srv.server_address[1]}/api/interno/contenido"

# ── el portero y el Coordinador, de verdad ─────────────────────────────────────────────────────────
tmp = tempfile.mkdtemp(prefix="contenido_")
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
    "R2_PANEL_CONTENIDO": f"r2beat2013={URL_JUEGO};gunbound-prueba=http://127.0.0.1:9/api/interno/contenido",
})
for k in ("R2_PANEL_SALUD", "R2_PRESENCIA", "R2_DISCORD_EVENTOS_WEBHOOK", "R2_JUEGOS_CATALOGO", "R2_UID_NUEVAS_DESDE",
          "R2_NOVEDADES_FUENTE"):
    os.environ.pop(k, None)

from servidor import portero as P          # noqa: E402
from servidor import coordinador as CO     # noqa: E402
from servidor import contenido as CT       # noqa: E402
from servidor import lanzamientos as LZ    # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    UID = {}
    for i, u in enumerate(["jefa", "modgb", "modviejo", "jugadora"]):
        UID[u] = P.registrar(u, clave_txt=f"clave-{u}", ip=f"10.2.0.{i}")[1]["uid"]
open(os.environ["R2_ADMIN_ARCHIVO"], "w", encoding="utf-8").write(f"{UID['jefa']}\n")
open(os.environ["R2_MODERADOR_ARCHIVO"], "w", encoding="utf-8").write(f"{UID['modgb']} gunbound\n{UID['modviejo']}\n")
JEFA, MOD, VIEJO, J = (UID[k] for k in ("jefa", "modgb", "modviejo", "jugadora"))
AHORA = time.time()


def callado(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return f(*a, **k)


print("1 · leer el contenido de un juego")
cod, d = callado(CT.leer, CO, P, JEFA, "r2beat2013", "live", AHORA)
ok(cod == 200 and d["servidor"] and d["servidor"]["asistencia"]["base"]["premios"] == [{"rcoin": 2000}]
   and d["puede_editar"] and d["es_admin"], f"la ADMIN ve R2Beat PROD con su asistencia ({cod})")
cod, d = callado(CT.leer, CO, P, MOD, "gunbound", "live", AHORA)
ok(cod == 200 and d["puede_editar"] and d["lanzamiento"] and d["lanzamiento"]["etiqueta"] == "BETA",
   f"el moderador de GunBound ve SU juego, con su lanzamiento ({cod})")
cod, d = callado(CT.leer, CO, P, MOD, "r2beat2013", "live", AHORA)
ok(cod == 404, f"⟲ el moderador de GunBound NO ve R2Beat ({cod})")
cod, d = callado(CT.leer, CO, P, J, "r2beat2013", "live", AHORA)
ok(cod == 404, f"⟲ una jugadora sin rol: nada ({cod})")

print("2 · sin fuente, sin versión o caído")
cod, d = callado(CT.leer, CO, P, MOD, "gunbound", "live", AHORA)
ok(cod == 200 and d["servidor"] is None and "todavía no tiene" in (d["sin_servidor"] or ""),
   f"GunBound PROD sin fuente: «{d['sin_servidor']}»")
cod, d = callado(CT.leer, CO, P, MOD, "gunbound", "test", AHORA)
ok(cod == 200 and d["servidor"] is None and "no contesta" in (d["sin_servidor"] or ""),
   f"GunBound TEST con fuente caída: «{d['sin_servidor']}»")
ficha_buena = os.environ["R2_CUENTAS_FICHA_INTERNA"]
os.environ["R2_CUENTAS_FICHA_INTERNA"] = "otra"
cod, d = callado(CT.leer, CO, P, JEFA, "r2beat2013", "live", AHORA)
ok(cod == 200 and d["servidor"] is None and "versión" in (d["sin_servidor"] or ""),
   f"⟲ con otra ficha el juego contesta 404 y se lee como «sin versión»: «{d['sin_servidor']}»")
os.environ["R2_CUENTAS_FICHA_INTERNA"] = ficha_buena

print("3 · guardar en el juego")
VISTO["posts"].clear()
fila = [{"texto": "Evento esta noche", "siempre": True}]
cod, d = callado(CT.guardar, CO, P, JEFA, {"juego": "r2beat2013", "entorno": "live", "clave": "tira", "valor": fila}, AHORA)
ok(cod == 200 and JUEGO["tira"] == fila and VISTO["posts"][-1]["quien"] == "coordinador:jefa",
   f"la tira llega al juego a nombre de «coordinador:jefa» ({cod})")
aud = P._propia().execute("SELECT accion, juego FROM auditoria ORDER BY id DESC LIMIT 1").fetchone()
ok(aud and aud["accion"] == "contenido · tira" and aud["juego"] == "r2beat2013", "y queda en la auditoría del Coordinador")
n = len(VISTO["posts"])
cod, d = callado(CT.guardar, CO, P, VIEJO, {"juego": "r2beat2013", "entorno": "live", "clave": "tira", "valor": []}, AHORA)
ok(cod == 403 and len(VISTO["posts"]) == n, f"⟲ el moderador de formato viejo sólo mira: 403 y nada viaja ({cod})")
cod, d = callado(CT.guardar, CO, P, MOD, {"juego": "r2beat2013", "entorno": "live", "clave": "tira", "valor": []}, AHORA)
ok(cod == 404 and len(VISTO["posts"]) == n, f"⟲ el moderador de GunBound en R2Beat: 404 ({cod})")
cod, d = callado(CT.guardar, CO, P, JEFA, {"juego": "r2beat2013", "entorno": "live", "clave": "noticias", "valor": []}, AHORA)
ok(cod == 400 and len(VISTO["posts"]) == n, f"⟲ las noticias NO se guardan por acá (van por Novedades): 400 ({cod})")
cod, d = callado(CT.guardar, CO, P, MOD, {"juego": "gunbound", "entorno": "live", "clave": "ruleta", "valor": {}}, AHORA)
ok(cod == 503, f"⟲ GunBound sin fuente: 503 con el porqué ({cod}: {d.get('error')})")

print("4 · novedades: cada uno lo suyo")
cod, d = callado(CT.leer_novedades, CO, P, MOD)
mias = [x for x in d["noticias"] if x["editable"]]
ok(cod == 200 and [x["titulo"] for x in mias] == ["Parche GB 1.0"] and len(d["noticias"]) == 4,
   f"el moderador ve las 4, y sólo la de GunBound es editable ({[x['titulo'] for x in mias]})")
ok({j["id"]: j["editable"] for j in d["juegos"]}.get("general") is False, "⟲ y «General» no es editable para él")
base = d["base"]
nueva = [{"titulo": "Parche GB 1.1", "etiqueta": "parche", "juego": "gunbound", "fecha": "2026-11-20", "activo": True}]
cod, d2 = callado(CT.guardar_novedades, CO, P, MOD, {"noticias": nueva, "base": base})
titulos = sorted(n["titulo"] for n in JUEGO["noticias"])
ok(cod == 200 and titulos == ["Mantenimiento", "Parche EDA", "Parche GB 1.1", "Ropa de Halloween"],
   f"cambia la suya; las de R2Beat, EDA y la general QUEDAN aunque mandó sólo la suya ({titulos})")
ok(VISTO["posts"][-1]["quien"] == "coordinador:modgb", "a su nombre")
antes = json.dumps(JUEGO["noticias"], sort_keys=True)
cod, _ = callado(CT.guardar_novedades, CO, P, MOD, {"noticias": nueva + [{"titulo": "x", "juego": "eda"}], "base": d2["base"]})
ok(cod == 403 and json.dumps(JUEGO["noticias"], sort_keys=True) == antes, f"⟲ mete una de EDA: 403 y nada cambia ({cod})")
cod, _ = callado(CT.guardar_novedades, CO, P, MOD,
                 {"noticias": [{"titulo": "Caído", "etiqueta": "mantenimiento", "juego": "general"}], "base": d2["base"]})
ok(cod == 403 and json.dumps(JUEGO["noticias"], sort_keys=True) == antes, f"⟲ una GENERAL: 403 ({cod})")
cod, _ = callado(CT.guardar_novedades, CO, P, VIEJO, {"noticias": [], "base": d2["base"]})
ok(cod == 403, f"⟲ el moderador de formato viejo no edita novedades ({cod})")
cod, d3 = callado(CT.leer_novedades, CO, P, JEFA)
ok(all(x["editable"] for x in d3["noticias"]), "la ADMIN puede todas")
cod, _ = callado(CT.guardar_novedades, CO, P, JEFA, {"noticias": [{"titulo": "x", "juego": "tetris"}], "base": d3["base"]})
ok(cod == 403, f"⟲ un juego que no está en el catálogo (tetris): 403 ({cod})")

print("5 · dos editando a la vez")
cod, d4 = callado(CT.leer_novedades, CO, P, JEFA)
vieja = d4["base"]
lista = [{k: v for k, v in x.items() if k != "editable"} for x in d4["noticias"]]
cod, _ = callado(CT.guardar_novedades, CO, P, JEFA, {"noticias": lista[:-1], "base": vieja})
ok(cod == 200 and len(JUEGO["noticias"]) == 3, f"la primera guarda (quita una) ({cod})")
antes = json.dumps(JUEGO["noticias"], sort_keys=True)
cod, d5 = callado(CT.guardar_novedades, CO, P, MOD, {"noticias": nueva, "base": vieja})
ok(cod == 409 and json.dumps(JUEGO["noticias"], sort_keys=True) == antes,
   f"⟲ la segunda, con la base VIEJA: 409 y no pisa ({cod}: {d5.get('error', '')[:50]})")

print("6 · el lanzamiento")
from datetime import datetime  # noqa: E402
EL_29 = int(datetime.fromisoformat("2026-11-29T20:30:00-05:00").timestamp())   # (derivado, no escrito a mano)
cod, d = callado(CT.guardar, CO, P, JEFA, {"juego": "gunbound", "clave": "lanzamiento",
                                           "valor": {"desde_peru": "2026-11-29T20:30", "etiqueta": "beta"}}, AHORA)
ok(cod == 200 and d["lanzamiento"]["desde_peru"] == "2026-11-29T20:30", f"la ADMIN mueve GunBound al 29, 20:30 ({cod})")
ok(LZ.tabla(P)["gunbound"]["desde_t"] == EL_29 and LZ.tabla(P)["gunbound"]["pases"] == ["gunbound", "gunbound-prueba"],
   "el portero lo lee (con sus pases de siempre)")
ok(LZ.tabla(P)["eda"]["desde"] == LZ.LANZAMIENTOS["eda"]["desde"], "⟲ EDA no se tocó")
cod, _ = callado(CT.guardar, CO, P, MOD, {"juego": "gunbound", "clave": "lanzamiento",
                                          "valor": {"desde_peru": "2026-11-20T00:00"}}, AHORA)
ok(cod == 403 and LZ.tabla(P)["gunbound"]["desde_t"] == EL_29, f"⟲ el moderador no mueve la fecha: 403 ({cod})")
for mala in ("mañana", "2026-13-01T10:00", ""):
    cod, _ = callado(CT.guardar, CO, P, JEFA, {"juego": "gunbound", "clave": "lanzamiento", "valor": {"desde_peru": mala}}, AHORA)
    ok(cod == 400, f"⟲ fecha {mala!r}: 400 ({cod})")
cod, _ = callado(CT.guardar, CO, P, JEFA, {"juego": "gunbound", "clave": "lanzamiento",
                                           "valor": {"desde_peru": "2026-11-29T20:30", "etiqueta": "GOLD"}}, AHORA)
ok(cod == 400, f"⟲ etiqueta GOLD: 400 ({cod})")
cod, _ = callado(CT.guardar, CO, P, JEFA, {"juego": "r2beat2013", "clave": "lanzamiento",
                                           "valor": {"desde_peru": "2026-11-29T20:30"}}, AHORA)
ok(cod == 404, f"⟲ R2Beat no tiene lanzamiento: 404 ({cod})")

print("7 · el porqué del juego llega tal cual")
cod, d = callado(CT.guardar, CO, P, JEFA, {"juego": "r2beat2013", "entorno": "live", "clave": "tira", "valor": "x"}, AHORA)
ok(cod == 400 and "lista" in d.get("error", ""), f"400 con el porqué del juego ({d.get('error')})")
cod, d = callado(CT.items, CO, P, JEFA, "r2beat2013", "live", "plata")
ok(cod == 200 and d["items"][0]["item"] == 297, "buscar ítems pasa por el Coordinador")
cod, d = callado(CT.previa, CO, P, JEFA, {"juego": "r2beat2013", "entorno": "live", "clave": "asistencia", "valor": {"a": 1}})
ok(cod == 200 and VISTO["posts"][-1].get("clave") == "asistencia" and "quien" not in VISTO["posts"][-1],
   "la previa viaja sin «quien» (no guarda nada)")

juego_srv.shutdown()
P.cerrar_conexiones()
print()
print(("✘ %d FALLAS" % len(fallos)) if fallos else "✔ todo bien")
sys.exit(1 if fallos else 0)
