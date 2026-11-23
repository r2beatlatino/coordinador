# -*- coding: utf-8 -*-
"""portero — las cuentas de R2Beat para los OTROS juegos (EDA, …). 11-nov-2026, NO en prod.

QUÉ ES
------
Eñeños: *«una capa arriba de ambos juegos para los accountid»* · *«sin reiniciar el server de r2beat»* · *«solo las
cuentas aprobadas tendrán acceso a eda por ahora»*.

La cuenta ES la de R2Beat (`users.uid` de `datos.db`): no se crean cuentas nuevas ni se muda a nadie. El portero
revisa usuario y clave contra esa tabla y, si la cuenta está APROBADA para el juego, le da un PASE firmado (Ed25519)
que el otro juego comprueba SOLO, con la clave pública, sin preguntarle nada a Chile.

    launcher ──POST /entrar {usuario, clave}──────────▶ portero  → {sesion, uid, juegos}
    launcher ──POST /pase {juego} + Bearer sesion─────▶ portero  → {pase}        (sólo si está aprobada)
    launcher ──el pase──▶ server de EDA (USA): comprueba la firma, aud, exp y jti, y da su ticket corto

POR QUÉ UN PROCESO APARTE (y no una ruta más de `api_web`)
---------------------------------------------------------
⛔ El server de R2Beat no se reinicia sin preguntar, y sus sesiones web viven en memoria: si EDA dependiera de él,
   cada subida de R2Beat sacaría a los de EDA. El portero:
   · corre SOLO (`python -m servidor.portero`), con su servicio, y se reinicia sin tocar el juego;
   · ⛔ NO ESCRIBE `datos.db`: la abre de SÓLO LECTURA (`mode=ro` + `query_only`). La prueba lo comprueba por md5;
   · guarda lo suyo en `portero.db` (aprobados, baneos por juego, sesiones, pases emitidos) y la clave privada en
     `portero_clave.json`. Los dos al lado de `datos.db`, gitignorados.

LAS RUTAS (con o sin el prefijo `/cuentas`, para que Caddy pueda pasarlas como quiera)
-------------------------------------------------------------------------------------
    GET  /salud                          {"ok": true}
    GET  /clave-publica                  JWKS: la clave pública (la baja el server de EDA una vez)
    POST /entrar {usuario, clave}        -> {sesion, uid, vence, juegos: [{id, nombre, permitido}]}
         (o {usuario, pass_sha256_upper}: el launcher ya calcula el hash, así la clave no viaja ni dentro del HTTPS)
    POST /pase {juego}     + Bearer      -> {pase, vence}            403 si no está aprobada o está baneada
    GET  /yo               + Bearer      -> {uid, juegos}
    GET  /juego/<jid>/personajes?entorno=live|test + Bearer -> {ok, personajes, maximo}
    GET  /manifiesto/<juego> + Bearer    -> el manifest del cliente {version, base, files[path,size,md5]}
         ★ Eñeños (11-nov): «solo las aprobadas podrán descargar / jugar». Sin aprobación no hay manifest, o sea que el
         launcher no sabe QUÉ bajar ni DE DÓNDE: la `base` lleva un tramo secreto (`/files-eda/<release>-<azar>/`).
         ⚠ Es una puerta en la LISTA, no en cada archivo: el que ya tiene la `base` (un aprobado que la pasa) baja
         igual de la CDN. Cerrar cada archivo pide servirlos sin caché o un token de Cloudflare: se decide aparte.
         Para JUGAR la puerta sí es completa: sin pase firmado, el server del juego no deja entrar.
    POST /salir            + Bearer
⛔ Todo POST pide `X-R2: 1` (como `api_web`: un formulario de otro sitio no puede mandarla).
⛔ El mismo mensaje para «no existe» y «clave mala». Freno: 8 fallos por IP y por usuario en 15 minutos.

EL PASE — el contrato con los otros juegos
------------------------------------------
JWT compacto, EdDSA (RFC 8037):
    header  {"alg": "EdDSA", "typ": "JWT", "kid": "<16 hex>"}
    payload {"iss": "r2beat-portero", "aud": "<juego>", "sub": "<uid>", "iat": s, "exp": iat+300, "jti": "<único>"}
El que lo recibe comprueba la firma, `alg`, `iss`, `aud` = su juego, `exp`, y que el `jti` no lo haya visto antes.
⛔ No lleva el nombre de login (es privado: la web nunca lo muestra). La identidad es `sub`, el uid de R2Beat.

LA LISTA DE APROBADOS — se maneja desde la consola del VPS (el panel, más adelante)
-----------------------------------------------------------------------------------
    python -m servidor.portero aprobar <usuario> [juego]      (juego por omisión: eda)
    python -m servidor.portero quitar <usuario> [juego]
    python -m servidor.portero banear <usuario> [juego] [--horas N | --dias N | --meses N] [motivo…]   (sin tiempo: permanente)
    python -m servidor.portero desbanear <usuario> [juego]    (antes de tiempo; el baneo vencido ya no cuenta solo)
    python -m servidor.portero lista [juego]
    python -m servidor.portero clave                          imprime la clave PÚBLICA (JWKS)
    python -m servidor.portero pase <usuario> [juego] [seg]   ★ SÓLO PRUEBAS: un pase real (≤ 1 h) de una cuenta aprobada
    -- ★ 15-nov (con R2_CUENTAS_DUENA=1: Cuenta Eñeños dueña de las cuentas) --
    python -m servidor.portero importar <ruta a datos.db>     copia las cuentas a cuentas.db (idempotente, sólo lectura)
    python -m servidor.portero importar-amigos <datos.db> [--apodos]  ★ los amigos del R2Beat viejo, por Eñeños ID
    python -m servidor.portero traduccion [archivo]          exporta el mapa uid_viejo,enenos_id en CSV (sin usuarios ni claves)
    python -m servidor.portero cambiar-clave <usuario> <nueva> pone una contraseña nueva a la cuenta en cuentas.db
    python -m servidor.portero banear <usuario> [motivo…]     suspende la cuenta en cuentas.db (o banear-cuenta)
    python -m servidor.portero desbanear <usuario>            reactiva la cuenta en cuentas.db (o desbanear-cuenta)
★ 12-nov: también hay PANEL web (`/cuentas/admin`, y por proxy `eñeños.link/admin`), sólo para los ADMIN de admin.txt.
★ 19-nov: y el PANEL DEL COORDINADOR (`/coordinador/…`, servidor/coordinador.py): se entra con Discord/Google vinculado
  a un Eñeños ID con rol; en `moderadores.txt` cada moderador puede llevar sus juegos (`uid eda,gunbound`).
  Ver documentacion/PANEL_COORDINADOR.md.
Un ban de R2Beat (`BANNED:` en el hash) o una cuenta fusionada (`FUSIONADA:`) tampoco recibe pases.

VARIABLES
---------
    R2_BASE              la base del juego (por omisión: `datos.db` al lado de `servidor/`)
    R2_PORTERO_BASE      su base            (por omisión: `portero.db`, al lado)
    R2_PORTERO_CLAVE     su clave privada   (por omisión: `portero_clave.json`, al lado)  ⛔ no se copia ni se imprime
    R2_PORTERO_PUERTO    48195; escucha SÓLO en 127.0.0.1 (afuera se llega por Caddy)
    R2_PORTERO_HOST      ★ 14-nov: dónde escucha (por omisión 127.0.0.1). En un contenedor: 0.0.0.0, y el puerto se
                         publica SÓLO hacia el proxy (nunca a internet: no hay HTTPS acá adentro)
    R2_PORTERO_PROXIES   ★ 14-nov: a quién se le cree la IP del jugador (`CF-Connecting-IP` / `X-Forwarded-For`):
                         IPs o redes separadas por coma. Por omisión `127.0.0.1,::1`
    R2_PORTERO_MANIFIESTOS  la carpeta con `<juego>.json` (el manifest de cada cliente). Sin ella: 503 «todavía no
                         hay cliente publicado». Se lee del disco en cada pedido (cambiarlo no pide reiniciar).
    R2_BANEO_TOPE_MODERADOR_DIAS  ★ 20-nov: lo más largo que banea un MODERADOR, en días (de fábrica 365 = 12 meses;
                         1..3650). Permanente y toda la red: sólo un ADMIN.
    R2_CUENTAS_DUENA     ★ 15-nov: `1` = Cuenta Eñeños es la DUEÑA de las cuentas (`cuentas.db`, nunca abre `datos.db`).
                         Sin esta variable (o != `1`), se comporta exactamente como antes.
    R2_CUENTAS_BASE      ruta a `cuentas.db` (por omisión: en la misma carpeta donde vive `portero.db`)
    R2_CUENTAS_UID_DESDE desde qué uid se numeran las cuentas NUEVAS (por omisión `UID_NUEVAS_DESDE` = 10.000.000)
    R2_CUENTAS_FICHA_INTERNA  ficha compartida para el pedido interno `GET /cuentas/interno/cuenta/<uid>` ->
                         `{uid, usuario, estado}` (sin esta variable, ese pedido no existe)
"""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import firma_ed25519 as ed
from . import vinculos as V          # ★ 16-nov: entrar / registrarse / vincular con Google y Discord
from . import social as SO           # ★ 16-nov: amigos, estado y chat de la plataforma
from . import lanzamientos as LZ     # ★ 18-nov: cuándo se abre cada juego + invitaciones anticipadas (Discord)
from . import coordinador as CO      # ★ 19-nov: el panel del Coordinador Eñeños (fase A: entrar, juegos, la red)
from . import gestion as GE

# ⚠ Este módulo NO se disfraza el `__file__` (ver CLAUDE.md §2): `RAIZ` es de verdad la carpeta de arriba de `servidor/`.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ★ 14-nov (contenedores, TOPOLOGIA_CONTENEDORES.md): dónde escucha y a quién le cree la IP del jugador. Sin las
#   variables queda IGUAL que siempre (127.0.0.1, y sólo Caddy en la misma máquina es «el proxy»).
#   ⛔ Dentro de un contenedor el proxy NO llega desde 127.0.0.1 sino desde la red de Docker: sin `R2_PORTERO_PROXIES`
#     todos los jugadores tendrían «la misma IP» (la del proxy) y el freno de 8 fallos los frenaría a TODOS juntos.
HOST = os.environ.get("R2_PORTERO_HOST") or "127.0.0.1"
PUERTO = int(os.environ.get("R2_PORTERO_PUERTO") or 48195)


def _redes(txt):
    """«127.0.0.1, 172.16.0.0/12» -> lista de redes. Lo que no se entiende se IGNORA (no se le cree a nadie de más)."""
    redes = []
    for t in str(txt or "").replace(";", ",").split(","):
        try:
            redes.append(ipaddress.ip_network(t.strip(), strict=False))
        except ValueError:
            pass
    return redes


PROXIES = _redes(os.environ.get("R2_PORTERO_PROXIES") or "127.0.0.1,::1")


def es_proxy(ip, redes=None):
    """¿Ese vecino es NUESTRO proxy (Caddy)? Sólo a él se le cree `CF-Connecting-IP` / `X-Forwarded-For`."""
    try:
        d = ipaddress.ip_address(str(ip).split("%")[0])
    except ValueError:
        return False
    if getattr(d, "ipv4_mapped", None):
        d = d.ipv4_mapped
    return any(d.version == r.version and d in r for r in (PROXIES if redes is None else redes))

# Los juegos que el portero conoce. `abierto`: False = sólo las cuentas APROBADAS (Eñeños, 11-nov: así arranca EDA).
# ★ 15-nov (R2_CUENTAS_DUENA=1): cuando Cuenta Eñeños es la dueña, también da pases para `r2beat2013`, `parches` y `web`
#   (abiertos a toda cuenta activa). Sin el interruptor queda sólo `eda`, igual que antes.
JUEGOS = {
    "eda": {"nombre": "Espada del Alma", "abierto": False},
}
JUEGOS_DUENA = {
    "eda": {"nombre": "Espada del Alma", "abierto": False},
    # ★ 21-nov: el server de PRUEBA de EDA (develop → eda-prueba) con su pase propio, como GunBound. Lo cierra el mismo
    #   lanzamiento que a `eda` (lanzamientos.py): antes de la fecha, admins, moderadores y aprobados; después, todos.
    "eda-prueba": {"nombre": "Espada del Alma (servidor de prueba)", "abierto": False},
    "r2beat2013": {"nombre": "R2Beat 2013", "abierto": True},
    # ★ 15-nov (dos servers por juego): el server de PRUEBA es «otro juego» para el pase (aud propio). Abierto a
    #   toda cuenta activa, como prod: cualquiera puede marcar «Servidor de prueba» en el launcher.
    "r2beat2013-prueba": {"nombre": "R2Beat 2013 (servidor de prueba)", "abierto": True},
    # ★ 16-nov: SUBIR archivos del cliente al server de prueba DIRECTO (sin esperar aprobación). Cerrado, como EDA: se
    #   aprueba por cuenta (`portero aprobar <usuario> r2beat2013-subir`). Los demás también suben, pero lo suyo espera.
    "r2beat2013-subir": {"nombre": "R2Beat 2013 · subir al servidor de prueba", "abierto": False},
    # ★ 16-nov: GunBound (repo propio, D:\Gunbound\gunbound-servidor). Mismo contrato que EDA: el pase se canjea
    #   en POST /gunbound/canje por un boleto. Abierto a toda cuenta activa, prod y prueba.
    #   (18-nov: aplicado a mano el `integracion/cuenta_enenos_gunbound.patch` de ese repo — la rama avanzó)
    "gunbound": {"nombre": "GunBound", "abierto": True},
    "gunbound-prueba": {"nombre": "GunBound (servidor de prueba)", "abierto": True},
    # ★ 18-nov: Eñeñosbit 2027 (el R2Beat moderno), ALPHA. Cerrado hasta su fecha (lanzamientos.py), salvo aprobados
    "r2beat-moderno": {"nombre": "Eñeñosbit 2027", "abierto": True},
    "parches": {"nombre": "Servidor de parches", "abierto": True},
    "web": {"nombre": "Web", "abierto": True},
}
EMISOR = "r2beat-portero"
JUEGOS_CON_LOGIN = ("parches", "r2beat2013-subir")   # ★ 16-nov: los pases que llevan el login como nombre visible
SESION_DIAS = 30
PASE_SEGUNDOS = 300
INTENTOS_MAX = 8
INTENTOS_VENTANA = 15 * 60
CUERPO_MAX = 4096
CUERPO_PAGINA_MAX = 512 << 10   # historial completo (10 versiones); admite JSON con Unicode escapado

# ★ 15-nov (Cuenta Eñeños dueña de las cuentas):
#   · las cuentas NUEVAS arrancan desde un número alto para no chocar con los `usn` de los personajes 2-4 de R2Beat;
#   · en `cuentas.db` el SHA-256 en hex mayúscula se guarda ENVUELTO en `hashlib.scrypt` con una sal aleatoria por cuenta.
UID_NUEVAS_DESDE = int(os.environ.get("R2_CUENTAS_UID_DESDE") or os.environ.get("R2_UID_NUEVAS_DESDE") or 10_000_000)
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LARGO = 32
SCRYPT_SAL_BYTES = 16
_HEX_MAYUS = frozenset("0123456789ABCDEF")
_HASH_VACIO = hashlib.sha256(b"").hexdigest().upper()


def es_duena():
    """¿Cuenta Eñeños es la dueña de las cuentas (`R2_CUENTAS_DUENA=1`)? Sin eso, lee `datos.db` como siempre."""
    return os.environ.get("R2_CUENTAS_DUENA") == "1"


def _juegos():
    return JUEGOS_DUENA if es_duena() else JUEGOS


def _uid_nuevas_desde():
    v = os.environ.get("R2_CUENTAS_UID_DESDE") or os.environ.get("R2_UID_NUEVAS_DESDE")
    return int(v) if v else int(UID_NUEVAS_DESDE)


def ruta_base_juego():
    return os.environ.get("R2_BASE") or os.path.join(RAIZ, "datos.db")


def ruta_base_portero():
    return os.environ.get("R2_PORTERO_BASE") or os.path.join(RAIZ, "portero.db")


def ruta_base_cuentas():
    if os.environ.get("R2_CUENTAS_BASE"):
        return os.environ["R2_CUENTAS_BASE"]
    return os.path.join(os.path.dirname(os.path.abspath(ruta_base_portero())), "cuentas.db")


def ruta_clave():
    return os.environ.get("R2_PORTERO_CLAVE") or os.path.join(RAIZ, "portero_clave.json")


def ficha_interna():
    return (os.environ.get("R2_CUENTAS_FICHA_INTERNA") or "").strip()


def _log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "[PORTERO]", msg, flush=True)


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  Las bases: la del JUEGO (sólo lectura, cuando no es dueña), la propia (`portero.db`) y `cuentas.db`
# ══════════════════════════════════════════════════════════════════════════════════════════════
_hilo = threading.local()
_escribir = threading.Lock()


def _juego():
    """La conexión del hilo a `datos.db`, de SÓLO LECTURA. ⛔ Nunca se escribe ahí, ni se abre con R2_CUENTAS_DUENA=1."""
    if es_duena():
        raise RuntimeError("⛔ con R2_CUENTAS_DUENA=1 no se abre datos.db")
    ruta = os.path.abspath(ruta_base_juego())
    c = getattr(_hilo, "juego", None)
    if c is None or getattr(_hilo, "juego_ruta", None) != ruta:
        if c is not None:
            c.close()
        url = "file:" + urllib.request.pathname2url(ruta) + "?mode=ro"
        c = sqlite3.connect(url, uri=True, timeout=5, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA query_only = 1")
        _hilo.juego, _hilo.juego_ruta = c, ruta
    return c


ESQUEMA = """
CREATE TABLE IF NOT EXISTS aprobados (uid INTEGER NOT NULL, juego TEXT NOT NULL, desde TEXT, quien TEXT, nota TEXT,
                                      PRIMARY KEY (uid, juego));
CREATE TABLE IF NOT EXISTS baneos    (uid INTEGER NOT NULL, juego TEXT NOT NULL, desde TEXT, quien TEXT, motivo TEXT,
                                      hasta INTEGER, PRIMARY KEY (uid, juego));
CREATE TABLE IF NOT EXISTS sesiones  (huella TEXT PRIMARY KEY, uid INTEGER NOT NULL, creada INTEGER, vence INTEGER,
                                      ip TEXT);
CREATE TABLE IF NOT EXISTS pases     (jti TEXT PRIMARY KEY, uid INTEGER, juego TEXT, emitido INTEGER, ip TEXT);
CREATE TABLE IF NOT EXISTS sesiones_admin (huella TEXT PRIMARY KEY, uid INTEGER NOT NULL, creada INTEGER, vence INTEGER,
                                      ip TEXT);
CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, cuando TEXT, quien TEXT, accion TEXT,
                                      uid INTEGER, juego TEXT, detalle TEXT);
CREATE TABLE IF NOT EXISTS traducciones_uid (uid_viejo INTEGER PRIMARY KEY, uid_nuevo INTEGER NOT NULL);
"""

# ★ `cuentas.uid` ES el Eñeños ID de la persona: un entero secuencial desde `UID_NUEVAS_DESDE` (10.000.000),
#   inmutable para toda la vida e independiente del `users.uid` (personaje / casillero 1) que tenga cada juego.
ESQUEMA_CUENTAS = """
CREATE TABLE IF NOT EXISTS cuentas (
    uid     INTEGER PRIMARY KEY,
    usuario TEXT UNIQUE NOT NULL COLLATE BINARY,
    clave   TEXT NOT NULL,
    estado  TEXT NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'baneada', 'fusionada')),
    creada  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS importadas (
    uid_viejo INTEGER PRIMARY KEY,
    uid       INTEGER NOT NULL,
    usuario   TEXT NOT NULL COLLATE BINARY
);
CREATE INDEX IF NOT EXISTS importadas_uid ON importadas (uid);
"""


def _propia():
    ruta = os.path.abspath(ruta_base_portero())
    c = getattr(_hilo, "propia", None)
    if c is None or getattr(_hilo, "propia_ruta", None) != ruta:
        if c is not None:
            c.close()
        c = sqlite3.connect(ruta, timeout=5, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(ESQUEMA)
        _migrar_baneos(c)
        c.executescript(LZ.ESQUEMA)
        c.executescript(CO.ESQUEMA)
        _hilo.propia, _hilo.propia_ruta = c, ruta
    return c


def _migrar_baneos(c):
    """★ 20-nov: la columna `hasta` (epoch; NULL = permanente) en una `portero.db` de antes. Los baneos viejos quedan
    con `hasta` NULL, o sea PERMANENTES, como eran. Idempotente (dos hilos a la vez: el 2.º ve «duplicate column»)."""
    if "hasta" in {r[1] for r in c.execute("PRAGMA table_info(baneos)")}:
        return
    try:
        c.execute("ALTER TABLE baneos ADD COLUMN hasta INTEGER")
        c.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise


def _cuentas():
    ruta = os.path.abspath(ruta_base_cuentas())
    c = getattr(_hilo, "cuentas", None)
    if c is None or getattr(_hilo, "cuentas_ruta", None) != ruta:
        if c is not None:
            c.close()
        c = sqlite3.connect(ruta, timeout=5, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(ESQUEMA_CUENTAS)
        c.executescript(V.ESQUEMA)
        SO.preparar(c)
        _hilo.cuentas, _hilo.cuentas_ruta = c, ruta
    return c


def cerrar_conexiones():
    """★ 20-nov: la llama el manejador al terminar CADA conexión HTTP (ver `_Manejador.handle`). Antes no la llamaba
    nadie y las conexiones de los hilos terminados quedaban abiertas: con toda la gente de Chile en Miami, el proceso
    llegó a 1023 archivos abiertos (tope 1024) y cada pedido dio «unable to open database file» (login caído)."""
    for k in ("juego", "propia", "cuentas"):
        c = getattr(_hilo, k, None)
        if c is not None:
            try:
                c.close()
            finally:
                setattr(_hilo, k, None)
            setattr(_hilo, k, None)
            setattr(_hilo, k + "_ruta", None)


def _ahora_txt():
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  La clave
# ══════════════════════════════════════════════════════════════════════════════════════════════
_clave = None


def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _de_b64u(s):
    s = s.encode("ascii") if isinstance(s, str) else s
    return base64.urlsafe_b64decode(s + b"=" * (-len(s) % 4))


def clave():
    """-> (semilla, pública, kid). La crea la primera vez (permisos 600 en Linux). ⛔ La semilla no sale de acá."""
    global _clave
    if _clave is None:
        ruta = ruta_clave()
        if not os.path.isfile(ruta):
            semilla = secrets.token_bytes(32)
            fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"ed25519_semilla": semilla.hex(), "creada": _ahora_txt()}, f)
            _log(f"clave NUEVA creada en {ruta}")
        with open(ruta, encoding="utf-8") as f:
            semilla = bytes.fromhex(json.load(f)["ed25519_semilla"])
        pub = ed.publica(semilla)
        _clave = (semilla, pub, hashlib.sha256(pub).hexdigest()[:16])
    return _clave


def jwks():
    _s, pub, kid = clave()
    return {"keys": [{"kty": "OKP", "crv": "Ed25519", "x": _b64u(pub), "kid": kid, "alg": "EdDSA", "use": "sig"}]}


def emitir_pase(uid, juego, ahora=None, vida=PASE_SEGUNDOS):
    ahora = int(time.time() if ahora is None else ahora)
    semilla, _pub, kid = clave()
    jti = secrets.token_urlsafe(16)
    cab = {"alg": "EdDSA", "typ": "JWT", "kid": kid}
    carga = {"iss": EMISOR, "aud": juego, "sub": str(int(uid)), "iat": ahora, "exp": ahora + int(vida),
             "jti": jti}
    # ★ 12-nov (Eñeños, por EDA: «que sus cuentas no lleven r2xxx sino sus nombres de r2beat»): el NOMBRE VISIBLE.
    #   ⛔ El APODO del personaje del casillero 1 (público: sale en el ranking), NUNCA el login (privado). Opcional:
    #   sin apodo no va el claim y el otro juego usa su nombre interno. El otro juego lo recorta a lo que entre.
    nombre = _apodo_de(uid)
    # ★ 16-nov (decisión de Eñeños): en las SUBIDAS al servidor de prueba se muestra «login · Eñeños ID» (Cuenta
    #   Eñeños no tiene apodo). SÓLO en los pases del servidor de parches; los de los juegos siguen sin el login.
    if not nombre and juego in JUEGOS_CON_LOGIN:
        nombre = _login_de(uid) or ""
    if nombre:
        carga["nombre"] = nombre
    a = _b64u(json.dumps(cab, separators=(",", ":")).encode())
    b = _b64u(json.dumps(carga, separators=(",", ":")).encode())
    firma = ed.firmar(semilla, f"{a}.{b}".encode("ascii"))
    return f"{a}.{b}.{_b64u(firma)}", carga


def comprobar_pase(pase, pub, juego, ahora=None, tolerancia=30):
    """Lo que tiene que hacer el server del OTRO juego (acá, para la prueba y como modelo). -> carga o None.
    ⛔ No mira el `jti` repetido: eso lo lleva quien recibe (lo tiene que guardar mientras el pase viva)."""
    try:
        a, b, c = pase.split(".")
        cab = json.loads(_de_b64u(a))
        carga = json.loads(_de_b64u(b))
        if cab.get("alg") != "EdDSA" or not ed.verificar(pub, f"{a}.{b}".encode("ascii"), _de_b64u(c)):
            return None
    except (ValueError, TypeError, AttributeError):
        return None
    ahora = time.time() if ahora is None else ahora
    if carga.get("iss") != EMISOR or carga.get("aud") != juego or not carga.get("jti"):
        return None
    if not isinstance(carga.get("exp"), int) or carga["exp"] + tolerancia < ahora:
        return None
    return carga


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  Las cuentas (`cuentas.db` cuando es dueña; `datos.db` en sólo lectura cuando no) y los permisos
# ══════════════════════════════════════════════════════════════════════════════════════════════
def hash_clave(clave_txt):
    """La MISMA cuenta que el juego (`basedatos.hash_pass`, `api_web.hash_clave`): SHA-256 en hex mayúscula."""
    return hashlib.sha256(str(clave_txt).encode("utf-8")).hexdigest().upper()


def _es_sha256_hex(h):
    return isinstance(h, str) and len(h) == 64 and all(c in _HEX_MAYUS for c in h)


def envolver_hash(hash_upper, sal=None):
    """Envuelve el SHA-256 en hex mayúscula (64 caracteres) en `hashlib.scrypt` con una sal por cuenta."""
    h = str(hash_upper or "").strip().upper()
    if not _es_sha256_hex(h):
        raise ValueError("el hash SHA-256 tiene que ser de 64 caracteres hexadecimales")
    sal = os.urandom(SCRYPT_SAL_BYTES) if sal is None else bytes(sal)
    dk = hashlib.scrypt(h.encode("ascii"), salt=sal, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                        maxmem=64 * 1024 * 1024, dklen=SCRYPT_LARGO)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${sal.hex()}${dk.hex()}"


def verificar_hash(hash_upper, guardado):
    """Comprueba con `hmac.compare_digest` el SHA-256 en hex mayúscula contra el scrypt guardado en `cuentas.db`."""
    h = str(hash_upper or "").strip().upper()
    if not _es_sha256_hex(h) or not guardado:
        return False
    try:
        esquema, n_s, r_s, p_s, sal_hex, dk_hex = str(guardado).split("$")
        if esquema != "scrypt":
            return False
        n, r, p = int(n_s), int(r_s), int(p_s)
        sal = bytes.fromhex(sal_hex)
        esperado = bytes.fromhex(dk_hex)
        if not sal or not esperado:
            return False
        calculado = hashlib.scrypt(h.encode("ascii"), salt=sal, n=n, r=r, p=p,
                                   maxmem=64 * 1024 * 1024, dklen=len(esperado))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculado, esperado)


def _usuario_valido(usuario):
    """Mismas reglas de formato que `basedatos.cuenta_crear`: 3 a 16 caracteres alfanuméricos o '_'."""
    u = str(usuario or "").strip()
    if not (3 <= len(u) <= 16) or not u.replace("_", "").isalnum():
        return None
    return u


def _hash_de_entrada(clave_txt=None, hash_upper=None):
    """Devuelve el SHA-256 en hex mayúscula (64 caracteres) de la contraseña o hash recibidos, o None."""
    if hash_upper is not None and str(hash_upper).strip() != "":
        dado = str(hash_upper).strip().upper()
        return dado if (_es_sha256_hex(dado) and dado != _HASH_VACIO) else None
    if clave_txt is not None:
        s = str(clave_txt)
        if not (1 <= len(s) <= 128):
            return None
        return hash_clave(s)
    return None


def cuenta(usuario):
    """-> fila de la cuenta o None. El usuario se compara EXACTO, como el juego (`Junior` ≠ `junior`)."""
    if es_duena():
        return _cuentas().execute(
            "SELECT uid, usuario, clave, estado, creada FROM cuentas WHERE usuario = ? COLLATE BINARY",
            (usuario,)).fetchone()
    return _juego().execute("SELECT uid, pass_hash FROM users WHERE username = ?", (usuario,)).fetchone()


def estado_r2beat(uid):
    """'ok' | 'baneada' | 'fusionada' | 'no_existe' — se mira en CADA pase: un ban corta también acá."""
    if es_duena():
        r = _cuentas().execute("SELECT estado FROM cuentas WHERE uid = ?", (int(uid),)).fetchone()
        if not r:
            return "no_existe"
        est = str(r["estado"] or "")
        return "ok" if est == "activa" else est
    r = _juego().execute("SELECT pass_hash FROM users WHERE uid = ?", (int(uid),)).fetchone()
    if not r:
        return "no_existe"
    h = str(r["pass_hash"] or "")
    return "baneada" if h.startswith("BANNED:") else "fusionada" if h.startswith("FUSIONADA:") else "ok"


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  ★ 20-nov — LOS BANEOS CON TIEMPO (Eñeños: «baneos en X juegos, por X horas, por X días, X motivo; el launcher
#  baneado, al presionar Jugar, debe recibir un popup con el motivo de su ban + el tiempo»).
#    · `baneos.hasta` = epoch en que vence; NULL = permanente (los de antes de esta columna quedan permanentes).
#    · Un baneo VENCIDO deja de contar solo, al chequear (`baneo_vigente`): la fila queda (historial) y la
#      auditoría tiene cada movimiento. Desbanear antes de tiempo = `hasta` pasa a «ahora» (tampoco se borra).
#    · El pase rechazado por un ban trae `error: "baneado"` + juego, motivo, hasta y restante_seg (ver `respuesta_baneo`).
#    · Sólo un ADMIN banea PERMANENTE y en TODA LA RED. Un moderador: sólo en sus juegos y hasta BANEO_TOPE_MODERADOR_SEG.
# ══════════════════════════════════════════════════════════════════════════════════════════════
BANEO_MOTIVO_MAX = 200
# ★ 20-nov (Eñeños: «que los mod puedan banear horas, días, meses, tiempo ajustable»): el tope de un MODERADOR se
#   AJUSTA con R2_BANEO_TOPE_MODERADOR_DIAS (de fábrica 365 = 12 meses). Permanente o toda la red: sólo un ADMIN.
BANEO_MES_SEG = 30 * 86400             # un «mes» de baneo = 30 días justos (así «vence en …» no depende del calendario)


def _tope_moderador_dias():
    v = (os.environ.get("R2_BANEO_TOPE_MODERADOR_DIAS") or "").strip()
    return max(1, min(3650, int(v))) if v.isdigit() else 365


BANEO_TOPE_MODERADOR_SEG = _tope_moderador_dias() * 86400
BANEO_TOPE_SEG = 3650 * 86400          # (el más largo con fecha: 10 años; más que eso, que sea permanente)


def baneo_vigente(uid, juego, ahora=None):
    """La fila del baneo que HOY cuenta (permanente, o con `hasta` en el futuro), o None."""
    ahora = int(time.time() if ahora is None else ahora)
    return _propia().execute("SELECT uid, juego, desde, quien, motivo, hasta FROM baneos WHERE uid = ? AND juego = ? "
                             "AND (hasta IS NULL OR hasta > ?)", (int(uid), juego, ahora)).fetchone()


def datos_baneo(fila, ahora=None):
    """{motivo, hasta, restante_seg} de una fila de `baneos` (hasta y restante: None si es permanente)."""
    ahora = int(time.time() if ahora is None else ahora)
    hasta = fila["hasta"]
    return {"motivo": fila["motivo"] or "", "hasta": int(hasta) if hasta is not None else None,
            "restante_seg": max(0, int(hasta) - ahora) if hasta is not None else None}


def texto_restante(seg):
    """«2 días y 3 horas», «5 horas y 12 minutos», «45 minutos» (redondea para arriba al minuto). None -> None."""
    if seg is None:
        return None
    m = max(1, -(-int(seg) // 60))
    d, h, mi = m // 1440, (m % 1440) // 60, m % 60
    uno = lambda n, s, p: f"{n} {s if n == 1 else p}"
    if d >= 60 or (d >= 30 and d % 30 == 0):
        me, d = d // 30, d % 30
        return uno(me, "mes", "meses") + (" y " + uno(d, "día", "días") if d else "")
    if d:
        return uno(d, "día", "días") + (" y " + uno(h, "hora", "horas") if h else "")
    if h:
        return uno(h, "hora", "horas") + (" y " + uno(mi, "minuto", "minutos") if mi else "")
    return uno(mi, "minuto", "minutos")


def respuesta_baneo(fila, juego, ahora=None):
    """El cuerpo del 403 de un pase (o un manifiesto) rechazado por un ban. ⛔ `error` es el código («baneado»): el
    launcher nuevo arma el popup con lo demás; `texto` es la frase lista para el que no lo sepa leer."""
    d = datos_baneo(fila, ahora)
    nombre = _juegos().get(juego, {}).get("nombre", juego)
    resto = texto_restante(d["restante_seg"])
    texto = (f"No puedes entrar a {nombre}: " + (d["motivo"] or "bloqueo del equipo") + ". "
             + (f"Vence en {resto}." if resto else "Este bloqueo es permanente."))
    return dict({"error": "baneado", "juego": juego, "nombre": nombre}, **d, texto=texto)


def permitido(uid, juego, ahora=None):
    juegos = _juegos()
    if juego not in juegos:
        return False
    if es_duena() and estado_r2beat(uid) != "ok":
        return False
    c = _propia()
    if baneo_vigente(uid, juego, ahora):
        return False
    # ★ 18-nov (Eñeños): los juegos con FECHA de lanzamiento: antes, sólo admins / moderadores y aprobados (invitación);
    #   después, toda cuenta activa — EDA incluido («se abre a todas las cuentas»). Ver lanzamientos.py
    lz = LZ.cerrado_para(sys.modules[__name__], uid, juego, ahora)
    if lz is not None:
        return lz
    if juegos[juego]["abierto"]:
        return True
    return bool(c.execute("SELECT 1 FROM aprobados WHERE uid = ? AND juego = ?", (int(uid), juego)).fetchone())


def manifiesto(token, juego):
    """-> (código, datos). Sólo a una sesión viva, con la cuenta en regla y APROBADA para ese juego."""
    uid = sesion_de(token)
    if not uid:
        return 401, {"error": "Tienes que iniciar sesión."}
    juegos = _juegos()
    if juego not in juegos:
        return 404, {"error": "Ese juego no existe."}
    ban = baneo_vigente(uid, juego) if estado_r2beat(uid) == "ok" else None
    if ban:                                  # ★ 20-nov: el porqué, para el launcher (`error` = la frase: el viejo la muestra)
        r = respuesta_baneo(ban, juego)
        return 403, dict(r, error=r["texto"], baneado=True)
    if estado_r2beat(uid) != "ok" or not permitido(uid, juego):
        return 403, {"error": f"Tu cuenta todavía no tiene acceso a {juegos[juego]['nombre']}."}
    carpeta = os.environ.get("R2_PORTERO_MANIFIESTOS") or ""
    ruta = os.path.join(carpeta, juego + ".json")
    if not carpeta or not os.path.isfile(ruta):
        return 503, {"error": "Todavía no hay cliente publicado para este juego."}
    with open(ruta, encoding="utf-8") as f:
        return 200, json.load(f)


def juegos_de(uid):
    """★ 20-nov: un juego en el que la cuenta está baneada trae además `baneo` {motivo, hasta, restante_seg}."""
    out = []
    for j, d in _juegos().items():
        g = {"id": j, "nombre": d["nombre"], "permitido": permitido(uid, j)}
        ban = baneo_vigente(uid, j)
        if ban:
            g["baneo"] = datos_baneo(ban)
        out.append(g)
    return out


_fallos = {}
_fallos_lock = threading.Lock()


def _frenado(claves, ahora):
    with _fallos_lock:
        for k in claves:
            v = [t for t in _fallos.get(k, []) if ahora - t < INTENTOS_VENTANA]
            _fallos[k] = v
            if len(v) >= INTENTOS_MAX:
                return True
    return False


def _anotar_fallo(claves, ahora):
    with _fallos_lock:
        if len(_fallos) > 50_000:
            _fallos.clear()
        for k in claves:
            _fallos.setdefault(k, []).append(ahora)


def _huella(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validar(usuario, clave_txt, hash_upper, ip, ahora, prefijo=""):
    """-> (None, uid) si usuario y clave están bien, o ((código, datos), None). Con el freno de intentos.
    ⛔ El mismo mensaje para «no existe» y «clave mala»."""
    usuario = str(usuario or "").strip()[:32]
    claves = [f"{prefijo}ip:{ip}", f"{prefijo}u:{usuario.lower()}"]
    if _frenado(claves, ahora):
        return (429, {"error": "Demasiados intentos. Espera unos minutos."}), None
    if hash_upper is not None:
        dado = str(hash_upper).strip().upper()
    elif clave_txt is not None:
        dado = hash_clave(clave_txt)
    else:
        dado = ""
    r = cuenta(usuario) if usuario else None
    if es_duena():
        if not r or not verificar_hash(dado, r["clave"]):
            _anotar_fallo(claves, ahora)
            return (401, {"error": "Usuario o contraseña incorrectos."}), None
        est = str(r["estado"] or "")
        if est != "activa":
            _anotar_fallo(claves, ahora)
            if est == "fusionada":
                return (403, {"error": "Esta cuenta se unió a otra: entra con aquélla."}), None
            return (403, {"error": "Esta cuenta está suspendida."}), None
        return None, int(r["uid"])
    guardado = str(r["pass_hash"] or "").upper() if r else ""
    if not r or len(dado) != 64 or not hmac.compare_digest(guardado, dado):
        _anotar_fallo(claves, ahora)
        if r and guardado.startswith("BANNED:") and hmac.compare_digest(guardado[7:], dado):
            return (403, {"error": "Esta cuenta está suspendida."}), None
        if r and guardado.startswith("FUSIONADA:") and hmac.compare_digest(guardado[10:], dado):
            return (403, {"error": "Esta cuenta se unió a otra: entra con aquélla."}), None
        return (401, {"error": "Usuario o contraseña incorrectos."}), None
    return None, int(r["uid"])


def entrar(usuario, clave_txt=None, hash_upper=None, ip="", ahora=None):
    """-> (código, datos)."""
    ahora = time.time() if ahora is None else ahora
    error, uid = _validar(usuario, clave_txt, hash_upper, ip, ahora)
    if error:
        return error
    token = abrir_sesion(uid, ip, ahora)
    _log(f"entró uid={uid} desde {ip}")
    return 200, {"sesion": token, "uid": uid, "vence": int(ahora + SESION_DIAS * 86400), "juegos": juegos_de(uid)}


def abrir_sesion(uid, ip="", ahora=None):
    """Una sesión nueva de ese Eñeños ID (la de /entrar; ★ 16-nov también la de Google/Discord). -> el token."""
    ahora = time.time() if ahora is None else ahora
    token = secrets.token_urlsafe(32)
    with _escribir:
        c = _propia()
        c.execute("DELETE FROM sesiones WHERE vence < ?", (int(ahora),))
        c.execute("INSERT INTO sesiones (huella, uid, creada, vence, ip) VALUES (?, ?, ?, ?, ?)",
                  (_huella(token), int(uid), int(ahora), int(ahora + SESION_DIAS * 86400), str(ip or "")[:64]))
        c.commit()
    return token


def _siguiente_uid(cc):
    """Próximo Eñeños ID secuencial libre en `cuentas.db`, empezando en `_uid_nuevas_desde()`."""
    desde = _uid_nuevas_desde()
    fila = cc.execute("SELECT COALESCE(MAX(uid), 0) FROM cuentas WHERE uid >= ?", (desde,)).fetchone()
    return max(desde, int(fila[0]) + 1)


def registrar(usuario, clave_txt=None, hash_upper=None, ip="", ahora=None):
    """Crea una cuenta nueva en `cuentas.db` (sólo con `R2_CUENTAS_DUENA=1`). Con freno por IP."""
    if not es_duena():
        return 404, {"error": "no existe"}
    ahora = time.time() if ahora is None else ahora
    claves_ip = [f"reg-ip:{ip}"]
    if _frenado(claves_ip, ahora):
        return 429, {"error": "Demasiados intentos. Espera unos minutos."}
    u = _usuario_valido(usuario)
    if not u:
        _anotar_fallo(claves_ip, ahora)
        return 400, {"error": "el usuario tiene que ser de 3 a 16 caracteres alfanuméricos"}
    dado = _hash_de_entrada(clave_txt, hash_upper)
    if not dado:
        _anotar_fallo(claves_ip, ahora)
        return 400, {"error": "la clave llegó mal"}
    envuelta = envolver_hash(dado)
    with _escribir:
        c = _cuentas()
        if c.execute("SELECT 1 FROM cuentas WHERE usuario = ? COLLATE BINARY", (u,)).fetchone():
            _anotar_fallo(claves_ip, ahora)
            return 409, {"error": "ese usuario ya existe"}
        uid = _siguiente_uid(c)
        c.execute("INSERT INTO cuentas (uid, usuario, clave, estado, creada) VALUES (?, ?, ?, 'activa', ?)",
                  (uid, u, envuelta, _ahora_txt()))
        c.commit()
        _admins["fecha"] = None
        _moderadores["fecha"] = None
    _anotar_fallo(claves_ip, ahora)
    _log(f"registrada cuenta uid={uid} desde {ip}")
    return 200, {"ok": True, "uid": uid, "usuario": u}


def cambiar_clave(token, clave_actual=None, clave_nueva=None, actual_sha256_upper=None,
                  nueva_sha256_upper=None, ip="", ahora=None):
    """El jugador cambia su contraseña (pide sesión viva y su contraseña actual; sólo con `R2_CUENTAS_DUENA=1`)."""
    if not es_duena():
        return 404, {"error": "no existe"}
    ahora = time.time() if ahora is None else ahora
    uid = sesion_de(token, ahora)
    if not uid:
        return 401, {"error": "Tienes que iniciar sesión."}
    claves = [f"cc-ip:{ip}", f"cc-u:{uid}"]
    if _frenado(claves, ahora):
        return 429, {"error": "Demasiados intentos. Espera unos minutos."}
    r = _cuentas().execute("SELECT uid, usuario, clave, estado FROM cuentas WHERE uid = ?", (int(uid),)).fetchone()
    if not r or r["estado"] != "activa":
        salir(token)
        return 403, {"error": "Esta cuenta está suspendida." if (r and r["estado"] == "baneada")
                     else "Esta cuenta ya no puede entrar."}
    dado_actual = _hash_de_entrada(clave_actual, actual_sha256_upper)
    if not dado_actual or not verificar_hash(dado_actual, r["clave"]):
        _anotar_fallo(claves, ahora)
        return 401, {"error": "Usuario o contraseña incorrectos."}
    dado_nueva = _hash_de_entrada(clave_nueva, nueva_sha256_upper)
    if not dado_nueva:
        return 400, {"error": "la clave llegó mal"}
    envuelta = envolver_hash(dado_nueva)
    with _escribir:
        c = _cuentas()
        c.execute("UPDATE cuentas SET clave = ? WHERE uid = ?", (envuelta, int(uid)))
        c.commit()
    _log(f"cambió su clave uid={uid} desde {ip}")
    return 200, {"ok": True}


def _verificar_ficha_interna(ficha_dada):
    """Comprueba `es_duena()`, `R2_CUENTAS_FICHA_INTERNA` configurada y la ficha recibida.
    -> None si pasa, o `(codigo, datos)` para devolver 404/401."""
    esperada = ficha_interna()
    if not es_duena() or not esperada:
        return 404, {"error": "no existe"}
    dada = str(ficha_dada or "").strip()
    if not dada or not hmac.compare_digest(dada.encode("utf-8"), esperada.encode("utf-8")):
        return 401, {"error": "No autorizado."}
    return None


def cuenta_interna(uid, ficha_dada):
    """GET interno de una cuenta por `uid` -> `{uid, usuario, estado}` (para el panel del juego).
    Protegido por `R2_CUENTAS_FICHA_INTERNA`; sin esa variable (o sin `R2_CUENTAS_DUENA=1`) no existe (404).
    ⛔ Nunca devuelve nada de la contraseña."""
    err = _verificar_ficha_interna(ficha_dada)
    if err:
        return err
    if isinstance(uid, bool):
        return 400, {"error": "Cuenta inválida."}
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return 400, {"error": "Cuenta inválida."}
    r = _cuentas().execute("SELECT uid, usuario, estado FROM cuentas WHERE uid = ?", (uid,)).fetchone()
    if not r:
        return 404, {"error": "Esa cuenta no existe."}
    return 200, {"uid": int(r["uid"]), "usuario": r["usuario"], "estado": r["estado"]}


def enlaces_internos(ficha_dada=""):
    """GET interno `/cuentas/interno/enlaces` -> `{"cuentas": [{usuario, uid}]}` (Eñeños IDs) para enlazar un juego.
    Protegido por `R2_CUENTAS_FICHA_INTERNA`. ⛔ Nunca devuelve contraseñas."""
    err = _verificar_ficha_interna(ficha_dada)
    if err:
        return err
    filas = _cuentas().execute("SELECT uid, usuario FROM cuentas ORDER BY uid").fetchall()
    return 200, {"cuentas": [{"usuario": r["usuario"], "uid": int(r["uid"])} for r in filas]}


def usuario_interno(usuario, ficha_dada):
    """GET interno por nombre EXACTO (`Junior` != `junior`) -> `{uid, usuario, estado}` o 404.
    ⛔ Nunca devuelve nada de la contraseña."""
    err = _verificar_ficha_interna(ficha_dada)
    if err:
        return err
    u = str(usuario or "").strip()
    if not u:
        return 404, {"error": "Esa cuenta no existe."}
    r = _cuentas().execute(
        "SELECT uid, usuario, estado FROM cuentas WHERE usuario = ? COLLATE BINARY", (u,)).fetchone()
    if not r:
        return 404, {"error": "Esa cuenta no existe."}
    return 200, {"uid": int(r["uid"]), "usuario": r["usuario"], "estado": r["estado"]}


def admin_interno_estado(uid, estado, motivo="", ficha_dada=""):
    """POST interno `/cuentas/interno/cuenta/<uid>/estado` `{estado, motivo}` -> `{uid, usuario, estado}`."""
    err = _verificar_ficha_interna(ficha_dada)
    if err:
        return err
    if isinstance(uid, bool):
        return 400, {"error": "Cuenta inválida."}
    try:
        uid_i = int(uid)
    except (TypeError, ValueError):
        return 400, {"error": "Cuenta inválida."}
    if uid_i <= 0:
        return 400, {"error": "Cuenta inválida."}
    est = str(estado or "").strip().lower()
    if est not in ("activa", "baneada", "fusionada"):
        return 400, {"error": "Estado inválido."}
    det = str(motivo or "")[:200]
    with _escribir:
        cc = _cuentas()
        r = cc.execute("SELECT uid, usuario, estado FROM cuentas WHERE uid = ?", (uid_i,)).fetchone()
        if not r:
            return 404, {"error": "Esa cuenta no existe."}
        cc.execute("UPDATE cuentas SET estado = ? WHERE uid = ?", (est, uid_i))
        cc.commit()
        cp = _propia()
        if est in ("baneada", "fusionada"):
            cp.execute("DELETE FROM sesiones WHERE uid = ?", (uid_i,))
        cp.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                   (_ahora_txt(), "interno:panel", f"interno-estado:{est}", uid_i, None, det))
        cp.commit()
    _log(f"interno estado uid={uid_i} -> {est}")
    return 200, {"uid": int(r["uid"]), "usuario": r["usuario"], "estado": est}


def admin_interno_clave(uid, pass_sha256_upper, ficha_dada=""):
    """POST interno `/cuentas/interno/cuenta/<uid>/clave` `{pass_sha256_upper}` -> `{uid, usuario}`.
    Cierra sesiones abiertas de ese `uid`. ⛔ No anota ni devuelve contraseñas ni hashes."""
    err = _verificar_ficha_interna(ficha_dada)
    if err:
        return err
    if isinstance(uid, bool):
        return 400, {"error": "Cuenta inválida."}
    try:
        uid_i = int(uid)
    except (TypeError, ValueError):
        return 400, {"error": "Cuenta inválida."}
    if uid_i <= 0:
        return 400, {"error": "Cuenta inválida."}
    dado = _hash_de_entrada(None, pass_sha256_upper)
    if not dado:
        return 400, {"error": "La clave llegó mal."}
    envuelta = envolver_hash(dado)
    with _escribir:
        cc = _cuentas()
        r = cc.execute("SELECT uid, usuario FROM cuentas WHERE uid = ?", (uid_i,)).fetchone()
        if not r:
            return 404, {"error": "Esa cuenta no existe."}
        cc.execute("UPDATE cuentas SET clave = ? WHERE uid = ?", (envuelta, uid_i))
        cc.commit()
        cp = _propia()
        cp.execute("DELETE FROM sesiones WHERE uid = ?", (uid_i,))
        cp.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                   (_ahora_txt(), "interno:panel", "interno-clave", uid_i, None, ""))
        cp.commit()
    _log(f"interno clave uid={uid_i}")
    return 200, {"uid": int(r["uid"]), "usuario": r["usuario"]}


def interno_comprobar_clave(uid, pass_sha256_upper, ficha_dada="", ahora=None):
    """POST interno `/cuentas/interno/cuenta/<uid>/comprobar-clave` `{pass_sha256_upper}` -> 200 `{"ok": true}`,
    401 si no es la contraseña de esa cuenta (o la cuenta no existe o no está activa), 429 con el freno.

    ★ 15-nov (lo vio Eñeños en el ensayo): el juego vuelve a pedir la contraseña para BORRAR un personaje desde el
    selector de adentro. Con pases el juego ya no guarda contraseñas: la comprueba Cuenta Eñeños. No abre sesión ni
    da pase: sólo dice sí o no. Con su propio freno POR CUENTA (los mismos intentos y la misma ventana que `entrar`).
    ⛔ No anota ni devuelve nada de la contraseña."""
    err = _verificar_ficha_interna(ficha_dada)
    if err:
        return err
    if isinstance(uid, bool):
        return 400, {"error": "Cuenta inválida."}
    try:
        uid_i = int(uid)
    except (TypeError, ValueError):
        return 400, {"error": "Cuenta inválida."}
    ahora = time.time() if ahora is None else ahora
    claves = [f"comprobar:u:{uid_i}"]
    if _frenado(claves, ahora):
        return 429, {"error": "Demasiados intentos. Espera unos minutos."}
    dado = _hash_de_entrada(None, pass_sha256_upper)
    r = _cuentas().execute("SELECT clave, estado FROM cuentas WHERE uid = ?", (uid_i,)).fetchone() if uid_i > 0 else None
    if not r or not dado or str(r["estado"] or "") != "activa" or not verificar_hash(dado, r["clave"]):
        _anotar_fallo(claves, ahora)
        return 401, {"error": "Contraseña incorrecta."}
    return 200, {"ok": True}


def admin_interno_crear(usuario, pass_sha256_upper, ficha_dada=""):
    """POST interno `/cuentas/interno/cuenta` `{usuario, pass_sha256_upper}` -> `{uid, usuario, estado}`.
    Para separar un personaje del juego a cuenta nueva: Cuenta Eñeños asigna el próximo Eñeños ID."""
    err = _verificar_ficha_interna(ficha_dada)
    if err:
        return err
    u = _usuario_valido(usuario)
    if not u:
        return 400, {"error": "el usuario tiene que ser de 3 a 16 caracteres alfanuméricos"}
    dado = _hash_de_entrada(None, pass_sha256_upper)
    if not dado:
        return 400, {"error": "la clave llegó mal"}
    envuelta = envolver_hash(dado)
    with _escribir:
        cc = _cuentas()
        if cc.execute("SELECT 1 FROM cuentas WHERE usuario = ? COLLATE BINARY", (u,)).fetchone():
            return 409, {"error": "ese usuario ya existe"}
        uid_i = _siguiente_uid(cc)
        cc.execute("INSERT INTO cuentas (uid, usuario, clave, estado, creada) VALUES (?, ?, ?, 'activa', ?)",
                   (uid_i, u, envuelta, _ahora_txt()))
        cc.commit()
        _admins["fecha"] = None
        _moderadores["fecha"] = None
        cp = _propia()
        cp.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                   (_ahora_txt(), "interno:panel", "interno-crear", uid_i, None, f"usuario={u}"))
        cp.commit()
    _log(f"interno crear uid={uid_i} usuario={u}")
    return 200, {"uid": uid_i, "usuario": u, "estado": "activa"}


def sesion_de(token, ahora=None):
    """El uid de esa sesión, o None. Vive en `portero.db`: sobrevive a un reinicio del portero (y del juego)."""
    if not token:
        return None
    ahora = time.time() if ahora is None else ahora
    r = _propia().execute("SELECT uid, vence FROM sesiones WHERE huella = ?", (_huella(token),)).fetchone()
    return int(r["uid"]) if r and r["vence"] > ahora else None


def salir(token):
    with _escribir:
        c = _propia()
        c.execute("DELETE FROM sesiones WHERE huella = ?", (_huella(token or ""),))
        c.commit()


def pedir_pase(token, juego, ip="", ahora=None):
    uid = sesion_de(token, ahora)
    if not uid:
        return 401, {"error": "Tienes que iniciar sesión."}
    juegos = _juegos()
    if juego not in juegos:
        return 404, {"error": "Ese juego no existe."}
    est = estado_r2beat(uid)
    if est != "ok":
        salir(token)
        return 403, {"error": "Esta cuenta ya no puede entrar." if est != "baneada" else "Esta cuenta está suspendida."}
    ban = baneo_vigente(uid, juego, ahora)
    if ban:                                  # ★ 20-nov: mismo 403 que «no permitido», con el porqué y el tiempo
        _log(f"pase {juego} NEGADO a uid={uid}: baneado")
        return 403, respuesta_baneo(ban, juego, ahora)
    if not permitido(uid, juego, ahora):
        return 403, {"error": f"Tu cuenta todavía no tiene acceso a {juegos[juego]['nombre']}."}
    pase, carga = emitir_pase(uid, juego, ahora)
    with _escribir:
        c = _propia()
        c.execute("INSERT INTO pases (jti, uid, juego, emitido, ip) VALUES (?, ?, ?, ?, ?)",
                  (carga["jti"], uid, juego, carga["iat"], ip[:64]))
        c.commit()
    _log(f"pase {juego} para uid={uid}")
    return 200, {"pase": pase, "vence": carga["exp"]}


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  ★ 12-nov: el PANEL de aprobaciones (Eñeños: «un panel admin en el dominio eñeños, no tan avanzado como el de R2,
#  sólo con la seguridad suficiente»). Página: `portero_panel.html` + `.js`, al lado de este archivo.
#    · entran SÓLO los ADMIN de R2Beat: `admin.txt`, el MISMO que lee `panel_admin` (al lado de `gm.txt`: en
#      `servidor/` o, en prod, en la raíz), mismo formato (uid, login o @apodo único). Se relee si cambia.
#    · sesión aparte (`sesiones_admin`, 8 h) en una cookie HttpOnly · Secure · SameSite=Strict; todo POST pide X-R2.
#      Se re-chequea que siga siendo ADMIN en CADA pedido (sacarlo de admin.txt lo deja afuera al instante).
#    · cada acción queda en `auditoria` con el login de quien la hizo. Nunca se muestran hashes ni IPs.
# ══════════════════════════════════════════════════════════════════════════════════════════════
ADMIN_HORAS = 8
COOKIE_ADMIN = "portero_admin"
_DIR_AQUI = os.path.dirname(os.path.abspath(__file__))
_admins = {"ruta": None, "fecha": None, "modo": None, "uids": frozenset()}


def ruta_admins():
    if os.environ.get("R2_ADMIN_ARCHIVO"):
        return os.environ["R2_ADMIN_ARCHIVO"]
    base = _DIR_AQUI if os.path.isfile(os.path.join(_DIR_AQUI, "gm.txt")) else RAIZ   # como gm.RUTA
    return os.path.join(base, "admin.txt")


_JUEGOS_LINEA = re.compile(r"^(?:-|[a-z0-9][a-z0-9-]*(?:\s*,\s*[a-z0-9][a-z0-9-]*)*)$")


def partir_linea_rol(cruda):
    """★ 19-nov (Coordinador, fase A): una línea de `admin.txt` / `moderadores.txt` -> (identidad, juegos).
    `juegos` = None si la línea no los trae (= como siempre: un moderador SIN lista puede en todos los juegos, con
    las acciones de antes) o un frozenset con los ids del catálogo (`juegos.json`); `-` = ninguno.
        110                     -> ("110", None)
        110 eda,gunbound        -> ("110", {"eda", "gunbound"})
        mod1   r2beat2013       -> ("mod1", {"r2beat2013"})
        110 -                   -> ("110", frozenset())
    ⛔ Si lo que sigue a la identidad NO tiene forma de lista de juegos, la línea entera es la identidad (como antes:
       un «@apodo con espacios» sigue siendo un apodo)."""
    linea = str(cruda).split("#", 1)[0].strip()
    if not linea:
        return "", None
    partes = linea.split(None, 1)
    if len(partes) == 2 and _JUEGOS_LINEA.match(partes[1].strip()):
        resto = partes[1].strip()
        if resto == "-":
            return partes[0], frozenset()
        return partes[0], frozenset(j.strip() for j in resto.split(",") if j.strip())
    return linea, None


def _leer_admins(ruta):
    return frozenset(_leer_roles(ruta))


def _leer_roles(ruta):
    """{uid: juegos} de un archivo de roles (ver `partir_linea_rol`). Dos líneas de la misma cuenta se juntan; si
    alguna no trae lista, queda sin lista (todos)."""
    roles = {}
    with open(ruta, encoding="utf-8", errors="replace") as f:
        for cruda in f:
            linea, juegos = partir_linea_rol(cruda)
            if not linea:
                continue
            for u in _uids_de_identidad(linea):
                if u in roles:
                    roles[u] = None if (roles[u] is None or juegos is None) else roles[u] | juegos
                else:
                    roles[u] = juegos
    return roles


def _uids_de_identidad(linea):
    """La(s) cuenta(s) que nombra una identidad de `admin.txt` / `moderadores.txt` (uid, login o @apodo)."""
    uids = set()
    if linea.isdigit():
        n = int(linea)
        if es_duena():
            cc = _cuentas()
            if cc.execute("SELECT 1 FROM cuentas WHERE uid = ?", (n,)).fetchone():
                uids.add(n)
            else:
                r_imp = cc.execute("SELECT uid FROM importadas WHERE uid_viejo = ?", (n,)).fetchone()
                if r_imp:
                    uids.add(int(r_imp[0]))
                elif n >= _uid_nuevas_desde():
                    uids.add(n)
        else:
            uids.add(n)
    elif linea.startswith("@"):
        if es_duena():
            return frozenset()
        try:
            filas = _juego().execute("SELECT uid FROM chars WHERE lower(nickname) = lower(?)",
                                     (linea[1:],)).fetchall()
        except sqlite3.Error:
            filas = []
        if len(filas) == 1:
            uids.add(int(filas[0][0]))
    elif es_duena():
        r = _cuentas().execute("SELECT uid FROM cuentas WHERE usuario = ? COLLATE BINARY", (linea,)).fetchone()
        if r:
            uids.add(int(r[0]))
    else:
        r = _juego().execute("SELECT uid FROM users WHERE username = ?", (linea,)).fetchone()
        if r:
            uids.add(int(r[0]))
    return frozenset(uids)


def _lista_de(cache, ruta):
    """Los uids de un archivo de roles, releído SÓLO si cambió (fecha): se consulta en cada pedido del panel.
    ★ 19-nov: guarda también `mapa` = {uid: juegos} (los juegos asignados de cada moderador)."""
    fecha = os.path.getmtime(ruta) if os.path.isfile(ruta) else None
    modo = es_duena()
    with _escribir:
        if ruta != cache["ruta"] or fecha != cache["fecha"] or modo != cache.get("modo"):
            mapa = _leer_roles(ruta) if fecha else {}
            cache.update(ruta=ruta, fecha=fecha, modo=modo, uids=frozenset(mapa), mapa=mapa)
        return cache["uids"]


def admins():
    return _lista_de(_admins, ruta_admins())


# ★ 12-nov — LOS MODERADORES (Eñeños: dos colaboradores de EDA que aprueben cuentas sin depender de él). Rol ACOTADO:
#   entran al MISMO panel con su cuenta de R2Beat, pero sólo pueden BUSCAR, APROBAR y QUITAR (Eñeños: «2, tu
#   recomendación» = sin banear). No tocan cuentas con rol (admins ni moderadores) y no ven el login de los ADMIN (en
#   la lista y en la auditoría sale «ADMIN»). `moderadores.txt` va AL LADO de `admin.txt`, mismo formato (uid, login
#   o @apodo, `#` comenta) y ⛔ también gitignorado: son cuentas reales. Sacarlo de la lista corta su sesión al instante.
ACCIONES_MODERADOR = ("aprobar", "quitar")
_moderadores = {"ruta": None, "fecha": None, "modo": None, "uids": frozenset()}


def ruta_moderadores():
    if os.environ.get("R2_MODERADOR_ARCHIVO"):
        return os.environ["R2_MODERADOR_ARCHIVO"]
    return os.path.join(os.path.dirname(ruta_admins()), "moderadores.txt")


def moderadores():
    return _lista_de(_moderadores, ruta_moderadores())


# ★ 19-nov (Coordinador, fase A) — LOS JUEGOS ASIGNADOS. En `moderadores.txt`, después de la identidad, la lista de
#   juegos del catálogo (`juegos.json`): `110 eda,gunbound`. Compatible con lo de antes:
#     · SIN lista  -> como siempre: ve todos los juegos y sólo APRUEBA / QUITA (Eñeños, 12-nov: «sin banear»);
#     · CON lista  -> sólo ve y toca ESOS juegos (también invitaciones y auditoría), y ahí además puede BANEAR /
#                     DESBANEAR por juego. `-` = ninguno (está en el equipo pero sin juegos todavía).
#   Los asigna un ADMIN desde «Moderadores y permisos» del Coordinador (`escribir_moderador`), y queda en la auditoría.
ACCIONES_MODERADOR_ASIGNADO = ("aprobar", "quitar", "banear", "desbanear")


def juegos_de_moderador(uid):
    """Los juegos del catálogo de ese moderador: frozenset, o None = sin lista (todos, como antes)."""
    moderadores()
    return _moderadores.get("mapa", {}).get(int(uid))


def juegos_de_rol(uid):
    """None = todos los juegos (ADMIN, o moderador sin lista) · frozenset = sólo ésos · frozenset() = ninguno."""
    rol = rol_de(uid)
    if rol == "admin":
        return None
    if rol == "moderador":
        return juegos_de_moderador(uid)
    return frozenset()


def puede_en(uid, pase):
    """¿Esa cuenta del equipo puede tocar ese pase (`aud`: eda, gunbound-prueba, r2beat2013-subir…)?"""
    if rol_de(uid) is None:
        return False
    permitidos = juegos_de_rol(uid)
    return permitidos is None or CO.juego_de_pase(sys.modules[__name__], pase) in permitidos


def escribir_moderador(uid, juegos, quien="", ahora_txt=None):
    """Pone (o saca, con `juegos=False`) una cuenta de `moderadores.txt` con su lista de juegos, SIN tocar las demás
    líneas ni los comentarios. `juegos`: iterable de ids del catálogo (vacío = `-`, ninguno). Escritura atómica
    (archivo nuevo + `os.replace`). -> cuántas líneas cambiaron o se sumaron. ⛔ El que llama valida y audita."""
    uid = int(uid)
    ruta = ruta_moderadores()
    lista = None if juegos is False else (",".join(sorted({str(j) for j in juegos})) or "-")
    lineas = []
    if os.path.isfile(ruta):
        with open(ruta, encoding="utf-8", errors="replace") as f:
            lineas = f.read().splitlines()
    nuevas, tocadas = [], 0
    for cruda in lineas:
        ident, _j = partir_linea_rol(cruda)
        if ident and uid in _uids_de_identidad(ident):
            tocadas += 1
            if lista is None:
                continue                                            # sacar del equipo
            coment = ("  #" + cruda.split("#", 1)[1]) if "#" in cruda else ""
            nuevas.append(f"{ident} {lista}{coment}")
        else:
            nuevas.append(cruda)
    if lista is not None and not tocadas:
        nuevas.append(f"{uid} {lista}  # desde el Coordinador, {ahora_txt or _ahora_txt()}")
        tocadas = 1
    if not tocadas:
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    tmp = ruta + ".nuevo"
    with _escribir:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(nuevas) + "\n")
        os.replace(tmp, ruta)
        _moderadores["fecha"] = None                                # se relee en el próximo pedido
    _log(f"moderadores.txt: uid={uid} -> {lista if lista is not None else '(fuera)'} ({quien})")
    return tocadas


def rol_de(uid):
    """'admin', 'moderador' o None. ⛔ Se pregunta en CADA pedido: sacarlo del archivo le corta el panel al instante."""
    if uid is None:
        return None
    if int(uid) in admins():
        return "admin"
    if int(uid) in moderadores():
        return "moderador"
    return None


def _login_de(uid):
    if es_duena():
        r = _cuentas().execute("SELECT usuario FROM cuentas WHERE uid = ?", (int(uid),)).fetchone()
        return r["usuario"] if r else None
    r = _juego().execute("SELECT username FROM users WHERE uid = ?", (int(uid),)).fetchone()
    return r["username"] if r else None


def _apodo_de(uid):
    if es_duena():
        return ""
    try:
        r = _juego().execute("SELECT nickname FROM chars WHERE uid = ?", (int(uid),)).fetchone()
        return (r["nickname"] or "") if r else ""
    except sqlite3.Error:
        return ""


def admin_entrar(usuario, clave_txt=None, ip="", ahora=None):
    """-> (código, datos, token). ⛔ Que no sea ADMIN da el MISMO 401 que una clave mala: no se le dice a nadie quién es admin."""
    ahora = time.time() if ahora is None else ahora
    error, uid = _validar(usuario, clave_txt, None, ip, ahora, prefijo="adm-")
    if error:
        return error[0], error[1], None
    rol = rol_de(uid)
    if rol is None:
        _anotar_fallo([f"adm-ip:{ip}"], ahora)
        return 401, {"error": "Usuario o contraseña incorrectos."}, None
    token = abrir_sesion_admin(uid, ip, ahora)
    _auditar(uid, "entrar al panel", None, None, rol)
    _log(f"panel: entró el {rol} uid={uid}")
    return 200, {"admin": _login_de(uid), "rol": rol}, token


def abrir_sesion_admin(uid, ip="", ahora=None):
    """Una sesión del panel (8 h) para una cuenta del equipo. -> el token (va en una cookie HttpOnly). ★ 19-nov: la
    usan el panel chico (`/cuentas/admin`) y el Coordinador (`servidor/coordinador.py`)."""
    ahora = time.time() if ahora is None else ahora
    token = secrets.token_urlsafe(32)
    with _escribir:
        c = _propia()
        c.execute("DELETE FROM sesiones_admin WHERE vence < ?", (int(ahora),))
        c.execute("INSERT INTO sesiones_admin VALUES (?, ?, ?, ?, ?)",
                  (_huella(token), int(uid), int(ahora), int(ahora + ADMIN_HORAS * 3600), str(ip or "")[:64]))
        c.commit()
    return token


def admin_de(token, ahora=None):
    """El uid de quien tiene esa sesión (ADMIN o MODERADOR), o None (vencida, o ya no está en su archivo)."""
    if not token:
        return None
    ahora = time.time() if ahora is None else ahora
    r = _propia().execute("SELECT uid, vence FROM sesiones_admin WHERE huella = ?", (_huella(token),)).fetchone()
    if not r or r["vence"] <= ahora or rol_de(r["uid"]) is None:
        return None
    return int(r["uid"])


def admin_salir(token):
    with _escribir:
        c = _propia()
        c.execute("DELETE FROM sesiones_admin WHERE huella = ?", (_huella(token or ""),))
        c.commit()


def _auditar(uid_admin, accion, uid, juego, detalle):
    with _escribir:
        c = _propia()
        c.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                  (_ahora_txt(), _login_de(uid_admin) or f"uid {uid_admin}", accion, uid, juego, str(detalle)[:200]))
        c.commit()


def _ficha(uid, juego):
    c = _propia()
    return {"uid": int(uid), "usuario": _login_de(uid) or "¿?", "apodo": _apodo_de(uid),
            "r2beat": estado_r2beat(uid),
            "aprobada": bool(c.execute("SELECT 1 FROM aprobados WHERE uid = ? AND juego = ?", (uid, juego)).fetchone()),
            "baneada": bool(baneo_vigente(uid, juego))}


def admin_buscar(q, juego="eda", rol="admin"):
    """Hasta 20 cuentas cuyo login EMPIEZA con `q` o cuyo apodo lo CONTIENE (sin distinguir mayúsculas).
    ⛔ A un MODERADOR no se le muestran las cuentas con rol: buscando por login podría descubrir el del ADMIN."""
    q = str(q or "").strip()[:32]
    if len(q) < 2:
        return 400, {"error": "Escriba al menos 2 letras."}
    patron = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    if es_duena():
        uids = [r[0] for r in _cuentas().execute(
            "SELECT uid FROM cuentas WHERE usuario LIKE ? ESCAPE '\\' ORDER BY usuario LIMIT 20", (patron + "%",))]
    else:
        uids = [r[0] for r in _juego().execute(
            "SELECT uid FROM users WHERE username LIKE ? ESCAPE '\\' ORDER BY username LIMIT 20", (patron + "%",))]
        try:
            for r in _juego().execute("SELECT uid FROM chars WHERE nickname LIKE ? ESCAPE '\\' LIMIT 20", ("%" + patron + "%",)):
                if r[0] not in uids and _login_de(r[0]):
                    uids.append(r[0])
        except sqlite3.Error:
            pass
    if rol != "admin":
        uids = [u for u in uids if rol_de(u) is None]
    return 200, {"cuentas": [_ficha(u, juego) for u in uids[:20]]}


def admin_lista(juego="eda", rol="admin"):
    juegos = _juegos()
    c = _propia()
    apr = [dict(_ficha(r["uid"], juego), desde=r["desde"], quien=r["quien"], nota=r["nota"] or "")
           for r in c.execute("SELECT uid, desde, quien, nota FROM aprobados WHERE juego = ? ORDER BY desde DESC", (juego,))]
    ban = [dict(_ficha(r["uid"], juego), desde=r["desde"], quien=r["quien"], **datos_baneo(r))
           for r in c.execute("SELECT uid, desde, quien, motivo, hasta FROM baneos WHERE juego = ? "
                              "AND (hasta IS NULL OR hasta > ?) ORDER BY desde DESC", (juego, int(time.time())))]
    aud = [dict(r) for r in c.execute("SELECT cuando, quien, accion, uid, juego, detalle FROM auditoria "
                                      "ORDER BY id DESC LIMIT 30")]
    for a in aud:
        a["usuario"] = _login_de(a["uid"]) if a["uid"] else ""
    if rol != "admin":
        # ★ el MODERADOR no ve el login de los ADMIN (es una cuenta real, como las de gm.txt): sale «ADMIN»; y de la
        #   auditoría sólo los movimientos de cuentas (no quién entró al panel)
        ocultos = {_login_de(u) for u in admins()} - {None}
        for fila in apr + ban:
            if fila["quien"] in ocultos:
                fila["quien"] = "ADMIN"
        aud = [a for a in aud if a["accion"] in ("aprobar", "quitar", "banear", "desbanear")]
        for a in aud:
            if a["quien"] in ocultos:
                a["quien"] = "ADMIN"
            if a["usuario"] in ocultos:
                a["usuario"] = "ADMIN"
    return 200, {"juego": juego, "nombre": juegos[juego]["nombre"], "aprobadas": apr, "baneadas": ban, "auditoria": aud,
                 "rol": rol}


def leer_duracion(d):
    """★ 20-nov: la duración de un baneo pedida como {horas: n} · {dias: n} · {meses: n} (30 días) · {permanente: true}.
    -> (dicha, seg, error): seg None = permanente · dicha False = no vino ninguna (el ADMIN: permanente, como antes)."""
    d = d if isinstance(d, dict) else {}
    vinieron = [k for k in ("horas", "dias", "meses") if d.get(k) not in (None, "")]
    perm = d.get("permanente") in (True, 1, "1", "si", "sí", "true")
    if len(vinieron) + perm > 1:
        return True, None, "Elija una sola duración: horas, días, meses o permanente."
    if perm:
        return True, None, None
    if not vinieron:
        return False, None, None
    v = d[vinieron[0]]
    if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit())):
        return True, None, "La duración tiene que ser un número entero de horas, días o meses."
    seg = int(v) * {"horas": 3600, "dias": 86400, "meses": BANEO_MES_SEG}[vinieron[0]]
    if seg <= 0:
        return True, None, "La duración tiene que ser de al menos 1 hora."
    if seg > BANEO_TOPE_SEG:
        return True, None, "Esa duración es demasiado larga: use «permanente»."
    return True, seg, None


def duracion_txt(seg):
    return "permanente" if seg is None else "por " + texto_restante(seg)


def pases_de_la_red():
    """Los pases de TODOS los juegos del catálogo (live, test y los «<live>-…»): lo que cubre «toda la red»."""
    yo = sys.modules[__name__]
    return [p for j in CO.catalogo(yo) for p, _e in CO.pases_de(yo, j["id"])]


def _puede_sancionar(uid_admin, uid, pases):
    """Las reglas comunes de banear / desbanear. -> (código, datos) del error, o None si se puede."""
    rol = rol_de(uid_admin)
    if rol is None:
        return 401, {"error": "Tiene que entrar con una cuenta ADMIN o MODERADOR."}
    if not pases:
        return 400, {"error": "Elija al menos un juego."}
    if any(p not in _juegos() for p in pases):
        return 404, {"error": "Ese juego no existe."}
    if rol != "admin":
        if juegos_de_moderador(uid_admin) is None:
            return 403, {"error": "Los moderadores sólo pueden aprobar o quitar."}
        if not all(puede_en(uid_admin, p) for p in pases):
            return 403, {"error": "Ese juego no está asignado a su cuenta."}
    if isinstance(uid, bool) or not str(uid).strip().isdigit():
        return 400, {"error": "Cuenta inválida."}
    if not _login_de(int(uid)):
        return 404, {"error": "Esa cuenta no existe."}
    if rol != "admin" and rol_de(int(uid)) is not None:
        return 403, {"error": "Esa cuenta la maneja un ADMIN."}
    return None


def admin_banear(uid_admin, uid, pases, motivo, duracion=None, red=False, ahora=None):
    """★ 20-nov: banea a `uid` en VARIOS pases de una vez (o en toda la red), por un tiempo o permanente.
    `duracion` = {horas | dias | meses | permanente} (ver `leer_duracion`). Todo o nada: si un pase no se puede, no se toca
    ninguno. Cada pase queda en la auditoría. -> (código, datos)."""
    ahora = int(time.time() if ahora is None else ahora)
    rol = rol_de(uid_admin)
    if red:
        if rol is None:
            return 401, {"error": "Tiene que entrar con una cuenta ADMIN o MODERADOR."}
        if rol != "admin":
            return 403, {"error": "Sólo un ADMIN banea en toda la red."}
        pases = pases_de_la_red()
    pases = list(dict.fromkeys(str(p) for p in (pases or [])))
    err = _puede_sancionar(uid_admin, uid, pases)
    if err:
        return err
    dicha, seg, err_dur = leer_duracion(duracion)
    if err_dur:
        return 400, {"error": err_dur}
    if rol != "admin":
        if not dicha:
            return 400, {"error": "Ponga cuánto dura el baneo (en horas, días o meses)."}
        if seg is None:
            return 403, {"error": "Sólo un ADMIN banea de forma permanente."}
        if seg > BANEO_TOPE_MODERADOR_SEG:
            return 403, {"error": f"Un moderador banea hasta {texto_restante(BANEO_TOPE_MODERADOR_SEG)}; "
                                  "para más, un ADMIN."}
    motivo = str(motivo or "").strip()
    if not motivo:
        return 400, {"error": "Escriba el motivo del baneo (lo ve la persona)."}
    if len(motivo) > BANEO_MOTIVO_MAX:
        return 400, {"error": f"El motivo tiene que tener {BANEO_MOTIVO_MAX} caracteres o menos."}
    uid = int(uid)
    hasta = None if seg is None else ahora + seg
    quien = _login_de(uid_admin) or f"uid {uid_admin}"
    with _escribir:
        c = _propia()
        for p in pases:
            c.execute("INSERT OR REPLACE INTO baneos (uid, juego, desde, quien, motivo, hasta) VALUES (?, ?, ?, ?, ?, ?)",
                      (uid, p, _ahora_txt(), quien, motivo, hasta))
        c.commit()
    detalle = ("toda la red · " if red else "") + f"{duracion_txt(seg)} · {motivo}"
    for p in pases:
        _auditar(uid_admin, "banear", uid, p, detalle)
    _log(f"panel: {quien} -> banear uid={uid} en {','.join(pases)} ({duracion_txt(seg)})")
    return 200, {"ok": True, "pases": pases, "hasta": hasta}


def admin_desbanear(uid_admin, uid, pases, ahora=None):
    """Levanta el baneo ANTES de tiempo en esos pases: `hasta` = ahora (la fila queda, como historial)."""
    ahora = int(time.time() if ahora is None else ahora)
    pases = list(dict.fromkeys(str(p) for p in (pases or [])))
    err = _puede_sancionar(uid_admin, uid, pases)
    if err:
        return err
    uid = int(uid)
    quien = _login_de(uid_admin) or f"uid {uid_admin}"
    with _escribir:
        c = _propia()
        tocados = [p for p in pases if c.execute(
            "UPDATE baneos SET hasta = ? WHERE uid = ? AND juego = ? AND (hasta IS NULL OR hasta > ?)",
            (ahora, uid, p, ahora)).rowcount]
        c.commit()
    for p in pases:
        _auditar(uid_admin, "desbanear", uid, p, "" if p in tocados else "no estaba baneada")
    _log(f"panel: {quien} -> desbanear uid={uid} en {','.join(pases)}")
    return 200, {"ok": True, "pases": pases, "levantados": tocados}


def admin_accion(uid_admin, accion, uid, juego="eda", detalle="", duracion=None):
    if juego not in _juegos():
        return 404, {"error": "Ese juego no existe."}
    if accion in ("banear", "desbanear"):                        # ★ 20-nov: con duración y motivo obligatorio
        codigo, datos = (admin_banear(uid_admin, uid, [juego], detalle, duracion) if accion == "banear"
                         else admin_desbanear(uid_admin, uid, [juego]))
        if codigo != 200:
            return codigo, datos
        return 200, {"ok": True, "cuenta": _ficha(int(uid), juego)}
    rol = rol_de(uid_admin)
    if rol is None:
        return 401, {"error": "Tiene que entrar con una cuenta ADMIN o MODERADOR."}
    if rol != "admin":
        asignados = juegos_de_moderador(uid_admin)
        if asignados is None and accion not in ACCIONES_MODERADOR:
            return 403, {"error": "Los moderadores sólo pueden aprobar o quitar."}
        if accion not in ACCIONES_MODERADOR_ASIGNADO:
            return 403, {"error": "Los moderadores no pueden hacer eso."}
        if not puede_en(uid_admin, juego):
            return 403, {"error": "Ese juego no está asignado a tu cuenta."}
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return 400, {"error": "Cuenta inválida."}
    if not _login_de(uid):
        return 404, {"error": "Esa cuenta no existe."}
    if rol != "admin" and rol_de(uid) is not None:
        return 403, {"error": "Esa cuenta la maneja un ADMIN."}
    quien = _login_de(uid_admin) or f"uid {uid_admin}"
    detalle = str(detalle or "").strip()[:200]
    with _escribir:
        c = _propia()
        if accion == "aprobar":
            c.execute("INSERT OR REPLACE INTO aprobados VALUES (?, ?, ?, ?, ?)", (uid, juego, _ahora_txt(), quien, detalle))
        elif accion == "quitar":
            c.execute("DELETE FROM aprobados WHERE uid = ? AND juego = ?", (uid, juego))
        else:
            return 400, {"error": "Acción desconocida."}
        c.commit()
    _auditar(uid_admin, accion, uid, juego, detalle)
    _log(f"panel: {quien} -> {accion} uid={uid} en {juego}")
    return 200, {"ok": True, "cuenta": _ficha(uid, juego)}


def _archivo_panel(nombre):
    with open(os.path.join(_DIR_AQUI, nombre), "rb") as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  HTTP
# ══════════════════════════════════════════════════════════════════════════════════════════════
class _Manejador(BaseHTTPRequestHandler):
    server_version = "r2beat-portero"
    sys_version = ""

    def handle(self):
        # ★ 20-nov: cada conexión HTTP corre en SU hilo (ThreadingHTTPServer) y abre sus conexiones a las bases: al
        #   terminar se cierran, siempre (ver `cerrar_conexiones`).
        try:
            super().handle()
        finally:
            cerrar_conexiones()

    def log_message(self, *_a):          # el log lo lleva `_log`, sin la línea por pedido
        pass

    def _ip(self):
        ip = self.client_address[0]
        if es_proxy(ip):                 # detrás de Caddy (por omisión: sólo 127.0.0.1; ver `R2_PORTERO_PROXIES`)
            ip = (self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For", "").split(",")[0]
                  or ip).strip()
        return ip[:64]

    def _token(self):
        a = self.headers.get("Authorization") or ""
        return a[7:].strip() if a.startswith("Bearer ") else ""

    def _ficha_interna(self):
        return (self._token()
                or (self.headers.get("X-Ficha-Interna") or "").strip()
                or (self.headers.get("X-R2-Ficha") or "").strip()
                or (self.headers.get("Authorization") or "").strip())

    def _partes(self):
        ruta = self.path.split("?", 1)[0].strip("/").split("/")
        if ruta and ruta[0] == "cuentas":
            ruta = ruta[1:]
        return [p for p in ruta if p]

    def _mandar(self, codigo, datos, cache="private, no-store", tipo=None, extra=()):
        cuerpo = datos if isinstance(datos, bytes) else json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo or "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in extra:
            self.send_header(k, v)
        try:
            self.end_headers()
            self.wfile.write(cuerpo)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # ★ 22-nov: el que preguntó ya colgó (casi siempre el launcher que se cierra en medio de la espera larga
            #   del chat, `social/esperar`). No hay a quién contestarle: antes esto subía, el `except` de do_POST
            #   intentaba un 500 al mismo socket muerto y dejaba DOS tracebacks — 724 en un día, todos ruido.
            self.close_connection = True

    # ---- ★ el panel ----
    _SEGURIDAD = (("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"),
                  ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                              "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"))

    _SEGURIDAD_OAUTH = (("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"),
                        ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"))

    def _cookie_admin(self):
        for trozo in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = trozo.strip().partition("=")
            if k == COOKIE_ADMIN:
                return v
        return ""

    def _poner_cookie(self, token, segundos):
        return ("Set-Cookie", f"{COOKIE_ADMIN}={token}; Path=/; Max-Age={segundos}; HttpOnly; Secure; SameSite=Strict")

    def _get_admin(self, p):
        if p == ["admin"]:
            if self.path.split("?", 1)[0].endswith("/"):           # «/admin/» -> «/admin»: las rutas del .js son relativas
                ruta = self.path.split("?", 1)[0].rstrip("/")
                return self._mandar(301, b"", extra=(("Location", ruta),))
            return self._mandar(200, _archivo_panel("portero_panel.html"), tipo="text/html; charset=utf-8",
                                extra=self._SEGURIDAD)
        if p == ["admin", "panel.js"]:
            return self._mandar(200, _archivo_panel("portero_panel.js"), tipo="text/javascript; charset=utf-8",
                                extra=self._SEGURIDAD)
        uid = admin_de(self._cookie_admin())
        if not uid:
            return self._mandar(401, {"error": "Tiene que entrar con una cuenta ADMIN."})
        rol = rol_de(uid) or "moderador"
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}
        if p == ["admin", "invitaciones"]:                            # ★ 18-nov: todas las pendientes
            fs = [f for f in LZ.pendientes(sys.modules[__name__]) if puede_en(uid, f["juego"])]
            if rol != "admin":
                for f in fs:
                    if rol_de(f["uid"]) == "admin":
                        f["usuario"] = "ADMIN"
            return self._mandar(200, {"invitaciones": fs})
        if p == ["admin", "invitacion"]:                              # ★ 18-nov: la solicitud que llegó por Discord
            try:
                f = LZ.ficha(sys.modules[__name__], int(q.get("id") or 0))
            except ValueError:
                f = None
            if not f:
                return self._mandar(404, {"error": "Esa solicitud no existe."})
            if rol != "admin" and rol_de(f["uid"]) == "admin":
                f["usuario"] = "ADMIN"
            return self._mandar(200, {"invitacion": f})
        juego = q.get("juego") or "eda"
        juegos = _juegos()
        if juego not in juegos:
            return self._mandar(404, {"error": "Ese juego no existe."})
        if p == ["admin", "yo"]:
            return self._mandar(200, {"admin": _login_de(uid), "rol": rol,
                                      "juegos": {j: d["nombre"] for j, d in juegos.items()}})
        if p == ["admin", "lista"]:
            return self._mandar(*admin_lista(juego, rol))
        if p == ["admin", "buscar"]:
            return self._mandar(*admin_buscar(q.get("q"), juego, rol))
        return self._mandar(404, {"error": "no existe"})

    def _post_admin(self, p, d):
        if p == ["admin", "entrar"]:
            codigo, datos, token = admin_entrar(d.get("usuario"), d.get("clave"), self._ip())
            extra = (self._poner_cookie(token, ADMIN_HORAS * 3600),) if token else ()
            return self._mandar(codigo, datos, extra=extra)
        if p == ["admin", "salir"]:
            admin_salir(self._cookie_admin())
            return self._mandar(200, {"ok": True}, extra=(self._poner_cookie("", 0),))
        uid = admin_de(self._cookie_admin())
        if not uid:
            return self._mandar(401, {"error": "Tiene que entrar con una cuenta ADMIN."})
        if p == ["admin", "invitacion"]:                              # ★ 18-nov: aprobar / rechazar (por POST, con X-R2)
            return self._mandar(*LZ.decidir(sys.modules[__name__], uid, d.get("id"), str(d.get("accion") or "")))
        if len(p) == 2 and p[1] in ("aprobar", "quitar", "banear", "desbanear"):
            return self._mandar(*admin_accion(uid, p[1], d.get("uid"), str(d.get("juego") or "eda"), d.get("detalle"), d))
        return self._mandar(404, {"error": "no existe"})

    def do_GET(self):
        try:
            p = self._partes()
            if p and p[0] == "admin":
                return self._get_admin(p)
            if p and p[0] == CO.PREFIJO:                             # ★ 19-nov: el panel del Coordinador
                return CO.atender(sys.modules[__name__], self, "GET", p[1:], None)
            if p == ["salud"]:
                return self._mandar(200, {"ok": True})
            # ★ 16-nov: Google y Discord (servidor/vinculos.py)
            if p == ["oauth", "proveedores"]:
                return self._mandar(200, {"proveedores": V.proveedores() if es_duena() else {}})
            if len(p) == 3 and p[:2] == ["oauth", "ir"]:
                url = V.url_proveedor(p[2]) if es_duena() else None
                if not url:
                    return self._mandar(400, V.pagina("El pedido venció", "Vuelva al launcher e inténtelo de nuevo."),
                                        tipo="text/html; charset=utf-8", extra=self._SEGURIDAD_OAUTH)
                return self._mandar(302, b"", extra=(("Location", url), ("Referrer-Policy", "no-referrer")))
            if p == ["oauth", "vuelta"] and es_duena():
                q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}
                codigo, cuerpo = V.vuelta_de(sys.modules[__name__], q, al_panel=lambda f, r, a: CO.al_volver(sys.modules[__name__], f, r, a))
                if codigo == 302:                                    # ★ 19-nov: el ingreso al Coordinador (ticket)
                    return self._mandar(302, b"", extra=(("Location", cuerpo), ("Referrer-Policy", "no-referrer")))
                return self._mandar(codigo, cuerpo, tipo="text/html; charset=utf-8", extra=self._SEGURIDAD_OAUTH)
            if p == ["oauth", "vinculos"] and es_duena():
                return self._mandar(*V.lista(sys.modules[__name__], self._token()))
            if p == ["clave-publica"]:
                return self._mandar(200, jwks(), cache="public, max-age=300")
            if p == ["lanzamientos"] and es_duena():                 # ★ 18-nov: el contenido dinámico (sesión opcional)
                return self._mandar(*LZ.lista(sys.modules[__name__], self._token()))
            if p == ["yo"]:
                uid = sesion_de(self._token())
                if not uid:
                    return self._mandar(401, {"error": "Tienes que iniciar sesión."})
                return self._mandar(200, {"uid": uid, "juegos": juegos_de(uid)})
            if len(p) == 3 and p[0] == "juego" and p[2] == "personajes":
                uid = sesion_de(self._token())
                if not uid:
                    return self._mandar(401, {"error": "Tienes que iniciar sesión."})
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, keep_blank_values=True)
                return self._mandar(*GE.personajes_launcher(uid, p[1], q.get("entorno", ["live"])[0]))
            if len(p) == 2 and p[0] == "manifiesto":
                return self._mandar(*manifiesto(self._token(), p[1]))
            if p == ["interno", "enlaces"]:
                return self._mandar(*enlaces_internos(self._ficha_interna()))
            if len(p) == 3 and p[0] == "interno" and p[1] == "usuario":
                return self._mandar(*usuario_interno(urllib.parse.unquote(p[2]), self._ficha_interna()))
            if ((len(p) == 3 and p[0] == "interno" and p[1] == "cuenta")
                    or (len(p) == 2 and p[0] in ("interno", "cuenta"))):
                return self._mandar(*cuenta_interna(p[-1], self._ficha_interna()))
            if p in (["interno"], ["interno", "cuenta"], ["cuenta"]):
                q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}
                return self._mandar(*cuenta_interna(q.get("uid"), self._ficha_interna()))
            return self._mandar(404, {"error": "no existe"})
        except Exception as e:                                   # noqa: BLE001 — un pedido no tumba al portero
            _log(f"⚠ GET {self.path}: {e!r}")
            return self._mandar(500, {"error": "error interno"})

    def do_POST(self):
        try:
            if self.headers.get("X-R2") != "1":
                return self._mandar(403, {"error": "pedido no permitido"})
            largo = int(self.headers.get("Content-Length") or 0)
            p = self._partes()
            tope = CUERPO_PAGINA_MAX if p == [CO.PREFIJO, "api", "pagina"] else CUERPO_MAX
            if largo < 0 or largo > tope:
                return self._mandar(413, {"error": "pedido demasiado grande"})
            try:
                d = json.loads(self.rfile.read(largo).decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                return self._mandar(400, {"error": "pedido mal armado"})
            if not isinstance(d, dict):
                return self._mandar(400, {"error": "pedido mal armado"})
            p = self._partes()
            if p and p[0] == "admin":
                return self._post_admin(p, d)
            if p and p[0] == CO.PREFIJO:                             # ★ 19-nov: el panel del Coordinador
                return CO.atender(sys.modules[__name__], self, "POST", p[1:], d)
            if p == ["interno", "cuenta"]:
                return self._mandar(*admin_interno_crear(
                    d.get("usuario"), d.get("pass_sha256_upper"), self._ficha_interna()))
            if len(p) == 4 and p[0] == "interno" and p[1] == "cuenta" and p[3] == "estado":
                return self._mandar(*admin_interno_estado(
                    p[2], d.get("estado"), d.get("motivo"), self._ficha_interna()))
            if len(p) == 4 and p[0] == "interno" and p[1] == "cuenta" and p[3] == "comprobar-clave":
                return self._mandar(*interno_comprobar_clave(
                    p[2], d.get("pass_sha256_upper"), self._ficha_interna()))
            if len(p) == 4 and p[0] == "interno" and p[1] == "cuenta" and p[3] == "clave":
                return self._mandar(*admin_interno_clave(
                    p[2], d.get("pass_sha256_upper"), self._ficha_interna()))
            if p == ["entrar"]:
                return self._mandar(*entrar(d.get("usuario"), d.get("clave"), d.get("pass_sha256_upper"),
                                            self._ip()))
            if p == ["registrar"]:
                return self._mandar(*registrar(d.get("usuario"), d.get("clave"), d.get("pass_sha256_upper"),
                                               self._ip()))
            if p in (["cambiar-clave"], ["cambiar_clave"]):
                tok = self._token() or str(d.get("sesion") or "").strip()
                c_act = (d.get("clave_actual") if "clave_actual" in d
                         else (d.get("actual") if "actual" in d else d.get("vieja")))
                c_nva = (d.get("clave_nueva") if "clave_nueva" in d
                         else (d.get("nueva") if "nueva" in d else d.get("clave")))
                h_act = (d.get("actual_sha256_upper") or d.get("pass_actual_sha256_upper")
                         or d.get("vieja_sha256_upper") or d.get("pass_sha256_upper"))
                h_nva = d.get("nueva_sha256_upper") or d.get("pass_nueva_sha256_upper")
                return self._mandar(*cambiar_clave(tok, c_act, c_nva, h_act, h_nva, self._ip()))
            if p == ["pase"]:
                return self._mandar(*pedir_pase(self._token(), str(d.get("juego") or ""), self._ip()))
            if p == ["invitacion"] and es_duena():                   # ★ 18-nov: pedir la invitación anticipada
                return self._mandar(*LZ.pedir(sys.modules[__name__], self._token(), d.get("juego")))
            # ★ 16-nov: amigos, estado y chat (servidor/social.py)
            if len(p) == 2 and p[0] == "social" and es_duena():
                yo, tok = sys.modules[__name__], self._token()
                accion = {
                    "estado": lambda: SO.estado(yo, tok, d.get("desde"), d.get("juego")),
                    "apodo": lambda: SO.poner_apodo(yo, tok, d.get("apodo")),
                    "pedir": lambda: SO.pedir(yo, tok, d.get("quien")),
                    "responder": lambda: SO.responder(yo, tok, d.get("uid"), bool(d.get("aceptar"))),
                    "quitar": lambda: SO.quitar(yo, tok, d.get("uid")),
                    "enviar": lambda: SO.enviar(yo, tok, d.get("para"), d.get("texto")),
                    "chat": lambda: SO.chat(yo, tok, d.get("con")),
                    "leido": lambda: SO.leido(yo, tok, d.get("con")),
                    "esperar": lambda: SO.esperar(yo, tok, d.get("desde")),     # ★ 18-nov: la espera larga
                }.get(p[1])
                return self._mandar(*(accion() if accion else (404, {"error": "no existe"})))
            # ★ 16-nov: Google y Discord (servidor/vinculos.py)
            if p == ["oauth", "iniciar"]:
                return self._mandar(*V.iniciar(sys.modules[__name__], str(d.get("proveedor") or ""),
                                               str(d.get("modo") or "entrar"), self._token(), self._ip()))
            if p == ["oauth", "estado"]:
                return self._mandar(*V.estado(d.get("sid"), self._ip()))
            if p == ["oauth", "registrar"] and es_duena():
                return self._mandar(*V.registrar(sys.modules[__name__], d.get("sid"), d.get("usuario"), self._ip()))
            if p == ["oauth", "desvincular"] and es_duena():
                return self._mandar(*V.desvincular(sys.modules[__name__], self._token(), str(d.get("proveedor") or "")))
            if p == ["salir"]:
                salir(self._token())
                return self._mandar(200, {"ok": True})
            return self._mandar(404, {"error": "no existe"})
        except Exception as e:                                   # noqa: BLE001
            _log(f"⚠ POST {self.path}: {e!r}")
            return self._mandar(500, {"error": "error interno"})


def servidor(puerto=None):
    """El servidor HTTP (sin arrancar el bucle). Comprueba ANTES que las bases y la clave abran."""
    if es_duena():
        _cuentas()
    else:
        if not os.path.isfile(ruta_base_juego()):
            raise SystemExit(f"⛔ no encuentro la base del juego: {ruta_base_juego()}")
        _juego().execute("SELECT COUNT(*) FROM users").fetchone()
    _propia()
    clave()
    return ThreadingHTTPServer((HOST, PUERTO if puerto is None else puerto), _Manejador)


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  La consola: importar cuentas, administrar cuentas en `cuentas.db` y la lista de aprobados
# ══════════════════════════════════════════════════════════════════════════════════════════════
def _desarmar_pass_hash(pass_hash):
    """Separa los prefijos ('BANNED:', 'FUSIONADA:') del SHA-256 en hex mayúscula. -> (estado, hash_upper)."""
    h = str(pass_hash or "").strip()
    baneada = False
    fusionada = False
    while True:
        u = h.upper()
        if u.startswith("BANNED:"):
            baneada = True
            h = h[7:].strip()
        elif u.startswith("FUSIONADA:"):
            fusionada = True
            h = h[10:].strip()
        else:
            break
    estado = "baneada" if baneada else ("fusionada" if fusionada else "activa")
    return estado, h.upper()


def _traducir_portero(p, mapa_importadas, uids_cuentas):
    """Traduce una sola vez `aprobados`/`baneos` de `uid_viejo` a Eñeños ID y limpia sesiones/pases viejos."""
    ya_trad = {int(r[0]) for r in p.execute("SELECT uid_viejo FROM traducciones_uid").fetchall()}
    pend = {uv: un for uv, un in mapa_importadas.items() if uv not in ya_trad and uv != un}
    traducidos = 0
    if pend:
        for tabla in ("aprobados", "baneos"):
            for fila in p.execute(f"SELECT * FROM {tabla}").fetchall():
                uv = int(fila["uid"])
                if uv in pend:
                    un = pend[uv]
                    p.execute(f"DELETE FROM {tabla} WHERE uid = ? AND juego = ?", (uv, fila["juego"]))
                    p.execute(f"INSERT OR IGNORE INTO {tabla} VALUES ({', '.join('?' * len(fila))})",
                              (un, *tuple(fila)[1:]))
                    traducidos += 1
        for uv, un in pend.items():
            p.execute("INSERT OR IGNORE INTO traducciones_uid (uid_viejo, uid_nuevo) VALUES (?, ?)", (uv, un))
    for tabla in ("sesiones", "pases"):
        for fila in p.execute(f"SELECT DISTINCT uid FROM {tabla}").fetchall():
            u = int(fila[0]) if fila[0] is not None else None
            if u in pend or (u is not None and u not in uids_cuentas):
                p.execute(f"DELETE FROM {tabla} WHERE uid = ?", (u,))
    return traducidos


def importar_cuentas(ruta_vieja, quien="consola"):
    """Copia las cuentas de una `datos.db` vieja (abierta en SÓLO LECTURA) a `cuentas.db`, asignando Eñeños IDs
    secuenciales desde `UID_NUEVAS_DESDE` (`ORDER BY rowid`) y guardando `uid_viejo -> Eñeños ID` en `importadas`.
    Traduce una vez `aprobados`/`baneos` en `portero.db` y borra sesiones/pases viejos. Idempotente. ⛔ Sin hashes."""
    ruta_abs = os.path.abspath(str(ruta_vieja or ""))
    if not os.path.isfile(ruta_abs):
        raise SystemExit(f"⛔ no encuentro la base a importar: {ruta_abs}")
    url = "file:" + urllib.request.pathname2url(ruta_abs) + "?mode=ro"
    origen = sqlite3.connect(url, uri=True, timeout=10)
    origen.row_factory = sqlite3.Row
    try:
        origen.execute("PRAGMA query_only = 1")
        cols = {r[1] for r in origen.execute("PRAGMA table_info(users)").fetchall()}
        if not {"uid", "username", "pass_hash"}.issubset(cols):
            raise SystemExit(f"⛔ {ruta_abs} no tiene la tabla users(uid, username, pass_hash)")
        col_fecha = "reg_time" if "reg_time" in cols else "NULL AS reg_time"
        filas = origen.execute(f"SELECT uid, username, pass_hash, {col_fecha} FROM users ORDER BY rowid").fetchall()
    finally:
        origen.close()
    copiadas = 0
    ya_estaban = 0
    baneadas = 0
    fusionadas = 0
    ahora = _ahora_txt()
    with _escribir:
        c = _cuentas()
        for r in filas:
            uid_viejo = int(r["uid"])
            usuario = str(r["username"] or "")
            if not usuario:
                continue
            estado, hash_upper = _desarmar_pass_hash(r["pass_hash"])
            if estado == "baneada":
                baneadas += 1
            elif estado == "fusionada":
                fusionadas += 1
            ya = c.execute("SELECT uid FROM cuentas WHERE usuario = ? COLLATE BINARY", (usuario,)).fetchone()
            if ya:
                c.execute("INSERT OR IGNORE INTO importadas (uid_viejo, uid, usuario) VALUES (?, ?, ?)",
                          (uid_viejo, int(ya[0]), usuario))
                ya_estaban += 1
                continue
            if not _es_sha256_hex(hash_upper):
                raise SystemExit(f"⛔ la cuenta uid={uid_viejo} ({usuario}) no tiene un SHA-256 de 64 hex válido")
            envuelta = envolver_hash(hash_upper)
            creada = str(r["reg_time"] or "").strip() or ahora
            enenos_id = _siguiente_uid(c)
            c.execute("INSERT INTO cuentas (uid, usuario, clave, estado, creada) VALUES (?, ?, ?, ?, ?)",
                      (enenos_id, usuario, envuelta, estado, creada))
            c.execute("INSERT OR IGNORE INTO importadas (uid_viejo, uid, usuario) VALUES (?, ?, ?)",
                      (uid_viejo, enenos_id, usuario))
            copiadas += 1
        c.commit()
        mapa_importadas = {int(x[0]): int(x[1]) for x in c.execute("SELECT uid_viejo, uid FROM importadas").fetchall()}
        uids_cuentas = {int(x[0]) for x in c.execute("SELECT uid FROM cuentas").fetchall()}
        p = _propia()
        traducidos = _traducir_portero(p, mapa_importadas, uids_cuentas)
        p.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                  (ahora, f"consola ({quien})", "importar", None, None,
                   f"copiadas={copiadas}, ya_estaban={ya_estaban}, baneadas={baneadas}, "
                   f"fusionadas={fusionadas}, traducidos={traducidos}"))
        p.commit()
        _admins["fecha"] = None
        _moderadores["fecha"] = None
    res = {"copiadas": copiadas, "ya_estaban": ya_estaban, "baneadas": baneadas,
           "fusionadas": fusionadas, "traducidos": traducidos}
    print(f"✔ importar: {copiadas} copiada(s), {ya_estaban} ya estaba(n), "
          f"{baneadas} baneada(s), {fusionadas} fusionada(s), {traducidos} registro(s) traducido(s).")
    return res


def exportar_traduccion(archivo=None):
    """Exporta `uid_viejo,enenos_id` en CSV desde `cuentas.importadas` (⛔ sin usuarios ni contraseñas)."""
    filas = _cuentas().execute("SELECT uid_viejo, uid FROM importadas ORDER BY uid, uid_viejo").fetchall()
    lineas = ["uid_viejo,enenos_id"] + [f"{int(r[0])},{int(r[1])}" for r in filas]
    csv_txt = "\n".join(lineas) + "\n"
    if archivo:
        ruta_out = os.path.abspath(str(archivo))
        with open(ruta_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(csv_txt)
        print(f"✔ traduccion: {len(filas)} fila(s) en {ruta_out}")
    else:
        sys.stdout.write(csv_txt)
    return [(int(r[0]), int(r[1])) for r in filas]


def _cuenta_en_duena(usuario):
    r = _cuentas().execute("SELECT uid, usuario, estado FROM cuentas WHERE usuario = ? COLLATE BINARY",
                           (str(usuario or ""),)).fetchone()
    if not r:
        raise SystemExit(f"⛔ no existe la cuenta «{usuario}» en cuentas.db (se compara exacto, con mayúsculas)")
    return r


def admin_poner_clave(usuario, clave_nueva, quien="consola"):
    """Pone una contraseña nueva a `usuario` en `cuentas.db` (ADMIN por consola). ⛔ No imprime ningún hash."""
    r = _cuenta_en_duena(usuario)
    uid = int(r["uid"])
    dado = _hash_de_entrada(clave_nueva, None)
    if not dado:
        raise SystemExit("⛔ la contraseña nueva no es válida")
    envuelta = envolver_hash(dado)
    with _escribir:
        cc = _cuentas()
        cc.execute("UPDATE cuentas SET clave = ? WHERE uid = ?", (envuelta, uid))
        cc.commit()
        cp = _propia()
        cp.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                   (_ahora_txt(), f"consola ({quien})", "cambiar-clave", uid, None, ""))
        cp.commit()
    print(f"✔ cambiar-clave: uid {uid} ({r['usuario']}).")


# ★ 20-nov (Eñeños: «quiero cambiar una contraseña de un jugador en el Coordinador»): sin consola ni contraseñas escritas
#   a mano. La genera el server al azar, se la muestra UNA vez al admin (que se la pasa al jugador) y el jugador la
#   cambia después en el launcher. ⛔ No va a ningún log ni a la auditoría: la auditoría dice quién y a quién.
_LETRAS_PROVISORIA = "abcdefghjkmnpqrstuvwxyz23456789"     # (sin l/1/i/o/0: se dicta por chat sin confundirse)


def admin_restablecer_clave(uid_admin, uid):
    """ADMIN (o un MODERADOR con el permiso «clave» de toda la red, ★ 21-nov): una contraseña PROVISORIA al azar para la
    cuenta `uid`, y se cierran sus sesiones abiertas. ⛔ Un moderador nunca a una cuenta del equipo. (★ 21-nov, Eñeños:
    el moderador con este permiso SÍ recibe el login, para el jugador que olvidó también su usuario.)
    -> (200, {ok, uid, usuario?, clave}) · 403 sin permiso · 404 si la cuenta no existe."""
    rol = rol_de(uid_admin)
    if rol != "admin":
        from servidor import gestion as GE
        if rol != "moderador" or not GE.puede_red(sys.modules[__name__], uid_admin, "clave"):
            return 403, {"error": "Su cuenta no tiene el permiso de restablecer contraseñas."}
    if not es_duena():
        return 409, {"error": "Las contraseñas no las guarda este servidor."}
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return 400, {"error": "Falta la cuenta."}
    r = _cuentas().execute("SELECT uid, usuario FROM cuentas WHERE uid = ?", (uid,)).fetchone()
    if not r:
        return 404, {"error": "Esa cuenta no existe."}
    if rol != "admin" and rol_de(uid) is not None:
        return 403, {"error": "Esa cuenta es del equipo: sólo un Admin le restablece la contraseña."}
    clave_txt = "".join(secrets.choice(_LETRAS_PROVISORIA) for _ in range(10))
    envuelta = envolver_hash(_hash_de_entrada(clave_txt, None))
    with _escribir:
        cc = _cuentas()
        cc.execute("UPDATE cuentas SET clave = ? WHERE uid = ?", (envuelta, uid))
        cc.commit()
        cp = _propia()
        cp.execute("DELETE FROM sesiones WHERE uid = ?", (uid,))
        cp.commit()
    _auditar(uid_admin, "restablecer-clave", uid, None,
             "contraseña provisoria; sesiones cerradas" + ("" if rol == "admin" else " (moderador, permiso de la red)"))
    return 200, {"ok": True, "uid": uid, "usuario": r["usuario"], "clave": clave_txt}


def admin_estado_cuenta(usuario, nuevo_estado, motivo="", quien="consola"):
    """Banea ('baneada') o desbanea ('activa') una cuenta en `cuentas.db` (ADMIN por consola)."""
    if nuevo_estado not in ("activa", "baneada"):
        raise ValueError("estado inválido")
    r = _cuenta_en_duena(usuario)
    uid = int(r["uid"])
    if r["estado"] == "fusionada" and nuevo_estado == "activa":
        raise SystemExit(f"⛔ la cuenta «{usuario}» (uid {uid}) está fusionada, no baneada")
    accion = "banear" if nuevo_estado == "baneada" else "desbanear"
    with _escribir:
        cc = _cuentas()
        cc.execute("UPDATE cuentas SET estado = ? WHERE uid = ?", (nuevo_estado, uid))
        cc.commit()
        cp = _propia()
        if nuevo_estado == "baneada":
            cp.execute("DELETE FROM sesiones WHERE uid = ?", (uid,))
        cp.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                   (_ahora_txt(), f"consola ({quien})", accion, uid, None, str(motivo or "")[:200]))
        cp.commit()
    print(f"✔ {accion}: uid {uid} ({r['usuario']}) -> {nuevo_estado}.")


def _uid_de(usuario):
    r = cuenta(usuario)
    if not r:
        raise SystemExit(f"⛔ no existe la cuenta «{usuario}» (se compara exacto, con mayúsculas)")
    return int(r["uid"])


def _juego_valido(j):
    juegos = _juegos()
    if j not in juegos:
        raise SystemExit(f"⛔ juego desconocido «{j}». Conozco: {', '.join(juegos)}")
    return j


def consola(args):
    quien = os.environ.get("USER") or os.environ.get("USERNAME") or "consola"
    orden = args[0]
    if orden == "clave" and len(args) == 1:
        print(json.dumps(jwks(), indent=2))
        return
    if orden == "importar":
        if len(args) < 2:
            raise SystemExit("⛔ uso: python -m servidor.portero importar <ruta a datos.db>")
        return importar_cuentas(args[1], quien)
    if orden == "traduccion":
        return exportar_traduccion(args[1] if len(args) >= 2 else None)
    if orden == "importar-amigos":
        # ★ 18-nov: las amistades del R2Beat viejo, por Eñeños ID (después de `importar`). `--apodos`: a quien no
        #   tiene Ñ2-ID le pone el apodo de su personaje del casillero 1
        if len(args) < 2:
            raise SystemExit("⛔ uso: python -m servidor.portero importar-amigos <ruta a datos.db> [--apodos]")
        r = SO.importar_amistades(sys.modules[__name__], args[1], apodos="--apodos" in args)
        print("✔ amigos: " + ", ".join(f"{k}={v}" for k, v in r.items()))
        return r
    if orden in ("cambiar-clave", "poner-clave") or (orden == "clave" and len(args) >= 2):
        if len(args) < 3:
            raise SystemExit("⛔ uso: python -m servidor.portero cambiar-clave <usuario> <nueva_clave>")
        return admin_poner_clave(args[1], args[2], quien)
    if orden in ("banear-cuenta", "desbanear-cuenta"):
        if len(args) < 2:
            raise SystemExit(f"⛔ uso: python -m servidor.portero {orden} <usuario> [motivo…]")
        nuevo = "baneada" if orden == "banear-cuenta" else "activa"
        return admin_estado_cuenta(args[1], nuevo, " ".join(args[2:]), quien)
    if es_duena() and orden in ("banear", "desbanear") and len(args) >= 2 and (len(args) == 2 or args[2] not in _juegos()):
        nuevo = "baneada" if orden == "banear" else "activa"
        return admin_estado_cuenta(args[1], nuevo, " ".join(args[2:]), quien)
    if orden == "lista":
        juego = _juego_valido(args[1] if len(args) > 1 else "eda")
        c = _propia()
        for t in ("aprobados", "baneos"):
            filas = c.execute(f"SELECT uid, desde, quien FROM {t} WHERE juego = ? ORDER BY desde", (juego,)).fetchall()
            print(f"{t} en {juego}: {len(filas)}")
            for f in filas:
                nombre = _login_de(f["uid"])
                print(f"   uid {f['uid']:>6}  {nombre if nombre else '¿?':<20} desde {f['desde']}  ({f['quien']})")
        return
    if orden == "pase" and len(args) >= 2:
        # ★ SÓLO PRUEBAS: un pase real para una cuenta APROBADA, para probar el canje del otro juego sin el launcher.
        #   Vida a elección hasta 1 h (el normal dura 5 min). Queda en `pases` y en la auditoría.
        uid = _uid_de(args[1])
        juego = _juego_valido(args[2] if len(args) > 2 else "eda")
        vida = max(30, min(3600, int(args[3]) if len(args) > 3 else PASE_SEGUNDOS))
        if estado_r2beat(uid) != "ok" or not permitido(uid, juego):
            raise SystemExit(f"⛔ uid {uid} no está aprobada (o está baneada) en {juego}: no hay pase")
        ahora = int(time.time())
        pase, carga = emitir_pase(uid, juego, ahora, vida)
        with _escribir:
            c = _propia()
            c.execute("INSERT INTO pases (jti, uid, juego, emitido, ip) VALUES (?, ?, ?, ?, ?)",
                      (carga["jti"], uid, juego, ahora, "consola"))
            c.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                      (_ahora_txt(), f"consola ({quien})", "pase de prueba", uid, juego, f"{vida} s"))
            c.commit()
        print(pase)
        return
    if orden not in ("aprobar", "quitar", "banear", "desbanear") or len(args) < 2:
        raise SystemExit(__doc__.split("LA LISTA DE APROBADOS")[1].split("VARIABLES")[0])
    uid = _uid_de(args[1])
    juego = _juego_valido(args[2] if len(args) > 2 else "eda")
    resto = " ".join(args[3:])
    if orden == "banear":                    # ★ 20-nov: [--horas N | --dias N | --meses N] antes del motivo; sin eso, permanente
        dur, palabras = {}, list(args[3:])
        while palabras and palabras[0] in ("--horas", "--dias", "--meses", "--permanente"):
            k = palabras.pop(0)[2:]
            dur[k] = True if k == "permanente" else (palabras.pop(0) if palabras else "")
        dicha, seg, err = leer_duracion(dur)
        if err:
            raise SystemExit("⛔ " + err)
        resto = " ".join(palabras).strip() or "(sin motivo, por consola)"
        if len(resto) > BANEO_MOTIVO_MAX:
            raise SystemExit(f"⛔ el motivo tiene que tener {BANEO_MOTIVO_MAX} caracteres o menos")
        hasta = None if seg is None else int(time.time()) + seg
        resto_aud = f"{duracion_txt(seg)} · {resto}"
    with _escribir:
        c = _propia()
        if orden == "aprobar":
            c.execute("INSERT OR REPLACE INTO aprobados VALUES (?, ?, ?, ?, ?)", (uid, juego, _ahora_txt(), quien, resto))
        elif orden == "quitar":
            c.execute("DELETE FROM aprobados WHERE uid = ? AND juego = ?", (uid, juego))
        elif orden == "banear":
            c.execute("INSERT OR REPLACE INTO baneos (uid, juego, desde, quien, motivo, hasta) VALUES (?, ?, ?, ?, ?, ?)",
                      (uid, juego, _ahora_txt(), quien, resto, hasta))
            resto = resto_aud
        else:                                # (desbanear: vence ahora; la fila queda como historial)
            ya = int(time.time())
            c.execute("UPDATE baneos SET hasta = ? WHERE uid = ? AND juego = ? AND (hasta IS NULL OR hasta > ?)",
                      (ya, uid, juego, ya))
        c.execute("INSERT INTO auditoria (cuando, quien, accion, uid, juego, detalle) VALUES (?, ?, ?, ?, ?, ?)",
                  (_ahora_txt(), f"consola ({quien})", orden, uid, juego, resto[:200]))
        c.commit()
    print(f"✔ {orden}: uid {uid} en {juego}. Ahora: {'PUEDE' if permitido(uid, juego) else 'NO puede'} entrar.")


def main(args=None):
    args = sys.argv[1:] if args is None else args
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                        # noqa: BLE001
            pass
    if args:
        return consola(args)
    srv = servidor()
    origen_txt = (f"base de cuentas (dueña): {ruta_base_cuentas()}" if es_duena()
                  else f"base del juego (sólo lectura): {ruta_base_juego()}")
    _log(f"escuchando en http://{HOST}:{srv.server_address[1]}/  · {origen_txt} · "
         f"juegos: {', '.join(_juegos())} · kid {clave()[2]}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        _log("cortado a mano")


if __name__ == "__main__":
    main()
