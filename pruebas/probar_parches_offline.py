# -*- coding: utf-8 -*-
"""probar_parches_offline — `GET /offline/…` del servidor de parches: el MINI SERVER del modo offline (16-nov-2026).

Público y de sólo lectura, desde `<releases>/_offline/`. Cada chequeo con su revés (⟲): nada fuera de la carpeta.

    python -X utf8 pruebas/probar_parches_offline.py
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(RAIZ, "herramientas", "contenedores", "parches")
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que, flush=True)
    if not cond:
        fallos.append(que)


def main():
    tmp = tempfile.mkdtemp(prefix="r2_offline_")
    try:
        sys.path.insert(0, P)
        spec = importlib.util.spec_from_file_location("patchserver_off", os.path.join(P, "patchserver.py"))
        ps = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ps)
        rels = os.path.join(tmp, "releases")
        off = os.path.join(rels, "_offline")
        os.makedirs(os.path.join(off, "archivos", "python"))
        man = {"version": "x1", "files": [{"path": "python/python.exe", "size": 5, "md5": "-"}]}
        json.dump(man, open(os.path.join(off, "manifest.json"), "w"))
        open(os.path.join(off, "archivos", "python", "python.exe"), "wb").write(b"MZexe")
        open(os.path.join(tmp, "secreto.txt"), "w").write("no")
        open(os.path.join(rels, "otra.txt"), "w").write("no")
        ps.CFG.clear()
        ps.CFG.update(listen="127.0.0.1", port=0, clean_db=os.path.join(tmp, "no.db"), status_file=os.path.join(tmp, "s.json"),
                      releases_dir=rels, current="prod1", token_ttl_sec=3600, quota_mb_per_token=1500,
                      per_ip_quota_mb_per_hour=3000, per_ip_auth_per_hour=30, ban_minutes=30, file_base_url="")
        srv = ps.ThreadingHTTPServer(("127.0.0.1", 0), ps.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d" % srv.server_address[1]

        def get(ruta):
            try:
                with urllib.request.urlopen(url + ruta, timeout=10) as r:
                    return r.status, r.read(), dict(r.headers)
            except urllib.error.HTTPError as e:
                return e.code, e.read(), {}

        c, b, h = get("/offline/manifest.json")
        ok(c == 200 and json.loads(b)["version"] == "x1" and "json" in h.get("Content-Type", ""),
           "el manifest se baja SIN token (público)")
        ok(h.get("Cache-Control") == "no-cache", "el manifest no se guarda en caché (siempre el último)")
        c, b, _ = get("/offline/archivos/python/python.exe")
        ok(c == 200 and b == b"MZexe", "un archivo, igual byte a byte")
        for mala in ("/offline/../secreto.txt", "/offline/%2e%2e/secreto.txt", "/offline/archivos/../../otra.txt",
                     "/offline/%2e%2e%2fotra.txt", "/offline/..%5cotra.txt", "/offline/", "/offline/archivos/python"):
            c, b, _ = get(mala)
            ok(c == 404 and b"no" != b, "⟲ %s: 404 (nada fuera de la carpeta, ni carpetas)" % mala)
        c, _b, _ = get("/offline/no_existe.bin")
        ok(c == 404, "⟲ lo que no existe: 404")
        c, _b, _ = get("/files/prod1/x.pak")
        ok(c == 401, "⟲ /files/ sigue pidiendo token (lo público es SÓLO /offline/)")
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%s" % ("✔ probar_parches_offline: todo bien" if not fallos else "✘ %d fallo(s)" % len(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
