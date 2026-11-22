# -*- coding: utf-8 -*-
"""probar_baneos — los BANEOS CON TIEMPO (20-nov-2026). Eñeños: «baneos en X juegos, por X horas, por X días, X motivo;
el launcher baneado, al presionar Jugar, debe recibir un popup con el motivo de su ban + el tiempo».

Se levanta el portero de verdad (HTTP, `R2_CUENTAS_DUENA=1`, bases temporales). Cada regla con su CONTROL AL REVÉS (⟲):
  · la MIGRACIÓN: una portero.db de antes (sin `hasta`) gana la columna y su baneo sigue PERMANENTE ⟲ otra cuenta entra
  · VENCE A LA HORA: 1 s antes niega ⟲ 1 s después deja, y la fila queda (historial)
  · PERMANENTE no vence: a 20 años sigue negando ⟲ desbanear antes de tiempo lo levanta (y la fila queda)
  · VARIOS JUEGOS a la vez (cada uno con todos sus servidores) ⟲ el que no se marcó sigue abierto
  · el MODERADOR: fuera de sus juegos no (y no toca NINGUNO: todo o nada), ni permanente, ni más del tope, ni sin
    duración, ni toda la red ⟲ el tope justo sí; el ADMIN, permanente y toda la red sí; el moderador viejo, nada
  · el MOTIVO es obligatorio y ≤ 200 ⟲ 200 justos andan
  · el PASE rechazado: el mismo 403 de siempre, con error «baneado», juego, motivo, hasta y restante_seg ⟲ sin ban, 200
  · la LISTA de vigentes («vence en …»): no trae los vencidos ni los levantados ⟲ trae los vigentes; el moderador sólo
    los de sus juegos
  · el TEXTO del tiempo: «2 días y 3 horas», «45 minutos» ⟲ singulares y redondeo
"""
import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


tmp = tempfile.mkdtemp(prefix="baneos_")
os.makedirs(os.path.join(tmp, "config"))
# todos los lanzamientos YA abiertos: lo que se prueba acá es el ban, no la fecha
with open(os.path.join(tmp, "config", "lanzamientos.json"), "w", encoding="utf-8") as f:
    json.dump({"eda": {"desde": "2020-01-01T00:00:00-05:00"}, "gunbound": {"desde": "2020-01-01T00:00:00-05:00"},
               "r2beat-moderno": {"desde": "2020-01-01T00:00:00-05:00"}}, f)

# ── 1 · una portero.db de ANTES (baneos sin `hasta`), con un baneo viejo ────────────────────────────────────────
VIEJA = os.path.join(tmp, "portero.db")
cv = sqlite3.connect(VIEJA)
cv.execute("CREATE TABLE baneos (uid INTEGER NOT NULL, juego TEXT NOT NULL, desde TEXT, quien TEXT, motivo TEXT, "
           "PRIMARY KEY (uid, juego))")
cv.execute("INSERT INTO baneos VALUES (10000000, 'r2beat2013', '2026-11-01 10:00:00', 'consola', 'viejo y permanente')")
cv.commit()
cv.close()

os.environ.update({
    "R2_CUENTAS_DUENA": "1",
    "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": VIEJA,
    "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe_datos.db"),
    "R2_ADMIN_ARCHIVO": os.path.join(tmp, "config", "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "config", "moderadores.txt"),
    "R2_PORTERO_PUERTO": "0",
    "R2_CUENTAS_UID_DESDE": "10000000",
})
for k in ("R2_PANEL_SALUD", "R2_PRESENCIA", "R2_DISCORD_EVENTOS_WEBHOOK", "R2_JUEGOS_CATALOGO", "R2_UID_NUEVAS_DESDE"):
    os.environ.pop(k, None)

from servidor import portero as P          # noqa: E402
from servidor import coordinador as CO     # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    UID, TOK = {}, {}
    for i, u in enumerate(["vieja", "jefa", "modgb", "modviejo", "jugadora", "otra", "control"]):
        UID[u] = P.registrar(u, clave_txt=f"clave-{u}", ip=f"10.1.0.{i}")[1]["uid"]
        TOK[u] = P.entrar(u, clave_txt=f"clave-{u}", ip=f"10.1.0.{i}")[1]["sesion"]
open(os.environ["R2_ADMIN_ARCHIVO"], "w", encoding="utf-8").write(f"{UID['jefa']}\n")
open(os.environ["R2_MODERADOR_ARCHIVO"], "w", encoding="utf-8").write(f"{UID['modgb']} gunbound\nmodviejo\n")
JEFA, MOD, VIEJO, J, OTRA, CTRL = (UID[k] for k in ("jefa", "modgb", "modviejo", "jugadora", "otra", "control"))

with contextlib.redirect_stdout(io.StringIO()):
    srv = P.servidor(0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/cuentas"


def pase_http(token, juego):
    req = urllib.request.Request(URL + "/pase", data=json.dumps({"juego": juego}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-R2": "1",
                                          "Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def callado(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return f(*a, **k)


T = int(time.time())

print("1 · la migración: una portero.db de antes")
cols = [r[1] for r in P._propia().execute("PRAGMA table_info(baneos)")]
ok("hasta" in cols, f"la tabla ganó la columna `hasta` ({cols})")
fila = P._propia().execute("SELECT hasta, motivo FROM baneos WHERE uid = 10000000").fetchone()
ok(UID["vieja"] == 10000000 and fila is not None and fila["hasta"] is None, "el baneo viejo quedó con `hasta` NULL (permanente)")
cod, d = pase_http(TOK["vieja"], "r2beat2013")
ok(cod == 403 and d.get("error") == "baneado" and d.get("hasta") is None and d.get("restante_seg") is None
   and d.get("motivo") == "viejo y permanente", f"…y sigue negando el pase, como permanente ({cod} {d})")
cod, d = pase_http(TOK["control"], "r2beat2013")
ok(cod == 200 and d.get("pase"), "⟲ otra cuenta, sin ban, recibe su pase")
P._migrar_baneos(P._propia())
ok([r[1] for r in P._propia().execute("PRAGMA table_info(baneos)")].count("hasta") == 1, "migrar dos veces no rompe nada")

print("2 · el pase rechazado trae el porqué y el tiempo")
cod, d = pase_http(TOK["jugadora"], "gunbound")
ok(cod == 200, f"⟲ antes del ban: pase de GunBound ({cod})")
cod, r = callado(P.admin_banear, JEFA, J, ["gunbound"], "Insultos en el chat", {"horas": 1}, ahora=T)
ok(cod == 200 and r["hasta"] == T + 3600, f"la ADMIN banea 1 hora en GunBound ({cod})")
cod, d = pase_http(TOK["jugadora"], "gunbound")
ok(cod == 403, f"el MISMO código de siempre para «no permitido»: 403 ({cod})")
ok(d.get("error") == "baneado" and d.get("juego") == "gunbound" and d.get("motivo") == "Insultos en el chat"
   and d.get("hasta") == T + 3600 and isinstance(d.get("restante_seg"), int) and 3500 < d["restante_seg"] <= 3600,
   f"trae error «baneado», juego, motivo, hasta y restante_seg ({d})")
ok(isinstance(d.get("texto"), str) and "Insultos en el chat" in d["texto"] and "Vence en" in d["texto"],
   "y la frase armada (`texto`) para quien no sepa leer lo demás")
cod, d = pase_http(TOK["jugadora"], "r2beat2013")
ok(cod == 200, f"⟲ en otro juego (R2Beat) sigue entrando ({cod})")
yo = {g["id"]: g for g in P.juegos_de(J)}
ok("baneo" in yo["gunbound"] and "baneo" not in yo["r2beat2013"], "/entrar y /yo marcan el juego baneado con su `baneo`")

print("3 · vence a la hora")
tok = TOK["jugadora"]
cod, d = callado(P.pedir_pase, tok, "gunbound", "", T + 3599)
ok(cod == 403 and d.get("error") == "baneado" and d.get("restante_seg") == 1, f"1 s antes: niega, falta 1 s ({cod} {d.get('restante_seg')})")
cod, d = callado(P.pedir_pase, tok, "gunbound", "", T + 3601)
ok(cod == 200 and d.get("pase"), f"⟲ 1 s después: deja, solo ({cod})")
ok(P._propia().execute("SELECT 1 FROM baneos WHERE uid = ? AND juego = 'gunbound'", (J,)).fetchone() is not None,
   "y el baneo vencido NO se borró (historial)")
ok(not P.permitido(J, "gunbound", T + 3599) and P.permitido(J, "gunbound", T + 3601), "permitido() dice lo mismo")

print("4 · permanente no vence")
cod, _ = callado(P.admin_banear, JEFA, OTRA, ["eda"], "Trampa reiterada", {"permanente": True}, ahora=T)
ok(cod == 200, f"la ADMIN banea PERMANENTE en EDA ({cod})")
VEINTE = T + 20 * 365 * 86400
ok(P.baneo_vigente(OTRA, "eda", VEINTE) is not None and not P.permitido(OTRA, "eda", VEINTE), "a 20 años sigue contando")
cod, d = callado(P.pedir_pase, TOK["otra"], "eda", "", T + 29 * 86400)   # (la sesión dura 30 días)
ok(cod == 403 and d.get("hasta") is None and d.get("restante_seg") is None, f"y el pase lo niega, sin fecha ({cod})")
ok("permanente" in d.get("texto", ""), "su frase dice que es permanente")
cod, r = callado(P.admin_desbanear, JEFA, OTRA, ["eda"])
ok(cod == 200 and r["levantados"] == ["eda"], "⟲ desbanear antes de tiempo")
cod, d = pase_http(TOK["otra"], "eda")
ok(cod == 200, f"…y ya entra ({cod})")
ok(P._propia().execute("SELECT hasta FROM baneos WHERE uid = ? AND juego = 'eda'", (OTRA,)).fetchone()["hasta"] is not None,
   "la fila quedó, con su `hasta` = el momento del desbaneo")

print("5 · varios juegos a la vez (por el panel del Coordinador)")
cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": OTRA, "juegos": ["gunbound", "eda"], "dias": 2,
                                      "motivo": "Multicuenta"})
ok(cod == 200, f"la ADMIN banea en GunBound y EDA de una vez ({cod} {d.get('error')})")
for pase in ("gunbound", "gunbound-prueba", "eda", "eda-prueba"):          # (★ 21-nov: EDA también tiene server de prueba)
    ok(not P.permitido(OTRA, pase), f"  {pase}: baneada")
ok(P.permitido(OTRA, "r2beat2013"), "⟲ R2Beat, que no se marcó, sigue abierto")
gb = next(j for j in d["persona"]["juegos"] if j["id"] == "gunbound")
ok(all(x["baneada"] and x["restante_seg"] > 2 * 86400 - 60 and x["hasta"] for x in gb["pases"]),
   "la ficha de la persona trae `hasta` y `restante_seg` en cada servidor")
aud = [a for a in P._propia().execute("SELECT accion, juego, detalle FROM auditoria WHERE uid = ? AND accion = 'banear' "
                                      "ORDER BY id DESC LIMIT 4", (OTRA,))]
ok({a["juego"] for a in aud} == {"gunbound", "gunbound-prueba", "eda", "eda-prueba"} and all(a["detalle"] == "por 2 días · Multicuenta" for a in aud),
   "cada servidor a la auditoría, con la duración y el motivo")

print("6 · el moderador: sólo sus juegos, con tope y sin permanente")
N = lambda: P._propia().execute("SELECT COUNT(*) FROM baneos WHERE uid = ?", (CTRL,)).fetchone()[0]
antes = N()
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound", "eda"], "horas": 3, "motivo": "x"})
ok(cod == 403 and N() == antes, f"⟲ GunBound + EDA (EDA no es suyo): 403 y no toca NINGUNO ({cod})")
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "pase": "eda", "horas": 3, "motivo": "x"})
ok(cod == 403, f"⟲ sólo EDA: 403 ({cod})")
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "permanente": True, "motivo": "x"})
ok(cod == 403 and N() == antes, f"⟲ permanente: 403 ({cod})")
tope_d = P.BANEO_TOPE_MODERADOR_SEG // 86400
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "dias": tope_d + 1, "motivo": "x"})
ok(cod == 403 and N() == antes, f"⟲ {tope_d + 1} días (más del tope): 403 ({cod})")
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "horas": tope_d * 24 + 1, "motivo": "x"})
ok(cod == 403, f"⟲ el tope también en horas ({tope_d * 24 + 1} h): 403 ({cod})")
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "motivo": "x"})
ok(cod == 400 and N() == antes, f"⟲ sin duración: 400 ({cod})")
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "red": True, "horas": 1, "motivo": "x"})
ok(cod == 403 and N() == antes, f"⟲ toda la red: 403 ({cod})")
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "dias": tope_d, "motivo": "Spam"})
ok(cod == 200 and not P.permitido(CTRL, "gunbound") and not P.permitido(CTRL, "gunbound-prueba"),
   f"el tope justo ({tope_d} días) en SU juego: sí, con sus dos servidores ({cod})")
cod, d = callado(CO.accion, P, MOD, {"accion": "desbanear", "uid": CTRL, "juegos": ["gunbound"]})
ok(cod == 200 and P.permitido(CTRL, "gunbound"), f"y lo desbanea antes de tiempo ({cod})")
# ★ en MESES (Eñeños: «que los mod puedan banear horas, días, meses»): un mes = 30 días justos
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "meses": 3, "motivo": "Trampas"})
b = P.baneo_vigente(CTRL, "gunbound")
ok(cod == 200 and b and 90 * 86400 - 60 < b["hasta"] - time.time() <= 90 * 86400,
   f"el moderador banea 3 MESES en su juego: vence en 90 días ({cod})")
callado(CO.accion, P, MOD, {"accion": "desbanear", "uid": CTRL, "juegos": ["gunbound"]})
tope_m = tope_d // 30 + 1
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "meses": tope_m, "motivo": "x"})
ok(cod == 403 and P.permitido(CTRL, "gunbound"), f"⟲ {tope_m} meses (más del tope): 403 ({cod})")
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": JEFA, "juegos": ["gunbound"], "horas": 1, "motivo": "x"})
ok(cod == 403, f"⟲ a una cuenta del equipo: 403 ({cod})")
cod, d = callado(CO.accion, P, VIEJO, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "horas": 1, "motivo": "x"})
ok(cod == 403, f"⟲ el moderador SIN lista (formato viejo) sigue sin banear ({cod})")

print("7 · la ADMIN: toda la red y permanente")
cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": CTRL, "red": True, "permanente": True, "motivo": "Fraude"})
red = set(P.pases_de_la_red())
ok(cod == 200 and red >= {"r2beat2013", "r2beat2013-prueba", "gunbound", "gunbound-prueba", "eda", "r2beat-moderno"}
   and all(P.baneo_vigente(CTRL, x) and not P.permitido(CTRL, x) for x in red), f"toda la red, permanente: baneada en {len(red)} servidores ({cod})")
ok(P.permitido(CTRL, "parches") and P.permitido(CTRL, "web"), "⟲ «toda la red» son los JUEGOS: parches y web no se tocan")
cod, d = callado(CO.accion, P, JEFA, {"accion": "desbanear", "uid": CTRL, "red": True})
ok(cod == 200 and not any(P.baneo_vigente(CTRL, x) for x in red) and P.permitido(CTRL, "r2beat2013"), f"⟲ y desbanear toda la red la deja entrar de nuevo ({cod})")

print("8 · el motivo y la duración")
cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": CTRL, "juegos": ["eda"], "horas": 1, "motivo": "   "})
ok(cod == 400, f"⟲ sin motivo: 400 ({cod})")
cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": CTRL, "juegos": ["eda"], "horas": 1, "motivo": "m" * 201})
ok(cod == 400, f"⟲ 201 caracteres: 400 ({cod})")
cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": CTRL, "juegos": ["eda"], "horas": 1, "dias": 1, "motivo": "x"})
ok(cod == 400, f"⟲ horas Y días: 400 ({cod})")
cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": CTRL, "juegos": ["eda"], "dias": 1, "meses": 1, "motivo": "x"})
ok(cod == 400, f"⟲ días Y meses: 400 ({cod})")
for malo in (0, "2.5", "x"):
    cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": CTRL, "juegos": ["eda"], "meses": malo, "motivo": "x"})
    ok(cod == 400, f"⟲ meses = {malo!r}: 400 ({cod})")
for malo in (0, -1, "1.5", True, "abc"):
    cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": CTRL, "juegos": ["eda"], "horas": malo, "motivo": "x"})
    ok(cod == 400, f"⟲ horas = {malo!r}: 400 ({cod})")
cod, d = callado(CO.accion, P, JEFA, {"accion": "banear", "uid": CTRL, "juegos": ["eda"], "horas": "6", "motivo": "m" * 200})
ok(cod == 200 and P.baneo_vigente(CTRL, "eda")["motivo"] == "m" * 200, f"200 caracteres justos y «6» horas: sí ({cod})")

print("9 · la lista de los vigentes")
callado(P.admin_banear, JEFA, J, ["r2beat2013-prueba"], "ya vencido", {"horas": 1}, ahora=T - 7200)
cod, d = CO.baneos(P, JEFA)
claves = {(b["uid"], b["pase"]) for b in d["baneos"]}
ok(cod == 200 and (CTRL, "eda") in claves and (UID["vieja"], "r2beat2013") in claves and (OTRA, "gunbound") in claves
   and (J, "gunbound") in claves,
   "trae los vigentes (con fecha y el permanente viejo)")
ok((J, "r2beat2013-prueba") not in claves and (CTRL, "gunbound") not in claves and (CTRL, "r2beat2013") not in claves,
   "⟲ no trae los vencidos ni los levantados")
b = next(x for x in d["baneos"] if (x["uid"], x["pase"]) == (CTRL, "eda"))
ok(b["restante_seg"] and 6 * 3600 - 60 < b["restante_seg"] <= 6 * 3600 and b["hasta"] and b.get("usuario") == "control",
   "cada uno con hasta y restante_seg (y, a la admin, el login)")
cod, d = CO.baneos(P, MOD)
ok(cod == 200 and d["baneos"] and all(x["juego"] == "gunbound" for x in d["baneos"])
   and all("usuario" not in x for x in d["baneos"]), "⟲ a la moderadora: sólo los de GunBound, sin logins")

print("10 · la frase del tiempo")
casos = {2 * 86400 + 3 * 3600: "2 días y 3 horas", 45 * 60: "45 minutos", 44 * 60 + 1: "45 minutos", 1: "1 minuto",
         3600: "1 hora", 86400: "1 día", 86400 + 3600 + 59 * 60: "1 día y 1 hora", 5 * 3600 + 12 * 60: "5 horas y 12 minutos",
         90 * 86400: "3 meses", 30 * 86400: "1 mes", 70 * 86400: "2 meses y 10 días", 90 * 86400 - 5: "3 meses",
         45 * 86400: "45 días", 59 * 86400 + 3600: "59 días y 1 hora", 365 * 86400: "12 meses y 5 días"}
for seg, esperado in casos.items():
    ok(P.texto_restante(seg) == esperado, f"{seg} s -> «{P.texto_restante(seg)}» (esperado «{esperado}»)")
ok(P.texto_restante(None) is None, "⟲ permanente: sin frase de tiempo")

print("11 · el tope del moderador se AJUSTA (R2_BANEO_TOPE_MODERADOR_DIAS)")
viejo = os.environ.pop("R2_BANEO_TOPE_MODERADOR_DIAS", None)
ok(P._tope_moderador_dias() == 365, f"de fábrica: 365 días = 12 meses ({P._tope_moderador_dias()})")
for dado, esperado in (("90", 90), ("1", 1), ("0", 1), ("99999", 3650), ("abc", 365), ("-5", 365), ("", 365)):
    os.environ["R2_BANEO_TOPE_MODERADOR_DIAS"] = dado
    ok(P._tope_moderador_dias() == esperado, f"{dado!r} -> {P._tope_moderador_dias()} días (esperado {esperado})")
os.environ.pop("R2_BANEO_TOPE_MODERADOR_DIAS", None)
if viejo is not None:
    os.environ["R2_BANEO_TOPE_MODERADOR_DIAS"] = viejo
tope_antes = P.BANEO_TOPE_MODERADOR_SEG
P.BANEO_TOPE_MODERADOR_SEG = 7 * 86400            # (lo que haría la variable en 7, al arrancar)
cod, d = callado(CO.accion, P, MOD, {"accion": "banear", "uid": CTRL, "juegos": ["gunbound"], "dias": 8, "motivo": "x"})
ok(cod == 403, f"⟲ con el tope en 7 días, 8 días: 403 ({cod})")
ok(CO.limites_sancion(P, MOD)["tope_seg"] == 7 * 86400 and CO.limites_sancion(P, JEFA)["tope_seg"] is None,
   "y el panel le avisa el tope nuevo al moderador")
P.BANEO_TOPE_MODERADOR_SEG = tope_antes

srv.shutdown()
P.cerrar_conexiones()
print()
print(("✘ %d FALLAS" % len(fallos)) if fallos else "✔ todo bien")
sys.exit(1 if fallos else 0)
