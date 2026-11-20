# -*- coding: utf-8 -*-
"""catalogo — comprueba `juegos.json` y rehace la tabla de juegos del README (entre las dos marcas).

    python herramientas/catalogo.py              # rehace la tabla
    python herramientas/catalogo.py --comprobar  # sólo mira; sale con error si la tabla está vieja o el JSON mal

Un juego nuevo = un bloque más en `juegos.json`; nunca se edita la tabla a mano.
"""
import json
import re
import sys

# la consola de Windows puede estar en cp949/cp1252: un «✔» no puede tirar abajo la guardia
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MARCA_INI = "<!-- juegos:inicio (la arma herramientas/catalogo.py desde juegos.json; no editar a mano) -->"
MARCA_FIN = "<!-- juegos:fin -->"
ESTADOS = {"produccion": "🟢 en producción", "beta": "🟡 beta", "alpha": "🟠 alpha",
           "en_preparacion": "🔧 en preparación", "en_planes": "💭 en planes"}
CAMPOS = {"id", "nombre", "repo", "estado", "pases", "nota"}
# ★ 19-nov (el panel del Coordinador): opcionales. `corto` = el nombre que se muestra en el panel y el launcher
#   («R2Beat», «EDA»); `panel` = cómo se pinta su tarjeta. El ARTE se nombra acá pero NO vive en el repo (es de cada
#   juego, a veces de terceros): el panel lo busca en su carpeta de arte y, si no está, usa el color.
OPCIONALES = {"corto", "panel"}
PANEL = {"color", "arte", "pos", "logo", "genero", "desc"}


def errores(cat):
    """La lista de problemas del catálogo (vacía = bien)."""
    mal = []
    juegos = cat.get("juegos")
    if not isinstance(juegos, list) or not juegos:
        return ["falta la lista «juegos»"]
    vistos, pases = set(), set()
    for i, j in enumerate(juegos):
        donde = f"juego #{i + 1} ({j.get('id', '?')})"
        if not CAMPOS <= set(j) <= CAMPOS | OPCIONALES:
            mal.append(f"{donde}: campos {sorted((set(j) - OPCIONALES) ^ CAMPOS)} de más o de menos")
            continue
        if "corto" in j and not (isinstance(j["corto"], str) and 1 <= len(j["corto"]) <= 24):
            mal.append(f"{donde}: «corto» es un texto de 1 a 24 letras")
        pan = j.get("panel", {})
        if not isinstance(pan, dict) or set(pan) - PANEL:
            mal.append(f"{donde}: «panel» sólo lleva {sorted(PANEL)}")
        elif "color" in pan and not re.fullmatch(r"\d{1,3},\d{1,3},\d{1,3}", str(pan["color"])):
            mal.append(f"{donde}: el color del panel va como «r,g,b»")
        elif any(k in pan and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.(jpg|jpeg|png|webp)", str(pan[k]))
                 for k in ("arte", "logo")):
            mal.append(f"{donde}: el arte del panel es un nombre de archivo simple (.jpg/.png/.webp)")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", j["id"] or ""):
            mal.append(f"{donde}: el id va en minúsculas, números y guiones")
        if j["id"] in vistos:
            mal.append(f"{donde}: id repetido")
        vistos.add(j["id"])
        if j["estado"] not in ESTADOS:
            mal.append(f"{donde}: estado «{j['estado']}» no es uno de {sorted(ESTADOS)}")
        if j["repo"] is not None and not re.fullmatch(r"[\w.-]+/[\w.-]+", j["repo"]):
            mal.append(f"{donde}: el repo va como «dueño/nombre»")
        if set(j["pases"] or {}) != {"live", "test"}:
            mal.append(f"{donde}: «pases» lleva live y test (null si no hay)")
        for p in (j["pases"] or {}).values():
            if p is not None and p in pases:
                mal.append(f"{donde}: el pase «{p}» ya es de otro juego")
            pases.add(p)
    return mal


def tabla(cat):
    filas = ["| juego | estado | repo | pase live / test | nota |", "|---|---|---|---|---|"]
    for j in cat["juegos"]:
        repo = f"[`{j['repo']}`](https://github.com/{j['repo']})" if j["repo"] else "— (todavía no)"
        p = j["pases"]
        pases = " / ".join(f"`{x}`" if x else "—" for x in (p["live"], p["test"]))
        filas.append(f"| **{j['nombre']}** | {ESTADOS[j['estado']]} | {repo} | {pases} | {j['nota']} |")
    return "\n".join(filas)


def readme_con_tabla(readme, cat):
    if MARCA_INI not in readme or MARCA_FIN not in readme:
        raise SystemExit("⛔ el README no tiene las marcas de la tabla de juegos")
    antes, resto = readme.split(MARCA_INI, 1)
    _, despues = resto.split(MARCA_FIN, 1)
    return f"{antes}{MARCA_INI}\n{tabla(cat)}\n{MARCA_FIN}{despues}"


def main():
    cat = json.loads((RAIZ / "juegos.json").read_text("utf-8"))
    mal = errores(cat)
    if mal:
        raise SystemExit("⛔ juegos.json:\n  " + "\n  ".join(mal))
    readme = (RAIZ / "README.md").read_text("utf-8")
    nuevo = readme_con_tabla(readme, cat)
    if "--comprobar" in sys.argv:
        if nuevo != readme:
            raise SystemExit("⛔ la tabla del README está vieja: correr python herramientas/catalogo.py")
        print(f"✔ catálogo bien · {len(cat['juegos'])} juegos · la tabla del README al día")
        return
    (RAIZ / "README.md").write_text(nuevo, "utf-8", newline="\n")
    print(f"✔ tabla rehecha · {len(cat['juegos'])} juegos")


if __name__ == "__main__":
    main()
