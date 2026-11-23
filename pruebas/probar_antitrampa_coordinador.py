# -*- coding: utf-8 -*-
"""probar_antitrampa_coordinador — el antitrampa AVISA y el Coordinador BANEA (23-nov-2026).

Levanta el portero real (HTTP, `R2_CUENTAS_DUENA=1`, `R2_CUENTAS_FICHA_INTERNA`, bases temporales). Cada regla con su
CONTROL AL REVÉS (⟲):
  · ficha interna: sin X-R2 -> 403 · sin ficha / ficha mala -> 401 · sin variable -> 404 ⟲ con ficha -> 200
  · validación: cuenta inexistente -> 404 · uid inválido -> 400 · juego desconocido -> 400 · regla con mayúsculas o
    > 40 -> 400 ⟲ regla de 40 caracteres `[a-z0-9_]` válida y recorte de detalle/nick sin controles -> 200
  · escalera (`R2_ANTITRAMPA_BANEO_EN=3`): 1.ª = expulsado (sin ban) · 2.ª = advertencia (sin ban) · 3.ª = baneo
    permanente en `baneos` SÓLO en ese juego (`quien="antitrampa"`) ⟲ en otro juego y en otra cuenta no hay ban
  · panel y auditoría: `antitrampa_faltas` en la ficha de la persona (sólo si > 0), `baneos` y `auditoria` muestran
    `antitrampa` (también al moderador de ese juego)
  · desbanear borra las faltas (`admin_desbanear` y consola): `faltas` vuelve a 0 y la siguiente falta vuelve a ser 1.ª
  · `R2_ANTITRAMPA_BANEO_EN=0` -> nunca banea (aunque pase de 3 faltas)
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


tmp = tempfile.mkdtemp(prefix="antitrampa_coord_")
srv = None
try:
    os.makedirs(os.path.join(tmp, "config"))
    with open(os.path.join(tmp, "config", "lanzamientos.json"), "w", encoding="utf-8") as f:
        json.dump({
            "eda": {"desde": "2020-01-01T00:00:00-05:00"},
            "gunbound": {"desde": "2020-01-01T00:00:00-05:00"},
            "r2beat-moderno": {"desde": "2020-01-01T00:00:00-05:00"},
        }, f)

    FICHA = "ficha-antitrampa-prueba-2026"
    os.environ.update({
        "R2_CUENTAS_DUENA": "1",
        "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
        "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"),
        "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
        "R2_BASE": os.path.join(tmp, "no_existe_datos.db"),
        "R2_ADMIN_ARCHIVO": os.path.join(tmp, "config", "admin.txt"),
        "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "config", "moderadores.txt"),
        "R2_CUENTAS_FICHA_INTERNA": FICHA,
        "R2_CUENTAS_UID_DESDE": "10000000",
    })
    for k in ("R2_ANTITRAMPA_BANEO_EN", "R2_PANEL_SALUD", "R2_PRESENCIA", "R2_DISCORD_EVENTOS_WEBHOOK",
              "R2_JUEGOS_CATALOGO", "R2_UID_NUEVAS_DESDE"):
        os.environ.pop(k, None)

    from servidor import portero as pt          # noqa: E402
    from servidor import coordinador as CO      # noqa: E402

    with contextlib.redirect_stdout(io.StringIO()):
        UID, TOK = {}, {}
        for i, u in enumerate(["jefa", "modr2", "tramposo", "otro", "sinban", "borde"]):
            UID[u] = pt.registrar(u, clave_txt=f"clave-{u}", ip=f"10.1.0.{i}")[1]["uid"]
            TOK[u] = pt.entrar(u, clave_txt=f"clave-{u}", ip=f"10.1.0.{i}")[1]["sesion"]
    with open(os.environ["R2_ADMIN_ARCHIVO"], "w", encoding="utf-8") as f:
        f.write(f"{UID['jefa']}\n")
    with open(os.environ["R2_MODERADOR_ARCHIVO"], "w", encoding="utf-8") as f:
        f.write(f"{UID['modr2']} r2beat2013\n")
    JEFA, MODR2 = UID["jefa"], UID["modr2"]

    with contextlib.redirect_stdout(io.StringIO()):
        srv = pt.servidor(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    URL = f"http://127.0.0.1:{srv.server_address[1]}"

    def pedir(ruta, cuerpo, ficha=FICHA, x_r2=True, via_header=False):
        h = {"Content-Type": "application/json"}
        if x_r2:
            h["X-R2"] = "1"
        if ficha is not None:
            if via_header:
                h["X-Ficha-Interna"] = ficha
            else:
                h["Authorization"] = "Bearer " + ficha
        req = urllib.request.Request(
            URL + ruta, data=json.dumps(cuerpo).encode("utf-8"), headers=h, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    base_ok = {
        "enenos_id": UID["tramposo"],
        "juego": "r2beat2013-prueba",
        "regla": "juego_automatico",
        "detalle": "gancho automatico en 0x005080B5",
        "nick": "Tramposo1",
    }

    print("1 · autenticación y cabeceras de POST /cuentas/interno/antitrampa")
    ok(pedir("/cuentas/interno/antitrampa", base_ok, x_r2=False)[0] == 403,
       "⟲ sin X-R2 da 403")
    ok(pedir("/cuentas/interno/antitrampa", base_ok, ficha=None)[0] == 401,
       "⟲ sin ficha da 401")
    ok(pedir("/cuentas/interno/antitrampa", base_ok, ficha="ficha-equivocada")[0] == 401,
       "⟲ con ficha mala da 401")
    os.environ.pop("R2_CUENTAS_FICHA_INTERNA", None)
    try:
        ok(pedir("/cuentas/interno/antitrampa", base_ok, ficha=FICHA)[0] == 404,
           "⟲ sin R2_CUENTAS_FICHA_INTERNA la ruta no existe (404)")
    finally:
        os.environ["R2_CUENTAS_FICHA_INTERNA"] = FICHA

    print("2 · validación de campos")
    cod_ne, d_ne = pedir("/cuentas/interno/antitrampa", {**base_ok, "enenos_id": 99999999})
    ok(cod_ne == 404 and d_ne.get("error") == "Esa cuenta no existe.",
       f"⟲ cuenta inexistente da 404 ({cod_ne} {d_ne})")
    for malo in (0, -7, True, False, 1.5, "no_num", None):
        ok(pedir("/cuentas/interno/antitrampa", {**base_ok, "enenos_id": malo})[0] == 400,
           f"⟲ enenos_id inválido ({malo!r}) da 400")
    ok(pedir("/cuentas/interno/antitrampa", {**base_ok, "juego": "juego_inventado"})[0] == 400,
       "⟲ juego desconocido da 400")
    for regla_mala in ("", "Juego_Automatico", "A", "a" * 41, "juego-auto", "juego auto", "regla\n"):
        ok(pedir("/cuentas/interno/antitrampa", {**base_ok, "regla": regla_mala})[0] == 400,
           f"⟲ regla inválida ({regla_mala!r}) da 400")
    regla_40 = "a" * 40
    cod_b, d_b = pedir("/cuentas/interno/antitrampa", {
        "enenos_id": UID["borde"],
        "juego": "r2beat2013",
        "regla": regla_40,
        "detalle": "x\x00\n\r" + "d" * 250,
        "nick": "N\x00\n" + "k" * 40,
    }, via_header=True)
    ok(cod_b == 200 and d_b == {"ok": True, "faltas": 1, "escalon": "expulsado", "baneada": False},
       f"regla de 40 chars [a-z0-9_] + X-Ficha-Interna y detalle/nick recortados sin controles -> 200 ({d_b})")
    aud_b = pt._propia().execute(
        "SELECT detalle FROM auditoria WHERE uid = ? AND accion = 'antitrampa · falta' ORDER BY id DESC LIMIT 1",
        (UID["borde"],),
    ).fetchone()
    ok(aud_b is not None and "\x00" not in aud_b["detalle"] and "\n" not in aud_b["detalle"],
       "los caracteres de control no entran en la auditoría")

    print("3 · escalera (1.ª expulsado · 2.ª advertencia · 3.ª baneo permanente sólo en ese juego)")
    c1, d1 = pedir("/cuentas/interno/antitrampa", base_ok)
    ok(c1 == 200 and d1 == {"ok": True, "faltas": 1, "escalon": "expulsado", "baneada": False}
       and pt.baneo_vigente(UID["tramposo"], "r2beat2013-prueba") is None,
       f"1.ª falta -> expulsado, sin baneo ({d1})")
    c2, d2 = pedir("/cuentas/interno/antitrampa", base_ok)
    ok(c2 == 200 and d2 == {"ok": True, "faltas": 2, "escalon": "advertencia", "baneada": False}
       and pt.baneo_vigente(UID["tramposo"], "r2beat2013-prueba") is None,
       f"2.ª falta -> advertencia, sin baneo ({d2})")

    # En la ficha de la persona (panel): aparece antitrampa_faltas=2 sólo en r2beat2013-prueba
    _, per2 = CO.persona(pt, JEFA, UID["tramposo"])
    pases_r2 = {x["pase"]: x for j in per2["persona"]["juegos"] if j["id"] == "r2beat2013" for x in j["pases"]}
    ok(pases_r2["r2beat2013-prueba"].get("antitrampa_faltas") == 2
       and "antitrampa_faltas" not in pases_r2["r2beat2013"],
       "en la ficha del panel sale antitrampa_faltas=2 en ese servidor y no en el otro")

    # 3.ª falta (también probando la ruta sin el prefijo /cuentas)
    c3, d3 = pedir("/interno/antitrampa", base_ok)
    ok(c3 == 200 and d3 == {"ok": True, "faltas": 3, "escalon": "baneo", "baneada": True},
       f"3.ª falta (sin prefijo /cuentas) -> baneo ({d3})")
    ban = pt.baneo_vigente(UID["tramposo"], "r2beat2013-prueba")
    ok(ban is not None and ban["quien"] == "antitrampa" and ban["hasta"] is None
       and ban["motivo"] == "Antitrampa: juego_automatico (3.ª falta)",
       f"baneo_vigente en r2beat2013-prueba: permanente, quien=antitrampa, motivo exacto ({dict(ban) if ban else None})")
    ok(pt.baneo_vigente(UID["tramposo"], "r2beat2013") is None
       and pt.baneo_vigente(UID["tramposo"], "gunbound") is None,
       "⟲ en otro juego (r2beat2013, gunbound) NO queda baneado")
    ok(pt.baneo_vigente(UID["otro"], "r2beat2013-prueba") is None,
       "⟲ otra cuenta NO queda baneada")
    cp_ban, dp_ban = pt.pedir_pase(TOK["tramposo"], "r2beat2013-prueba")
    cp_ok, _ = pt.pedir_pase(TOK["tramposo"], "r2beat2013")
    ok(cp_ban == 403 and dp_ban.get("error") == "baneado" and cp_ok == 200,
       "pedir_pase niega en r2beat2013-prueba con error='baneado' ⟲ en r2beat2013 sigue entrando")

    # Auditoría y panel (admin + moderador)
    aud_filas = pt._propia().execute(
        "SELECT quien, accion, juego, detalle FROM auditoria WHERE uid = ? ORDER BY id",
        (UID["tramposo"],),
    ).fetchall()
    acciones_aud = [r["accion"] for r in aud_filas]
    ok(acciones_aud.count("antitrampa · falta") == 3 and acciones_aud.count("antitrampa · baneo") == 1
       and all(r["quien"] == "antitrampa" and r["juego"] == "r2beat2013-prueba" for r in aud_filas),
       f"auditoría tiene 3 «antitrampa · falta» y 1 «antitrampa · baneo» con quien='antitrampa' ({acciones_aud})")
    _, bans_adm = CO.baneos(pt, JEFA)
    _, bans_mod = CO.baneos(pt, MODR2)
    b_adm = next((b for b in bans_adm["baneos"] if b["uid"] == UID["tramposo"] and b["pase"] == "r2beat2013-prueba"), None)
    b_mod = next((b for b in bans_mod["baneos"] if b["uid"] == UID["tramposo"] and b["pase"] == "r2beat2013-prueba"), None)
    ok(b_adm is not None and b_adm["quien"] == "antitrampa" and b_adm.get("antitrampa_faltas") == 3
       and b_mod is not None and b_mod["quien"] == "antitrampa",
       "el baneo del antitrampa aparece en CO.baneos (admin y moderador) con quien='antitrampa'")
    _, aud_mod = CO.auditoria(pt, MODR2)
    ok(any(a["accion"] == "antitrampa · baneo" and a["quien"] == "antitrampa" for a in aud_mod["auditoria"]),
       "el moderador de ese juego ve el evento de antitrampa en su auditoría")

    print("4 · desbanear borra las faltas (admin_desbanear y consola)")
    with contextlib.redirect_stdout(io.StringIO()):
        cd, dd = pt.admin_desbanear(JEFA, UID["tramposo"], ["r2beat2013-prueba"])
    ok(cd == 200 and dd.get("levantados") == ["r2beat2013-prueba"]
       and pt.baneo_vigente(UID["tramposo"], "r2beat2013-prueba") is None,
       "admin_desbanear levanta el baneo del antitrampa")
    f_post = pt._propia().execute(
        "SELECT faltas FROM antitrampa_faltas WHERE uid = ? AND juego = 'r2beat2013-prueba'",
        (UID["tramposo"],),
    ).fetchone()
    ok(f_post is not None and int(f_post["faltas"]) == 0,
       "admin_desbanear deja antitrampa_faltas.faltas en 0")
    _, per_post = CO.persona(pt, JEFA, UID["tramposo"])
    pases_post = {x["pase"]: x for j in per_post["persona"]["juegos"] if j["id"] == "r2beat2013" for x in j["pases"]}
    ok("antitrampa_faltas" not in pases_post["r2beat2013-prueba"],
       "⟲ tras desbanear, la ficha ya no muestra faltas de antitrampa")
    c_re1, d_re1 = pedir("/cuentas/interno/antitrampa", base_ok)
    ok(c_re1 == 200 and d_re1 == {"ok": True, "faltas": 1, "escalon": "expulsado", "baneada": False}
       and pt.baneo_vigente(UID["tramposo"], "r2beat2013-prueba") is None,
       f"la siguiente detección después de desbanear vuelve a ser 1.ª ({d_re1})")

    # Subir hasta 3.ª de nuevo y desbanear por consola
    pedir("/cuentas/interno/antitrampa", base_ok)
    c_re3, d_re3 = pedir("/cuentas/interno/antitrampa", base_ok)
    ok(c_re3 == 200 and d_re3["baneada"] is True and pt.baneo_vigente(UID["tramposo"], "r2beat2013-prueba") is not None,
       "vuelve a banear al llegar a 3.ª")
    with contextlib.redirect_stdout(io.StringIO()):
        pt.consola(["desbanear", "tramposo", "r2beat2013-prueba"])
    f_cons = pt._propia().execute(
        "SELECT faltas FROM antitrampa_faltas WHERE uid = ? AND juego = 'r2beat2013-prueba'",
        (UID["tramposo"],),
    ).fetchone()
    ok(pt.baneo_vigente(UID["tramposo"], "r2beat2013-prueba") is None
       and f_cons is not None and int(f_cons["faltas"]) == 0,
       "desbanear por consola también levanta el baneo y deja las faltas en 0")

    print("5 · R2_ANTITRAMPA_BANEO_EN=0 -> nunca banea")
    os.environ["R2_ANTITRAMPA_BANEO_EN"] = "0"
    try:
        res_0 = [pedir("/cuentas/interno/antitrampa", {
            "enenos_id": UID["sinban"],
            "juego": "r2beat2013",
            "regla": "modulo_prohibido",
            "detalle": "toolbit.dll",
            "nick": "SinBan",
        }) for _ in range(5)]
    finally:
        os.environ.pop("R2_ANTITRAMPA_BANEO_EN", None)
    ok(all(c == 200 and d == {"ok": True, "faltas": i + 1, "escalon": "expulsado", "baneada": False}
           for i, (c, d) in enumerate(res_0)),
       f"con R2_ANTITRAMPA_BANEO_EN=0, 5 faltas seguidas son siempre 'expulsado' y baneada=False ({res_0})")
    ok(pt.baneo_vigente(UID["sinban"], "r2beat2013") is None,
       "⟲ y nunca escribe un baneo en baneos")
    n_ban_aud = pt._propia().execute(
        "SELECT COUNT(*) FROM auditoria WHERE uid = ? AND accion = 'antitrampa · baneo'",
        (UID["sinban"],),
    ).fetchone()[0]
    ok(n_ban_aud == 0, "⟲ ni registra 'antitrampa · baneo' en la auditoría")
finally:
    if srv is not None:
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:                                        # noqa: BLE001
            pass
    try:
        from servidor import portero as _p
        _p.cerrar_conexiones()
    except Exception:                                            # noqa: BLE001
        pass
    shutil.rmtree(tmp, ignore_errors=True)

print()
if fallos:
    print(f"✘ {len(fallos)} FALLAS")
    sys.exit(1)
print("✔ antitrampa en Coordinador: todo bien")
