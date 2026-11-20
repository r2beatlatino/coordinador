#!/bin/sh
# «Generar backup» — se corre A MANO en el VPS, como root, parado en la raíz del repo coordinador:
#     sh herramientas/respaldo/generar_backup.sh
# Deja enenos_respaldo_<fecha>.tar.gz.age en /opt/enenos/respaldos (sólo root). Bajarlo con scp y BORRARLO del VPS.
#
# Todo se monta en sólo lectura, salvo las carpetas de las bases SQLite: para leer una base en vivo SQLite necesita
# poder escribir su archivo -shm. El respaldo no escribe nada más (abre cada base con mode=ro).
set -eu
AQUI=$(cd "$(dirname "$0")" && pwd)
LISTA=${LISTA:-$AQUI/respaldo_vps.json}
PARA=${PARA:-$AQUI/llave_publica.txt}
SALIDA=${SALIDA:-/opt/enenos/respaldos}
[ -s "$PARA" ] || { echo "⛔ falta la llave pública en $PARA (ver crear_llave.sh)"; exit 1; }
mkdir -p "$SALIDA" && chmod 700 "$SALIDA"
docker build -q -f "$AQUI/respaldo.Dockerfile" -t enenos-respaldo "$AQUI" >/dev/null
RW=$(python3 -c "import json,os,sys; c=json.load(open(sys.argv[1]))['cosas']; print(' '.join(sorted({'/'+os.path.dirname(x['ruta']) for x in c if x['tipo']=='sqlite' and os.path.exists('/'+x['ruta'])})))" "$LISTA")
MONTAJES=""
for d in $RW; do MONTAJES="$MONTAJES -v $d:/origen$d"; done
# shellcheck disable=SC2086
docker run --rm -v /:/origen:ro $MONTAJES -v "$SALIDA":/salida -v "$LISTA":/lista.json:ro -v "$PARA":/para.txt:ro \
    enenos-respaldo armar --lista /lista.json --origen /origen --salida /salida --para /para.txt
ls -la "$SALIDA" | tail -3
