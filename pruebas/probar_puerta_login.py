# -*- coding: utf-8 -*-
"""probar_puerta_login — el repartidor del 48004 (dos servers de R2Beat en una máquina). 15-nov-2026.

Dos servers de mentira (PROD y PRUEBA) que contestan el login COMO el de verdad (`lobby.resp_login_launcher`, el
generador, no un esperado escrito a mano) y dicen quiénes son. La puerta corre de verdad, en un hilo.

    python -X utf8 pruebas/probar_puerta_login.py

★ En el coordinador (19-nov): los paquetes se arman con el GENERADOR del juego (`servidor/cifrado.py`, `servidor/lobby.py`,
  `servidor/ajustes.py`), que vive en el repo del R2Beat 2013. Se le dice dónde con `R2BEAT2013_REPO=<copia de ese repo>`.
  Sin esa variable la prueba se SALTA (sale con 77, que `correr_todas.py` cuenta como saltada, no como verde).
"""
import asyncio
import base64
import importlib.util
import json
import os
import re
import socket
import struct
import sys
import tempfile
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JUEGO = os.environ.get("R2BEAT2013_REPO") or ""
if not os.path.isfile(os.path.join(JUEGO, "servidor", "lobby.py")):
    print("⏭ probar_puerta_login: SALTADA — falta R2BEAT2013_REPO (una copia del repo del R2Beat 2013: de ahí salen "
          "los paquetes de verdad)")
    sys.exit(77)
sys.path.insert(0, JUEGO)                       # el `servidor/` del JUEGO (no el de acá, que es el de las cuentas)
from servidor.cifrado import frame, parse_frames                           # noqa: E402
from servidor.lobby import armar_login_pase, resp_login_launcher           # noqa: E402

_tmp = tempfile.mkdtemp(prefix="r2_puerta_")
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que, flush=True)
    if not cond:
        fallos.append(que)


def libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def pase_falso(aud, sub="10000001"):
    """Un JWT con la forma de verdad (la firma no la mira la puerta: la mira el server de destino)."""
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return "%s.%s.%s" % (b({"alg": "EdDSA", "typ": "JWT"}), b({"iss": "r2beat-portero", "aud": aud, "sub": sub,
                                                                 "exp": int(time.time()) + 300, "jti": "x"}),
                         "A" * 86)


def sesion_en(cmd, usn, vcode):
    """La respuesta que ABRE una sesión, «como el FF01» (`cuenta_personajes._sesion_para`): el cuerpo del generador."""
    return frame(cmd, resp_login_launcher(usn, vcode)[4:])


class Falso:
    """Un server de login de mentira: al pase le contesta como el de verdad; al ELEGIR del selector (FFF8) abre la
    sesión de OTRO personaje; a lo demás, un paquete con su nombre."""

    def __init__(self, nombre, usn, vcode):
        self.nombre, self.usn, self.vcode, self.vistos, self.proxys = nombre, usn, vcode, [], []
        self.elegido = (usn + 100, vcode ^ 0x5555)
        self.puerto = libre()
        self.s = socket.socket()
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(("127.0.0.1", self.puerto))
        self.s.listen(20)
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self):
        while True:
            c, _ = self.s.accept()
            threading.Thread(target=self._uno, args=(c,), daemon=True).start()

    def _uno(self, c):
        c.settimeout(1.5)
        buf = b""
        try:
            while True:
                try:
                    d = c.recv(65536)
                except socket.timeout:
                    break
                if not d:
                    break
                buf += d
                self.vistos.append(d)
                if buf.startswith(b"PROXY ") and b"\r\n" in buf:     # ★ 26-nov: la línea de la puerta (como el 2013)
                    linea, _, buf = buf.partition(b"\r\n")
                    self.proxys.append(linea)
                fs, buf = parse_frames(buf)
                for _m, cmd, pl in fs:
                    if cmd == 0x01 and len(pl) > 12 and pl[4] == 0x50:
                        c.sendall(resp_login_launcher(self.usn, self.vcode))
                    elif cmd == 0xF8:
                        c.sendall(sesion_en(0xF8, *self.elegido))
                    else:
                        c.sendall(frame(0xEE, ("SOY " + self.nombre).encode()))
                if not fs and len(buf) >= 3 and buf[:1] != b"\xff":
                    c.sendall(frame(0xEE, ("SOY " + self.nombre).encode()))
                    break
        finally:
            c.close()


def hablar(puerto, datos, trozos=1):
    s = socket.create_connection(("127.0.0.1", puerto), timeout=5)
    paso = max(1, len(datos) // trozos)
    for i in range(0, len(datos), paso):
        s.sendall(datos[i:i + paso])
        time.sleep(0.05)
    r = b""
    try:
        while True:
            x = s.recv(4096)
            if not x:
                break
            r += x
    except socket.timeout:
        pass
    s.close()
    return r


def arrancar_puerta(env):
    for k, v in env.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location(
        "puerta_%d" % len(env) + str(time.time_ns()), os.path.join(RAIZ, "herramientas", "contenedores", "puerta", "puerta_login.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    hilo = threading.Thread(target=lambda: asyncio.run(m.main()), daemon=True)
    hilo.start()
    _, p = env["PUERTA_ESCUCHAR"].rsplit(":", 1)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", int(p)), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    return m


def main():
    # Los DOS dan el MISMO usn (cada server tiene su base: los usn chocan). Sólo el vcode los distingue.
    prod = Falso("PROD", 7, 0x1111222233334444)
    prueba = Falso("PRUEBA", 7, 0x0ABCDEF012345678)
    mapa = os.path.join(_tmp, "mapa.json")
    pp = libre()
    env = {"PUERTA_ESCUCHAR": "127.0.0.1:%d" % pp, "PUERTA_PROD": "127.0.0.1:%d" % prod.puerto,
           "PUERTA_PRUEBA": "127.0.0.1:%d" % prueba.puerto, "PUERTA_MAPA": mapa, "PUERTA_ESPERA_S": "1"}
    m1 = arrancar_puerta(env)
    from servidor.ajustes import SESION_PASO, SESION_PASOS_MAX
    ok((m1.PASO, m1.PASOS_MAX) == (SESION_PASO, SESION_PASOS_MAX),
       "la puerta acepta los re-logins con la MISMA regla que el server (+%d, hasta %d veces)" % (SESION_PASO, SESION_PASOS_MAX))
    exe = lambda usn, vc: frame(0x01, struct.pack("<IQ", usn, vc))

    print("1 · el launcher, con pase")
    r = hablar(pp, armar_login_pase(pase_falso("r2beat2013")))
    ok(r == resp_login_launcher(7, prod.vcode), "un pase de prod (aud=r2beat2013) va a PROD y vuelve su respuesta intacta")
    enviado = armar_login_pase(pase_falso("r2beat2013-prueba"))
    r = hablar(pp, enviado, trozos=5)
    ok(r == resp_login_launcher(7, prueba.vcode), "un pase de prueba va a PRUEBA (aunque llegue en 5 pedazos)")
    ok(prueba.vistos and prueba.vistos[-1] == enviado, "y el server de prueba recibe el paquete entero, sin cambios")

    print("2 · el exe (12 bytes: usn + vcode)")
    ok(hablar(pp, exe(7, prueba.vcode)) .endswith(b"SOY PRUEBA"), "con el vcode que dio PRUEBA, el exe va a PRUEBA")
    ok(hablar(pp, exe(7, prod.vcode)) .endswith(b"SOY PROD"), "⟲ revés: el MISMO usn con el vcode de prod va a PROD")
    ok(hablar(pp, exe(8, prueba.vcode)) .endswith(b"SOY PROD"), "⟲ revés: otro usn con ese vcode va a PROD (la clave es el par)")
    ok(hablar(pp, exe(7, prueba.vcode), trozos=3).endswith(b"SOY PRUEBA"), "volver a entrar con el mismo permiso sigue yendo a PRUEBA")
    # ★ 16-nov: el exe le SUMA 10 al permiso en cada re-login (lo mismo que acepta `basedatos._mismo_vcode`)
    ok(hablar(pp, exe(7, prueba.vcode + SESION_PASO)).endswith(b"SOY PRUEBA"), "★ cambiar de canal: el exe manda el permiso +10 y va a PRUEBA")
    ok(hablar(pp, exe(7, prueba.vcode + 3 * SESION_PASO)).endswith(b"SOY PRUEBA"), "…y +30 (el tercer cambio de canal) también")
    ok(hablar(pp, exe(7, prueba.vcode + 5)).endswith(b"SOY PROD"), "⟲ revés: +5 no es un re-login: va a PROD")
    ok(hablar(pp, exe(7, prueba.vcode + SESION_PASO * (SESION_PASOS_MAX + 1))).endswith(b"SOY PROD"), "⟲ revés: más de 64 re-logins tampoco (como el server)")

    print("2b · ★ el SELECTOR de la dll (16-nov: el FFF6 caía en prod y no salía el selector)")
    hola = lambda usn, vc: frame(0xF6, struct.pack("<IQ", usn, vc))
    elegir = lambda usn, vc, r: frame(0xF8, struct.pack("<IQ", usn, vc) + bytes([r, 0]))
    ok(hablar(pp, hola(7, prueba.vcode)).endswith(b"SOY PRUEBA"), "el HOLA (FFF6) con la sesión de prueba va a PRUEBA")
    ok(hablar(pp, hola(7, prod.vcode)).endswith(b"SOY PROD"), "⟲ revés: el HOLA con la sesión de prod va a PROD")
    r = hablar(pp, hola(7, prueba.vcode) + elegir(7, prueba.vcode, 2))
    ok(sesion_en(0xF8, *prueba.elegido) in r, "en la MISMA conexión, ELEGIR (FFF8) le abre al juego otra sesión (otro personaje)")
    ok(hablar(pp, exe(*prueba.elegido)).endswith(b"SOY PRUEBA"),
       "★ y el juego vuelve a entrar con esa sesión NUEVA… a PRUEBA (la puerta la anotó al pasar)")
    hablar(pp, hola(7, prod.vcode) + elegir(7, prod.vcode, 2))
    ok(hablar(pp, exe(*prod.elegido)).endswith(b"SOY PROD"), "⟲ revés: la sesión nueva que da PROD sigue en PROD")

    print("3 · lo demás es prod")
    ok(hablar(pp, frame(0xEC, b"eco")) .endswith(b"SOY PROD"), "otro paquete (el eco del nombre público) va a PROD")
    ok(hablar(pp, frame(0xF9, b"\x00\x00" + pase_falso("r2beat2013-prueba").encode())) .endswith(b"SOY PRUEBA"),
       "el pedido de personajes con un pase de prueba delante va a PRUEBA")
    ok(hablar(pp, b"\x01\x02\x03") .endswith(b"SOY PROD"), "basura que no es un paquete del juego va a PROD (al rato)")

    print("4 · lo anotado sobrevive a reiniciar la puerta")
    ok(os.path.isfile(mapa) and any(int(v) == prueba.vcode for _u, v, _d, _ve in json.load(open(mapa))),
       "el mapa se guardó en PUERTA_MAPA")
    pp2 = libre()
    arrancar_puerta(dict(env, PUERTA_ESCUCHAR="127.0.0.1:%d" % pp2))
    ok(hablar(pp2, exe(7, prueba.vcode)) .endswith(b"SOY PRUEBA"), "una puerta NUEVA con el mismo archivo lo manda a PRUEBA")
    pp3 = libre()
    os.environ.pop("PUERTA_MAPA")
    m3 = arrancar_puerta(dict((k, v) for k, v in env.items() if k != "PUERTA_MAPA") | {"PUERTA_ESCUCHAR": "127.0.0.1:%d" % pp3})
    m3._mapa.clear()
    ok(hablar(pp3, exe(7, prueba.vcode)) .endswith(b"SOY PROD"), "⟲ revés: sin el archivo (y sin memoria) cae en PROD")

    print("5 · un server que no contesta")
    pp4 = libre()
    arrancar_puerta({"PUERTA_ESCUCHAR": "127.0.0.1:%d" % pp4, "PUERTA_PROD": "127.0.0.1:%d" % prod.puerto,
                     "PUERTA_PRUEBA": "127.0.0.1:%d" % libre(), "PUERTA_MAPA": os.path.join(_tmp, "m4.json")})
    ok(hablar(pp4, armar_login_pase(pase_falso("r2beat2013-prueba"))) == b"", "prueba apagado: se corta (no cae en prod)")
    ok(hablar(pp4, armar_login_pase(pase_falso("r2beat2013"))) == resp_login_launcher(7, prod.vcode),
       "…y prod sigue andando igual")

    print("6 · ★ la IP del jugador (PROXY protocol), sólo a los destinos de PUERTA_PROXY_A")
    pp5 = libre()
    prod.proxys.clear()
    prueba.proxys.clear()
    arrancar_puerta(dict(env, PUERTA_ESCUCHAR="127.0.0.1:%d" % pp5, PUERTA_PROXY_A="prueba"))
    os.environ.pop("PUERTA_PROXY_A")
    r = hablar(pp5, armar_login_pase(pase_falso("r2beat2013-prueba")), trozos=3)
    ok(r == resp_login_launcher(7, prueba.vcode), "con la línea delante, el login de PRUEBA contesta igual")
    ok(len(prueba.proxys) == 1 and re.fullmatch(rb"PROXY TCP4 127\.0\.0\.1 127\.0\.0\.1 [0-9]+ %d" % pp5, prueba.proxys[0]),
       "PRUEBA recibe la línea PROXY con la IP y el puerto del jugador (%r)" % (prueba.proxys[:1],))
    r = hablar(pp5, armar_login_pase(pase_falso("r2beat2013")))
    ok(r == resp_login_launcher(7, prod.vcode) and not prod.proxys, "⟲ revés: PROD (no está en PUERTA_PROXY_A) no recibe ninguna línea")
    hablar(pp, armar_login_pase(pase_falso("r2beat2013-prueba")))
    ok(len(prueba.proxys) == 1, "⟲ revés: una puerta sin PUERTA_PROXY_A no la manda")
    ok(m1.linea_proxy(("::ffff:10.1.2.3", 5), ("::ffff:172.18.0.5", 48004)) == b"PROXY TCP4 10.1.2.3 172.18.0.5 5 48004\r\n",
       "una IPv4 escrita como IPv6 sale como TCP4")
    ok(m1.linea_proxy(("?", 0), ("1.2.3.4", 1)) == b"", "⟲ revés: si no se sabe la IP, no se manda línea (el server sigue con la que ve)")

    print("\n%s" % ("✔ probar_puerta_login: todo bien" if not fallos else "✘ %d fallo(s): %s" % (len(fallos), fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
