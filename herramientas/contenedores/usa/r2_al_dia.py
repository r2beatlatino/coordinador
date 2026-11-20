#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""r2_al_dia — deja en Cloudflare R2 (bucket `r2beat-2013`, 10 GB gratis) la release de PROD del 2013, y SÓLO esa.
Corre EN el VPS de USA, por cron cada 10 min (`/etc/cron.d/enenos-r2`). 18-nov-2026.

    python3 r2_al_dia.py              si prod cambió: pone R2 al día; si no, nada
    python3 r2_al_dia.py --verificar  revisa R2 contra la release de prod aunque r2.json ya la nombre

Benja: «R2 descarga principal — CDN del VPS secundaria; el launcher sigue en el VPS; que se actualice recién cuando
el cliente de prod se actualice; que no se choque con el del test server; que no se exceda de los 10 GB por accidente».

CÓMO SE CONECTA: el server de parches pone `base` = R2 (y `respaldo` = la CDN) SÓLO si `releases/r2.json` nombra la
release de prod (`patchserver.release_en_r2`). Este script es el ÚNICO que escribe `r2.json`, y lo escribe al FINAL,
después de verificar cada archivo y de probar la descarga pública. Mientras tanto, todos bajan de la CDN como antes.

LOS 10 GB: el bucket es SÓLO para la release de prod. Al cambiar de release:
  1. se borra `r2.json` PRIMERO (si prod volviera a la release vieja a mitad de camino, no apuntaría a archivos borrados)
  2. lo que no cambió se MUEVE adentro de R2 (copia + borra, de a uno: el espacio no crece y no se vuelve a subir)
  3. todo lo demás que no es de la release nueva se BORRA
  4. se sube lo que falta — y si con eso el bucket pasaría de TOPE (9,5 GB), no se sube nada: prod sigue por la CDN
⛔ Ninguna llave se imprime: se leen del archivo de `R2_LLAVES_ARCHIVO` (chmod 600, fuera del repo).
"""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError

ENV = "/opt/enenos/.env"
RELEASES = "/opt/enenos/releases"
MARCA = os.path.join(RELEASES, "r2.json")
LLAVE = os.environ.get("R2_LLAVES_ARCHIVO") or "/root/.r2_r2beat"   # (por omisión, el del cron del VPS de USA)
LOG = "/opt/enenos/r2_al_dia.log"
CANDADO = "/run/r2_al_dia.lock"
TOPE = 9.5e9                 # bytes: el plan gratis es 10 GB, con margen
HILOS = 8
MB = 1024 * 1024
MULTI = 64 * MB              # desde acá se sube en partes (y el ETag deja de ser el md5)
UA = "R2BeatLauncher/r2_al_dia"


def anotar(texto):
    linea = time.strftime("%Y-%m-%d %H:%M:%S ") + texto
    print(linea, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def leer_env(ruta):
    d = {}
    for l in open(ruta, encoding="utf-8"):
        l = l.strip()
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def cliente():
    k = leer_env(LLAVE)
    s3 = boto3.client("s3", endpoint_url=k["R2_ENDPOINT"], aws_access_key_id=k["R2_KEY"],
                      aws_secret_access_key=k["R2_SECRET"], region_name="auto",
                      config=Config(signature_version="s3v4", retries={"max_attempts": 8, "mode": "standard"},
                                    max_pool_connections=HILOS * 4))
    return s3, k["R2_BUCKET"]


def md5_de(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(4 * MB), b""):
            h.update(b)
    return h.hexdigest()


def listar(s3, bucket):
    """clave -> (tamaño, etag)"""
    out = {}
    for p in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for o in p.get("Contents", []):
            out[o["Key"]] = (o["Size"], o["ETag"].strip('"'))
    return out


def md5_remoto(s3, bucket, clave, tam, etag):
    """El md5 del objeto: el ETag si se subió entero; si se subió en partes, el que guardamos en la metadata."""
    if tam < MULTI and "-" not in etag:
        return etag
    try:
        return s3.head_object(Bucket=bucket, Key=clave).get("Metadata", {}).get("md5")
    except ClientError:
        return None


def escribir_marca(datos):
    tmp = MARCA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=1)
    os.replace(tmp, MARCA)


def borrar_marca():
    if os.path.exists(MARCA):
        os.remove(MARCA)
        anotar("r2.json borrado: hasta terminar, prod baja de la CDN")


def leer_marca():
    try:
        return json.load(open(MARCA, encoding="utf-8")).get("release")
    except (OSError, ValueError):
        return None


def borrar(s3, bucket, claves):
    claves = list(claves)
    for i in range(0, len(claves), 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in claves[i:i + 1000]], "Quiet": True})


def probar_publico(base, rel, files):
    """La descarga como la hace el launcher: entera (200) y por rango (206 con Content-Range)."""
    chico = min(files, key=lambda f: f["size"] if f["size"] > 16 else 1 << 62)
    url = base.rstrip("/") + "/" + urllib.parse.quote(rel + "/" + chico["path"].replace("\\", "/"), safe="/")
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(r, timeout=30) as x:
        datos = x.read()
        if x.status != 200 or hashlib.md5(datos).hexdigest() != chico["md5"]:
            return "entero: %s, md5 %s" % (x.status, "bien" if hashlib.md5(datos).hexdigest() == chico["md5"] else "MAL")
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity", "Range": "bytes=4-11"})
    with urllib.request.urlopen(r, timeout=30) as x:
        if x.status != 206 or not x.headers.get("Content-Range") or x.read() != datos[4:12]:
            return "por rango: %s %s" % (x.status, x.headers.get("Content-Range"))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args()
    candado = open(CANDADO, "w")
    try:
        fcntl.flock(candado, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0            # ya hay uno corriendo

    env = leer_env(ENV)
    rel = env.get("PARCHES_RELEASE_ACTIVA", "")
    publico = env.get("PARCHES_URL_R2", "")
    if not rel or not publico:
        return 0            # R2 apagado (sin PARCHES_URL_R2): nada que hacer
    if leer_marca() == rel and not a.verificar:
        return 0            # al día
    raiz = os.path.join(RELEASES, rel)
    files = json.load(open(os.path.join(raiz, "manifest.json"), encoding="utf-8"))["files"]
    total = sum(f["size"] for f in files)
    anotar("== prod es %s (%d archivos, %.2f GB)" % (rel, len(files), total / 1e9))
    if total > TOPE:
        borrar_marca()
        anotar("⛔ la release pesa %.2f GB, más que el tope de %.1f GB: prod sigue por la CDN" % (total / 1e9, TOPE / 1e9))
        return 1

    s3, bucket = cliente()
    pre = rel + "/"
    hay = listar(s3, bucket)
    viejos = {k: v for k, v in hay.items() if not k.startswith(pre)}
    if viejos and leer_marca() != rel:
        borrar_marca()

    # 1 · mover adentro de R2 lo que no cambió (de otra release que siga en el bucket, misma ruta y mismo md5)
    if viejos:
        por_ruta = {}
        for k, (tam, etag) in viejos.items():
            por_ruta.setdefault(k.split("/", 1)[1] if "/" in k else k, []).append((k, tam, etag))

        def mover(f):
            clave = pre + f["path"]
            if clave in hay:
                return 0
            for k, tam, etag in por_ruta.get(f["path"], []):
                if tam == f["size"] and md5_remoto(s3, bucket, k, tam, etag) == f["md5"]:
                    s3.copy({"Bucket": bucket, "Key": k}, bucket, clave, ExtraArgs={"MetadataDirective": "COPY"},
                            Config=TransferConfig(multipart_threshold=1 << 40))
                    s3.delete_object(Bucket=bucket, Key=k)
                    return 1
            return 0
        with concurrent.futures.ThreadPoolExecutor(HILOS) as ex:
            n = sum(ex.map(mover, files))
        anotar("movidos adentro de R2 (no se vuelven a subir): %d" % n)
        hay = listar(s3, bucket)

    # 2 · borrar lo que no es de la release de prod (otras releases, y basura adentro del prefijo)
    validas = {pre + f["path"] for f in files}
    sobra = [k for k in hay if k not in validas]
    if sobra:
        borrar(s3, bucket, sobra)
        anotar("borrados (no son de prod): %d objetos, %.2f GB" % (len(sobra), sum(hay[k][0] for k in sobra) / 1e9))
        hay = {k: v for k, v in hay.items() if k in validas}

    # 3 · subir lo que falta o está distinto — con el tope mirado ANTES
    def esta_bien(f):
        v = hay.get(pre + f["path"])
        return v is not None and v[0] == f["size"] and md5_remoto(s3, bucket, pre + f["path"], *v) == f["md5"]
    with concurrent.futures.ThreadPoolExecutor(HILOS * 2) as ex:
        bien = list(ex.map(esta_bien, files))
    faltan = [f for f, b in zip(files, bien) if not b]
    usado = sum(v[0] for k, v in hay.items()) - sum(hay[pre + f["path"]][0] for f in faltan if pre + f["path"] in hay)
    if usado + sum(f["size"] for f in faltan) > TOPE:
        borrar_marca()
        anotar("⛔ subir %d archivos dejaría el bucket en %.2f GB (tope %.1f): no se sube nada"
               % (len(faltan), (usado + sum(f["size"] for f in faltan)) / 1e9, TOPE / 1e9))
        return 1
    if faltan:
        if leer_marca() == rel:
            borrar_marca()
        anotar("a subir: %d archivos, %.2f GB" % (len(faltan), sum(f["size"] for f in faltan) / 1e9))
        cfg = TransferConfig(multipart_threshold=MULTI, multipart_chunksize=MULTI, max_concurrency=4)

        def subir(f):
            local = os.path.join(raiz, f["path"])
            if os.path.getsize(local) != f["size"] or md5_de(local) != f["md5"]:
                raise RuntimeError("el archivo local no es el del manifest: " + f["path"])
            s3.upload_file(local, bucket, pre + f["path"], Config=cfg,
                           ExtraArgs={"Metadata": {"md5": f["md5"]}, "ContentType": "application/octet-stream"})
        with concurrent.futures.ThreadPoolExecutor(HILOS) as ex:
            list(ex.map(subir, faltan))

    # 4 · verificar TODO de nuevo (largo + md5 de cada objeto) y la descarga pública
    hay = listar(s3, bucket)
    with concurrent.futures.ThreadPoolExecutor(HILOS * 2) as ex:
        malos = [f["path"] for f, b in zip(files, ex.map(esta_bien, files)) if not b]
    if malos:
        borrar_marca()
        anotar("⛔ %d archivos no coinciden en R2 (p. ej. %s): prod sigue por la CDN" % (len(malos), malos[0]))
        return 1
    usado = sum(v[0] for v in hay.values())
    error = probar_publico(publico, rel, files)
    if error:
        borrar_marca()
        anotar("⛔ la descarga pública de R2 falla (%s): prod sigue por la CDN" % error)
        return 1
    escribir_marca({"release": rel, "archivos": len(files), "bytes": total, "bucket_bytes": usado,
                    "fecha": time.strftime("%Y-%m-%d %H:%M:%S")})
    anotar("✔ R2 tiene %s entera (%d archivos; bucket %.2f GB de 10): prod baja de R2, con la CDN de respaldo"
           % (rel, len(files), usado / 1e9))
    # ★ la regla del precalentado (Benja, 18-nov): cada publicación se precalienta — esta también
    import subprocess
    with open("/opt/enenos/precalentar.log", "a") as log:
        subprocess.run([sys.executable, "/opt/enenos/precalentar_cdn.py", "--r2beat", rel], stdout=log, stderr=log)
    anotar("precalentado R2 de %s (ver precalentar.log)" % rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
