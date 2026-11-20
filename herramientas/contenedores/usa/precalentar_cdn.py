#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""precalentar_cdn — pide cada archivo de lo publicado UNA vez por la CDN (cdn.eñeños.link), así queda guardado en
Cloudflare ANTES de que lleguen los jugadores. Corre EN el VPS de USA. Es el `herramientas/precalentar.py` de Chile
(COMO_SE_SUBE_A_PROD.md §2.5) para el sistema nuevo.

    python3 precalentar_cdn.py                      los tres juegos: la release activa y la de prueba del 2013,
                                                    la versión de GunBound y la de EDA del ensayo
    python3 precalentar_cdn.py --r2beat <release>   sólo esa release del 2013
    python3 precalentar_cdn.py --gunbound | --eda   sólo ese juego

⛔ REGLA (Benja, 18-nov: «que siempre funcione así durante parches»): cada vez que se publica algo —una release del
   2013, una versión de GunBound o de EDA, el launcher— se precalienta ANTES de anunciarlo. La tarea de EDA
   (`eda_ensayo.sh`) lo hace sola al cambiar la lista.

POR QUÉ: la primera vez que alguien pide un archivo, Cloudflare lo trae del VPS de Miami mientras se lo da (lento: lo
vio Benja, «no llega a 200 Mbps», y el VPS tenía 317 conexiones de Cloudflare). Con la caché en niveles prendida, esta
pasada llena el nivel alto (el nodo junto al VPS) y los demás nodos (Río, el de Bolivia) se sirven de ahí por la red
de Cloudflare, no del VPS. Y el VPS entrega cada archivo UNA vez, en un horario tranquilo.

★ La URL se arma IGUAL que el launcher (quote del path con «/»): si esta herramienta pidiera distinto, sus errores no
  dirían nada del cliente (lección de Chile: un espacio o una carpeta en coreano).
★ Con el User-Agent del launcher: Cloudflare frena el de «Python-urllib» (403).
★ Los archivos de más de 512 MB no se guardan en el plan gratis: no se piden (para eso están las PARTES).
"""
import argparse
import base64
import concurrent.futures
import json
import os
import sys
import time
import urllib.parse
import urllib.request

CDN = "https://cdn.xn--eeos-gqab.link"
ENSAYO = "https://ensayo.xn--eeos-gqab.link"
UA = "R2BeatLauncher/precalentar"
TOPE = 512 * 1024 * 1024
HILOS = 12


def pedir(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=300) as x:
            n = 0
            while True:
                b = x.read(1 << 20)
                if not b:
                    break
                n += len(b)
            return x.status, x.headers.get("cf-cache-status", "?"), n, time.time() - t0
    except Exception as e:  # noqa: BLE001
        return getattr(e, "code", 0), str(e)[:60], 0, time.time() - t0


def carga_jws(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    a, b, c = urllib.request.urlopen(r, timeout=30).read().decode().strip().split(".")
    return json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)))


def entradas_de(files, base):
    """(url, tamaño) de cada archivo; de los que vienen en partes, las partes."""
    out = []
    for f in files:
        for q in (f.get("partes") or [f]):
            out.append((base + urllib.parse.quote(q["path"].replace("\\", "/"), safe="/"), int(q.get("size", 0))))
    return out


def r2beat(release):
    """De dónde la baja el launcher: de R2 si es la de prod y `r2.json` dice que está entera allá (como el server de
    parches, `release_en_r2`); si no, de la CDN."""
    m = json.load(open(f"/opt/enenos/releases/{release}/manifest.json", encoding="utf-8"))
    base = f"{CDN}/r2beat2013/{release}/"
    try:
        env = dict(l.strip().split("=", 1) for l in open("/opt/enenos/.env", encoding="utf-8") if "=" in l and not l.startswith("#"))
        if env.get("PARCHES_URL_R2") and json.load(open("/opt/enenos/releases/r2.json", encoding="utf-8")).get("release") == release:
            base = env["PARCHES_URL_R2"].rstrip("/") + f"/{release}/"
    except (OSError, ValueError):
        pass
    return entradas_de(m["files"], base)


def precalentar(nombre, lista):
    grandes = [u for u, t in lista if t > TOPE]
    lista = [(u, t) for u, t in lista if t <= TOPE]
    total = sum(t for _, t in lista)
    print(f"== {nombre}: {len(lista)} archivos, {total / 2**20:.0f} MB" + (f" (salteo {len(grandes)} de más de 512 MB)" if grandes else ""), flush=True)
    cuenta, malos, t0, hecho = {}, [], time.time(), 0
    with concurrent.futures.ThreadPoolExecutor(HILOS) as ex:
        for (u, t), (c, cache, n, s) in zip(lista, ex.map(lambda x: pedir(x[0]), lista)):
            hecho += n
            cuenta[cache] = cuenta.get(cache, 0) + 1
            if c != 200 or n != t:
                malos.append((c, n, t, u))
    s = time.time() - t0
    print(f"   {s:.0f} s · {hecho * 8 / max(s, 0.1) / 1e6:.0f} Mbps · " + " ".join(f"{k}={v}" for k, v in sorted(cuenta.items())), flush=True)
    for c, n, t, u in malos[:10]:
        print(f"   ⚠ {c} {n}/{t} {u}", flush=True)
    return not malos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r2beat", action="append", default=[])
    ap.add_argument("--gunbound", action="store_true")
    ap.add_argument("--eda", action="store_true")
    a = ap.parse_args()
    todo = not (a.r2beat or a.gunbound or a.eda)
    ok = True
    rels = a.r2beat
    if todo:
        env = dict(l.strip().split("=", 1) for l in open("/opt/enenos/.env", encoding="utf-8") if "=" in l and not l.startswith("#"))
        rels = sorted({env.get("PARCHES_RELEASE_ACTIVA", ""), env.get("PARCHES_RELEASE_PRUEBA", "")} - {""})
    for rel in rels:
        lista = r2beat(rel)
        ok &= precalentar(f"R2Beat 2013 {rel}" + (" (R2)" if lista and "//r2." in lista[0][0] else ""), lista)
    if todo or a.gunbound:
        g = carga_jws(f"{ENSAYO}/gunbound/lista.jws")
        ok &= precalentar(f"GunBound {g['version']}", entradas_de(g["files"], g["base"]))
    if todo or a.eda:
        e = carga_jws(f"{ENSAYO}/eda/manifiesto.jws")
        ok &= precalentar(f"EDA {e['version']}", entradas_de(e["files"], e["base"]))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
