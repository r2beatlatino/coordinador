# -*- coding: utf-8 -*-
"""probar_subidas — los amigos suben archivos del cliente al server de PRUEBA (subidas.py + juez.py + patchserver).

16-nov-2026. Eñeños: «que sólo los autorizados, tipo EDA, puedan subir directamente; que los otros tengan que ser
aprobados, así como las PR». Y después (§37): «que si algo no gustó se pueda volver al estado anterior, hasta 5
atrás» y «pruebas de seguridad para que no puedan subir malware o archivos malintencionados».

Corre el `patchserver.py` de verdad en un hilo, con pases firmados de verdad (`portero.emitir_pase`). Cada chequeo
lleva su revés (⟲). Los ataques de §37 están en las secciones 9 a 14.

    python -X utf8 pruebas/probar_subidas.py
"""
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(RAIZ, "herramientas", "contenedores", "parches")
sys.path.insert(0, RAIZ)
_tmp = tempfile.mkdtemp(prefix="r2_subidas_")
os.environ["R2_PORTERO_CLAVE"] = os.path.join(_tmp, "clave.json")
# ★ coordinador (19-nov): una base del juego de MENTIRA (vacía). Antes el portero leía la `datos.db` que hubiera en la
#   raíz del repo (en la PC de desarrollo, la base local de verdad): acá no hay ninguna, y no tiene que haberla.
import sqlite3 as _sql                       # noqa: E402
os.environ["R2_BASE"] = os.path.join(_tmp, "datos.db")
os.environ["R2_PORTERO_BASE"] = os.path.join(_tmp, "portero.db")
_c = _sql.connect(os.environ["R2_BASE"])
_c.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, username TEXT, pass_hash TEXT)")
_c.commit()
_c.close()
from servidor import portero as pt          # noqa: E402

fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que, flush=True)
    if not cond:
        fallos.append(que)


def modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


def md5(b):
    return hashlib.md5(b).hexdigest()


def pak(archivos, pre=b""):
    """Un .pak del R2Beat bien formado (el formato que lee el juez: datos, tabla en claro, cola de 9 bytes)."""
    datos, tabla, off = b"", b"", 0
    for nombre, cont in archivos.items():
        n = nombre.encode("latin-1")
        tabla += bytes([len(n), 1]) + struct.pack("<III", off, len(cont), len(cont)) + n + b"\x00"
        datos += cont
        off += len(cont)
    return datos + pre + tabla + struct.pack("<II", len(datos), len(archivos)) + b"\x12"


def release(raiz, nombre, archivos):
    d = os.path.join(raiz, nombre)
    os.makedirs(d)
    fs = []
    for n, datos in archivos.items():
        os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True)
        open(os.path.join(d, n), "wb").write(datos)
        fs.append({"path": n, "md5": md5(datos), "size": len(datos)})
    json.dump({"version": nombre, "files": fs}, open(os.path.join(d, "manifest.json"), "w"))


def main():
    sys.path.insert(0, P)
    ps = modulo("patchserver_sub", os.path.join(P, "patchserver.py"))
    S = sys.modules.get("subidas") or modulo("subidas", os.path.join(P, "subidas.py"))
    J = sys.modules["juez"]
    rels = os.path.join(_tmp, "releases")
    EXE = b"MZ el exe de siempre" * 50
    NOCHE = pak({"isla/noche.dds": b"DDS noche" * 50})
    NIEVE = pak({"isla/nieve.dds": b"DDS nieve" * 50})
    release(rels, "prod1", {"R2Beat.exe": EXE, "isla.pak": NOCHE, "Pack/Sala.pak": pak({"sala.dds": b"DDS s"})})
    release(rels, "prod1-nieve", {"R2Beat.exe": EXE, "isla.pak": NIEVE, "Pack/Sala.pak": pak({"sala.dds": b"DDS s"})})
    _s, pub, _k = pt.clave()
    ps.CFG.clear()
    ps.CFG.update(listen="127.0.0.1", port=0, clean_db=os.path.join(_tmp, "no.db"), status_file=os.path.join(_tmp, "no.json"),
                  releases_dir=rels, current="prod1", current_prueba="prod1-nieve", token_ttl_sec=3600,
                  quota_mb_per_token=1500, per_ip_quota_mb_per_hour=3000, per_ip_auth_per_hour=30, ban_minutes=30,
                  login_mode="pase", file_base_url="", cuentas_public_key=pt._b64u(pub))
    srv = ps.ThreadingHTTPServer(("127.0.0.1", 0), ps.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d" % srv.server_address[1]
    A, B, C = 10000101, 10000102, 10000103        # A = un amigo cualquiera · B y C = AUTORIZADOS
    tok = {A: "a" * 32, B: "b" * 32, C: "c" * 32}
    for u, t in tok.items():
        ps.TOKENS[t] = {"uid": u, "user": str(u), "exp": time.time() + 3600, "used": 0, "ip": "127.0.0.1"}
    ps.TOKENS[tok[B]]["nombre"] = "EñeñosB"                   # lo que pone el pase de Cuenta Eñeños

    def pedir(u, ruta, cuerpo=None, crudo=None, cab=None):
        datos = crudo if crudo is not None else (None if cuerpo is None else json.dumps(cuerpo).encode())
        req = urllib.request.Request(url + ruta, data=datos, method="POST" if datos is not None else "GET",
                                     headers=dict({"Authorization": "Bearer " + tok[u]}, **(cab or {})))
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                b = r.read()
                return r.status, (json.loads(b) if b[:1] in (b"{", b"[") else b)
        except urllib.error.HTTPError as e:
            b = e.read()
            return e.code, (json.loads(b) if b[:1] == b"{" else {})

    subir = lambda u, ruta, datos: pedir(u, "/subidas/archivo", crudo=datos, cab={"X-Ruta": urllib.parse.quote(ruta)})
    pase = lambda u: pt.emitir_pase(u, "r2beat2013-subir")[0]
    prueba = lambda: pedir(A, "/manifest?canal=prueba")[1]
    de = lambda m, ruta: next((e for e in m.get("files", []) if e["path"] == ruta), {})
    enviar = lambda u, nota, **k: pedir(u, "/subidas/enviar", dict({"nota": nota}, **k))
    MZ_DLL = b"MZ\x90\x00" + b"\x00" * 120 + b"una dll de prueba"
    blobs = lambda: sorted(n for n in os.listdir(os.path.join(rels, "_subidas", "blobs")) if not n.startswith("."))

    print("0 · subir es POR INVITACIÓN; jugar y probar, para todos (Eñeños)")
    c, d = subir(A, "isla.pak", pak({"a.dds": b"DDS"}))
    ok(c == 403 and "invitación" in d.get("error", ""), "⟲ A sin invitación no puede subir (%s)" % d.get("error"))
    c, d = enviar(A, "sin invitación")
    ok(c == 403, "⟲ ni enviar")
    ok(prueba().get("version") == "prod1-nieve", "pero sí ve (y baja) la lista del servidor de prueba")
    c, d = pedir(A, "/subidas/invitacion", {"nota": "quiero subir la isla de nieve"})
    ok(c == 200 and d["estado"] == "pendiente" and d["quien"] == "cuenta %d" % A, "A SOLICITA invitación: pendiente")
    c, d = pedir(A, "/subidas/invitar", {"uid": A, "accion": "aprobar"})
    ok(c == 403, "⟲ A no se puede aprobar a sí mismo")
    c, l = pedir(B, "/subidas/lista", {"pase": pase(B)})
    ok(any(i["uid"] == A and i["estado"] == "pendiente" for i in l["invitaciones"]) and l["invitado"],
       "B (autorizado) ve la solicitud de A y queda invitado solo")
    ok(pedir(A, "/subidas/lista", {})[1]["invitaciones"] == [], "⟲ A no ve las invitaciones de nadie")
    c, d = pedir(B, "/subidas/invitar", {"pase": pase(B), "uid": A, "accion": "aprobar"})
    ok(c == 200 and d["estado"] == "aprobada" and pedir(A, "/subidas/lista", {})[1]["invitado"], "B aprueba: A queda invitado")
    c, d = pedir(B, "/subidas/invitar", {"pase": pase(B), "uid": A, "accion": "quitar"})
    c2, _d = subir(A, "isla.pak", pak({"a.dds": b"DDS"}))
    ok(c == 200 and c2 == 403, "⟲ B le QUITA la invitación: A ya no sube")
    pedir(A, "/subidas/invitacion", {"nota": "de nuevo"})
    pedir(B, "/subidas/invitar", {"pase": pase(B), "uid": A, "accion": "aprobar"})

    def invitar(u):
        pedir(u, "/subidas/invitacion", {"nota": "prueba"})
        pedir(B, "/subidas/invitar", {"pase": pase(B), "uid": u, "accion": "aprobar"})

    print("1 · las rutas")
    for mala in ("../fuera.pak", "/etc/passwd", "C:/Windows/x.dll", "Pack/../../x", "manifest.json", "_subidas/x", "", "a//"):
        c, _d = subir(A, mala, b"x")
        if c != 400:
            ok(False, "⟲ ruta tramposa %r rechazada (dio %s)" % (mala, c))
    ok(True, "⟲ rutas tramposas (.., absoluta, unidad, el manifest, _subidas, vacía): todas 400")
    SALA = pak({"sala/nueva.dds": b"DDS nueva" * 30})
    c, d = subir(A, "Pack/sala nueva.pak", SALA)
    ok(c == 200 and d["ruta"] == "Pack/sala nueva.pak" and d["md5"] == md5(SALA) and d["clase"] == "recurso",
       "una ruta con carpeta y espacios entra al borrador (recurso)")

    print("2 · un amigo cualquiera (A): su envío queda PENDIENTE")
    NIEVE2 = pak({"isla/nieve.dds": b"DDS nieve con muneco" * 40})
    c, d = subir(A, "isla.pak", NIEVE2)
    ok(c == 200 and not d["ejecutable"], "sube la isla")
    c, d = subir(A, "d3d9.dll", b"MZ una dll" + b"\x00" * 64)
    ok(c == 200 and d["ejecutable"] is True and d["clase"] == "sensible", "una .dll entra como SENSIBLE (marcada)")
    antes = prueba()
    c, p1 = enviar(A, "isla con muñeco de nieve", quien="Eñeños")     # ⟲ intenta firmar como otro
    ok(c == 200 and p1["estado"] == "pendiente" and p1["ejecutables"] == ["d3d9.dll"] and len(p1["archivos"]) == 3
       and p1["dos_llaves"], "enviado: #%s PENDIENTE, 3 archivos, la dll marcada (dos llaves)" % p1.get("id"))
    ok(p1["quien"] == "cuenta %d" % A, "⟲ el nombre lo pone el SERVER, no el launcher («Eñeños» se ignora): %r" % p1.get("quien"))
    ok(prueba() == antes, "⟲ la lista de prueba NO cambió (todavía no la aprobó nadie)")
    ok(pedir(A, "/subidas/lista", {})[1]["borrador"] == [], "y su borrador quedó vacío")

    print("3 · quién puede aprobar")
    c, _d = pedir(A, "/subidas/revisar", {"id": p1["id"], "accion": "aprobar"})
    ok(c == 403, "⟲ A sin pase de autorizado: no puede aprobar (ni lo suyo)")
    c, _d = pedir(A, "/subidas/revisar", {"pase": pt.emitir_pase(A, "parches")[0], "id": p1["id"], "accion": "aprobar"})
    ok(c == 403, "⟲ con un pase de otra cosa (aud parches): tampoco")
    c, _d = pedir(A, "/subidas/revisar", {"pase": pase(B), "id": p1["id"], "accion": "aprobar"})
    ok(c == 403, "⟲ con el pase de B pero la sesión de A: tampoco (el pase tiene que ser SUYO)")
    c, l = pedir(A, "/subidas/lista", {})
    ok(not l["autorizado"] and [p["id"] for p in l["propuestas"]] == [p1["id"]], "A ve sólo lo suyo")
    c, l = pedir(B, "/subidas/lista", {"pase": pase(B)})
    ok(l["autorizado"] and any(p["id"] == p1["id"] and p["estado"] == "pendiente" for p in l["propuestas"]),
       "B (autorizado) ve las pendientes de los demás")

    print("4 · B aprueba: release de prueba NUEVA")
    p_usado = pase(B)
    c, r = pedir(B, "/subidas/revisar", {"pase": p_usado, "id": p1["id"], "accion": "aprobar"})
    ok(c == 200 and r["estado"] == "aplicada" and r["release"] == "prod1-p%d" % p1["id"] and r["revisor"] == B,
       "aprobada: release %s" % r.get("release"))
    rel1 = r["release"]
    m = prueba()
    ok(m.get("version") == r["release"] and de(m, "isla.pak").get("md5") == md5(NIEVE2) and de(m, "Pack/sala nueva.pak")
       and de(m, "R2Beat.exe").get("md5") == md5(EXE), "la lista de prueba ya trae lo de A (y lo demás igual)")
    c, b = pedir(A, m["base"] + "isla.pak")
    ok(c == 200 and md5(b) == md5(NIEVE2), "y se baja con su md5")
    mp = pedir(A, "/manifest")[1]
    ok(mp["version"] == "prod1" and de(mp, "isla.pak")["md5"] == md5(NOCHE) and not de(mp, "Pack/sala nueva.pak"),
       "⟲ PROD no cambió nada")
    ok(open(os.path.join(rels, "prod1-nieve", "isla.pak"), "rb").read() == NIEVE,
       "⟲ y la release de prueba anterior quedó intacta (enlaces duros: se borra el enlace, no se escribe encima)")
    c, _d = pedir(B, "/subidas/revisar", {"pase": p_usado, "id": p1["id"], "accion": "aprobar"})
    ok(c == 403, "⟲ el mismo pase no sirve dos veces")
    c, _d = pedir(B, "/subidas/revisar", {"pase": pase(B), "id": p1["id"], "accion": "aprobar"})
    ok(c == 409, "⟲ una ya aplicada no se vuelve a aplicar")

    print("5 · B (autorizado) sube DIRECTO")
    ISLA_B = pak({"isla/b.dds": b"DDS de B" * 60})
    subir(B, "isla.pak", ISLA_B)
    c, p2 = enviar(B, "otra isla", pase=pase(B), quien="otro")
    m = prueba()
    ok(c == 200 and p2["estado"] == "aplicada" and p2.get("directa") and m["version"] == p2["release"],
       "se aplica en el acto (sin pendiente): %s" % p2.get("release"))
    ok(p2["quien"] == "EñeñosB", "y lo firma con el nombre de su pase (%r)" % p2.get("quien"))
    ok(de(m, "isla.pak")["md5"] == md5(ISLA_B) and de(m, "Pack/sala nueva.pak"),
       "y se arma SOBRE la anterior (sigue la sala que subió A)")

    print("6 · rechazar (y lo rechazado no ocupa lugar)")
    FEA = pak({"isla/fea.dds": b"DDS fea" * 10})
    subir(A, "isla.pak", FEA)
    c, p3 = enviar(A, "otra")
    ok(md5(FEA) in blobs(), "mientras espera, su archivo está guardado")
    c, r = pedir(B, "/subidas/revisar", {"pase": pase(B), "id": p3["id"], "accion": "rechazar"})
    ok(c == 200 and r["estado"] == "rechazada" and prueba()["version"] == p2["release"], "rechazada: la lista no cambia")
    ok(md5(FEA) not in blobs() and md5(ISLA_B) in blobs(), "⟲ y su archivo se borró (lo aplicado sigue)")

    print("7 · topes (Eñeños): 1 pendiente por cuenta —el nuevo REEMPLAZA—, 5 en total, 500 MB por envío")
    X1, X2 = pak({"x1.dds": b"DDS uno"}), pak({"x2.dds": b"DDS dos"})
    subir(A, "x1.pak", X1)
    c, q1 = enviar(A, "primero")
    subir(A, "x2.pak", X2)
    c, q2 = enviar(A, "segundo")
    l = pedir(A, "/subidas/lista", {})[1]
    est = {p["id"]: p["estado"] for p in l["propuestas"]}
    ok(c == 200 and q2["estado"] == "pendiente" and q2.get("reemplaza") == [q1["id"]] and est.get(q1["id"]) == "reemplazada"
       and sum(1 for p in l["propuestas"] if p["estado"] == "pendiente") == 1,
       "A manda otro envío: REEMPLAZA al que tenía esperando (nunca 2 abiertos a la vez)")
    ok(md5(X1) not in blobs() and md5(X2) in blobs(), "⟲ y el archivo del reemplazado se borró")
    otros = [10000201, 10000202, 10000203, 10000204, 10000205]
    for u in otros:
        tok[u] = "%032d" % u
        ps.TOKENS[tok[u]] = {"uid": u, "user": str(u), "exp": time.time() + 3600, "used": 0, "ip": "127.0.0.1"}
        invitar(u)
    cs = []
    for k, u in enumerate(otros[:4]):
        subir(u, "o%d.pak" % k, pak({"o%d.dds" % k: b"DDS o%d" % k}))
        cs.append(enviar(u, "otro %d" % k)[0])
    l = pedir(A, "/subidas/lista", {})[1]
    ok(cs == [200] * 4 and l["pendientes_total"] == 5 and l["limites"]["pendientes_total"] == 5,
       "4 cuentas más mandan: 5 pendientes en total (%s)" % l.get("pendientes_total"))
    subir(otros[4], "o4.pak", pak({"o4.dds": b"DDS o4"}))
    c, d = enviar(otros[4], "el sexto")
    ok(c == 429, "⟲ una 6.ª cuenta no puede: ya hay 5 pendientes (%s)" % d.get("error"))
    subir(A, "x3.pak", pak({"x3.dds": b"DDS tres"}))
    c, q3 = enviar(A, "tercero")
    ok(c == 200 and q3["estado"] == "pendiente" and pedir(A, "/subidas/lista", {})[1]["pendientes_total"] == 5,
       "pero A, con 5 en total, SÍ puede reemplazar el suyo (siguen 5)")
    subir(B, "directo.pak", pak({"d.dds": b"DDS directo"}))
    c, d = enviar(B, "directo con 5 esperando", pase=pase(B))
    ok(c == 200 and d["estado"] == "aplicada", "un autorizado sin programas entra directo aunque haya 5 esperando")
    for u in [A] + otros[:4]:                          # se vacía la cola para lo que sigue
        for p in pedir(B, "/subidas/lista", {"pase": pase(B)})[1]["propuestas"]:
            if p["estado"] == "pendiente" and p["uid"] == u:
                pedir(B, "/subidas/revisar", {"pase": pase(B), "id": p["id"], "accion": "rechazar"})
    pedir(otros[4], "/subidas/descartar", {})
    tope, S.TAM_MAX_BORRADOR = S.TAM_MAX_BORRADOR, 3000
    c1, _d = subir(A, "g1.pak", pak({"g1.dds": b"DDS" + b"a" * 1800}))
    c2, d2 = subir(A, "g2.pak", pak({"g2.dds": b"DDS" + b"b" * 1800}))
    S.TAM_MAX_BORRADOR = tope
    ok(c1 == 200 and c2 == 413, "⟲ el tope es POR ENVÍO, sumando los archivos (%s)" % d2.get("error"))
    ok(S.TAM_MAX_BORRADOR == S.TAM_MAX_ARCHIVO == 500 * 2**20, "el tope es 500 MB (archivo o archivos)")
    pedir(A, "/subidas/descartar", {})
    c, d = pedir(A, "/subidas/archivo", crudo=b"", cab={"X-Ruta": "vacio.pak"})
    ok(c == 400, "⟲ un archivo vacío no entra")

    print("7b · PROBAR cualquier pendiente; editar/cancelar SÓLO el propio (Eñeños)")
    O = otros[0]
    VA, VO = pak({"va.dds": b"DDS de A"}), pak({"vo.dds": b"DDS de O"})
    subir(A, "isla.pak", VA)
    c, qa = enviar(A, "isla de A para probar")
    subir(O, "isla.pak", VO)
    c, qo = enviar(O, "isla de O para probar")
    vig = prueba()["version"]
    l = pedir(A, "/subidas/lista", {})[1]
    ok(any(p["id"] == qo["id"] for p in l["propuestas"]), "A (no autorizado) VE el pendiente de O (para poder probarlo)")
    c, mo = pedir(A, "/manifest?canal=prueba&envio=%d" % qo["id"])
    ok(c == 200 and mo.get("envio") == qo["id"] and mo["version"] == "%s-v%d" % (vig, qo["id"])
       and de(mo, "isla.pak").get("md5") == md5(VO), "A prueba el envío de O: su lista trae la isla de O (%s)" % mo.get("version"))
    c, b = pedir(A, mo["base"] + "isla.pak")
    ok(c == 200 and md5(b) == md5(VO), "y se descarga")
    c, ma = pedir(A, "/manifest?canal=prueba&envio=%d" % qa["id"])
    ok(de(ma, "isla.pak").get("md5") == md5(VA), "A rota al suyo: ahora la isla de A")
    ok(prueba()["version"] == vig and pedir(A, "/manifest")[1]["version"] == "prod1",
       "⟲ la lista de prueba de TODOS y la de prod no cambiaron")
    c, d = pedir(A, "/subidas/cancelar", {"id": qo["id"]})
    ok(c == 403, "⟲ A no puede cancelar el envío de O (%s)" % d.get("error"))
    c, d = pedir(A, "/subidas/editar", {"id": qo["id"], "nota": "trucho"})
    ok(c == 403, "⟲ ni editarlo")
    c, d = pedir(A, "/subidas/editar", {"id": qa["id"], "nota": "isla de A, corregida"})
    ok(c == 200 and d["nota"] == "isla de A, corregida", "A edita la descripción del SUYO")
    c, d = pedir(A, "/subidas/cancelar", {"id": qa["id"]})
    ok(c == 200 and d["estado"] == "cancelada", "A cancela el SUYO")
    c, m = pedir(A, "/manifest?canal=prueba&envio=%d" % qa["id"])
    ok(c == 200 and m.get("envio_no_disponible") and m["version"] == vig and not os.path.isdir(os.path.join(rels, "%s-v%d" % (vig, qa["id"]))),
       "⟲ un envío cancelado ya no se prueba: vuelve la lista de prueba normal y su vista previa se borró")
    subir(O, "d3d9.dll", MZ_DLL)
    c, qo2 = enviar(O, "dll de O")
    c, m = pedir(A, "/manifest?canal=prueba&envio=%d" % qo2["id"])
    ok(m.get("envio_no_disponible") and not de(m, "d3d9.dll").get("md5") == md5(MZ_DLL),
       "⟲ una dll SIN APROBAR de otro no se puede probar (%s)" % (m.get("envio_no_disponible") or "")[:60])
    c, m = pedir(O, "/manifest?canal=prueba&envio=%d" % qo2["id"])
    ok(m.get("envio") == qo2["id"] and de(m, "d3d9.dll").get("md5") == md5(MZ_DLL), "quien la subió sí la prueba")
    ok(qo2.get("reemplaza") == [qo["id"]], "(el envío nuevo de O reemplazó al anterior)")
    c, d = pedir(B, "/subidas/revisar", {"pase": pase(B), "id": qo2["id"], "accion": "habilitar"})
    c2, m = pedir(A, "/manifest?canal=prueba&envio=%d" % qo2["id"])
    ok(c == 200 and d.get("programas_ok") == B and d["estado"] == "pendiente" and m.get("envio") == qo2["id"]
       and de(m, "d3d9.dll").get("md5") == md5(MZ_DLL),
       "otro AUTORIZADO habilita sus programas: ahora A también la puede probar (y sigue pendiente)")
    ok(prueba()["version"] == vig, "⟲ habilitar no cambia la lista de nadie")
    subir(B, "d3d9.dll", MZ_DLL + b"B")
    c, qb = enviar(B, "dll de B")
    c, d = pedir(B, "/subidas/revisar", {"pase": pase(B), "id": qb["id"], "accion": "habilitar"})
    ok(c == 403, "⟲ un autorizado no habilita SUS propios programas (dos llaves)")
    pedir(B, "/subidas/cancelar", {"id": qb["id"]})
    subir(O, "sin_nota.pak", pak({"sn.dds": b"DDS sin nota"}))
    c, d = enviar(O, "")
    ok(c == 200 and d["nota"] == "" and d["estado"] == "pendiente", "la descripción es OPCIONAL")
    pedir(O, "/subidas/cancelar", {"id": d["id"]})
    pedir(B, "/subidas/revisar", {"pase": pase(B), "id": qo2["id"], "accion": "rechazar"})

    print("8 · las trampas de Windows en la RUTA (§37)")
    for mala, por_que in (("evil.dll.", "punto al final: Windows guarda «evil.dll»"),
                          ("evil.dll ", "espacio al final: ídem"), ("Pack/nul.pak", "NUL es un dispositivo"),
                          ("com1.txt", "COM1 es un dispositivo"), ("R2BEAT~1.EXE", "nombre corto 8.3 de otro archivo"),
                          ("isla.pak:oculto", "flujo alternativo NTFS")):
        c, _d = subir(A, mala, pak({"a.dds": b"DDS"}))
        # (el espacio del final lo recorta el server ANTES de juzgar: «evil.dll» lo rechaza el juez, 415)
        ok(c in (400, 415), "⟲ %r (%s): rechazada (%s)" % (mala, por_que, c))
    c, d = subir(A, "ISLA.PAK", pak({"isla/m.dds": b"DDS mayus"}))
    ok(c == 200 and d["ruta"] == "isla.pak", "«ISLA.PAK» se guarda como «isla.pak» (en Windows son el mismo): %r" % d.get("ruta"))
    c, d = subir(A, "pack/sala.pak", pak({"s.dds": b"DDS"}))
    ok(c == 200 and d["ruta"] == "Pack/Sala.pak", "«pack/sala.pak» → «Pack/Sala.pak» (la de la lista)")
    pedir(A, "/subidas/descartar", {})

    print("9 · el JUEZ: lo que no es un recurso del juego no entra (§37)")
    MZ = b"MZ\x90\x00" + b"\x00" * 200
    for ruta, datos, por_que in (
            ("instalar.bat", b"@echo off\r\ndel C:\\", "un .bat"), ("x.ps1", b"Remove-Item", "un .ps1"),
            ("acceso.lnk", b"L\x00\x00\x00", "un acceso directo"), ("x.vbs", b"CreateObject", "un .vbs"),
            ("x.msi", b"\xd0\xcf\x11\xe0", "un instalador"), ("sin_extension", b"hola", "sin extensión"),
            ("fondo.png", MZ, "un PROGRAMA disfrazado de .png"), ("isla.pak", MZ + b"\x00" * 64, "un programa disfrazado de .pak"),
            ("leeme.txt", MZ, "un programa disfrazado de .txt"), ("x.bmp", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "un .bmp que no es BMP"),
            ("x.mp3", b"no soy un mp3" * 5, "un .mp3 falso"), ("x.dds", b"nada" * 10, "un .dds falso"),
            ("isla.pak", b"basura " * 40, "un .pak con la tabla rota"),
            ("isla.pak", pak({"isla/virus.exe": MZ}), "un .pak con un PROGRAMA adentro"),
            ("isla.pak", pak({"isla/x.dll": MZ}), "un .pak con una dll adentro"),
            ("isla.pak", pak({"../../Windows/x.dds": b"DDS"}), "un .pak con rutas que salen para afuera"),
            ("d3d9.dll", b"no soy una dll", "una .dll que no es un programa de Windows"),
            ("leeme.txt", b"texto\x00con\x00ceros" * 10, "un .txt binario")):
        n = len(blobs())
        c, d = subir(A, ruta, datos)
        ok(c == 415 and len(blobs()) == n, "⟲ %s (%s): 415 y no se guardó — %s" % (por_que, ruta, d.get("error", c)))
    ok(pedir(A, "/subidas/lista", {})[1]["borrador"] == [], "⟲ y nada de eso quedó en el borrador")
    for ruta, datos, que in (("img/fondo.bmp", b"BM" + b"\x00" * 60, "un .bmp"), ("leeme.txt", "hola ñandú".encode("utf-8"), "un .txt"),
                             ("leeme16.txt", "hola".encode("utf-16"), "un .txt UTF-16"),
                             ("rnr_music/e_song1.pak", pak({"e_song1/\xb0\xa1.mp3": b"ID3x"}), "un .pak con nombres coreanos")):
        c, d = subir(A, ruta, datos)
        ok(c == 200 and d["clase"] == "recurso", "%s legítimo sí entra (recurso)" % que)
    c, d = subir(A, "d3d9_proxy.ini", b"[proxy]\r\ndll=\\\\10.0.0.5\\share\\evil.dll\r\n")
    ok(c == 200 and d["clase"] == "sensible" and any("red" in x.lower() for x in d["alertas"]),
       "un .ini que apunta a una dll de RED: SENSIBLE con la alerta a la vista")
    c, d = subir(A, "dxvk.conf", b"# dxvk\r\nd3d9.maxFrameRate = 0\r\n")
    ok(c == 200 and d["clase"] == "sensible", "un .conf: sensible (decide cómo se carga el video)")
    pedir(A, "/subidas/descartar", {})

    print("10 · el control del juez: el cliente REAL entra entero (si R2_CLIENTE_REAL dice dónde está)")
    # (coordinador: antes era una carpeta fija de la PC de desarrollo; ahora se pasa por variable, p. ej. la copia del
    #  cliente del launcher de ensayo. Sin ella, se salta.)
    real = os.environ.get("R2_CLIENTE_REAL") or ""
    if real and os.path.isdir(real):
        malos, n = [], 0
        for r_, _ds, fs in os.walk(real):
            for f in fs:
                if f.lower().endswith(".log"):
                    continue                               # (los logs son de esta PC: no van en la lista)
                p = os.path.join(r_, f)
                n += 1
                try:
                    J.juzgar(f, p, os.path.getsize(p))
                except J.Rechazo as e:
                    malos.append((f, str(e)))
        ok(not malos and n > 2000, "los %d archivos del cliente pasan el juez %s" % (n, malos[:3]))
    else:
        print("  (no está el cliente: se salta)")

    print("11 · DOS LLAVES: los programas nunca entran directo (§37)")
    DLL = MZ + b"una dll de video nueva" * 10
    subir(B, "d3d9.dll", DLL)
    c, p4 = enviar(B, "dll de video nueva", pase=pase(B))
    ok(c == 200 and p4["estado"] == "pendiente" and p4["dos_llaves"],
       "B (autorizado) sube una dll: queda PENDIENTE igual (no entra directo)")
    c, d = pedir(B, "/subidas/revisar", {"pase": pase(B), "id": p4["id"], "accion": "aprobar"})
    ok(c == 403, "⟲ B no puede aprobar su propia dll: %s" % d.get("error"))
    c, r = pedir(C, "/subidas/revisar", {"pase": pase(C), "id": p4["id"], "accion": "aprobar"})
    ok(c == 200 and r["estado"] == "aplicada" and de(prueba(), "d3d9.dll").get("md5") == md5(DLL),
       "C (OTRO autorizado) la aprueba: recién ahí entra")

    print("12 · VOLVER ATRÁS: la vigente y 5 más (§37)")
    c, l = pedir(A, "/subidas/lista", {})
    est = l["estados"]
    ok(est[0]["vigente"] and est[0]["release"] == prueba()["version"] and est[-1]["release"] == "prod1-nieve",
       "el historial: el vigente arriba, la base de prueba abajo (%d estados)" % len(est))
    c, _d = pedir(A, "/subidas/volver", {"release": "prod1-nieve"})
    ok(c == 403, "⟲ A (no autorizado) no puede volver atrás")
    c, v = pedir(B, "/subidas/volver", {"pase": pase(B), "release": rel1})
    m = prueba()
    ok(c == 200 and m["version"] == rel1 and de(m, "isla.pak")["md5"] == md5(NIEVE2)
       and de(m, "d3d9.dll")["md5"] != md5(DLL), "B vuelve al estado de #%d: la lista de prueba es la de entonces (la "
       "isla de A, y NO la dll nueva)" % p1["id"])
    c, l = pedir(A, "/subidas/lista", {})
    c, lb = pedir(B, "/subidas/lista", {})
    ok(any(p["id"] == p4["id"] and p.get("revertida") for p in lb["propuestas"]),
       "la dll de B (que quedó afuera) se marca «revertida» en su lista de envíos")
    c, _d = pedir(B, "/subidas/volver", {"pase": pase(B), "release": rel1})
    ok(c == 409, "⟲ volver al que ya está vigente: 409")
    c, _d = pedir(B, "/subidas/volver", {"pase": pase(B), "release": "prod1"})
    ok(c == 404, "⟲ volver a algo que no está en el historial (prod, u otra cualquiera): 404")
    c, v = pedir(B, "/subidas/volver", {"pase": pase(B), "release": r["release"]})
    ok(c == 200 and prueba()["version"] == r["release"], "y se puede DESHACER el volver (vuelve la dll)")
    pedir(B, "/subidas/volver", {"pase": pase(B), "release": rel1})
    pedir(B, "/subidas/volver", {"pase": pase(B), "release": r["release"]})
    est = pedir(A, "/subidas/lista", {})[1]["estados"]
    ok(len({e["release"] for e in est}) == len(est) and sum(1 for e in est if e["vigente"]) == 1
       and not any("volver a" in e["que"] for e in est) and est[0]["vigente"] and est[0].get("restaurada"),
       "⟲ (captura de Eñeños) restaurar varias veces: cada versión UNA vez, una sola «actual», sin «volver a: volver a:»")
    for i in range(7):                                   # llena el historial de sobra
        subir(B, "extra%d.pak" % i, pak({"e%d.dds" % i: b"DDS e%d" % i}))
        enviar(B, "extra %d" % i, pase=pase(B))
    c, l = pedir(A, "/subidas/lista", {})
    ok(len(l["estados"]) == S.HISTORIAL_MAX and l["estados"][0]["vigente"], "el historial guarda %d (la vigente + 5)" % S.HISTORIAL_MAX)
    ok(not os.path.isdir(os.path.join(rels, rel1)) and os.path.isdir(os.path.join(rels, "prod1-nieve"))
       and os.path.isdir(os.path.join(rels, "prod1")),
       "lo que salió del historial se borra del disco; ⟲ la base y prod NUNCA")
    viejo = l["estados"][-1]["release"]
    c, _d = pedir(B, "/subidas/volver", {"pase": pase(B), "release": viejo})
    ok(c == 200 and prueba()["version"] == viejo, "volver 5 atrás anda (%s)" % viejo)

    print("13 · el INTERRUPTOR de emergencia (§37)")
    interruptor = os.path.join(rels, "_subidas", "apagado")
    open(interruptor, "w").close()
    c, d = subir(A, "isla.pak", pak({"a.dds": b"DDS"}))
    ok(c == 503, "⟲ con «apagado»: nadie sube (%s)" % d.get("error"))
    c, _d = enviar(B, "x", pase=pase(B))
    ok(c == 503, "⟲ ni envía (ni los autorizados)")
    c, l = pedir(A, "/subidas/lista", {})
    ok(c == 200 and l["apagado"], "la lista avisa que está apagado")
    c, _d = pedir(B, "/subidas/volver", {"pase": pase(B), "release": l["estados"][1]["release"]})
    ok(c == 200, "pero VOLVER ATRÁS sigue andando (es lo que se usa en una emergencia)")
    os.remove(interruptor)
    c, _d = subir(A, "isla.pak", pak({"a.dds": b"DDS"}))
    ok(c == 200, "sin el archivo, se vuelve a subir")
    pedir(A, "/subidas/descartar", {})

    print("14 · topes de lugar y de ritmo (§37)")
    tope, S.TAM_MAX_TOTAL = S.TAM_MAX_TOTAL, sum(os.path.getsize(os.path.join(rels, "_subidas", "blobs", n)) for n in blobs()) + 100
    c, d = subir(A, "grande.pak", pak({"g.dds": b"DDS" + b"g" * 500}))
    ok(c == 507, "⟲ si el disco de subidas está lleno: 507 (%s)" % d.get("error"))
    S.TAM_MAX_TOTAL = tope
    S.SUBIDAS_MAX_POR_HORA, ritmo = 3, S.SUBIDAS_MAX_POR_HORA
    ps.SUBIDAS._ritmo.clear()
    cs = [subir(A, "r%d.pak" % i, pak({"r.dds": b"DDS r%d" % i}))[0] for i in range(4)]
    ok(cs == [200, 200, 200, 429], "⟲ más de N archivos por hora: 429 (%s)" % cs)
    S.SUBIDAS_MAX_POR_HORA = ritmo
    pedir(A, "/subidas/descartar", {})

    print("15 · reiniciar el server de parches")
    vig = prueba()["version"]
    ps.SUBIDAS = None
    ok(prueba()["version"] == vig, "se acuerda de la última release de prueba (estado.json)")
    ps.CFG["current"] = "prod2"
    release(rels, "prod2", {"R2Beat.exe": EXE, "isla.pak": NOCHE})
    ps.SUBIDAS = None
    ok(prueba()["version"] == "prod1-nieve", "⟲ si cambió PROD, vuelve a la de la configuración (lo subido era sobre la vieja)")
    srv.shutdown()
    print("\n%s" % ("✔ probar_subidas: todo bien" if not fallos else "✘ %d fallo(s)" % len(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
