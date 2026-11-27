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
# ⛔ Prod NO se actualiza con esto: prod sale de `master` y lo aprueba Eñeños.
# ★ 21-nov: con el PANEL encima (prueba_panel/ → $DIR/panel): los controles del Coordinador y el contenido del launcher,
#   con la base de PRUEBA (nada de prod). Sin $DIR/panel/Dockerfile, queda develop solo, como antes.
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
# ★ 21-nov: la DLL de develop → la lista del cliente de PRUEBA (dll_prueba.py: sólo con la prueba «dll» de GitHub en
#   verde). Va aparte del server: mira en cada vuelta aunque el server no cambie, y si falla, todo sigue igual.
if [ -f "$CONJUNTO/dll_prueba.py" ]; then
    python3 "$CONJUNTO/dll_prueba.py" "$REPO" "$RAMA" || echo "$(date '+%F %T') ⚠ dll_prueba falló: la lista de prueba sigue igual"
fi
AHORA="$(git rev-parse --short "origin/$RAMA")"
CORRE="$(docker image inspect -f '{{index .Config.Labels "enenos.commit"}}' "$IMAGEN" 2>/dev/null || true)"
# ★ 21-nov: el PANEL (prueba_panel/): encima de develop van los módulos de PROD, sacados de la imagen del juego de prod
#   (JUEGO_IMAGEN). Si prod cambió de imagen, la de prueba se rearma aunque develop no haya cambiado.
PANEL="$DIR/panel"
PROD_IMAGEN="$(grep -E '^JUEGO_IMAGEN=' "$CONJUNTO/.env" 2>/dev/null | cut -d= -f2-)"
CORRE_PROD="$(docker image inspect -f '{{index .Config.Labels "enenos.privado"}}' "$IMAGEN" 2>/dev/null || true)"
[ -f "$PANEL/Dockerfile" ] && [ -n "$PROD_IMAGEN" ] || PROD_IMAGEN=""
# ★ 27-nov: lo PRIVADO que todavía NO está en prod (p. ej. el enganche de las cuentas GM NPC en contenido_interno.py)
#   va en $DIR/panel_encima/ y PISA lo sacado de prod, sólo en el de prueba. ⚠ Se congela: cuando eso llegue a prod,
#   se borra de ahí (si no, el de prueba se queda con la versión vieja de ese archivo). Si cambia, se rearma.
ENCIMA="$DIR/panel_encima"
SUMA_ENCIMA="$( (cd "$ENCIMA" 2>/dev/null && find . -type f -print0 | sort -z | xargs -0 -r md5sum) | md5sum | cut -c1-12)"
CORRE_ENCIMA="$(docker image inspect -f '{{index .Config.Labels "enenos.encima"}}' "$IMAGEN" 2>/dev/null || true)"
if [ "${1:-}" != "--forzar" ]; then
    [ "$AHORA" = "$CORRE" ] && [ "$PROD_IMAGEN" = "$CORRE_PROD" ] && [ "$SUMA_ENCIMA" = "$CORRE_ENCIMA" ] && exit 0   # nada nuevo
    [ "$AHORA" = "$(cat "$DIR/fallido" 2>/dev/null)" ] && exit 0         # ya falló: espera otro commit
fi
echo "$(date '+%F %T') prueba ($RAMA): ${CORRE:-nada} → $AHORA"
git reset -q --hard "origin/$RAMA"
if ! docker build -q --label "enenos.commit=$AHORA" -f despliegue/Dockerfile -t "${IMAGEN}-nueva" . ; then
    echo "$(date '+%F %T') ⛔ no se pudo armar $AHORA (¿fallaron sus pruebas?). Sigue el anterior (${CORRE:-ninguno})."
    echo "$AHORA" > "$DIR/fallido"
    exit 1
fi
if [ -n "$PROD_IMAGEN" ]; then
    # ⛔ estos archivos NO están en ningún repo público: salen de la imagen de prod, al armar (ver prueba_panel/)
    rm -rf "$PANEL/servidor" && mkdir -p "$PANEL/servidor"
    TMPC="$(docker create "$PROD_IMAGEN")"
    for f in api_web.py seguridad_panel.py asistencia.py clasificacion.py geoip_paises.bin launcher_api.py launcher_contenido.py              npc_charla.py panel_admin.py portero.py portero_panel.html portero_panel.js respaldo.py ruleta.py              ruleta_mayor.json ruleta_ropa.json tienda_launcher.py contenido_interno.py; do
        docker cp -q "$TMPC:/app/servidor/$f" "$PANEL/servidor/" || echo "$(date '+%F %T') ⚠ $f no está en $PROD_IMAGEN"
    done
    docker rm -f "$TMPC" >/dev/null
    if [ -d "$ENCIMA" ] && [ -n "$(ls -A "$ENCIMA")" ]; then
        cp -f "$ENCIMA"/* "$PANEL/servidor/"
        echo "$(date '+%F %T') panel: ENCIMA de prod (sólo prueba): $(ls "$ENCIMA" | tr '
' ' ')"
    fi
    if ! docker build -q --build-arg BASE="${IMAGEN}-nueva" --label "enenos.privado=$PROD_IMAGEN" --label "enenos.encima=$SUMA_ENCIMA"             -t "${IMAGEN}-nueva" "$PANEL" ; then
        echo "$(date '+%F %T') ⛔ el panel no se pudo poner encima de $AHORA ($PROD_IMAGEN). Sigue el anterior."
        echo "$AHORA" > "$DIR/fallido"
        exit 1
    fi
    rm -rf "$PANEL/servidor"
    echo "$(date '+%F %T') panel: los módulos de $PROD_IMAGEN encima de $AHORA"
fi
docker tag "${IMAGEN}-nueva" "$IMAGEN"
docker rmi -f "${IMAGEN}-nueva" >/dev/null 2>&1 || true
rm -f "$DIR/fallido"
cd "$CONJUNTO"
docker compose up -d --no-deps r2beat2013-prueba
docker image prune -f >/dev/null 2>&1 || true
echo "$(date '+%F %T') ✅ prueba en $AHORA"
