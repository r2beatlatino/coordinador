# -*- coding: utf-8 -*-
"""probar_portero_colgado — el que pregunta y cuelga no deja tracebacks. 22-nov-2026.

En prod Cuenta Eñeños juntaba ~700 `BrokenPipeError` por día: el launcher se cierra en medio de la espera larga del chat
(`social/esperar`), `_mandar` reventaba al escribir y el `except` de do_POST probaba un 500 al mismo socket muerto.

  · un socket que se rompe al escribir (BrokenPipe / ConnectionReset / ConnectionAborted) -> `_mandar` NO revienta
    y marca la conexión para cerrar;
  ⟲ CONTROL: cualquier OTRO error al escribir SÍ sube (no tapamos bugs de verdad);
  ⟲ CONTROL: con un socket sano la respuesta sale entera (código, Content-Length y el cuerpo).
"""
import io
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from servidor import portero  # noqa: E402

fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


class _Roto(io.RawIOBase):
    def __init__(self, error):
        self.error = error

    def writable(self):
        return True

    def write(self, b):
        raise self.error


def manejador(wfile):
    h = portero._Manejador.__new__(portero._Manejador)      # sin socket de verdad: sólo lo que usa `_mandar`
    h.wfile, h.request_version, h.command, h.requestline = wfile, "HTTP/1.1", "POST", "POST /social/esperar HTTP/1.1"
    h.close_connection = False
    return h


print("probar_portero_colgado")
for err in (BrokenPipeError(32, "Broken pipe"), ConnectionResetError(104, "reset"), ConnectionAbortedError(103, "abort")):
    h = manejador(_Roto(err))
    try:
        h._mandar(200, {"ok": True})
        ok(h.close_connection, "%s: no revienta y cierra la conexión" % type(err).__name__)
    except Exception as e:                                     # noqa: BLE001
        ok(False, "%s: reventó igual (%r)" % (type(err).__name__, e))

h = manejador(_Roto(ValueError("otro error")))
try:
    h._mandar(200, {"ok": True})
    ok(False, "CONTROL: un error que NO es de socket colgado tiene que subir (se lo tragó)")
except ValueError:
    ok(True, "CONTROL: un error que NO es de socket colgado sube")

buf = io.BytesIO()
h = manejador(buf)
h._mandar(200, {"ok": True})
sal = buf.getvalue()
ok(sal.split(b"\r\n")[0].endswith(b" 200 OK") and sal.endswith(b'{"ok": true}') and b"Content-Length: 12" in sal and not h.close_connection,
   "CONTROL: con el socket sano la respuesta sale entera")

print("FALLOS: %d" % len(fallos) if fallos else "TODO BIEN")
sys.exit(1 if fallos else 0)
