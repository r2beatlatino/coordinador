#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""probar_contenedores — R2Beat 2013 y el servicio de cuentas, cada uno en su contenedor. 14-nov-2026.

La guía: documentacion/TOPOLOGIA_CONTENEDORES.md. Los archivos: herramientas/contenedores/.

    python pruebas/probar_contenedores.py              PARTE A: lo que se puede probar sin Docker (el banco corre esto)
    python3 pruebas/probar_contenedores.py --docker    PARTE A + PARTE B: construye, levanta, apaga, muda
    python3 pruebas/probar_contenedores.py --docker --plataforma linux/arm64
                                                       lo mismo con las imágenes de OTRA arquitectura (prod es ARM).
                                                       Pide emulación en la máquina (`qemu-user-binfmt`) y va lento.
    python3 pruebas/probar_contenedores.py --docker --imagenes <la del juego> <la de cuentas>
                                                       NO construye: prueba las imágenes que ya están en la máquina con
                                                       esos nombres (las BAJADAS del registro). Se combina con --plataforma.

⚠ LA PARTE B NO LA CORRE EL BANCO: necesita Docker y tarda minutos. En esta PC Docker vive DENTRO del WSL:

    wsl -d Ubuntu-26.04 -u root -- bash -lc "cd '/mnt/c/…/Servidor R2Beat 2013' && python3 pruebas/probar_contenedores.py --docker"

  Sin `--docker` lo dice bien claro al final («PARTE B NO CORRIDA»): un verde de la parte A no prueba los contenedores.

QUÉ PRUEBA LA PARTE B, cada cosa con su CONTROL AL REVÉS (⟲)
  1 · las dos imágenes construyen y NO traen ni una base, ni una clave, ni un gm.txt ⟲ el buscador sí encuentra una plantada
  2 · el juego escucha en los 12 puertos medidos y sólo escribe en su volumen ⟲ escribir fuera del volumen REBOTA
  3 · con los dos arriba: el login de prueba entra y el pase firmado verifica ⟲ clave mala, vcode ajeno, cuenta no
      aprobada y pase tocado, no
  4 · se apaga el JUEGO: cuentas sigue dando pases (y hasta se reinicia sola) ⟲ el juego de verdad no contesta
  5 · se apaga CUENTAS: el que ya estaba en un canal sigue atendido y entran jugadores nuevos ⟲ cuentas de verdad no contesta
  6 · el estado sobrevive a reiniciar cada contenedor (la sesión del juego, la sesión del portero)
  7 · MUDANZA: exportar en caliente, bajar todo, borrar las imágenes, importar en una carpeta limpia con OTRO nombre de
      proyecto: las cuentas entran con la misma clave y el mismo uid, y el pase verifica con la clave pública DE ANTES
      ⟲ sin importar, la cuenta no existe y la clave es otra · ⟲ un paquete dañado se rechaza · ⟲ no pisa un volumen con base
  8 · por qué el volumen del juego no se monta `:ro` en cuentas (medido) ⟲ con `rw` anda

★ EN EL COORDINADOR (19-nov): la imagen del JUEGO, `bot_carga.py` y `sembrar_prueba.py` son del repo del R2Beat 2013.
  La parte A corre sola acá. La parte B pide además `R2BEAT2013_REPO=<una copia de ese repo>` y la imagen del juego
  ya armada allá: `--imagenes <la del juego> <la de cuentas>` (este repo no construye la del juego).

⛔ Todo con cuentas inventadas (`prueba1`…) y una clave sorteada en cada corrida. Usa proyectos `enenos-prueba-*` y
   borra SÓLO esos al terminar. Ocupa los puertos de verdad (48004…, 48190, 48195) en 127.0.0.1: si ya hay un server
   escuchando ahí DENTRO de la máquina de Docker, se niega a empezar.
"""
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONT = os.path.join(RAIZ, "herramientas", "contenedores")
sys.path.insert(0, RAIZ)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                    # noqa: BLE001
        pass

fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que, flush=True)
    if not cond:
        fallos.append(que)
    return bool(cond)


def titulo(t):
    print("\n" + t, flush=True)


def _modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  PARTE A — sin Docker
# ══════════════════════════════════════════════════════════════════════════════════════════════
def parte_a():
    from servidor import portero

    titulo("A1 · a quién se le cree la IP del jugador (R2_PORTERO_PROXIES / R2_API_PROXIES)")
    ok(portero.es_proxy("127.0.0.1") and portero.es_proxy("::1"), "por omisión, el proxy es sólo esta máquina")
    ok(not portero.es_proxy("172.18.0.1") and not portero.es_proxy("8.8.8.8"),
       "⟲ por omisión NO se le cree a la red de Docker ni a internet")
    redes = portero._redes("127.0.0.1, ::1, 172.16.0.0/12")
    ok(portero.es_proxy("172.18.0.1", redes) and portero.es_proxy("::ffff:172.18.0.1", redes),
       "con la red de Docker declarada, la puerta 172.18.0.1 sí es el proxy")
    ok(not portero.es_proxy("8.8.8.8", redes) and not portero.es_proxy("no-es-una-ip", redes),
       "⟲ y aun así un vecino de afuera (o una basura) no")
    ok(portero._redes("cualquier cosa, 300.1.1.1") == [], "⟲ una lista que no se entiende no le cree a NADIE")

    titulo("A2 · sin las variables nuevas, el portero escucha donde siempre (127.0.0.1)")
    tmp = tempfile.mkdtemp(prefix="cont_a_")
    try:
        base_env = {k: v for k, v in os.environ.items() if not k.startswith("R2_")}
        base_env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", R2_LOG=os.path.join(tmp, "x.log"),
                        R2_BASE=os.path.join(tmp, "datos.db"))
        # (coordinador: `api_web` es del juego y se prueba en su repo; acá, el portero)
        cod = ("import sys; sys.path.insert(0, sys.argv[1]); from servidor import portero; "
               "print(portero.HOST, portero.es_proxy('172.18.0.1'))")

        def hosts(**extra):
            r = subprocess.run([sys.executable, "-X", "utf8", "-c", cod, RAIZ], capture_output=True, text=True,
                               env=dict(base_env, **extra), cwd=tmp, encoding="utf-8", errors="replace")
            return r.stdout.strip().split()[-2:] if r.returncode == 0 else ["ERROR", r.stderr[-200:]]

        ok(hosts() == ["127.0.0.1", "False"], "portero: 127.0.0.1 y sin proxies de más")
        ok(hosts(R2_PORTERO_HOST="0.0.0.0", R2_PORTERO_PROXIES="127.0.0.1,172.16.0.0/12")
           == ["0.0.0.0", "True"], "⟲ con las variables (lo que pone la imagen) escucha en 0.0.0.0")

        titulo("A3 · ni una IP ni un dominio clavados en los archivos de los contenedores")
        ip = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        permitidas = {"127.0.0.1", "0.0.0.0", "172.16.0.0"}            # esta máquina, «todas», y la red privada de Docker
        dominio = re.compile(r"\b[\w-]+\.(?:com|link|net|org|io)\b", re.I)
        archivos = ["docker-compose.yml", "docker-compose.red-host.yml", "ejemplo.env"] + [
            f"{n}.Dockerfile{x}" for n in ("cuentas", "parches", "puerta") for x in ("", ".dockerignore")]
        clavadas = []
        for n in archivos:
            t = open(os.path.join(CONT, n), encoding="utf-8").read()
            clavadas += [f"{n}: {x}" for x in ip.findall(t) if x not in permitidas]
            clavadas += [f"{n}: {x}" for x in dominio.findall(t)]
        ok(not clavadas, f"los {len(archivos)} archivos no nombran ninguna máquina (encontradas: {clavadas})")
        ok(ip.findall("server 161.153.192.100") == ["161.153.192.100"] and dominio.findall("ir a r2beatlatino.com"),
           "⟲ el buscador sí caza una IP y un dominio de verdad")
        compose = open(os.path.join(CONT, "docker-compose.yml"), encoding="utf-8").read()
        ok("depends_on" not in compose.split("services:", 1)[1],
           "ningún servicio depende de otro para arrancar (no hay depends_on)")
        for n in ("cuentas", "parches", "puerta"):
            lista = [x.strip() for x in open(os.path.join(CONT, f"{n}.Dockerfile.dockerignore"), encoding="utf-8")
                     if x.strip() and not x.startswith("#")]
            ok(lista[0] == "*", f"{n}: la lista de lo que entra a la imagen es BLANCA (arranca negando todo)")

        titulo("A3b · la imagen de cuentas lleva todo lo que el portero importa")
        blanca = {x.strip()[1:] for x in open(os.path.join(CONT, "cuentas.Dockerfile.dockerignore"), encoding="utf-8")
                  if x.startswith("!servidor/")}
        df = open(os.path.join(CONT, "cuentas.Dockerfile"), encoding="utf-8").read()
        copia = set(re.findall(r"servidor/[\w.]+", df.split("COPY", 1)[1].split("ENV", 1)[0]))
        importa = lambda ruta: {"servidor/%s.py" % m for m in re.findall(
            r"^\s*from \. import (\w+)", open(ruta, encoding="utf-8").read(), re.M)}
        hace_falta, vistos = {"servidor/portero.py"}, set()
        while hace_falta - vistos:
            m = sorted(hace_falta - vistos)[0]
            vistos.add(m)
            hace_falta |= importa(os.path.join(RAIZ, m))
        ok(hace_falta <= blanca and hace_falta <= copia,
           f"cada módulo que el portero importa va en la lista blanca y en el COPY (faltan: {sorted(hace_falta - (blanca & copia))})")
        ok(blanca == copia, f"la lista blanca y el COPY dicen lo mismo ({sorted(blanca ^ copia)})")
        sin_lz = copia - {"servidor/lanzamientos.py"}
        ok(hace_falta - (blanca & sin_lz) == {"servidor/lanzamientos.py"},
           "⟲ con el COPY de antes (sin lanzamientos.py: así estaba hasta el 19-nov) el chequeo lo caza")

        titulo("A4 · mudanza.py: el paquete de una instalación SIN contenedores (la carpeta de prod de hoy)")
        mud = _modulo("mudanza", os.path.join(CONT, "mudanza.py"))
        vieja = os.path.join(tmp, "game2013")
        os.makedirs(os.path.join(vieja, "servidor"))
        c = sqlite3.connect(os.path.join(vieja, "datos.db"))
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, username TEXT, pass_hash TEXT)")
        c.executemany("INSERT INTO users VALUES (?, ?, ?)", [(i, f"prueba{i}", "X" * 64) for i in range(1, 8)])
        c.commit()                                         # ⚠ SIN cerrar: las 7 filas están sólo en el -wal, como en un server vivo
        open(os.path.join(vieja, "gm.txt"), "w").write("prueba1\n")            # en prod gm.txt está en la RAÍZ
        open(os.path.join(vieja, "sesiones.json"), "w").write("{}")
        open(os.path.join(vieja, "status.json"), "w").write("{}")
        antes = {n: hashlib.md5(open(os.path.join(vieja, n), "rb").read()).hexdigest() for n in ("datos.db", "datos.db-wal")}
        dest = os.path.join(tmp, "mudanza")
        mud.main(["desde-carpeta", "--pieza", "r2beat2013", "--carpeta", vieja, "--destino", dest])
        ficha = mud._ficha_de(os.path.join(dest, "r2beat2013.tar"))
        ok(ficha["bases"]["datos.db"]["filas"] == {"users": 7} and ficha["bases"]["datos.db"]["integridad"] == "ok",
           "la base viaja con sus 7 cuentas (las que estaban sólo en el WAL también)")
        cruda = os.path.join(tmp, "copia_a_mano.db")
        shutil.copy(os.path.join(vieja, "datos.db"), cruda)
        try:
            n_cruda = sqlite3.connect(cruda).execute("SELECT COUNT(*) FROM users").fetchone()[0]
        except sqlite3.Error:
            n_cruda = -1
        ok(n_cruda != 7, f"⟲ copiar el .db a mano NO trae las 7 (trae {n_cruda}): por eso es backup() y no cp")
        ok(sorted(ficha["archivos"]) == ["config/gm.txt", "datos.db", "sesiones.json"],
           f"gm.txt va a config/, y status.json no viaja ({sorted(ficha['archivos'])})")
        ahora = {n: hashlib.md5(open(os.path.join(vieja, n), "rb").read()).hexdigest() for n in antes}
        ok(antes == ahora, "⛔ la carpeta de origen quedó byte a byte como estaba (sólo se lee)")
        c.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  PARTE B — con Docker
# ══════════════════════════════════════════════════════════════════════════════════════════════
YA_HECHAS = False        # True con `--imagenes`: no se construye, se prueba lo que ya está en la máquina con esos nombres
PLATAFORMA = None        # None = la de esta máquina; "linux/arm64" = emulada (ver `main`)
LENTO = 1                # por cuánto se estiran las esperas: emulado, Python corre varias veces más despacio
MAQUINA = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}
PUERTOS_JUEGO = [48004] + [48005 + 10 * i for i in range(10)] + [48190]
PUERTO_CUENTAS = 48195
PREFIJO = "enenos-prueba"
IMAGENES = {"JUEGO_IMAGEN": "r2beat2013-juego:prueba", "CUENTAS_IMAGEN": "enenos-cuentas:prueba"}
LOCAL = "127.0.0.1"


def sh(*args, entrada=None, env=None, cwd=None, tope=600):
    return subprocess.run(list(args), input=entrada, capture_output=True, env=env, cwd=cwd, timeout=tope * LENTO)


def txt(r):
    return (r.stdout + r.stderr).decode("utf-8", "replace")


class Conjunto:
    """Un `docker compose` con su nombre de proyecto, parado en una carpeta."""

    def __init__(self, proyecto, carpeta, con_env_archivo=False):
        self.proyecto, self.carpeta = proyecto, carpeta
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("R2_", "JUEGO_", "CUENTAS_", "COMPOSE_"))}
        valores = dict(COMPOSE_PROJECT_NAME=proyecto, R2_IP_PUBLICA=LOCAL, JUEGO_PUBLICAR=LOCAL, TZ="America/Lima",
                       JUEGO_PROXIES="127.0.0.1,::1,172.16.0.0/12", CUENTAS_PROXIES="127.0.0.1,::1,172.16.0.0/12",
                       **IMAGENES)
        if con_env_archivo:                               # como lo va a usar Benja: un `.env` al lado del compose
            with open(os.path.join(carpeta, ".env"), "w", encoding="utf-8") as f:
                f.write("".join(f"{k}={v}\n" for k, v in valores.items()))
        else:
            self.env.update(valores)

    def __call__(self, *args, entrada=None, tope=600):
        return sh("docker", "compose", *args, entrada=entrada, env=self.env, cwd=self.carpeta, tope=tope)

    def id(self, servicio):
        return self("ps", "-aq", servicio).stdout.decode().strip()

    def bajar(self):
        self("down", "-v", "--remove-orphans", tope=120)


def abre(puerto, host=LOCAL, tope=2.0):
    try:
        socket.create_connection((host, puerto), tope).close()
        return True
    except OSError:
        return False


def esperar(cond, segundos=60, cada=0.5):
    fin = time.time() + segundos * LENTO
    while time.time() < fin:
        try:
            if cond():
                return True
        except Exception:                                                # noqa: BLE001
            pass
        time.sleep(cada)
    return False


# ── el cliente del JUEGO: los mismos bytes que el launcher y el exe (primitivas de `bot_carga`) ──
bc = None


def _leer(sock, buf, tope=10.0):
    """La próxima trama completa, o None si el server cerró."""
    sock.settimeout(tope * LENTO)
    while True:
        tramas, resto = bc.partir_tramas(buf[0])
        if tramas:
            m, c, p = tramas[0]
            buf[0] = buf[0][4 + len(p):]
            return m, c, p
        try:
            d = sock.recv(65536)
        except (socket.timeout, ConnectionError, OSError):
            return None
        if not d:
            return None
        buf[0] += d


def launcher(usuario, clave):
    """El FF01 del launcher (usuario + sha256) -> (usn, vcode) o None si lo rechaza."""
    with socket.create_connection((LOCAL, 48004), 5) as s:
        s.sendall(bc.ff01_launcher(usuario, clave))
        t = _leer(s, [b""])
        if not t or t[1] != 0x01 or t[2][0] != 0:
            return None
        p = t[2]
        return struct.unpack_from("<I", p, 1)[0], int(p[10:10 + p[9]].decode("ascii"), 16)


def login_juego(usn, vcode):
    """El FF01 del exe ([usn][vcode]) + FF02 -> la lista de canales, o None si el server corta."""
    with socket.create_connection((LOCAL, 48004), 5) as s:
        buf = [b""]
        s.sendall(bc.trama(0x01, struct.pack("<IQ", usn, vcode)))
        t = _leer(s, buf)
        if not t or t[1] != 0x01 or t[2][:1] != b"\x00":
            return None
        s.sendall(bc.trama(0x02))
        t = _leer(s, buf)
        return bc.leer_canales(t[2]) if t and t[1] == 0x02 else None


class EnCanal:
    """Un jugador sentado en un canal: CheckVer + login al canal -> el cifrado; después pide cosas."""

    def __init__(self, usn, canal):
        self.s = socket.create_connection((canal["ip"], canal["puerto"]), 5)     # ★ la IP que ANUNCIÓ el server
        self.buf = [b""]
        self.s.sendall(bc.trama(0x01, b"\x04\x00"))
        t = _leer(self.s, self.buf)
        if not t or t[1] != 0x01:
            raise RuntimeError("canal: no llegó el ACK del CheckVer")
        chal = secrets.randbits(32)
        self.s.sendall(bc.ff02_canal(usn, challenge=chal))
        t = _leer(self.s, self.buf)
        if not t or t[1] != 0x02 or len(t[2]) < 9 + 256:
            raise RuntimeError("canal: no llegó el RESP-4")
        _a, b = struct.unpack_from("<II", t[2], 1)
        self.cifra = bc.Cifra((b + usn) & 0xFFFFFFFF, t[2][9:9 + 256])

    def pedir(self, cmd, data=b"", tope=15.0):
        """Manda un comando cifrado y espera SU respuesta. -> los bytes, o None."""
        try:
            self.s.sendall(self.cifra.sobre_ff55(cmd, data))
        except OSError:
            return None
        fin = time.time() + tope * LENTO
        while time.time() < fin:
            t = _leer(self.s, self.buf, max(0.2, fin - time.time()) / LENTO)
            if t is None:
                return None
            if t[1] == 0x55:
                for c, d in self.cifra.abrir_ff55(t[2]) or []:
                    if c == cmd:
                        return d
        return None

    def cerrar(self):
        try:
            self.s.close()
        except OSError:
            pass


def entrar_del_todo(usuario, clave):
    """launcher -> login -> canal Libre -> FF03 (la ficha). -> (usn, vcode, EnCanal) o (None, motivo, None)."""
    par = launcher(usuario, clave)
    if not par:
        return None, "el launcher lo rechazó", None
    canales = login_juego(*par)
    if not canales:
        return None, "el login del juego cortó", None
    libre = next((c for c in canales if c["nombre"] == "Libre"), canales[-1])
    cx = EnCanal(par[0], libre)
    if not cx.pedir(0x03):
        cx.cerrar()
        return None, "no llegó la ficha (FF03)", None
    return par[0], par[1], cx


# ── el cliente de CUENTAS ──
def http(metodo, ruta, cuerpo=None, token=None):
    """-> (código, datos). (0, {}) si no contesta nadie."""
    req = urllib.request.Request(f"http://{LOCAL}:{PUERTO_CUENTAS}{ruta}", method=metodo,
                                 data=None if cuerpo is None else json.dumps(cuerpo).encode())
    req.add_header("X-R2", "1")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=8 * LENTO) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (OSError, ValueError):
        return 0, {}


def clave_publica():
    cod, d = http("GET", "/clave-publica")
    if cod != 200:
        return None, None
    from servidor import portero
    k = d["keys"][0]
    return portero._de_b64u(k["x"]), k["kid"]


def pase_de(usuario, clave):
    """/entrar + /pase eda -> (código del pase, pase o None, sesión)."""
    cod, d = http("POST", "/entrar", {"usuario": usuario, "clave": clave})
    if cod != 200:
        return cod, None, None
    cod2, d2 = http("POST", "/pase", {"juego": "eda"}, d["sesion"])
    return cod2, d2.get("pase"), d["sesion"]


def verifica(pase, pub):
    from servidor import portero
    return portero.comprobar_pase(pase, pub, "eda")


# lo que se le pregunta a un contenedor por dentro
ESCUCHA = ("ps=set()\nfor l in open('/proc/net/tcp').read().splitlines()[1:]:\n f=l.split()\n"
           " if f[3]=='0A' and not f[1].startswith('0B00007F'): ps.add(int(f[1].split(':')[1],16))\nprint(sorted(ps))")
PROHIBIDOS = ("import os,fnmatch\nmalos=[]\nfor r in ('/app','/datos','/juego','/tmp','/home','/root','/srv','/opt'):\n"
              " for c,_d,fs in os.walk(r):\n  for n in fs:\n"
              "   if any(fnmatch.fnmatch(n,p) for p in ('*.db','*.db-wal','*.db.*','gm.txt','admin.txt','moderadores.txt',"
              "'streamers.txt','*clave*.json','sesiones*.json','.env','*.pem','*.key')): malos.append(os.path.join(c,n))\n"
              "print(sorted(malos))")


def escucha(conj, servicio):
    """Los puertos en los que ESCUCHA un contenedor, preguntado ADENTRO (/proc/net/tcp).
    ⚠ Probar el puerto publicado desde afuera no alcanza: el proxy de Docker acepta la conexión aunque adentro
      todavía no haya nadie (medido en la 1.ª corrida: daba «listo» con el server a medio arrancar)."""
    try:
        return json.loads(conj("exec", "-T", servicio, "python", "-c", ESCUCHA).stdout.decode() or "[]")
    except ValueError:
        return []


def juego_listo(conj):
    return escucha(conj, "r2beat2013") == sorted(PUERTOS_JUEGO)


def parte_b():
    global bc
    juego = os.environ.get("R2BEAT2013_REPO") or ""
    if not ok(os.path.isfile(os.path.join(juego, "herramientas", "bot_carga.py")) and YA_HECHAS,
              "la parte B tiene R2BEAT2013_REPO (con herramientas/bot_carga.py) y --imagenes (la del juego se arma allá)"):
        return
    bc = _modulo("bot_carga", os.path.join(juego, "herramientas", "bot_carga.py"))
    sembrar = os.path.join(juego, "herramientas", "contenedores", "sembrar_prueba.py")
    from servidor import portero
    mudanza = [sys.executable, os.path.join(CONT, "mudanza.py")]
    clave = secrets.token_urlsafe(12)                      # la de las cuentas de prueba: nace y muere en esta corrida
    A = Conjunto(f"{PREFIJO}-a", CONT)
    trabajo = tempfile.mkdtemp(prefix="enenos_prueba_")     # en el disco de Linux (los .tar traen hashes y la clave)
    limpia = os.path.join(trabajo, "carpeta_limpia")
    os.makedirs(limpia)
    shutil.copy(os.path.join(CONT, "docker-compose.yml"), limpia)
    B = Conjunto(f"{PREFIJO}-b", limpia, con_env_archivo=True)
    conjuntos = [A, B]
    env_mud = dict(os.environ, **IMAGENES)
    vol_suelto = f"{PREFIJO}-suelto"
    mia = [False]            # ¿esta corrida es la dueña de los `enenos-prueba-*`? Hasta comprobarlo no se limpia nada

    def limpiar():
        for c in conjuntos:
            c.bajar()
        for p in ("a", "b", "v", "c"):
            for v in ("r2beat2013_datos", "cuentas_datos"):
                sh("docker", "volume", "rm", "-f", f"{PREFIJO}-{p}_{v}")
        sh("docker", "volume", "rm", "-f", vol_suelto)

    try:
        titulo("B0 · antes de empezar")
        if not ok(sh("docker", "compose", "version").returncode == 0, "hay Docker y `docker compose`"):
            return
        # ⛔ ANTES DE LIMPIAR NADA: ¿hay OTRA corrida de esta prueba en esta máquina? Usa los mismos nombres de proyecto y
        #   los mismos puertos. El 15-nov esta limpieza le borró los volúmenes a una corrida que estaba a la mitad (la de
        #   la sesión que probaba las imágenes bajadas del registro): limpiaba primero y miraba los puertos después.
        ajenos = sh("docker", "ps", "-a", "--format", "{{.Names}} ({{.Status}})", "--filter", f"name={PREFIJO}").stdout.decode().splitlines()
        if ajenos and "--limpiar" not in sys.argv[1:]:
            ok(False, f"no hay otra corrida de esta prueba en curso — hay contenedores de la prueba: {'; '.join(ajenos)}. "
                      f"Si es otra corrida, esperala. Si quedaron colgados de una que se cortó, repetí con --limpiar")
            return
        mia[0] = True                                       # desde acá los `enenos-prueba-*` son de ESTA corrida
        limpiar()
        ocupados = [p for p in PUERTOS_JUEGO + [PUERTO_CUENTAS] if abre(p, tope=0.5)]
        if not ok(not ocupados, f"los puertos están libres en esta máquina (ocupados: {ocupados})"):
            return
        sin_ip = dict(A.env)
        sin_ip.pop("R2_IP_PUBLICA")
        ok(sh("docker", "compose", "config", env=sin_ip, cwd=CONT).returncode != 0,
           "⟲ sin R2_IP_PUBLICA el compose se NIEGA a arrancar (si no, anunciaría una IP 172.x de adentro)")

        titulo("B1 · las dos imágenes construyen, y adentro no hay nada que no deba")
        if YA_HECHAS:
            # ★ `--imagenes`: NO se construye nada. Se prueba lo que ya está en esta máquina con esos nombres
            #   (lo bajado de un registro): así la prueba vale para la imagen que va a correr, no para una hecha acá.
            hay = all(sh("docker", "image", "inspect", v).returncode == 0 for v in IMAGENES.values())
            if not ok(hay, f"las imágenes dadas están en esta máquina, sin construir nada ({', '.join(IMAGENES.values())})"):
                return
            ids = {v: sh("docker", "image", "inspect", "--format", "{{.Id}}", v).stdout.decode().strip() for v in IMAGENES.values()}
            print("      (medido: se prueban " + " · ".join(f"{k} = {v[:19]}…" for k, v in ids.items()) + ")")
        else:
            r = None
            t0 = time.time()
            for _ in range(8):                             # la red de esta PC corta bajadas («tls: bad record MAC»): reintenta
                r = A("build", tope=900)
                if r.returncode == 0:
                    break
            if not ok(r.returncode == 0, "docker compose build" + ("" if r.returncode == 0 else ": " + txt(r)[-400:])):
                return
            print(f"      (medido: construir las dos, con lo que ya hubiera en caché: {time.time() - t0:.0f} s)")
        nativa = os.uname().machine
        esperada = MAQUINA[PLATAFORMA] if PLATAFORMA else nativa
        for var, n in (("JUEGO_IMAGEN", "juego"), ("CUENTAS_IMAGEN", "cuentas")):
            r = sh("docker", "run", "--rm", "--network", "none", IMAGENES[var], "python", "-c",
                   "import platform, sys; print(platform.machine(), sys.version.split()[0])")
            sale = r.stdout.decode().split() or ["?", "?"]
            arq = sh("docker", "image", "inspect", "--format", "{{.Architecture}} {{.Size}}", IMAGENES[var]).stdout.decode().split()
            peso = f"{int(arq[1]) / 1e6:.0f} MB" if len(arq) == 2 else "?"
            ok(sale[0] == esperada, f"imagen de {n}: corre como {sale[0]} ({arq[0] if arq else '?'}, {peso}, Python {sale[-1]})")
        if esperada != nativa:
            r = sh("docker", "run", "--rm", "--network", "none", "--platform", "linux/amd64" if nativa == "x86_64" else "linux/arm64",
                   "python:3.13-slim-bookworm", "uname", "-m")
            ok(r.stdout.decode().strip() == nativa != esperada,
               f"⟲ la misma pregunta a una imagen de ESTA máquina contesta {r.stdout.decode().strip()}: el chequeo distingue")
        for var, n in (("JUEGO_IMAGEN", "juego"), ("CUENTAS_IMAGEN", "cuentas")):
            r = sh("docker", "run", "--rm", "--network", "none", IMAGENES[var], "python", "-c", PROHIBIDOS)
            ok(r.stdout.decode().strip() == "[]", f"imagen de {n}: ni bases, ni claves, ni listas de cuentas ({r.stdout.decode().strip()})")
        r = sh("docker", "run", "--rm", "--network", "none", IMAGENES["JUEGO_IMAGEN"], "sh", "-c",
               "mkdir /tmp/x && touch /tmp/x/datos.db /tmp/x/portero_clave.json /tmp/x/gm.txt && python -c \"$0\"", PROHIBIDOS)
        ok(r.stdout.decode().count("/tmp/x/") == 3, "⟲ el buscador sí encuentra una base, una clave y un gm.txt plantados")
        r = sh("docker", "run", "--rm", "--network", "none", IMAGENES["CUENTAS_IMAGEN"], "sh", "-c", "ls /app/servidor | sort | tr '\\n' ' '")
        esperados = sorted(x.strip().split("/", 1)[1] for x in open(os.path.join(CONT, "cuentas.Dockerfile.dockerignore"),
                                                                encoding="utf-8") if x.startswith("!servidor/"))
        ok(r.stdout.decode().split() == esperados,
           f"la imagen de cuentas trae sus {len(esperados)} archivos (los de la lista blanca) y NADA del juego")
        r = sh("docker", "run", "--rm", "--network", "none", IMAGENES["JUEGO_IMAGEN"], "sh", "-c",
               "ls /app/servidor/notes | wc -l; ls /app/R2Beat; id -u")
        ok(r.stdout.decode().split()[1:] == ["R2Beat.exe.pristino", "rnr_script", "10013"] and int(r.stdout.decode().split()[0]) > 2000,
           "la imagen del juego trae los charts y la tabla de niveles, y NO corre como root")
        # ★ la dificultad de las canciones (`music_lt.txt`): sin ella no hay error, el sorteo del cooperativo queda PAREJO
        niveles = ("import sys; sys.path.insert(0, '/app'); from servidor import notas; "
                   "print('NIVELES', len(notas.cargar_niveles()))")

        def cuantos_niveles(*extra):
            r = sh("docker", "run", "--rm", "--network", "none", "-e", "R2_LOG=/tmp/niveles.log", *extra,
                   IMAGENES["JUEGO_IMAGEN"], "python", "-c", niveles)
            m = re.search(r"NIVELES (\d+)", txt(r))
            return (int(m.group(1)) if m else -1), txt(r)

        con, _t = cuantos_niveles()
        ok(con > 500, f"la imagen trae music_lt.txt: {con} canciones con su dificultad (el sorteo del cooperativo filtra por nivel)")
        sin, salida = cuantos_niveles("--tmpfs", "/app/R2Beat/rnr_script")      # la misma imagen, con esa carpeta tapada
        ok(sin == 0 and "music_lt.txt no aparece" in salida,
           f"⟲ sin ese archivo quedan {sin} niveles y el server sólo deja un aviso en el log: por eso se comprueba acá")

        titulo("B2 · el juego solo, sobre un volumen vacío: qué abre y dónde escribe (medido)")
        r = A("run", "--rm", "-T", "--no-deps", "-e", f"PRUEBA_CLAVE={clave}", "r2beat2013", "python", "-",
              entrada=open(sembrar, "rb").read())
        sembrado = json.loads(txt(r).split("SEMBRADO ", 1)[1].splitlines()[0]) if "SEMBRADO " in txt(r) else {}
        if not ok(set(sembrado) == {"prueba1", "prueba2", "prueba3"}, f"3 cuentas de prueba sembradas por los caminos del juego ({sembrado or txt(r)[-300:]})"):
            return
        t0 = time.time()
        A("up", "-d", "--no-build", "r2beat2013")
        listo = esperar(lambda: juego_listo(A), 90, 1)
        print(f"      (medido: del `up` a escuchar en los 12 puertos: {time.time() - t0:.0f} s)")
        ok(listo,
           f"adentro escucha en 12 puertos y en ninguno más: login 48004, 10 canales, API 48190 ({escucha(A, 'r2beat2013')})")
        ok(all(abre(p) for p in PUERTOS_JUEGO), "y los 12 están publicados en la máquina")
        ok(login_juego(1, 12345) is None,
           "en un volumen NUEVO el login no queda abierto: un vcode inventado rebota (arranque.py creó sesiones.json)")
        A("exec", "-T", "r2beat2013", "rm", "/datos/sesiones.json")
        ok(login_juego(1, 12345) is not None,
           "⟲ sin ese archivo el server deja entrar a cualquiera con cualquier vcode (por eso se crea al arrancar)")
        A("exec", "-T", "r2beat2013", "sh", "-c", "echo '{}' > /datos/sesiones.json")
        ok(login_juego(1, 12345) is None, "y con el archivo de vuelta, rebota otra vez")
        log = txt(A("logs", "r2beat2013"))
        ok("tabla de niveles: 99 umbrales" in log and "TODOS nivel 1" not in log, "leyó la tabla de niveles del exe (nadie queda en nivel 1)")
        ok(re.search(r"picker de música: \d{3,} canciones", log) is not None, "y cargó los charts")
        r = A("exec", "-T", "r2beat2013", "sh", "-c", "cd /datos && find . -type f | sort | tr '\\n' ' '")
        escritos = set(r.stdout.decode().split())
        ok({"./datos.db", "./panel.db", "./status.json", "./logs/servidor.log"} <= escritos,
           f"su estado quedó en el volumen ({' '.join(sorted(escritos))})")
        r = sh("docker", "diff", A.id("r2beat2013"))
        fuera = [x for x in r.stdout.decode().splitlines() if "docker-init" not in x and x.strip() not in ("C /usr", "C /usr/sbin")]
        ok(not fuera, f"y no escribió NADA fuera del volumen ({fuera})")
        r = A("exec", "-T", "r2beat2013", "sh", "-c", "echo x > /app/prueba_de_escritura")
        ok(r.returncode != 0, "⟲ escribir fuera del volumen rebota (el contenedor es de sólo lectura)")

        titulo("B3 · los dos arriba: el login de prueba entra y el pase verifica")
        A("up", "-d", "--no-build", "cuentas")
        ok(esperar(lambda: http("GET", "/salud")[0] == 200, 40), "cuentas contesta /salud")
        ok(escucha(A, "cuentas") == [PUERTO_CUENTAS], f"cuentas escucha sólo en el {PUERTO_CUENTAS} ({escucha(A, 'cuentas')})")
        ok(escucha(A, "cuentas") != escucha(A, "r2beat2013"), "⟲ la medición distingue un contenedor del otro")
        r = A("exec", "-T", "cuentas", "python", "-m", "servidor.portero", "aprobar", "prueba1", "eda")
        ok("PUEDE" in txt(r), "prueba1 aprobada para EDA desde la consola del contenedor")

        t0 = time.time()
        usn1, vcode1, cx = entrar_del_todo("prueba1", clave)
        print(f"      (medido: launcher + login + canal + ficha: {time.time() - t0:.2f} s)")
        ok(usn1 == sembrado["prueba1"], f"prueba1: launcher -> login -> canal -> ficha (usn {usn1})" if usn1 else f"prueba1 no entró: {vcode1}")
        if cx:
            cx.cerrar()
        ok(launcher("prueba1", clave + "x") is None, "⟲ con la clave mala el launcher lo rechaza")
        ok(launcher("nadie99", clave) is None, "⟲ y una cuenta que no existe, también")
        ok(usn1 and login_juego(usn1, vcode1 ^ 0x5A5A5A) is None, "⟲ con un vcode que no es el suyo, el login del juego corta")
        canales = login_juego(usn1, vcode1) if usn1 else None
        ok(canales and {c["ip"] for c in canales} == {LOCAL} and len(canales) == 10,
           "los 10 canales se anuncian con la IP del .env (R2_IP_PUBLICA), no con la 172.x de adentro")

        vistas = sorted(set(re.findall(r"conexion desde (\d+\.\d+\.\d+\.\d+)", txt(A("logs", "r2beat2013")))))
        print(f"      (medido: con la red de Docker y entrando desde esta misma máquina, el juego ve al jugador como {vistas})")
        de_afuera = [v for v in vistas if v != LOCAL]      # 127.0.0.1 es el chequeo de salud, que corre adentro
        ok(de_afuera and all(v.startswith("172.") for v in de_afuera),
           "con la red de Docker, un jugador que entra desde la MISMA máquina se ve con la IP de la puerta de Docker (172.x)")

        pub, kid = clave_publica()
        t0 = time.time()
        cod, pase, _s = pase_de("prueba1", clave)
        print(f"      (medido: entrar a cuentas + un pase firmado: {time.time() - t0:.2f} s)")
        carga = verifica(pase, pub) if pase else None
        ok(cod == 200 and carga and carga["sub"] == str(usn1) and carga["aud"] == "eda",
           f"prueba1 recibe su pase y verifica con la clave pública (sub = su uid {usn1})")
        ok(pase and verifica(pase[:-6] + ("AAAAAA" if not pase.endswith("AAAAAA") else "BBBBBB"), pub) is None,
           "⟲ el mismo pase con la firma tocada NO verifica")
        ok(pase_de("prueba2", clave)[0] == 403, "⟲ prueba2 (no aprobada) entra a cuentas pero NO recibe pase (403)")
        ok(pase_de("prueba1", clave + "x")[0] == 401, "⟲ y con la clave mala, 401")

        titulo("B3b · R2_NOMBRE_PUBLICO: el server saca del DNS la IP que anuncia en los canales")
        # El juego se vuelve a crear con otras variables (su volumen es el mismo: la sesión de prueba1 sigue valiendo).
        # R2_IP_PUBLICA queda en 127.0.0.2 (una IP de mentira): así se VE cuándo manda el nombre y cuándo la red de seguridad.
        NOMBRES = ("R2_NOMBRE_PUBLICO", "R2_NOMBRE_PUBLICO_PRIVADAS", "R2_NOMBRE_PUBLICO_SIN_COMPROBAR")

        def con_variables(**nuevas):
            for k in NOMBRES:
                A.env.pop(k, None)
            A.env.update(nuevas)
            A("up", "-d", "--no-build", "r2beat2013")
            esperar(lambda: juego_listo(A), 90, 1)

        def anunciadas():
            c = login_juego(usn1, vcode1)
            return sorted({x["ip"] for x in c}) if c else None

        def en_el_log(texto):
            return texto in txt(A("logs", "r2beat2013"))

        con_variables(R2_IP_PUBLICA="127.0.0.2")
        ok(anunciadas() == ["127.0.0.2"] and not en_el_log("nombre público"),
           "sin el nombre, como siempre: anuncia lo que diga R2_IP_PUBLICA (acá, una IP de mentira) y no resuelve nada")
        trae = A("exec", "-T", "r2beat2013", "test", "-f", "/app/servidor/nombre_publico.py").returncode == 0
        if not trae:
            # Una imagen hecha ANTES de esta función (p. ej. la `2026-11-14` del registro): el resto de B3b no le toca.
            print("      ⚠ ESTA IMAGEN ES ANTERIOR A R2_NOMBRE_PUBLICO (no trae servidor/nombre_publico.py): el resto de "
                  "B3b NO SE CORRE. No es un verde: es que esta imagen no tiene la función.")
            con_variables(R2_IP_PUBLICA=LOCAL)
        ok(trae or YA_HECHAS, "la imagen trae la función (una construida ahora la tiene que traer; una anterior dada con --imagenes, no)")
        if trae:
            con_variables(R2_NOMBRE_PUBLICO="localhost", R2_NOMBRE_PUBLICO_PRIVADAS="1")
            ok(esperar(lambda: anunciadas() == [LOCAL], 40, 1) and en_el_log("comprobado: por esa IP se llega a este server"),
               f"⟲ con el nombre: resuelve, se manda el eco a sí mismo, y anuncia la IP del DNS ({anunciadas()}), no la de la variable")
            con_variables(R2_NOMBRE_PUBLICO="localhost")
            ok(esperar(lambda: en_el_log("IP privada"), 40, 1) and anunciadas() == ["127.0.0.2"],
               "el DNS devuelve una IP privada y no se pidió aceptarlas: no la adopta, anuncia la de la variable")
            con_variables(R2_NOMBRE_PUBLICO="no-existe-enenos-prueba.invalid", R2_NOMBRE_PUBLICO_PRIVADAS="1")
            ok(esperar(lambda: en_el_log("no pude resolver"), 60, 1) and anunciadas() == ["127.0.0.2"],
               "el nombre no existe: la lista de canales sale igual, con la IP de la variable (el FF02 no revienta)")
            con_variables(R2_NOMBRE_PUBLICO="cuentas", R2_NOMBRE_PUBLICO_PRIVADAS="1")
            ok(esperar(lambda: en_el_log("NO se llega a este server"), 60, 1) and anunciadas() == ["127.0.0.2"],
               "el nombre apunta a OTRA máquina (el contenedor de cuentas): el eco no vuelve y no la adopta (lo de una mudanza)")
            con_variables(R2_NOMBRE_PUBLICO="cuentas", R2_NOMBRE_PUBLICO_PRIVADAS="1", R2_NOMBRE_PUBLICO_SIN_COMPROBAR="1")
            ok(esperar(lambda: (anunciadas() or ["127.0.0.2"])[0].startswith("172."), 40, 1),
               f"⟲ sin comprobar (R2_NOMBRE_PUBLICO_SIN_COMPROBAR) sí se la cree, y anuncia la IP de otra máquina ({anunciadas()}): por eso el eco")
            con_variables(R2_IP_PUBLICA=LOCAL)
            ok(anunciadas() == [LOCAL], "y sacando el nombre, todo vuelve a como estaba")

        titulo("B4 · se apaga el JUEGO: cuentas sigue dando pases")
        t0 = time.time()
        A("stop", "r2beat2013")
        tardo = time.time() - t0
        ok(tardo < (6 if LENTO == 1 else 8.5), f"el juego se apaga enseguida ({tardo:.1f} s): `init: true` le hace llegar la señal a Python")
        sh("docker", "run", "-d", "--rm", "--network", "none", "--name", f"{PREFIJO}-sininit", IMAGENES["JUEGO_IMAGEN"])
        time.sleep(4 * LENTO)
        t0 = time.time()
        sh("docker", "stop", f"{PREFIJO}-sininit")
        tardo_sin = time.time() - t0
        ok(tardo_sin >= 9, f"⟲ el mismo server SIN `init` ignora el aviso: Docker espera 10 s y lo mata ({tardo_sin:.1f} s)")
        ok(not abre(48004) and launcher_seguro("prueba1", clave) is None, "⟲ el juego de verdad está apagado (48004 no contesta)")
        cod, pase, _s = pase_de("prueba1", clave)
        ok(cod == 200 and pase and verifica(pase, pub), "un login NUEVO en cuentas y su pase, con el juego apagado")
        A("restart", "cuentas")
        ok(esperar(lambda: http("GET", "/salud")[0] == 200, 40), "cuentas se reinicia y vuelve SOLA, con el juego apagado")
        cod, pase, sesion_larga = pase_de("prueba1", clave)
        ok(cod == 200 and pase and verifica(pase, pub) and clave_publica()[1] == kid,
           "y sigue firmando con la MISMA clave (vive en su volumen, no en la imagen)")

        titulo("B5 · vuelve el juego; se apaga CUENTAS: el juego sigue atendiendo")
        A("start", "r2beat2013")
        ok(esperar(lambda: juego_listo(A), 90, 1), "el juego volvió")
        ok(login_juego(usn1, vcode1) is not None, "la sesión de ANTES de reiniciar el juego sigue valiendo (sesiones.json está en el volumen)")
        _u, _v, cx = entrar_del_todo("prueba1", clave)
        ok(cx is not None, "prueba1 sentado en un canal")
        A("stop", "cuentas")
        ok(http("GET", "/salud")[0] == 0 and not abre(PUERTO_CUENTAS), "⟲ cuentas de verdad está apagado (no contesta)")
        ok(cx is not None and cx.pedir(0x03) is not None and cx.pedir(0x97) is not None,
           "el que ya estaba en el canal sigue recibiendo respuestas (su ficha, los avisos)")
        usn2, motivo, cx2 = entrar_del_todo("prueba2", clave)
        ok(usn2 == sembrado["prueba2"], "y hoy hasta entra un jugador NUEVO (el juego todavía comprueba la clave él mismo)"
           if usn2 else f"prueba2 no pudo entrar: {motivo}")
        for x in (cx, cx2):
            if x:
                x.cerrar()
        A("start", "cuentas")
        ok(esperar(lambda: http("GET", "/salud")[0] == 200, 40), "cuentas volvió")
        cod, d = http("POST", "/pase", {"juego": "eda"}, sesion_larga)
        ok(cod == 200 and verifica(d.get("pase", ""), pub), "la sesión del launcher de ANTES de apagar cuentas sigue valiendo (portero.db está en su volumen)")
        cod_s, d_s = http("POST", "/entrar", {"usuario": "prueba3", "clave": clave})
        http("POST", "/salir", {}, d_s.get("sesion"))
        ok(http("GET", "/yo", token=d_s.get("sesion"))[0] == 401, "⟲ una sesión cerrada con /salir ya no vale")

        titulo("B6 · MUDANZA: exportar en caliente, bajar todo, importar en una carpeta limpia con otro nombre")
        dest = os.path.join(trabajo, "mudanza")
        r = sh(*mudanza, "exportar", "--proyecto", A.proyecto, "--destino", dest, "--imagenes", env=env_mud)
        ok(r.returncode == 0 and all(os.path.isfile(os.path.join(dest, n)) for n in ("r2beat2013.tar", "cuentas.tar", "imagenes.tar", "MANIFIESTO.json")),
           "exportado con los dos servers PRENDIDOS: un .tar por pieza + las imágenes" + ("" if r.returncode == 0 else ": " + txt(r)[-300:]))
        man = json.load(open(os.path.join(dest, "MANIFIESTO.json"), encoding="utf-8"))
        filas_j = man["piezas"]["r2beat2013"]["ficha"]["bases"]["datos.db"]["filas"]
        filas_c = man["piezas"]["cuentas"]["ficha"]["bases"]["portero.db"]["filas"]
        ok(filas_j.get("users") == 3 and filas_j.get("chars") == 3 and filas_c.get("aprobados") == 1,
           f"el paquete dice lo que trae: {filas_j.get('users')} cuentas, {filas_j.get('chars')} personajes, {filas_c.get('aprobados')} aprobada")
        ok("portero_clave.json" in man["piezas"]["cuentas"]["ficha"]["archivos"] and "sesiones.json" in man["piezas"]["r2beat2013"]["ficha"]["archivos"],
           "y viajan la clave que firma y las sesiones del juego")
        ok(login_juego(usn1, vcode1) is not None and http("GET", "/salud")[0] == 200, "exportar no cortó a nadie: los dos siguen atendiendo")
        A("down")                                           # se apaga el origen (sus volúmenes quedan: es la vuelta atrás)
        ok(not abre(48004) and not abre(PUERTO_CUENTAS), "el origen quedó apagado")
        sh("docker", "rmi", "-f", *IMAGENES.values())
        ok(B("up", "-d", "--no-build").returncode != 0, "⟲ en la carpeta limpia, sin las imágenes, no arranca nada")
        B("down", "-v")

        V = Conjunto(f"{PREFIJO}-v", limpia)                # ⟲ el control: todo igual, pero SIN importar el estado
        conjuntos.append(V)
        otra = []
        if PLATAFORMA and MAQUINA[PLATAFORMA] != os.uname().machine:
            r = sh(*mudanza, "importar", "--proyecto", B.proyecto, "--origen", dest, "--imagenes", env=env_mud)
            ok(r.returncode != 0 and "no van a arrancar" in txt(r),
               "⟲ mudanza.py se NIEGA a cargar imágenes de otra arquitectura (acá sólo andan porque hay emulación)")
            otra = ["--otra-arquitectura"]
        r = sh(*mudanza, "importar", "--proyecto", B.proyecto, "--origen", dest, "--imagenes", *otra, env=env_mud)
        ok(r.returncode == 0, "importado en el proyecto nuevo (imágenes + los dos volúmenes)" + ("" if r.returncode == 0 else ": " + txt(r)[-400:]))
        V("up", "-d", "--no-build")
        esperar(lambda: juego_listo(V), 90, 1)
        ok(launcher("prueba1", clave) is None, "⟲ SIN importar, prueba1 no existe en la máquina nueva")
        # ⚠ medido: sobre un volumen VACÍO el juego recién crea la tabla de cuentas con el primer login, y el portero
        #   (etapa 0: lee esa tabla) se cae al arrancar hasta que exista. Docker lo reintenta solo; acá no se espera.
        estado = sh("docker", "inspect", "--format", "{{.RestartCount}}", V.id("cuentas")).stdout.decode().strip()
        print(f"      (medido: en el volumen vacío, cuentas llevaba {estado} reinicio(s) esperando la base del juego)")
        V("restart", "cuentas")
        esperar(lambda: clave_publica()[1] is not None, 60, 1)
        kid_v = clave_publica()[1]
        if not ok(kid_v not in (None, kid), "⟲ SIN importar, la clave que firma es OTRA (los juegos rechazarían sus pases)"):
            print(f"      (diagnóstico: kid de antes {kid}, kid acá {kid_v}, /salud {http('GET', '/salud')[0]}, "
                  f"cuentas: {txt(V('ps', '-a', '--format', '{{.Service}} {{.Status}}')).strip()!r})")
            print("      " + txt(V("logs", "--tail", "6", "cuentas")).strip().replace("\n", "\n      ")[-900:])
        V.bajar()

        r = B("up", "-d", "--no-build")
        ok(r.returncode == 0 and "not created by Docker Compose" not in txt(r),
           "docker compose up en la carpeta limpia (sólo el compose, el .env y lo importado)" + ("" if r.returncode == 0 else ": " + txt(r)[-300:]))
        ok(esperar(lambda: juego_listo(B) and http("GET", "/salud")[0] == 200, 90, 1), "los dos atienden")
        usn_m, motivo, cx = entrar_del_todo("prueba1", clave)
        ok(usn_m == usn1, f"prueba1 entra con la MISMA clave y el MISMO uid ({usn_m})" if usn_m else f"prueba1 no entró tras la mudanza: {motivo}")
        if cx:
            cx.cerrar()
        ok(login_juego(usn1, vcode1) is not None, "y hasta la sesión abierta en la máquina vieja sigue valiendo")
        cod, pase, _s = pase_de("prueba1", clave)
        ok(cod == 200 and pase and verifica(pase, pub) and clave_publica()[1] == kid,
           "el pase de la máquina nueva verifica con la clave pública DE ANTES (EDA no tiene que cambiar nada)")
        ok(pase_de("prueba2", clave)[0] == 403, "la lista de aprobados viajó: prueba2 sigue sin pase")
        ok(http("POST", "/pase", {"juego": "eda"}, sesion_larga)[0] == 200, "y la sesión del launcher de la máquina vieja sigue valiendo")
        r = sh(*mudanza, "importar", "--proyecto", B.proyecto, "--origen", dest, env=env_mud)
        ok(r.returncode != 0 and "no la piso" in txt(r), "⟲ importar otra vez encima se NIEGA (el volumen ya tiene una base)")
        roto = os.path.join(trabajo, "mudanza_rota")
        shutil.copytree(dest, roto, ignore=shutil.ignore_patterns("imagenes.tar"))
        with open(os.path.join(roto, "cuentas.tar"), "r+b") as f:
            f.seek(700)
            b = f.read(1)
            f.seek(700)
            f.write(bytes([b[0] ^ 0xFF]))
        r = sh(*mudanza, "importar", "--proyecto", f"{PREFIJO}-c", "--origen", roto, "--pieza", "cuentas", env=env_mud)
        ok(r.returncode != 0 and "DAÑADO" in txt(r), "⟲ un paquete con UN byte cambiado se rechaza entero")

        titulo("B8 · la variante con la red DE LA MÁQUINA (docker-compose.red-host.yml), sobre los volúmenes mudados")
        B("down")
        shutil.copy(os.path.join(CONT, "docker-compose.red-host.yml"), limpia)
        dos = ("-f", "docker-compose.yml", "-f", "docker-compose.red-host.yml")
        r = B(*dos, "up", "-d", "--no-build")
        ok(r.returncode == 0, "arranca con los dos archivos" + ("" if r.returncode == 0 else ": " + txt(r)[-300:]))
        todos = ("ps=[]\nfor l in open('/proc/net/tcp').read().splitlines()[1:]:\n f=l.split()\n"
                 " if f[3]=='0A': ps.append([f[1].split(':')[0], int(f[1].split(':')[1],16)])\n"
                 "print(__import__('json').dumps(ps))")

        def abiertos():
            try:
                return {p: ip for ip, p in json.loads(B(*dos, "exec", "-T", "r2beat2013", "python", "-c", todos).stdout.decode() or "[]")}
            except ValueError:
                return {}

        ok(esperar(lambda: set(PUERTOS_JUEGO + [PUERTO_CUENTAS]) <= set(abiertos()), 90, 1), "los 13 puertos abren directo en la máquina")
        ab = abiertos()
        ok(ab.get(48190) == "0100007F" and ab.get(PUERTO_CUENTAS) == "0100007F" and ab.get(48004) == "00000000",
           "la API y cuentas escuchan SÓLO en 127.0.0.1 (como hoy en prod); el juego, en todas")
        usn_h, motivo, cx = entrar_del_todo("prueba1", clave)
        ok(usn_h == usn1, "prueba1 entra igual" if usn_h else f"prueba1 no entró: {motivo}")
        if cx:
            cx.cerrar()
        vistas_h = sorted(set(re.findall(r"conexion desde (\d+\.\d+\.\d+\.\d+)", txt(B(*dos, "logs", "r2beat2013")))))
        ok(vistas_h == [LOCAL], f"⟲ y acá el juego ve la IP REAL del jugador ({vistas_h}), ninguna 172.x de Docker")
        cod, pase, _s = pase_de("prueba1", clave)
        ok(cod == 200 and pase and verifica(pase, pub), "y el pase sale y verifica")
        B(*dos, "down")

        titulo("B7 · por qué el volumen del juego no va `:ro` en cuentas (medido)")
        sh("docker", "volume", "create", vol_suelto)
        img = IMAGENES["CUENTAS_IMAGEN"]
        sh("docker", "run", "--rm", "--user", "0", "--network", "none", "-v", f"{vol_suelto}:/juego", img, "python", "-c",
           "import sqlite3; c=sqlite3.connect('/juego/datos.db'); c.execute('PRAGMA journal_mode=WAL'); "
           "c.execute('CREATE TABLE users (uid INTEGER)'); c.execute('INSERT INTO users VALUES (1)'); c.commit(); c.close()")
        leer = ("import sqlite3; c=sqlite3.connect('file:/juego/datos.db?mode=ro', uri=True); c.execute('PRAGMA query_only=1'); "
                "print('FILAS', c.execute('SELECT COUNT(*) FROM users').fetchone()[0])")
        r_ro = sh("docker", "run", "--rm", "--user", "0", "--network", "none", "-v", f"{vol_suelto}:/juego:ro", img, "python", "-c", leer)
        r_rw = sh("docker", "run", "--rm", "--user", "0", "--network", "none", "-v", f"{vol_suelto}:/juego", img, "python", "-c", leer)
        ok("FILAS 1" not in txt(r_ro) and "unable to open database file" in txt(r_ro).splitlines()[-1],
           "con `:ro` y el juego apagado LIMPIO (sin -wal/-shm), el portero no puede ni abrir la base")
        ok("FILAS 1" in txt(r_rw), "⟲ con el volumen sin `:ro` (y el código abriendo en sólo lectura) la lee")
    finally:
        try:
            if mia[0]:                                      # ⛔ si los contenedores eran de OTRA corrida, no se tocan
                titulo("limpieza")
                limpiar()
                quedan = sh("docker", "ps", "-aq", "--filter", f"name={PREFIJO}").stdout.decode().split()
                ok(not quedan, "no quedó ningún contenedor de la prueba")
                sobran = [v for v in sh("docker", "volume", "ls", "-q").stdout.decode().split() if v.startswith(PREFIJO)]
                ok(not sobran, "ni ningún volumen de la prueba" + (f": {sobran}" if sobran else ""))
        finally:
            # ★ 15-nov: la carpeta de trabajo se borra DESPUÉS de bajar los contenedores. Antes iba primero, y
            #   `docker compose down` (que corre parado en esa carpeta) reventaba con FileNotFoundError: la prueba
            #   terminaba en código 1 con todos los chequeos en verde, y dejaba volúmenes sueltos.
            shutil.rmtree(trabajo, ignore_errors=True)


def launcher_seguro(usuario, clave):
    try:
        return launcher(usuario, clave)
    except OSError:
        return None


def main():
    global PLATAFORMA, LENTO, YA_HECHAS
    con_docker = "--docker" in sys.argv[1:]
    if "--imagenes" in sys.argv[1:]:
        i = sys.argv.index("--imagenes")
        if len(sys.argv) < i + 3:
            sys.exit("⛔ --imagenes pide dos nombres: la del juego y la de cuentas")
        IMAGENES["JUEGO_IMAGEN"], IMAGENES["CUENTAS_IMAGEN"] = sys.argv[i + 1], sys.argv[i + 2]
        YA_HECHAS = True
    if "--plataforma" in sys.argv[1:]:
        PLATAFORMA = sys.argv[sys.argv.index("--plataforma") + 1]
        if PLATAFORMA not in MAQUINA:
            sys.exit(f"⛔ plataforma desconocida: {PLATAFORMA} (conozco {', '.join(MAQUINA)})")
        os.environ["DOCKER_DEFAULT_PLATFORM"] = PLATAFORMA           # la heredan `docker`, `docker compose` y mudanza.py
        sufijo = PLATAFORMA.split("/")[1]
        if "--imagenes" not in sys.argv[1:]:
            for k in IMAGENES:
                IMAGENES[k] = IMAGENES[k] + "-" + sufijo
        if con_docker and MAQUINA[PLATAFORMA] != os.uname().machine:
            LENTO = 6                                                # emulada: todo tarda varias veces más
        print(f"★ plataforma {PLATAFORMA} ({'EMULADA, esperas ×' + str(LENTO) if LENTO > 1 else 'la de esta máquina'})")
    parte_a()
    if con_docker:
        parte_b()
    if fallos:
        print(f"\n✘ {len(fallos)} cosa(s) mal:")
        for f in fallos:
            print("   · " + f)
        return 1
    if con_docker:
        print(f"\n✔ contenedores: todo bien (parte A y parte B{', ' + PLATAFORMA if PLATAFORMA else ''})")
    else:
        print("\n✔ parte A bien.  ⚠ PARTE B NO CORRIDA: los contenedores de verdad se prueban con `--docker`, "
              "dentro del WSL (ver la cabecera).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
