#!/usr/bin/env python3
"""dll_prueba.py — ★ 21-nov: la `d3d9.dll` de `develop` (repo PÚBLICO R2beat-2013) llega SOLA al server de PRUEBA.

Benja: «la dll de Hysteria no se autoactualizaba en testserver, tal y como ya lo hace EDA». El server de prueba se
rearmaba solo (`actualizar_prueba.sh`), pero la dll que bajan los jugadores la reparte el server de PARCHES según una
release, y esa release se armaba a mano. Esto la arma sola:

    python3 /opt/enenos/dll_prueba.py <repo> [rama]     # lo llama actualizar_prueba.sh en cada vuelta (cron, 5 min)
    python3 /opt/enenos/dll_prueba.py <repo> --ver      # dice qué haría, sin tocar nada

1. Lee la `exe/d3d9.dll` de `origin/<rama>` (el clon que ya trae `actualizar_prueba.sh`; no baja nada más).
2. ⛔ Sólo la reparte si la prueba `dll` de GitHub de ESE commit dio verde: GitHub compila el fuente y tiene que dar
   EXACTO esa dll (pruebas.yml). Así lo que llega a la PC de los jugadores es lo que sale del fuente del PR.
3. Arma una release NUEVA = la lista de prueba vigente + esa dll (`<prod>-dll<commit>`), con la maquinaria de las
   SUBIDAS del server de parches (`subidas.py`: enlaces duros, el historial, «volver» en el launcher). Sin reiniciar
   nada: el server de parches lee `_subidas/estado.json` en cada pedido. Prod no se toca.

Cuándo actúa: cuando la dll de develop cambió desde la última que publicó, o cuando cambió prod (el historial de
prueba arranca de nuevo con la base y la dll se habría perdido). ⚠ NO cuando alguien «vuelve» a una versión anterior
desde el launcher: eso se respeta hasta la próxima dll nueva.
⚠ Corre en OTRO proceso que el server de parches: no comparte su candado. Si justo en el mismo segundo un amigo aplica
una subida, gana el último que escribe `estado.json` (la release del otro sigue en disco; se vuelve desde el launcher).
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

CONJUNTO = os.environ.get("CONJUNTO") or "/opt/enenos"
ESTADO = os.path.join(CONJUNTO, "prueba", "dll_estado.json")
RELEASES = os.environ.get("PARCHES_RELEASES") or os.path.join(CONJUNTO, "releases")
PARCHES = os.environ.get("PARCHES_CONTENEDOR") or "enenos-parches-1"
GITHUB = os.environ.get("DLL_REPO_GITHUB") or "r2beatlatino/R2beat-2013"
UID = 10013                                   # el usuario del server de parches (dueño de las releases)
RUTA = "d3d9.r2b"                             # el launcher la copia a d3d9.dll al apretar JUGAR
ESPERA_CHEQUEO = 45 * 60                      # sin la prueba `dll` todavía: se espera hasta 45 min desde el commit

# Lo que corre ADENTRO del server de parches: su propio subidas.py, con su configuración (las variables del contenedor)
ADENTRO = r'''
import json, os, re, shutil, sys, time
R = os.environ.get("DLL_RELEASES") or "/releases"                  # (las dos variables: para la prueba, sin docker)
sys.path.insert(0, os.environ.get("DLL_APP") or "/app")
import subidas
cfg = {"current": (os.environ.get("PARCHES_RELEASE_ACTIVA") or "").strip(),
       "current_prueba": (os.environ.get("PARCHES_RELEASE_PRUEBA") or "").strip()}
s = subidas.Subidas(R, cfg)
vig = s.release_prueba()
def md5_de(rel):
    m = json.load(open(os.path.join(R, rel, "manifest.json"), encoding="utf-8"))
    return next((e["md5"] for e in m["files"] if e["path"] == "d3d9.r2b"), None)
if sys.argv[1] == "ver":
    print(json.dumps({"vigente": vig, "prod": cfg["current"], "md5": md5_de(vig),
                      "url": (os.environ.get("PARCHES_URL_ARCHIVOS") or "").strip()}))
    sys.exit(0)
_, _, md5, tam, corto, nota = sys.argv
nueva = "%s-dll%s" % (cfg["current"], corto)
while os.path.exists(os.path.join(R, nueva)):            # nunca se reusa un nombre (la CDN lo guarda)
    nueva += "b"
s._armar(vig, [{"ruta": "d3d9.r2b", "md5": md5, "tam": int(tam)}], nueva)
s._anotar(nueva, nota, "develop (GitHub)", time.time())
assert s.release_prueba() == nueva and md5_de(nueva) == md5, "la release nueva no quedó vigente"
# las nuestras que ya salieron del historial (el launcher guarda la vigente + 5) se borran: son enlaces duros
en_hist = {e["release"] for e in s._historial()} | {nueva}
for e in os.scandir(R):
    if e.is_dir() and e.name not in en_hist and re.fullmatch(re.escape(cfg["current"]) + r"-dll[0-9a-f]{7}b*", e.name):
        shutil.rmtree(e.path, ignore_errors=True)
try:
    os.remove(os.path.join(s.blobs, md5))                          # la release ya tiene su enlace
except OSError:
    pass
print(json.dumps({"nueva": nueva, "base": vig}))
'''


def log(msg):
    print("%s dll_prueba: %s" % (time.strftime("%F %T"), msg), flush=True)


def git(repo, *args, texto=True):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=texto).stdout


def adentro(*args):
    r = subprocess.run(["docker", "exec", "-i", PARCHES, "python3", "-c", ADENTRO, *args],
                       capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError("el server de parches no pudo: " + (r.stderr or r.stdout)[-1500:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def chequeo_dll(sha):
    """La prueba `dll` de GitHub para ese commit: 'success', 'failure'…, 'en_curso' o None (no está)."""
    url = "https://api.github.com/repos/%s/commits/%s/check-runs?check_name=dll&per_page=20" % (GITHUB, sha)
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "enenos-dll"})
    with urllib.request.urlopen(req, timeout=20) as r:
        corridas = json.load(r).get("check_runs", [])
    if not corridas:
        return None
    if any(c.get("status") != "completed" for c in corridas):
        return "en_curso"
    # si se corrió más de una vez (re-run), vale la última
    return max(corridas, key=lambda c: c.get("completed_at") or "").get("conclusion")


def decidir(estado, sha, md5, info, chequeo, edad):
    """Qué hacer. -> (acción, motivo). Acciones: 'nada', 'anotar' (guardar que ya se vio), 'esperar', 'publicar'.
    Pura (sin red ni disco), para poder probarla con sus reveses."""
    misma_prod = estado.get("prod") == info["prod"]
    if estado.get("sha") == sha and misma_prod:
        return "nada", "ya visto"
    if md5 == estado.get("md5") and misma_prod:
        return "anotar", "develop cambió, pero no su dll"
    if info["md5"] == md5:
        return "anotar", "la lista de prueba ya tiene esa dll"
    if chequeo == "en_curso" or (chequeo is None and edad < ESPERA_CHEQUEO):
        return "esperar", "la prueba «dll» de GitHub todavía no terminó"
    if chequeo != "success":
        return "anotar", "⛔ la prueba «dll» de GitHub no dio verde (%s): NO se reparte" % (chequeo or "no está")
    return "publicar", "dll nueva con la prueba «dll» en verde"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ver = "--ver" in sys.argv
    repo, rama = args[0], (args[1] if len(args) > 1 else "develop")
    ref = "origin/" + rama
    sha = git(repo, "rev-parse", ref).strip()
    corto = sha[:7]
    dll = subprocess.run(["git", "-C", repo, "show", "%s:exe/d3d9.dll" % ref], check=True, capture_output=True).stdout
    md5 = hashlib.md5(dll).hexdigest()
    try:
        estado = json.load(open(ESTADO, encoding="utf-8"))
    except (OSError, ValueError):
        estado = {}
    info = adentro("ver")
    edad = time.time() - int(git(repo, "log", "-1", "--format=%ct", ref).strip())
    # (a GitHub se le pregunta sólo si hace falta: 60 pedidos por hora sin ficha)
    previa, _ = decidir(estado, sha, md5, info, "success", 0)
    chequeo = chequeo_dll(sha) if previa == "publicar" else "success"
    accion, motivo = decidir(estado, sha, md5, info, chequeo, edad)
    if ver:
        log("[--ver] %s %s · dll %s · vigente %s (%s) → %s: %s"
            % (rama, corto, md5[:8], info["vigente"], (info["md5"] or "?")[:8], accion, motivo))
        return 0
    if accion == "nada":
        return 0
    if accion == "esperar":
        log("%s %s: %s; se mira en la próxima vuelta" % (rama, corto, motivo))
        return 0
    nuevo = {"sha": sha, "prod": info["prod"], "md5": estado.get("md5"), "release": estado.get("release")}
    if accion == "publicar":
        blob = os.path.join(RELEASES, "_subidas", "blobs", md5)
        with open(blob + ".tmp", "wb") as f:
            f.write(dll)
        os.chown(blob + ".tmp", UID, UID)
        os.replace(blob + ".tmp", blob)
        asunto = git(repo, "log", "-1", "--format=%s", ref).strip()
        r = adentro("aplicar", md5, str(len(dll)), corto, ("dll de develop %s: %s" % (corto, asunto))[:160])
        nuevo.update(md5=md5, release=r["nueva"])
        log("✅ %s %s: lista de prueba %s → %s (sólo cambia la dll, md5 %s)" % (rama, corto, r["base"], r["nueva"], md5[:8]))
        # se precalienta la CDN y se comprueba que entrega ESA dll
        if info.get("url"):
            try:
                with urllib.request.urlopen("%s/%s/%s" % (info["url"].rstrip("/"), r["nueva"], RUTA), timeout=120) as u:
                    cdn = hashlib.md5(u.read()).hexdigest()
                log("CDN: %s" % ("entrega la dll nueva ✅" if cdn == md5 else "⚠ entrega OTRA cosa (md5 %s)" % cdn[:8]))
            except OSError as e:
                log("⚠ CDN: no se pudo comprobar (%s)" % e)
    else:
        if info["md5"] == md5:
            nuevo.update(md5=md5)
        log("%s %s: %s" % (rama, corto, motivo))
    os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
    with open(ESTADO + ".tmp", "w", encoding="utf-8") as f:
        json.dump(nuevo, f, indent=1)
    os.replace(ESTADO + ".tmp", ESTADO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
