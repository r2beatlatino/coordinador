# -*- coding: utf-8 -*-
"""probar_parches_r2 — la release de PROD del 2013 se baja de Cloudflare R2, con la CDN de respaldo. 18-nov-2026.

Benja: «R2 descarga principal, CDN del VPS secundaria; que no se choque con el cliente del test server; que no se
exceda de los 10 GB por accidente». El server de parches pone `base` = R2 SÓLO para la release de prod y SÓLO si
`releases/r2.json` (lo escribe `usa/r2_al_dia.py` después de verificar) dice que está entera allá. Todo lo demás —la
de prueba, un envío, una release que todavía no se subió— sigue por la CDN como antes.

    python -X utf8 pruebas/probar_parches_r2.py
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(RAIZ, "herramientas", "contenedores", "parches")
fallos = []

CDN = "https://cdn.ejemplo/r2beat2013"
R2 = "https://r2.ejemplo"


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que, flush=True)
    if not cond:
        fallos.append(que)


def modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    tmp = tempfile.mkdtemp(prefix="r2_parches_")
    ps = modulo("patchserver_r2", os.path.join(P, "patchserver.py"))
    arr = modulo("arranque_r2", os.path.join(P, "arranque.py"))
    try:
        print("1 · arranque.py")
        ok(arr.armar_config({"PARCHES_URL_R2": R2})["file_base_url_r2"] == R2, "PARCHES_URL_R2 llega a la config")
        ok(arr.armar_config({})["file_base_url_r2"] == "", "⟲ sin la variable: vacía (nadie va a R2)")

        rels = os.path.join(tmp, "releases")
        for r in ("r_prod", "r_prueba", "r_nueva"):
            os.makedirs(os.path.join(rels, r))
            json.dump({"version": r, "files": []}, open(os.path.join(rels, r, "manifest.json"), "w"))
        ps.CFG.clear()
        ps.CFG.update(releases_dir=rels, current="r_prod", current_prueba="r_prueba", file_base_url=CDN, file_base_url_r2=R2)
        marca = os.path.join(rels, "r2.json")

        def base(canal=None):
            rel, quien = ps.release_de(canal) if canal != "envio" else ("r_prueba", "envio")
            m = ps.manifest_de_release(rel, quien)
            return m["base"], m.get("respaldo")

        print("2 · sin r2.json: todo por la CDN (la subida no terminó o falló)")
        ok(base() == (CDN + "/r_prod/", None), "⟲ prod va por la CDN, sin respaldo")

        print("3 · r2.json dice r_prod")
        json.dump({"release": "r_prod"}, open(marca, "w"))
        os.utime(marca, (1, 1))   # (un mtime distinto del de 'no existía')
        ok(base() == (R2 + "/r_prod/", CDN + "/r_prod/"), "prod: base = R2 y respaldo = la CDN")
        ok(base("prueba") == (CDN + "/r_prueba/", None), "⟲ el test server NO va a R2")
        ok(base("envio")[0].startswith("/files/"), "⟲ un envío sin aprobar sigue por /files")

        print("4 · prod cambia a una release que R2 todavía no tiene")
        ps.CFG["current"] = "r_nueva"
        ok(base() == (CDN + "/r_nueva/", None), "⟲ la nueva va por la CDN hasta que r2_al_dia la suba")
        json.dump({"release": "r_nueva"}, open(marca, "w"))
        os.utime(marca, (2, 2))
        ok(base()[0] == R2 + "/r_nueva/", "y en cuanto r2.json la nombra, va a R2 (sin reiniciar: la caché mira r2.json)")

        print("5 · sin PARCHES_URL_R2 no hay R2, aunque haya r2.json")
        ps.CFG["file_base_url_r2"] = ""
        os.utime(marca, (3, 3))
        ok(base() == (CDN + "/r_nueva/", None), "⟲ R2 apagado: todo por la CDN")

        print("6 · un r2.json roto no rompe el manifest")
        ps.CFG["file_base_url_r2"] = R2
        open(marca, "w").write("{roto")
        os.utime(marca, (4, 4))
        ok(base() == (CDN + "/r_nueva/", None), "⟲ r2.json ilegible: por la CDN")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("✘ %d fallas" % len(fallos) if fallos else "✔ todo bien"))
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
