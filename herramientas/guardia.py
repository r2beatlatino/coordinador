# -*- coding: utf-8 -*-
"""guardia — lo que NUNCA entra a este repo (es público): bases, llaves, .env, respaldos.

    python herramientas/guardia.py           # mira los archivos que git sigue + los que están por entrar
    python herramientas/guardia.py RUTA...   # mira esos archivos (lo usan las pruebas)

Sale con error y la lista si encuentra algo. Lo corre el hook de pre-commit y GitHub Actions.
Los datos de los usuarios y los secretos van SÓLO en el respaldo cifrado de Benja (ver RECONSTRUIR.md).
"""
import re
import subprocess
import sys

# la consola de Windows puede estar en cp949/cp1252: un «✔» no puede tirar abajo la guardia
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# por NOMBRE
NOMBRES = [
    (r"\.(db|sqlite3?|db-wal|db-shm)$", "una base de datos"),
    (r"(^|/)\.env(\..*)?$", "un .env (secretos)"),
    (r"\.(pem|key|p12|pfx|jks)$", "una llave"),
    (r"(^|/)id_(rsa|ed25519|ecdsa)(\.pub)?$", "una llave SSH"),
    (r"\.(bak|bundle|tar|tgz|zip|7z|age|gpg)$", "un respaldo o un comprimido"),
    (r"(^|/)(moderadores|admin|gm)\.txt$", "una lista de cuentas reales"),
]
PERMITIDOS = [r"(^|/)ejemplo\.env$", r"(^|/)\.env\.ejemplo$"]
# por CONTENIDO (sólo texto)
CONTENIDO = [
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "una llave privada"),
    (r"https://(discord(app)?\.com)/api/webhooks/\d+/[\w-]{20,}", "un webhook de Discord"),
    (r"\b(ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}", "un token de GitHub"),
    (r"\bAKIA[0-9A-Z]{16}\b", "una llave de AWS/R2"),
    (r"\$(argon2(id|i|d)?|pbkdf2[-\w]*|scrypt|2[aby])\$[^\s\"']{20,}", "un hash de contraseña"),
]


def problemas(ruta, texto):
    """Lo que tiene de malo un archivo (por su ruta y, si es texto, su contenido)."""
    r = ruta.replace("\\", "/")
    if any(re.search(p, r) for p in PERMITIDOS):
        return []
    mal = [f"{r}: es {que}" for p, que in NOMBRES if re.search(p, r, re.I)]
    if texto is not None:
        mal += [f"{r}: tiene {que}" for p, que in CONTENIDO if re.search(p, texto)]
    return mal


def leer(p):
    try:
        datos = p.read_bytes()
    except OSError:
        return None
    if b"\0" in datos[:4096]:
        return None
    return datos.decode("utf-8", "replace")


def archivos_de_git():
    salida = subprocess.run(["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"], cwd=RAIZ,
                            capture_output=True, check=True).stdout
    return [x for x in salida.decode("utf-8").split("\0") if x]


def main(args):
    rutas = args or archivos_de_git()
    mal = []
    for r in rutas:
        p = Path(r) if args else RAIZ / r
        mal += problemas(r, leer(p) if p.is_file() else None)
    if mal:
        print("⛔ guardia: esto NO puede entrar al repo (es público):\n  " + "\n  ".join(mal))
        return 1
    print(f"✔ guardia: {len(rutas)} archivos revisados, nada prohibido")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
