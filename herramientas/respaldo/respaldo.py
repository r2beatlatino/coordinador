# -*- coding: utf-8 -*-
"""respaldo — «Generar backup» del mundo Eñeños: UN archivo cifrado con las bases, la configuración y los secretos.

    python respaldo.py armar  --lista respaldo.json --origen /origen --salida /salida --para llave_publica.txt
    python respaldo.py abrir  --archivo X.tar.age --llave mi_llave.txt --destino carpeta/
    python respaldo.py ver    --archivo X.tar.age --llave mi_llave.txt          # sólo comprueba, no deja nada

Cómo es por dentro (lo lee también RECONSTRUIR.md):
- La LISTA (`respaldo.json`) dice qué se guarda: cada cosa es una base SQLite, un archivo o una carpeta, con su ruta en
  la máquina (relativa a la raíz `/`). Un juego nuevo = una línea más. Lo `"opcional": true` que no está se anota y se
  sigue; lo obligatorio que falta FRENA el respaldo (un respaldo incompleto que parece completo es lo peor).
- Las bases se copian con la API de respaldo de SQLite (`Connection.backup`): copiar el .db a mano con WAL pierde lo
  que está en el -wal. Cada copia pasa `PRAGMA integrity_check` y se cuentan sus filas por tabla.
- Adentro va `MANIFIESTO.json`: qué se guardó, de dónde, su sha256, su tamaño y las filas de cada tabla. `abrir`/`ver`
  comprueban todo eso.
- Se cifra con `age` para una LLAVE PÚBLICA: la máquina que respalda puede cifrar pero nunca descifrar. La llave
  privada la tiene sólo Eñeños (protegida con su contraseña).
"""
import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

VERSION = 1
TIPOS = {"sqlite", "archivo", "carpeta"}


class Falla(Exception):
    pass


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def leer_lista(ruta):
    lista = json.loads(Path(ruta).read_text("utf-8"))
    cosas = lista.get("cosas")
    if not isinstance(cosas, list) or not cosas:
        raise Falla("la lista no tiene «cosas»")
    vistos = set()
    for c in cosas:
        if c.get("tipo") not in TIPOS or not c.get("nombre") or not c.get("ruta"):
            raise Falla(f"cosa mal escrita en la lista: {c}")
        if c["nombre"] in vistos:
            raise Falla(f"nombre repetido en la lista: {c['nombre']}")
        if c["ruta"].startswith("/") or ".." in Path(c["ruta"]).parts:
            raise Falla(f"la ruta va relativa a la raíz y sin «..»: {c['ruta']}")
        vistos.add(c["nombre"])
    return cosas


def copiar_sqlite(origen, destino):
    """Copia en vivo con la API de respaldo; abre el original en sólo lectura. Devuelve {tabla: filas}."""
    src = sqlite3.connect(f"file:{origen}?mode=ro", uri=True, timeout=30)
    try:
        dst = sqlite3.connect(destino)
        try:
            src.backup(dst)
            ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise Falla(f"{origen}: la copia no pasa integrity_check ({ok})")
            tablas = [r[0] for r in dst.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            filas = {t: dst.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
            dst.execute("PRAGMA journal_mode=DELETE")       # la copia queda en UN archivo, sin -wal
        finally:
            dst.close()
    finally:
        src.close()
    return filas


def armar(lista, origen, salida, para, ahora=None, nombre="enenos_respaldo"):
    """Arma el respaldo y devuelve la ruta del archivo cifrado."""
    cosas = leer_lista(lista)
    origen, salida = Path(origen), Path(salida)
    llaves = [x.strip() for x in Path(para).read_text("utf-8").splitlines() if x.strip().startswith("age1")]
    if not llaves:
        raise Falla(f"{para} no tiene ninguna llave pública age1…")
    ahora = ahora or datetime.now(timezone.utc)
    sello = ahora.strftime("%Y-%m-%d_%H%M%S")
    manifiesto = {"version": VERSION, "fecha_utc": ahora.isoformat(timespec="seconds"), "maquina": socket.gethostname(),
                  "lista": Path(lista).name, "cosas": [], "faltan_opcionales": []}
    with tempfile.TemporaryDirectory() as tmp:
        caja = Path(tmp) / "respaldo"
        for c in cosas:
            src = origen / c["ruta"]
            dst = caja / "datos" / c["ruta"]
            if not src.exists():
                if c.get("opcional"):
                    manifiesto["faltan_opcionales"].append(c["nombre"])
                    print(f"  · {c['nombre']}: no está (opcional) — {c['ruta']}")
                    continue
                raise Falla(f"falta {c['nombre']} ({c['ruta']}) y no es opcional: el respaldo NO se arma")
            dst.parent.mkdir(parents=True, exist_ok=True)
            item = {"nombre": c["nombre"], "tipo": c["tipo"], "ruta": c["ruta"]}
            if c["tipo"] == "sqlite":
                item["filas"] = copiar_sqlite(src, dst)
                item["sha256"], item["bytes"] = sha256(dst), dst.stat().st_size
            elif c["tipo"] == "archivo":
                shutil.copy2(src, dst)
                item["sha256"], item["bytes"] = sha256(dst), dst.stat().st_size
            else:
                # archivo por archivo (no copytree): una base de la lista puede vivir ADENTRO de esta carpeta (EDA:
                # estado-prod/porteria.db) y ya estar copiada; la carpeta anota sólo lo suyo
                ignorar = c.get("ignorar", [])
                item["archivos"], item["bytes"] = {}, 0
                for q in sorted(src.rglob("*")):
                    rel = q.relative_to(src)
                    if any(fnmatch.fnmatch(parte, pat) for parte in rel.parts for pat in ignorar) or not q.is_file():
                        continue
                    destino = dst / rel
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(q, destino)
                    item["archivos"][rel.as_posix()] = sha256(destino)
                    item["bytes"] += destino.stat().st_size
            manifiesto["cosas"].append(item)
            print(f"  ✔ {c['nombre']}: {item['bytes']:,} bytes"
                  + (f" · {sum(item['filas'].values()):,} filas" if "filas" in item else "")
                  + (f" · {len(item['archivos'])} archivos" if "archivos" in item else ""))
        (caja / "MANIFIESTO.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), "utf-8")
        tar = Path(tmp) / "respaldo.tar.gz"
        with tarfile.open(tar, "w:gz") as t:
            t.add(caja, arcname="respaldo")
        salida.mkdir(parents=True, exist_ok=True)
        final = salida / f"{nombre}_{sello}.tar.gz.age"
        parcial = final.with_suffix(".age.parcial")
        cmd = ["age", "--encrypt"] + sum((["-r", k] for k in llaves), []) + ["-o", str(parcial), str(tar)]
        subprocess.run(cmd, check=True)
        os.replace(parcial, final)
    print(f"✔ respaldo cifrado: {final} ({final.stat().st_size:,} bytes, para {len(llaves)} llave/s)")
    return final


def descifrar(archivo, llave, destino):
    """Descifra y desarma en `destino`; comprueba todo contra el MANIFIESTO. Devuelve el manifiesto."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    tar = destino / "_respaldo.tar.gz"
    # sin capturar la salida: si la llave privada está protegida con contraseña, age la pide por la terminal
    r = subprocess.run(["age", "--decrypt", "-i", str(llave), "-o", str(tar), str(archivo)])
    if r.returncode:
        raise Falla("no se pudo descifrar (¿la llave no es la de este respaldo, o la contraseña está mal?)")
    with tarfile.open(tar) as t:
        for m in t.getmembers():
            if m.name.startswith("/") or ".." in Path(m.name).parts:
                raise Falla(f"el respaldo trae una ruta rara: {m.name}")
        t.extractall(destino, filter="data")
    tar.unlink()
    return comprobar(destino / "respaldo")


def comprobar(caja):
    """Compara lo desarmado contra su MANIFIESTO (sha256, integridad y filas). Devuelve el manifiesto o Falla."""
    caja = Path(caja)
    man = json.loads((caja / "MANIFIESTO.json").read_text("utf-8"))
    mal = []
    for it in man["cosas"]:
        p = caja / "datos" / it["ruta"]
        if it["tipo"] in ("sqlite", "archivo"):
            if not p.is_file() or sha256(p) != it["sha256"]:
                mal.append(f"{it['nombre']}: no coincide su sha256")
                continue
            if it["tipo"] == "sqlite":
                con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                try:
                    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        mal.append(f"{it['nombre']}: integrity_check")
                    for tabla, n in it["filas"].items():
                        if con.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0] != n:
                            mal.append(f"{it['nombre']}: la tabla {tabla} no tiene sus {n} filas")
                finally:
                    con.close()
        else:
            for rel, h in it["archivos"].items():
                q = p / rel
                if not q.is_file() or sha256(q) != h:
                    mal.append(f"{it['nombre']}: {rel} no coincide")
    if mal:
        raise Falla("el respaldo NO está sano:\n  " + "\n  ".join(mal))
    return man


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="que", required=True)
    a = sub.add_parser("armar")
    a.add_argument("--lista", required=True)
    a.add_argument("--origen", default="/origen")
    a.add_argument("--salida", required=True)
    a.add_argument("--para", required=True, help="archivo con la/s llave/s pública/s age1…")
    a.add_argument("--nombre", default="enenos_respaldo", help="comienzo del nombre del archivo (el de la PC: enenos_respaldo_pc)")
    for nombre in ("abrir", "ver"):
        b = sub.add_parser(nombre)
        b.add_argument("--archivo", required=True)
        b.add_argument("--llave", required=True, help="la llave PRIVADA de age (la de Eñeños)")
        if nombre == "abrir":
            b.add_argument("--destino", required=True)
    x = ap.parse_args(argv)
    try:
        if x.que == "armar":
            armar(x.lista, x.origen, x.salida, x.para, nombre=x.nombre)
        elif x.que == "abrir":
            man = descifrar(x.archivo, x.llave, x.destino)
            print(f"✔ respaldo sano · {len(man['cosas'])} cosas · del {man['fecha_utc']} · en {Path(x.destino) / 'respaldo'}")
        else:
            with tempfile.TemporaryDirectory() as tmp:
                man = descifrar(x.archivo, x.llave, tmp)
            print(f"✔ respaldo sano · {len(man['cosas'])} cosas · del {man['fecha_utc']}"
                  + (f" · faltaban (opcionales): {', '.join(man['faltan_opcionales'])}" if man["faltan_opcionales"] else ""))
    except (Falla, subprocess.CalledProcessError, sqlite3.Error) as e:
        print(f"⛔ {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
