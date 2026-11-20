#!/bin/bash
# ★ 20-nov — el server de parches de Chile anuncia OTRA versión del N2launcher (después de la mudanza, para los que
#   todavía tienen el 3.0.1). Baja el exe del CDN de Miami, comprueba su md5, respalda el que había y lo cambia.
#   ⛔ Va DESPUÉS de GitHub (v-latest) con la descarga pública comprobada: `launcher_url` de Chile es GitHub «latest».
#   ⚠ restart de r2beat-patch = ~1 s (el juego de Chile ya está apagado).
# Uso: sudo bash chile_n2_version.sh <version> <md5> <url del exe en el CDN>
set -euo pipefail
V="$1"; MD5="$2"; URL="$3"
K=/opt/r2beat/_subida_launcher_n2
B=/opt/r2beat/backups/launcher_n2
BIN=/opt/r2beat/launcher/Launcher.exe
CFG=/opt/r2beat/patchserver/config.json
md5() { md5sum "$1" | cut -d' ' -f1; }
curl -s --max-time 180 -o "$K/Launcher.exe" "$URL"
[ "$(md5 "$K/Launcher.exe")" = "$MD5" ] || { echo "⛔ el exe bajado no da $MD5"; exit 1; }
ANTES=$(md5 "$BIN")
cp -a "$BIN" "$B/Launcher.exe.$ANTES"
cp -p "$CFG" "$B/patchserver_config.antes-$V.json"
install -o r2beat -g r2beat -m 644 "$K/Launcher.exe" "$BIN"
[ "$(md5 "$BIN")" = "$MD5" ] || { echo "⛔ no quedó el nuevo"; exit 1; }
python3 - "$CFG" "$V" <<'PY'
import json, os, sys
ruta, v = sys.argv[1], sys.argv[2]
c = json.load(open(ruta)); c["launcher_version"] = v
tmp = ruta + ".tmp"; json.dump(c, open(tmp, "w"), indent=2); os.replace(tmp, ruta)
PY
chown --reference="$B/patchserver_config.antes-$V.json" "$CFG"; chmod --reference="$B/patchserver_config.antes-$V.json" "$CFG"
systemctl restart r2beat-patch
sleep 2
curl -s -m 8 https://patch.r2beatlatino.com/launcher/meta | python3 -c 'import json,sys;d=json.load(sys.stdin);print("meta: versión", d["version"], "· md5", d["md5"])'
echo "antes: $ANTES (respaldado en $B)"
