# -*- coding: utf-8 -*-
"""probar_social_espera — la ESPERA LARGA de mensajes (social.esperar). 18-nov-2026.

Benja: «los mensajes funcionan, pero llegan con algo de delay». El launcher preguntaba cada 4 s (cada 20 s con el
panel cerrado); ahora deja una pregunta abierta que el server contesta apenas alguien escribe. Con CONTROLES (⟲):
  · un mensaje para mí DESPIERTA la espera enseguida (no a los 25 s)
  · ⟲ sin mensajes, la espera vuelve sola al tope con «no hay»
  · ⟲ un mensaje para OTRA persona no me despierta
  · si el mensaje ya estaba (llegó antes de preguntar), contesta al instante
  · ⟲ sin sesión: 401; `desde` roto: 400
"""
import contextlib
import hashlib
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


tmp = tempfile.mkdtemp(prefix="social_espera_")
os.environ.update({
    "R2_CUENTAS_DUENA": "1", "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"), "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe.db"), "R2_ADMIN_ARCHIVO": os.path.join(tmp, "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "mod.txt"), "R2_PORTERO_PUERTO": "0",
})
from servidor import portero as P  # noqa: E402
from servidor import social as SO  # noqa: E402

try:
    vieja = os.path.join(tmp, "vieja.db")
    v = sqlite3.connect(vieja)
    v.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, username TEXT, pass_hash TEXT, reg_time TEXT)")
    v.executemany("INSERT INTO users VALUES (?, ?, ?, '2026-01-01')",
                  [(i, n, hashlib.sha256(n.encode()).hexdigest().upper()) for i, n in ((1, "ana"), (2, "beto"), (3, "caro"))])
    v.commit(); v.close()
    with contextlib.redirect_stdout(io.StringIO()):
        P.importar_cuentas(vieja)
    c = P._cuentas()
    eid = {r["usuario"]: int(r["uid"]) for r in c.execute("SELECT uid, usuario FROM cuentas")}
    for x, y in (("ana", "beto"), ("ana", "caro"), ("beto", "caro")):
        a, b = SO._par(eid[x], eid[y])
        c.execute("INSERT INTO amistades (a, b, estado, de, creada) VALUES (?, ?, 'amigos', ?, 'x')", (a, b, a))
    c.commit()
    SO._sesion = lambda P_, tok, ahora: int(tok) if str(tok).isdigit() else None   # (la sesión = el uid, para la prueba)
    SO._freno.clear()

    def esperar_en_hilo(quien, desde, tope):
        out = {}

        def h():
            t0 = time.monotonic()
            out["r"] = SO.esperar(P, str(eid[quien]), desde, tope=tope)
            out["s"] = time.monotonic() - t0
        th = threading.Thread(target=h)
        th.start()
        return th, out

    print("1 · un mensaje despierta la espera")
    th, out = esperar_en_hilo("beto", 0, 10)
    time.sleep(0.4)
    SO.enviar(P, str(eid["ana"]), eid["beto"], "hola")
    th.join(12)
    ok(out["r"] == (200, {"hay": True}), "la espera de Beto dice «hay»")
    ok(out["s"] < 1.5, "… enseguida (%.2f s, no a los 10 s del tope)" % out["s"])

    print("2 · sin mensajes")
    ultimo = c.execute("SELECT MAX(id) FROM mensajes").fetchone()[0]
    th, out = esperar_en_hilo("beto", ultimo, 1.0)
    th.join(5)
    ok(out["r"] == (200, {"hay": False}) and 0.9 <= out["s"] < 2.5, "⟲ sin mensajes vuelve sola al tope con «no hay» (%.2f s)" % out["s"])

    print("3 · un mensaje para otra persona")
    th, out = esperar_en_hilo("caro", c.execute("SELECT MAX(id) FROM mensajes").fetchone()[0], 1.5)
    time.sleep(0.3)
    SO.enviar(P, str(eid["ana"]), eid["beto"], "esto es para Beto")
    th.join(5)
    ok(out["r"] == (200, {"hay": False}) and out["s"] >= 1.3, "⟲ un mensaje para Beto no despierta a Caro (%.2f s)" % out["s"])

    print("4 · el que ya estaba")
    t0 = time.monotonic()
    r = SO.esperar(P, str(eid["beto"]), 0, tope=5)
    ok(r == (200, {"hay": True}) and time.monotonic() - t0 < 0.5, "si ya había un mensaje después de `desde`, contesta al instante")

    print("5 · pedidos malos")
    ok(SO.esperar(P, "nadie", 0, tope=1)[0] == 401, "⟲ sin sesión: 401")
    ok(SO.esperar(P, str(eid["ana"]), "x", tope=1)[0] == 400, "⟲ `desde` roto: 400")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + ("✘ %d fallas" % len(fallos) if fallos else "✔ probar_social_espera: todo bien"))
sys.exit(1 if fallos else 0)
