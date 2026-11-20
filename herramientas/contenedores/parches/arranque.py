# -*- coding: utf-8 -*-
"""arranque — lo que corre el contenedor del servidor de parches: arma `config.json` en `/tmp` y llama a `patchserver.py`.

Va DENTRO de la imagen (`/app/arranque.py`). No toca `patchserver.py`: traduce las variables `PARCHES_*` al único
`config.json` que el servidor espera recibir por argumento.

⛔ `status_password` llega por `PARCHES_CLAVE_PANEL` o leyendo el archivo `PARCHES_CLAVE_PANEL_ARCHIVO` (secreto de
   Docker). Si no está ninguno de los dos, queda vacío y el panel viejo responde 503 («panel deshabilitado»).
   Nunca se imprime ni se escribe en ningún log, y el `config.json` temporal se crea con modo `0600`.
"""
import json
import os
import runpy
import sys
import tempfile


def _entero(env, nombre, omision):
    val = (env.get(nombre) or "").strip()
    if not val:
        return omision
    try:
        return int(val)
    except ValueError:
        sys.exit(f"⛔ {nombre} tiene que ser un número entero (recibí: {val!r})")


def _leer_clave_panel(env):
    """Devuelve la clave del panel desde `PARCHES_CLAVE_PANEL` o `PARCHES_CLAVE_PANEL_ARCHIVO`, o '' si no hay."""
    directa = env.get("PARCHES_CLAVE_PANEL") or ""
    if directa:
        return directa
    ruta = (env.get("PARCHES_CLAVE_PANEL_ARCHIVO") or "").strip()
    if not ruta:
        return ""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read().rstrip("\r\n")
    except OSError as e:
        sys.exit(f"⛔ no pude leer PARCHES_CLAVE_PANEL_ARCHIVO ({ruta}): {e.strerror or e}")


def armar_config(env=None):
    """Arma el diccionario de `config.json` a partir de las variables `PARCHES_*`."""
    if env is None:
        env = os.environ
    cfg = {
        "listen": (env.get("PARCHES_HOST") or "0.0.0.0").strip(),
        "port": _entero(env, "PARCHES_PUERTO", 8080),
        "clean_db": (env.get("PARCHES_BASE") or "/juego/datos.db").strip(),
        "status_file": (env.get("PARCHES_STATUS") or "/juego/status.json").strip(),
        "releases_dir": (env.get("PARCHES_RELEASES") or "/releases").strip(),
        "current": (env.get("PARCHES_RELEASE_ACTIVA") or "").strip(),
        # ★ 16-nov (dos servers por juego): la lista del cliente del server de PRUEBA (`/manifest?canal=prueba`).
        #   Vacía = el de prueba usa la misma lista que prod.
        "current_prueba": (env.get("PARCHES_RELEASE_PRUEBA") or "").strip(),
        "file_base_url": (env.get("PARCHES_URL_ARCHIVOS") or "").strip(),
        # ★ 18-nov: R2 para la release de prod (sólo si `r2.json` lo dice; ver patchserver.release_en_r2)
        "file_base_url_r2": (env.get("PARCHES_URL_R2") or "").strip(),
        "launcher_version": (env.get("PARCHES_LAUNCHER_VERSION") or "0").strip(),
        "launcher_bin": (env.get("PARCHES_LAUNCHER_BIN") or "").strip(),
        "launcher_url": (env.get("PARCHES_LAUNCHER_URL") or "").strip(),
        "token_ttl_sec": _entero(env, "PARCHES_TOKEN_TTL_SEG", 3600),
        "quota_mb_per_token": _entero(env, "PARCHES_CUOTA_TOKEN_MB", 1500),
        "per_ip_quota_mb_per_hour": _entero(env, "PARCHES_CUOTA_IP_MB_HORA", 3000),
        "per_ip_auth_per_hour": _entero(env, "PARCHES_AUTH_IP_HORA", 30),
        "ban_minutes": _entero(env, "PARCHES_BAN_MINUTOS", 30),
        "login_mode": (env.get("PARCHES_LOGIN") or "").strip().lower(),
        "cuentas_public_key": (env.get("PARCHES_CUENTAS_CLAVE_PUBLICA") or "").strip(),
        "cuentas_url": (env.get("PARCHES_CUENTAS_URL") or env.get("R2_CUENTAS_URL") or "").strip(),
    }
    # ★ 15-nov (al comparar con el patchserver de PROD, que es del 26-jul): el server le ANUNCIA al launcher a qué
    #   dirección hablarle (`base`) y un mapa host -> IP de emergencia (`ips`); el launcher los guarda en su
    #   `net.json`. Es lo que deja mudar de dominio o de VPS sin recompilar el launcher. Vacías = no anuncia nada.
    base = (env.get("PARCHES_LAUNCHER_BASE") or "").strip()
    if base:
        cfg["launcher_base"] = base
    ips_txt = (env.get("PARCHES_LAUNCHER_IPS") or "").strip()
    if ips_txt:
        try:
            ips = json.loads(ips_txt)
        except ValueError:
            ips = None
        if not isinstance(ips, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in ips.items()):
            sys.exit('⛔ PARCHES_LAUNCHER_IPS tiene que ser un JSON {"host": "ip", …}')
        cfg["launcher_ips"] = ips
    clave = _leer_clave_panel(env)
    if clave:
        cfg["status_password"] = clave
    return cfg


def main():
    cfg = armar_config(os.environ)
    os.environ.pop("PARCHES_CLAVE_PANEL", None)  # no dejar el secreto suelto en el entorno del proceso

    carpeta_tmp = tempfile.mkdtemp(prefix="parches_")
    os.chmod(carpeta_tmp, 0o700)
    ruta_cfg = os.path.join(carpeta_tmp, "config.json")
    fd = os.open(ruta_cfg, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    aqui = os.path.dirname(os.path.abspath(__file__))
    servidor = os.path.join(aqui, "patchserver.py")
    sys.argv = [servidor, ruta_cfg]
    runpy.run_path(servidor, run_name="__main__")


if __name__ == "__main__":
    main()
