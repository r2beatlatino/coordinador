# -*- coding: utf-8 -*-
"""probar_repo — el catálogo y la guardia, cada uno con su control al revés (el caso que DEBE fallar).

    python pruebas/probar_repo.py
"""
import copy
import json
import sys

# la consola de Windows puede estar en cp949/cp1252: un «✔» no puede tirar abajo la guardia
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "herramientas"))
import catalogo  # noqa: E402
import guardia  # noqa: E402

bien = mal = 0


def ver(cond, que):
    global bien, mal
    print(("  ✔ " if cond else "  ✘ ") + que)
    bien, mal = bien + bool(cond), mal + (not cond)


cat = json.loads((RAIZ / "juegos.json").read_text("utf-8"))
ver(catalogo.errores(cat) == [], "el juegos.json de verdad está bien")
ver(len(cat["juegos"]) >= 5, "trae los 5 juegos (2013, GunBound, EDA, Eñeñosbit 2027, Wolf Team)")
readme = (RAIZ / "README.md").read_text("utf-8")
ver(catalogo.readme_con_tabla(readme, cat) == readme, "la tabla del README está al día con juegos.json")
for j in cat["juegos"]:
    if j["repo"]:
        ver(f"https://github.com/{j['repo']}" in readme, f"el README cita al hijo {j['repo']}")

# controles: cada error tiene que saltar
def roto(cambio):
    c = copy.deepcopy(cat)
    cambio(c["juegos"])
    return catalogo.errores(c)

ver(roto(lambda js: js.append(dict(js[0]))), "control: un id repetido salta")
ver(roto(lambda js: js[0].update(estado="vivo")), "control: un estado inventado salta")
ver(roto(lambda js: js[1].update(pases={"live": "r2beat2013", "test": None})), "control: un pase de otro juego salta")
ver(roto(lambda js: js[0].pop("nota")), "control: un campo de menos salta")
ver(roto(lambda js: js[0].update(repo="sin-barra")), "control: un repo sin «dueño/nombre» salta")
c = copy.deepcopy(cat); c["juegos"].append({**cat["juegos"][0], "id": "nuevo", "nombre": "Juego Nuevo",
                                            "pases": {"live": "nuevo", "test": None}})
ver(catalogo.readme_con_tabla(readme, c) != readme, "control: sumar un juego cambia la tabla (no queda vieja)")
ver("Juego Nuevo" in catalogo.tabla(c), "y el juego nuevo aparece en la tabla")

# la guardia: el repo de verdad pasa; lo prohibido salta
ver(guardia.main([]) == 0, "la guardia deja pasar el repo tal cual")
casos_malos = {
    "datos/cuentas.db": None, "servidor/.env": None, "llaves/firma.pem": None, "respaldo.age": None,
    "config/moderadores.txt": None, "algo.py": "-----BEGIN " + "PRIVATE KEY-----\nabc",
    "x.md": "hook https://discord.com/api/webhooks/123456/" + "a" * 30,
    "y.py": "t = 'ghp_" + "A" * 30 + "'", "z.sql": "pass_hash = '$" + "argon2id$v=19$m=65536,t=3,p=4$" + "x" * 30 + "'",
    "datos/portero_clave.json": None, "copia.json": '{"ed25519_' + 'semilla": "' + "ab" * 32 + '"}',
}
for ruta, texto in casos_malos.items():
    ver(guardia.problemas(ruta, texto), f"control: la guardia frena {ruta}")
ver(not guardia.problemas("despliegue/ejemplo.env", "CLAVE="), "pero el ejemplo.env (sin valores) pasa")
ver(not guardia.problemas("servidor/cuentas.py", "pass_hash TEXT NOT NULL"), "y nombrar la columna pass_hash pasa")

print(f"probar_repo: {'VERDE' if not mal else 'ROJO'} · {bien} bien, {mal} mal")
sys.exit(1 if mal else 0)
