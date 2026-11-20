# ─────────────────────────────────────────────────────────────────────────────────────────────
#  R2Beat 2013 — el servidor de PARCHES (`patchserver.py`), en un contenedor.
#  La guía: documentacion/TOPOLOGIA_CONTENEDORES.md
#
#      docker build -f herramientas/contenedores/parches.Dockerfile -t r2beat2013-parches .
#
#  · En la imagen van TRES archivos (`patchserver.py`, `make_manifest.py`, `arranque.py`) y nada más.
#  · Las releases del cliente (varios GB) NO van en la imagen: se montan en `/releases`.
#  · Para `/auth` hoy lee la tabla `users` de la `datos.db` del juego (montada en `/juego`).
#  · `arranque.py` arma el `config.json` en `/tmp` a partir de las variables `PARCHES_*`.
#  ★ Biblioteca estándar pura: sirve igual para amd64 y arm64.
# ─────────────────────────────────────────────────────────────────────────────────────────────
ARG PYTHON=3.13-slim-bookworm
FROM python:${PYTHON}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

# El MISMO uid que el juego y cuentas (10013): SQLite en WAL necesita poder abrir el `-shm` al lado de `datos.db`.
RUN groupadd -g 10013 r2 && useradd -u 10013 -g 10013 -M -d /app -s /usr/sbin/nologin r2 \
 && mkdir -p /app /releases /juego && chown -R r2:r2 /releases

WORKDIR /app
COPY --chown=root:root herramientas/contenedores/parches/patchserver.py \
     herramientas/contenedores/parches/make_manifest.py \
     herramientas/contenedores/parches/arranque.py \
     herramientas/contenedores/parches/subidas.py herramientas/contenedores/parches/juez.py /app/

ENV PARCHES_HOST=0.0.0.0 \
    PARCHES_PUERTO=8080 \
    PARCHES_BASE=/juego/datos.db \
    PARCHES_STATUS=/juego/status.json \
    PARCHES_RELEASES=/releases

USER r2
VOLUME ["/releases"]
EXPOSE 8080

HEALTHCHECK --interval=30s --start-interval=2s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % (os.environ.get('PARCHES_PUERTO') or 8080), timeout=3).read()"]

CMD ["python", "arranque.py"]
