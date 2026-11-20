#!/bin/sh
# ★ 18-nov — la MUDANZA del ensayo al VPS de USA (185.147.157.33), donde vive EDA (Benja: «mudar todo»; ⛔ Chile no).
# Corre EN el VPS de USA, después de copiar /opt/enenos desde el ensayo (103.90.160.237). Deja la pila del ensayo
# CONVIVIENDO con lo que ya había (el Caddy del sistema con eñeños.link y EDA de prod y prueba):
#   · la web del ensayo NO toma 80/443: escucha en 127.0.0.1:8088 (HTTP) y el Caddy del sistema le pasa
#     ensayo.xn--eeos-gqab.link y auth.xn--eeos-gqab.link (eso se prende con activar_dns.sh, DESPUÉS de que el DNS
#     apunte acá: si no, Caddy pide el certificado y falla);
#   · sin el EDA del ensayo (sus puertos son los del EDA real de esta máquina): COMPOSE_PROFILES=prueba,gunbound;
#   · la IP pública es la de esta máquina.
set -eu
cd /opt/enenos
V=/var/lib/docker/volumes
[ -f .env.del-ensayo ] || cp .env .env.del-ensayo
[ -f docker-compose.yml.del-ensayo ] || cp docker-compose.yml docker-compose.yml.del-ensayo

poner() {  # poner CLAVE valor  (la cambia o la agrega)
	if grep -q "^$1=" .env; then sed -i "s#^$1=.*#$1=$2#" .env; else echo "$1=$2" >> .env; fi
}
poner R2_IP_PUBLICA 185.147.157.33
poner WEB_NOMBRE :80
poner WEB_AUTH_NOMBRE http://auth.xn--eeos-gqab.link
poner COMPOSE_PROFILES prueba,gunbound
poner WEB_IMAGEN r2beat2013-web:ensayo13-usa

cat > docker-compose.override.yml <<'FIN'
# ★ 18-nov (VPS de USA): la web del ensayo detrás del Caddy del SISTEMA (que tiene 443 con eñeños.link y EDA).
#   Escucha sólo adentro, en HTTP; el Caddy de afuera le pasa ensayo.* y auth.* (/etc/caddy/enenos-ensayo.caddy).
services:
  web:
    ports: !override
      - "127.0.0.1:8088:80"
FIN

# la imagen de la web, con el Caddy de adentro confiando en el de afuera (la IP real del jugador en X-Forwarded-For)
mkdir -p /root/ctx_web13usa && cd /root/ctx_web13usa
cat > Dockerfile <<'FIN'
FROM r2beat2013-web:ensayo13
USER root
RUN printf '{\n\tservers {\n\t\ttrusted_proxies static private_ranges\n\t}\n}\n\n' > /tmp/g \
 && cat /tmp/g /etc/caddy/Caddyfile > /tmp/c && cp /tmp/c /etc/caddy/Caddyfile && rm /tmp/g /tmp/c \
 && caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile \
 && grep -q trusted_proxies /etc/caddy/Caddyfile
USER r2
FIN
docker build -q -t r2beat2013-web:ensayo13-usa . >/dev/null
cd /opt/enenos

# el sitio del ensayo para el Caddy del sistema: LISTO pero sin prender (activar_dns.sh)
cat > /etc/caddy/enenos-ensayo.caddy <<'FIN'
# ★ 18-nov el ENSAYO (la pila /opt/enenos) — sin la nube: Caddy saca el certificado solo (TLS-ALPN por el 443).
ensayo.xn--eeos-gqab.link, auth.xn--eeos-gqab.link {
	reverse_proxy 127.0.0.1:8088
}
FIN
cat > /opt/enenos/activar_dns.sh <<'FIN'
#!/bin/sh
# ★ 18-nov: correr DESPUÉS de apuntar en Cloudflare `ensayo` y `auth` (sin nube) a 185.147.157.33.
#   Prende el sitio del ensayo en el Caddy del sistema y abre el 443 a todos (el sitio de eñeños.link sigue
#   rechazando lo que no venga de Cloudflare: tiene su propio @no_cf). `activar_dns.sh volver` lo apaga.
set -eu
if [ "${1:-}" = volver ]; then
	sed -i '/^import \/etc\/caddy\/enenos-ensayo.caddy$/d' /etc/caddy/Caddyfile
	systemctl reload caddy; echo "apagado el sitio del ensayo"; exit 0
fi
cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.antes-ensayo
grep -q '^import /etc/caddy/enenos-ensayo.caddy$' /etc/caddy/Caddyfile || printf '\nimport /etc/caddy/enenos-ensayo.caddy\n' >> /etc/caddy/Caddyfile
# (que caddy.sh de EDA lo vuelva a poner si regenera el Caddyfile)
grep -q 'enenos-ensayo.caddy' /opt/eda/caddy.sh || sed -i 's#^install -m 644 "$NUEVO" /etc/caddy/Caddyfile#printf "\\nimport /etc/caddy/enenos-ensayo.caddy\\n" >> "$NUEVO"\n&#' /opt/eda/caddy.sh
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
systemctl reload caddy
ufw allow 443/tcp comment "ensayo (sin nube)" >/dev/null
ufw allow 443/udp comment "ensayo (sin nube)" >/dev/null
echo "✅ sitio del ensayo prendido; el certificado sale solo en 1-2 min"
FIN
chmod +x /opt/enenos/activar_dns.sh
docker compose config -q && echo "✅ preparado (falta copiar los volúmenes y levantar)"
