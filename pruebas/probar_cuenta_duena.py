# -*- coding: utf-8 -*-
"""probar_cuenta_duena — Cuenta Eñeños como DUEÑA de las cuentas (R2_CUENTAS_DUENA=1). 15-nov-2026.

Arma una `datos.db` de formato viejo en una carpeta temporal, importa las cuentas a `cuentas.db`, borra toda referencia
a `datos.db` y prueba el servicio en modo dueño (`R2_CUENTAS_DUENA=1`). Cada chequeo con su CONTROL AL REVÉS (⟲):

  · `importar` abre la `datos.db` vieja en SÓLO LECTURA (mismo md5), copia `uid`, `usuario`, `estado` (`BANNED:` /
    `FUSIONADA:`) y envuelve el SHA-256 en `scrypt` sin imprimir hashes ⟲ correrlo dos veces no duplica;
  · en el archivo `cuentas.db` NO aparece el SHA-256 de ninguna contraseña ⟲ en `datos.db` vieja sí aparece;
  · con `R2_CUENTAS_DUENA=1` nunca se abre `datos.db` (anda sin archivo) ⟲ `_juego()` rehúsa abrirse;
  · `entrar` valida contra `cuentas.db`, distingue `Junior` de `junior`, y rechaza baneadas y fusionadas ⟲ claves
    cruzadas o malas dan 401;
  · `registrar` da `uid >= UID_NUEVAS_DESDE` y mayor que el máximo existente ⟲ rechaza usuarios repetidos o mal
    formados y frena por IP;
  · `cambiar-clave` (jugador y consola) reemplaza la clave envuelta ⟲ la vieja deja de servir y con la actual mal no
    cambia; `banear` / `desbanear` por consola suspende y reactiva la cuenta en `cuentas.db`;
  · `pase` sale para cualquier cuenta activa en `r2beat2013`, `parches` y `web`, sin incluir el `usuario` ⟲ `eda`
    sigue pidiendo aprobación y un `aud` inexistente da 404;
  · el pedido interno `GET /cuentas/interno/cuenta/<uid>` devuelve `{uid, usuario, estado}` con la ficha correcta ⟲ sin
    ficha o con otra da 401, y sin `R2_CUENTAS_FICHA_INTERNA` no existe (404).
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

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest().upper()


def md5(p):
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def bytes_base(ruta):
    trozos = []
    for suf in ("", "-wal", "-shm"):
        p = ruta + suf
        if os.path.isfile(p):
            with open(p, "rb") as f:
                trozos.append(f.read())
    return b"".join(trozos)


tmp = tempfile.mkdtemp(prefix="cuenta_duena_")
srv = None
try:
    base_vieja = os.path.join(tmp, "datos_vieja.db")
    claves_iniciales = {
        "Junior": "clave_mayus_1",
        "junior": "clave_minus_2",
        "baneada": "clave_ban_3",
        "fusion": "clave_fus_4",
        "jefe": "clave_jefe_5",
        "veterana": "clave_vet_6",
        "negativa": "clave_neg_7",
    }
    c = sqlite3.connect(base_vieja)
    c.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, username TEXT UNIQUE, pass_hash TEXT, reg_time TEXT)")
    c.executemany("INSERT INTO users VALUES (?, ?, ?, ?)", [
        (101, "Junior", sha(claves_iniciales["Junior"]), "2025-01-10 12:00:00"),
        (102, "junior", sha(claves_iniciales["junior"]), "2025-01-11 12:00:00"),
        (103, "baneada", "BANNED:" + sha(claves_iniciales["baneada"]), "2025-02-01 00:00:00"),
        (104, "fusion", "FUSIONADA:" + sha(claves_iniciales["fusion"]), "2025-02-02 00:00:00"),
        (105, "jefe", sha(claves_iniciales["jefe"]), "2025-01-01 00:00:00"),
        (500, "veterana", sha(claves_iniciales["veterana"]), "2024-12-01 00:00:00"),
        (-77, "negativa", "FUSIONADA:" + sha(claves_iniciales["negativa"]), "2024-11-01 00:00:00"),
    ])
    c.commit()
    c.close()
    md5_vieja = md5(base_vieja)

    ruta_cuentas = os.path.join(tmp, "cuentas.db")
    ruta_portero = os.path.join(tmp, "portero.db")
    ruta_no_existe = os.path.join(tmp, "no_existe_datos.db")
    admin_txt = os.path.join(tmp, "admin.txt")
    with open(admin_txt, "w", encoding="utf-8") as f:
        f.write("# admins\njefe\n")

    FICHA = "ficha-interna-secreta-2026"
    os.environ.update(
        R2_CUENTAS_DUENA="1",
        R2_BASE=ruta_no_existe,
        R2_PORTERO_BASE=ruta_portero,
        R2_CUENTAS_BASE=ruta_cuentas,
        R2_PORTERO_CLAVE=os.path.join(tmp, "portero_clave.json"),
        R2_ADMIN_ARCHIVO=admin_txt,
        R2_MODERADOR_ARCHIVO=os.path.join(tmp, "moderadores.txt"),
        R2_CUENTAS_FICHA_INTERNA=FICHA,
    )
    os.environ.pop("R2_PORTERO_MANIFIESTOS", None)
    os.environ.pop("R2_CUENTAS_UID_DESDE", None)
    os.environ.pop("R2_UID_NUEVAS_DESDE", None)

    from servidor import portero as pt

    print("1 · importar desde una datos.db vieja (Eñeños ID secuencial, traducción en portero.db, CSV)")
    # Sembrar en portero.db aprobados, baneos, sesiones, pases y auditoria históricos con uid_viejo antes de importar:
    with pt._escribir:
        cp_init = pt._propia()
        cp_init.execute("INSERT INTO aprobados VALUES (101, 'eda', '2026-11-01', 'viejo', 'ok')")
        cp_init.execute("INSERT INTO baneos (uid, juego, desde, quien, motivo) VALUES (102, 'eda', '2026-11-02', 'viejo', 'prueba')")
        cp_init.execute("INSERT INTO sesiones VALUES ('huella_vieja_101', 101, 1000, 9999999999, '1.2.3.4')")
        cp_init.execute("INSERT INTO pases VALUES ('jti_viejo_101', 101, 'eda', 1000, '1.2.3.4')")
        cp_init.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) "
                        "VALUES ('2026-11-01', 'viejo', 'aprobar', 101, 'eda', 'hist')")
        cp_init.commit()

    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        res1 = pt.consola(["importar", base_vieja])
    txt_imp = salida.getvalue()
    ok(res1 == {"copiadas": 7, "ya_estaban": 0, "baneadas": 1, "fusionadas": 2, "traducidos": 2}
       and "7 copiada(s)" in txt_imp and "1 baneada(s)" in txt_imp and "2 fusionada(s)" in txt_imp,
       "importar copia las 7 cuentas (incluido uid negativo) asignando Eñeños IDs secuenciales y traduce portero.db")
    filas_cuentas = pt._cuentas().execute("SELECT uid, usuario, estado FROM cuentas ORDER BY uid").fetchall()
    eids_por_usuario = {r["usuario"]: int(r["uid"]) for r in filas_cuentas}
    ok(list(r["uid"] for r in filas_cuentas) == [pt.UID_NUEVAS_DESDE + i for i in range(7)],
       f"todas las cuentas importadas recibieron Eñeños ID secuencial desde {pt.UID_NUEVAS_DESDE}")
    ok(eids_por_usuario["negativa"] == pt.UID_NUEVAS_DESDE
       and eids_por_usuario["Junior"] == pt.UID_NUEVAS_DESDE + 1
       and eids_por_usuario["veterana"] == pt.UID_NUEVAS_DESDE + 6,
       "en el orden de la base vieja (ORDER BY rowid): el número negativo (-77) va primero, y el 500 último")
    mapa_imp = {int(r["uid_viejo"]): int(r["uid"])
                for r in pt._cuentas().execute("SELECT uid_viejo, uid FROM importadas").fetchall()}
    ok(mapa_imp == {101: eids_por_usuario["Junior"], 102: eids_por_usuario["junior"],
                    103: eids_por_usuario["baneada"], 104: eids_por_usuario["fusion"],
                    105: eids_por_usuario["jefe"], 500: eids_por_usuario["veterana"],
                    -77: eids_por_usuario["negativa"]},
       "tabla importadas guarda la traducción exacta uid_viejo -> Eñeños ID")
    cp_post = pt._propia()
    ok(cp_post.execute("SELECT uid FROM aprobados WHERE juego = 'eda'").fetchall()[0][0] == eids_por_usuario["Junior"]
       and cp_post.execute("SELECT uid FROM baneos WHERE juego = 'eda'").fetchall()[0][0] == eids_por_usuario["junior"]
       and cp_post.execute("SELECT COUNT(*) FROM sesiones").fetchone()[0] == 0
       and cp_post.execute("SELECT COUNT(*) FROM pases").fetchone()[0] == 0
       and cp_post.execute("SELECT uid FROM auditoria WHERE accion = 'aprobar'").fetchone()[0] == 101,
       "importar traduce aprobados/baneos al Eñeños ID, borra sesiones/pases viejos y deja auditoria histórica intacta")
    ok(all(sha(cl).lower() not in txt_imp.lower() and cl not in txt_imp for cl in claves_iniciales.values()),
       "⛔ importar NO imprime ningún hash ni contraseña")
    ok(md5(base_vieja) == md5_vieja, "datos.db vieja queda con el MISMO md5 (abierta en sólo lectura)")
    salida2 = io.StringIO()
    with contextlib.redirect_stdout(salida2):
        res2 = pt.consola(["importar", base_vieja])
    total_filas = pt._cuentas().execute("SELECT COUNT(*) FROM cuentas").fetchone()[0]
    ok(res2 == {"copiadas": 0, "ya_estaban": 7, "baneadas": 1, "fusionadas": 2, "traducidos": 0} and total_filas == 7,
       "⟲ correr importar dos veces NO duplica ni retraduce (0 copiadas, 7 ya estaban, 0 traducidos)")
    # Limpiar baneo traducido de prueba sobre junior para no afectar sección 7:
    with pt._escribir:
        cp_post.execute("DELETE FROM aprobados")
        cp_post.execute("DELETE FROM baneos")
        cp_post.commit()

    ruta_csv = os.path.join(tmp, "trad.csv")
    sal_csv = io.StringIO()
    with contextlib.redirect_stdout(sal_csv):
        pt.consola(["traduccion", ruta_csv])
    csv_txt = open(ruta_csv, encoding="utf-8").read()
    ok(csv_txt.startswith("uid_viejo,enenos_id\n")
       and f"101,{eids_por_usuario['Junior']}\n" in csv_txt
       and f"-77,{eids_por_usuario['negativa']}\n" in csv_txt
       and all(u not in csv_txt for u in claves_iniciales)
       and all(sha(cl).lower() not in csv_txt.lower() for cl in claves_iniciales.values()),
       "CLI `traduccion` exporta uid_viejo,enenos_id en CSV sin usuarios ni contraseñas")

    print("2 · contraseñas envueltas en scrypt (sin SHA-256 en cuentas.db)")
    pt._fallos.clear()      # (la sección anterior falló a propósito muchas veces: sin esto, el freno contesta 429 a todo)
    pt._cuentas().execute("PRAGMA wal_checkpoint(FULL)")
    crudo_cuentas = bytes_base(ruta_cuentas)
    crudo_vieja = bytes_base(base_vieja)
    ok(b"scrypt$" in crudo_cuentas, "cuentas.db guarda las claves con formato scrypt$")
    ok(all(sha(cl).encode("ascii") not in crudo_cuentas and sha(cl).lower().encode("ascii") not in crudo_cuentas
           for cl in claves_iniciales.values()),
       "⛔ en cuentas.db NO aparece el SHA-256 de ninguna cuenta")
    ok(all(sha(cl).encode("ascii") in crudo_vieja for cl in claves_iniciales.values()),
       "⟲ control: en la datos.db vieja SÍ estaban los SHA-256 en crudo")
    h_jr = sha(claves_iniciales["Junior"])
    e1, e2 = pt.envolver_hash(h_jr), pt.envolver_hash(h_jr)
    ok(e1 != e2 and pt.verificar_hash(h_jr, e1) and pt.verificar_hash(h_jr, e2),
       "cada cuenta lleva su propia sal aleatoria y verifica con hmac.compare_digest")
    ok(not pt.verificar_hash(sha("otra"), e1) and not pt.verificar_hash("no-hex", e1),
       "⟲ otro hash o un texto mal formado NO verifican")

    print("3 · con R2_CUENTAS_DUENA=1 la base del juego no se abre nunca")
    pt._fallos.clear()      # (la sección anterior falló a propósito muchas veces: sin esto, el freno contesta 429 a todo)
    ok(not os.path.exists(ruta_no_existe), "datos.db ni siquiera existe en disco")
    try:
        pt._juego()
        abrio_juego = True
    except RuntimeError:
        abrio_juego = False
    ok(not abrio_juego, "⟲ _juego() rehúsa abrir datos.db cuando R2_CUENTAS_DUENA=1")
    os.environ["R2_CUENTAS_DUENA"] = "0"
    try:
        pt.servidor(0)
        arranco_sin_datos = True
    except SystemExit:
        arranco_sin_datos = False
    finally:
        os.environ["R2_CUENTAS_DUENA"] = "1"
    ok(not arranco_sin_datos, "⟲ con el interruptor apagado, sin datos.db el servidor NO arranca")

    srv = pt.servidor(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    def pedir(metodo, ruta, cuerpo=None, token=None, x_r2=True, ip=None, cab_extra=None):
        h = {"Content-Type": "application/json"}
        if x_r2:
            h["X-R2"] = "1"
        if token:
            h["Authorization"] = "Bearer " + token
        if ip:
            h["X-Forwarded-For"] = ip
        if cab_extra:
            h.update(cab_extra)
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else (b"{}" if metodo == "POST" else None)
        req = urllib.request.Request(url + ruta, data=datos, headers=h, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    ok(pedir("GET", "/cuentas/salud") == (200, {"ok": True}),
       "con el interruptor prendido y sin datos.db, el servidor arranca y responde /salud")

    print("4 · entrar contra cuentas.db (Junior ≠ junior, baneada y fusionada)")
    pt._fallos.clear()      # (la sección anterior falló a propósito muchas veces: sin esto, el freno contesta 429 a todo)
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "Junior", "clave": claves_iniciales["Junior"]}, x_r2=False)[0] == 403,
       "⟲ entrar sin X-R2 da 403")
    eid_jr1 = eids_por_usuario["Junior"]
    eid_jr2 = eids_por_usuario["junior"]
    eid_ban = eids_por_usuario["baneada"]
    eid_vet = eids_por_usuario["veterana"]
    eid_jefe = eids_por_usuario["jefe"]

    c_jr1, d_jr1 = pedir("POST", "/cuentas/entrar", {"usuario": "Junior", "clave": claves_iniciales["Junior"]})
    c_jr2, d_jr2 = pedir("POST", "/cuentas/entrar", {"usuario": "junior", "clave": claves_iniciales["junior"]})
    ok(c_jr1 == 200 and d_jr1.get("uid") == eid_jr1 and c_jr2 == 200 and d_jr2.get("uid") == eid_jr2,
       f"Junior (eid {eid_jr1}) y junior (eid {eid_jr2}) son dos cuentas distintas y entran con su Eñeños ID")
    c_x1, d_x1 = pedir("POST", "/cuentas/entrar", {"usuario": "Junior", "clave": claves_iniciales["junior"]})
    c_x2, d_x2 = pedir("POST", "/cuentas/entrar", {"usuario": "junior", "clave": claves_iniciales["Junior"]})
    c_ne, d_ne = pedir("POST", "/cuentas/entrar", {"usuario": "no_existe", "clave": "cualquiera"})
    ok(c_x1 == 401 and c_x2 == 401 and c_ne == 401 and d_x1 == d_ne and d_x2 == d_ne,
       "⟲ claves cruzadas entre Junior y junior fallan con el MISMO 401 que una cuenta inexistente")
    c_sh, d_sh = pedir("POST", "/cuentas/entrar",
                       {"usuario": "veterana", "pass_sha256_upper": sha(claves_iniciales["veterana"])})
    ok(c_sh == 200 and d_sh.get("uid") == eid_vet, "entra también mandando pass_sha256_upper (como el launcher)")
    ok(pt.rol_de(eid_jefe) == "admin" and pt.rol_de(105) is None,
       "admin.txt por nombre de usuario resuelve al Eñeños ID (y no al uid_viejo 105)")
    with open(admin_txt, "w", encoding="utf-8") as f:
        f.write("105\n")
    ok(pt.rol_de(eid_jefe) == "admin" and pt.rol_de(105) is None,
       "si admin.txt trae un número viejo (105), se traduce vía importadas al Eñeños ID")
    c_ban, d_ban = pedir("POST", "/cuentas/entrar", {"usuario": "baneada", "clave": claves_iniciales["baneada"]})
    ok(c_ban == 403 and d_ban.get("error") == "Esta cuenta está suspendida.",
       "cuenta baneada importada no entra (403 con el mensaje de suspensión)")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "baneada", "clave": "mala"})[0] == 401,
       "⟲ cuenta baneada con clave mala da 401 (no revela que está baneada)")
    c_fus, d_fus = pedir("POST", "/cuentas/entrar", {"usuario": "fusion", "clave": claves_iniciales["fusion"]})
    ok(c_fus == 403 and d_fus.get("error") == "Esta cuenta se unió a otra: entra con aquélla.",
       "cuenta fusionada importada no entra (403 con el mensaje de fusión)")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "fusion", "clave": "mala"})[0] == 401,
       "⟲ cuenta fusionada con clave mala da 401")

    print("5 · registrar (uid >= UID_NUEVAS_DESDE y > máx copiado, unicidad y freno)")
    pt._fallos.clear()      # (la sección anterior falló a propósito muchas veces: sin esto, el freno contesta 429 a todo)
    ok(pedir("POST", "/cuentas/registrar", {"usuario": "nueva_1", "clave": "clave_n1"}, x_r2=False)[0] == 403,
       "⟲ registrar sin X-R2 da 403")
    c_r1, d_r1 = pedir("POST", "/cuentas/registrar", {"usuario": "nueva_1", "clave": "clave_n1"}, ip="10.2.2.1")
    ok(c_r1 == 200 and d_r1.get("uid") == pt.UID_NUEVAS_DESDE + 7
       and d_r1.get("usuario") == "nueva_1",
       f"registrar asigna Eñeños ID secuencial uid={d_r1.get('uid')} (>= UID_NUEVAS_DESDE={pt.UID_NUEVAS_DESDE})")
    c_e1, d_e1 = pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_n1"})
    ok(c_e1 == 200 and d_e1.get("uid") == d_r1.get("uid"), "la cuenta recién registrada entra enseguida")
    pt._cuentas().execute("PRAGMA wal_checkpoint(FULL)")
    ok(sha("clave_n1").encode("ascii") not in bytes_base(ruta_cuentas),
       "⛔ el SHA-256 de la cuenta nueva tampoco aparece en cuentas.db")
    ok(pedir("POST", "/cuentas/registrar", {"usuario": "nueva_1", "clave": "otra"}, ip="10.2.2.2")[0] == 409,
       "⟲ usuario repetido (nueva_1) se rechaza con 409")
    ok(pedir("POST", "/cuentas/registrar", {"usuario": "Junior", "clave": "otra"}, ip="10.2.2.2")[0] == 409,
       "⟲ usuario ya importado (Junior) se rechaza con 409")
    c_jmay, d_jmay = pedir("POST", "/cuentas/registrar", {"usuario": "JUNIOR", "clave": "clave_jmay"}, ip="10.2.2.3")
    ok(c_jmay == 200 and d_jmay.get("uid") == pt.UID_NUEVAS_DESDE + 8,
       "JUNIOR (todo mayúscula) se permite porque la comparación es exacta (COLLATE BINARY)")
    # Incluso si una base vieja trae un uid_viejo >= UID_NUEVAS_DESDE, importar le da un Eñeños ID secuencial nuevo:
    base_alta = os.path.join(tmp, "datos_alta.db")
    ca = sqlite3.connect(base_alta)
    ca.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, username TEXT UNIQUE, pass_hash TEXT)")
    ca.execute("INSERT INTO users VALUES (?, ?, ?)", (15_000_000, "importada_alta", sha("clave_alta")))
    ca.commit()
    ca.close()
    with contextlib.redirect_stdout(io.StringIO()):
        pt.consola(["importar", base_alta])
    eid_alta = pt._cuentas().execute("SELECT uid FROM cuentas WHERE usuario = 'importada_alta'").fetchone()[0]
    ok(int(eid_alta) == pt.UID_NUEVAS_DESDE + 9,
       "importar NO hereda el uid_viejo 15_000_000: asigna el siguiente Eñeños ID secuencial")
    c_r2, d_r2 = pedir("POST", "/cuentas/registrar",
                       {"usuario": "nueva_2", "pass_sha256_upper": sha("clave_n2")}, ip="10.2.2.4")
    ok(c_r2 == 200 and d_r2.get("uid") == pt.UID_NUEVAS_DESDE + 10,
       "registrar continúa secuencialmente después de importar")
    for mal_u in ("ab", "a" * 17, "con espacio", "mal!"):
        ok(pedir("POST", "/cuentas/registrar", {"usuario": mal_u, "clave": "clave_ok"}, ip="10.2.3.1")[0] == 400,
           f"⟲ formato de usuario inválido ({mal_u!r}) da 400")
    ok(pedir("POST", "/cuentas/registrar", {"usuario": "valida_x", "clave": ""}, ip="10.2.3.2")[0] == 400
       and pedir("POST", "/cuentas/registrar", {"usuario": "valida_x", "pass_sha256_upper": "1234"},
                 ip="10.2.3.2")[0] == 400,
       "⟲ clave vacía o hash mal formado en registrar da 400")
    for i in range(8):
        pedir("POST", "/cuentas/registrar", {"usuario": "no!", "clave": "x"}, ip="10.8.8.8")
    ok(pedir("POST", "/cuentas/registrar", {"usuario": "frenada_9", "clave": "clave_ok"}, ip="10.8.8.8")[0] == 429,
       "⟲ freno por IP en registrar: al 9.º intento desde la misma IP da 429")
    ok(pedir("POST", "/cuentas/registrar", {"usuario": "frenada_9", "clave": "clave_ok"}, ip="10.8.8.9")[0] == 200,
       "desde otra IP sí deja registrar")

    print("6 · cambiar-clave (jugador y consola) y banear / desbanear por consola")
    pt._fallos.clear()      # (la sección anterior falló a propósito muchas veces: sin esto, el freno contesta 429 a todo)
    tok_n1 = d_e1["sesion"]
    ok(pedir("POST", "/cuentas/cambiar-clave",
             {"clave_actual": "clave_n1", "clave_nueva": "clave_n1_nueva"}, token=tok_n1, x_r2=False)[0] == 403,
       "⟲ cambiar-clave sin X-R2 da 403")
    ok(pedir("POST", "/cuentas/cambiar-clave",
             {"clave_actual": "clave_n1", "clave_nueva": "clave_n1_nueva"}, token="sesion_falsa")[0] == 401,
       "⟲ cambiar-clave sin sesión válida da 401")
    ok(pedir("POST", "/cuentas/cambiar-clave",
             {"clave_actual": "clave_equivocada", "clave_nueva": "clave_n1_nueva"}, token=tok_n1)[0] == 401,
       "⟲ cambiar-clave con la clave actual mal da 401")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_n1"})[0] == 200
       and pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_n1_nueva"})[0] == 401,
       "⟲ tras fallar cambiar-clave, la contraseña vieja sigue andando y la nueva no")
    pt._fallos.clear()
    c_cc, _ = pedir("POST", "/cuentas/cambiar-clave",
                    {"clave_actual": "clave_n1", "clave_nueva": "clave_n1_nueva"}, token=tok_n1)
    ok(c_cc == 200, "cambiar-clave con sesión y clave actual correctas da 200")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_n1"})[0] == 401,
       "⟲ la clave vieja deja de servir enseguida")
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_n1_nueva"})[0] == 200,
       "la clave nueva ya sirve para entrar")
    c_cc2, _ = pedir("POST", "/cuentas/cambiar-clave",
                     {"actual_sha256_upper": sha("clave_n1_nueva"), "nueva_sha256_upper": sha("clave_n1_tercera")},
                     token=tok_n1)
    ok(c_cc2 == 200
       and pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_n1_nueva"})[0] == 401
       and pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_n1_tercera"})[0] == 200,
       "cambiar-clave también acepta los SHA-256 en hex mayúscula")
    sal_adm = io.StringIO()
    with contextlib.redirect_stdout(sal_adm):
        pt.consola(["cambiar-clave", "nueva_1", "clave_por_admin"])
    ok(sha("clave_por_admin").lower() not in sal_adm.getvalue().lower()
       and pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_n1_tercera"})[0] == 401
       and pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_por_admin"})[0] == 200,
       "ADMIN por consola (cambiar-clave) cambia la contraseña sin imprimir hashes ⟲ la anterior deja de servir")
    with contextlib.redirect_stdout(io.StringIO()):
        pt.consola(["banear", "nueva_1", "prueba de ban"])
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_por_admin"})[0] == 403
       and pedir("POST", "/cuentas/pase", {"juego": "r2beat2013"}, token=tok_n1)[0] in (401, 403),
       "ADMIN por consola (banear) suspende la cuenta en cuentas.db y mata su sesión")
    with contextlib.redirect_stdout(io.StringIO()):
        pt.consola(["desbanear", "nueva_1"])
    ok(pedir("POST", "/cuentas/entrar", {"usuario": "nueva_1", "clave": "clave_por_admin"})[0] == 200,
       "⟲ ADMIN por consola (desbanear) reactiva la cuenta y vuelve a entrar")

    print("7 · pases para r2beat2013, parches, web y eda")
    pt._fallos.clear()      # (la sección anterior falló a propósito muchas veces: sin esto, el freno contesta 429 a todo)
    tok_jr = d_jr1["sesion"]
    tok_jr_min = d_jr2["sesion"]
    mapa_juegos = {j["id"]: j["permitido"] for j in d_jr1["juegos"]}
    # ★ coordinador (19-nov): el esperado se DERIVA de `JUEGOS_DUENA` y de la fecha de cada lanzamiento
    #   (`lanzamientos.py`). El que estaba escrito a mano había envejecido (sin `r2beat-moderno`, con GunBound abierto).
    _lz = sys.modules["servidor.lanzamientos"]
    esperado = {}
    for j, v in pt.JUEGOS_DUENA.items():
        lz = _lz.de_pase(pt, j)
        esperado[j] = (time.time() >= lz[1]) if lz else v["abierto"]
    ok(mapa_juegos == esperado,
       f"al entrar, una cuenta activa sin aprobar ve cada juego abierto o cerrado según su lanzamiento ({mapa_juegos})")
    ok(mapa_juegos.get("r2beat2013") is True and mapa_juegos.get("parches") is True and mapa_juegos.get("web") is True
       and mapa_juegos.get("r2beat2013-subir") is False,
       "⟲ y lo que no tiene lanzamiento no depende de la fecha: r2beat2013, parches y web abiertos; subir, cerrado")
    jw = pedir("GET", "/cuentas/clave-publica")[1]["keys"][0]
    pub = pt._de_b64u(jw["x"])
    for j_abierto in ("r2beat2013", "parches", "web"):
        cp, dp = pedir("POST", "/cuentas/pase", {"juego": j_abierto}, token=tok_jr)
        carga = pt.comprobar_pase(dp.get("pase", ""), pub, j_abierto)
        ok(cp == 200 and carga is not None and carga["sub"] == str(eid_jr1) and carga["aud"] == j_abierto,
           f"pase para {j_abierto} sale para cualquier cuenta activa y verifica con la clave pública")
        if j_abierto in pt.JUEGOS_CON_LOGIN:
            # ★ 16-nov (decisión de Eñeños): el pase del servidor de PARCHES lleva el login como nombre visible, para
            #   firmar las subidas al servidor de prueba («login · Eñeños ID»). Sólo en `nombre`, nunca como `usuario`.
            ok(carga.get("nombre") == "Junior" and "usuario" not in carga,
               f"el pase de {j_abierto} lleva el login SÓLO como nombre visible (subidas)")
        else:
            ok("Junior" not in json.dumps(carga) and "usuario" not in carga,
               f"⛔ el pase de {j_abierto} NO trae el nombre de usuario")
        otro_aud = "web" if j_abierto != "web" else "r2beat2013"
        ok(pt.comprobar_pase(dp["pase"], pub, otro_aud) is None,
           f"⟲ el pase de {j_abierto} NO sirve como pase de {otro_aud}")
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, token=tok_jr)[0] == 403,
       "⟲ el pase de eda sigue pidiendo aprobación (403 antes de aprobar)")
    with contextlib.redirect_stdout(io.StringIO()):
        pt.consola(["aprobar", "Junior", "eda"])
    cp_eda, dp_eda = pedir("POST", "/cuentas/pase", {"juego": "eda"}, token=tok_jr)
    carga_eda = pt.comprobar_pase(dp_eda.get("pase", ""), pub, "eda")
    ok(cp_eda == 200 and carga_eda is not None and carga_eda["sub"] == str(eid_jr1) and "Junior" not in json.dumps(carga_eda),
       "tras aprobar a Junior en eda, recibe pase válido sin el nombre de usuario")
    ok(pedir("POST", "/cuentas/pase", {"juego": "eda"}, token=tok_jr_min)[0] == 403,
       "⟲ aprobar a Junior no aprueba a junior")
    ok(pedir("POST", "/cuentas/pase", {"juego": "juego_inexistente"}, token=tok_jr)[0] == 404,
       "⟲ un aud que no existe se rechaza con 404")

    print("8 · pedidos internos GET /cuentas/interno/cuenta/<uid> y /enlaces")
    pt._fallos.clear()      # (la sección anterior falló a propósito muchas veces: sin esto, el freno contesta 429 a todo)
    ci, di = pedir("GET", f"/cuentas/interno/cuenta/{eid_jr1}", token=FICHA)
    ok(ci == 200 and di == {"uid": eid_jr1, "usuario": "Junior", "estado": "activa"},
       "con la ficha correcta devuelve {uid, usuario, estado} de Junior por su Eñeños ID")
    ci_b, di_b = pedir("GET", f"/cuentas/interno/cuenta/{eid_ban}", cab_extra={"X-Ficha-Interna": FICHA})
    ok(ci_b == 200 and di_b == {"uid": eid_ban, "usuario": "baneada", "estado": "baneada"},
       "con cabecera X-Ficha-Interna también responde y muestra el estado baneada")
    ce_l, de_l = pedir("GET", "/cuentas/interno/enlaces", token=FICHA)
    ok(ce_l == 200 and isinstance(de_l.get("cuentas"), list)
       and {"usuario": "Junior", "uid": eid_jr1} in de_l["cuentas"]
       and "clave" not in json.dumps(de_l) and "scrypt" not in json.dumps(de_l),
       "GET /cuentas/interno/enlaces devuelve lista {usuario, uid} con Eñeños IDs y sin claves")
    ok("clave" not in json.dumps(di) and "scrypt" not in json.dumps(di)
       and sha(claves_iniciales["Junior"]).lower() not in json.dumps(di).lower(),
       "⛔ el pedido interno nunca devuelve nada de la contraseña")
    ok(pedir("GET", f"/cuentas/interno/cuenta/{eid_jr1}")[0] == 401
       and pedir("GET", "/cuentas/interno/enlaces")[0] == 401,
       "⟲ sin ficha da 401")
    ok(pedir("GET", f"/cuentas/interno/cuenta/{eid_jr1}", token="ficha-mala")[0] == 401
       and pedir("GET", "/cuentas/interno/enlaces", token="ficha-mala")[0] == 401,
       "⟲ con otra ficha da 401")
    ok(pedir("GET", "/cuentas/interno/cuenta/99999999", token=FICHA)[0] == 404,
       "⟲ un uid que no existe da 404")
    os.environ.pop("R2_CUENTAS_FICHA_INTERNA", None)
    try:
        ci_sin, _ = pedir("GET", f"/cuentas/interno/cuenta/{eid_jr1}", token=FICHA)
        ce_sin, _ = pedir("GET", "/cuentas/interno/enlaces", token=FICHA)
    finally:
        os.environ["R2_CUENTAS_FICHA_INTERNA"] = FICHA
    ok(ci_sin == 404 and ce_sin == 404,
       "⟲ sin la variable R2_CUENTAS_FICHA_INTERNA esos pedidos internos no existen (404)")
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
print("✔ cuenta dueña (parte 1): todo bien")
