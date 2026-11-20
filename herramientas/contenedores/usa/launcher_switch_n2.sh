#!/bin/bash
# ★ 20-nov — LA MUDANZA: el launcher viejo (3.0.1) se actualiza solo al N2LAUNCHER (el que sólo funciona con Miami).
#   Benja: «a Chile no avisaremos, solamente ya mandaremos nuestro nuevo launcher como actualización».
#   ⛔ Va DESPUÉS de publicarlo en GitHub (v-latest: Launcher.exe + R2BeatTEST_Setup.exe), y con la descarga PÚBLICA
#      comprobada: `launcher_url` de config.json sigue siendo GitHub «latest», el 3.0.1 baja de ahí.
#   nuevo -> /opt/r2beat/launcher/Launcher.exe = N2launcher 3.0.21 + launcher_version + restart r2beat-patch (~1 s)
#   viejo -> vuelve el 3.0.1 (respaldado acá) — ⚠ y volver a publicar el 3.0.1 en GitHub
#   El JUEGO (r2beat-game2013) no se toca acá.
# Uso: sudo bash /opt/r2beat/_subida_launcher_n2/launcher_switch_n2.sh nuevo | viejo
set -euo pipefail
K=/opt/r2beat/_subida_launcher_n2
B=/opt/r2beat/backups/launcher_n2
BIN=/opt/r2beat/launcher/Launcher.exe
CFG=/opt/r2beat/patchserver/config.json
NUEVO=18a67b72b90820e5e33fdaa5607a69d6     # N2launcher 3.0.21
VIEJO=9c3c5cab27deef6d37a4ea0ff0f4be7a     # 3.0.1
md5() { md5sum "$1" | cut -d' ' -f1; }
version() {
  python3 - "$CFG" "$1" <<'PY'
import json, os, sys
ruta, v = sys.argv[1], sys.argv[2]
c = json.load(open(ruta)); c["launcher_version"] = v
tmp = ruta + ".tmp"; json.dump(c, open(tmp, "w"), indent=2); os.replace(tmp, ruta)
PY
  chown --reference="$B/patchserver_config.json" "$CFG"; chmod --reference="$B/patchserver_config.json" "$CFG"
}
mirar() {
  sleep 2
  curl -s -m 8 https://patch.r2beatlatino.com/launcher/meta | python3 -c 'import json,sys;d=json.load(sys.stdin);print("meta: versión", d["version"], "· md5", d["md5"])'
}
mkdir -p "$B" && chown r2beat:r2beat "$B"
case "${1:-}" in
nuevo)
  [ "$(md5 "$K/Launcher.exe")" = "$NUEVO" ] || { echo "⛔ el Launcher.exe subido no es el N2launcher 3.0.21"; exit 1; }
  [ "$(md5 "$BIN")" = "$VIEJO" ] || { echo "⛔ el de /opt no es el 3.0.1 que se esperaba ($(md5 "$BIN"))"; exit 1; }
  cp -a "$BIN" "$B/Launcher.exe.v301-$VIEJO"
  cp -p "$CFG" "$B/patchserver_config.json"
  install -o r2beat -g r2beat -m 644 "$K/Launcher.exe" "$BIN"
  [ "$(md5 "$BIN")" = "$NUEVO" ] || { echo "⛔ no quedó el N2launcher"; exit 1; }
  version N2launcher-3.0.21
  systemctl restart r2beat-patch
  mirar ;;
viejo)
  [ -f "$B/Launcher.exe.v301-$VIEJO" ] || { echo "⛔ no está el respaldo del 3.0.1"; exit 1; }
  install -o r2beat -g r2beat -m 644 "$B/Launcher.exe.v301-$VIEJO" "$BIN"
  version 3.0.1
  systemctl restart r2beat-patch
  mirar
  echo "↩ /opt = 3.0.1 · ⚠ falta volver a publicar el 3.0.1 en GitHub (v-latest)" ;;
*) echo "uso: $0 nuevo | viejo"; exit 1 ;;
esac
