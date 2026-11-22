# -*- coding: utf-8 -*-
"""contenido — ★ 20-nov-2026, FASE B del panel del Coordinador: NOVEDADES y el CONTENIDO DINÁMICO de cada juego.

Eñeños: *«zona de contenido dinámico del launcher nuevo (para todos los juegos que tengan esa opción): premios de las
casillas de asistencia, premios de la ruleta, nuevos avisos… y arriba una pastilla de Novedades: el acordeón de
noticias (el que abre hacia abajo) y los parches de los juegos (el que abre hacia la izquierda)»*.

DE DÓNDE SALE CADA COSA (no hay copias: el panel edita la fuente que ya lee el launcher o el juego)
- Noticias y parches del launcher, asistencia, ruleta, tira del lobby: en el SERVER DEL JUEGO (R2Beat 2013:
  `launcher_contenido` + `tira_anuncios` de su datos.db). Se llega por la red de adentro con la ficha interna:
  `R2_PANEL_CONTENIDO` = «pase=http://…/api/interno/contenido;…» (ver `contenido_interno.py` del juego).
  Un servidor sin fuente, o que no contesta, aparece como «todavía no tiene contenido dinámico» (no se inventa).
- NOVEDADES: el acordeón es UNO para toda la red, y hoy lo sirve el server de R2Beat (el launcher lo pide a
  `/api/launcher/publico`). `R2_NOVEDADES_FUENTE` = el pase que lo tiene (de fábrica r2beat2013).
  Cada juego del catálogo dice con qué nombre aparece ahí: `juegos.json` → `"noticias": "gunbound"` (el server sólo
  acepta r2beat · eda · love · gunbound · general).
- LANZAMIENTO (fecha de apertura y etiqueta): `config/lanzamientos.json` de Cuenta Eñeños (acá mismo).

QUIÉN PUEDE
- Ver: el que ve ese juego (ADMIN, o el moderador que lo tiene).
- Editar el contenido de un juego: ADMIN, o el MODERADOR que tiene ese juego asignado (como banear). El de formato
  viejo (sin lista de juegos) sólo mira.
- Novedades: el moderador edita SÓLO las de sus juegos; las de otros juegos y las GENERALES (mantenimiento, launcher)
  quedan como están aunque mande otra cosa. Las generales: sólo ADMIN.
- La fecha de un lanzamiento: sólo ADMIN (abrir un juego antes es decisión de Eñeños).
⛔ Todo cambio queda en DOS auditorías: la del Coordinador y la del panel viejo del juego («coordinador:<login>»).
⛔ Novedades lleva `base` (la huella de lo que el panel tenía): si otro guardó en el medio, 409 y no se pisa.
"""
import hashlib
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from . import lanzamientos as LZ

TIMEOUT = 8
NOVEDADES_FUENTE_DEFECTO = "r2beat2013"
NOTICIAS_GENERAL = "general"
CLAVES_JUEGO = ("asistencia", "ruleta", "tira")
_PERU = timezone(timedelta(hours=-5))
_lanz_lock = threading.Lock()


class SinFuente(Exception):
    """Ese servidor no tiene contenido dinámico (sin fuente, o no contesta). El texto va tal cual al panel."""


# ── la red de adentro ─────────────────────────────────────────────────────────────────────────────
def fuentes():
    out = {}
    for parte in (os.environ.get("R2_PANEL_CONTENIDO") or "").split(";"):
        if "=" in parte:
            p, u = parte.split("=", 1)
            if p.strip() and u.strip().startswith(("http://", "https://")):
                out[p.strip()] = u.strip().rstrip("/")
    return out


def _http(pase, ruta="", cuerpo=None):
    """-> (código, datos) del server del juego. ⛔ Sin fuente o sin ficha: SinFuente."""
    url = fuentes().get(pase)
    ficha = (os.environ.get("R2_CUENTAS_FICHA_INTERNA") or "").strip()
    if not url or not ficha:
        raise SinFuente("Este servidor todavía no tiene contenido dinámico.")
    cab = {"X-Ficha-Interna": ficha, "User-Agent": "enenos-coordinador", "Content-Type": "application/json"}
    datos = None
    if cuerpo is not None:
        cab["X-R2"] = "1"
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(url + ruta, data=datos, headers=cab), timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read(4 << 20).decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SinFuente("Este servidor todavía no tiene contenido dinámico (su versión no lo trae).") from None
        try:
            return e.code, json.loads(e.read(65536).decode("utf-8") or "{}")
        except ValueError:
            return e.code, {"error": f"El servidor del juego contestó {e.code}."}
    except (OSError, ValueError):
        raise SinFuente("El servidor del juego no contesta ahora. Pruebe en un rato.") from None


# ── permisos ──────────────────────────────────────────────────────────────────────────────────────
def _juego(CO, P, jid):
    return next((j for j in CO.catalogo(P) if j["id"] == jid), None)


def puede_ver(CO, P, viewer, jid):
    return P.rol_de(viewer) is not None and any(j["id"] == jid for j in CO.visibles(P, viewer))


def puede_editar(P, viewer, jid):
    rol = P.rol_de(viewer)
    if rol == "admin":
        return True
    if rol != "moderador":
        return False
    mios = P.juegos_de_moderador(viewer)
    return mios is not None and jid in mios


def _quien(P, viewer):
    return "coordinador:" + (P._login_de(viewer) or f"uid {viewer}")


def _pase(CO, P, jid, entorno):
    j = _juego(CO, P, jid)
    if not j:
        return None
    return ((j.get("pases") or {}).get(entorno)) if entorno in ("live", "test") else None


# ── el contenido de UN juego ──────────────────────────────────────────────────────────────────────
def _lanzamiento(CO, P, jid, ahora):
    for k, v in LZ.tabla(P).items():
        if CO.juego_de_pase(P, k) == jid:
            return {"clave": k, "etiqueta": v.get("etiqueta", ""), "desde": v["desde_t"],
                    "desde_peru": datetime.fromtimestamp(v["desde_t"], _PERU).strftime("%Y-%m-%dT%H:%M"),
                    "libre": ahora >= v["desde_t"]}
    return None


def leer(CO, P, viewer, jid, entorno, ahora):
    if not puede_ver(CO, P, viewer, jid):
        return 404, {"error": "Ese juego no existe o no está asignado a su cuenta."}
    pase = _pase(CO, P, jid, entorno)
    out = {"juego": jid, "entorno": entorno, "pase": pase, "puede_editar": puede_editar(P, viewer, jid),
           "es_admin": P.rol_de(viewer) == "admin", "lanzamiento": _lanzamiento(CO, P, jid, ahora),
           "servidor": None, "sin_servidor": None}
    if not pase:
        out["sin_servidor"] = "Este juego no tiene servidor de " + ("prueba." if entorno == "test" else "producción.")
        return 200, out
    try:
        cod, d = _http(pase)
        if cod != 200:
            out["sin_servidor"] = d.get("error") or f"El servidor del juego contestó {cod}."
        else:
            out["servidor"] = {k: d.get(k) for k in ("cambiado", "asistencia", "asistencia_mes", "ruleta",
                                                      "ruleta_resumen", "ruleta_mayor_total", "tira",
                                                      "tira_texto_max", "tira_total_max")}
    except SinFuente as e:
        out["sin_servidor"] = str(e)
    return 200, out


def guardar(CO, P, viewer, d, ahora):
    jid, entorno, clave = str(d.get("juego") or ""), str(d.get("entorno") or ""), d.get("clave")
    if not puede_ver(CO, P, viewer, jid):
        return 404, {"error": "Ese juego no existe o no está asignado a su cuenta."}
    if not puede_editar(P, viewer, jid):
        return 403, {"error": "Su cuenta puede mirar este juego, pero no cambiar su contenido."}
    if clave == "lanzamiento":
        return guardar_lanzamiento(CO, P, viewer, jid, d.get("valor"), ahora)
    if clave not in CLAVES_JUEGO:
        return 400, {"error": "clave: " + " · ".join(CLAVES_JUEGO + ("lanzamiento",))}
    pase = _pase(CO, P, jid, entorno)
    if not pase:
        return 404, {"error": "Ese juego no tiene ese servidor."}
    try:
        cod, r = _http(pase, "", {"clave": clave, "valor": d.get("valor"), "quien": _quien(P, viewer)})
    except SinFuente as e:
        return 503, {"error": str(e)}
    if cod == 200:
        P._auditar(viewer, f"contenido · {clave}", None, pase, "guardado desde el Coordinador")
    return cod, r


def previa(CO, P, viewer, d):
    jid, entorno = str(d.get("juego") or ""), str(d.get("entorno") or "")
    if not puede_ver(CO, P, viewer, jid):
        return 404, {"error": "Ese juego no existe o no está asignado a su cuenta."}
    pase = _pase(CO, P, jid, entorno)
    if not pase:
        return 404, {"error": "Ese juego no tiene ese servidor."}
    try:
        return _http(pase, "/previa", {"clave": d.get("clave"), "valor": d.get("valor"), "mes": d.get("mes")})
    except SinFuente as e:
        return 503, {"error": str(e)}


def items(CO, P, viewer, jid, entorno, q):
    if not puede_ver(CO, P, viewer, jid):
        return 404, {"error": "Ese juego no existe o no está asignado a su cuenta."}
    pase = _pase(CO, P, jid, entorno)
    if not pase:
        return 404, {"error": "Ese juego no tiene ese servidor."}
    try:
        import urllib.parse
        return _http(pase, "/items?q=" + urllib.parse.quote(str(q or "")[:60]))
    except SinFuente as e:
        return 503, {"error": str(e)}


def guardar_lanzamiento(CO, P, viewer, jid, v, ahora):
    """{desde_peru: "AAAA-MM-DDTHH:MM", etiqueta}. Sólo ADMIN. Escribe `config/lanzamientos.json` (lo relee solo)."""
    if P.rol_de(viewer) != "admin":
        return 403, {"error": "La fecha de apertura la cambia un ADMIN."}
    lz = _lanzamiento(CO, P, jid, ahora)
    if not lz:
        return 404, {"error": "Este juego no tiene lanzamiento."}
    v = v if isinstance(v, dict) else {}
    try:
        cuando = datetime.strptime(str(v.get("desde_peru") or ""), "%Y-%m-%dT%H:%M").replace(tzinfo=_PERU)
    except ValueError:
        return 400, {"error": "La fecha tiene que ser día y hora (hora de Perú)."}
    etiqueta = str(v.get("etiqueta", lz["etiqueta"]) or "").strip().upper()
    if etiqueta not in ("", "BETA", "ALPHA"):
        return 400, {"error": "Etiqueta: BETA, ALPHA o ninguna."}
    ruta = os.path.join(os.path.dirname(os.path.abspath(P.ruta_base_portero())), "config", "lanzamientos.json")
    with _lanz_lock:
        try:
            with open(ruta, encoding="utf-8") as f:
                actual = json.load(f) or {}
        except FileNotFoundError:
            actual = {}
        except (OSError, ValueError):
            return 500, {"error": "lanzamientos.json está ilegible: no lo piso. Hay que revisarlo a mano."}
        actual.setdefault(lz["clave"], {}).update({"desde": cuando.isoformat(), "etiqueta": etiqueta})
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        tmp = ruta + ".nuevo"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(actual, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ruta)
    P._auditar(viewer, "contenido · lanzamiento", None, lz["clave"], f"abre {cuando.isoformat()} {etiqueta}".strip())
    return 200, {"ok": True, "lanzamiento": _lanzamiento(CO, P, jid, ahora)}


# ── NOVEDADES (una para toda la red) ──────────────────────────────────────────────────────────────
def _fuente_novedades():
    return (os.environ.get("R2_NOVEDADES_FUENTE") or NOVEDADES_FUENTE_DEFECTO).strip()


def _huella(lista):
    return hashlib.sha256(json.dumps(lista, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _mapa_noticias(CO, P):
    """{nombre en las noticias: juego del catálogo} (sólo los juegos que declaran `"noticias"` en juegos.json)."""
    return {j["noticias"]: j for j in CO.catalogo(P) if j.get("noticias")}


def _editables(CO, P, viewer):
    """Los `juego` de noticia que esa cuenta puede tocar."""
    if P.rol_de(viewer) == "admin":
        return set(_mapa_noticias(CO, P)) | {NOTICIAS_GENERAL}
    return {n for n, j in _mapa_noticias(CO, P).items() if puede_editar(P, viewer, j["id"])}


def leer_novedades(CO, P, viewer):
    if P.rol_de(viewer) is None:
        return 401, {"error": "Tiene que entrar con Discord o Google."}
    try:
        cod, d = _http(_fuente_novedades())
    except SinFuente as e:
        return 200, {"sin_servidor": str(e), "noticias": [], "juegos": [], "base": None}
    if cod != 200:
        return 200, {"sin_servidor": d.get("error") or f"El servidor contestó {cod}.", "noticias": [], "juegos": [],
                     "base": None}
    lista = d.get("noticias") or []
    ed = _editables(CO, P, viewer)
    vistos = {j["id"] for j in CO.visibles(P, viewer)}
    mapa = _mapa_noticias(CO, P)
    juegos = [{"id": n, "juego": j["id"], "nombre": j.get("corto") or j.get("nombre"), "editable": n in ed,
               "color": ((j.get("panel") or {}).get("color")) or "81,216,229"}
              for n, j in mapa.items() if j["id"] in vistos or n in ed]
    juegos.append({"id": NOTICIAS_GENERAL, "juego": None, "nombre": "General", "editable": NOTICIAS_GENERAL in ed,
                   "color": "81,216,229"})
    return 200, {"noticias": [dict(n, editable=n.get("juego", "r2beat") in ed) for n in lista],
                 "juegos": juegos, "base": _huella(lista), "etiquetas": d.get("etiquetas") or [],
                 "etiquetas_general": d.get("etiquetas_general") or [], "noticias_max": d.get("noticias_max"),
                 "texto_max": d.get("noticia_texto_max"), "cambiado": (d.get("cambiado") or {}).get("noticias")}


def guardar_novedades(CO, P, viewer, d):
    """{noticias: [...], base}. El moderador sólo toca las de SUS juegos: lo demás se conserva tal cual."""
    if P.rol_de(viewer) is None:
        return 401, {"error": "Tiene que entrar con Discord o Google."}
    ed = _editables(CO, P, viewer)
    if not ed:
        return 403, {"error": "Su cuenta no tiene juegos asignados para editar novedades."}
    nuevas = d.get("noticias")
    if not isinstance(nuevas, list):
        return 400, {"error": "noticias: una lista."}
    limpias = []
    for i, n in enumerate(nuevas, 1):
        if not isinstance(n, dict):
            return 400, {"error": f"noticia {i}: mal armada."}
        n = {k: v for k, v in n.items() if k not in ("editable", "id")}
        if n.get("juego", "r2beat") not in ed:
            return 403, {"error": f"«{str(n.get('titulo') or '')[:40]}»: ese juego no está asignado a su cuenta."}
        limpias.append(n)
    fuente = _fuente_novedades()
    try:
        cod, actual = _http(fuente)
        if cod != 200:
            return 503, {"error": actual.get("error") or "El servidor de las novedades no contesta."}
        lista = actual.get("noticias") or []
        if d.get("base") != _huella(lista):
            return 409, {"error": "Alguien cambió las novedades mientras usted editaba. Se recargan: revise y vuelva "
                                  "a guardar."}
        quedan = [n for n in lista if n.get("juego", "r2beat") not in ed]       # lo que NO es suyo, intacto
        cod, r = _http(fuente, "", {"clave": "noticias", "valor": quedan + limpias, "quien": _quien(P, viewer)})
    except SinFuente as e:
        return 503, {"error": str(e)}
    if cod != 200:
        return cod, r
    P._auditar(viewer, "contenido · novedades", None, fuente, f"{len(limpias)} propias, {len(quedan)} de otros")
    return leer_novedades(CO, P, viewer)
