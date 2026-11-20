#!/bin/sh
# ★ 18-nov — copia los VOLÚMENES del ensayo (103.90.160.237) a este VPS (USA). Corre EN el de USA.
#   copiar_volumenes.sh           en caliente (para PROBAR la pila acá; las bases pueden quedar a medio escribir)
#   copiar_volumenes.sh final     la de verdad: APAGA la pila del ensayo viejo, copia y la deja apagada
#                                 (después: docker compose up -d acá, y el DNS)
set -eu
L="ssh -o BatchMode=yes -i ${MUDANZA_LLAVE:?falta MUDANZA_LLAVE: la llave ssh temporal de la mudanza} root@103.90.160.237"
VOLS="cuentas_datos r2beat2013_datos r2beat2013_prueba_datos puerta_datos parches_releases web_datos eda_estado gunbound_datos gunbound_prueba_datos"
if [ "${1:-}" = final ]; then
	$L "cd /opt/enenos && docker compose stop"
fi
cd /opt/enenos && docker compose stop 2>/dev/null || true
for v in $VOLS; do
	n="enenos_$v"
	docker volume inspect "$n" >/dev/null 2>&1 || docker volume create "$n" >/dev/null
	d=$(docker volume inspect "$n" --format '{{.Mountpoint}}')
	find "$d" -mindepth 1 -delete
	$L "tar -C /var/lib/docker/volumes/$n/_data -cf - ." | tar -C "$d" -xpf -
	echo "  $n: $(du -sh "$d" | cut -f1)"
done
# (el ensayo viejo tiene web_datos con SUS certificados: acá los saca el Caddy del sistema; no molestan)
echo "✅ volúmenes copiados"
