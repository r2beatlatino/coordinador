# -*- coding: utf-8 -*-
"""Páginas del launcher: publicación local, borradores de NOVEDADES y base contra pisadas.

Fuente: config/paginas.json junto a portero.db; nunca se publica al importar.
Permisos: los de contenido. Auditoría local: «contenido · pagina» (no hay server
del juego que replicar). Todas las mutaciones releen y reemplazan bajo el mismo lock.
"""
import hashlib
import json
import os
import re
import tempfile
import threading
import unicodedata
import urllib.request
from datetime import date, datetime, timezone

from . import contenido as CT

_lock = threading.RLock()
IDIOMAS_EDA = [{"id": "es", "nombre": "Español"}, {"id": "en", "nombre": "English"}]


def _texto(v, maximo, campo, vacio=True, multilinea=False):
    if multilinea and isinstance(v, str):
        v = v.replace("\r", "")
    if (not isinstance(v, str) or len(v) > maximo or (not vacio and not v.strip())
            or any(c in "<>" or (unicodedata.category(c).startswith("C")
                                and not (multilinea and c == "\n")) for c in v)):
        raise ValueError(f"{campo}: texto plano, hasta {maximo} caracteres, sin controles ni < >.")
    return v if multilinea else v.strip()


def _lista(v, maximo, campo):
    if not isinstance(v, list) or len(v) > maximo:
        raise ValueError(f"{campo}: una lista de hasta {maximo} entradas.")
    return v


def validar_version(v):
    if not isinstance(v, dict):
        raise ValueError("versión: una entrada de NOVEDADES.")
    out = {"version": _texto(v.get("version"), 80, "version", False),
           "fecha": _texto(v.get("fecha"), 10, "fecha", False),
           "resumen": _texto(v.get("resumen", ""), 280, "resumen")}
    try:
        if date.fromisoformat(out["fecha"]).isoformat() != out["fecha"]:
            raise ValueError()
    except ValueError:
        raise ValueError("fecha: AAAA-MM-DD válido.") from None
    for k in ("corregidos", "mejoras", "avisos"):
        out[k] = [_texto(x, 160, k, False) for x in _lista(v.get(k, []), 8, k)]
    return out


def validar(v, jid):
    if not isinstance(v, dict) or not isinstance(v.get("banner"), dict):
        raise ValueError("publicada: una página con banner.")
    b = v["banner"]
    out = {"banner": {"sello": _texto(b.get("sello", ""), 24, "sello"),
                      "titulo": _texto(b.get("titulo", ""), 48, "título")},
           "version_actual": _texto(v.get("version_actual", ""), 80, "version_actual"),
           "versiones": [validar_version(x) for x in _lista(v.get("versiones", []), 10, "versiones")],
           "cajas": [], "idiomas": []}
    ids = [x["version"] for x in out["versiones"]]
    if len(set(ids)) != len(ids) or (out["version_actual"] and out["version_actual"] not in ids):
        raise ValueError("version_actual debe estar en el historial, sin versiones repetidas.")
    out["versiones"].sort(key=lambda x: (x["fecha"], tuple(
        (1, int(p)) if p.isdigit() else (0, p) for p in re.split(r"(\d+)", x["version"]))), reverse=True)
    for x in _lista(v.get("cajas", []), 4, "cajas"):
        if not isinstance(x, dict):
            raise ValueError("caja: título y texto.")
        out["cajas"].append({"titulo": _texto(x.get("titulo", ""), 40, "caja título"),
                             "texto": _texto(x.get("texto", ""), 200, "caja texto")})
    for x in _lista(v.get("idiomas", IDIOMAS_EDA if jid == "eda" else []), 8, "idiomas"):
        if not isinstance(x, dict) or not isinstance(x.get("id"), str) or not re.fullmatch(r"[a-z]{2,8}", x["id"]):
            raise ValueError("idioma id: de 2 a 8 letras minúsculas (a-z).")
        idioma = {"id": x["id"], "nombre": _texto(x.get("nombre"), 24, "idioma nombre", False)}
        # ★ 23-nov (Eñeños): el % de traducción de cada idioma, al lado de su nombre en el launcher. Opcional; lo mide
        #   `herramientas/avance_traduccion.py` del repo del R2Beat 2013 sobre el cliente, no se escribe a ojo.
        if x.get("avance") is not None:
            if type(x["avance"]) is not int or not 0 <= x["avance"] <= 100:
                raise ValueError("idioma avance: un entero de 0 a 100.")
            idioma["avance"] = x["avance"]
        out["idiomas"].append(idioma)
    if len({x["id"] for x in out["idiomas"]}) != len(out["idiomas"]):
        raise ValueError("idiomas: ids repetidos.")
    if "presentacion" in v:
        p = v["presentacion"]
        if not isinstance(p, dict) or p.get("arte", "1") not in ("1", "2", "3"):
            raise ValueError("presentacion: título, texto y arte (1, 2 o 3).")
        out["presentacion"] = {"titulo": _texto(p.get("titulo", ""), 60, "presentacion título"),
                               "texto": _texto(p.get("texto", ""), 1200, "presentacion texto", multilinea=True),
                               "arte": p.get("arte", "1")}
    if "voces" in v:
        out["voces"] = []
        for x in _lista(v["voces"], 8, "voces"):
            if not isinstance(x, dict) or not isinstance(x.get("id"), str) or not re.fullmatch(r"[a-z]{2,10}", x["id"]):
                raise ValueError("voz id: de 2 a 10 letras minúsculas (a-z).")
            out["voces"].append({"id": x["id"], "nombre": _texto(x.get("nombre"), 24, "voz nombre", False)})
        if len({x["id"] for x in out["voces"]}) != len(out["voces"]):
            raise ValueError("voces: ids repetidos.")
    return out


def _ruta(P):
    return os.path.join(os.path.dirname(os.path.abspath(P.ruta_base_portero())), "config", "paginas.json")


def _leer(P):
    try:
        with open(_ruta(P), encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        P._log("paginas.json ausente; no hay páginas publicadas")
        return {}
    if not isinstance(datos, dict) or any(not isinstance(v, dict) for v in datos.values()):
        raise ValueError("estructura inválida")
    for jid, registro in datos.items():
        publicada = registro.get("publicada")
        if publicada is not None:
            actualizada = publicada.get("actualizada") if isinstance(publicada, dict) else None
            if not isinstance(actualizada, str) or datetime.fromisoformat(actualizada).tzinfo is None:
                raise ValueError("actualizada: ISO con huso")
            registro["publicada"] = dict(validar(publicada, jid), actualizada=actualizada)
        borradores = registro.get("borradores", [])
        if not isinstance(borradores, list):
            raise ValueError("borradores: una lista")
        vistos = set()
        for entrada in borradores:
            limpia = validar_version(entrada)
            importada = entrada.get("importada")
            if not isinstance(importada, str) or datetime.fromisoformat(importada).tzinfo is None:
                raise ValueError("importada: ISO con huso")
            if limpia["version"] in vistos:
                raise ValueError("borradores repetidos")
            vistos.add(limpia["version"])
    return datos


def publicadas(P):
    """Sólo el contrato público; un archivo roto jamás rompe /lanzamientos."""
    with _lock:
        try:
            return {jid: registro["publicada"] for jid, registro in _leer(P).items()
                    if registro.get("publicada") is not None}
        except (OSError, ValueError, TypeError, RecursionError) as e:
            P._log(f"⚠ paginas.json ilegible ({e}); no hay páginas publicadas")
            return {}


def _estado(registro):
    contenido = {"publicada": registro.get("publicada"), "borradores": registro.get("borradores", [])}
    base = hashlib.sha256(json.dumps(contenido, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return dict(contenido, base=base)


def _permiso(CO, P, viewer, jid, editar=False):
    if not CT._juego(CO, P, jid):
        return 404, {"error": "Ese juego no existe."}
    if editar and not CT.puede_editar(P, viewer, jid):
        return 403, {"error": "Ese juego no está asignado a su cuenta para editar."}
    if not CT.puede_ver(CO, P, viewer, jid):
        return 404, {"error": "Ese juego no existe o no está asignado a su cuenta."}


def leer(CO, P, viewer, jid):
    error = _permiso(CO, P, viewer, jid)
    if error:
        return error
    with _lock:
        try:
            return 200, dict(_estado(_leer(P).get(jid, {})), puede_editar=CT.puede_editar(P, viewer, jid))
        except (OSError, ValueError, TypeError, RecursionError):
            return 500, {"error": "paginas.json está ilegible: no lo piso. Hay que revisarlo a mano."}


def _guardar(P, datos):
    ruta = _ruta(P)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="paginas-", suffix=".nuevo", dir=os.path.dirname(ruta))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ruta)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _ahora():
    return datetime.now(timezone.utc).isoformat()


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "enenos-coordinador"})
    with urllib.request.urlopen(req, timeout=8) as r:
        raw = r.read((4 << 20) + 1)
    if len(raw) > 4 << 20:
        raise ValueError("NOVEDADES.json supera 4 MiB.")
    return json.loads(raw.decode("utf-8-sig"))


def cambiar(CO, P, viewer, d, accion="guardar", fetch=None):
    jid = d.get("juego")
    error = _permiso(CO, P, viewer, jid, editar=True)
    if error:
        return error
    entradas = None
    if accion == "importar":
        url = CT._juego(CO, P, jid).get("novedades_url")
        if not isinstance(url, str) or not url.startswith("https://"):
            return 400, {"error": "Este juego no declara novedades_url (HTTPS) en el catálogo."}
        try:
            fuente = (fetch or _fetch)(url)
            entradas = fuente.get("versiones") if isinstance(fuente, dict) else fuente
            if not isinstance(entradas, list):
                raise ValueError("NOVEDADES.json: se esperaba una lista de versiones.")
        except (OSError, ValueError, TypeError) as e:
            return 502, {"error": f"No se pudo importar NOVEDADES.json: {e}"}
    with _lock:
        try:
            datos = _leer(P)
            estado = _estado(datos.get(jid, {}))
        except (OSError, ValueError, TypeError, RecursionError):
            return 500, {"error": "paginas.json está ilegible: no lo piso. Hay que revisarlo a mano."}
        if accion != "importar" and d.get("base") != estado["base"]:
            return 409, {"error": "Alguien cambió la página. Recargue, revise y vuelva a guardar."}
        resultado = {}
        try:
            if accion == "guardar":
                estado["publicada"] = dict(validar(d.get("publicada"), jid), actualizada=_ahora())
            elif accion == "publicar":
                version = d.get("version")
                entrada = next((x for x in estado["borradores"] if x["version"] == version), None)
                if entrada is None:
                    return 404, {"error": "Ese borrador no existe."}
                pagina = estado["publicada"] or {"banner": {"sello": "", "titulo": ""}}
                versiones = [validar_version(entrada)] + [x for x in pagina.get("versiones", []) if x["version"] != version]
                pagina = dict(pagina, versiones=versiones[:10], version_actual=version)
                estado["publicada"] = dict(validar(pagina, jid), actualizada=_ahora())
                estado["borradores"] = [x for x in estado["borradores"] if x["version"] != version]
            elif accion == "importar":
                existentes = {x["version"] for x in estado["borradores"]}
                existentes.update(x["version"] for x in (estado["publicada"] or {}).get("versiones", []))
                invalidas, cantidad = [], 0
                for i, x in enumerate(entradas, 1):
                    if isinstance(x, dict) and x.get("borrador") is True:
                        continue
                    try:
                        limpia = validar_version(x)
                    except ValueError as e:
                        invalidas.append({"entrada": i, "error": str(e)})
                        continue
                    if limpia["version"] not in existentes:
                        estado["borradores"].append(dict(limpia, importada=_ahora()))
                        existentes.add(limpia["version"])
                        cantidad += 1
                resultado = {"importadas": cantidad, "invalidas": invalidas}
            else:
                return 400, {"error": "Acción desconocida."}
            datos[jid] = _estado(estado)
            _guardar(P, datos)
        except ValueError as e:
            return 400, {"error": str(e)}
        except OSError:
            return 500, {"error": "No se pudo guardar paginas.json."}
        P._auditar(viewer, "contenido · pagina", None, jid, accion)
        return 200, dict(datos[jid], puede_editar=True, **resultado)
