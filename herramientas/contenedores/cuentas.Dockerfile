# ─────────────────────────────────────────────────────────────────────────────────────────────
#  «Cuenta Eñeños» — el servicio de cuentas, en un contenedor.   documentacion/TOPOLOGIA_CONTENEDORES.md
#
#  ETAPA 0 (hoy): es el PORTERO tal cual (`servidor/portero.py`), sin cambiarle el comportamiento.
#  Todavía LEE las cuentas de la `datos.db` de R2Beat (sólo lectura), que le llega por el volumen
#  del juego montado en `/juego`. Lo suyo (`portero.db` y la clave que firma) vive en `/datos`.
#
#      docker build -f herramientas/contenedores/cuentas.Dockerfile -t enenos-cuentas .
#
#  ★ Coordinador (19-nov): se suma `servidor/lanzamientos.py`, que `portero.py` importa al arrancar (faltaba en la
#    lista: sin él la imagen no arranca). Se construye parado en la RAÍZ de este repo.
#  ★ 19-nov: el panel del Coordinador (`servidor/coordinador.py` + `servidor/panel/`) y `juegos.json` (el catálogo: de ahí
#    salen las tarjetas). El ARTE de los juegos no: va en el volumen (`/datos/panel_arte/`, ver PANEL_COORDINADOR.md).
#  ⛔ En la imagen va SÓLO lo que lista `cuentas.Dockerfile.dockerignore`, y nada más. Ni base ni clave: la clave la crea él
#     la primera vez, ADENTRO DEL VOLUMEN, y no sale de ahí.
#  ★ Biblioteca estándar pura (la firma Ed25519 está escrita en Python): sirve para amd64 y arm64.
# ─────────────────────────────────────────────────────────────────────────────────────────────
ARG PYTHON=3.13-slim-bookworm
FROM python:${PYTHON}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

# El MISMO uid que la imagen del juego (ver `juego.Dockerfile` en el repo del R2Beat 2013).
RUN groupadd -g 10013 r2 && useradd -u 10013 -g 10013 -M -d /app -s /usr/sbin/nologin r2 \
 && mkdir -p /app/servidor /datos/config /datos/manifiestos /datos/panel_arte /juego && chown -R r2:r2 /datos

WORKDIR /app
COPY --chown=root:root servidor/__init__.py servidor/portero.py servidor/vinculos.py servidor/social.py servidor/firma_ed25519.py \
     servidor/lanzamientos.py servidor/coordinador.py servidor/portero_panel.html servidor/portero_panel.js /app/servidor/
# ★ 19-nov: el panel del Coordinador (la página, sin datos ni arte de los juegos) y el catálogo de los juegos
COPY --chown=root:root servidor/panel /app/servidor/panel
COPY --chown=root:root juegos.json /app/juegos.json

ENV R2_BASE=/juego/datos.db \
    R2_PORTERO_BASE=/datos/portero.db \
    R2_PORTERO_CLAVE=/datos/portero_clave.json \
    R2_PORTERO_MANIFIESTOS=/datos/manifiestos \
    R2_ADMIN_ARCHIVO=/datos/config/admin.txt \
    R2_MODERADOR_ARCHIVO=/datos/config/moderadores.txt \
    R2_PORTERO_HOST=0.0.0.0 \
    R2_PORTERO_PUERTO=48195

USER r2
VOLUME ["/datos"]
EXPOSE 48195

HEALTHCHECK --interval=30s --start-interval=2s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/salud' % (os.environ.get('R2_PORTERO_PUERTO') or 48195), timeout=3).read()"]

CMD ["python", "-m", "servidor.portero"]
