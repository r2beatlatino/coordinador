# -*- coding: utf-8 -*-
"""probar_amigos_viejos — la mudanza de los AMIGOS del R2Beat viejo a Eñeños ID (social.importar_amistades). 18-nov-2026.

Eñeños: «quienes estén agregados en el R2Beat viejo deberán estar ya agregados como amigos en Eñeños ID». En el viejo
la amistad es de PERSONAJE y se guarda en los dos sentidos; en Eñeños es de PERSONA. Una `datos.db` vieja de mentira
con un caso de cada regla, y cada uno con su CONTROL (⟲):
  · Ana↔Beto (guardada en los dos sentidos) = UNA amistad «amigos»
  · el 2º personaje de Caro (cuenta_personajes) amigo de Ana = Ana↔Caro
  · un personaje MUDADO a la cuenta de Eli cuenta para Eli ⟲ no para su dueño de antes (Dani)
  · ⟲ dos personajes de la misma persona (Ana y su 2º) no la hacen amiga de sí misma
  · ⟲ un personaje BORRADO no trae amigos (Fede)
  · ⟲ una cuenta SUSPENDIDA no entra (Gabo)
  · un PEDIDO que ya estaba (Beto→Caro) pasa a «amigos»
  · ⟲ correrlo dos veces no duplica nada
  · --apodos: Ana recibe el apodo de su personaje del casillero 1 ⟲ Beto (apodo inválido) y Dani (apodo que ya tiene
    otra persona) quedan sin; Caro conserva el suyo; ⟲ Eli (su personaje se llama como su login) queda sin
"""
import contextlib
import hashlib
import io
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest().upper()


tmp = tempfile.mkdtemp(prefix="amigos_viejos_")
os.environ.update({
    "R2_CUENTAS_DUENA": "1", "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"), "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe.db"), "R2_ADMIN_ARCHIVO": os.path.join(tmp, "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "mod.txt"), "R2_PORTERO_PUERTO": "0",
})
from servidor import portero as P  # noqa: E402
from servidor import social as SO  # noqa: E402

# ── la base vieja de mentira ──
VIEJA = os.path.join(tmp, "datos_viejo.db")
v = sqlite3.connect(VIEJA)
v.executescript("""
CREATE TABLE users (uid INTEGER PRIMARY KEY, username TEXT, pass_hash TEXT, reg_time TEXT, last_ip TEXT, last_time TEXT);
CREATE TABLE chars (uid INTEGER PRIMARY KEY, nickname TEXT);
CREATE TABLE cuenta_personajes (username TEXT, ranura INTEGER, uid INTEGER);
CREATE TABLE personajes_borrados (uid INTEGER, username TEXT, ranura INTEGER, apodo TEXT, cuando TEXT);
CREATE TABLE friends (uid INTEGER, friend_uid INTEGER, added_at TEXT);
CREATE TABLE historial_diario (fecha TEXT, uid INTEGER, exp INTEGER, coin INTEGER);
CREATE TABLE record_cancion (uid INTEGER, cancion INTEGER, ultima INTEGER);
""")
# (la historia vieja tiene rastros de juego: una carrera y una foto diaria que cambia)
v.execute("INSERT INTO record_cancion VALUES (30, 1, 1795000000)")
v.executemany("INSERT INTO historial_diario VALUES (?, 3, ?, 0)", [("2026-09-26", 1), ("2026-09-27", 2)])
cuentas = [(1, "ana", sha("a")), (2, "beto", sha("b")), (3, "caro", sha("c")), (4, "dani", sha("d")),
           (5, "eli", sha("e")), (6, "fede", sha("f")), (7, "gabo", "BANNED:" + sha("g"))]
v.executemany("INSERT INTO users (uid, username, pass_hash, reg_time) VALUES (?, ?, ?, '2026-01-01')", cuentas)
v.executemany("INSERT INTO chars VALUES (?, ?)", [(1, "jugador1"), (2, "b!"), (3, "Carolina"), (4, "La Caro"), (5, "ELI"),
                                                   (6, "Fede"), (7, "Gabo")])
v.executemany("INSERT INTO cuenta_personajes VALUES (?, ?, ?)", [
    ("ana", 2, 11),     # el 2º personaje de Ana
    ("caro", 2, 30),    # el 2º de Caro
    ("eli", 2, 40),     # el personaje 40 era de Dani y se MUDÓ a Eli
])
v.execute("INSERT INTO personajes_borrados VALUES (60, 'fede', 2, 'borradito', '2026-02-02')")
v.execute("INSERT INTO cuenta_personajes VALUES ('fede', 2, 60)")

def amigos(a, b, cuando="2026-03-03 10:00:00"):
    v.execute("INSERT INTO friends VALUES (?, ?, ?)", (a, b, cuando))
    v.execute("INSERT INTO friends VALUES (?, ?, ?)", (b, a, cuando))

amigos(1, 2)            # Ana ↔ Beto
amigos(30, 1)           # 2º de Caro ↔ Ana
amigos(40, 2)           # el mudado (hoy de Eli) ↔ Beto
amigos(1, 11)           # Ana ↔ su propio 2º personaje
amigos(60, 1)           # el BORRADO de Fede ↔ Ana
amigos(7, 1)            # Gabo (suspendido) ↔ Ana
amigos(2, 3)            # Beto ↔ Caro (ya había un pedido)
v.commit()
v.close()

try:
    with contextlib.redirect_stdout(io.StringIO()):
        P.importar_cuentas(VIEJA)
    c = P._cuentas()
    eid = {r["usuario"]: int(r["uid"]) for r in c.execute("SELECT uid, usuario FROM cuentas")}
    # lo que ya había en Eñeños: Caro con su apodo; un pedido Beto→Caro
    c.execute("UPDATE cuentas SET apodo = 'La Caro', apodo_clave = 'la caro' WHERE uid = ?", (eid["caro"],))
    a, b = SO._par(eid["beto"], eid["caro"])
    c.execute("INSERT INTO amistades (a, b, estado, de, creada) VALUES (?, ?, 'pedido', ?, '2026-11-01')", (a, b, eid["beto"]))
    c.commit()

    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        r = P.consola(["importar-amigos", VIEJA, "--apodos"])
    print("  resumen:", salida.getvalue().strip())

    def es(x, y):
        a, b = SO._par(eid[x], eid[y])
        f = c.execute("SELECT estado FROM amistades WHERE a = ? AND b = ?", (a, b)).fetchone()
        return f["estado"] if f else None

    print("1 · las amistades")
    ok(es("ana", "beto") == "amigos", "Ana↔Beto (guardada en los dos sentidos) = amigos")
    ok(c.execute("SELECT COUNT(*) FROM amistades WHERE (a, b) = (?, ?)", SO._par(eid["ana"], eid["beto"])).fetchone()[0] == 1,
       "… y UNA sola fila")
    ok(es("ana", "caro") == "amigos", "el 2º personaje de Caro trae a Caro")
    ok(es("eli", "beto") == "amigos", "el personaje mudado cuenta para su cuenta de hoy (Eli)")
    ok(es("dani", "beto") is None, "⟲ no para su dueño de antes (Dani)")
    ok(c.execute("SELECT COUNT(*) FROM amistades WHERE a = b").fetchone()[0] == 0, "⟲ nadie es amigo de sí mismo")
    ok(es("fede", "ana") is None, "⟲ un personaje borrado no trae amigos")
    ok(es("gabo", "ana") is None, "⟲ una cuenta suspendida no entra")
    ok(es("beto", "caro") == "amigos", "el pedido que ya estaba pasó a amigos")
    ok(r["misma_persona"] == 2 and r["inactivas"] == 2, "el resumen cuenta lo salteado (misma persona, suspendida)")

    print("2 · otra vez")
    antes = c.execute("SELECT COUNT(*) FROM amistades").fetchone()[0]
    with contextlib.redirect_stdout(io.StringIO()):
        r2 = P.consola(["importar-amigos", VIEJA, "--apodos"])
    ok(c.execute("SELECT COUNT(*) FROM amistades").fetchone()[0] == antes and r2["nuevas"] == 0,
       "⟲ correrlo dos veces no duplica nada")

    print("3 · «visto por última vez»")
    import time as _t
    vi = {r["usuario"]: r["visto"] for r in c.execute("SELECT usuario, visto FROM cuentas")}
    ok(all(x is None for x in vi.values()), "⟲ importar NO inventa «visto» con la historia vieja (sólo cuenta el launcher nuevo o el juego)")
    SO._visto_escrito.clear()
    ok(SO.anotar_visto(P, [eid["beto"]], 1800000000) == 1, "un latido guarda el «visto»")
    ok(SO.anotar_visto(P, [eid["beto"]], 1800000100) == 0, "⟲ otro a los 100 s NO escribe (cada 5 min como mucho)")
    ok(c.execute("SELECT visto FROM cuentas WHERE uid = ?", (eid["beto"],)).fetchone()[0] == 1800000000, "… y quedó el primero")
    ok(SO.anotar_visto(P, [eid["beto"]], 1800000301) == 1, "a los 301 s sí escribe")
    SO._visto_escrito.clear()
    SO.anotar_visto(P, [eid["caro"]], 1795000000)
    SO._visto_escrito.clear()
    SO.anotar_visto(P, [eid["caro"]], 1700000000)
    ok(c.execute("SELECT visto FROM cuentas WHERE uid = ?", (eid["caro"],)).fetchone()[0] == 1795000000, "⟲ nunca va para atrás")
    # el JUEGO cuenta quién está adentro (como /api/interno/presencia): leer_juegos anota «visto» de esos
    import json as _json, threading as _th
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class _Juego(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            cuerpo = _json.dumps({"jugadores": [{"eid": eid["ana"], "personaje": "jugador1"}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(cuerpo))); self.end_headers()
            self.wfile.write(cuerpo)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Juego)
    _th.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["R2_PRESENCIA"] = "r2beat2013=http://127.0.0.1:%d/presencia" % srv.server_address[1]
    SO._visto_escrito.clear()
    SO.leer_juegos(P, ahora=1800000500)
    srv.shutdown()
    ok(c.execute("SELECT visto FROM cuentas WHERE uid = ?", (eid["ana"],)).fetchone()[0] == 1800000500,
       "estar en el JUEGO también anota «visto» (leer_juegos)")
    ok(c.execute("SELECT visto FROM cuentas WHERE uid = ?", (eid["eli"],)).fetchone()[0] is None,
       "⟲ quien no está en el juego ni en el launcher no recibe «visto»")
    ok(SO.con_visto({"tipo": "desconectado", "visto": None}, 1795000000)["visto"] == 1795000000,
       "desconectado sin dato en memoria: usa el guardado (sobrevive a un reinicio)")
    ok(SO.con_visto({"tipo": "desconectado", "visto": 1795000500}, 1795000000)["visto"] == 1795000500, "⟲ si la memoria es más nueva, gana la memoria")
    ok("visto" not in SO.con_visto({"tipo": "launcher"}, 1795000000), "⟲ conectado: no lleva «visto»")

    print("4 · los apodos (--apodos)")
    ap = {r["usuario"]: r["apodo"] for r in c.execute("SELECT usuario, apodo FROM cuentas")}
    ok(ap["ana"] == "jugador1", "Ana recibe el apodo de su personaje del casillero 1")
    ok(ap["caro"] == "La Caro", "Caro conserva el suyo")
    ok(not ap["beto"], "⟲ un apodo inválido («b!») no se pone")
    ok(not ap["dani"], "⟲ un apodo que ya tiene otra persona («La Caro») no se pone")
    ok(not ap["gabo"], "⟲ una cuenta suspendida no recibe apodo")
    ok(not ap["eli"], "⟲ un apodo igual al LOGIN («ELI» / eli) no se pone: el login es privado")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + ("✘ %d fallas" % len(fallos) if fallos else "✔ probar_amigos_viejos: todo bien"))
sys.exit(1 if fallos else 0)
