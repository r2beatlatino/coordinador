#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────────────────────
#  publicar_imagenes.sh — las imágenes de la CASA (cuentas y parches), para amd64 Y arm64, a ghcr.io.
#  ★ Coordinador (19-nov): las del juego y la web (`juego`, `web`) se publican desde el repo del R2Beat 2013, que
#    tiene su propia copia de este script (y el exe, los charts y las tablas que esas imágenes llevan).
#  La guía: documentacion/TOPOLOGIA_CONTENEDORES.md §13 y §15.
#
#  Se corre DENTRO del WSL, parado en la raíz de ESTE repo (el coordinador):
#
#      bash herramientas/contenedores/publicar_imagenes.sh construir       2026-11-14   # sólo acá, no sube nada
#      bash herramientas/contenedores/publicar_imagenes.sh subir           2026-11-14   # ⛔ SUBE. Sólo a la orden de Eñeños
#      bash herramientas/contenedores/publicar_imagenes.sh bajar-y-probar  2026-11-14   # baja por digest y corre la prueba
#
#  ⛔ Las imágenes llevan el exe original del juego, sus charts y sus tablas: el paquete tiene que quedar PRIVADO.
#     Por eso no se les pone ninguna etiqueta `org.opencontainers.image.source` (GitHub enlazaría el paquete a ese
#     repo, y si el repo es público lo muestra ahí) ni viajan «attestations» con datos de la construcción.
#  ⛔ `subir` y `bajar-y-probar` piden haber entrado antes al registro. Desde Git Bash de Windows, sin mostrar ni
#     guardar el token:
#         gh auth token | wsl -d Ubuntu-26.04 -u root -- docker login ghcr.io -u r2beatlatino --password-stdin
#     y al terminar:   wsl -d Ubuntu-26.04 -u root -- docker logout ghcr.io
#  ⛔ No existe `latest`: cada subida lleva su fecha, y prod se fija a una fecha (o a un digest).
# ─────────────────────────────────────────────────────────────────────────────────────────────
set -u
ORDEN="${1:-}"; ETIQUETA="${2:-}"
DUENO="${GHCR_DUENO:-r2beatlatino}"
PLATAFORMAS="linux/amd64,linux/arm64"
# <Dockerfile>:<nombre del paquete>. Las piezas que se arman ACÁ (`puerta` también se puede: puerta:enenos-puerta).
#     GHCR_PIEZAS="cuentas:enenos-cuentas" bash …/publicar_imagenes.sh subir <fecha>
PIEZAS="${GHCR_PIEZAS:-cuentas:enenos-cuentas parches:r2beat2013-parches}"
REINTENTOS=15                                              # la red de esta PC corta («tls: bad record MAC»)

case "$ETIQUETA" in ""|latest) echo "⛔ falta la etiqueta (una fecha, p. ej. 2026-11-14). «latest» no se usa."; exit 2;; esac
[ -f herramientas/contenedores/cuentas.Dockerfile ] || { echo "⛔ corré esto parado en la raíz del repo"; exit 2; }
export BUILDX_NO_DEFAULT_ATTESTATIONS=1 BUILDX_GIT_INFO=false

ref() { echo "ghcr.io/$DUENO/$1:$ETIQUETA"; }

digests() {   # imprime «plataforma digest» de cada imagen del índice que está EN EL REGISTRO
  docker buildx imagetools inspect --raw "$1" | python3 -c '
import json, sys
d = json.load(sys.stdin)
for m in d.get("manifests", []):
    p = m.get("platform", {})
    if p.get("os") == "linux":
        print(p["os"] + "/" + p["architecture"], m["digest"])'
}

construir() {
  for par in $PIEZAS; do
    df=${par%%:*}; nombre=${par##*:}; listo=0
    for i in $(seq 1 $REINTENTOS); do
      if docker buildx build --platform "$PLATAFORMAS" --provenance=false --sbom=false \
           -f "herramientas/contenedores/$df.Dockerfile" -t "$(ref "$nombre")" --load . > "/tmp/publicar_$df.log" 2>&1; then listo=1; break; fi
      echo "   $nombre: intento $i falló: $(grep -iE 'error|failed|MAC' "/tmp/publicar_$df.log" | tail -1 | cut -c1-160)"; sleep 3
    done
    [ $listo = 1 ] || { echo "⛔ $nombre NO se pudo construir (ver /tmp/publicar_$df.log)"; exit 1; }
    etiquetas=$(docker image inspect --format '{{json .Config.Labels}}' "$(ref "$nombre")")
    echo "✔ $(ref "$nombre") construida para $PLATAFORMAS (intento $i) · etiquetas de la imagen: $etiquetas"
    # ⛔ Lo que no puede pasar: que la imagen diga que su fuente es un repo NUESTRO (GitHub enlaza el paquete a ese
    #   repo y, si es público, lo muestra ahí). Una etiqueta heredada de la imagen base que apunta al repo de OTRO
    #   (la de Caddy apunta a caddyserver/caddy-docker) no enlaza nada: se avisa y se sigue. Después de subir se
    #   comprueba igual, con `gh api`, que el paquete quedó privado y sin repo.
    fuente=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.source"}}' "$(ref "$nombre")" 2>/dev/null)
    case "$(echo "$fuente" | tr 'A-Z' 'a-z')" in
      *"github.com/$(echo "$DUENO" | tr 'A-Z' 'a-z')"*) echo "⛔ trae org.opencontainers.image.source=$fuente (un repo nuestro): NO subir así"; exit 1;;
      "") ;;
      *) echo "   (hereda de su imagen base image.source=$fuente: no es un repo nuestro, no enlaza nada)";;
    esac
  done
}

case "$ORDEN" in
construir)
  construir
  ;;
subir)
  # ⚠ Siempre se vuelve a construir antes de subir (con la caché tarda segundos): la prueba de mudanza guarda y
  #   recarga las imágenes de UNA arquitectura, y el nombre local puede haber quedado sin la otra (medido el 15-nov).
  construir
  for par in $PIEZAS; do
    nombre=${par##*:}; listo=0
    docker image inspect "$(ref "$nombre")" >/dev/null 2>&1 || { echo "⛔ falta $(ref "$nombre"): primero «construir»"; exit 1; }
    for i in $(seq 1 $REINTENTOS); do
      if docker push --platform linux/amd64 "$(ref "$nombre")" > "/tmp/subir_$nombre.log" 2>&1 \
         && docker push --platform linux/arm64 "$(ref "$nombre")" >> "/tmp/subir_$nombre.log" 2>&1 \
         && docker push "$(ref "$nombre")" >> "/tmp/subir_$nombre.log" 2>&1; then listo=1; break; fi
      echo "   $nombre: intento $i falló: $(grep -iE 'error|denied|unauthorized|MAC' "/tmp/subir_$nombre.log" | tail -1 | cut -c1-160)"; sleep 3
    done
    [ $listo = 1 ] || { echo "⛔ $nombre NO subió tras $REINTENTOS intentos (ver /tmp/subir_$nombre.log). No darlo por hecho."; exit 1; }
    echo "✔ subida $(ref "$nombre") (intento $i)"
    echo "   índice:  $(docker buildx imagetools inspect "$(ref "$nombre")" --format '{{.Manifest.Digest}}')"
    digests "$(ref "$nombre")" | sed 's/^/   /'
  done
  echo
  echo "⛔ FALTA, desde Windows (ahí está el gh): comprobar que cada paquete quedó PRIVADO y sin repo enlazado:"
  for par in $PIEZAS; do echo "     gh api /user/packages/container/${par##*:} --jq '{name, visibility, repo: .repository.full_name}'"; done
  ;;
bajar-y-probar)
  # Lo que se prueba es lo BAJADO: primero se borra de esta máquina todo nombre que apunte a lo construido acá.
  mal=0
  for par in $PIEZAS; do
    nombre=${par##*:}
    digests "$(ref "$nombre")" > "/tmp/digests_$nombre.txt" || { echo "⛔ no pude leer $(ref "$nombre") del registro"; exit 1; }
    [ -s "/tmp/digests_$nombre.txt" ] || { echo "⛔ $(ref "$nombre") no está en el registro"; exit 1; }
    docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E "(^|/)$nombre:" | xargs -r docker image rm -f >/dev/null 2>&1
    while read -r plataforma digest; do
      arq=${plataforma##*/}; listo=0
      for i in $(seq 1 40); do
        if docker pull -q --platform "$plataforma" "ghcr.io/$DUENO/$nombre@$digest" >/dev/null 2>"/tmp/bajar_$nombre.err"; then listo=1; break; fi
        sleep 2
      done
      [ $listo = 1 ] || { echo "⛔ no pude bajar $nombre $plataforma ($digest): $(tail -1 "/tmp/bajar_$nombre.err")"; exit 1; }
      docker tag "ghcr.io/$DUENO/$nombre@$digest" "$nombre:bajada-$arq"
      echo "✔ bajada $nombre $plataforma por su digest $digest (intento $i) -> $nombre:bajada-$arq"
    done < "/tmp/digests_$nombre.txt"
  done
  # ⚠ La prueba de contenedores es del juego + cuentas: pide la imagen del juego ya bajada (r2beat2013-juego:bajada-<arq>,
  #   la publica el repo del 2013) y R2BEAT2013_REPO (una copia de ese repo: de ahí salen bot_carga y sembrar_prueba).
  for arq in amd64 arm64; do
    salida="/tmp/prueba_bajadas_$arq.txt"
    PYTHONIOENCODING=utf-8 python3 -X utf8 pruebas/probar_contenedores.py --docker --plataforma "linux/$arq" \
        --imagenes "r2beat2013-juego:bajada-$arq" "enenos-cuentas:bajada-$arq" > "$salida" 2>&1
    cod=$?
    echo "prueba contra lo BAJADO, $arq: código $cod · $(grep -c '✔' "$salida") en verde · $(grep -c '✘' "$salida") en rojo  ($salida)"
    grep '✘' "$salida" | head -5
    [ $cod = 0 ] || mal=1
  done
  exit $mal
  ;;
*)
  echo "uso: bash herramientas/contenedores/publicar_imagenes.sh construir|subir|bajar-y-probar <etiqueta-con-fecha>"; exit 2;;
esac
