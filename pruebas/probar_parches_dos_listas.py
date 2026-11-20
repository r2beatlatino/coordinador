# -*- coding: utf-8 -*-
"""probar_parches_dos_listas — el servidor de parches con DOS listas del cliente: prod y PRUEBA. 16-nov-2026.

Benja: un solo cliente instalado; prod y el server de prueba usan listas distintas en la CDN (TOPOLOGIA §33.1).
`GET /manifest` = la de prod; `GET /manifest?canal=prueba` = la de prueba (`PARCHES_RELEASE_PRUEBA`). Si no hay una
de prueba configurada, sirve la de prod. Corre el `patchserver.py` DE VERDAD en un hilo, con dos releases de mentira.

    python -X utf8 pruebas/probar_parches_dos_listas.py
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(RAIZ, "herramientas", "contenedores", "parches")
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que, flush=True)
    if not cond:
        fallos.append(que)


def modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def release(raiz, nombre, archivos):
    d = os.path.join(raiz, nombre)
    os.makedirs(d)
    fs = []
    for n, datos in archivos.items():
        open(os.path.join(d, n), "wb").write(datos)
        fs.append({"path": n, "md5": hashlib.md5(datos).hexdigest(), "size": len(datos)})
    json.dump({"version": nombre, "files": fs}, open(os.path.join(d, "manifest.json"), "w"))


def main():
    tmp = tempfile.mkdtemp(prefix="r2_dos_listas_")
    ps = modulo("patchserver_dl", os.path.join(P, "patchserver.py"))
    arr = modulo("arranque_dl", os.path.join(P, "arranque.py"))
    try:
        print("1 · arranque.py")
        c = arr.armar_config({"PARCHES_RELEASE_ACTIVA": "r_prod", "PARCHES_RELEASE_PRUEBA": "r_prueba"})
        ok(c["current"] == "r_prod" and c["current_prueba"] == "r_prueba", "PARCHES_RELEASE_PRUEBA llega a la config")
        ok(arr.armar_config({"PARCHES_RELEASE_ACTIVA": "r_prod"})["current_prueba"] == "", "⟲ sin la variable: vacía")

        print("2 · el servidor de parches, con las dos listas")
        rels = os.path.join(tmp, "releases")
        comun = b"R2Beat.exe igual en las dos" * 100
        release(rels, "r_prod", {"R2Beat.exe": comun, "rnr_ui_bg_isla_hw.pak": b"ISLA DE NOCHE" * 50})
        release(rels, "r_prueba", {"R2Beat.exe": comun, "rnr_ui_bg_isla_hw.pak": b"ISLA DE NIEVE" * 40})
        ps.CFG.clear()
        ps.CFG.update(listen="127.0.0.1", port=0, clean_db=os.path.join(tmp, "no.db"), status_file=os.path.join(tmp, "no.json"),
                      releases_dir=rels, current="r_prod", current_prueba="r_prueba", token_ttl_sec=3600,
                      quota_mb_per_token=1500, per_ip_quota_mb_per_hour=3000, per_ip_auth_per_hour=30, ban_minutes=30,
                      login_mode="", file_base_url="")
        srv = ps.ThreadingHTTPServer(("127.0.0.1", 0), ps.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d" % srv.server_address[1]
        tok = "t" * 32
        ps.TOKENS[tok] = {"uid": 1, "user": "x", "exp": time.time() + 600, "used": 0, "ip": "127.0.0.1"}

        def get(ruta):
            req = urllib.request.Request(url + ruta, headers={"Authorization": "Bearer " + tok})
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                return e.code, e.read()

        def isla(m):
            return next((f for f in m.get("files", []) if f["path"] == "rnr_ui_bg_isla_hw.pak"), {})

        def man(ruta):
            c, b = get(ruta)
            try:
                return c, json.loads(b)
            except ValueError:
                return c, {}

        cp, mp = man("/manifest")
        cq, mq = man("/manifest?canal=prueba")
        ok(cp == 200 and mp.get("version") == "r_prod" and mp.get("canal") == "prod" and mp.get("base") == "/files/r_prod/",
           "/manifest = la lista de PROD (base /files/r_prod/)")
        ok(cq == 200 and mq.get("version") == "r_prueba" and mq.get("canal") == "prueba" and mq.get("base") == "/files/r_prueba/",
           "/manifest?canal=prueba = la lista de PRUEBA (base /files/r_prueba/)")
        ok(isla(mp).get("md5") and isla(mq).get("md5") and isla(mp)["md5"] != isla(mq)["md5"], "la isla es distinta en cada lista")
        ok(mq.get("files") and [f["md5"] for f in mp.get("files", []) if f["path"] == "R2Beat.exe"] == [f["md5"] for f in mq["files"] if f["path"] == "R2Beat.exe"],
           "y lo demás es igual (el launcher sólo baja lo distinto)")
        c1, d1 = get(mq.get("base", "/x/") + "rnr_ui_bg_isla_hw.pak")
        ok(c1 == 200 and hashlib.md5(d1).hexdigest() == isla(mq).get("md5"), "el archivo de la isla de prueba se baja con su md5")
        c2, d2 = get(mp.get("base", "/x/") + "rnr_ui_bg_isla_hw.pak")
        ok(c2 == 200 and hashlib.md5(d2).hexdigest() == isla(mp).get("md5"), "…y el de prod, el suyo")
        ok(man("/manifest?canal=otro")[1].get("version") == "r_prod", "⟲ revés: un canal desconocido = prod")
        ok(man("/manifest?canal=prueba&x=1")[1].get("version") == "r_prueba", "con más parámetros sigue andando")
        ps.CFG["current_prueba"] = ""
        m3 = man("/manifest?canal=prueba")[1]
        ok(m3.get("version") == "r_prod" and m3.get("canal") == "prod", "⟲ sin lista de prueba configurada, el de prueba recibe la de prod")
        ok(man("/manifest")[0] == 200 and man("/manifest")[1].get("version") == "r_prod", "y /manifest sigue siendo prod")
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%s" % ("✔ probar_parches_dos_listas: todo bien" if not fallos else "✘ %d fallo(s)" % len(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
