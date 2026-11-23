# -*- coding: utf-8 -*-
"""torneos — ★ 20-nov-2026: los TORNEOS de cada juego, manejados desde el panel del Coordinador.

Eñeños: *«me encanta, mételo al launcher»* (el popup de torneos del prototipo). Los torneos, la votación de la hora, la
inscripción y la llave viven en el SERVER DEL JUEGO (R2Beat 2013: `servidor/torneos.py` de su repo, con su datos.db).
El contrato es `documentacion/TORNEOS.md` del R2Beat 2013 (sección 3: la puerta del Coordinador). Acá no hay copias:
el panel le pide al juego y el juego es el que decide (estados, cupo, llave, quién gana).

CÓMO
- Por la red de adentro, con la ficha interna: `R2_PANEL_TORNEOS` = «pase=http://…/api/interno/torneos;…».
  GET = todos los torneos (también borrador y cancelado), con inscritos y cruces completos.
  POST {accion, …} = crear · editar · estado · fijar_hora · resultado · reiniciar · cancion · jugando · tercero · quitar.
  El pedido viaja con `X-Ficha-Interna`, `X-R2: 1` (los POST) y `X-Coordinador-Quien: coordinador:<login>`: el juego
  lo anota en la auditoría de su panel viejo. El error del juego (en español neutro de «usted») llega TAL CUAL.
- Un servidor sin fuente, o con una versión que no lo trae (el juego contesta 404 «no existe»), aparece como
  «todavía no tiene torneos» (no se inventa nada).

QUIÉN PUEDE
- Ver: el que ve ese juego (ADMIN, o el moderador que lo tiene asignado). A un moderador no le llega nada privado
  (IP, login…: `gestion._limpiar`), y cada «quien» le llega como en la auditoría (su nombre o «ADMIN», nunca un login).
  A los ADMIN se les sacan las IP, salvo si su Eñeños-ID está en R2_VEN_IPS.
- Manejar (todo POST): ADMIN, o el MODERADOR con ese juego asignado Y la acción asignable «torneos»
  (`gestion.ASIGNABLES`, la asigna un ADMIN en «Permisos» del equipo). El de formato viejo (sin juegos) sólo mira.
⛔ Todo cambio queda en DOS auditorías: la del Coordinador («torneos · <acción>») y la del panel viejo del juego.
"""
import json
import os
import urllib.error
import urllib.request

from . import gestion as GE

TIMEOUT = 10
ACCIONES = ("crear", "editar", "estado", "fijar_hora", "resultado", "reiniciar", "cancion", "jugando", "tercero",
            "quitar")
SIN_TORNEOS = "Este servidor todavía no tiene torneos."


class SinFuente(Exception):
    """Ese servidor no tiene torneos (sin fuente, sin versión o no contesta). El texto va tal cual al panel."""


# ── la red de adentro ─────────────────────────────────────────────────────────────────────────────
def fuentes():
    out = {}
    for parte in (os.environ.get("R2_PANEL_TORNEOS") or "").split(";"):
        if "=" in parte:
            p, u = parte.split("=", 1)
            if p.strip() and u.strip().startswith(("http://", "https://")):
                out[p.strip()] = u.strip().rstrip("/")
    return out


def _http(url, cuerpo, quien):
    """-> (código, datos) del server del juego. ⛔ Sin ficha, sin versión o caído: SinFuente."""
    ficha = (os.environ.get("R2_CUENTAS_FICHA_INTERNA") or "").strip()
    if not url or not ficha:
        raise SinFuente(SIN_TORNEOS)
    cab = {"X-Ficha-Interna": ficha, "X-Coordinador-Quien": quien, "User-Agent": "enenos-coordinador",
           "Content-Type": "application/json"}
    datos = None
    if cuerpo is not None:
        cab["X-R2"] = "1"
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=datos, headers=cab), timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read(8 << 20).decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read(65536).decode("utf-8") or "{}")
        except ValueError:
            d = None
        # el 404 de la PUERTA (ficha mala o una versión sin torneos) no es el 404 de un torneo que no existe
        if e.code == 404 and (not isinstance(d, dict) or str(d.get("error") or "") in ("", "no existe")):
            raise SinFuente("Este servidor todavía no tiene torneos (su versión no los trae).") from None
        if not isinstance(d, dict):
            d = {"error": f"El servidor del juego contestó {e.code}."}
        return e.code, d
    except (OSError, ValueError):
        raise SinFuente("El servidor del juego no contesta ahora. Pruebe en un rato.") from None


# ── permisos ──────────────────────────────────────────────────────────────────────────────────────
def _juego(CO, P, jid):
    return next((j for j in CO.catalogo(P) if j["id"] == jid), None)


def puede_ver(CO, P, viewer, jid):
    return P.rol_de(viewer) is not None and any(j["id"] == jid for j in CO.visibles(P, viewer))


def puede_manejar(P, viewer, jid):
    """ADMIN, o el moderador con ese juego y la acción asignable «torneos» (la lista la arma `gestion.permisos`)."""
    return "torneos" in GE.permisos(P, viewer, jid)["acciones"]


def _quien(P, viewer):
    return "coordinador:" + (P._login_de(viewer) or f"uid {viewer}")


def _pase(CO, P, jid, entorno):
    j = _juego(CO, P, jid)
    if not j or entorno not in ("live", "test"):
        return None
    return (j.get("pases") or {}).get(entorno)


def _para_moderador(CO, P, d):
    """Lo que el juego manda, como lo puede ver un moderador: sin nada privado (`gestion._limpiar`) y con cada
    `quien` («coordinador:<login>») pasado a como lo muestra la auditoría (su nombre, o «ADMIN»). ⛔ Nunca un login."""
    admins_login = {P._login_de(u) for u in P.admins()} - {None}

    def quien(v):
        q = str(v or "")
        if q.startswith("coordinador:"):
            q = q[len("coordinador:"):]
        return CO._quien_para(P, q, False, admins_login) if q else v

    def andar(v):
        if isinstance(v, dict):
            return {k: (quien(x) if k == "quien" else andar(x)) for k, x in v.items()}
        if isinstance(v, list):
            return [andar(x) for x in v]
        return v
    return andar(GE._limpiar(d))


def _detalle(accion, d):
    """Lo que se anota en la auditoría del Coordinador (corto, sin datos de jugadores)."""
    t = d.get("torneo")
    partes = [f"torneo {t}" if t is not None else str(d.get("nombre") or "")[:60]]
    if accion in ("resultado", "reiniciar", "cancion", "jugando"):
        partes.append(f"ronda {d.get('ronda')} cruce {d.get('idx')}")
    if accion == "estado":
        partes.append(f"→ {d.get('estado')}")
    elif accion == "resultado":
        partes.append(f"ganó {d.get('ganador')}")
    elif accion == "reiniciar" and d.get("forzar"):
        partes.append("forzado")
    elif accion == "jugando":
        partes.append("se está jugando" if d.get("si") else "ya no")
    elif accion in ("tercero", "quitar"):
        partes.append(f"inscrito {d.get('ins_id')}")
    elif accion == "fijar_hora":
        partes.append(f"opción {d['opcion']}" if d.get("opcion") is not None else f"fecha {d.get('fecha')}")
    return " · ".join(p for p in partes if p)[:160]


# ── lo que pide el panel ──────────────────────────────────────────────────────────────────────────
def leer(CO, P, viewer, jid, entorno):
    """GET /api/torneos?juego=&entorno= -> {juego, entorno, pase, con_fuente, puede, es_admin, servidor|null,
    sin_servidor|null}. `servidor` = lo que contesta el juego (`torneos: [...]`)."""
    jid = str(jid or "")
    if not puede_ver(CO, P, viewer, jid):
        return 404, {"error": "Ese juego no existe o no está asignado a su cuenta."}
    pase = _pase(CO, P, jid, entorno)
    url = fuentes().get(pase or "")
    admin = P.rol_de(viewer) == "admin"
    out = {"juego": jid, "entorno": entorno, "pase": pase, "con_fuente": bool(url), "es_admin": admin,
           "puede": puede_manejar(P, viewer, jid), "servidor": None, "sin_servidor": None}
    if not pase:
        out["sin_servidor"] = "Este juego no tiene servidor de " + ("prueba." if entorno == "test" else "producción.")
        return 200, out
    if not url:
        out["sin_servidor"] = SIN_TORNEOS
        return 200, out
    try:
        cod, d = _http(url, None, _quien(P, viewer))
    except SinFuente as e:
        out["sin_servidor"] = str(e)
        return 200, out
    if cod != 200:
        out["sin_servidor"] = d.get("error") or f"El servidor del juego contestó {cod}."
        return 200, out
    out["servidor"] = (d if GE.puede_ver_ips(P, viewer) else GE._sin_ips(d)) if admin else _para_moderador(CO, P, d)
    return 200, out


def accion(CO, P, viewer, d):
    """POST /api/torneos {juego, entorno, accion, …el resto va al juego tal cual}."""
    d = d if isinstance(d, dict) else {}
    jid, entorno, acc = str(d.get("juego") or ""), str(d.get("entorno") or ""), str(d.get("accion") or "")
    if not puede_ver(CO, P, viewer, jid):
        return 404, {"error": "Ese juego no existe o no está asignado a su cuenta."}
    if not puede_manejar(P, viewer, jid):
        return 403, {"error": "Su cuenta puede mirar los torneos de este juego, pero no manejarlos. Lo asigna un ADMIN."}
    if acc not in ACCIONES:
        return 400, {"error": "accion: " + " · ".join(ACCIONES)}
    pase = _pase(CO, P, jid, entorno)
    url = fuentes().get(pase or "")
    if not url:
        return 404, {"error": SIN_TORNEOS}
    cuerpo = {k: v for k, v in d.items() if k not in ("juego", "entorno", "quien")}
    try:
        cod, r = _http(url, cuerpo, _quien(P, viewer))
    except SinFuente as e:
        return 503, {"error": str(e)}
    if cod == 200:
        P._auditar(viewer, f"torneos · {acc}", None, pase, _detalle(acc, cuerpo))
    if P.rol_de(viewer) != "admin":
        r = _para_moderador(CO, P, r)
    elif not GE.puede_ver_ips(P, viewer):
        r = GE._sin_ips(r)
    return cod, r
