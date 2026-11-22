"""★ 21-nov — el `/salud` de Eñeñosbit 2027 (el R2Beat moderno) para el Coordinador.

Eñeños: «que EDA y Eñeñosbit 2027 muestren en prod y test server cuántas personas están, o si están 0». El server de
Fluidez no tiene HTTP, así que esto corre AL LADO, dentro del mismo contenedor (lo mete `moderno_imagen.sh`), y cuenta
sin tocar su código: las conexiones TCP vivas (ESTABLISHED) a SUS puertos —el login, el juego y los de cuentas—, leídas
de /proc/net/tcp del contenedor. Un jugador = una IP de afuera distinta (el healthcheck y lo local no cuentan).

    GET /salud  →  {"ok": true, "en_linea": true|false, "jugando": n}     (el formato del contrato, como EDA)

`en_linea` = el login acepta una conexión. Escucha en SALUD_PUERTO (28190) sin publicarse: sólo se alcanza por la red
de Docker de la pila (`http://r2beat-moderno:28190/salud`). ⚠ Docker se salta el ufw: NO agregarlo a `ports:`.
"""
import json
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _lista(nombre, defecto):
    return [int(p) for p in (os.environ.get(nombre) or defecto).split(",") if p.strip().isdigit()]


LOGIN = _lista("PUERTOS", "28004")
JUEGO = _lista("PUERTOS_JUEGO", "28008")
_c = int(os.environ.get("PUERTO_CUENTAS") or 28101)
PUERTOS = set(LOGIN + JUEGO + list(range(_c, _c + 9)))
SALUD_PUERTO = int(os.environ.get("SALUD_PUERTO") or 28190)


def _ip(hexa):
    """La IP de una línea de /proc/net/tcp[6] (en hex, little-endian por palabra)."""
    if len(hexa) == 8:
        return socket.inet_ntop(socket.AF_INET, bytes.fromhex(hexa)[::-1])
    b = b"".join(bytes.fromhex(hexa[i:i + 8])[::-1] for i in range(0, 32, 8))
    ip = socket.inet_ntop(socket.AF_INET6, b)
    return ip[7:] if ip.startswith("::ffff:") else ip


def conectados(puertos=None, archivos=("/proc/net/tcp", "/proc/net/tcp6")):
    """Las IPs de afuera con una conexión viva a nuestros puertos."""
    puertos = PUERTOS if puertos is None else puertos
    ips = set()
    for a in archivos:
        try:
            lineas = open(a, encoding="ascii").read().splitlines()[1:]
        except OSError:
            continue
        for l in lineas:
            c = l.split()
            if len(c) < 4 or c[3] != "01":                         # 01 = ESTABLISHED
                continue
            loc, rem = c[1].split(":"), c[2].split(":")
            if int(loc[1], 16) not in puertos:
                continue
            ip = _ip(rem[0])
            if ip.startswith("127.") or ip == "::1":
                continue
            ips.add(ip)
    return ips


def en_linea():
    try:
        socket.create_connection(("127.0.0.1", LOGIN[0]), 2).close()
        return True
    except OSError:
        return False


class Salud(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] != "/salud":
            self.send_error(404)
            return
        cuerpo = json.dumps({"ok": True, "en_linea": en_linea(), "jugando": len(conectados())}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):                                     # sin una línea por pedido (lo pide cada 15 s)
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", SALUD_PUERTO), Salud).serve_forever()
