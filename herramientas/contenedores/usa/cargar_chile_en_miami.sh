#!/bin/bash
# ★ 20-nov — LA MUDANZA en Miami: la base FINAL de Chile (sacada con el juego de Chile ya apagado) pasa a ser la del
#   juego de Miami, y Cuenta Eñeños suma las cuentas nuevas y las enlaza. Eñeños: «manda Chile» (lo jugado sólo en
#   Miami por testers se pierde). Validado antes con el ensayo 13 sobre la copia de las 14:47 (15 bien, 0 mal).
#   Entrada: /root/carga_chile/{datos.db,panel.db} — ⛔ traen pass_hash: se borran al terminar. (Los gm/admin.txt de
#   Chile NO vienen: en Miami los roles los maneja el Coordinador y su config/ va vacía.)
# Uso: bash /root/carga_chile/cargar_chile_en_miami.sh
set -euo pipefail
C=/root/carga_chile
cd /opt/enenos
J=$(docker volume inspect -f '{{.Mountpoint}}' enenos_r2beat2013_datos)
U=$(docker volume inspect -f '{{.Mountpoint}}' enenos_cuentas_datos)
R=/root/respaldo_mudanza_$(date +%Y%m%d_%H%M)
mkdir -p "$R"

echo "== 0) lo que llegó de Chile"
for f in datos.db panel.db; do
  python3 -c "import sqlite3,sys;c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True);print(sys.argv[1].split('/')[-1],c.execute('pragma integrity_check').fetchone()[0])" "$C/$f"
done
python3 -c "import sqlite3;c=sqlite3.connect('file:$C/datos.db?mode=ro',uri=True);print('usuarios de Chile:',c.execute('select count(*) from users').fetchone()[0])"

echo "== 1) respaldo de Miami ANTES ($R)"
for db in "$J/datos.db" "$J/panel.db" "$U/cuentas.db" "$U/portero.db"; do
  python3 -c "import sqlite3,sys;s=sqlite3.connect(sys.argv[1]);d=sqlite3.connect(sys.argv[2]);s.backup(d);d.close();print(sys.argv[2],sqlite3.connect(sys.argv[2]).execute('pragma integrity_check').fetchone()[0])" "$db" "$R/$(basename "$(dirname "$db")")_$(basename "$db")"
done
cp -a "$J/config" "$R/juego_config"
cp .env "$R/env"

echo "== 2) el juego de Miami: se apaga, se pone la base de Chile, se prende"
DUENO=$(stat -c %u:%g "$J/datos.db")
docker compose stop r2beat2013
for f in datos.db panel.db; do
  rm -f "$J/$f" "$J/$f-wal" "$J/$f-shm"
  install -o "${DUENO%:*}" -g "${DUENO#*:}" -m 644 "$C/$f" "$J/$f"
done
docker compose up -d --no-deps r2beat2013 2>&1 | grep -v warning || true
sleep 20
docker compose ps --format '{{.Service}} {{.Status}}' r2beat2013

echo "== 3) Cuenta Eñeños: las cuentas nuevas desde la base de Chile, y sus amigos"
mkdir -p "$U/_carga"
install -o "$(stat -c %u "$U/cuentas.db")" -m 600 "$C/datos.db" "$U/_carga/datos.db"
docker exec -w /app enenos-cuentas-1 python -m servidor.portero importar /datos/_carga/datos.db
docker exec -w /app enenos-cuentas-1 python -m servidor.portero importar-amigos /datos/_carga/datos.db --apodos
rm -rf "$U/_carga"

echo "== 4) el juego enlaza cada cuenta con su Eñeños ID, y recién ahí borra las contraseñas de SU base"
docker exec -w /app enenos-r2beat2013-1 python -m servidor.enlazar_cuentas
docker exec -w /app enenos-r2beat2013-1 python -m servidor.enlazar_cuentas vaciar-claves

echo "== 5) limpieza (lo que traía pass_hash)"
rm -f "$C/datos.db" "$C/panel.db"
echo "respaldo de Miami de antes: $R"
