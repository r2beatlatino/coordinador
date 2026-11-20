# ─────────────────────────────────────────────────────────────────────────────────────────────
#  La PUERTA del 48004 — reparte el login de R2Beat entre el server de prod y el de prueba.
#  documentacion/TOPOLOGIA_CONTENEDORES.md §34 · el código: herramientas/contenedores/puerta/puerta_login.py
#
#      docker build -f herramientas/contenedores/puerta.Dockerfile -t enenos-puerta .
#
#  ★ Un archivo de Python puro, sin nada del juego: no ve contraseñas ni bases. Sólo lee el primer paquete
#    de cada conexión (el `aud` del pase, o el usn + permiso del exe) y la pasa entera.
# ─────────────────────────────────────────────────────────────────────────────────────────────
ARG PYTHON=3.13-slim-bookworm
FROM python:${PYTHON}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

# El MISMO uid que las otras imágenes (ver `juego.Dockerfile` en el repo del R2Beat 2013).
RUN groupadd -g 10013 r2 && useradd -u 10013 -g 10013 -M -d /app -s /usr/sbin/nologin r2 \
 && mkdir -p /app /datos && chown r2:r2 /datos

WORKDIR /app
COPY --chown=root:root herramientas/contenedores/puerta/puerta_login.py /app/puerta_login.py

ENV PUERTA_ESCUCHAR=0.0.0.0:48004 \
    PUERTA_MAPA=/datos/mapa.json

USER r2
EXPOSE 48004
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 48004), 3).close()"
CMD ["python", "/app/puerta_login.py"]
