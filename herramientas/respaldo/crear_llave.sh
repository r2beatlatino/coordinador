#!/bin/sh
# Crea LA llave del respaldo (una sola vez). Lo corre EÑEÑOS en su PC, en una terminal (le pide una contraseña).
#     sh herramientas/respaldo/crear_llave.sh  C:/ruta/donde/guardarla
# Deja: enenos_respaldo_llave.age  = la llave PRIVADA, cifrada con tu contraseña (guardala en 2 lugares FUERA de la PC)
#       herramientas/respaldo/llave_publica.txt = la PÚBLICA (ésa sí va al repo: sólo sirve para cifrar)
# Usa `age` si está instalado (winget install FiloSottile.age); si no, Docker.
# ⛔ Sin la llave privada + su contraseña, NINGÚN respaldo se puede abrir. La llave sin cifrar nunca toca el disco
#    fuera de un archivo temporal que se borra al terminar.
set -eu
DEST=${1:?"decime en qué carpeta guardo la llave privada"}
AQUI=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$DEST"
[ -e "$DEST/enenos_respaldo_llave.age" ] && { echo "⛔ ya hay una llave en $DEST: no la piso"; exit 1; }
if command -v age-keygen >/dev/null 2>&1; then
  TMP=$(mktemp)
  trap 'rm -f "$TMP"' EXIT
  age-keygen 2>/dev/null > "$TMP"
  age-keygen -y "$TMP" > "$DEST/llave_publica.txt"
  echo "Ahora age te pide la CONTRASEÑA que protege la llave (dos veces):"
  age -p -o "$DEST/enenos_respaldo_llave.age" "$TMP"
else
  docker build -q -f "$AQUI/respaldo.Dockerfile" -t enenos-respaldo "$AQUI" >/dev/null
  docker run --rm -it -v "$DEST":/llave --entrypoint sh enenos-respaldo -c '
    set -e
    age-keygen -o /tmp/llave.txt 2>/dev/null
    age-keygen -y /tmp/llave.txt > /llave/llave_publica.txt
    echo "Ahora age te pide la CONTRASEÑA que protege la llave (dos veces):"
    age -p -o /llave/enenos_respaldo_llave.age /tmp/llave.txt
    rm -f /tmp/llave.txt'
fi
cp "$DEST/llave_publica.txt" "$AQUI/llave_publica.txt"
echo "✔ llave privada (cifrada): $DEST/enenos_respaldo_llave.age"
echo "✔ llave pública: $(cat "$AQUI/llave_publica.txt")"
echo "  → herramientas/respaldo/llave_publica.txt: commitearla (y subirla al VPS con el repo)"
