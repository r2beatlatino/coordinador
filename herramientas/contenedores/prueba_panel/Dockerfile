# El server de PRUEBA de R2Beat CON el panel (★ 21-nov-2026): la imagen de `develop` + los módulos de PROD.
# La arma `actualizar_prueba.sh` (ver con_panel.py). `servidor/` de este contexto lo llena el script con los
# archivos sacados de la imagen de prod (JUEGO_IMAGEN): ⛔ no están en el repo y no van a GitHub.
ARG BASE
FROM ${BASE}
COPY servidor/ /r2b/servidor/
COPY con_panel.py /r2b/con_panel.py
RUN sed -i 's|^exec python correr_servidor.py$|exec python con_panel.py|' /r2b/arrancar.sh \
 && grep -q 'exec python con_panel.py' /r2b/arrancar.sh \
 && cd /r2b && python -c "import sys; sys.path.insert(0, '.'); import servidor.api_web, servidor.launcher_api, servidor.launcher_contenido, servidor.panel_admin, servidor.contenido_interno, servidor.ruleta, servidor.asistencia, servidor.clasificacion, servidor.tienda_launcher; print('panel: los módulos de prod importan sobre develop')"
