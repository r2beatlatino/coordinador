#!/usr/bin/env bash
# actualizar_prueba.sh — pone el server de PRUEBA de R2Beat en lo último de `develop` del repo PÚBLICO (§34).
#
#   bash /opt/enenos/actualizar_prueba.sh            # (cron, cada 5 min) sólo si hay algo nuevo
#   bash /opt/enenos/actualizar_prueba.sh --forzar   # lo rearma igual
#
#   crontab -e (root):  */5 * * * * bash /opt/enenos/actualizar_prueba.sh >> /opt/enenos/prueba/actualizar.log 2>&1
#
# ★ La imagen sale del Dockerfile DEL REPO (`despliegue/Dockerfile`), que corre `pruebas/probar_login.py` al
#   armarse: si un PR roto llega a develop, no se arma y el server de prueba que andaba SIGUE andando. Ese commit
#   queda anotado en `prueba/fallido` y no se reintenta hasta que llegue otro.
# ⚠ Reemplazar el contenedor corta a los que están jugando EN EL DE PRUEBA (prod no se toca).
# ⛔ Prod NO se actualiza con esto: prod sale de `master` y lo aprueba Benja.
set -euo pipefail

CONJUNTO="${CONJUNTO:-/opt/enenos}"
DIR="$CONJUNTO/prueba"
REPO="$DIR/R2beat-2013"
URL="${PRUEBA_REPO_URL:-https://github.com/r2beatlatino/R2beat-2013.git}"
RAMA="${PRUEBA_RAMA:-develop}"
IMAGEN="$(grep -E '^PRUEBA_IMAGEN=' "$CONJUNTO/.env" 2>/dev/null | cut -d= -f2-)"
IMAGEN="${IMAGEN:-r2b2013-server:prueba}"
mkdir -p "$DIR"
exec 9>"$DIR/.cerrojo"
flock -n 9 || exit 0                                     # una sola vuelta a la vez

[ -d "$REPO/.git" ] || git clone -q -b "$RAMA" "$URL" "$REPO"
cd "$REPO"
git fetch -q origin "$RAMA"
AHORA="$(git rev-parse --short "origin/$RAMA")"
CORRE="$(docker image inspect -f '{{index .Config.Labels "enenos.commit"}}' "$IMAGEN" 2>/dev/null || true)"
if [ "${1:-}" != "--forzar" ]; then
    [ "$AHORA" = "$CORRE" ] && exit 0                                    # nada nuevo
    [ "$AHORA" = "$(cat "$DIR/fallido" 2>/dev/null)" ] && exit 0         # ya falló: espera otro commit
fi
echo "$(date '+%F %T') prueba ($RAMA): ${CORRE:-nada} → $AHORA"
git reset -q --hard "origin/$RAMA"
if ! docker build -q --label "enenos.commit=$AHORA" -f despliegue/Dockerfile -t "${IMAGEN}-nueva" . ; then
    echo "$(date '+%F %T') ⛔ no se pudo armar $AHORA (¿fallaron sus pruebas?). Sigue el anterior (${CORRE:-ninguno})."
    echo "$AHORA" > "$DIR/fallido"
    exit 1
fi
docker tag "${IMAGEN}-nueva" "$IMAGEN"
docker rmi -f "${IMAGEN}-nueva" >/dev/null 2>&1 || true
rm -f "$DIR/fallido"
cd "$CONJUNTO"
docker compose up -d --no-deps r2beat2013-prueba
docker image prune -f >/dev/null 2>&1 || true
echo "$(date '+%F %T') ✅ prueba en $AHORA"
