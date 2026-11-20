#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mudanza — llevar el ESTADO de una pieza (R2Beat 2013, Cuenta Eñeños) de una máquina a otra.

La guía: documentacion/TOPOLOGIA_CONTENEDORES.md §5. Corre en la máquina que tiene Docker (Linux).

    python3 mudanza.py exportar --proyecto enenos --destino /ruta/mudanza [--pieza cuentas] [--imagenes] [--todo]
    python3 mudanza.py importar --proyecto enenos --origen  /ruta/mudanza [--pieza cuentas] [--imagenes]
    python3 mudanza.py ver      --origen /ruta/mudanza
    python3 mudanza.py desde-carpeta --pieza r2beat2013 --carpeta /opt/r2beat/game2013 --destino /ruta/mudanza

QUÉ ES IMAGEN Y QUÉ ES ESTADO
-----------------------------
· La IMAGEN es el programa: se vuelve a construir desde el repo (o viaja con `--imagenes`, un `docker save`).
  ⚠ Una imagen sirve para UNA arquitectura: la de esta PC (amd64) no arranca en el VPS de prod (arm64).
· El ESTADO es lo que no se puede volver a construir: las bases, las sesiones, la clave que firma los pases,
  las listas de GM. Vive en UN volumen por pieza, y esto lo empaqueta en UN `.tar` por pieza.

CÓMO LO HACE (y por qué no es un `cp`)
--------------------------------------
· Cada `.db` se copia con la copia en caliente de SQLite (`backup()`): con el WAL prendido, copiar el archivo a
  mano da una base ILEGIBLE o vieja. La copia se abre, se le pide `integrity_check` y se cuentan sus filas.
· Se puede exportar con el server PRENDIDO: no lo frena ni lo corta.
· Cada archivo viaja con su sha256; al importar se comprueba uno por uno, y las bases se vuelven a contar.
· `importar` se NIEGA a escribir sobre un volumen que ya tiene una base (salvo `--pisar`).
· Por omisión NO viajan `logs/` ni `respaldos/` (pesan y no hacen falta para arrancar): `--todo` los suma.
  `status.json` y los `-wal`/`-shm` no viajan nunca: los rehace el server.
· Para elegir la imagen de cada pieza busca en este orden:
  1) `JUEGO_IMAGEN` / `CUENTAS_IMAGEN` en el entorno;
  2) el contenedor de ese servicio en `--proyecto` (corriendo o parado);
  3) al importar con `--imagenes`, la imagen que trae `MANIFIESTO.json`;
  4) el `.env` de la carpeta actual;
  5) `r2beat2013-juego:local` / `enenos-cuentas:local`.

⛔ LO QUE SALE DE ACÁ ES SECRETO: trae los `pass_hash` de las cuentas y la clave privada del servicio de cuentas.
   Va a una carpeta FUERA del repo, viaja por `scp`/`rsync` sobre ssh, y se borra al terminar. No se imprime nada
   de adentro: sólo nombres de archivo y cantidades.
"""
import argparse
import hashlib
import io
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                    # noqa: BLE001
        pass

# Las piezas: su servicio en compose, su volumen (`<proyecto>_<volumen>`), su variable e imagen por omisión,
# y de qué archivos de una instalación SIN contenedores (la de prod hoy, con systemd) se arma su estado.
PIEZAS = {
    "r2beat2013": {
        "etiqueta": "del juego",
        "servicio": "r2beat2013",
        "volumen": "r2beat2013_datos",
        "env_imagen": "JUEGO_IMAGEN",
        "imagen": "r2beat2013-juego:local",
        "principal": "datos.db",
        # (dónde está en la carpeta vieja — varios candidatos, gana el primero que exista —, dónde va en el volumen)
        "desde_carpeta": [
            (("datos.db",), "datos.db"),
            (("panel.db",), "panel.db"),
            (("sesiones.json",), "sesiones.json"),
            (("servidor/gm.txt", "gm.txt"), "config/gm.txt"),
            (("servidor/admin.txt", "admin.txt"), "config/admin.txt"),
            (("servidor/streamers.txt", "streamers.txt"), "config/streamers.txt"),
        ],
    },
    "cuentas": {
        "etiqueta": "de cuentas",
        "servicio": "cuentas",
        "volumen": "cuentas_datos",
        "env_imagen": "CUENTAS_IMAGEN",
        "imagen": "enenos-cuentas:local",
        "principal": "portero.db",
        "desde_carpeta": [
            (("portero.db",), "portero.db"),
            (("portero_clave.json",), "portero_clave.json"),
            (("servidor/admin.txt", "admin.txt"), "config/admin.txt"),
            (("servidor/moderadores.txt", "moderadores.txt"), "config/moderadores.txt"),
        ],
    },
}
FICHA = "_MUDANZA.json"          # dentro de cada .tar: qué trae, con sus sha256 y sus cuentas de filas
MANIFIESTO = "MANIFIESTO.json"   # al lado de los .tar: la lista de piezas y (si viajan) las imágenes

# ─────────────────────────────────────────────────────────────────────────────────────────────
#  Lo que corre ADENTRO de un contenedor de la propia imagen (como el usuario de la imagen), con el volumen
#  montado en /datos. Un solo texto, sin dependencias: la imagen sólo trae Python.
# ─────────────────────────────────────────────────────────────────────────────────────────────
ADENTRO = r'''
import hashlib, io, json, os, sqlite3, sys, tarfile, tempfile, time

RAIZ = "/datos"
FICHA = "_MUDANZA.json"

def sha(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for t in iter(lambda: f.read(1 << 20), b""):
            h.update(t)
    return h.hexdigest()

def filas(ruta):
    """integrity_check + cuántas filas tiene cada tabla. Abre la COPIA, nunca la viva."""
    c = sqlite3.connect("file:" + ruta + "?mode=ro", uri=True)
    try:
        sana = c.execute("PRAGMA integrity_check").fetchone()[0]
        tablas = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {"integridad": sana, "filas": {t: c.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0] for t in sorted(tablas)}}
    finally:
        c.close()

def exportar():
    todo = os.environ.get("MUDANZA_TODO") == "1"
    saltar = set() if todo else {"logs", "respaldos"}
    tmp = tempfile.mkdtemp()
    ficha = {"hecho": time.strftime("%Y-%m-%d %H:%M:%S"), "archivos": {}, "bases": {}}
    sal = tarfile.open(fileobj=sys.stdout.buffer, mode="w|")
    for carpeta, dirs, archivos in os.walk(RAIZ):
        if carpeta == RAIZ:
            dirs[:] = sorted(d for d in dirs if d not in saltar)
        for n in sorted(archivos):
            ruta = os.path.join(carpeta, n)
            rel = os.path.relpath(ruta, RAIZ).replace(os.sep, "/")
            if n.endswith(("-wal", "-shm", ".tmp")) or rel == "status.json" or not os.path.isfile(ruta):
                continue
            origen = ruta
            if n.endswith(".db"):
                origen = os.path.join(tmp, rel.replace("/", "__"))
                a, b = sqlite3.connect(ruta, timeout=60), sqlite3.connect(origen)
                a.backup(b)                      # la copia en caliente: el server puede estar escribiendo
                b.close(); a.close()
                ficha["bases"][rel] = filas(origen)
                if ficha["bases"][rel]["integridad"] != "ok":
                    sys.stderr.write("LA COPIA DE %s NO ESTA SANA\n" % rel); sys.exit(3)
            ficha["archivos"][rel] = {"sha256": sha(origen), "bytes": os.path.getsize(origen)}
            sal.add(origen, arcname=rel, recursive=False)
            if origen != ruta:
                os.remove(origen)
    datos = json.dumps(ficha, indent=1, sort_keys=True).encode()
    ti = tarfile.TarInfo(FICHA); ti.size = len(datos); ti.mtime = int(time.time())
    sal.addfile(ti, io.BytesIO(datos))
    sal.close()

def importar():
    principal = os.environ["MUDANZA_PRINCIPAL"]
    if os.path.exists(os.path.join(RAIZ, principal)) and os.environ.get("MUDANZA_PISAR") != "1":
        sys.stderr.write("YA HAY UNA BASE en este volumen (%s): no la piso\n" % principal); sys.exit(4)
    ent = tarfile.open(fileobj=sys.stdin.buffer, mode="r|")
    ficha, puestos = None, []
    for m in ent:
        if m.name == FICHA:
            ficha = json.loads(ent.extractfile(m).read()); continue
        if not m.isfile() or m.name.startswith(("/", "..")) or "/../" in m.name:
            sys.stderr.write("ENTRADA RARA en el paquete: %r\n" % m.name); sys.exit(5)
        destino = os.path.join(RAIZ, m.name)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        for sobra in ("-wal", "-shm"):           # nunca dejar el WAL de OTRA base al lado de la que llega
            if m.name.endswith(".db") and os.path.exists(destino + sobra):
                os.remove(destino + sobra)
        with open(destino + ".tmp", "wb") as f:
            src = ent.extractfile(m)
            for t in iter(lambda: src.read(1 << 20), b""):
                f.write(t)
        os.chmod(destino + ".tmp", 0o600)
        os.replace(destino + ".tmp", destino)
        puestos.append(m.name)
    if ficha is None:
        sys.stderr.write("EL PAQUETE NO TRAE SU FICHA\n"); sys.exit(6)
    res = {"archivos": len(puestos), "malos": [], "bases": {}}
    for rel, d in ficha["archivos"].items():
        ruta = os.path.join(RAIZ, rel)
        if not os.path.isfile(ruta) or sha(ruta) != d["sha256"]:
            res["malos"].append(rel)
    for rel, antes in ficha["bases"].items():
        ahora = filas(os.path.join(RAIZ, rel))
        res["bases"][rel] = ahora
        if ahora != antes:
            res["malos"].append(rel + " (filas)")
    sys.stdout.write("MUDANZA " + json.dumps(res, sort_keys=True) + "\n")
    sys.exit(7 if res["malos"] else 0)

{"exportar": exportar, "importar": importar}[sys.argv[1]]()
'''


def docker(*args, **kw):
    return subprocess.run(["docker", *args], **kw)


def _sha_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for t in iter(lambda: f.read(1 << 20), b""):
            h.update(t)
    return h.hexdigest()


def _ficha_de(ruta_tar):
    with tarfile.open(ruta_tar) as t:
        return json.loads(t.extractfile(FICHA).read())


def _resumen(ficha):
    bases = "; ".join(f"{b}: " + ", ".join(f"{t}={n}" for t, n in d["filas"].items() if n)
                      for b, d in ficha["bases"].items())
    return f"{len(ficha['archivos'])} archivo(s) · {bases or 'sin bases'}"


def _piezas(args):
    return [args.pieza] if args.pieza else list(PIEZAS)


def _leer_manifiesto(carpeta):
    ruta = os.path.join(carpeta, MANIFIESTO)
    if not os.path.isfile(ruta):
        return {"piezas": {}, "imagenes": None}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _guardar_manifiesto(carpeta, m):
    with open(os.path.join(carpeta, MANIFIESTO), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1, sort_keys=True, ensure_ascii=False)


def _arquitectura(imagen):
    r = docker("image", "inspect", "--format", "{{.Architecture}}", imagen, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _arquitectura_local():
    return {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower(),
                                                                                           platform.machine().lower())


def _leer_env(ruta=".env"):
    """Lee pares CLAVE=VALOR de un `.env` local (sin imprimir ni exportar nada)."""
    env = {}
    if not os.path.isfile(ruta):
        return env
    with open(ruta, encoding="utf-8", errors="replace") as f:
        for linea in f:
            s = linea.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("export "):
                s = s[7:].lstrip()
            if "=" not in s:
                continue
            clave, valor = s.split("=", 1)
            clave, valor = clave.strip(), valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ('"', "'"):
                valor = valor[1:-1]
            else:
                for i, ch in enumerate(valor):
                    if ch == "#" and (i == 0 or valor[i - 1].isspace()):
                        valor = valor[:i].strip()
                        break
            if clave and valor:
                env[clave] = valor
    return env


def _imagen_contenedor(proyecto, servicio):
    """Imagen del contenedor de ese servicio en `proyecto` (corriendo o parado), o '' si no hay."""
    r = docker("compose", "-p", proyecto, "ps", "-aq", servicio, capture_output=True, text=True)
    if r.returncode != 0:
        r = docker("ps", "-aq",
                   "--filter", f"label=com.docker.compose.project={proyecto}",
                   "--filter", f"label=com.docker.compose.service={servicio}",
                   capture_output=True, text=True)
    cid = next((l.strip() for l in r.stdout.splitlines() if l.strip()), "") if r.returncode == 0 else ""
    if not cid:
        return ""
    ins = docker("inspect", "--format", "{{.Config.Image}}", cid, capture_output=True, text=True)
    return ins.stdout.strip() if ins.returncode == 0 else ""


def _resolver_imagen(pieza, proyecto=None, manifiesto=None, con_imagenes=False):
    """Elige la imagen de `pieza`: 1) entorno, 2) contenedor, 3) paquete (--imagenes), 4) .env, 5) :local."""
    d = PIEZAS[pieza]
    var = d["env_imagen"]
    img = os.environ.get(var, "").strip()
    if img:
        return img, f"de {var}"
    if proyecto:
        img = _imagen_contenedor(proyecto, d["servicio"])
        if img:
            return img, "del contenedor"
    if con_imagenes and manifiesto:
        im = manifiesto.get("imagenes") or {}
        nombres = im.get("nombres") or []
        img = (((manifiesto.get("piezas") or {}).get(pieza) or {}).get("imagen") or "").strip()
        if img and (not nombres or img in nombres):
            return img, "del paquete"
    img = _leer_env().get(var, "").strip()
    if img:
        return img, "de .env"
    return d["imagen"], "por omisión"


def exportar(args):
    os.makedirs(args.destino, exist_ok=True)
    os.chmod(args.destino, 0o700)
    m = _leer_manifiesto(args.destino)
    m.update(proyecto=args.proyecto, hecho=time.strftime("%Y-%m-%d %H:%M:%S"))
    imagenes = {}
    for pieza in _piezas(args):
        d = PIEZAS[pieza]
        volumen = f"{args.proyecto}_{d['volumen']}"
        if docker("volume", "inspect", volumen, capture_output=True).returncode != 0:
            sys.exit(f"⛔ no existe el volumen {volumen}")
        imagen, fuente = _resolver_imagen(pieza, proyecto=args.proyecto)
        imagenes[pieza] = imagen
        print(f"imagen {d['etiqueta']}: {imagen} ({fuente})")
        ruta = os.path.join(args.destino, f"{pieza}.tar")
        with open(os.open(ruta + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f:
            r = docker("run", "--rm", "-i", "--network", "none", "-v", f"{volumen}:/datos",
                       "-e", f"MUDANZA_TODO={'1' if args.todo else '0'}",
                       imagen, "python", "-c", ADENTRO, "exportar", stdout=f, stderr=subprocess.PIPE)
        if r.returncode != 0:
            os.remove(ruta + ".tmp")
            sys.exit(f"⛔ exportar {pieza}: {r.stderr.decode('utf-8', 'replace').strip()[-300:]}")
        os.replace(ruta + ".tmp", ruta)
        ficha = _ficha_de(ruta)
        m["piezas"][pieza] = {"archivo": f"{pieza}.tar", "sha256": _sha_archivo(ruta), "bytes": os.path.getsize(ruta),
                              "imagen": imagen, "ficha": ficha}
        print(f"✔ {pieza}: {ruta} ({os.path.getsize(ruta) // 1024} KB) · {_resumen(ficha)}")
    if args.imagenes:
        nombres = [imagenes[p] for p in _piezas(args)]
        ruta = os.path.join(args.destino, "imagenes.tar")
        if docker("save", "-o", ruta, *nombres).returncode != 0:
            sys.exit("⛔ no pude guardar las imágenes")
        os.chmod(ruta, 0o600)
        m["imagenes"] = {"archivo": "imagenes.tar", "sha256": _sha_archivo(ruta), "nombres": nombres,
                         "arquitectura": _arquitectura(nombres[0])}
        print(f"✔ imágenes: {ruta} ({os.path.getsize(ruta) // (1 << 20)} MB, {m['imagenes']['arquitectura']})")
    _guardar_manifiesto(args.destino, m)
    print("⛔ Esa carpeta trae hashes de contraseñas y la clave que firma los pases: que no entre a ningún repo, "
          "que viaje por ssh, y borrala al terminar.")


def importar(args):
    m = _leer_manifiesto(args.origen)
    if args.imagenes:
        im = m.get("imagenes") or sys.exit("⛔ esta mudanza no trae imágenes (se exportó sin --imagenes)")
        ruta = os.path.join(args.origen, im["archivo"])
        if _sha_archivo(ruta) != im["sha256"]:
            sys.exit("⛔ imagenes.tar llegó DAÑADO (el sha256 no coincide)")
        if im.get("arquitectura") and im["arquitectura"] != _arquitectura_local() and not args.otra_arquitectura:
            sys.exit(f"⛔ las imágenes son {im['arquitectura']} y esta máquina es {_arquitectura_local()}: "
                     f"no van a arrancar. Construilas acá desde el repo (`docker compose build`). "
                     f"(Si esta máquina tiene emulación —sólo para pruebas—: --otra-arquitectura.)")
        if docker("load", "-i", ruta).returncode != 0:
            sys.exit("⛔ no pude cargar las imágenes")
    for pieza in _piezas(args):
        d = PIEZAS[pieza]
        e = m["piezas"].get(pieza) or sys.exit(f"⛔ esta mudanza no trae la pieza «{pieza}»")
        ruta = os.path.join(args.origen, e["archivo"])
        if _sha_archivo(ruta) != e["sha256"]:
            sys.exit(f"⛔ {e['archivo']} llegó DAÑADO (el sha256 no coincide): no importo nada de esa pieza")
        imagen, fuente = _resolver_imagen(pieza, proyecto=args.proyecto, manifiesto=m, con_imagenes=args.imagenes)
        print(f"imagen {d['etiqueta']}: {imagen} ({fuente})")
        volumen = f"{args.proyecto}_{d['volumen']}"
        if docker("volume", "inspect", volumen, capture_output=True).returncode != 0:
            # con las etiquetas de compose, para que `docker compose up` lo tome como suyo
            docker("volume", "create", "--label", f"com.docker.compose.project={args.proyecto}",
                   "--label", f"com.docker.compose.volume={d['volumen']}", volumen, check=True, capture_output=True)
        with open(ruta, "rb") as f:
            r = docker("run", "--rm", "-i", "--network", "none", "-v", f"{volumen}:/datos",
                       "-e", f"MUDANZA_PRINCIPAL={d['principal']}", "-e", f"MUDANZA_PISAR={'1' if args.pisar else '0'}",
                       imagen, "python", "-c", ADENTRO, "importar", stdin=f, capture_output=True)
        salida = r.stdout.decode("utf-8", "replace")
        if r.returncode != 0:
            sys.exit(f"⛔ importar {pieza} (código {r.returncode}): "
                     f"{(r.stderr.decode('utf-8', 'replace').strip() or salida.strip())[-300:]}")
        res = json.loads(salida.split("MUDANZA ", 1)[1])
        print(f"✔ {pieza} -> volumen {volumen}: {res['archivos']} archivo(s), todos con su sha256; "
              + "; ".join(f"{b}: {sum(x['filas'].values())} filas, {x['integridad']}" for b, x in res["bases"].items()))


def ver(args):
    m = _leer_manifiesto(args.origen)
    print(f"mudanza del proyecto «{m.get('proyecto')}», hecha el {m.get('hecho')}")
    for pieza, e in m["piezas"].items():
        sana = _sha_archivo(os.path.join(args.origen, e["archivo"])) == e["sha256"]
        print(f"  {pieza}: {e['archivo']} {e['bytes'] // 1024} KB · {'sha256 bien' if sana else '⛔ DAÑADO'} · "
              f"{_resumen(e['ficha'])}")
        for rel in sorted(e["ficha"]["archivos"]):
            print(f"      {rel}")
    if m.get("imagenes"):
        print(f"  imágenes: {', '.join(m['imagenes']['nombres'])} ({m['imagenes']['arquitectura']})")


def _solo_lectura(ruta):
    """La URI de SQLite para abrir en sólo lectura (con `pathname2url`: una ruta de Windows no es una URI)."""
    return "file:" + urllib.request.pathname2url(os.path.abspath(ruta)) + "?mode=ro"


def _filas_local(ruta):
    c = sqlite3.connect(_solo_lectura(ruta), uri=True)
    try:
        sana = c.execute("PRAGMA integrity_check").fetchone()[0]
        tablas = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {"integridad": sana, "filas": {t: c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in sorted(tablas)}}
    finally:
        c.close()


def desde_carpeta(args):
    """Arma el MISMO paquete a partir de una instalación sin contenedores (la de prod hoy: una carpeta + systemd).
    ⛔ Sólo LEE la carpeta: las bases se copian con `backup()` a un temporal, y la viva queda como estaba."""
    d = PIEZAS[args.pieza]
    os.makedirs(args.destino, exist_ok=True)
    os.chmod(args.destino, 0o700)
    ruta_tar = os.path.join(args.destino, f"{args.pieza}.tar")
    ficha = {"hecho": time.strftime("%Y-%m-%d %H:%M:%S"), "archivos": {}, "bases": {}, "origen": "carpeta"}
    extras = list(d["desde_carpeta"])
    if args.pieza == "cuentas" and args.manifiestos and os.path.isdir(args.manifiestos):
        for n in sorted(os.listdir(args.manifiestos)):
            if n.endswith(".json"):
                extras.append(((os.path.join(os.path.abspath(args.manifiestos), n),), f"manifiestos/{n}"))
    with tempfile.TemporaryDirectory() as tmp, \
            open(os.open(ruta_tar + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f, \
            tarfile.open(fileobj=f, mode="w") as sal:
        for candidatos, rel in extras:
            origen = next((p for p in (os.path.join(args.carpeta, c) for c in candidatos) if os.path.isfile(p)), None)
            if origen is None:
                continue
            if rel.endswith(".db"):
                copia = os.path.join(tmp, rel.replace("/", "__"))
                a, b = sqlite3.connect(_solo_lectura(origen), uri=True, timeout=60), sqlite3.connect(copia)
                a.backup(b)
                b.close()
                a.close()
                ficha["bases"][rel] = _filas_local(copia)
                if ficha["bases"][rel]["integridad"] != "ok":
                    sys.exit(f"⛔ la copia de {rel} no está sana")
                origen = copia
            ficha["archivos"][rel] = {"sha256": _sha_archivo(origen), "bytes": os.path.getsize(origen)}
            sal.add(origen, arcname=rel, recursive=False)
        if d["principal"] not in ficha["archivos"]:
            sys.exit(f"⛔ en {args.carpeta} no está {d['principal']}: ¿es la carpeta correcta?")
        datos = json.dumps(ficha, indent=1, sort_keys=True).encode()
        ti = tarfile.TarInfo(FICHA)
        ti.size, ti.mtime = len(datos), int(time.time())
        sal.addfile(ti, io.BytesIO(datos))
    os.replace(ruta_tar + ".tmp", ruta_tar)
    m = _leer_manifiesto(args.destino)
    m.setdefault("proyecto", "(carpeta)")
    m["hecho"] = ficha["hecho"]
    imagen, _fuente = _resolver_imagen(args.pieza)
    m["piezas"][args.pieza] = {"archivo": f"{args.pieza}.tar", "sha256": _sha_archivo(ruta_tar),
                               "bytes": os.path.getsize(ruta_tar), "imagen": imagen, "ficha": ficha}
    _guardar_manifiesto(args.destino, m)
    print(f"✔ {args.pieza} desde {args.carpeta}: {ruta_tar} · {_resumen(ficha)}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Exportar e importar el estado de las piezas de Eñeños.")
    sub = p.add_subparsers(dest="orden", required=True)
    e = sub.add_parser("exportar")
    e.add_argument("--proyecto", required=True)
    e.add_argument("--destino", required=True)
    e.add_argument("--pieza", choices=list(PIEZAS))
    e.add_argument("--imagenes", action="store_true", help="suma un `docker save` de las imágenes")
    e.add_argument("--todo", action="store_true", help="suma logs/ y respaldos/")
    i = sub.add_parser("importar")
    i.add_argument("--proyecto", required=True)
    i.add_argument("--origen", required=True)
    i.add_argument("--pieza", choices=list(PIEZAS))
    i.add_argument("--imagenes", action="store_true", help="carga primero las imágenes (`docker load`)")
    i.add_argument("--pisar", action="store_true", help="⛔ escribe aunque el volumen ya tenga una base")
    i.add_argument("--otra-arquitectura", action="store_true",
                   help="carga imágenes de OTRA arquitectura (sólo sirve con emulación, para pruebas: van lentas)")
    v = sub.add_parser("ver")
    v.add_argument("--origen", required=True)
    c = sub.add_parser("desde-carpeta")
    c.add_argument("--pieza", required=True, choices=list(PIEZAS))
    c.add_argument("--carpeta", required=True)
    c.add_argument("--destino", required=True)
    c.add_argument("--manifiestos", help="(cuentas) la carpeta de R2_PORTERO_MANIFIESTOS")
    args = p.parse_args(argv)
    {"exportar": exportar, "importar": importar, "ver": ver, "desde-carpeta": desde_carpeta}[args.orden](args)


if __name__ == "__main__":
    main()
