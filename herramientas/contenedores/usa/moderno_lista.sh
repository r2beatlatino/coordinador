#!/usr/bin/env bash
# ★ 21-nov — la LISTA FIRMADA de Eñeñosbit 2027 (el R2Beat moderno) para el launcher, como la de GunBound y EDA.
#
#   Lee el manifest de la release del cliente (/opt/enenos/releases/<release>/manifest.json, el que arma
#   make_manifest.py) y arma la lista: los MISMOS archivos (path, md5, size), de dónde bajarlos (la CDN) y A QUÉ SERVER
#   ENTRAR → /opt/enenos/moderno_web/.trabajo/lista.json, SIN firmar. La firma es la de PUBLICACIÓN de la PLATAFORMA
#   (kid 140674dc…, la de GunBound), cuya privada NO vive en el VPS: la pone `moderno_firmar.py` en la PC de Benja,
#   que la sube a /opt/enenos/moderno_web/lista.jws → https://ensayo.eñeños.link/r2beat-moderno/lista.jws (el Caddy
#   del sistema, enenos-ensayo.caddy). La anterior queda como lista.jws.antes.
#
#   ★ MUDAR ES FÁCIL: la dirección del server vive SÓLO acá (MODERNO_SERVIDOR). El launcher la escribe en r2beat.ini
#     cada vez que abre el juego. Mudarse = correr esto con la IP nueva (sin sacar otro launcher).
#     ⚠ El exe guarda el host en un hueco fijo: como máximo 29 − largo del puerto (24 con 28004). Una IP entra; un
#       dominio con ñ (punycode) casi seguro no. Este script se niega si no entra.
#
#   ★ 21-nov PRUEBA=1: la del SERVIDOR DE PRUEBA (los mismos archivos, el server 185.147.157.33:38004) → .trabajo/prueba.json
#     → moderno_firmar.py --prueba → moderno_web/prueba.jws → https://ensayo.eñeños.link/r2beat-moderno-prueba/lista.jws
#   Uso:  bash /opt/enenos/moderno_lista.sh [release]      (por omisión MODERNO_RELEASE, o la de abajo)
#         MODERNO_SERVIDOR=<ip:puerto> bash /opt/enenos/moderno_lista.sh
#   No toca ningún server ni ningún contenedor que corre: sólo escribe el contenido de la lista.
set -euo pipefail
ENS=/opt/enenos
REL="${1:-${MODERNO_RELEASE:-r2beat-moderno_2026-11-18}}"
VERSION="${MODERNO_VERSION:-$(echo "$REL" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | tr - .)}"
if [ "${PRUEBA:-0}" = "1" ]; then
    SERVIDOR="${MODERNO_SERVIDOR:-185.147.157.33:38004}"; NOMBRE=prueba
else
    SERVIDOR="${MODERNO_SERVIDOR:-185.147.157.33:28004}"; NOMBRE=lista
fi
BASE="https://cdn.xn--eeos-gqab.link/r2beat2013/$REL/"
OUT=$ENS/moderno_web
TRAB=$OUT/.trabajo
MAN=$ENS/releases/$REL/manifest.json
log() { echo "$(date '+%F %T') [moderno-lista] $*"; }

[ -f "$MAN" ] || { log "⛔ no está $MAN"; exit 1; }
mkdir -p "$TRAB"
python3 - "$MAN" "$REL" "$VERSION" "$BASE" "$SERVIDOR" > "$TRAB/$NOMBRE.json" <<'PY'
import json, re, sys
man, rel, version, base, servidor = sys.argv[1:6]
m = json.load(open(man, encoding="utf-8"))
if m.get("version") != rel:
    sys.exit(f"⛔ el manifest dice {m.get('version')!r}, no {rel!r}")
if not re.fullmatch(r"[0-9]{1,8}(\.[0-9]{1,8}){0,7}", version):
    sys.exit(f"⛔ versión inválida para el launcher: {version!r}")
host, _, puerto = servidor.rpartition(":")
if not host or not puerto.isdigit():
    sys.exit(f"⛔ servidor inválido: {servidor!r} (tiene que ser host:puerto)")
if len(host) > 29 - len(puerto):
    sys.exit(f"⛔ el host {host!r} ({len(host)}) no entra en el exe: máximo {29 - len(puerto)} con el puerto {puerto}")
files = [{"path": f["path"], "md5": f["md5"], "size": f["size"]} for f in m["files"]]
for f in files:
    if not re.fullmatch(r"[A-Za-z0-9_.\- /]+", f["path"]) or ".." in f["path"].split("/"):
        sys.exit(f"⛔ ruta que el launcher no acepta: {f['path']!r}")
print(json.dumps({"juego": "r2beat-moderno", "version": version, "release": rel, "base": base, "servidor": servidor,
                  "exe": "Game.exe", "del_usuario": ["Config.ini", "r2beat.ini", "r2beat_estado.ini"], "files": files},
                 ensure_ascii=False))
PY
chmod 644 "$TRAB/$NOMBRE.json"
log "✅ $TRAB/$NOMBRE.json ($REL → $SERVIDOR): falta FIRMARLA en la PC de Benja con la clave de la PLATAFORMA"
log "   (python herramientas/contenedores/usa/moderno_firmar.py$([ "$NOMBRE" = prueba ] && echo " --prueba"), que también la sube a $OUT/$NOMBRE.jws)"

