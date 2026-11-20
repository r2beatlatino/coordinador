# -*- coding: utf-8 -*-
"""probar_respaldo — «Generar backup» de punta a punta, con datos de mentira y una llave de prueba.

Necesita `age` (se corre dentro de la imagen del respaldo; sin age se SALTA con 77):
    docker build -f herramientas/respaldo/respaldo.Dockerfile -t enenos-respaldo herramientas/respaldo
    docker run --rm -v "$PWD":/repo -w /repo --entrypoint python enenos-respaldo pruebas/probar_respaldo.py

Cada regla con su control al revés:
- una base en WAL con datos SÓLO en el -wal: el respaldo los trae (y copiar el .db a mano NO: el control)
- descifra con la llave buena; con otra llave NO
- falta algo obligatorio → no se arma; falta algo opcional → se arma y se anota
- un archivo tocado después → la comprobación lo caza
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "herramientas" / "respaldo"))
import respaldo  # noqa: E402

if not shutil.which("age") or not shutil.which("age-keygen"):
    print("probar_respaldo: SALTADA · no hay `age` (correrla dentro de la imagen enenos-respaldo)")
    sys.exit(77)

bien = mal = 0


def ver(cond, que):
    global bien, mal
    print(("  ✔ " if cond else "  ✘ ") + que)
    bien, mal = bien + bool(cond), mal + (not cond)


def llave(carpeta, nombre):
    priv = carpeta / f"{nombre}.txt"
    subprocess.run(["age-keygen", "-o", str(priv)], check=True, capture_output=True)
    pub = carpeta / f"{nombre}.pub"
    pub.write_text(subprocess.run(["age-keygen", "-y", str(priv)], check=True, capture_output=True, text=True).stdout)
    return priv, pub


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    origen = tmp / "maquina"
    # una base EN VIVO, en WAL, con filas que todavía NO pasaron al .db (la conexión queda abierta, sin checkpoint)
    (origen / "vol/cuentas").mkdir(parents=True)
    viva = sqlite3.connect(origen / "vol/cuentas/cuentas.db")
    viva.execute("PRAGMA journal_mode=WAL")
    viva.execute("PRAGMA wal_autocheckpoint=0")
    viva.execute("CREATE TABLE cuentas (uid INTEGER PRIMARY KEY, login TEXT)")
    viva.executemany("INSERT INTO cuentas (login) VALUES (?)", [(f"jugador{i}",) for i in range(250)])
    viva.commit()
    (origen / "vol/cuentas/clave.json").write_text('{"semilla": "de-prueba"}')
    (origen / "vol/cuentas/config").mkdir()
    (origen / "vol/cuentas/config/admin.txt").write_text("1\n")
    (origen / "vol/cuentas/config/viejo.antes").write_text("no va\n")
    # como EDA en el VPS: una base ADENTRO de una carpeta que también se guarda (19-nov: el 1.er respaldo real se cayó acá)
    (origen / "vol/eda/cuentas").mkdir(parents=True)
    e = sqlite3.connect(origen / "vol/eda/porteria.db")
    e.execute("CREATE TABLE tickets (uid INTEGER)")
    e.executemany("INSERT INTO tickets VALUES (?)", [(i,) for i in range(7)])
    e.commit()
    e.close()
    (origen / "vol/eda/cuentas/en_1.json").write_text('{"nivel": 3}')
    (origen / "vol/eda/relay.log").write_text("ruido\n")
    lista = tmp / "lista.json"
    lista.write_text(json.dumps({"cosas": [
        {"nombre": "base", "tipo": "sqlite", "ruta": "vol/cuentas/cuentas.db"},
        {"nombre": "llave", "tipo": "archivo", "ruta": "vol/cuentas/clave.json"},
        {"nombre": "roles", "tipo": "carpeta", "ruta": "vol/cuentas/config", "ignorar": ["*.antes"]},
        {"nombre": "un juego que todavía no está", "tipo": "sqlite", "ruta": "vol/futuro/x.db", "opcional": True},
        {"nombre": "eda base", "tipo": "sqlite", "ruta": "vol/eda/porteria.db"},
        {"nombre": "eda estado", "tipo": "carpeta", "ruta": "vol/eda", "ignorar": ["*.db", "*.log"]},
    ]}))
    priv, pub = llave(tmp, "benja")
    priv_otra, _ = llave(tmp, "otra")

    # control: el .db solo (sin su -wal) NO tiene las filas — por eso hay que usar la API de respaldo
    a_mano = tmp / "a_mano.db"
    shutil.copy2(origen / "vol/cuentas/cuentas.db", a_mano)
    c = sqlite3.connect(a_mano)
    try:
        n_a_mano = c.execute("SELECT COUNT(*) FROM cuentas").fetchone()[0]
    except sqlite3.Error:
        n_a_mano = 0
    c.close()
    ver(n_a_mano < 250, f"control: copiar el .db a mano pierde lo del -wal ({n_a_mano} de 250 filas)")

    archivo = respaldo.armar(lista, origen, tmp / "salida", pub)
    ver(archivo.name.startswith("enenos_respaldo_") and archivo.suffix == ".age", f"armó {archivo.name}")
    ver(b"jugador1" not in archivo.read_bytes() and b"de-prueba" not in archivo.read_bytes(),
        "el archivo está cifrado (no se lee ni un login ni la llave adentro)")

    man = respaldo.descifrar(archivo, priv, tmp / "abierto")
    caja = tmp / "abierto/respaldo"
    base = {it["nombre"]: it for it in man["cosas"]}
    ver(base["base"]["filas"] == {"cuentas": 250}, "la base trae sus 250 filas (también las que estaban sólo en el -wal)")
    ver(sqlite3.connect(caja / "datos/vol/cuentas/cuentas.db").execute("SELECT COUNT(*) FROM cuentas").fetchone()[0] == 250,
        "y la base desarmada se abre sola, sin -wal")
    ver((caja / "datos/vol/cuentas/clave.json").read_text() == '{"semilla": "de-prueba"}', "la llave viene igual")
    ver(set(base["roles"]["archivos"]) == {"admin.txt"}, "la carpeta viene sin lo ignorado (*.antes)")
    ver(man["faltan_opcionales"] == ["un juego que todavía no está"], "lo opcional que falta queda anotado")
    ver(base["eda base"]["filas"] == {"tickets": 7} and set(base["eda estado"]["archivos"]) == {"cuentas/en_1.json"},
        "una base ADENTRO de una carpeta guardada: van las dos, y la carpeta anota sólo lo suyo (sin la base ni el .log)")

    # control: con OTRA llave no se abre
    try:
        respaldo.descifrar(archivo, priv_otra, tmp / "otra")
        ver(False, "control: con otra llave NO se abre")
    except respaldo.Falla:
        ver(True, "control: con otra llave NO se abre")

    # control: si algo cambió después, la comprobación lo caza
    (caja / "datos/vol/cuentas/clave.json").write_text('{"semilla": "cambiada"}')
    try:
        respaldo.comprobar(caja)
        ver(False, "control: un archivo tocado después se caza")
    except respaldo.Falla as e:
        ver("llave" in str(e), "control: un archivo tocado después se caza")

    # control: lo obligatorio que falta frena el respaldo (no se arma uno incompleto que parece completo)
    datos = json.loads(lista.read_text())
    datos["cosas"].append({"nombre": "obligatorio que no está", "tipo": "archivo", "ruta": "vol/no/existe"})
    lista2 = tmp / "lista2.json"
    lista2.write_text(json.dumps(datos))
    try:
        respaldo.armar(lista2, origen, tmp / "salida2", pub)
        ver(False, "control: falta algo obligatorio → no se arma")
    except respaldo.Falla:
        ver(not list((tmp / "salida2").glob("*.age")) if (tmp / "salida2").exists() else True,
            "control: falta algo obligatorio → no se arma (y no deja archivo a medias)")
    viva.close()

# la lista de verdad (la del VPS) está bien escrita
cosas = respaldo.leer_lista(RAIZ / "herramientas/respaldo/respaldo_vps.json")
ver(len(cosas) >= 15, f"la lista del VPS se lee ({len(cosas)} cosas)")
ver(any("portero_clave" in c["ruta"] for c in cosas if not c.get("opcional")),
    "y la llave que firma los pases es OBLIGATORIA (sin ella hay que reinstalar el launcher de todos)")
for mala in ({"cosas": [{"nombre": "x", "tipo": "sqlite", "ruta": "/abs.db"}]},
             {"cosas": [{"nombre": "x", "tipo": "zip", "ruta": "a"}]},
             {"cosas": [{"nombre": "x", "tipo": "archivo", "ruta": "a"}, {"nombre": "x", "tipo": "archivo", "ruta": "b"}]}):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(mala, f)
    try:
        respaldo.leer_lista(f.name)
        ver(False, f"control: lista mala rechazada {mala['cosas'][0]}")
    except respaldo.Falla:
        ver(True, f"control: lista mala rechazada ({'ruta absoluta' if mala['cosas'][0]['ruta'].startswith('/') else 'tipo raro' if mala['cosas'][0]['tipo'] == 'zip' else 'nombre repetido'})")
    Path(f.name).unlink()

print(f"probar_respaldo: {'VERDE' if not mal else 'ROJO'} · {bien} bien, {mal} mal")
sys.exit(1 if mal else 0)
