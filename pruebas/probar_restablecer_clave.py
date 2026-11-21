# -*- coding: utf-8 -*-
"""probar_restablecer_clave — ★ 20-nov-2026: el Admin restablece la contraseña de un jugador desde el Coordinador.

Benja: «quiero cambiar una contraseña de un jugador en el Coordinador». El server genera una provisoria al azar, se la
muestra una vez al Admin y cierra las sesiones del jugador. Cada chequeo con su CONTROL AL REVÉS (⟲).

    python pruebas/probar_restablecer_clave.py
"""
import contextlib
import io
import os
import shutil
import sqlite3
import sys
import tempfile

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


tmp = tempfile.mkdtemp(prefix="r2_restablecer_")
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
        "R2_CUENTAS_UID_DESDE": "10000000",
    })
    for k in ("R2_PANEL_SALUD", "R2_PRESENCIA", "R2_DISCORD_EVENTOS_WEBHOOK", "R2_JUEGOS_CATALOGO", "R2_UID_NUEVAS_DESDE"):
        os.environ.pop(k, None)
    from servidor import portero as P

    with contextlib.redirect_stdout(io.StringIO()):
        UID, TOK = {}, {}
        for i, u in enumerate(["jefa", "moderadora", "jugador", "otro"]):
            UID[u] = P.registrar(u, clave_txt=f"vieja-{u}", ip=f"10.2.0.{i}")[1]["uid"]
            TOK[u] = P.entrar(u, clave_txt=f"vieja-{u}", ip=f"10.2.0.{i}")[1]["sesion"]
    open(os.environ["R2_ADMIN_ARCHIVO"], "w", encoding="utf-8").write(f"{UID['jefa']}\n")
    open(os.environ["R2_MODERADOR_ARCHIVO"], "w", encoding="utf-8").write(f"{UID['moderadora']} r2beat2013\n")

    sesiones = lambda u: P._propia().execute("SELECT COUNT(*) FROM sesiones WHERE uid = ?", (UID[u],)).fetchone()[0]
    ok(sesiones("jugador") == 1, "el jugador tiene su sesión abierta")

    print("\n1 · el Admin restablece")
    cod, d = P.admin_restablecer_clave(UID["jefa"], UID["jugador"])
    ok(cod == 200 and d.get("usuario") == "jugador" and len(d.get("clave", "")) == 10, "200, con el usuario y una provisoria de 10")
    prov = d.get("clave", "")
    ok(set(prov) <= set(P._LETRAS_PROVISORIA), "sin letras que se confunden al dictarlas (l, 1, i, o, 0)")
    with contextlib.redirect_stdout(io.StringIO()):
        c_nueva = P.entrar("jugador", clave_txt=prov, ip="10.2.9.1")[0]
        c_vieja = P.entrar("jugador", clave_txt="vieja-jugador", ip="10.2.9.2")[0]
    ok(c_nueva == 200, "el jugador entra con la provisoria")
    ok(c_vieja == 401, "⟲ la vieja ya no entra")
    ok(sesiones("jugador") == 1, "las sesiones de antes se cerraron (queda sólo la de recién)")
    ok(not P.sesion_de(TOK["jugador"]), "⟲ el token viejo ya no sirve")
    otra = P.admin_restablecer_clave(UID["jefa"], UID["jugador"])[1].get("clave")
    ok(otra and otra != prov, "otra vez: OTRA provisoria (al azar)")

    print("\n2 · la auditoría")
    filas = P._propia().execute("SELECT quien, accion, uid, detalle FROM auditoria WHERE accion = 'restablecer-clave'").fetchall()
    ok(len(filas) == 2 and all(f[2] == UID["jugador"] for f in filas), "quedó en la auditoría: quién, a quién")
    texto = " ".join(str(x) for f in filas for x in f)
    ok(prov not in texto and otra not in texto, "⟲ y la contraseña NO está en la auditoría")

    print("\n3 · quién NO puede")
    antes = P._cuentas().execute("SELECT clave FROM cuentas WHERE uid = ?", (UID["otro"],)).fetchone()[0]
    with contextlib.redirect_stdout(io.StringIO()):
        c_mod = P.admin_restablecer_clave(UID["moderadora"], UID["otro"])[0]
        c_jug = P.admin_restablecer_clave(UID["jugador"], UID["otro"])[0]
        c_otro = P.entrar("otro", clave_txt="vieja-otro", ip="10.2.9.3")[0]
    despues = P._cuentas().execute("SELECT clave FROM cuentas WHERE uid = ?", (UID["otro"],)).fetchone()[0]
    ok(c_mod == 403, "⟲ una moderadora: 403")
    ok(c_jug == 403, "⟲ un jugador: 403")
    ok(antes == despues, "⟲ y la contraseña del otro quedó intacta")
    ok(c_otro == 200, "⟲ el otro sigue entrando con la suya")
    ok(P.admin_restablecer_clave(UID["jefa"], 99999999)[0] == 404, "una cuenta que no existe: 404")
    ok(P.admin_restablecer_clave(UID["jefa"], "x")[0] == 400, "sin cuenta válida: 400")

    print("\n4 · ★ 21-nov: el permiso ASIGNABLE a un moderador (toda la red)")
    from servidor import gestion as GE, coordinador as CO
    ok(not GE.puede_red(P, UID["moderadora"], "clave"), "⟲ sin asignar: la moderadora no puede")
    cod, _ = GE.poner_permisos(CO, P, UID["moderadora"], {"uid": UID["moderadora"], "juego": GE.RED, "acciones": ["clave"]})
    ok(cod == 403, "⟲ una moderadora no se lo asigna a sí misma (403)")
    cod, _ = GE.poner_permisos(CO, P, UID["jefa"], {"uid": UID["moderadora"], "juego": GE.RED, "acciones": ["rcoin"]})
    ok(cod == 400, "⟲ en toda la red sólo se asigna lo de la red (rcoin: 400)")
    cod, d = GE.poner_permisos(CO, P, UID["jefa"], {"uid": UID["moderadora"], "juego": GE.RED, "acciones": ["clave"]})
    ok(cod == 200 and GE.puede_red(P, UID["moderadora"], "clave"), "la Admin se lo asigna: ahora puede")
    ok(any(x["juego"] == GE.RED and x["acciones"] == ["clave"] for x in d["permisos"]) and d["asignables_red"][0]["id"] == "clave",
       "el panel lo ve (fila de toda la red y su casilla)")
    cod, d = P.admin_restablecer_clave(UID["moderadora"], UID["jugador"])
    ok(cod == 200 and len(d.get("clave", "")) == 10, "la moderadora restablece la de un jugador")
    ok("usuario" not in d, "⟲ y NO recibe el login del jugador (es privado)")
    with contextlib.redirect_stdout(io.StringIO()):
        c_entra = P.entrar("jugador", clave_txt=d.get("clave", ""), ip="10.2.9.7")[0]
    ok(c_entra == 200, "el jugador entra con la provisoria")
    antes = P._cuentas().execute("SELECT clave FROM cuentas WHERE uid = ?", (UID["jefa"],)).fetchone()[0]
    ok(P.admin_restablecer_clave(UID["moderadora"], UID["jefa"])[0] == 403, "⟲ a una cuenta del EQUIPO (la Admin): 403")
    ok(P.admin_restablecer_clave(UID["moderadora"], UID["moderadora"])[0] == 403, "⟲ ni a sí misma (es del equipo): 403")
    ok(antes == P._cuentas().execute("SELECT clave FROM cuentas WHERE uid = ?", (UID["jefa"],)).fetchone()[0], "⟲ la de la Admin quedó intacta")
    ok(P._propia().execute("SELECT COUNT(*) FROM auditoria WHERE accion = 'restablecer-clave' AND detalle LIKE '%moderador%'").fetchone()[0] == 1,
       "queda en la auditoría como de moderador")
    GE.poner_permisos(CO, P, UID["jefa"], {"uid": UID["moderadora"], "juego": GE.RED, "acciones": []})
    ok(P.admin_restablecer_clave(UID["moderadora"], UID["jugador"])[0] == 403, "⟲ se lo quitan: ya no puede")
finally:
    try:
        P.cerrar_conexiones()
    except Exception:                                                    # noqa: BLE001
        pass
    shutil.rmtree(tmp, ignore_errors=True)
print("\n✔ todo bien" if not mal else f"\n✘ {mal} mal")
sys.exit(1 if mal else 0)
