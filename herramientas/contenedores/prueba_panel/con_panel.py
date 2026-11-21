# -*- coding: utf-8 -*-
"""con_panel — el arranque del server de PRUEBA de R2Beat CON el panel (★ 21-nov-2026).

Benja: «el servidor de prueba debería tener las mismas funciones que ya tiene el Coordinador en prod, pero sin los
datos de prod». El server de prueba corre `develop` del repo PÚBLICO, que deja afuera a propósito lo de prod
(`api_web`, `panel_admin`, `launcher_*`, `ruleta`, …: decisión del 11-nov). `actualizar_prueba.sh` le copia ENCIMA esos
módulos sacados de la imagen de PROD (no van a GitHub) y arranca con esto en vez de `correr_servidor.py`:

1. prepara el entorno IGUAL que `correr_servidor.py` (su base de prueba en /r2b/datos: nada de prod);
2. prende la API (`api_web.arrancar()`: el contenido del launcher, `/api/interno/contenido` y `/api/interno/panel`
   para el Coordinador) en el 48510, el puerto que ya usaba la presencia — así ni el Coordinador ni Cuenta Eñeños
   cambian (sus variables ya apuntan a `r2beat2013-prueba:48510`). La presencia sigue ahí: `/presencia` y
   `/amistades` se atienden como `/api/interno/presencia|amistades` (con la ficha, igual que antes);
3. corre el juego de `develop` (`correr_servidor.main()`, sin tocar su `lobby.py`).

⛔ Si la API no arranca, el juego sigue igual (como en prod).
"""
import os
import sys
import threading
import time

AQUI = "/r2b"
sys.path.insert(0, AQUI)
os.chdir(AQUI)
PUERTO = os.environ.pop("R2_PRESENCIA_PUERTO", "") or "48510"   # el juego NO abre su presencia suelta: la da la API
os.environ.setdefault("R2_API_HOST", "0.0.0.0")
os.environ.setdefault("R2_API_PUERTO", PUERTO)
os.environ.setdefault("R2_API_PROXIES", "127.0.0.1,::1,172.16.0.0/12")
os.environ.setdefault("R2_RESPALDO", "0")                        # es una base de prueba: sin respaldo diario

import correr_servidor as C                                      # noqa: E402

C.preparar_entorno()


def _panel():
    time.sleep(3)                                                # que `servidor.lobby` ya esté importado (un solo módulo)
    try:
        from servidor import api_web
        orig = api_web._Manejador.do_GET

        from servidor import presencia
        sin_amistades = not hasattr(presencia, "amistades")      # el presencia.py de develop puede ser más viejo

        def do_GET(self):
            ruta, _, q = self.path.partition("?")
            if sin_amistades and ruta.rstrip("/").endswith("/amistades"):
                self.send_response(404)                          # como antes: «este server no tiene amistades»
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            if ruta.rstrip("/") in ("/presencia", "/amistades"):
                self.path = "/api/interno" + ruta.rstrip("/") + ("?" + q if q else "")
            return orig(self)

        api_web._Manejador.do_GET = do_GET
        if api_web.arrancar() is None:
            print("[PRUEBA] ⚠ la API del panel no arrancó: el juego sigue sin ella", flush=True)
    except Exception as e:                                       # noqa: BLE001
        print(f"[PRUEBA] ⚠ panel: {e!r} (el juego sigue)", flush=True)


threading.Thread(target=_panel, daemon=True, name="prueba-panel").start()
C.main()
