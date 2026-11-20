"""La lista de EDA del ENSAYO, con los ARCHIVOS de la de prod (version, base, files) y el SERVER del ensayo (servidor,
canje). Firma con la clave de publicación (la carpeta de `ENENOS_CLAVES`, fuera del repo; no se imprime), verificada antes de escribir.
   python eda_al_dia.py <prod.jws> <ensayo.jws> <salida.jws>"""
import base64, hashlib, json, sys, time
from pathlib import Path

import os  # noqa: E402
# (coordinador) la firma es la del propio repo, servidor/firma_ed25519.py (antes: la copia del repo de GunBound)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from servidor import firma_ed25519 as ed  # noqa: E402

PKCS8 = bytes.fromhex("302e020100300506032b657004220420")
b64u = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
de = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def leer(p):
    a, b, f = Path(p).read_text("ascii").strip().split(".")
    return json.loads(de(a)), json.loads(de(b))


cp, prod = leer(sys.argv[1])
ce, ens = leer(sys.argv[2])
for c, d in ((cp, prod), (ce, ens)):
    assert c["typ"] == "eda-manifiesto" and d["aud"] == "eda-launcher", "no es una lista de EDA"
der = base64.b64decode("".join(x for x in (Path(os.environ.get("ENENOS_CLAVES") or sys.exit("⛔ falta ENENOS_CLAVES (la carpeta con publicacion_actual.pem)")) / "publicacion_actual.pem").read_text("ascii").splitlines()
                               if x and not x.startswith("-----")))
assert len(der) == 48 and der.startswith(PKCS8)
semilla = der[16:]
pub = ed.publica(semilla)
assert hashlib.sha256(pub).hexdigest()[:16] == ce["kid"], "la clave actual no es la que firmó la lista del ensayo"
nueva = dict(prod)
nueva["servidor"], nueva["canje"] = ens["servidor"], ens["canje"]
nueva["iat"] = int(time.time())
assert "ensayo" in nueva["canje"] and nueva["servidor"].endswith(":25910"), "⛔ el server tiene que ser el del ensayo"
a = b64u(json.dumps(ce, separators=(",", ":")).encode())
b = b64u(json.dumps(nueva, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
f = ed.firmar(semilla, f"{a}.{b}".encode())
assert ed.verificar(pub, f"{a}.{b}".encode(), f)
assert not ed.verificar(pub, f"{a}.{b}x".encode(), f), "⟲ control"
Path(sys.argv[3]).write_text(f"{a}.{b}.{b64u(f)}", "ascii")
print(f"ok: version {ens['version']} -> {nueva['version']} · servidor {nueva['servidor']} · canje {nueva['canje']} · "
      f"{len(nueva['files'])} archivos · firma verificada")
