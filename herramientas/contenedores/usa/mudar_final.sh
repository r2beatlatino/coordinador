#!/bin/sh
# ★ 18-nov — el CAMBIO FINAL del ensayo al VPS de USA. Corre EN el de USA (185.147.157.33), en /opt/enenos.
#   ANTES: en Cloudflare, `ensayo` y `auth` (registros A, SIN nube) -> 185.147.157.33.
#   1. trae lo último de /opt/enenos del ensayo viejo (sin pisar lo propio de acá: .env, override, la lista de EDA)
#   2. APAGA la pila del ensayo viejo y copia sus volúmenes en frío (copiar_volumenes.sh final)
#   3. levanta la pila acá
#   4. si el DNS ya apunta acá, prende el sitio en el Caddy del sistema (activar_dns.sh)
#   5. borra la llave temporal de la mudanza del ensayo viejo
#   Volver atrás: `docker compose stop` acá, `activar_dns.sh volver`, DNS a 103.90.160.237 y allá `docker compose start`.
set -eu
cd /opt/enenos
L="ssh -o BatchMode=yes -i ${MUDANZA_LLAVE:?falta MUDANZA_LLAVE: la llave ssh temporal de la mudanza} root@103.90.160.237"
echo "1. lo último de /opt/enenos"
rsync -aH -e "ssh -o BatchMode=yes -i ${MUDANZA_LLAVE:?falta MUDANZA_LLAVE: la llave ssh temporal de la mudanza}" \
	--exclude '.env' --exclude '.env.*' --exclude 'docker-compose.override.yml' \
	--exclude 'eda_web/manifiesto.jws' --exclude 'eda_web/manifiesto.jws.*' \
	root@103.90.160.237:/opt/enenos/ /opt/enenos/
echo "2. los volúmenes, en frío (apaga el ensayo viejo)"
sh copiar_volumenes.sh final
echo "3. la pila acá"
docker compose up -d
sleep 30
docker ps --format '{{.Names}}\t{{.Status}}' | sort
echo "4. el DNS"
for n in ensayo.xn--eeos-gqab.link auth.xn--eeos-gqab.link; do
	ip=$(getent ahostsv4 "$n" | awk 'NR==1{print $1}')
	echo "   $n -> $ip"
	[ "$ip" = 185.147.157.33 ] || { echo "⚠ $n todavía no apunta acá: cuando apunte, correr  sh /opt/enenos/activar_dns.sh"; exit 0; }
done
sh activar_dns.sh
echo "5. la llave temporal"
$L "sed -i '/mudanza-ensayo-temporal/d' /root/.ssh/authorized_keys" && echo "   borrada del ensayo viejo"
echo "✅ mudanza terminada"
