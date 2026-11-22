# -*- coding: utf-8 -*-
"""puerta_login — el REPARTIDOR del puerto 48004: dos servers de R2Beat 2013 en la misma máquina (15-nov-2026).

Por qué existe: Eñeños quiere dos servers por juego (prod y prueba, TOPOLOGIA_CONTENEDORES §32). Los CANALES se
pueden mover de puerto (el cliente los aprende del FF02 que arma el server: `R2_PUERTOS=1000` → 49005…), pero el
LOGIN no: el exe entra SIEMPRE por el 48004 (el puerto que le pasa el launcher no lo usa). Para no tocar el exe, el
48004 lo atiende esta puerta, que lee el PRIMER paquete de cada conexión y la pasa entera a uno de los dos:

  · un paquete con un pase (el launcher: `FF01` con 0x50, o el pedido de personajes con el pase delante): se mira el
    `aud` del pase SIN comprobar la firma (eso lo hace el server de destino). Si termina en `-prueba` → prueba.
    Y cuando prueba le contesta el login `[0][usn:u32][0000][len][vcode hex]`, se anota (usn, vcode) → prueba;
  · el `FF01` del EXE (12 bytes `[usn:u32][vcode:u64]`) y las órdenes del SELECTOR de la dll (`FFF6`…`FFFB`, que
    llevan esa misma sesión adelante): van adonde se anotó ese (usn, vcode). El vcode es al azar de 62 bits, así que
    dos servers con el mismo usn no se confunden;
  · y TODA sesión que da el server de prueba se anota, no sólo la del login: al ELEGIR un personaje (`FFF8`), al
    VOLVER al selector (`FFFA`) o al elegir desde el launcher (`FFF3`), el server abre otra y el juego vuelve a
    entrar con ella (16-nov: sin esto el `FFF6` de la dll caía en prod y no salía el selector);
  · cualquier otra cosa (o lo que no se reconozca) → PROD. Prod es lo de siempre: sin la puerta, todo es prod.

⚠ Lo anotado vive en memoria y en `PUERTA_MAPA` (si está): si la puerta se reinicia sin ese archivo, alguien en el
  server de prueba que cambia de canal cae en prod y le dice «Imposible conectarse» (vuelve a entrar y listo).
⚠ El server ve la IP de la puerta en el LOGIN (sólo la usa para el log). Los canales van directo: ahí ve la de verdad.

    PUERTA_ESCUCHAR=0.0.0.0:48004 PUERTA_PROD=r2beat2013:47004 PUERTA_PRUEBA=r2beat2013-prueba:49004 python puerta_login.py
"""
import asyncio
import base64
import json
import os
import re
import struct
import sys
import time

SUFIJO = os.environ.get("PUERTA_SUFIJO") or "-prueba"
RECORDAR_S = float(os.environ.get("PUERTA_RECORDAR_HORAS") or 24) * 3600
ESPERA_PRIMERO_S = float(os.environ.get("PUERTA_ESPERA_S") or 20)   # el primer paquete; lo que haya va a prod
TOPE_PRIMERO = 16384             # un pase mide ~300 B: más que esto no es un primer paquete nuestro
JWT = re.compile(rb"eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{8,}")

_mapa = {}                        # (usn, vcode) -> (destino, vence)
_ruta_mapa = os.environ.get("PUERTA_MAPA") or ""


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S") + " [PUERTA] " + msg, flush=True)


def _hostport(txt, defecto):
    h, _, p = (txt or defecto).rpartition(":")
    return h, int(p)


def primer_frame(buf):
    """(magic, cmd, payload, largo_total) del primer frame de `buf`, o None si todavía no está entero."""
    if len(buf) < 4:
        return None
    ln = buf[2] | (buf[3] << 8)
    if len(buf) < 4 + ln:
        return None
    return buf[0], buf[1], buf[4:4 + ln], 4 + ln


def aud_del_pase(payload):
    """El `aud` del primer JWT que aparezca en el paquete (sin comprobar la firma), o None."""
    m = JWT.search(payload)
    if not m:
        return None
    try:
        b = m.group(0).split(b".")[1]
        carga = json.loads(base64.urlsafe_b64decode(b + b"=" * (-len(b) % 4)))
        aud = carga.get("aud") if isinstance(carga, dict) else None
        return aud if isinstance(aud, str) else None
    except (ValueError, TypeError):
        return None


# ★ 16-nov (Eñeños: «al cambiar de canal se quedó en "nos estamos conectando"»): el EXE le SUMA 10 al permiso cada vez
#   que vuelve a entrar (cambiar de canal). El server lo acepta (`basedatos._mismo_vcode`: SESION_PASO=10, hasta 64
#   veces); la puerta tiene que reconocerlo igual o lo manda a prod, que lo rechaza.
PASO = int(os.environ.get("PUERTA_PASO") or 10)
PASOS_MAX = int(os.environ.get("PUERTA_PASOS_MAX") or 64)
CON_SESION = (0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB)        # las órdenes del selector de la dll: [usn][vcode] adelante
DAN_SESION = (0x01, 0xF3, 0xF8, 0xFA)                    # respuestas [0][usn:u32][0000][len][vcode hex]


def login_del_exe(magic, cmd, payload):
    """(usn, vcode) si el paquete viene con una SESIÓN adelante: el `FF01` del exe (12 bytes justos) o una orden del
    selector de la dll (`FFF6`…`FFFB`). None si no."""
    if magic == 0xFF and ((cmd == 0x01 and len(payload) == 12) or (cmd in CON_SESION and len(payload) >= 12)):
        return struct.unpack_from("<IQ", payload)
    return None


def frames(buf):
    """-> ([(magic, cmd, payload)...], resto) de todos los frames enteros de `buf`."""
    out = []
    while True:
        f = primer_frame(buf)
        if not f:
            return out, buf
        out.append(f[:3])
        buf = buf[f[3]:]


def sesion_dada(magic, cmd, p):
    """(usn, vcode) si este paquete del server ABRE una sesión (login, elegir, volver), o None."""
    if magic != 0xFF or cmd not in DAN_SESION or len(p) < 10 or p[0] != 0:
        return None
    usn = struct.unpack_from("<I", p, 1)[0]
    ln = p[9]
    try:
        return (usn, int(p[10:10 + ln].decode("ascii"), 16)) if ln else None
    except (ValueError, UnicodeDecodeError):
        return None


def login_contestado(buf):
    """(usn, vcode) del primer paquete de `buf` si abre una sesión (para las pruebas), o None."""
    f = primer_frame(buf)
    return sesion_dada(*f[:3]) if f else None


def _guardar_mapa():
    if not _ruta_mapa:
        return
    try:
        ahora = time.time()
        datos = [[u, v, d, ve] for (u, v), (d, ve) in _mapa.items() if ve > ahora]
        tmp = _ruta_mapa + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f)
        os.replace(tmp, _ruta_mapa)
    except OSError as e:
        log(f"⚠ no se pudo guardar {_ruta_mapa}: {e}")


def cargar_mapa():
    if not _ruta_mapa or not os.path.isfile(_ruta_mapa):
        return 0
    try:
        ahora = time.time()
        for u, v, d, ve in json.load(open(_ruta_mapa, encoding="utf-8")):
            if ve > ahora:
                _mapa[(int(u), int(v))] = (str(d), float(ve))
    except (OSError, ValueError, TypeError) as e:
        log(f"⚠ no se pudo leer {_ruta_mapa}: {e}")
    return len(_mapa)


def anotar(usn, vcode, destino):
    _mapa[(usn, vcode)] = (destino, time.time() + RECORDAR_S)
    if len(_mapa) > 50_000:                                   # tope: se van los que vencen antes
        for k in sorted(_mapa, key=lambda k: _mapa[k][1])[:10_000]:
            _mapa.pop(k, None)
    _guardar_mapa()


def buscar(usn, vcode):
    """La sesión anotada que corresponde a (usn, vcode): la exacta, o la que con +PASO unas cuantas veces da ésta
    (como el server). -> ((usn, vcode_anotado), (destino, vence)) o (None, None)."""
    for n in range(PASOS_MAX + 1):
        k = (usn, vcode - n * PASO)
        if k in _mapa:
            return k, _mapa[k]
    return None, None


def elegir(buf):
    """-> (destino 'prod'|'prueba', motivo, anotar_respuesta)."""
    f = primer_frame(buf)
    if not f:
        return "prod", "no es un paquete del juego", False
    magic, cmd, payload, _n = f
    aud = aud_del_pase(payload)
    if aud is not None:
        return ("prueba" if aud.endswith(SUFIJO) else "prod"), f"pase aud={aud}", aud.endswith(SUFIJO)
    exe = login_del_exe(magic, cmd, payload)
    if exe:
        quien = f"{'exe' if cmd == 0x01 else 'selector FF%02X' % cmd} usn={exe[0]}"
        clave, d = buscar(*exe)
        if d and d[1] > time.time():
            anotar(clave[0], clave[1], d[0])                  # se renueva: sigue jugando
            return d[0], quien + (" (anotado)" if clave == exe else " (anotado, +%d)" % (exe[1] - clave[1])), d[0] != "prod"
        return "prod", quien, False
    return "prod", f"paquete FF{cmd:02X}", False


async def _caño(lector, escritor, al_dar_sesion=None):
    """Pasa todo de `lector` a `escritor`. Con `al_dar_sesion`, mira CADA paquete que pasa y avisa de las sesiones."""
    pendiente = b""
    try:
        while True:
            datos = await lector.read(65536)
            if not datos:
                break
            if al_dar_sesion is not None:
                lista, pendiente = frames(pendiente + datos)
                for f in lista:
                    r = sesion_dada(*f)
                    if r:
                        al_dar_sesion(*r)
                if len(pendiente) > 1 << 20:                 # algo que no es del juego: se deja de mirar
                    al_dar_sesion, pendiente = None, b""
            escritor.write(datos)
            await escritor.drain()
    except (ConnectionError, OSError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            escritor.close()
        except Exception:                                     # noqa: BLE001
            pass


async def atender(lector, escritor, destinos):
    quien = escritor.get_extra_info("peername") or ("?", 0)
    buf = b""
    try:
        while not primer_frame(buf) and len(buf) < TOPE_PRIMERO:
            datos = await asyncio.wait_for(lector.read(4096), timeout=ESPERA_PRIMERO_S)
            if not datos:
                break
            buf += datos
    except asyncio.TimeoutError:
        pass
    if not buf:
        escritor.close()
        return
    destino, motivo, anotar_resp = elegir(buf)
    anotar_resp = anotar_resp or destino != "prod"            # todo lo de prueba se mira (las sesiones nuevas)
    host, puerto = destinos[destino]
    try:
        l2, e2 = await asyncio.wait_for(asyncio.open_connection(host, puerto), timeout=10)
    except (OSError, asyncio.TimeoutError) as e:
        log(f"{quien[0]} {motivo} -> {destino} ⛔ no contesta ({host}:{puerto}: {e})")
        escritor.close()
        return
    log(f"{quien[0]} {motivo} -> {destino}")
    e2.write(buf)
    await e2.drain()

    def _anotar(usn, vcode):
        anotar(usn, vcode, destino)
        log(f"  anotado usn={usn} -> {destino}")

    await asyncio.gather(_caño(lector, e2),
                         _caño(l2, escritor, _anotar if anotar_resp else None))


async def main():
    h, p = _hostport(os.environ.get("PUERTA_ESCUCHAR"), "0.0.0.0:48004")
    destinos = {"prod": _hostport(os.environ.get("PUERTA_PROD"), "r2beat2013:47004"),
                "prueba": _hostport(os.environ.get("PUERTA_PRUEBA"), "r2beat2013-prueba:49004")}
    n = cargar_mapa()
    srv = await asyncio.start_server(lambda l, e: atender(l, e, destinos), h, p)
    log(f"escucha {h}:{p} · prod {destinos['prod']} · prueba {destinos['prueba']} · {n} sesiones anotadas")
    async with srv:
        await srv.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
