# -*- coding: utf-8 -*-
"""eda_prueba_cliente — ★ 21-nov-2026: el cliente del server de PRUEBA de EDA = el publicado + el de DEVELOP.

Benja: «el launcher se actualizó pero el juego no» / «¿la dll no debió compilarse al cambiar el código?». Sí se
compila: el CI de r2beatlatino/EDA (trabajo «cliente-develop», herramientas/dll_d3d9/canal.py), en cada push a
develop, compila la d3d9.dll y la deja con su eda_d3d9.ini y la lista `cliente-develop.json` en la release
«cliente-develop». Esta herramienta lleva ESE cliente al server de prueba:

  · se parte de la versión PUBLICADA (`/opt/eda/manifiesto/eda.json`, la que sale de main)
  · cada archivo de `cliente-develop.json` (dll, ini, y el exe por su `url`) se baja y se comprueba (sha256 y md5
    de la lista); si es DISTINTO al publicado — o no está — lo pisa. ⛔ Uno que no cierra = no se usa NADA (falla y
    la lista de prueba sigue con lo publicado)
  · la carpeta nueva (`/opt/eda/files-eda/<versión>-prueba-<huella>/`) son ENLACES DUROS a la publicada (el Data.dat
    de 345 MB no se copia) y sólo lo de develop son copias propias. ⛔ Nunca se escribe ADENTRO de un enlace: se
    borra el enlace y se copia (si no, se pisaría también el archivo de PROD)
  · la VERSIÓN de la lista no cambia: el launcher no acepta una menor que la última, y prod y prueba comparten esa
    marca. El launcher compara archivo por archivo (md5), así que baja sólo lo distinto, al ir y al volver
  · sin nada distinto, la lista queda IGUAL a la publicada (misma carpeta)
  · lo bajado se guarda por md5 en `<cache>`: cada 5 min sólo se baja la lista (1 KB)

    python3 eda_prueba_cliente.py armar <eda.json> <url de cliente-develop.json> <files-eda> <cache> <salida.json>
    python3 eda_prueba_cliente.py control          # ★ con sus controles al revés, en una carpeta temporal
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

GUARDAR = 5                       # carpetas «-prueba-» que se dejan (la actual + las anteriores)
LISTA_CANAL = "https://github.com/r2beatlatino/EDA/releases/download/cliente-develop/cliente-develop.json"


def bajar(url, tope):
    req = urllib.request.Request(url, headers={"User-Agent": "enenos-eda-prueba"})
    with urllib.request.urlopen(req, timeout=60) as r:
        datos = r.read(tope + 1)
    if len(datos) > tope:
        raise ValueError(f"{url}: más de {tope} bytes")
    return datos


def archivos_canal(url_lista, cache, publicados):
    """{nombre: (bytes, md5)} del cliente de develop, cada uno comprobado. Lo que ya es igual a lo publicado no se baja."""
    lista = json.loads(bajar(url_lista, 1 << 20))
    base = lista.get("base") or url_lista.rsplit("/", 1)[0] + "/"
    os.makedirs(cache, exist_ok=True)
    out = {}
    for f in lista.get("files", []):
        nombre, md5, sha = f.get("path", ""), str(f.get("md5", "")).lower(), str(f.get("sha256", "")).lower()
        if not nombre or "/" in nombre or "\\" in nombre or nombre.startswith(".") or len(md5) != 32 or len(sha) != 64:
            raise ValueError(f"la lista de develop trae un archivo inválido: {nombre!r}")
        if publicados.get(nombre, {}).get("md5", "").lower() == md5:
            continue                                         # igual a lo publicado: ni se baja
        guardado = os.path.join(cache, md5)
        if os.path.isfile(guardado):
            datos = open(guardado, "rb").read()
        else:
            datos = bajar(f.get("url") or base + nombre, 64 << 20)
        if hashlib.md5(datos).hexdigest() != md5 or hashlib.sha256(datos).hexdigest() != sha or len(datos) != f.get("size"):
            raise ValueError(f"{nombre}: no es lo de la lista de develop (¿el CI está subiendo? se reintenta)")
        if not os.path.isfile(guardado):
            with open(guardado + ".tmp", "wb") as fh:
                fh.write(datos)
            os.replace(guardado + ".tmp", guardado)
        out[nombre] = (datos, md5)
    return out


def armar(fuente, url_lista, files_eda, cache, salida):
    d = json.load(open(fuente, encoding="utf-8"))
    base = d["base"].rstrip("/")
    publicada = base.rsplit("/", 1)[-1]
    origen = os.path.join(files_eda, publicada)
    if not os.path.isdir(origen):
        raise SystemExit(f"⛔ no está la carpeta publicada {origen}")
    por_ruta = {f["path"]: f for f in d["files"]}
    distintos = {n: v for n, v in archivos_canal(url_lista, cache, por_ruta).items() if "partes" not in por_ruta.get(n, {})}
    if distintos:
        huella = hashlib.sha256("".join(f"{n}:{m};" for n, (_, m) in sorted(distintos.items())).encode()).hexdigest()[:10]
        carpeta = f"{publicada}-prueba-{huella}"
        destino = os.path.join(files_eda, carpeta)
        if not os.path.isdir(destino):
            tmp = destino + ".armando"
            shutil.rmtree(tmp, ignore_errors=True)
            subprocess.run(["cp", "-al", origen, tmp], check=True)          # enlaces duros: no ocupa lugar
            for nombre, (datos, _md5) in distintos.items():
                p = os.path.join(tmp, nombre)
                if os.path.lexists(p):
                    os.unlink(p)                     # ⛔ el enlace se BORRA: escribirle adentro pisaría el de prod
                with open(p, "wb") as fh:
                    fh.write(datos)
                os.chmod(p, 0o755 if nombre.lower().endswith((".exe", ".dll")) else 0o644)
            os.rename(tmp, destino)
        for nombre, (datos, md5) in distintos.items():
            nuevo = {"path": nombre, "size": len(datos), "md5": md5}
            if nombre in por_ruta:
                por_ruta[nombre].clear()
                por_ruta[nombre].update(nuevo)
            else:
                d["files"].append(nuevo)
        d["base"] = base.rsplit("/", 1)[0] + "/" + carpeta + "/"
        limpiar(files_eda, carpeta)
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    return sorted(distintos)


def limpiar(files_eda, actual):
    viejas = sorted((c for c in os.listdir(files_eda) if "-prueba-" in c and c != actual and not c.endswith(".armando")),
                    key=lambda c: os.path.getmtime(os.path.join(files_eda, c)), reverse=True)
    for c in viejas[GUARDAR - 1:]:
        shutil.rmtree(os.path.join(files_eda, c), ignore_errors=True)


# ───────────────────────────────────────────────────────────────── control
def control():
    mal = 0

    def ok(c, que):
        nonlocal mal
        print(("  ✔ " if c else "  ✘ ") + que)
        mal += 0 if c else 1

    t = tempfile.mkdtemp(prefix="eda_prueba_cliente_")
    try:
        files, cache = os.path.join(t, "files-eda"), os.path.join(t, "cache")
        pub = os.path.join(files, "2026.11.19-abc")
        os.makedirs(pub)
        cont = {"Data.dat": b"D" * 1000, "d3d9.dll": b"dll-de-main", "eda_d3d9.ini": b"ini", "EDA_limpio.exe": b"exe"}
        for n, b in cont.items():
            open(os.path.join(pub, n), "wb").write(b)
        md5 = lambda b: hashlib.md5(b).hexdigest()
        sha = lambda b: hashlib.sha256(b).hexdigest()
        lista = {"version": "2026.11.19", "base": "https://x/files-eda/2026.11.19-abc/", "servidor": "h:1", "canje": "https://c",
                 "files": [{"path": n, "size": len(b), "md5": md5(b)} for n, b in cont.items()]}
        fuente = os.path.join(t, "eda.json")
        json.dump(lista, open(fuente, "w"))
        rel = os.path.join(t, "release")
        os.makedirs(rel)
        url = "file:///" + os.path.join(rel, "cliente-develop.json").replace("\\", "/").lstrip("/")

        def publicar_canal(archivos, rotos=()):
            for n, b in archivos.items():
                open(os.path.join(rel, n), "wb").write(b"ROTO" if n in rotos else b)
            json.dump({"base": "file:///" + rel.replace("\\", "/").lstrip("/") + "/",
                       "files": [{"path": n, "size": len(b), "md5": md5(b), "sha256": sha(b)} for n, b in archivos.items()]},
                      open(os.path.join(rel, "cliente-develop.json"), "w"))
        sal = os.path.join(t, "prueba.json")

        print("1 · develop igual a lo publicado")
        publicar_canal({"d3d9.dll": cont["d3d9.dll"], "eda_d3d9.ini": cont["eda_d3d9.ini"], "EDA_limpio.exe": cont["EDA_limpio.exe"]})
        r = armar(fuente, url, files, cache, sal)
        ok(r == [] and json.load(open(sal)) == lista, "⟲ nada distinto: la lista es la publicada tal cual (misma carpeta)")
        ok(sorted(os.listdir(files)) == ["2026.11.19-abc"] and not os.listdir(cache), "⟲ no se armó carpeta ni se bajó nada")

        print("2 · el CI publica una dll nueva (y un archivo nuevo)")
        publicar_canal({"d3d9.dll": b"dll-de-DEVELOP", "eda_d3d9.ini": cont["eda_d3d9.ini"], "nuevo.dll": b"nuevo",
                        "EDA_limpio.exe": cont["EDA_limpio.exe"]})
        r = armar(fuente, url, files, cache, sal)
        d = json.load(open(sal))
        f = {x["path"]: x for x in d["files"]}
        ok(r == ["d3d9.dll", "nuevo.dll"], f"los distintos: la dll y el nuevo ({r}) — ⟲ no lo que es igual")
        ok(f["d3d9.dll"]["md5"] == md5(b"dll-de-DEVELOP") and f["nuevo.dll"]["size"] == 5, "la lista trae los de develop")
        ok(d["version"] == lista["version"], "★ la versión NO cambia (el launcher no acepta una menor al volver a prod)")
        carp = d["base"].rstrip("/").rsplit("/", 1)[-1]
        ok(carp.startswith("2026.11.19-abc-prueba-") and d["base"].startswith("https://x/files-eda/"), f"carpeta propia: {carp}")
        nueva = os.path.join(files, carp)
        ok(open(os.path.join(nueva, "d3d9.dll"), "rb").read() == b"dll-de-DEVELOP", "en la carpeta nueva, la dll de develop")
        ok(open(os.path.join(pub, "d3d9.dll"), "rb").read() == b"dll-de-main", "★ ⟲ la de PROD quedó intacta (se borró el enlace, no se escribió adentro)")
        ok(os.stat(os.path.join(nueva, "Data.dat")).st_ino == os.stat(os.path.join(pub, "Data.dat")).st_ino, "el Data.dat es un ENLACE (no ocupa lugar)")
        ok(f["Data.dat"]["md5"] == md5(cont["Data.dat"]), "⟲ lo que develop no tocó, igual que lo publicado")

        print("3 · repetir, una descarga rota, y develop otra vez igual")
        antes = sorted(os.listdir(files))
        os.remove(os.path.join(rel, "d3d9.dll"))                       # ⟲ la 2.ª vez sale del cache (no se baja)
        ok(armar(fuente, url, files, cache, sal) == r and sorted(os.listdir(files)) == antes, "⟲ repetir no arma otra carpeta ni baja de nuevo")
        publicar_canal({"d3d9.dll": b"dll-OTRA", "EDA_limpio.exe": cont["EDA_limpio.exe"]}, rotos=("d3d9.dll",))
        try:
            armar(fuente, url, files, cache, sal)
            ok(False, "⟲ una dll que no es la de la lista: tiene que fallar")
        except ValueError:
            ok(sorted(os.listdir(files)) == antes, "⟲ una dll que no es la de la lista: falla y no arma nada")
        publicar_canal({"d3d9.dll": cont["d3d9.dll"], "EDA_limpio.exe": cont["EDA_limpio.exe"]})
        ok(armar(fuente, url, files, cache, sal) == [] and json.load(open(sal)) == lista, "develop igual otra vez: vuelve la lista publicada")
    finally:
        shutil.rmtree(t, ignore_errors=True)
    print("\n✔ todo bien" if not mal else f"\n✘ {mal} mal")
    return 1 if mal else 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "control":
        sys.exit(control())
    if len(sys.argv) == 7 and sys.argv[1] == "armar":
        try:
            print(" ".join(armar(*sys.argv[2:])) or "-")
        except (OSError, ValueError) as e:
            print(f"no se pudo: {e}")
            sys.exit(1)
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
