# -*- coding: utf-8 -*-
"""juez — revisa CADA archivo que sube un amigo antes de guardarlo (16-nov-2026, TOPOLOGIA_CONTENEDORES §37).

Benja: «pruebas de seguridad para que no puedan subir malware o archivos malintencionados; un juez que valide los
archivos, que sea barato». Barato = sin antivirus ni dependencias: lee la CABEZA del archivo (y la COLA de un .pak,
donde está su tabla), nunca lo abre ni lo ejecuta. Unos milisegundos por archivo.

Lo que entra a la lista de prueba se INSTALA en la PC de todos los que marcan «Servidor de prueba». El juez separa:

    recurso   un archivo del juego (paks, imágenes, sonidos, textos) cuyo CONTENIDO es lo que dice la extensión.
              Entra como siempre: el autorizado directo, los demás con aprobación.
    sensible  un PROGRAMA (.exe .dll .asi …) o algo que decide qué se carga (.ini .conf .dat …). NUNCA entra directo:
              lo aprueba OTRO autorizado distinto de quien lo subió («dos llaves»), con las alertas a la vista.
    rechazo   todo lo demás: extensiones que el cliente no usa (.bat .ps1 .lnk .vbs .js .msi …), un programa
              DISFRAZADO (un «.png» que empieza con MZ), un contenido que no es lo que dice la extensión, un .pak con
              la tabla rota o con un programa adentro.

⚠ Ningún juez barato prueba que un archivo es inofensivo: un .pak bien formado puede traer contenido feo, y un
  programa aprobado puede ser un virus. Por eso el juez es UNA capa: las otras son la aprobación (dos llaves para
  programas), el historial para volver atrás (5 estados) y el interruptor que apaga las subidas.
"""
import os
import re
import struct

# Las que trae el cliente de verdad (inventario del 16-nov sobre D:\Game\R2beatENSAYO, 2.555 archivos) + las comunes
# de imagen/sonido que el motor también lee adentro de los paks.
RECURSOS = (".pak", ".bmp", ".jpg", ".jpeg", ".png", ".dds", ".tga", ".ogg", ".mp3", ".wav", ".ani", ".ico",
            ".txt", ".xml", ".csv")
# Programas y lo que decide qué programa se carga (la dll de video se elige desde un .ini; `.dxvk`/`.r2b`/`.dat`/
# `.bin` del cliente SON dlls/exes renombrados; `.lua`/`.xse`/`.xfs` son del anti-trampas viejo).
SENSIBLES = (".exe", ".dll", ".asi", ".sys", ".ocx", ".drv", ".dxvk", ".r2b", ".dat", ".bin", ".ini", ".conf",
             ".cfg", ".lua", ".xse", ".xfs", ".xmf", ".rc", ".ex_", ".sy_", ".r_")
# Adentro de un .pak: nada que Windows ejecute.
PROGRAMAS = (".exe", ".dll", ".asi", ".sys", ".ocx", ".drv", ".scr", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".vbe",
             ".js", ".jse", ".wsf", ".wsh", ".hta", ".msi", ".msp", ".lnk", ".url", ".reg", ".jar", ".pif", ".cpl",
             ".inf", ".application", ".gadget", ".psm1", ".dxvk", ".r2b")

MAGIA = {                       # extensión -> cabezas válidas (None = sin firma fija: se mira aparte)
    ".bmp": (b"BM",),
    ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".dds": (b"DDS ",),
    ".ogg": (b"OggS",),
    ".wav": (b"RIFF",),
    ".ani": (b"RIFF", b"\x00\x00\x01\x00", b"\x00\x00\x02\x00"),
    ".ico": (b"\x00\x00\x01\x00",),
}
_RED = re.compile(rb"\\\\[A-Za-z0-9_.\-]+\\|(?:https?|ftp|smb|file)://", re.I)
_MENCIONA_PROGRAMA = re.compile(rb"[A-Za-z0-9_\-]+\.(?:dll|exe|asi|dxvk|r2b|bat|ps1)\b", re.I)


class Rechazo(Exception):
    pass


def extension(ruta):
    return os.path.splitext(ruta)[1].lower()


def _es_texto(cab):
    if cab[:2] in (b"\xff\xfe", b"\xfe\xff"):          # UTF-16 con BOM
        return True
    return b"\x00" not in cab


def tabla_pak(f, largo):
    """La tabla de un .pak del R2Beat (en claro, al final; formato medido idéntico a r2pak, ver
    taller/launcher_webui/muneco_local.py): [(nombre, offset, guardado)]. Lee SÓLO la cola. Rechazo si no encuadra."""
    if largo < 32:
        raise Rechazo("No es un .pak válido (demasiado pequeño).")
    f.seek(largo - 9)
    idx_off = struct.unpack("<I", f.read(4))[0]
    if not 0 < idx_off < largo - 9 or largo - idx_off > 64 * 2**20:
        raise Rechazo("No es un .pak válido (índice ausente).")
    f.seek(idx_off)
    d = f.read(largo - idx_off)
    fin = len(d) - 9
    for pre in range(64):
        out, p = [], pre
        while p < fin:
            if p + 15 > fin:
                break
            nl, ty = d[p], d[p + 1]
            if nl == 0 or ty > 2 or p + 14 + nl >= len(d):
                break
            nombre = d[p + 14:p + 14 + nl]
            # (los nombres pueden venir en cp949/gbk: 35 paks del cliente real; sólo se niegan los de control)
            if d[p + 14 + nl] != 0 or any(b < 0x20 or b == 0x7F for b in nombre):
                break
            off, guardado, _orig = struct.unpack_from("<III", d, p + 2)
            out.append((nombre.decode("latin-1").replace("\\", "/"), off, guardado))
            p += nl + 15
        if out and p == fin:
            return out, idx_off
    raise Rechazo("No es un .pak válido (índice dañado).")


def _revisar_pak(f, largo):
    entradas, idx_off = tabla_pak(f, largo)
    for nombre, off, guardado in entradas:
        partes = nombre.split("/")
        if nombre.startswith("/") or ":" in nombre or ".." in partes:
            raise Rechazo(f"El .pak contiene una ruta fuera de la carpeta del juego: {nombre!r}.")
        if off + guardado > idx_off:
            raise Rechazo(f"El .pak está dañado: {nombre!r} excede el final del archivo.")
        if extension(nombre) in PROGRAMAS:
            raise Rechazo(f"El .pak contiene un programa: {nombre!r}.")
    return len(entradas)


def juzgar(ruta, archivo, largo):
    """-> {"clase": "recurso"|"sensible", "tipo": ".ext", "alertas": [...]} o Rechazo(motivo). `archivo` = la ruta
    del archivo YA guardado (temporal), `largo` = su tamaño."""
    ext = extension(ruta)
    if ext not in RECURSOS and ext not in SENSIBLES:
        raise Rechazo(f"Tipo de archivo no permitido: «{ext or 'sin extensión'}»" +
                      (" (programa o script)." if ext in PROGRAMAS else "."))
    alertas = []
    with open(archivo, "rb") as f:
        cab = f.read(65536)
        es_pe = cab[:2] == b"MZ"
        if ext in RECURSOS:
            if es_pe:
                raise Rechazo(f"El archivo es un programa con extensión {ext}.")
            if ext in MAGIA and not cab.startswith(MAGIA[ext]):
                raise Rechazo(f"El contenido no corresponde a un archivo {ext}.")
            if ext in (".txt", ".xml", ".csv") and not _es_texto(cab):
                raise Rechazo(f"El contenido no es texto: no corresponde a un archivo {ext}.")
            if ext == ".mp3" and not (cab[:3] == b"ID3" or (len(cab) > 1 and cab[0] == 0xFF and cab[1] & 0xE0 == 0xE0)):
                raise Rechazo("El contenido no corresponde a un archivo .mp3.")
            if ext == ".tga" and (len(cab) < 18 or cab[2] not in (1, 2, 3, 9, 10, 11)):
                raise Rechazo("El contenido no corresponde a un archivo .tga.")
            if ext == ".pak":
                n = _revisar_pak(f, largo)
                return {"clase": "recurso", "tipo": ext, "alertas": [], "adentro": n}
            return {"clase": "recurso", "tipo": ext, "alertas": []}
        # sensible: entra, pero con dos llaves y lo que el revisor tiene que mirar
        if es_pe:
            alertas.append("Programa ejecutable de Windows.")
        elif ext in (".exe", ".dll", ".asi", ".sys", ".ocx", ".drv", ".dxvk", ".r2b"):
            raise Rechazo(f"El archivo {ext} no es un programa de Windows válido.")
        if _RED.search(cab):
            alertas.append("Menciona una dirección de red (\\\\servidor\\… o http://): podría cargar contenido externo.")
        if not es_pe and _MENCIONA_PROGRAMA.search(cab):
            alertas.append("Menciona programas (" + ", ".join(sorted({m.decode('latin-1') for m in
                                                                    _MENCIONA_PROGRAMA.findall(cab)}))[:120] + ")")
        return {"clase": "sensible", "tipo": ext, "alertas": alertas or ["Modifica qué se carga al iniciar el juego."]}
