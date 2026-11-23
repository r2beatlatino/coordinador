#!/usr/bin/env bash
# actualizar_moderno.sh — pone un server de Eñeñosbit 2027 en lo último de su rama del repo r2beatlatino/Enenosbit-2027.
#   ★ 23-nov-2026, pedido de Eñeños: «r2beat moderno debe auto-actualizar como eda o r2beat2013, al actualizar la repo de
#   prod o testserver». Mismo flujo que el de prueba (antes actualizar_moderno_prueba.sh, que ahora llama a éste).
#
#   bash /opt/enenos/actualizar_moderno.sh prueba            # develop → r2beat-moderno-prueba (MODERNO_PRUEBA_IMAGEN)
#   bash /opt/enenos/actualizar_moderno.sh prod              # main    → r2beat-moderno        (MODERNO_IMAGEN)
#   bash /opt/enenos/actualizar_moderno.sh <entorno> --forzar
#
#   crontab (root):
#     2-59/5 * * * * bash /opt/enenos/actualizar_moderno.sh prueba >> /opt/enenos/moderno_prueba/actualizar.log 2>&1
#     4-59/5 * * * * bash /opt/enenos/actualizar_moderno.sh prod   >> /opt/enenos/moderno_prod/actualizar.log 2>&1
#
# Cómo es una vuelta: si la rama cambió → `git archive` → moderno_imagen.sh arma `r2beat-moderno:<entorno>-<commit>`
#   (control: todo el server importa) → [prod: RESPALDO de las cuentas] → .env → reinicia SÓLO ese servicio → espera
#   que quede SANO (el login contesta). Si no queda sano, VUELVE SOLO a la imagen anterior. En los dos casos el
#   commit queda en `fallido` y no se reintenta hasta que llegue otro.
# ⏸ PAUSAR un entorno: `touch /opt/enenos/moderno_<entorno>/pausado` (se reanuda borrándolo).
# ⚠ Reemplazar el contenedor corta a los que están jugando EN ESE server.
# ⚠ PROD: la migración de cuentas a SQLite (M09) es de ida: si después se vuelve a una imagen vieja, lee cuenta.json
#   (que queda intacto) y pierde lo escrito en la base desde la migración. Por eso el respaldo va ANTES de cada cambio.
# ⛔ El .env no se imprime: se cambia SÓLO la línea de la imagen de ese entorno, con respaldo en $DIR/.env.antes (600).
# Acceso al repo: deploy key de SÓLO LECTURA /root/.ssh/enenosbit_deploy (Host github-enenosbit en /root/.ssh/config).
set -euo pipefail

ENTORNO="${1:-}"
case "$ENTORNO" in
    prueba) RAMA="${MODERNO_PRUEBA_RAMA:-develop}"; SERVICIO="r2beat-moderno-prueba"; VAR="MODERNO_PRUEBA_IMAGEN"; VOLUMEN="enenos_moderno_prueba_datos" ;;
    prod)   RAMA="${MODERNO_PROD_RAMA:-main}";      SERVICIO="r2beat-moderno";        VAR="MODERNO_IMAGEN";        VOLUMEN="enenos_moderno_datos" ;;
    *) echo "uso: $0 prueba|prod [--forzar]" >&2; exit 2 ;;
esac
FORZAR="${2:-}"
CONJUNTO="${CONJUNTO:-/opt/enenos}"
DIR="$CONJUNTO/moderno_$ENTORNO"
REPO="$DIR/Enenosbit-2027"
URL="${MODERNO_REPO_URL:-git@github-enenosbit:r2beatlatino/Enenosbit-2027.git}"
ENV="$CONJUNTO/.env"
log() { echo "$(date '+%F %T') [moderno-$ENTORNO] $*"; }

mkdir -p "$DIR"
[ -f "$DIR/pausado" ] && [ "$FORZAR" != "--forzar" ] && exit 0
exec 9>"$DIR/.cerrojo"
flock -n 9 || exit 0                                     # una sola vuelta a la vez por entorno

[ -d "$REPO/.git" ] || git clone -q -b "$RAMA" "$URL" "$REPO"
cd "$REPO"
git fetch -q origin "$RAMA"
AHORA="$(git rev-parse --short=8 "origin/$RAMA")"
ETI="$ENTORNO-$AHORA"
IMG="r2beat-moderno:$ETI"
CORRE="$(grep -E "^$VAR=" "$ENV" | cut -d= -f2-)"
[ -n "$CORRE" ] || { log "⛔ el .env no tiene $VAR: no sigo"; exit 1; }
if [ "$FORZAR" != "--forzar" ]; then
    [ "$CORRE" = "$IMG" ] && exit 0                                   # nada nuevo
    [ "$AHORA" = "$(cat "$DIR/fallido" 2>/dev/null)" ] && exit 0     # ya falló: espera otro commit
fi
log "$ENTORNO ($RAMA): $CORRE → $IMG"
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

if [ "$ENTORNO" = "prod" ]; then
    # RESPALDO de las cuentas ANTES de tocar nada. La base SQLite se copia con la API de backup (con WAL, copiar el
    # archivo no es respaldarlo); el resto (cuenta.json, respaldos viejos), con tar. Se guardan los últimos 10.
    VOL="$(docker volume inspect -f '{{.Mountpoint}}' "$VOLUMEN")"
    RES="/root/respaldo_moderno_prod/$(date +%Y%m%d_%H%M%S)_antes_$AHORA"
    mkdir -p "$RES"
    tar -czf "$RES/volumen.tgz" -C "$VOL" --exclude='cuentas.db' --exclude='cuentas.db-wal' --exclude='cuentas.db-shm' .
    if [ -f "$VOL/cuentas.db" ]; then
        python3 - "$VOL/cuentas.db" "$RES/cuentas.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
ok = dst.execute("pragma integrity_check").fetchone()[0]
n = dst.execute("select count(*) from cuentas").fetchone()[0]
dst.close(); src.close()
print("cuentas.db respaldada: integrity=%s, %d cuentas" % (ok, n))
sys.exit(0 if ok == "ok" else 1)
PY
    fi
    log "respaldo de cuentas: $RES ($(du -sh "$RES" | cut -f1))"
    ls -1dt /root/respaldo_moderno_prod/*/ 2>/dev/null | tail -n +11 | xargs -r rm -rf
fi

poner() {                                    # $1 = imagen: la pone en el .env y reinicia SÓLO este servicio
    sed -i "s|^$VAR=.*|$VAR=$1|" "$ENV"
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
log "✅ $ENTORNO en $AHORA ($IMG)"

# limpieza: imágenes y carpetas <entorno>-* viejas, menos la que corre y la anterior (para volver atrás a mano)
for t in $(docker images r2beat-moderno --format '{{.Tag}}' | grep "^$ENTORNO-" || true); do
    [ "r2beat-moderno:$t" = "$IMG" ] || [ "r2beat-moderno:$t" = "$CORRE" ] || docker rmi "r2beat-moderno:$t" >/dev/null 2>&1 || true
done
for d in "$CONJUNTO"/moderno/servidor_"$ENTORNO"-*; do
    [ -d "$d" ] || continue
    t="${d##*/servidor_}"
    [ "r2beat-moderno:$t" = "$IMG" ] || [ "r2beat-moderno:$t" = "$CORRE" ] || rm -rf "$d"
done
