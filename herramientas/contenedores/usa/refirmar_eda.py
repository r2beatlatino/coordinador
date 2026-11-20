"""Vuelve a firmar la lista del cliente de EDA del ENSAYO con el servidor nuevo (VPS de USA, 185.147.157.33:25910).
Cambia SÓLO `servidor` (y `iat`); todo lo demás (version, base, canje, files, aud) queda igual. La firma, con la
clave de PUBLICACIÓN de la plataforma (la de siempre, en la carpeta de `ENENOS_CLAVES`, fuera del repo: no se imprime ni se copia), y se
verifica con su pública antes de escribir.  python refirmar_eda.py <entrada.jws> <salida.jws>"""
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

import os  # noqa: E402
# (coordinador) la firma es la del propio repo, servidor/firma_ed25519.py (antes: la copia del repo de GunBound)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from servidor import firma_ed25519 as ed  # noqa: E402

CLAVES = Path(os.environ.get("ENENOS_CLAVES") or sys.exit("⛔ falta ENENOS_CLAVES (la carpeta con publicacion_actual.pem)"))
PKCS8 = bytes.fromhex("302e020100300506032b657004220420")
NUEVO = "185.147.157.33:25910"


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def de_b64u(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


ent, sal = sys.argv[1], sys.argv[2]
a0, b0, f0 = Path(ent).read_text("ascii").strip().split(".")
cab, carga = json.loads(de_b64u(a0)), json.loads(de_b64u(b0))
assert cab["typ"] == "eda-manifiesto" and carga["aud"] == "eda-launcher", "no es una lista de EDA"
der = base64.b64decode("".join(x for x in (CLAVES / "publicacion_actual.pem").read_text("ascii").splitlines()
                               if x and not x.startswith("-----")))
assert len(der) == 48 and der.startswith(PKCS8), "la clave no es Ed25519 PKCS#8"
semilla = der[16:]
pub = ed.publica(semilla)
kid = hashlib.sha256(pub).hexdigest()[:16]
assert kid == cab["kid"], "la clave actual no es la que firmó la lista de antes"
antes = carga["servidor"]
carga["servidor"] = NUEVO
carga["iat"] = int(time.time())
a = b64u(json.dumps(cab, separators=(",", ":")).encode())
b = b64u(json.dumps(carga, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
firma = ed.firmar(semilla, f"{a}.{b}".encode())
assert ed.verificar(pub, f"{a}.{b}".encode(), firma), "la firma recién hecha no verifica"
assert not ed.verificar(pub, f"{a}.{b}x".encode(), firma), "⟲ el control: con un byte cambiado tendría que fallar"
Path(sal).write_text(f"{a}.{b}.{b64u(firma)}", "ascii")
print(f"ok: servidor {antes} -> {NUEVO} · kid {kid} · {len(carga.get('files', []))} archivos · firma verificada")
