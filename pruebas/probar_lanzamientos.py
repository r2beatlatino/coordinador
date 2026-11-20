# -*- coding: utf-8 -*-
"""probar_lanzamientos — el «contenido dinámico»: cuándo se abre cada juego y las invitaciones anticipadas. 18-nov-2026.

Benja: EDA sábado 21 19:00 (Perú), GunBound domingo 22 12:00 (Perú), Eñeñosbit 2027 lunes 23 19:00 (Perú); EDA y
GunBound BETA, Eñeñosbit ALPHA; antes, cerrado salvo invitación; la invitación llega a Discord con Ñ2-ID y
aprobar / rechazar (admins y moderadores). Con un DISCORD FALSO (webhook local) y CONTROLES (⟲):
  · las fechas en hora de Perú ⟲ un lanzamientos.json las cambia sin publicar nada
  · antes de la fecha: una cuenta común NO entra (eda, gunbound, gunbound-prueba, r2beat-moderno) ⟲ admin y
    moderador sí ⟲ r2beat2013 (sin lanzamiento) sigue abierto
  · después: toda cuenta activa (EDA también) ⟲ un baneado sigue afuera
  · pedir: queda pendiente y Discord recibe el Ñ2-ID y el Eñeños ID ⟲ NUNCA el login ⟲ pedir otra vez no repite
  · decidir: ⟲ una cuenta común no puede ⟲ aprobar da el permiso ANTES de la fecha y EDITA el mensaje de Discord
    ⟲ decidir dos veces da 409
  · rechazar: ⟲ no se puede volver a pedir enseguida; a las 24 h sí
  · ⟲ el enlace de Discord (GET del panel) no decide nada: sin la sesión del panel, 401 y la solicitud sigue igual
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


# ── el DISCORD falso: guarda lo que le mandan ──
DISCORD = []


class Webhook(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _resp(self, cuerpo):
        b = json.dumps(cuerpo).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        DISCORD.append(("POST", self.path, d))
        self._resp({"id": "9001"})

    def do_PATCH(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        DISCORD.append(("PATCH", self.path, d))
        self._resp({"id": "9001"})


wh = ThreadingHTTPServer(("127.0.0.1", 0), Webhook)
threading.Thread(target=wh.serve_forever, daemon=True).start()

tmp = tempfile.mkdtemp(prefix="lanzamientos_")
os.environ.update({
    "R2_CUENTAS_DUENA": "1", "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"), "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe.db"), "R2_ADMIN_ARCHIVO": os.path.join(tmp, "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "mod.txt"), "R2_PORTERO_PUERTO": "0",
    "R2_DISCORD_EVENTOS_WEBHOOK": "http://127.0.0.1:%d/api/webhooks/1/abc" % wh.server_address[1],
})
open(os.path.join(tmp, "admin.txt"), "w").write("jefa\n")
open(os.path.join(tmp, "mod.txt"), "w").write("mode\n")
from servidor import portero as P  # noqa: E402
from servidor import social as SO  # noqa: E402
from servidor import lanzamientos as LZ  # noqa: E402

LZ._discord_en_hilo = LZ.avisar_discord           # (en la prueba, Discord sin hilo: así se puede mirar enseguida)


def esperar_discord(n):
    return len(DISCORD) >= n


try:
    vieja = os.path.join(tmp, "vieja.db")
    v = sqlite3.connect(vieja)
    v.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, username TEXT, pass_hash TEXT, reg_time TEXT)")
    v.executemany("INSERT INTO users VALUES (?, ?, ?, '2026-01-01')",
                  [(i, n, hashlib.sha256(n.encode()).hexdigest().upper()) for i, n in
                   ((1, "ana_login"), (2, "beto"), (3, "jefa"), (4, "mode"), (5, "malo"))])
    v.commit(); v.close()
    with contextlib.redirect_stdout(io.StringIO()):
        P.importar_cuentas(vieja)
    c = P._cuentas()
    eid = {r["usuario"]: int(r["uid"]) for r in c.execute("SELECT uid, usuario FROM cuentas")}
    c.execute("UPDATE cuentas SET apodo = 'jugador1', apodo_clave = 'jugador1' WHERE uid = ?", (eid["ana_login"],))
    c.commit()
    SO._sesion = lambda P_, tok, ahora: int(tok) if str(tok).isdigit() else None
    P.sesion_de = lambda tok, *a, **k: int(tok) if str(tok).isdigit() else None
    P.estado_r2beat = lambda uid: "ok"
    ana, beto, jefa, mode, malo = (eid[k] for k in ("ana_login", "beto", "jefa", "mode", "malo"))
    pc = P._propia()
    pc.execute("INSERT INTO baneos (uid, juego, desde, quien, motivo) VALUES (?, 'eda', 'x', 'x', 'x')", (malo,)); pc.commit()

    print("1 · las fechas (hora de Perú)")
    t = LZ.tabla(P)
    ok(t["eda"]["desde_t"] == int(datetime.fromisoformat("2026-11-22T00:00:00+00:00").timestamp()), "EDA: sábado 21, 19:00 Perú = 00:00 UTC del 22")
    ok(t["gunbound"]["desde_t"] == int(datetime.fromisoformat("2026-11-22T17:00:00+00:00").timestamp()), "GunBound: domingo 22, 12:00 Perú")
    ok(t["r2beat-moderno"]["desde_t"] == int(datetime.fromisoformat("2026-11-24T00:00:00+00:00").timestamp()), "Eñeñosbit 2027: lunes 23, 19:00 Perú")
    ok((t["eda"]["etiqueta"], t["gunbound"]["etiqueta"], t["r2beat-moderno"]["etiqueta"]) == ("BETA", "BETA", "ALPHA"), "BETA · BETA · ALPHA")

    print("2 · antes de la fecha")
    antes = t["eda"]["desde_t"] - 3600
    for pase in ("eda", "gunbound", "gunbound-prueba", "r2beat-moderno"):
        ok(LZ.cerrado_para(P, beto, pase, antes) is False, f"⟲ una cuenta común no entra a {pase}")
    ok(LZ.cerrado_para(P, jefa, "eda", antes) is True and LZ.cerrado_para(P, mode, "gunbound", antes) is True, "admin y moderador sí")
    ok(LZ.cerrado_para(P, beto, "r2beat2013", antes) is None and P.permitido(beto, "r2beat2013"), "⟲ r2beat2013 no tiene lanzamiento: sigue abierto")

    print("3 · después de la fecha")
    ok(LZ.cerrado_para(P, beto, "eda", t["eda"]["desde_t"] + 1) is True, "EDA abierto a toda cuenta (antes era sólo aprobadas)")
    os.makedirs(os.path.join(tmp, "config"), exist_ok=True)
    open(os.path.join(tmp, "config", "lanzamientos.json"), "w").write(json.dumps({"eda": {"desde": "2020-01-01T00:00:00-05:00"}}))
    ok(P.permitido(beto, "eda"), "un lanzamientos.json con la fecha pasada lo abre YA, sin publicar nada")
    ok(not P.permitido(malo, "eda"), "⟲ un baneado sigue afuera")
    ok(not P.permitido(beto, "gunbound"), "⟲ GunBound (su fecha no cambió) sigue cerrado")
    os.remove(os.path.join(tmp, "config", "lanzamientos.json"))
    ok(not P.permitido(beto, "eda"), "⟲ sin el archivo, vuelve a la fecha de fábrica (cerrado)")

    print("4 · pedir la invitación")
    r = LZ.pedir(P, str(ana), "eda", antes)
    ok(r == (200, {"estado": "pendiente"}), "pedir: pendiente")
    ok(esperar_discord(1) and DISCORD[0][0] == "POST" and "wait=true" in DISCORD[0][1], "Discord recibió el mensaje (webhook, ?wait=true)")
    texto = json.dumps(DISCORD[0][2], ensure_ascii=False)
    ok("jugador1" in texto and str(ana) in texto and "EDA" in texto and "BETA" in texto, "… con el Ñ2-ID, el Eñeños ID, el juego y la etiqueta")
    ok("ana_login" not in texto, "⟲ ⛔ el LOGIN no viaja a Discord")
    ok("#invitacion=" in texto and "accion=aprobar" in texto and "accion=rechazar" in texto, "… y los enlaces Aprobar / Rechazar al panel")
    ok(LZ.pedir(P, str(ana), "eda", antes)[1] == {"estado": "pendiente"} and len(DISCORD) == 1, "⟲ pedir otra vez: sigue pendiente y no repite el mensaje")
    ok(LZ.pedir(P, "nadie", "eda", antes)[0] == 401 and LZ.pedir(P, str(ana), "nada", antes)[0] == 404, "⟲ sin sesión 401 · juego inexistente 404")
    ok(LZ.pedir(P, str(ana), "eda", t["eda"]["desde_t"] + 5)[1] == {"estado": "libre"}, "después de la fecha: «libre» (no hace falta)")
    l = LZ.lista(P, str(ana), antes)[1]["juegos"]["eda"]
    ok(l["permitido"] is False and l["invitacion"] == "pendiente" and l["libre"] is False, "la lista del launcher: cerrado, pendiente")

    print("5 · decidir (el panel)")
    iid = pc.execute("SELECT id FROM invitaciones WHERE uid = ?", (ana,)).fetchone()[0]
    ok(LZ.decidir(P, beto, iid, "aprobar")[0] == 401, "⟲ una cuenta común no puede decidir")
    r = LZ.decidir(P, mode, iid, "aprobar", antes)
    ok(r[0] == 200 and r[1]["invitacion"]["estado"] == "aprobada", "un MODERADOR aprueba")
    ok(LZ.cerrado_para(P, ana, "eda", antes) is True, "… y jugador1 entra a EDA ANTES de la fecha")
    ok(LZ.cerrado_para(P, ana, "gunbound", antes) is False, "⟲ sólo a EDA (GunBound sigue cerrado para ella)")
    ok(esperar_discord(2) and DISCORD[1][0] == "PATCH" and DISCORD[1][1].endswith("/messages/9001"), "el mensaje de Discord se EDITA")
    ok("Aprobada por mode" in json.dumps(DISCORD[1][2], ensure_ascii=False) and "accion=" not in json.dumps(DISCORD[1][2]),
       "… «Aprobada por mode», sin los enlaces")
    ok(LZ.decidir(P, jefa, iid, "rechazar")[0] == 409, "⟲ decidir dos veces: 409")
    ok(P._propia().execute("SELECT COUNT(*) FROM auditoria WHERE accion = 'aprobar' AND detalle LIKE 'invitación%'").fetchone()[0] == 1,
       "queda en la auditoría del panel")

    print("6 · rechazar")
    lejos = t["gunbound"]["desde_t"] - 5 * 86400        # (5 días antes: «24 h después» sigue antes de la fecha)
    LZ.pedir(P, str(beto), "gunbound", lejos)
    iid2 = pc.execute("SELECT id FROM invitaciones WHERE uid = ?", (beto,)).fetchone()[0]
    LZ.decidir(P, jefa, iid2, "rechazar", lejos)
    ok(LZ.cerrado_para(P, beto, "gunbound", lejos) is False, "rechazada: sigue sin entrar")
    ok(LZ.pedir(P, str(beto), "gunbound", lejos + 60)[0] == 429, "⟲ no puede volver a pedirla enseguida")
    ok(LZ.pedir(P, str(beto), "gunbound", lejos + LZ.REPEDIR_SEG + 60)[1] == {"estado": "pendiente"}, "a las 24 h sí")
    pend = LZ.pendientes(P)
    ok([f["juego"] for f in pend] == ["gunbound"] and pend[0]["uid"] == beto, "la lista del panel: sólo las PENDIENTES (no la aprobada ni la rechazada)")
    LZ.pedir(P, str(beto), "r2beat-moderno", lejos)
    ok([f["juego"] for f in LZ.pendientes(P)] == ["gunbound", "r2beat-moderno"], "varias de la misma cuenta: todas en la lista")
    LZ.decidir(P, jefa, LZ.pendientes(P)[1]["id"], "aprobar", lejos)
    ok([f["juego"] for f in LZ.pendientes(P)] == ["gunbound"], "⟲ decidida, sale de la lista")

    print("7 · el enlace de Discord no decide solo")
    srv = P.armar_servidor(0) if hasattr(P, "armar_servidor") else None
    if srv is None:
        from http.server import ThreadingHTTPServer as _T
        srv = _T(("127.0.0.1", 0), P._Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    iid_pend = LZ.pendientes(P)[0]["id"]                # (la de GunBound de beto, pendiente)
    url = "http://127.0.0.1:%d/admin/invitacion?id=%d" % (srv.server_address[1], iid_pend)
    try:
        urllib.request.urlopen(url, timeout=5); cod = 200
    except urllib.error.HTTPError as e:
        cod = e.code
    estado = pc.execute("SELECT estado FROM invitaciones WHERE id = ?", (iid_pend,)).fetchone()[0]
    ok(cod == 401 and estado == "pendiente", "⟲ abrir el enlace sin la sesión del panel: 401 y la solicitud sigue pendiente")
    srv.shutdown()
finally:
    wh.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + ("✘ %d fallas" % len(fallos) if fallos else "✔ probar_lanzamientos: todo bien"))
sys.exit(1 if fallos else 0)
