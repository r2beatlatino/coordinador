"""★ 21-nov — FIRMA la lista de Eñeñosbit 2027 (el R2Beat moderno) con la clave de PUBLICACIÓN de la PLATAFORMA y la
sube al VPS de USA. El contenido lo arma `moderno_lista.sh` en el VPS (/opt/enenos/moderno_web/.trabajo/lista.json);
la privada vive SÓLO en la carpeta de `ENENOS_CLAVES` (fuera del repo y de todo VPS: no se imprime ni se copia).

    ENENOS_CLAVES=<carpeta> python herramientas/contenedores/usa/moderno_firmar.py            # bajar, firmar, subir
    ENENOS_CLAVES=<carpeta> python herramientas/contenedores/usa/moderno_firmar.py --no-subir # sólo firmar (prueba)

★ 21-nov `--prueba`: la del SERVIDOR DE PRUEBA (.trabajo/prueba.json → moderno_web/prueba.jws).
Mudarse a otra IP = en el VPS `MODERNO_SERVIDOR=<ip:28004> bash /opt/enenos/moderno_lista.sh` y después esto.
Antes de escribir: la firma se verifica con su pública, y el control al revés (un byte cambiado) tiene que fallar."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from servidor import firma_ed25519 as ed  # noqa: E402

VPS = "root@185.147.157.33"
LLAVE_SSH = str(Path.home() / ".ssh" / "eda_vps")
PRUEBA = "--prueba" in sys.argv
CONTENIDO = "/opt/enenos/moderno_web/.trabajo/%s.json" % ("prueba" if PRUEBA else "lista")
DESTINO = "/opt/enenos/moderno_web/%s.jws" % ("prueba" if PRUEBA else "lista")
TYP = "r2beat-moderno-manifiesto"
AUD = "r2beat-moderno-launcher"
KID_PLATAFORMA = "140674dc24472102"
PKCS8 = bytes.fromhex("302e020100300506032b657004220420")


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def ssh(*args, **kw):
    return subprocess.run(["ssh", "-i", LLAVE_SSH, VPS, *args], check=True, **kw)


def main():
    claves = Path(os.environ.get("ENENOS_CLAVES") or sys.exit("⛔ falta ENENOS_CLAVES (la carpeta con publicacion_actual.pem)"))
    subir = "--no-subir" not in sys.argv
    carga = json.loads(ssh("cat", CONTENIDO, capture_output=True).stdout.decode("utf-8"))
    assert carga.get("juego") == "r2beat-moderno" and carga.get("files"), "no es el contenido de la lista del moderno"
    host, _, puerto = carga["servidor"].rpartition(":")
    assert host and len(host) <= 29 - len(puerto), "el host no entra en el exe"
    der = base64.b64decode("".join(x for x in (claves / "publicacion_actual.pem").read_text("ascii").splitlines()
                                   if x and not x.startswith("-----")))
    assert len(der) == 48 and der.startswith(PKCS8), "la clave no es Ed25519 PKCS#8"
    semilla = der[16:]
    pub = ed.publica(semilla)
    kid = hashlib.sha256(pub).hexdigest()[:16]
    assert kid == KID_PLATAFORMA, "la clave no es la de publicación de la plataforma"
    carga = dict(carga, aud=AUD, iat=int(time.time()))
    a = b64u(json.dumps({"alg": "EdDSA", "typ": TYP, "kid": kid}, separators=(",", ":")).encode())
    b = b64u(json.dumps(carga, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    firma = ed.firmar(semilla, f"{a}.{b}".encode())
    assert ed.verificar(pub, f"{a}.{b}".encode(), firma), "la firma recién hecha no verifica"
    assert not ed.verificar(pub, f"{a}.{b}x".encode(), firma), "⟲ el control: con un byte cambiado tendría que fallar"
    jws = f"{a}.{b}.{b64u(firma)}"
    print(f"ok: versión {carga['version']} · {len(carga['files'])} archivos · servidor {carga['servidor']} · kid {kid} · firma verificada")
    if not subir:
        Path(tempfile.gettempdir(), "moderno_lista.jws").write_text(jws, "ascii")
        print("(sin subir: quedó en", Path(tempfile.gettempdir(), "moderno_lista.jws"), ")")
        return
    ssh(f"[ -f {DESTINO} ] && cp {DESTINO} {DESTINO}.antes; cat > {DESTINO}.nueva && chmod 644 {DESTINO}.nueva "
        f"&& mv {DESTINO}.nueva {DESTINO} && sha256sum {DESTINO} | cut -c1-16", input=jws.encode("ascii"))
    print("subida:", DESTINO, "· local", hashlib.sha256(jws.encode("ascii")).hexdigest()[:16])


if __name__ == "__main__":
    main()
