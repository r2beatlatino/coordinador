# -*- coding: utf-8 -*-
"""probar_dll_prueba — la dll de `develop` llega SOLA a la lista de PRUEBA (21-nov-2026, `dll_prueba.py`).

Benja: «la dll de Hysteria no se autoactualizaba en testserver, tal y como ya lo hace EDA».
Cada regla con su CONTROL AL REVÉS (⟲):
  · DECIDIR (la regla pura):
      - dll nueva con la prueba «dll» de GitHub en verde → publica ⟲ en rojo NO, sin prueba (vieja) NO, en curso espera
      - commit sin prueba todavía y reciente → espera ⟲ el mismo, viejo → anota y no reparte
      - el mismo commit ya visto → nada ⟲ si cambió prod, vuelve a mirar (y publica si a la lista le falta la dll)
      - develop cambió pero NO su dll → anota sin publicar ⟲ con la dll cambiada, publica
      - la lista ya tiene esa dll (se armó a mano) → anota ⟲ si es otra, publica
      - alguien VOLVIÓ a una versión anterior desde el launcher → se respeta ⟲ la próxima dll nueva sí entra
  · ARMAR (lo que corre adentro del server de parches, con SU subidas.py, sobre releases de juguete):
      - la release nueva = la vigente + la dll; queda VIGENTE y el resto son enlaces duros ⟲ la base queda intacta
      - el nombre no se reusa (la CDN lo guarda) ⟲ el segundo con el mismo commit lleva «b»
      - las nuestras fuera del historial se borran ⟲ las del historial y las que no son nuestras, no
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "herramientas", "contenedores"))
import dll_prueba as d  # noqa: E402

fallas = []


def ok(nombre, cond):
    print("  %s %s" % ("✅" if cond else "⛔", nombre))
    if not cond:
        fallas.append(nombre)


# ── DECIDIR ─────────────────────────────────────────────────────────────────────────────────────
INFO = {"vigente": "r-p3", "prod": "r", "md5": "viejo", "url": ""}
EST = {"sha": "aaa", "prod": "r", "md5": "viejo"}


def dec(estado=EST, sha="bbb", md5="nuevo", info=INFO, chequeo="success", edad=10 * 3600):
    return d.decidir(estado, sha, md5, info, chequeo, edad)[0]


print("decidir:")
ok("dll nueva + prueba «dll» en verde → publica", dec() == "publicar")
ok("⟲ en rojo → NO publica (anota)", dec(chequeo="failure") == "anotar")
ok("⟲ cancelada → NO publica", dec(chequeo="cancelled") == "anotar")
ok("⟲ commit viejo sin prueba «dll» → NO publica", dec(chequeo=None) == "anotar")
ok("⟲ en curso → espera", dec(chequeo="en_curso") == "esperar")
ok("commit reciente sin prueba todavía → espera", dec(chequeo=None, edad=60) == "esperar")
ok("el mismo commit ya visto → nada", dec(sha="aaa") == "nada")
ok("⟲ el mismo commit pero cambió prod → vuelve a publicar", dec(sha="aaa", info=dict(INFO, prod="r2")) == "publicar")
ok("develop cambió pero no su dll → anota", dec(md5="viejo") == "anotar")
ok("la lista ya tiene esa dll → anota", dec(info=dict(INFO, md5="nuevo")) == "anotar")
volvio = dict(INFO, md5="otra-anterior")               # alguien volvió a una versión vieja desde el launcher
ok("volvieron atrás desde el launcher → se respeta", dec(sha="aaa", md5="viejo", info=volvio) == "nada")
ok("⟲ y la próxima dll nueva sí entra", dec(sha="ccc", md5="nueva2", info=volvio) == "publicar")


# ── ARMAR, con el subidas.py de verdad ─────────────────────────────────────────────────────────
print("armar (subidas.py de verdad, releases de juguete):")
APP = os.path.join(RAIZ, "herramientas", "contenedores", "parches")
with tempfile.TemporaryDirectory() as R:
    base = os.path.join(R, "r-base")
    os.makedirs(os.path.join(base, "pack"))
    archivos = {"d3d9.r2b": b"dll vieja", "pack/x.pak": b"un pak"}
    for ruta, datos in archivos.items():
        open(os.path.join(base, *ruta.split("/")), "wb").write(datos)
    man = {"version": "r-base", "files": [{"path": p, "md5": hashlib.md5(b).hexdigest(), "size": len(b)}
                                          for p, b in archivos.items()]}
    json.dump(man, open(os.path.join(base, "manifest.json"), "w"))
    ajena = os.path.join(R, "r-p9")                       # una release de subidas (no es nuestra)
    os.makedirs(ajena)
    vieja_nuestra = os.path.join(R, "r-dll0000000")       # una nuestra que ya no está en el historial
    os.makedirs(vieja_nuestra)
    env = dict(os.environ, DLL_RELEASES=R, DLL_APP=APP, PARCHES_RELEASE_ACTIVA="r", PARCHES_RELEASE_PRUEBA="r-base",
               PYTHONIOENCODING="utf-8")

    def correr(*args):
        r = subprocess.run([sys.executable, "-c", d.ADENTRO, *args], env=env, capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-2000:])
        return r.returncode, (json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else None)

    rc, v = correr("ver")
    ok("ver: la vigente es la base, con su dll", rc == 0 and v["vigente"] == "r-base"
       and v["md5"] == hashlib.md5(b"dll vieja").hexdigest())
    nueva = b"dll nueva de develop"
    m5 = hashlib.md5(nueva).hexdigest()
    blobs = os.path.join(R, "_subidas", "blobs")
    os.makedirs(blobs, exist_ok=True)
    open(os.path.join(blobs, m5), "wb").write(nueva)
    rc, a = correr("aplicar", m5, str(len(nueva)), "abc1234", "dll de develop abc1234: prueba")
    ok("aplicar: release nueva <prod>-dll<commit>", rc == 0 and a["nueva"] == "r-dllabc1234" and a["base"] == "r-base")
    rc, v = correr("ver")
    ok("queda VIGENTE con la dll nueva", v["vigente"] == "r-dllabc1234" and v["md5"] == m5)
    nd = os.path.join(R, "r-dllabc1234")
    ok("la dll nueva está en la release", open(os.path.join(nd, "d3d9.r2b"), "rb").read() == nueva)
    ok("⟲ la base quedó intacta", open(os.path.join(base, "d3d9.r2b"), "rb").read() == b"dll vieja")
    mismo = os.path.samefile(os.path.join(nd, "pack", "x.pak"), os.path.join(base, "pack", "x.pak"))
    ok("lo demás son enlaces duros (no ocupa)", mismo)
    mn = json.load(open(os.path.join(nd, "manifest.json")))
    ok("el manifest cambia SÓLO la dll", {e["path"]: e["md5"] for e in mn["files"]}
       == {"d3d9.r2b": m5, "pack/x.pak": hashlib.md5(b"un pak").hexdigest()})
    ok("la nuestra fuera del historial se borró", not os.path.exists(vieja_nuestra))
    ok("⟲ la de subidas (ajena) sigue", os.path.isdir(ajena))
    est = json.load(open(os.path.join(R, "_subidas", "estado.json"), encoding="utf-8"))
    ok("el historial la anota (para «volver» en el launcher)", est["historial"][-1]["release"] == "r-dllabc1234"
       and est["historial"][-1]["quien"] == "develop (GitHub)" and est["historial"][0]["release"] == "r-base")
    open(os.path.join(blobs, m5), "wb").write(nueva)
    rc, a2 = correr("aplicar", m5, str(len(nueva)), "abc1234", "otra vez")
    ok("⟲ el mismo commit otra vez → otro nombre («b»): no se reusa", rc == 0 and a2["nueva"] == "r-dllabc1234b")
    ok("⟲ y la anterior sigue (está en el historial)", os.path.isdir(nd))
    rc, _ = correr("aplicar", "f" * 32, "3", "def5678", "sin blob")
    ok("⟲ sin el archivo (blob) no arma nada", rc != 0 and not os.path.exists(os.path.join(R, "r-dlldef5678")))

print()
print("→ TODO BIEN" if not fallas else "→ ⛔ %d fallas: %s" % (len(fallas), "; ".join(fallas)))
sys.exit(1 if fallas else 0)
