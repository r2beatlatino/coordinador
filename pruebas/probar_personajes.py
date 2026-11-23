# -*- coding: utf-8 -*-
"""Personajes del launcher: rutas y sesiones reales, transporte interno inyectado, sin red."""
import contextlib
import copy
import io
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
cuenta = 0
fallos = []


def ok(cond, texto):
    global cuenta
    cuenta += 1
    print(("  ✔ " if cond else "  ✘ ") + texto)
    if not cond:
        fallos.append(texto)


with tempfile.TemporaryDirectory(prefix="personajes_") as tmp:
    os.environ.update({
        "R2_CUENTAS_DUENA": "1", "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
        "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"), "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
        "R2_BASE": os.path.join(tmp, "ausente.db"), "R2_ADMIN_ARCHIVO": os.path.join(tmp, "admin.txt"),
        "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "moderadores.txt"),
        "R2_PANEL_GESTION": "r2beat-moderno=contrato1:http://juego-live/interno/panel;"
                            "r2beat-moderno-prueba=contrato1:http://juego-test/interno/panel",
    })
    from servidor import portero as P
    from servidor import gestion as GE

    class Pedido(P._Manejador):
        def __init__(self, path, token=None, cookie=None):
            self.path = path
            self.headers = {}
            if token:
                self.headers["Authorization"] = "Bearer " + token
            if cookie:
                self.headers["Cookie"] = "coordinador=" + cookie

        def _mandar(self, cod, datos, **kwargs):
            self.respuesta = cod, copy.deepcopy(datos)
            return self.respuesta

    def pedir(path="/juego/r2beat-moderno/personajes", token=None, cookie=None):
        h = Pedido(path, token, cookie)
        h.do_GET()
        return h.respuesta

    personaje = {"id": 17, "nick": "Jugador", "sexo": "m", "nivel": 0, "conectado": True}
    datos = {"personajes": [dict(personaje, correo="privado", enenos_id=-1, inventario=["interno"])],
             "maximo": 4, "detalle": "interno"}
    fallo = (502, {"error": "no pudimos traer tus personajes"})
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            uid = P.registrar("jugadorprueba", clave_txt="clave-de-prueba", ip="127.0.0.1")[1]["uid"]
            otro = P.registrar("otroprueba", clave_txt="clave-de-prueba", ip="127.0.0.2")[1]["uid"]
        token, token_otro = P.abrir_sesion(uid), P.abrir_sesion(otro)
        cookie = P.abrir_sesion_admin(uid)
        vencida = P.abrir_sesion(uid, ahora=time.time() - (P.SESION_DIAS + 1) * 86400)
        with patch.object(GE, "_http", return_value=(200, datos)) as http:
            for tok in (None, "invalida", vencida):
                ok(pedir(token=tok)[0] == 401, "⟲ sesión ausente, inválida o vencida: 401")
            ok(pedir(cookie=cookie)[0] == 401 and not http.called, "⟲ cookie del panel no reemplaza la sesión del launcher")
            for prefijo in ("", "/cuentas"):
                cod, d = pedir(prefijo + "/juego/r2beat-moderno/personajes?entorno=live&enenos_id=" + str(otro), token)
                ok((cod, d) == (200, {"ok": True, "personajes": [personaje], "maximo": 4}),
                   "live con/sin /cuentas: sólo los campos públicos validados")
                ok(http.call_args.args == ("http://juego-live/interno/panel", "personajes", {"enenos_id": uid},
                                           None, f"launcher:{uid}", False),
                   "envía sólo SU UID de sesión, ignora enenos_id del cliente y no usa admin")
            pedir(token=token_otro)
            ok(http.call_args.args[2] == {"enenos_id": otro}, "⟲ otra sesión consulta el UID de esa otra cuenta")
            pedir("/cuentas/juego/r2beat-moderno/personajes?entorno=test", token)
            ok(http.call_args.args[0] == "http://juego-test/interno/panel", "test consulta el pase r2beat-moderno-prueba")
            http.reset_mock()
            ok(pedir("/juego/eda/personajes", token) ==
               (404, {"error": "este juego no tiene personajes en el launcher"}) and not http.called,
               "⟲ otro juego: 404 sin consulta interna")
            for entorno in ("otro", "", "TEST"):
                ok(pedir("/juego/r2beat-moderno/personajes?entorno=" + entorno, token)[0] == 400
                   and not http.called, "⟲ entorno inválido: 400 sin consulta interna")
            for fuentes in ("", "r2beat-moderno=http://panel-viejo", "r2beat-moderno-prueba=contrato1:http://solo-test"):
                with patch.dict(os.environ, {"R2_PANEL_GESTION": fuentes}):
                    ok(pedir(token=token) ==
                       (503, {"error": "el servidor de ese juego todavía no publica sus personajes"}) and not http.called,
                       "⟲ sin fuente contrato1 de live: 503, no usa otro pase")
            with patch.dict(os.environ, {"R2_PANEL_GESTION": "r2beat-moderno=contrato1:http://solo-live"}):
                ok(pedir("/juego/r2beat-moderno/personajes?entorno=test", token)[0] == 503 and not http.called,
                   "⟲ test sin fuente propia no consulta live")
            for codigo in (400, 401, 500, 503):
                http.return_value = codigo, {"error": "detalle privado del servidor"}
                ok(pedir(token=token) == fallo, "⟲ error del servidor: 502 sin detalle interno")
            for error in (OSError("detalle privado"), TimeoutError("detalle privado"), ValueError("JSON roto")):
                http.side_effect = error
                ok(pedir(token=token) == fallo, "⟲ caída, timeout o JSON roto: 502 sin detalle interno")
            http.side_effect = None

            def respuesta(d):
                http.return_value = 200, d
                return pedir(token=token)

            for d in (None, [], {}, {"personajes": [], "maximo": True}, {"personajes": [], "maximo": -1},
                      {"personajes": [], "maximo": 9}, {"personajes": [], "maximo": "4"},
                      {"personajes": {}, "maximo": 4}, {"personajes": [personaje] * 5, "maximo": 4}):
                ok(respuesta(d) == fallo, "⟲ respuesta o máximo inválido: 502 cerrado")
            for campo, valor in (("id", True), ("id", "17"), ("id", 1.5), ("nick", 17), ("nick", "x" * 25),
                                 ("sexo", "M"), ("sexo", []), ("nivel", True), ("nivel", -1), ("nivel", "2"),
                                 ("nivel", 1.5), ("conectado", 1), ("conectado", None)):
                p = dict(personaje, **{campo: valor})
                ok(respuesta({"personajes": [p], "maximo": 4}) == fallo, f"⟲ tipo/valor inválido en {campo}: 502")
            for campo in personaje:
                p = dict(personaje)
                del p[campo]
                ok(respuesta({"personajes": [p], "maximo": 4}) == fallo, f"⟲ falta {campo}: 502")
            ok(respuesta({"personajes": [None], "maximo": 4}) == fallo, "⟲ personaje no es objeto: 502")
            p = dict(personaje, nick="x" * 24, sexo=None, nivel=None, conectado=False)
            ok(respuesta({"personajes": [p] * 8, "maximo": 8}) ==
               (200, {"ok": True, "personajes": [p] * 8, "maximo": 8}),
               "máximos exactos, nick 24, sexo/nivel nulos y desconectado: 200")
            ok(respuesta({"personajes": [dict(personaje, sexo="f")], "maximo": 1})[0] == 200,
               "sexo f también se acepta")
            ok(respuesta({"personajes": [], "maximo": 0}) == (200, {"ok": True, "personajes": [], "maximo": 0}),
               "sin personajes: lista vacía válida")
            # ★ 23-nov: la apariencia (el muñeco del launcher) pasa limpia; si no cierra, null — nunca tira el 502
            ap = {"cuerpo": 130900, "sexo": "m", "partes": [{"id": 310565, "pestana": 302}], "mascota": None, "alas": None}
            r = respuesta({"personajes": [dict(personaje, apariencia=dict(ap, secreto="x"))], "maximo": 4})
            ok(r[0] == 200 and r[1]["personajes"][0]["apariencia"] == ap, "apariencia válida pasa, sin campos de más")
            r = respuesta({"personajes": [dict(personaje, apariencia=dict(ap, partes=[{"id": 1, "pestana": 2, "x": 3}]))],
                           "maximo": 4})
            ok(r[0] == 200 and r[1]["personajes"][0]["apariencia"]["partes"] == [{"id": 1, "pestana": 2}],
               "⟲ una parte con campos de más llega sólo con id y pestana")
            for malo in (None, "x", dict(ap, cuerpo="130900"), dict(ap, sexo="M"), dict(ap, partes={}),
                         dict(ap, partes=[{"id": -1, "pestana": 302}]), dict(ap, partes=[{"id": 1}] * 33),
                         dict(ap, mascota="perro"), dict(ap, alas=True)):
                r = respuesta({"personajes": [dict(personaje, apariencia=malo)], "maximo": 4})
                ok(r[0] == 200 and r[1]["personajes"][0]["apariencia"] is None,
                   f"⟲ apariencia inválida ({str(malo)[:30]}…): null, el resto llega")
            r = respuesta({"personajes": [personaje], "maximo": 4})
            ok("apariencia" not in r[1]["personajes"][0], "⟲ sin apariencia en el server: la clave no aparece")
    finally:
        P.cerrar_conexiones()

print(f"\n{'✘' if fallos else '✔'} probar_personajes: {cuenta} controles, {len(fallos)} fallas")
sys.exit(1 if fallos else 0)
