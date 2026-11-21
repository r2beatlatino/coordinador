# -*- coding: utf-8 -*-
"""eda_prueba_cliente — ★ 21-nov-2026: el cliente del server de PRUEBA de EDA = el publicado + lo que develop cambió.

Benja: «el launcher se actualizó pero el juego no». El server de prueba (develop → eda-prueba) usaba la lista de
prod tal cual: una dll compilada que el equipo de EDA sube a `exe/` en develop no llegaba nunca al de prueba. Ahora:

  · se parte de la versión PUBLICADA (`/opt/eda/manifiesto/eda.json`, la que sale de main)
  · cada archivo de `exe/` del commit de develop (sin los .md) que sea DISTINTO al publicado — o que no esté — lo pisa
  · la carpeta nueva (`/opt/eda/files-eda/<versión>-prueba-<huella>/`) son ENLACES DUROS a la publicada (el Data.dat
    de 345 MB no se copia) y sólo los archivos de develop son copias propias. ⛔ Nunca se escribe ADENTRO de un
    enlace: se borra el enlace y se copia (si no, se pisaría también el archivo de PROD)
  · la VERSIÓN de la lista no cambia: el launcher no acepta una menor que la última, y prod y prueba comparten esa
    marca. El launcher compara archivo por archivo (md5), así que igual baja sólo lo distinto, al ir y al volver.
  · sin nada distinto, la lista queda IGUAL a la publicada (misma carpeta).

Se lee de git (`HEAD` del clon de develop), no de la carpeta: así no se mezcla con un `git reset` a medias.

    python3 eda_prueba_cliente.py armar <eda.json> <clon develop> <files-eda> <salida.json>
    python3 eda_prueba_cliente.py control          # ★ con sus controles al revés, en una carpeta temporal
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

GUARDAR = 5                       # carpetas «-prueba-» que se dejan (la actual + las anteriores)


def git(repo, *args, binario=False):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True)
    return r.stdout if binario else r.stdout.decode("utf-8")


def archivos_develop(repo):
    """{nombre: bytes} de `exe/` en HEAD: sólo archivos de la raíz de exe/, sin los .md."""
    out = {}
    for linea in git(repo, "ls-tree", "HEAD", "exe/").splitlines():
        meta, ruta = linea.split("\t", 1)
        _modo, tipo, sha = meta.split()
        nombre = ruta[len("exe/"):]
        if tipo != "blob" or "/" in nombre or nombre.lower().endswith(".md"):
            continue
        out[nombre] = git(repo, "cat-file", "blob", sha, binario=True)
    return out


def armar(fuente, repo, files_eda, salida):
    d = json.load(open(fuente, encoding="utf-8"))
    base = d["base"].rstrip("/")
    publicada = base.rsplit("/", 1)[-1]
    origen = os.path.join(files_eda, publicada)
    if not os.path.isdir(origen):
        raise SystemExit(f"⛔ no está la carpeta publicada {origen}")
    por_ruta = {f["path"]: f for f in d["files"]}
    distintos = {}
    for nombre, datos in archivos_develop(repo).items():
        md5 = hashlib.md5(datos).hexdigest()
        f = por_ruta.get(nombre)
        if f is None or f.get("md5", "").lower() != md5 or "partes" in f:
            if f is not None and "partes" in f:
                continue                                 # (un archivo en partes no se pisa desde develop)
            distintos[nombre] = (datos, md5)
    if distintos:
        huella = hashlib.sha256("".join(f"{n}:{m};" for n, (_, m) in sorted(distintos.items())).encode()).hexdigest()[:10]
        carpeta = f"{publicada}-prueba-{huella}"
        destino = os.path.join(files_eda, carpeta)
        if not os.path.isdir(destino):
            tmp = destino + ".armando"
            shutil.rmtree(tmp, ignore_errors=True)
            subprocess.run(["cp", "-al", origen, tmp], check=True)          # enlaces duros: no ocupa lugar
            for nombre, (datos, md5) in distintos.items():
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
        limpiar(files_eda, publicada, carpeta)
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    return sorted(distintos)


def limpiar(files_eda, publicada, actual):
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
        files = os.path.join(t, "files-eda")
        pub = os.path.join(files, "2026.11.19-abc")
        os.makedirs(pub)
        cont = {"Data.dat": b"D" * 1000, "d3d9.dll": b"dll-de-main", "eda_d3d9.ini": b"ini"}
        for n, b in cont.items():
            open(os.path.join(pub, n), "wb").write(b)
        md5 = lambda b: hashlib.md5(b).hexdigest()
        lista = {"version": "2026.11.19", "base": "https://x/files-eda/2026.11.19-abc/", "servidor": "h:1", "canje": "https://c",
                 "files": [{"path": n, "size": len(b), "md5": md5(b)} for n, b in cont.items()]}
        fuente = os.path.join(t, "eda.json")
        json.dump(lista, open(fuente, "w"))
        repo = os.path.join(t, "repo")
        os.makedirs(os.path.join(repo, "exe"))
        g = lambda *a: subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True)
        g("init", "-q"); g("config", "user.email", "x@x"); g("config", "user.name", "x")
        for n in ("d3d9.dll", "eda_d3d9.ini"):
            open(os.path.join(repo, "exe", n), "wb").write(cont[n])
        open(os.path.join(repo, "exe", "LEEME.md"), "w").write("doc")
        g("add", "-A"); g("commit", "-qm", "igual")
        sal = os.path.join(t, "prueba.json")

        print("1 · develop igual a lo publicado")
        r = armar(fuente, repo, files, sal)
        d = json.load(open(sal))
        ok(r == [] and d == lista, "⟲ nada distinto: la lista es la publicada tal cual (misma carpeta)")
        ok(sorted(os.listdir(files)) == ["2026.11.19-abc"], "⟲ y no se armó ninguna carpeta")

        print("2 · develop sube una dll nueva (y un archivo nuevo)")
        open(os.path.join(repo, "exe", "d3d9.dll"), "wb").write(b"dll-de-DEVELOP")
        open(os.path.join(repo, "exe", "nuevo.dll"), "wb").write(b"nuevo")
        open(os.path.join(repo, "exe", "LEEME.md"), "w").write("doc cambiada")
        g("add", "-A"); g("commit", "-qm", "dll nueva")
        open(os.path.join(repo, "exe", "d3d9.dll"), "wb").write(b"SIN COMMIT")      # ⟲ lo que no está en HEAD no va
        r = armar(fuente, repo, files, sal)
        d = json.load(open(sal))
        f = {x["path"]: x for x in d["files"]}
        ok(r == ["d3d9.dll", "nuevo.dll"], f"los distintos: la dll y el nuevo ({r}) — ⟲ no el .md")
        ok(f["d3d9.dll"]["md5"] == md5(b"dll-de-DEVELOP") and f["nuevo.dll"]["size"] == 5, "la lista trae los de develop (del COMMIT, ⟲ no lo sin commitear)")
        ok(d["version"] == lista["version"], "★ la versión NO cambia (el launcher no acepta una menor al volver a prod)")
        carp = d["base"].rstrip("/").rsplit("/", 1)[-1]
        ok(carp.startswith("2026.11.19-abc-prueba-") and d["base"].startswith("https://x/files-eda/"), f"carpeta propia: {carp}")
        nueva = os.path.join(files, carp)
        ok(open(os.path.join(nueva, "d3d9.dll"), "rb").read() == b"dll-de-DEVELOP", "en la carpeta nueva, la dll de develop")
        ok(open(os.path.join(pub, "d3d9.dll"), "rb").read() == b"dll-de-main", "★ ⟲ la de PROD quedó intacta (se borró el enlace, no se escribió adentro)")
        ok(os.stat(os.path.join(nueva, "Data.dat")).st_ino == os.stat(os.path.join(pub, "Data.dat")).st_ino, "el Data.dat es un ENLACE (no ocupa lugar)")
        ok(f["Data.dat"]["md5"] == md5(cont["Data.dat"]), "⟲ lo que develop no tocó, igual que lo publicado")

        print("3 · otra vez lo mismo, y después develop vuelve a ser igual")
        antes = sorted(os.listdir(files))
        ok(armar(fuente, repo, files, sal) == r and sorted(os.listdir(files)) == antes, "⟲ repetir no arma otra carpeta")
        open(os.path.join(repo, "exe", "d3d9.dll"), "wb").write(cont["d3d9.dll"])
        os.remove(os.path.join(repo, "exe", "nuevo.dll"))
        g("add", "-A"); g("commit", "-qm", "vuelve")
        ok(armar(fuente, repo, files, sal) == [] and json.load(open(sal)) == lista, "develop igual otra vez: vuelve la lista publicada")
    finally:
        shutil.rmtree(t, ignore_errors=True)
    print("\n✔ todo bien" if not mal else f"\n✘ {mal} mal")
    return 1 if mal else 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "control":
        sys.exit(control())
    if len(sys.argv) == 6 and sys.argv[1] == "armar":
        print(" ".join(armar(*sys.argv[2:])) or "-")
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
