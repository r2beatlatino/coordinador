#!/usr/bin/env bash
# actualizar_moderno_prueba.sh — pone el server de PRUEBA de Eñeñosbit 2027 en lo último de `develop` del repo
#   r2beatlatino/Enenosbit-2027 (privado). El mismo flujo que R2Beat 2013 (actualizar_prueba.sh) y EDA: PR → merge a
#   develop → a los ≤ 5 min el de prueba está en ese commit. ★ 22-nov-2026, pedido de Eñeños.
#
#   bash /opt/enenos/actualizar_moderno_prueba.sh            # (cron, cada 5 min) sólo si hay algo nuevo
#   bash /opt/enenos/actualizar_moderno_prueba.sh --forzar   # lo rearma / lo vuelve a poner igual
#
#   crontab (root):  2-59/5 * * * * bash /opt/enenos/actualizar_moderno_prueba.sh >> /opt/enenos/moderno_prueba/actualizar.log 2>&1
#
# La imagen la arma moderno_imagen.sh (el mismo de siempre) a partir de `git archive` del commit: etiqueta
#   `r2beat-moderno:prueba-<commit>`. Su control: si a la imagen le falta una librería, no se usa.
# ★ Y uno más que el de 2013: después de reiniciar, espera que el contenedor quede SANO (el login contesta). Si no
#   queda sano, VUELVE SOLO a la imagen anterior. En los dos casos el commit queda en `fallido` y no se reintenta
#   hasta que llegue otro.
# ⚠ Reemplazar el contenedor corta a los que están jugando EN EL DE PRUEBA.
# ⛔ PROD (r2beat-moderno, MODERNO_IMAGEN) NO se toca con esto: sale de `main` y lo aprueba Eñeños.
# ⛔ El .env no se imprime: se cambia SÓLO la línea MODERNO_PRUEBA_IMAGEN, con respaldo en $DIR/.env.antes (600).
# Acceso al repo: la deploy key de SÓLO LECTURA /root/.ssh/enenosbit_deploy (Host github-enenosbit en /root/.ssh/config).
set -euo pipefail

CONJUNTO="${CONJUNTO:-/opt/enenos}"
DIR="$CONJUNTO/moderno_prueba"
REPO="$DIR/Enenosbit-2027"
URL="${MODERNO_PRUEBA_REPO_URL:-git@github-enenosbit:r2beatlatino/Enenosbit-2027.git}"
RAMA="${MODERNO_PRUEBA_RAMA:-develop}"
SERVICIO="r2beat-moderno-prueba"
ENV="$CONJUNTO/.env"
log() { echo "$(date '+%F %T') [moderno-prueba] $*"; }

mkdir -p "$DIR"
exec 9>"$DIR/.cerrojo"
flock -n 9 || exit 0                                     # una sola vuelta a la vez

[ -d "$REPO/.git" ] || git clone -q -b "$RAMA" "$URL" "$REPO"
cd "$REPO"
git fetch -q origin "$RAMA"
AHORA="$(git rev-parse --short=8 "origin/$RAMA")"
ETI="prueba-$AHORA"
IMG="r2beat-moderno:$ETI"
CORRE="$(grep -E '^MODERNO_PRUEBA_IMAGEN=' "$ENV" | cut -d= -f2-)"
[ -n "$CORRE" ] || { log "⛔ el .env no tiene MODERNO_PRUEBA_IMAGEN: no sigo"; exit 1; }
if [ "${1:-}" != "--forzar" ]; then
    [ "$CORRE" = "$IMG" ] && exit 0                                   # nada nuevo
    [ "$AHORA" = "$(cat "$DIR/fallido" 2>/dev/null)" ] && exit 0     # ya falló: espera otro commit
fi
log "prueba ($RAMA): $CORRE → $IMG"
git reset -q --hard "origin/$RAMA"

if docker image inspect "$IMG" >/dev/null 2>&1; then
    log "la imagen $IMG ya estaba armada"
else
    PAQ="$DIR/enenosbit-$AHORA.tgz"
    git archive --format=tar.gz -o "$PAQ" HEAD
    if ! bash "$CONJUNTO/moderno_imagen.sh" "$PAQ" "$ETI"; then
        log "⛔ no se pudo armar $AHORA. Sigue el anterior ($CORRE)."
        echo "$AHORA" > "$DIR/fallido"; rm -f "$PAQ"
        exit 1
    fi
    rm -f "$PAQ"
fi

poner() {                                    # $1 = imagen: la pone en el .env y reinicia SÓLO el de prueba
    sed -i "s|^MODERNO_PRUEBA_IMAGEN=.*|MODERNO_PRUEBA_IMAGEN=$1|" "$ENV"
    (cd "$CONJUNTO" && docker compose up -d --no-deps "$SERVICIO" >/dev/null 2>&1)
}
sano() {                                     # espera hasta ~3 min a que el HEALTHCHECK (el login contesta) dé healthy
    local id st=""
    for _ in $(seq 36); do
        sleep 5
        id="$(cd "$CONJUNTO" && docker compose ps -q "$SERVICIO")"
        st="$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null || true)"
        [ "$st" = "healthy" ] && return 0
    done
    log "estado del contenedor: ${st:-desconocido}"
    return 1
}

install -m 600 "$ENV" "$DIR/.env.antes"
poner "$IMG"
if ! sano; then
    log "⛔ $IMG no quedó sano: VUELVO a $CORRE"
    echo "$AHORA" > "$DIR/fallido"
    poner "$CORRE"
    sano && log "de vuelta en $CORRE, sano" || log "⚠⚠ $CORRE TAMPOCO quedó sano: mirar a mano (docker logs)"
    exit 1
fi
rm -f "$DIR/fallido"
log "✅ prueba en $AHORA ($IMG)"

# limpieza: las imágenes y carpetas prueba-* viejas, menos la que corre y la anterior (para volver atrás a mano)
for t in $(docker images r2beat-moderno --format '{{.Tag}}' | grep '^prueba-' || true); do
    [ "r2beat-moderno:$t" = "$IMG" ] || [ "r2beat-moderno:$t" = "$CORRE" ] || docker rmi "r2beat-moderno:$t" >/dev/null 2>&1 || true
done
for d in "$CONJUNTO"/moderno/servidor_prueba-*; do
    [ -d "$d" ] || continue
    t="${d##*/servidor_}"
    [ "r2beat-moderno:$t" = "$IMG" ] || [ "r2beat-moderno:$t" = "$CORRE" ] || rm -rf "$d"
done
