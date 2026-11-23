#!/usr/bin/env bash
# actualizar_moderno_prueba.sh — ATAJO: desde el 23-nov todo vive en actualizar_moderno.sh (prueba y prod), según la
#   plantilla de EDA prod (eda_ensayo.sh) y del de prueba del 2013 (actualizar_prueba.sh). Lo mismo que
#   `actualizar_moderno.sh prueba`. El cron está en /etc/cron.d/enenos-moderno.
exec bash "$(dirname "$0")/actualizar_moderno.sh" prueba "$@"
