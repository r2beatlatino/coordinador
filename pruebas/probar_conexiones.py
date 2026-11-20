# -*- coding: utf-8 -*-
"""probar_conexiones — ★ 20-nov-2026: el portero CIERRA las conexiones a las bases de cada pedido.

Lo que pasó: después de la mudanza, con toda la gente de Chile en Miami, el proceso de Cuenta Eñeños llegó a 1023
archivos abiertos (tope 1024): cada hilo de `ThreadingHTTPServer` abría sus conexiones a `cuentas.db` y `portero.db`
(`portero._hilo`) y NADIE las cerraba. Desde ahí cada pedido dio «unable to open database file» y se cayó el login.

    python pruebas/probar_conexiones.py

  · 150 pedidos (entrar mal, salud, estado social) → las conexiones ABIERTAS a las bases no crecen.
  · cada conexión HTTP termina llamando a `cerrar_conexiones` ⟲ con el `handle` de siempre, nadie la llama.
  ⚠ la fuga de prod no se reproduce en esta PC (acá Python libera solo los hilos terminados): se mide en el VPS.
"""
import gc
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

mal = 0


def ok(cond, que):
    global mal
    print(("  ✔ " if cond else "  ✘ ") + que)
    mal += 0 if cond else 1


def abiertas():
    """Las conexiones sqlite3 VIVAS y ABIERTAS del proceso (una cerrada da ProgrammingError al usarla)."""
    gc.collect()
    n = 0
    for o in gc.get_objects():
        if isinstance(o, sqlite3.Connection):
            try:
                o.execute("SELECT 1")
                n += 1
            except sqlite3.ProgrammingError:
                pass
    return n


def main():
    tmp = tempfile.mkdtemp(prefix="r2_conexiones_")
    try:
        os.environ.update(
            R2_CUENTAS_DUENA="1",
            R2_BASE=os.path.join(tmp, "no_existe.db"),
            R2_PORTERO_BASE=os.path.join(tmp, "portero.db"),
            R2_CUENTAS_BASE=os.path.join(tmp, "cuentas.db"),
            R2_PORTERO_CLAVE=os.path.join(tmp, "portero_clave.json"),
            R2_ADMIN_ARCHIVO=os.path.join(tmp, "admin.txt"),
            R2_MODERADOR_ARCHIVO=os.path.join(tmp, "moderadores.txt"),
            R2_CUENTAS_FICHA_INTERNA="ficha-de-prueba-conexiones",
        )
        for k in ("R2_PORTERO_MANIFIESTOS", "R2_CUENTAS_UID_DESDE", "R2_UID_NUEVAS_DESDE"):
            os.environ.pop(k, None)
        from servidor import portero as pt

        srv = pt.servidor(0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}"

        def pedir(metodo, ruta, cuerpo=None):
            datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else (b"{}" if metodo == "POST" else None)
            req = urllib.request.Request(url + ruta, data=datos, method=metodo,
                                         headers={"Content-Type": "application/json", "X-R2": "1"})
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code

        def tanda(n=50):
            for i in range(n):
                pedir("POST", "/cuentas/entrar", {"usuario": f"nadie{i}", "clave": "mala"})
                pedir("GET", "/cuentas/salud")
                pedir("POST", "/cuentas/social/estado", {})

        tanda(5)                                  # (el arranque abre las suyas: se cuenta desde acá)
        base = abiertas()
        tanda()
        despues = abiertas()
        print(f"  conexiones abiertas: {base} al empezar → {despues} después de 150 pedidos")
        ok(despues <= base + 2, "con el cierre por pedido, las conexiones abiertas no crecen")

        # ⚠ La fuga de PROD (1023 archivos en Miami) NO se reproduce acá: en esta PC Python libera solo las conexiones
        #   de un hilo que termina. Lo que esta prueba asegura es el MECANISMO nuevo: cada conexión HTTP termina
        #   llamando a `cerrar_conexiones` (sin depender de cuándo el intérprete libere nada). La fuga real se mide en
        #   el VPS después de publicar (los archivos abiertos del proceso no crecen).
        llamadas = {"n": 0}
        original = pt.cerrar_conexiones

        def contar():
            llamadas["n"] += 1
            original()
        pt.cerrar_conexiones = contar
        try:
            tanda(20)
            n_con = llamadas["n"]
            # ⟲ control: con el `handle` de siempre (sin el finally), nadie la llama
            mio = pt._Manejador.handle
            pt._Manejador.handle = pt.BaseHTTPRequestHandler.handle
            llamadas["n"] = 0
            tanda(20)
            n_sin = llamadas["n"]
            pt._Manejador.handle = mio
        finally:
            pt.cerrar_conexiones = original
        print(f"  cierres: {n_con} en 60 pedidos · ⟲ sin el handle nuevo: {n_sin}")
        ok(n_con >= 60, "cada conexión HTTP termina cerrando sus bases (una llamada por pedido)")
        ok(n_sin == 0, "⟲ control: sin el `handle` nuevo no las cierra nadie (lo de antes)")
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n✔ todo bien" if not mal else f"\n✘ {mal} mal")
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main())
