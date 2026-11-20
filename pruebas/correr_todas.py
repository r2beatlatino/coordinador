# -*- coding: utf-8 -*-
"""correr_todas — corre todas las `pruebas/probar_*.py`, cada una en su proceso, y da el resumen al final.

    python pruebas/correr_todas.py          # todas
    python pruebas/correr_todas.py -v       # y la salida de las que fallan
    python pruebas/correr_todas.py social   # sólo las que tienen «social» en el nombre

· Fuerza `PYTHONIOENCODING=utf-8` y `-X utf8`: en una consola cp949/cp1252 una «ñ» tira una prueba sin que haya bug.
· Una prueba que sale con 77 está SALTADA (le falta algo de afuera, p. ej. el repo de un juego): no cuenta como verde.
· Sale con error si alguna da rojo.
"""
import os
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SALTADA = 77
TOPE_S = 600


def main(args):
    detalle = "-v" in args
    filtros = [a for a in args if not a.startswith("-")]
    pruebas = sorted(n for n in os.listdir(AQUI) if n.startswith("probar_") and n.endswith(".py")
                     and (not filtros or any(f in n for f in filtros)))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    verdes, rojas, saltadas = [], [], []
    for n in pruebas:
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(AQUI, n)], cwd=RAIZ, env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TOPE_S)
            cod, salida = r.returncode, r.stdout + r.stderr
        except subprocess.TimeoutExpired as e:
            cod, salida = -1, f"(se pasó de {TOPE_S} s)\n" + str(e.stdout or "")
        dt = time.time() - t0
        if cod == 0:
            verdes.append(n)
            marca = "✔"
        elif cod == SALTADA:
            saltadas.append(n)
            marca = "⏭"
        else:
            rojas.append(n)
            marca = "✘"
        print(f"{marca} {n:<40} {dt:5.1f} s   ({salida.count('✔')} ✔ · {salida.count('✘')} ✘)", flush=True)
        if cod == SALTADA:
            print("    " + (salida.strip().splitlines() or [""])[-1])
        if cod not in (0, SALTADA) and detalle:
            print("    " + "\n    ".join(salida.strip().splitlines()[-40:]))
    print(f"\ncorrer_todas: {'VERDE' if not rojas else 'ROJO'} · {len(verdes)} verdes, {len(rojas)} rojas, "
          f"{len(saltadas)} saltadas (de {len(pruebas)})")
    for n in rojas:
        print("  ✘ " + n)
    return 1 if rojas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
