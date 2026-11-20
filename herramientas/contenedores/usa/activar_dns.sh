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
