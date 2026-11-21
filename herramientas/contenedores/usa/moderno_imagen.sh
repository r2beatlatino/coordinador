#!/usr/bin/env bash
# ★ 21-nov — ARMA la imagen del server de Eñeñosbit 2027 (el R2Beat moderno) a partir de la ENTREGA de Fluidez, de una
#   sola vez y siempre igual (en vez de la cadena de parches 1121 → 1121b → 1121c). Como las otras imágenes de la pila:
#   una etiqueta con la fecha, las etiquetas `enenos.*` (de dónde salió) y un HEALTHCHECK (el login contesta).
#
#   Entra:  el paquete .tgz de la entrega (+ su .sha256) y, si hace falta, una carpeta con archivos que PISAN al paquete
#           (los arreglos que Fluidez pasó sueltos, con la misma ruta: servidor/neutro.py…).
#   Sale:   la imagen r2beat-moderno:<etiqueta>. NO la pone a correr: eso es MODERNO_IMAGEN (y/o MODERNO_PRUEBA_IMAGEN)
#           en /opt/enenos/.env + `docker compose up -d --no-deps r2beat-moderno` (⛔ reinicia ESE server: preguntar).
#
#   Uso:  bash /opt/enenos/moderno_imagen.sh <paquete.tgz> <etiqueta> [carpeta que pisa]
#   p. ej. bash /opt/enenos/moderno_imagen.sh /root/entrega_r2beat_moderno_1121/r2beat-moderno-servidor_2026-11-21b.tgz \
#            2026-11-21 /root/entrega_r2beat_moderno_1121/1121c
set -euo pipefail
PAQ="${1:?falta el paquete .tgz}"
ETI="${2:?falta la etiqueta (p. ej. 2026-11-21)}"
PISA="${3:-}"
IMG="r2beat-moderno:$ETI"
DIR="/opt/enenos/moderno/servidor_$ETI"
log() { echo "$(date '+%F %T') [moderno-imagen] $*"; }

[ -f "$PAQ" ] || { log "⛔ no está $PAQ"; exit 1; }
if [ -f "$PAQ.sha256" ]; then
    ( cd "$(dirname "$PAQ")" && sha256sum -c "$(basename "$PAQ").sha256" >/dev/null ) || { log "⛔ el sha256 del paquete NO coincide"; exit 1; }
    log "sha256 del paquete: ok"
else
    log "⚠ el paquete no trae .sha256"
fi
docker image inspect "$IMG" >/dev/null 2>&1 && { log "⛔ $IMG ya existe: usar otra etiqueta"; exit 1; }
rm -rf "$DIR" && mkdir -p "$DIR"
tar -xzf "$PAQ" -C "$DIR"
[ -f "$DIR/vps/Dockerfile" ] && [ -d "$DIR/servidor" ] || { log "⛔ el paquete no trae vps/Dockerfile y servidor/"; exit 1; }
if [ -n "$PISA" ]; then
    [ -d "$PISA" ] || { log "⛔ no está la carpeta que pisa: $PISA"; exit 1; }
    (cd "$PISA" && find . -type f) | while read -r f; do
        log "pisa: ${f#./} ($(md5sum "$PISA/$f" | cut -c1-12))"
        mkdir -p "$DIR/$(dirname "$f")" && cp "$PISA/$f" "$DIR/$f"
    done
fi
# la del paquete + lo de la pila (etiquetas y el HEALTHCHECK del login), sin tocar su Dockerfile
cat "$DIR/vps/Dockerfile" > "$DIR/Dockerfile.enenos"
cat >> "$DIR/Dockerfile.enenos" <<EOF

# ── agregado por moderno_imagen.sh (repo coordinador) ──
LABEL enenos.juego="r2beat-moderno" enenos.paquete="$(basename "$PAQ")" enenos.pisa="$(basename "${PISA:-ninguno}")" enenos.armada="$(date -u +%FT%TZ)"
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \\
  CMD python -c "import os,socket; socket.create_connection(('127.0.0.1', int(os.environ.get('PUERTOS','28004').split(',')[0])), 3).close()"
EOF
docker build -q -f "$DIR/Dockerfile.enenos" -t "$IMG" "$DIR" >/dev/null
# el control: arranca, importa todo el server (las librerías de afuera incluidas) y trae los archivos que pisaron
docker run --rm --entrypoint sh "$IMG" -c 'cd /app/servidor && python -c "
import importlib, pkgutil, sys
sys.path.insert(0, \".\")
malos = []
for m in pkgutil.iter_modules([\".\"]):
    try:
        importlib.import_module(m.name)
    except SystemExit:
        pass
    except Exception as e:
        malos.append((m.name, repr(e)[:80]))
print(\"módulos con error al importar:\", malos or \"ninguno\")
sys.exit(1 if any(\"ModuleNotFoundError\" in e for _, e in malos) else 0)
"' || { log "⛔ a la imagen le falta una librería: no se usa"; docker rmi "$IMG" >/dev/null; exit 1; }
if [ -n "$PISA" ]; then
    (cd "$PISA" && find . -type f) | while read -r f; do
        a=$(md5sum "$PISA/$f" | cut -c1-32); b=$(docker run --rm --entrypoint md5sum "$IMG" "/app/${f#./}" | cut -c1-32)
        [ "$a" = "$b" ] || { log "⛔ ${f#./} no quedó en la imagen"; exit 1; }
    done
fi
log "✅ $IMG lista ($(docker image inspect -f '{{.Size}}' "$IMG" | awk '{printf "%.0f MB", $1/1048576}'))"
