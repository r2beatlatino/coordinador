# -*- coding: utf-8 -*-
"""probar_social — amigos, estado y chat de la plataforma Eñeños (servidor/social.py). 16-nov-2026.

El portero de verdad (HTTP, bases temporales, `R2_CUENTAS_DUENA=1`) + un «servidor de juego» falso que contesta la
presencia como lo hace R2Beat (`/api/interno/presencia`, con la ficha). Cada chequeo con su CONTROL AL REVÉS (⟲):
  · apodo: se pone y es único sin distinguir mayúsculas ⟲ uno repetido da 409 y uno mal formado 400
  · pedir por apodo y por Eñeños ID; el otro lo ve en «recibidos»; aceptar → amigos los dos ⟲ un pedido cruzado
    (el otro me pide a mí) también deja amigos; pedirse a sí mismo da 400; alguien inexistente 404
  · ⛔ el login NO aparece en ninguna respuesta ⟲ (el apodo sí)
  · estado: «launcher» con latido, «jugando» con el detalle que contó el juego (sala, canción, dificultad),
    «jugando EDA» si el launcher lo dice ⟲ sin latido = «desconectado»; lo del juego vencido no cuenta
  · chat: sólo entre amigos ⟲ a un no-amigo 403; vacío 400; más de 500 caracteres se recorta; el freno corta a 10
    cada 10 s; los mensajes de más de 2 DÍAS se borran ⟲ el de hace 1 día queda
  · «no leídos» cuenta y `chat` los marca leídos ⟲ después vuelve a 0
  · quitar deja de ser amigos ⟲ y ya no se puede escribir
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest().upper()


# ── el «juego» falso: cuenta la presencia como R2Beat ──
PRESENCIA = {"jugadores": []}


class Juego(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.headers.get("X-Ficha-Interna") != "ficha-prueba":
            self.send_response(404); self.end_headers(); return
        b = json.dumps(dict(PRESENCIA, juego="r2beat2013")).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


juego = ThreadingHTTPServer(("127.0.0.1", 0), Juego)
threading.Thread(target=juego.serve_forever, daemon=True).start()

tmp = tempfile.mkdtemp(prefix="social_")
os.environ.update({
    "R2_CUENTAS_DUENA": "1", "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"), "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe.db"), "R2_ADMIN_ARCHIVO": os.path.join(tmp, "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "mod.txt"), "R2_PORTERO_PUERTO": "0",
    "R2_CUENTAS_FICHA_INTERNA": "ficha-prueba",
    "R2_PRESENCIA": f"r2beat2013=http://127.0.0.1:{juego.server_address[1]}/api/interno/presencia",
})
from servidor import portero as P          # noqa: E402
from servidor import social as S           # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    srv = P.servidor(0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/cuentas"


def pedir(ruta, datos=None, token=None):
    cab = {"X-R2": "1", "Content-Type": "application/json"}
    if token:
        cab["Authorization"] = "Bearer " + token
    r = urllib.request.Request(URL + ruta, data=json.dumps(datos or {}).encode(), headers=cab, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=10) as x:
            return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def cuenta(usuario):
    pedir("/registrar", {"usuario": usuario, "pass_sha256_upper": sha("clave-" + usuario)})
    c, d = pedir("/entrar", {"usuario": usuario, "pass_sha256_upper": sha("clave-" + usuario)})
    return d["uid"], d["sesion"]


ana, s_ana = cuenta("ana_login")
beto, s_beto = cuenta("beto_login")
caro, s_caro = cuenta("caro_login")

print("· apodo")
c, d = pedir("/social/apodo", {"apodo": "jugador1 ñ"}, s_ana)
ok(c == 200 and d["apodo"] == "jugador1 ñ", "Ana se pone «jugador1 ñ» (acepta ñ y espacios)")
c, d = pedir("/social/apodo", {"apodo": "JUGADOR1 Ñ"}, s_beto)
ok(c == 409, f"⟲ el mismo apodo con otras mayúsculas: 409 (dio {c})")
c, d = pedir("/social/apodo", {"apodo": "ab"}, s_beto)
ok(c == 400, f"⟲ apodo corto: 400 (dio {c})")
c, d = pedir("/social/apodo", {"apodo": "Beto<script>"}, s_beto)
ok(c == 400, f"⟲ apodo con símbolos: 400 (dio {c})")
pedir("/social/apodo", {"apodo": "Beto"}, s_beto)

print("· pedidos")
c, d = pedir("/social/pedir", {"quien": "beto"}, s_ana)
ok(c == 200 and d["estado"] == "pedido", "Ana pide a «beto» por apodo (sin mayúsculas)")
c, d = pedir("/social/estado", {}, s_beto)
ok([x["apodo"] for x in d["recibidos"]] == ["jugador1 ñ"], "Beto lo ve en «recibidos»")
c, d = pedir("/social/responder", {"uid": ana, "aceptar": True}, s_beto)
c, d = pedir("/social/estado", {}, s_ana)
ok([x["apodo"] for x in d["amigos"]] == ["Beto"], "aceptado: Ana tiene a Beto de amigo")
c, d = pedir("/social/pedir", {"quien": str(ana)}, s_caro)
ok(c == 200 and d["estado"] == "pedido", "Caro pide a Ana por Eñeños ID (sin apodo propio)")
c, d = pedir("/social/pedir", {"quien": f"#{caro}"}, s_ana)
ok(d.get("estado") == "amigos", "⟲ Ana pide a Caro, que ya le había pedido: quedan amigos")
c, d = pedir("/social/estado", {}, s_ana)
ok(sorted(x["apodo"] for x in d["amigos"]) == ["Beto", f"Eñeños #{caro}"], "sin apodo se ve «Eñeños #id»")
c, d = pedir("/social/pedir", {"quien": "jugador1 ñ"}, s_ana)
ok(c == 400, f"⟲ pedirse a sí misma: 400 (dio {c})")
c, d = pedir("/social/pedir", {"quien": "nadie_existe"}, s_ana)
ok(c == 404, f"⟲ alguien que no existe: 404 (dio {c})")
crudo = json.dumps([pedir("/social/estado", {}, s)[1] for s in (s_ana, s_beto, s_caro)], ensure_ascii=False)
ok(not any(u in crudo for u in ("ana_login", "beto_login", "caro_login")), "⛔ el login NO aparece en ninguna respuesta")
ok("jugador1 ñ" in crudo, "⟲ (el apodo sí)")

print("· estado")
S._latidos.pop(caro, None)                                          # (Caro latió al pedir el estado de arriba)
c, d = pedir("/social/estado", {}, s_beto)                         # (Beto late; Caro no)
c, d = pedir("/social/estado", {}, s_ana)
est = {x["apodo"]: x["estado"] for x in d["amigos"]}
ok(est["Beto"]["tipo"] == "launcher", "Beto, con latido: «en el launcher»")
ok(est[f"Eñeños #{caro}"]["tipo"] == "desconectado", "⟲ Caro, sin latido: «desconectado»")
pedir("/social/estado", {"juego": "eda"}, s_caro)
c, d = pedir("/social/estado", {}, s_ana)
e = {x["apodo"]: x["estado"] for x in d["amigos"]}[f"Eñeños #{caro}"]
ok(e["tipo"] == "jugando" and e["nombre_juego"] == "Espada del Alma", "el launcher de Caro dice «jugando EDA»")
PRESENCIA["jugadores"] = [{"eid": beto, "personaje": "Betito", "canal": "Sol",
                           "sala": {"n": 12, "nombre": "Vengan", "cancion": "A la luna", "dificultad": 5,
                                    "jugando": True, "ocupantes": 4, "capacidad": 8}}]
S.leer_juegos(P)
c, d = pedir("/social/estado", {}, s_ana)
e = {x["apodo"]: x["estado"] for x in d["amigos"]}["Beto"]
ok(e["tipo"] == "jugando" and e["juego"] == "r2beat2013" and e["sala"]["cancion"] == "A la luna"
   and e["sala"]["dificultad"] == 5 and e["personaje"] == "Betito", "lo que cuenta R2Beat: sala, canción, dificultad, personaje")
ok([x["apodo"] for x in d["amigos"]][0] == "Beto", "los que juegan van primero")
c, d = pedir("/social/estado", {}, s_beto)
ok(d["yo"]["estado"]["tipo"] == "jugando" and d["yo"]["estado"]["sala"]["n"] == 12,
   "«yo.estado»: Beto ve su propia sala (para la presencia de Discord)")
c, d = pedir("/social/estado", {}, s_ana)
ok(d["yo"]["estado"]["tipo"] == "launcher", "⟲ Ana, que no juega: «en el launcher»")
S._en_juego[beto]["t"] -= S.VIDA_JUEGO + 1
c, d = pedir("/social/estado", {}, s_ana)
ok({x["apodo"]: x["estado"] for x in d["amigos"]}["Beto"]["tipo"] == "launcher", "⟲ lo del juego VENCIDO no cuenta")

print("· chat")
c0, d0 = pedir("/social/estado", {}, s_beto)
c, d = pedir("/social/enviar", {"para": beto, "texto": "hola  Beto 👋"}, s_ana)
ok(c == 200 and d["mensaje"]["texto"] == "hola  Beto 👋", "Ana le escribe a Beto")
c, d = pedir("/social/estado", {"desde": d0["ultimo"]}, s_beto)
ok([m["texto"] for m in d["mensajes"]] == ["hola  Beto 👋"], "Beto lo recibe en su latido (id > desde)")
ok({x["apodo"]: x["no_leidos"] for x in d["amigos"]}["jugador1 ñ"] == 1, "y figura 1 «no leído»")
c, d = pedir("/social/chat", {"con": ana}, s_beto)
ok([m["texto"] for m in d["mensajes"]] == ["hola  Beto 👋"], "abrir el chat trae el historial")
c, d = pedir("/social/estado", {}, s_beto)
ok({x["apodo"]: x["no_leidos"] for x in d["amigos"]}["jugador1 ñ"] == 0, "⟲ y lo marca leído")
c, d = pedir("/social/enviar", {"para": beto, "texto": "   "}, s_ana)
ok(c == 400, f"⟲ mensaje vacío: 400 (dio {c})")
c, d = pedir("/social/enviar", {"para": beto, "texto": "x" * 900}, s_ana)
ok(c == 200 and len(d["mensaje"]["texto"]) == 500, "un mensaje largo se recorta a 500")
c, d = pedir("/social/enviar", {"para": beto, "texto": "a\x00b\x1bc"}, s_ana)
ok(d["mensaje"]["texto"] == "abc", "sin caracteres de control")
ultimo = None
for i in range(12):
    ultimo, _ = pedir("/social/enviar", {"para": beto, "texto": f"m{i}"}, s_ana)
ok(ultimo == 429, f"⟲ el freno: más de 10 en 10 s da 429 (dio {ultimo})")
S._freno.clear()
dave, s_dave = cuenta("dave_login")
c, d = pedir("/social/enviar", {"para": dave, "texto": "hola"}, s_ana)
ok(c == 403, f"⟲ a alguien que no es amigo: 403 (dio {c})")

print("· ★ 20-nov: ya NO se borra a los 2 días (manda el tope de 1 GB: probar_chat_guardias.py)")
c = P._cuentas()
ahora = int(time.time())
with P._escribir:
    c.execute("INSERT INTO mensajes (de, para, texto, cuando) VALUES (?, ?, 'viejo', ?)", (ana, beto, ahora - 3 * 86400))
    c.execute("INSERT INTO mensajes (de, para, texto, cuando) VALUES (?, ?, 'de ayer', ?)", (ana, beto, ahora - 86400))
    c.commit()
pedir("/social/enviar", {"para": beto, "texto": "nuevo"}, s_ana)
textos = [r[0] for r in c.execute("SELECT texto FROM mensajes")]
ok("viejo" in textos and "de ayer" in textos, "el mensaje de hace 3 días QUEDA (Benja: quitar «se borrará en 2 días»)")

print("· quitar")
c, d = pedir("/social/quitar", {"uid": beto}, s_ana)
c, d = pedir("/social/estado", {}, s_ana)
ok("Beto" not in [x["apodo"] for x in d["amigos"]], "Ana quita a Beto")
c, d = pedir("/social/enviar", {"para": beto, "texto": "hola"}, s_ana)
ok(c == 403, f"⟲ y ya no le puede escribir (dio {c})")
c, d = pedir("/social/estado", {})
ok(c == 401, f"⟲ sin sesión: 401 (dio {c})")

srv.shutdown(); juego.shutdown()
P.cerrar_conexiones()
shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'OK' if not fallos else 'FALLAN ' + str(len(fallos))} · amigos, estado y chat")
sys.exit(1 if fallos else 0)
