#!/bin/sh
# ★ 20-nov (Eñeños: «desconectar EDA de Chile… todo Miami»): se RETIRA el EDA viejo (eda-prod, el que validaba el pase
#   con el JWKS de r2beatlatino.com = Chile, y su /admin que iba a Chile). Queda un solo EDA: el de /opt/enenos
#   (Cuenta Eñeños), que se actualiza solo desde GitHub main. Sus datos: SÓLO respaldo (Eñeños: «empiezan de cero»).
set -eu
R=/root/respaldo_eda_viejo_$(date +%Y%m%d_%H%M)
mkdir -p "$R"
tar czf "$R/estado-prod.tgz" -C /opt/eda estado-prod
cp -p /etc/cron.d/eda "$R/cron.eda"
cp -p /etc/caddy/Caddyfile "$R/Caddyfile"
cp -p /opt/eda/prod.env "$R/prod.env"
docker inspect eda-prod --format '{{.Config.Image}} {{.HostConfig.RestartPolicy.Name}}' > "$R/contenedor.txt"
echo "respaldo: $R"; ls -la "$R"

# 1. el contenedor: se APAGA (no se borra: volver = docker update --restart=unless-stopped eda-prod && docker start eda-prod)
flock /tmp/eda-prod.lock docker update --restart=no eda-prod >/dev/null
docker stop eda-prod >/dev/null
echo "eda-prod: $(docker inspect -f '{{.State.Status}}' eda-prod)"

# 2. el actualizador de prod pasa a SÓLO bajar main a /opt/eda/prod (de ahí arma eda_ensayo.sh el EDA de Miami);
#    ya no arma ni reinicia eda-prod. El de prueba (develop → eda-prueba) queda igual.
cat > /etc/cron.d/eda <<'CRON'
# EDA: PRUEBA sigue a develop (eda-prueba). ★ 20-nov: el EDA viejo (eda-prod, atado al login de Chile) se RETIRÓ;
#   la línea de prod sólo baja main a /opt/eda/prod, de donde /opt/enenos/eda_ensayo.sh arma el EDA de Miami.
*/5 * * * * root cp /opt/eda/prod/despliegue/actualizar.sh /tmp/eda-act-prueba.sh && flock -n /tmp/eda-prueba.lock bash /tmp/eda-act-prueba.sh prueba >> /opt/eda/actualizaciones.log 2>&1
*/5 * * * * root flock -w 240 /tmp/eda-prod.lock sh -c 'cd /opt/eda/prod && git fetch -q origin main && git reset -q --hard origin/main' >> /opt/eda/actualizaciones.log 2>&1
CRON
chmod 644 /etc/cron.d/eda
cat /etc/cron.d/eda

# 3. Caddy sin el /admin que iba a Chile (caddy.sh sin el 3.er dato; conserva los import del ensayo y la CDN)
sh /opt/eda/caddy.sh xn--eeos-gqab.link 25901
grep -c "r2beatlatino" /etc/caddy/Caddyfile || true
grep -n "^import" /etc/caddy/Caddyfile
