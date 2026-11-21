#!/usr/bin/env bash
# ★ 18-nov — el EDA del ENSAYO sigue a PROD solo (Benja: «que eda ensayo use el mismo repo que usa el viejo
#   launcher», «su trabajo manda»). Corre en el VPS de USA, cada 5 min (/etc/cron.d/enenos-eda-ensayo), con el MISMO
#   candado que el actualizador de prod (no arma mientras prod hace `git reset` en /opt/eda/prod).
#
#   1. LA LISTA DEL CLIENTE: cuando cambia /opt/eda/manifiesto/eda.json (lo que publica EDA), arma la del ensayo con
#      los MISMOS archivos y el server y el canje del ensayo, y la firma con la clave de EDA del VPS (el launcher la
#      acepta). La anterior queda como manifiesto.jws.antes.
#   2. EL SERVER: cuando /opt/eda/prod (rama main) cambia y YA trae el ingreso con Cuenta Eñeños (PR #49 de
#      r2beatlatino/EDA), arma `eda-server:ensayo-<commit>` con el mismo Dockerfile (corre sus pruebas al armar),
#      lo pone en /opt/enenos/.env y reinicia sólo el EDA del ensayo. Si no contesta, vuelve a la imagen de antes.
#   ★ 21-nov: y la lista del server de PRUEBA de EDA (develop → eda-prueba, red host, 35900): los MISMOS archivos,
#      con su server y su canje (`/eda-prueba/pase`, que el Caddy del sistema lleva a 127.0.0.1:35901), en
#      eda_web/prueba.jws → https://ensayo.eñeños.link/eda-prueba/lista.jws (el botón «Servidor de prueba» del launcher).
#   SOLO_LISTA=1: hace sólo el paso 1 (para correrlo a mano sin que arme ni reinicie el server).
#   No toca prod ni prueba de EDA, ni su repo.
set -euo pipefail
EDA=/opt/eda
ENS=/opt/enenos
EST=$ENS/eda_web/.sigue_a_prod
SERVIDOR="185.147.157.33:25910"
CANJE="https://ensayo.xn--eeos-gqab.link/eda/pase"
SERVIDOR_PRUEBA="185.147.157.33:35900"
CANJE_PRUEBA="https://ensayo.xn--eeos-gqab.link/eda-prueba/pase"
mkdir -p "$EST"
log() { echo "$(date '+%F %T') [eda-ensayo] $*"; }

# ── 1. las listas (la del ensayo = prod, y la del server de PRUEBA) ──
FUENTE=$EDA/manifiesto/eda.json
# armar_lista <server> <canje> <archivo en eda_web> <marca>: la firma con la clave de EDA si cambió la de EDA.
#   Devuelve 0 = igual · 1 = la cambió · 2 = falló (y la de antes queda). ⚠ Dentro de un `||` el `set -e` NO corta
#   (bash lo apaga en la función entera): por eso cada paso se comprueba a mano.
armar_lista() {
    local SRV="$1" CJ="$2" SALIDA="$ENS/eda_web/$3" MARCA="$EST/$4" H
    H=$(sha256sum "$FUENTE" | cut -c1-16)
    [ "$H" = "$(cat "$MARCA" 2>/dev/null || true)" ] && [ -f "$SALIDA" ] && return 0
    python3 - "$FUENTE" "$SRV" "$CJ" > "$EST/eda.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for k in ("aud", "iat"):
    d.pop(k, None)
d["servidor"], d["canje"] = sys.argv[2], sys.argv[3]
# ★ 18-nov: los archivos, por la CDN del sistema nuevo (los mismos de prod: /opt/eda/files-eda/<versión>/)
d["base"] = "https://cdn.xn--eeos-gqab.link/eda/" + d["base"].rstrip("/").rsplit("/", 1)[-1] + "/"
assert d.get("files") and d.get("version"), "eda.json sin archivos o sin versión"
json.dump(d, sys.stdout, ensure_ascii=False)
PY
    [ $? -eq 0 ] || { log "⛔ $3: no se pudo armar la lista"; return 2; }
    # (la firma necesita pycryptodome: la tiene la imagen de EDA, no el sistema. Un contenedor descartable, todo de lectura)
    docker run --rm --network none --entrypoint python         -v "$EDA/prod/herramientas:/h:ro" -v "$EDA/claves:/k:ro" -v "$EST:/e:ro" eda-server:prod         /h/firmar_manifiesto.py firmar /e/eda.json /k/manifiesto-actual.pem > "$EST/nueva.jws"         || { log "⛔ $3: no se pudo firmar"; return 2; }
    python3 - "$EST/nueva.jws" "$SRV" "$CJ" <<'PY'
import base64, json, sys
a, b, c = open(sys.argv[1]).read().strip().split(".")
d = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)))
assert d["servidor"] == sys.argv[2] and d["canje"] == sys.argv[3] and d["aud"] == "eda-launcher" and d["files"],     "la lista nueva no es la que se pidió"
PY
    [ $? -eq 0 ] || { log "⛔ $3: la firmada no es la que se pidió: queda la de antes"; return 2; }
    [ -f "$SALIDA" ] && cp "$SALIDA" "$SALIDA.antes"
    mv "$EST/nueva.jws" "$SALIDA"
    echo "$H" > "$MARCA"
    log "lista $3 = la de prod $(python3 -c "import json;print(json.load(open('$FUENTE'))['version'])") (server $SRV)"
    return 1                                                         # (1 = cambió)
}
if [ -f "$FUENTE" ]; then
    r=0; armar_lista "$SERVIDOR" "$CANJE" manifiesto.jws lista || r=$?
    if [ "$r" = 1 ]; then
        # ★ 18-nov (Benja: «que siempre funcione así durante parches»): la versión nueva, precalentada en la CDN
        python3 "$ENS/precalentar_cdn.py" --eda >> "$ENS/precalentar.log" 2>&1 || log "⚠ el precalentado de EDA tuvo fallas (ver precalentar.log)"
    fi
    armar_lista "$SERVIDOR_PRUEBA" "$CANJE_PRUEBA" prueba.jws lista-prueba || true
fi
[ "${SOLO_LISTA:-}" = "1" ] && exit 0
# ── 2. el server ──
cd "$EDA/prod"
grep -q "EDA_CUENTAS_CLAVE_PUBLICA" servidor/config.py || exit 0          # main todavía no trae Cuenta Eñeños
SHA=$(git rev-parse --short HEAD)
[ "$SHA" = "$(cat "$EST/server" 2>/dev/null || true)" ] && exit 0
[ "$SHA" = "$(cat "$EST/server.fallido" 2>/dev/null || true)" ] && exit 0
IMG="eda-server:ensayo-$SHA"
log "server: armando $IMG (main $SHA)"
if ! docker build -q -t "$IMG" -f despliegue/Dockerfile . >/dev/null; then
    log "⛔ no se pudo armar $IMG: sigue el de antes"; echo "$SHA" > "$EST/server.fallido"; exit 1
fi
ANTES=$(sed -n 's/^EDA_IMAGEN=//p' "$ENS/.env")
cp "$ENS/.env" "$ENS/.env.antes-eda-$SHA"
sed -i "s|^EDA_IMAGEN=.*|EDA_IMAGEN=$IMG|" "$ENS/.env"
cd "$ENS" && docker compose up -d eda >/dev/null 2>&1
sleep 8
if docker exec enenos-eda-1 sh -c 'python -m servidor.red prueba "127.0.0.1:${EDA_PUERTO}"' >/dev/null 2>&1; then
    echo "$SHA" > "$EST/server"; rm -f "$EST/server.fallido"
    log "✅ server del ensayo = main $SHA ($IMG; antes $ANTES)"
else
    log "⛔ $IMG no contesta: vuelvo a $ANTES"
    sed -i "s|^EDA_IMAGEN=.*|EDA_IMAGEN=$ANTES|" "$ENS/.env"
    docker compose up -d eda >/dev/null 2>&1 || true
    echo "$SHA" > "$EST/server.fallido"; exit 1
fi
