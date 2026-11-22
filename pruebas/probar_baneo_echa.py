# -*- coding: utf-8 -*-
"""probar_baneo_echa — ★ 21-nov-2026: banear en el Coordinador también DESCONECTA a la persona de los juegos.

Eñeños: «banear no desconecta al usuario». El baneo vive en Cuenta Eñeños (no le da más pases) y el que ya estaba
adentro seguía jugando. Ahora, después de banear, en cada server baneado que se gestiona se busca a la persona por su
Eñeños ID y se echa a sus personajes CONECTADOS. Dos juegos de mentira: uno habla como el panel de R2Beat
(`usuarios?q=` + `usuario/N/echar`) y otro como el contrato (`buscar?q=` + `echar {id}`).
Cada regla con su control al revés (⟲).

    python pruebas/probar_baneo_echa.py
"""
import contextlib
import io
import json
import os
import shutil
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
mal = 0


def ok(cond, que):
    global mal
    print(("  ✔ " if cond else "  ✘ ") + que)
    mal += 0 if cond else 1


FICHA = "ficha-de-prueba-baneo"
ECHADOS = []            # (juego, a quién, motivo, quién lo pidió)
LOCK = threading.Lock()
EID = {}                # se llena después de registrar


def servidor(tipo):
    class H(BaseHTTPRequestHandler):
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
            malo, otro = EID.get("malo"), EID.get("otro")
            if tipo == "r2beat" and self.path.startswith("/api/interno/panel/usuarios"):
                # la búsqueda del juego trae de más (un apodo que coincide): el Coordinador filtra por el Eñeños ID
                return self._mandar(200, {"filas": [
                    {"uid": 11, "enenos_id": malo, "conectado": True},      # su casillero 1, adentro
                    {"uid": 12, "enenos_id": malo, "conectado": False},     # su casillero 2, afuera
                    {"uid": 13, "enenos_id": otro, "conectado": True}]})    # OTRA persona, adentro
            if tipo == "contrato1" and self.path.startswith("/interno/panel/buscar"):
                return self._mandar(200, {"filas": [{"id": "gb-7", "enenos_id": malo, "conectado": True},
                                                    {"id": "gb-8", "enenos_id": otro, "conectado": True}]})
            return self._mandar(404, {"error": "no existe"})

        def do_POST(self):
            if self.headers.get("X-Ficha-Interna") != FICHA or self.headers.get("X-R2") != "1":
                return self._mandar(404, {"error": "no existe"})
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            quien = self.headers.get("X-Coordinador-Quien")
            if tipo == "r2beat" and self.path.endswith("/echar"):
                with LOCK:
                    ECHADOS.append(("r2", int(self.path.split("/")[-2]), d.get("motivo"), quien))
                return self._mandar(200, {"ok": True})
            if tipo == "contrato1" and self.path.endswith("/echar"):
                with LOCK:
                    ECHADOS.append(("gb", d.get("id"), d.get("motivo"), quien))
                return self._mandar(200, {"ok": True})
            return self._mandar(404, {"error": "no existe"})
    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s.server_address[1]


P_R2, P_GB = servidor("r2beat"), servidor("contrato1")
tmp = tempfile.mkdtemp(prefix="r2_baneo_echa_")
try:
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
        "R2_PANEL_GESTION": f"r2beat2013-prueba=http://127.0.0.1:{P_R2}/api/interno/panel;"
                            f"gunbound=contrato1:http://127.0.0.1:{P_GB}/interno/panel",
    })
    for k in ("R2_PANEL_SALUD", "R2_PRESENCIA", "R2_DISCORD_EVENTOS_WEBHOOK", "R2_JUEGOS_CATALOGO", "R2_UID_NUEVAS_DESDE"):
        os.environ.pop(k, None)
    from servidor import coordinador as CO
    from servidor import gestion as GE
    from servidor import portero as P

    with contextlib.redirect_stdout(io.StringIO()):
        for i, u in enumerate(["jefa", "malo", "otro"]):
            EID[u] = P.registrar(u, clave_txt=f"clave-{u}", ip=f"10.4.0.{i}")[1]["uid"]
    open(os.environ["R2_ADMIN_ARCHIVO"], "w", encoding="utf-8").write(f"{EID['jefa']}\n")
    pases = list(P._juegos())

    def banear(pases_b, viewer=None):
        ECHADOS.clear()
        CO._echando = None
        with contextlib.redirect_stdout(io.StringIO()):
            cod, _d = CO.accion(P, viewer or EID["jefa"], {"accion": "banear", "uid": EID["malo"], "pases": pases_b,
                                                           "motivo": "insultos", "horas": 2})
            if CO._echando:
                CO._echando.join(15)
        return cod, sorted(((e[0], str(e[1]), e[2], e[3]) for e in ECHADOS))

    print("1 · banear en R2Beat (prueba) echa a SUS personajes conectados")
    ok("r2beat2013-prueba" in pases and "gunbound" in pases, f"los pases del catálogo existen ({len(pases)})")
    cod, ech = banear(["r2beat2013-prueba"])
    ok(cod == 200, f"el baneo se hizo ({cod})")
    ok([e[:2] for e in ech] == [("r2", "11")], f"echado su personaje conectado (uid 11): {[e[:2] for e in ech]}")
    ok(bool(ech) and all(e[2] == "insultos" and e[3] == "coordinador:jefa" for e in ech),
       "con el motivo y firmado «coordinador:jefa»")
    ok(("r2", "12") not in [e[:2] for e in ech], "⟲ su casillero de afuera (uid 12) no se toca")
    ok(("r2", "13") not in [e[:2] for e in ech], "⟲ OTRA persona que aparece en la búsqueda (uid 13) no se echa")
    ok(not [e for e in ech if e[0] == "gb"], "⟲ GunBound no se toca: no se lo baneó ahí")

    print("\n2 · el contrato (GunBound): `buscar` + `echar {id}`")
    cod, ech = banear(["gunbound"])
    ok(cod == 200 and [e[:2] for e in ech] == [("gb", "gb-7")], f"echado por su id del juego: {[e[:2] for e in ech]}")
    ok(("gb", "gb-8") not in [e[:2] for e in ech], "⟲ el otro jugador conectado no")

    print("\n3 · ⟲ lo que NO echa")
    ECHADOS.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        CO.accion(P, EID["jefa"], {"accion": "desbanear", "uid": EID["malo"], "pases": ["r2beat2013-prueba", "gunbound"]})
    ok(not ECHADOS, "⟲ desbanear no echa a nadie")
    sin_gestion = [p for p in pases if p not in ("r2beat2013-prueba", "gunbound")]
    cod, ech = banear(sin_gestion[:1])
    ok(cod == 200 and not ech, f"⟲ un server sin gestión ({sin_gestion[:1]}): se banea igual y no hay a quién echar")
    cod, ech = banear(["gunbound"], viewer=EID["otro"])
    ok(cod in (401, 403) and not ech, f"⟲ alguien sin rol no banea ni echa ({cod})")

    print("\n4 · un juego que no contesta no rompe nada")
    os.environ["R2_PANEL_GESTION"] = "r2beat2013-prueba=http://127.0.0.1:9/api/interno/panel"
    with contextlib.redirect_stdout(io.StringIO()):
        res = GE.echar_de_los_juegos(EID["malo"], ["r2beat2013-prueba"], "coordinador:jefa", "x")
    ok(res == {"r2beat2013-prueba": "no contesta"}, f"queda anotado «no contesta»: {res}")
    cod, ech = banear(["r2beat2013-prueba"])
    ok(cod == 200 and not ech, f"⟲ y el baneo se hace igual ({cod})")
finally:
    try:
        P.cerrar_conexiones()
    except Exception:                                                    # noqa: BLE001
        pass
    shutil.rmtree(tmp, ignore_errors=True)
print("\n✔ todo bien" if not mal else f"\n✘ {mal} mal")
sys.exit(1 if mal else 0)
