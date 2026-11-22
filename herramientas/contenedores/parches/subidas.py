# -*- coding: utf-8 -*-
"""subidas — los amigos SUBEN archivos del cliente al server de PRUEBA desde el launcher (16-nov-2026).

Eñeños: «que sólo los autorizados, tipo EDA, puedan subir directamente; que los otros tengan que ser aprobados, así
como las PR que abran otras personas, por ser público». (TOPOLOGIA_CONTENEDORES §36)

    · Cualquier cuenta con sesión sube archivos: quedan en un BORRADOR suyo, guardados por su md5.
    · Al ENVIAR, el borrador pasa a ser una PROPUESTA (#n, con su nota):
          - si quien envía es AUTORIZADO (Cuenta Eñeños le da el pase `r2beat2013-subir`, que se aprueba por cuenta
            como el de EDA) → se APLICA en el acto;
          - si no → queda PENDIENTE hasta que un autorizado la apruebe o la rechace.
    · APLICAR = una release de prueba NUEVA = la de prueba de ahora + esos archivos (enlaces duros: no ocupa), con su
      `manifest.json`, y el server de parches pasa a servir ésa en `/manifest?canal=prueba`. Nunca se reusa un
      nombre (la CDN guarda los archivos por el nombre de la release).

⛔ Lo que entra a la lista de prueba se INSTALA en la PC de todo el que marca «Servidor de prueba». Un .exe o una .dll
   de un desconocido puede ser un virus: por eso lo de afuera no entra sin aprobación, y los ejecutables se marcan.
⛔ Prod no se toca nunca desde acá: sólo la lista de PRUEBA.

Todo vive en `<releases>/_subidas/` (mismo disco que las releases, para los enlaces duros):
    blobs/<md5>        los archivos, una sola vez cada uno
    borradores.json    uid -> [{ruta, md5, tam}]
    propuestas.json    [{id, uid, quien, nota, archivos, estado, creada, revisor, release, ...}]
    estado.json        {"prueba", "prod", "historial": [{release, que, quien, cuando, propuesta?}]}  (★ §37)
    apagado            si EXISTE, nadie sube ni envía (el interruptor de emergencia; volver atrás sigue andando)

★ 16-nov (§37, Eñeños: «que si algo no gustó se pueda volver al estado anterior, hasta 5 atrás» y «pruebas de
  seguridad: un juez barato»): cada archivo pasa por `juez.py`; los PROGRAMAS nunca entran directo (dos llaves); el
  historial guarda la release vigente y las 5 anteriores, y `volver` deja vigente cualquiera de ellas.
"""
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time

try:
    import juez
except ImportError:                                   # (en la imagen va al lado)
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import juez

# ★ 16-nov (Eñeños): «límite por subida 500 MB, entre archivo o archivos»
TAM_MAX_BORRADOR = int(os.environ.get("PARCHES_SUBIDA_ENVIO_MAX_MB") or 500) * 1024 * 1024
TAM_MAX_ARCHIVO = TAM_MAX_BORRADOR
TAM_MAX_TOTAL = int(os.environ.get("PARCHES_SUBIDA_TOTAL_MAX_GB") or 5) * 1024 ** 3   # todo lo guardado en blobs/
ARCHIVOS_MAX_BORRADOR = 200
# ★ 16-nov (Eñeños): «sólo puede haber un máximo de 5; el que subió algo no puede tener 2 abiertos al mismo tiempo,
#   sí puede reemplazar lo que subió»: 5 pendientes EN TOTAL y 1 por cuenta (un envío nuevo reemplaza al suyo)
PENDIENTES_MAX_TOTAL = 5
INVITACIONES_PENDIENTES_MAX = 50                      # solicitudes de invitación esperando (que no se llene de pedidos)
PENDIENTES_MAX_POR_CUENTA = 1
SUBIDAS_MAX_POR_HORA = 400                            # archivos por cuenta (lo que cabe en dos envíos llenos)
HISTORIAL_MAX = 6                                     # la vigente + 5 para volver
DOS_LLAVES = (os.environ.get("PARCHES_SUBIDA_DOS_LLAVES") or "1") != "0"
EJECUTABLES = juez.SENSIBLES + juez.PROGRAMAS        # (para marcar en la lista; quien decide es el juez)
_RUTA_OK = re.compile(r"^[A-Za-z0-9_\- .()\[\]+@#&,'!=]+(/[A-Za-z0-9_\- .()\[\]+@#&,'!=]+)*$")
# Windows: estos nombres son DISPOSITIVOS en cualquier carpeta y con cualquier extensión («nul.pak» no es un archivo)
_RESERVADOS = {"con", "prn", "aux", "nul", "clock$", "conin$", "conout$"} | {f"{p}{n}" for p in ("com", "lpt")
                                                                            for n in "0123456789¹²³"}
_lock = threading.RLock()


class Error(Exception):
    """Un no con su motivo y su código HTTP."""

    def __init__(self, codigo, motivo):
        super().__init__(motivo)
        self.codigo, self.motivo = codigo, motivo


def ruta_valida(ruta):
    """La ruta dentro del cliente, normalizada (`a/b.pak`), o Error. Ni absoluta, ni `..`, ni el manifest.

    ★ §37, las trampas de Windows: un punto o espacio al FINAL se borra al guardar («x.dll.» se vuelve «x.dll», y el
    chequeo de extensión ya pasó); `con`/`nul`/`com1`… son dispositivos; `~` deja escribir con el nombre corto 8.3
    («R2BEAT~1.EXE» abre R2BeatMultiTest.exe). Las tres se niegan."""
    r = str(ruta or "").replace("\\", "/").strip()
    while "//" in r:
        r = r.replace("//", "/")
    partes = r.split("/")
    if (not r or len(r) > 200 or r.startswith("/") or ":" in r or any(p in ("", ".", "..") for p in partes)
            or not _RUTA_OK.match(r) or r.lower() == "manifest.json" or partes[0].startswith("_")
            or any(p.endswith((".", " ")) or p.startswith(" ") for p in partes)
            or any(p.split(".")[0].strip().lower() in _RESERVADOS for p in partes)):
        raise Error(400, f"Ruta no válida: {ruta!r}")
    return r


def es_ejecutable(ruta):
    return ruta.lower().endswith(EJECUTABLES)


def nombre_limpio(t, uid):
    """El nombre visible de quien sube: lo dice el PASE (Cuenta Eñeños), nunca el launcher. Sin caracteres raros."""
    t = "".join(c for c in str(t or "") if c.isprintable() and c not in "<>&\"'")[:40].strip()
    return t or f"cuenta {uid}"


class Subidas:
    def __init__(self, releases_dir, cfg):
        self.releases = releases_dir
        self.cfg = cfg                                   # el CFG del server de parches (current / current_prueba)
        self.dir = os.path.join(releases_dir, "_subidas")
        self.blobs = os.path.join(self.dir, "blobs")
        os.makedirs(self.blobs, exist_ok=True)
        self._ritmo = {}                                 # uid -> [instantes de subida] (la última hora)
        self._rutas_cache = (None, {})                   # (release, {ruta en minúsculas: ruta}) de la lista vigente

    # ── lo guardado ──────────────────────────────────────────────────────────────────────────────
    def _leer(self, nombre, defecto):
        try:
            with open(os.path.join(self.dir, nombre), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return defecto

    def _escribir(self, nombre, datos):
        p = os.path.join(self.dir, nombre)
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        os.replace(p + ".tmp", p)

    def apagado(self):
        """★ §37 el interruptor de emergencia: `touch <releases>/_subidas/apagado` (o PARCHES_SUBIDAS=apagado) y nadie
        sube ni envía más. Volver atrás sigue andando: es justo lo que se usa en una emergencia."""
        return (os.environ.get("PARCHES_SUBIDAS") or "").lower() == "apagado" \
            or os.path.exists(os.path.join(self.dir, "apagado"))

    def _base_config(self):
        return self.cfg.get("current_prueba") or self.cfg.get("current")

    def release_prueba(self):
        """La release de prueba vigente: la última aplicada (si se armó sobre la prod de hoy) o la de la config."""
        est = self._leer("estado.json", {})
        if est.get("prueba") and est.get("prod") == self.cfg.get("current") \
                and os.path.isfile(os.path.join(self.releases, est["prueba"], "manifest.json")):
            return est["prueba"]
        return self._base_config()

    def _rutas_vigentes(self):
        """{ruta en minúsculas: ruta tal cual} de la lista de prueba vigente (para no meter «pack/x.pak» al lado de
        «Pack/X.pak»: en Windows son EL MISMO archivo y el launcher los bajaría por turno, sin terminar nunca)."""
        rel = self.release_prueba()
        if self._rutas_cache[0] != rel:
            try:
                man = json.load(open(os.path.join(self.releases, rel, "manifest.json"), encoding="utf-8"))
                self._rutas_cache = (rel, {e["path"].lower(): e["path"] for e in man.get("files", [])})
            except (OSError, ValueError, TypeError):
                self._rutas_cache = (rel, {})
        return self._rutas_cache[1]

    def _guardado_total(self):
        try:
            return sum(e.stat().st_size for e in os.scandir(self.blobs) if e.is_file())
        except OSError:
            return 0

    # ── subir ────────────────────────────────────────────────────────────────────────────────────
    def recibir(self, uid, ruta, lector, largo, ahora=None):
        """Lee `largo` bytes de `lector` (el cuerpo del pedido), los pasa por el JUEZ, los guarda por su md5 y los
        suma al borrador."""
        if self.apagado():
            raise Error(503, "Las subidas están desactivadas temporalmente.")
        self._exigir_invitacion(uid)
        ruta = ruta_valida(ruta)
        ruta = self._rutas_vigentes().get(ruta.lower(), ruta)       # misma ruta que ya tiene la lista, mismas letras
        if largo <= 0:
            raise Error(400, "El archivo está vacío.")
        if largo > TAM_MAX_ARCHIVO:
            raise Error(413, f"El archivo supera el máximo de {TAM_MAX_ARCHIVO // 2**20} MB.")
        ahora = ahora or time.time()
        with _lock:
            r = [t for t in self._ritmo.get(uid, []) if t > ahora - 3600]
            if len(r) >= SUBIDAS_MAX_POR_HORA:
                raise Error(429, f"Se alcanzó el máximo de {SUBIDAS_MAX_POR_HORA} archivos por hora. Intentar más tarde.")
            r.append(ahora)
            self._ritmo[uid] = r
            b = self._leer("borradores.json", {}).get(str(uid), [])
            if sum(x["tam"] for x in b if x["ruta"] != ruta) + largo > TAM_MAX_BORRADOR:
                raise Error(413, f"El envío supera el máximo de {TAM_MAX_BORRADOR // 2**20} MB (entre todos sus archivos).")
            if len(b) >= ARCHIVOS_MAX_BORRADOR and all(x["ruta"] != ruta for x in b):
                raise Error(413, f"El envío supera el máximo de {ARCHIVOS_MAX_BORRADOR} archivos.")
            if self._guardado_total() + largo > TAM_MAX_TOTAL:
                self.limpiar()
                if self._guardado_total() + largo > TAM_MAX_TOTAL:
                    raise Error(507, "No queda espacio para subidas en el servidor de prueba. Contactar a un administrador.")
        h, quedan = hashlib.md5(), largo
        fd, tmp = tempfile.mkstemp(dir=self.blobs, prefix=".subiendo_")
        try:
            with os.fdopen(fd, "wb") as f:
                while quedan > 0:
                    trozo = lector.read(min(1 << 20, quedan))
                    if not trozo:
                        raise Error(400, "El archivo llegó incompleto.")
                    h.update(trozo)
                    f.write(trozo)
                    quedan -= len(trozo)
            try:
                veredicto = juez.juzgar(ruta, tmp, largo)       # ★ §37: ANTES de guardarlo
            except juez.Rechazo as e:
                raise Error(415, f"{ruta}: {e}")
            md5 = h.hexdigest()
            destino = os.path.join(self.blobs, md5)
            if os.path.isfile(destino):
                os.remove(tmp)
            else:
                os.replace(tmp, destino)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        entrada = {"ruta": ruta, "md5": md5, "tam": largo, "clase": veredicto["clase"],
                   "alertas": veredicto.get("alertas", [])}
        with _lock:
            todos = self._leer("borradores.json", {})
            b = [x for x in todos.get(str(uid), []) if x["ruta"] != ruta]
            b.append(entrada)
            todos[str(uid)] = b
            self._escribir("borradores.json", todos)
        return dict(entrada, ejecutable=veredicto["clase"] == "sensible", en_el_envio=len(b))

    def borrador(self, uid):
        return self._leer("borradores.json", {}).get(str(uid), [])

    def descartar(self, uid):
        with _lock:
            todos = self._leer("borradores.json", {})
            todos.pop(str(uid), None)
            self._escribir("borradores.json", todos)

    # ── enviar, revisar, aplicar ─────────────────────────────────────────────────────────────────
    def enviar(self, uid, quien, nota, autorizado, ahora=None):
        """El borrador pasa a propuesta. Autorizado y sin programas → se aplica ya. Si no → pendiente.
        `quien` lo pone el SERVER (el nombre del pase), nunca el launcher."""
        if self.apagado():
            raise Error(503, "Las subidas están desactivadas temporalmente.")
        if not autorizado:
            self._exigir_invitacion(uid)
        # ★ 16-nov (Eñeños): la descripción es OPCIONAL («breve descripción, si es que ponen»)
        nota = " ".join(str(nota or "").split())[:500]
        with _lock:
            arch = self.borrador(uid)
            if not arch:
                raise Error(400, "No hay archivos para enviar.")
            props = self._leer("propuestas.json", [])
            sensibles = [a["ruta"] for a in arch if a.get("clase") == "sensible" or es_ejecutable(a["ruta"])]
            dos_llaves = bool(sensibles) and DOS_LLAVES
            queda_pendiente = not autorizado or dos_llaves
            mias = [x for x in props if x["uid"] == uid and x["estado"] == "pendiente"]
            if queda_pendiente:
                otras = sum(1 for x in props if x["estado"] == "pendiente" and x["uid"] != uid)
                if otras + 1 > PENDIENTES_MAX_TOTAL:
                    raise Error(429, f"Ya hay {PENDIENTES_MAX_TOTAL} envíos pendientes de revisión. "
                                     "Intentar cuando se revisen.")
            p = {"id": max([x["id"] for x in props] or [0]) + 1, "uid": uid, "quien": nombre_limpio(quien, uid),
                 "nota": nota, "archivos": arch, "ejecutables": sensibles, "dos_llaves": dos_llaves,
                 "estado": "pendiente", "creada": int(ahora or time.time()), "revisor": None, "release": None}
            if queda_pendiente and mias:            # 1 por cuenta: el nuevo REEMPLAZA a los suyos que esperaban
                for x in mias:
                    x.update(estado="reemplazada", reemplazada_por=p["id"], revisada=int(ahora or time.time()))
                p["reemplaza"] = [x["id"] for x in mias]
            props.append(p)
            self._escribir("propuestas.json", props)
            todos = self._leer("borradores.json", {})
            todos.pop(str(uid), None)
            self._escribir("borradores.json", todos)
            if p.get("reemplaza"):
                self.limpiar()                       # (lo del envío reemplazado que ya nadie usa)
            if autorizado and not p["dos_llaves"]:
                return self._aplicar(p["id"], uid, ahora, sola=True, quien=p["quien"])
            return p

    def lista(self, uid, autorizado):
        """Lo que ve cada uno: sus propias propuestas y todas las pendientes."""
        props = self._leer("propuestas.json", [])
        # ★ 16-nov: los PENDIENTES los ve todo el mundo (cada uno puede probar cualquiera, como un PR público)
        return [p for p in props if p["uid"] == uid or p["estado"] == "pendiente"][-50:]

    # ── ★ 16-nov (Eñeños): «test server pueden entrar; subir archivos: solicitar invitación» ──────────
    #   Jugar y PROBAR envíos sigue abierto a todos; SUBIR, sólo con invitación. Las invitaciones se piden desde el
    #   launcher y las aprueba un AUTORIZADO (pase `r2beat2013-subir`), que queda invitado solo.
    #   invitaciones.json: uid -> {estado: pendiente|aprobada|rechazada|quitada, quien, nota, cuando, revisor}
    def invitado(self, uid):
        return self._leer("invitaciones.json", {}).get(str(uid), {}).get("estado") == "aprobada"

    def _exigir_invitacion(self, uid):
        if not self.invitado(uid):
            raise Error(403, "Subir archivos requiere invitación. Solicitarla desde el menú «Subir archivos».")

    def invitacion(self, uid):
        return self._leer("invitaciones.json", {}).get(str(uid))

    def marcar_autorizado(self, uid, quien, ahora=None):
        """Un autorizado queda invitado solo (se anota la primera vez que muestra su pase)."""
        with _lock:
            todas = self._leer("invitaciones.json", {})
            if todas.get(str(uid), {}).get("estado") != "aprobada":
                todas[str(uid)] = {"estado": "aprobada", "quien": nombre_limpio(quien, uid), "nota": "cuenta autorizada",
                                   "cuando": int(ahora or time.time()), "revisor": "autorizado"}
                self._escribir("invitaciones.json", todas)

    def solicitar_invitacion(self, uid, quien, nota, ahora=None):
        nota = " ".join(str(nota or "").split())[:300]
        with _lock:
            todas = self._leer("invitaciones.json", {})
            ya = todas.get(str(uid), {})
            if ya.get("estado") == "aprobada":
                raise Error(409, "La cuenta ya tiene invitación para subir archivos.")
            if sum(1 for x in todas.values() if x.get("estado") == "pendiente") >= INVITACIONES_PENDIENTES_MAX \
                    and ya.get("estado") != "pendiente":
                raise Error(429, "Hay demasiadas solicitudes pendientes. Intentar más tarde.")
            todas[str(uid)] = {"estado": "pendiente", "quien": nombre_limpio(quien, uid), "nota": nota,
                               "cuando": int(ahora or time.time()), "revisor": None}
            self._escribir("invitaciones.json", todas)
            return dict(todas[str(uid)], uid=uid)

    def revisar_invitacion(self, uid_obj, accion, revisor, ahora=None):
        """Sólo AUTORIZADOS (lo comprueba quien llama): aprobar / rechazar una solicitud, o quitar una invitación."""
        if accion not in ("aprobar", "rechazar", "quitar"):
            raise Error(400, "Acción no válida: aprobar, rechazar o quitar.")
        with _lock:
            todas = self._leer("invitaciones.json", {})
            x = todas.get(str(uid_obj))
            if not x:
                raise Error(404, "Esa cuenta no tiene solicitud ni invitación.")
            if accion in ("aprobar", "rechazar") and x.get("estado") != "pendiente":
                raise Error(409, f"La solicitud ya fue procesada ({x.get('estado')}).")
            if accion == "quitar" and x.get("estado") != "aprobada":
                raise Error(409, "Esa cuenta no tiene invitación.")
            x.update(estado={"aprobar": "aprobada", "rechazar": "rechazada", "quitar": "quitada"}[accion],
                     revisor=revisor, revisada=int(ahora or time.time()))
            self._escribir("invitaciones.json", todas)
            return dict(x, uid=int(uid_obj))

    def invitaciones(self):
        """Para los autorizados: las solicitudes pendientes y las cuentas invitadas."""
        return [dict(v, uid=int(k)) for k, v in self._leer("invitaciones.json", {}).items()
                if v.get("estado") in ("pendiente", "aprobada")]

    def pendientes(self):
        return sum(1 for p in self._leer("propuestas.json", []) if p["estado"] == "pendiente")

    def revisar(self, id_, accion, revisor, ahora=None, quien=None):
        """Sólo para AUTORIZADOS (lo comprueba quien llama): aprobar (= aplicar) o rechazar una pendiente.
        ★ §37 dos llaves: un envío con PROGRAMAS no lo aprueba quien lo subió."""
        with _lock:
            props = self._leer("propuestas.json", [])
            p = next((x for x in props if x["id"] == id_), None)
            if not p:
                raise Error(404, f"El envío #{id_} no existe.")
            if p["estado"] != "pendiente":
                raise Error(409, f"El envío #{id_} ya fue procesado ({p['estado']}).")
            if accion == "rechazar":
                p.update(estado="rechazada", revisor=revisor, revisada=int(ahora or time.time()))
                self._escribir("propuestas.json", props)
                self.limpiar()
                return p
            if accion == "habilitar":
                # ★ 16-nov: HABILITAR los programas de una modificación = que los DEMÁS la puedan probar (sigue
                #   pendiente: no cambia la lista de nadie). Dos llaves: no lo hace quien la subió.
                if not p.get("ejecutables"):
                    raise Error(400, "El envío no contiene programas.")
                if p["uid"] == revisor:
                    raise Error(403, "Los programas los habilita otra cuenta autorizada, no quien los subió.")
                p.update(programas_ok=revisor, programas_ok_cuando=int(ahora or time.time()))
                self._escribir("propuestas.json", props)
                return p
            if accion != "aprobar":
                raise Error(400, "Acción no válida: aprobar, rechazar o habilitar.")
            if p.get("dos_llaves") and p["uid"] == revisor:
                raise Error(403, "El envío contiene programas o configuración: requiere la aprobación de otra cuenta autorizada.")
            return self._aplicar(id_, revisor, ahora, quien=quien)

    # ── el historial: la vigente + 5 para volver ─────────────────────────────────────────────────
    def _historial(self, est=None):
        """El historial vigente (más viejo primero). Si prod cambió desde que se armó, arranca de nuevo con la base."""
        est = self._leer("estado.json", {}) if est is None else est
        h = est.get("historial") if est.get("prod") == self.cfg.get("current") else None
        if not h:
            h = [{"release": self._base_config(), "que": "la lista de prueba de base", "quien": "", "cuando": 0}]
            antes = est.get("prueba") if est.get("prod") == self.cfg.get("current") else None
            if antes and antes != h[0]["release"]:          # (lo aplicado antes de que existiera el historial)
                h.append({"release": antes, "que": "lo subido antes del historial", "quien": "", "cuando": 0})
        return h

    def _anotar(self, release, que, quien, ahora, **extra):
        est = self._leer("estado.json", {})
        # ★ 16-nov (captura de Eñeños: tres «Versión actual» y «volver a: volver a:…»): cada versión UNA vez en el
        #   historial; restaurar una la sube arriba (no agrega otra copia)
        h = [x for x in self._historial(est) if x["release"] != release]
        h = h + [dict({"release": release, "que": que[:160], "quien": quien or "", "cuando": int(ahora or time.time())},
                      **extra)]
        h = h[-HISTORIAL_MAX:]
        self._escribir("estado.json", {"prueba": release, "prod": self.cfg.get("current"), "historial": h,
                                       "desde": est.get("prueba"), "propuesta": extra.get("propuesta")})

    def estados(self):
        """El historial para mostrar: el más nuevo primero, con cuál es el vigente. Se puede volver a cualquiera."""
        vig, vistos, out = self.release_prueba(), set(), []
        for e in reversed(self._historial()):
            if e["release"] in vistos:                 # (historiales viejos con la misma versión repetida)
                continue
            vistos.add(e["release"])
            out.append(dict(e, vigente=e["release"] == vig,
                            existe=os.path.isfile(os.path.join(self.releases, e["release"], "manifest.json"))))
        return out

    def volver(self, release, revisor, quien=None, ahora=None):
        """★ §37 deja vigente una release del historial (la lista de prueba vuelve a como estaba). No borra nada:
        es un estado más, así que también se puede deshacer."""
        with _lock:
            h = self._historial()
            e = next((x for x in reversed(h) if x["release"] == release), None)
            if not e:
                raise Error(404, "Esa versión no está en el historial (se guardan la actual y 5 anteriores).")
            if release == self.release_prueba():
                raise Error(409, "Esa ya es la versión actual.")
            if not os.path.isfile(os.path.join(self.releases, release, "manifest.json")):
                raise Error(410, "Esa versión ya no está disponible.")
            antes = self.release_prueba()
            que = e["que"]
            while que.startswith("volver a: "):        # (los anotados antes del arreglo)
                que = que[len("volver a: "):]
            self._anotar(release, que, nombre_limpio(quien, revisor), ahora, volvio_de=antes, revisor=revisor,
                         restaurada=True, propuesta=e.get("propuesta"))
            # las propuestas que ya no están en la lista vigente quedan marcadas (siguen en la lista de envíos)
            props = self._leer("propuestas.json", [])
            despues = {x.get("propuesta") for x in h[h.index(e) + 1:] if x.get("propuesta")}
            for p in props:
                if p["id"] in despues and p["estado"] == "aplicada":
                    p["revertida"] = int(ahora or time.time())
            self._escribir("propuestas.json", props)
            return {"release": release, "antes": antes, "estados": self.estados()}

    def limpiar(self):
        """Borra lo que ya nadie usa: blobs de envíos rechazados/cancelados/reemplazados, releases de subidas que
        salieron del historial y las VISTAS PREVIAS de envíos que ya no esperan (o armadas sobre otra base).
        Nunca toca la base de la config ni nada del historial (y las releases son enlaces duros: no se rompe nada)."""
        with _lock:
            props = self._leer("propuestas.json", [])
            en_hist = {e["release"] for e in self._historial()} | {self.cfg.get("current"), self._base_config()}
            usados = {a["md5"] for b in self._leer("borradores.json", {}).values() for a in b}
            usados |= {a["md5"] for p in props if p["estado"] == "pendiente" or p.get("release") in en_hist
                       for a in p["archivos"]}
            for e in os.scandir(self.blobs):
                if e.is_file() and not e.name.startswith(".") and e.name not in usados:
                    try:
                        os.remove(e.path)
                    except OSError:
                        pass
            for p in props:
                rel = p.get("release")
                if rel and rel not in en_hist and re.fullmatch(r"[\w.\-]+-p\d+b*", rel):
                    shutil.rmtree(os.path.join(self.releases, rel), ignore_errors=True)
            pend = {p["id"] for p in props if p["estado"] == "pendiente"}
            vig = self.release_prueba()
            for e in os.scandir(self.releases):
                m = re.fullmatch(r"(.+)-v(\d+)", e.name)
                if m and e.is_dir() and (int(m.group(2)) not in pend or m.group(1) != vig):
                    shutil.rmtree(e.path, ignore_errors=True)

    def _armar(self, base, archivos, nueva):
        """Una release NUEVA = `base` + `archivos` (enlaces duros: no ocupa). Devuelve su manifest."""
        dir_base = os.path.join(self.releases, base)
        man = json.load(open(os.path.join(dir_base, "manifest.json"), encoding="utf-8"))
        dir_nueva = os.path.join(self.releases, nueva)
        tmp = dir_nueva + ".armando"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            for raiz, _ds, nombres in os.walk(dir_base):
                for n in nombres:
                    src = os.path.join(raiz, n)
                    rel = os.path.relpath(src, dir_base)
                    if rel == "manifest.json":
                        continue
                    dst = os.path.join(tmp, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    os.link(src, dst)
            por_ruta = {e["path"]: e for e in man["files"]}
            for a in archivos:
                dst = os.path.join(tmp, *a["ruta"].split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.lexists(dst):
                    os.remove(dst)                    # ⛔ borrar el enlace, NUNCA escribir encima (es de la base)
                os.link(os.path.join(self.blobs, a["md5"]), dst)
                por_ruta[a["ruta"]] = {"path": a["ruta"], "md5": a["md5"], "size": a["tam"]}
            man["files"] = sorted(por_ruta.values(), key=lambda e: e["path"].lower())
            man.update(version=nueva, generated=time.strftime("%Y-%m-%dT%H:%M:%S"), file_count=len(man["files"]),
                       total_size=sum(e["size"] for e in man["files"]))
            man.pop("base", None)
            man.pop("canal", None)
            with open(os.path.join(tmp, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(man, f)
            os.replace(tmp, dir_nueva)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return man

    def _aplicar(self, id_, revisor, ahora=None, sola=False, quien=None):
        """Arma la release de prueba NUEVA con los archivos de la propuesta y la deja vigente."""
        with _lock:
            props = self._leer("propuestas.json", [])
            p = next(x for x in props if x["id"] == id_)
            nueva = f"{self.cfg.get('current')}-p{id_}"
            while os.path.exists(os.path.join(self.releases, nueva)):     # nunca se reusa un nombre
                nueva += "b"
            self._armar(self.release_prueba(), p["archivos"], nueva)
            self._anotar(nueva, f"#{id_} {p['nota']}", p.get("quien"), ahora, propuesta=id_,
                         revisor=nombre_limpio(quien, revisor) if not sola else None)
            p.update(estado="aplicada", revisor=revisor, revisada=int(ahora or time.time()), release=nueva,
                     directa=sola)
            self._escribir("propuestas.json", props)
            self.limpiar()
            return p

    # ── ★ 16-nov (Eñeños): cada uno PRUEBA cualquiera de los pendientes y maneja SÓLO el suyo ─────────
    #   «el que envió puede ejecutar su modificación o la de otro, rotar lanzamiento/descarga entre los 5 que hay,
    #    pero no puede editar/borrar/cancelar el de otro; sí puede borrar/editar el de él mismo».
    def release_de_envio(self, id_, uid):
        """La VISTA PREVIA de un envío pendiente: la lista de prueba vigente + sus archivos, en una release aparte
        (`<vigente>-v<id>`) que no cambia la de nadie. ⛔ Un envío con PROGRAMAS sin aprobar sólo lo prueba quien lo
        subió: instalarle a otro una dll que nadie revisó es justo lo que las dos llaves evitan."""
        with _lock:
            p = next((x for x in self._leer("propuestas.json", []) if x["id"] == id_), None)
            if not p or p["estado"] != "pendiente":
                raise Error(404, f"El envío #{id_} ya no está pendiente.")
            if p.get("ejecutables") and p["uid"] != uid and not p.get("programas_ok"):
                raise Error(403, f"El envío #{id_} contiene programas o configuración: hasta que se apruebe, "
                                 "solo puede probarlo quien lo subió.")
            base = self.release_prueba()
            nombre = f"{base}-v{id_}"
            if not os.path.isfile(os.path.join(self.releases, nombre, "manifest.json")):
                self._armar(base, p["archivos"], nombre)
            return nombre

    def _mio_pendiente(self, props, id_, uid):
        p = next((x for x in props if x["id"] == id_), None)
        if not p:
            raise Error(404, f"El envío #{id_} no existe.")
        if p["uid"] != uid:
            raise Error(403, "Solo quien subió el envío puede editarlo o cancelarlo.")
        if p["estado"] != "pendiente":
            raise Error(409, f"El envío #{id_} ya fue procesado ({p['estado']}).")
        return p

    def cancelar(self, id_, uid, ahora=None):
        """Quien lo subió retira SU envío pendiente (el de otro, no)."""
        with _lock:
            props = self._leer("propuestas.json", [])
            p = self._mio_pendiente(props, id_, uid)
            p.update(estado="cancelada", revisada=int(ahora or time.time()))
            self._escribir("propuestas.json", props)
            self.limpiar()
            return p

    def editar(self, id_, uid, nota):
        """Quien lo subió corrige la descripción de SU envío pendiente (los archivos se cambian mandando otro envío,
        que lo reemplaza)."""
        nota = " ".join(str(nota or "").split())[:500]
        with _lock:
            props = self._leer("propuestas.json", [])
            p = self._mio_pendiente(props, id_, uid)
            p["nota"] = nota
            self._escribir("propuestas.json", props)
            return p
