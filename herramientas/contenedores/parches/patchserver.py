#!/usr/bin/env python3
"""
patchserver.py — Servidor de descargas/parcheo de R2BeatTEST (corre en el VPS).

Modelo "launcher viejo de Softnyx/Gunbound":
  1) El launcher hace login (mismas cuentas del juego, clean.db) -> recibe un TOKEN.
  2) Con el token pide el MANIFEST (lista de archivos del cliente + su MD5 + tamano).
  3) Compara MD5 local vs manifest y baja SOLO los archivos distintos.
  4) El servidor limita el trafico POR TOKEN y POR IP: si se pasan, baneo temporal.

Sin dependencias externas (solo stdlib). El HTTPS lo pone Caddy por delante
(reverse_proxy 127.0.0.1:8080), asi que aca hablamos HTTP plano en localhost.

Endpoints:
  GET  /health                         -> "ok"
  POST /auth        {user, pass_sha256_upper}  -> {token, ttl, quota_mb}
  GET  /manifest    (Bearer token)     -> manifest.json del release "current"
  GET  /files/<release>/<path...>      (Bearer token) -> archivo (con cuota/baneo)

Uso:  python3 patchserver.py /opt/r2beat/patchserver/config.json
"""
import sys, os, json, time, hmac, hashlib, sqlite3, threading, secrets, posixpath
import base64, urllib.parse, urllib.request  # pase: (urllib.parse: ?canal= del manifest, 16-nov)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ----------------------------------------------------------------------------
CFG = {}
LOCK = threading.Lock()
TOKENS = {}     # token -> {uid, user, exp, used, ip}
IP_STATE = {}   # ip    -> {bytes, auth, win}   (ventana de 1h)
BANS = {}       # clave (ip o token) -> unban_epoch
USED_PASE_JTIS = {}  # jti -> exp_epoch (un solo uso)  # pase:
_PUB_CACHE = {"raw": None, "pub": None}  # pase:

MB = 1024 * 1024


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def load_cfg(path):
    global CFG
    with open(path, "r", encoding="utf-8") as f:
        CFG = json.load(f)
    CFG.setdefault("listen", "127.0.0.1")
    CFG.setdefault("port", 8080)
    CFG.setdefault("token_ttl_sec", 3600)
    CFG.setdefault("quota_mb_per_token", 1500)
    CFG.setdefault("per_ip_quota_mb_per_hour", 3000)
    CFG.setdefault("per_ip_auth_per_hour", 30)
    CFG.setdefault("ban_minutes", 30)
    CFG.setdefault("launcher_version", "0")
    CFG.setdefault("launcher_bin", "")  # ruta al Launcher.exe que se sirve para auto-update
    CFG.setdefault("file_base_url", "")  # si se setea, el manifest sirve los archivos desde esta URL (CDN Cloudflare) en vez de /files local
    # ★ 18-nov (Benja: «R2 descarga principal, CDN del VPS secundaria»): la release de PROD del 2013 se baja de
    #   Cloudflare R2 (10 GB gratis) SÓLO si `releases_dir/r2.json` dice que está entera allá (lo escribe
    #   `usa/r2_al_dia.py` después de verificar cada archivo). El manifest lleva además `respaldo` = la CDN.
    CFG.setdefault("file_base_url_r2", "")
    CFG.setdefault("launcher_url", "")   # si se setea, el auto-update del launcher baja el .exe del CDN (rápido) en vez de /launcher/bin (VPS lento)
    CFG.setdefault("login_mode", "")  # pase:
    CFG.setdefault("cuentas_public_key", "")  # pase:
    CFG.setdefault("cuentas_url", "")  # pase:
    if modo_pase():  # pase:
        init_pase_key()  # pase:


def md5_file(path, buf=1024 * 1024):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# Meta del launcher (md5/size) con cache por mtime.
_LBIN = {"path": None, "mtime": 0, "md5": None, "size": 0}


def launcher_meta():
    p = CFG.get("launcher_bin", "")
    if not p or not os.path.isfile(p):
        return None
    mt = os.path.getmtime(p)
    if _LBIN["path"] != p or _LBIN["mtime"] != mt:
        _LBIN.update(path=p, mtime=mt, md5=md5_file(p), size=os.path.getsize(p))
    meta = {"version": CFG.get("launcher_version", "0"), "md5": _LBIN["md5"], "size": _LBIN["size"]}
    # ★ 2026-07-26: el server ANUNCIA a que host debe hablarle el launcher ("base") y un mapa
    #   host->IP de emergencia ("ips"). El launcher v1.2+ los guarda en %LOCALAPPDATA%\r2beat\net.json
    #   y esos valores mandan sobre lo que trae compilado -> mudarse de dominio o de VPS ya NO exige
    #   recompilar el .exe ni que nadie reinstale nada. Nacio porque r2beat.lat cayo en serverHold y
    #   la flota entera quedo apuntando a un hostname muerto que no se podia cambiar.
    b = CFG.get("launcher_base")
    if b:
        meta["base"] = b
    ips = CFG.get("launcher_ips")
    if isinstance(ips, dict) and ips:
        meta["ips"] = ips
    lu = CFG.get("launcher_url")  # si está, el launcher baja su update del CDN (rápido) en vez del VPS lento
    if lu:
        meta["url"] = lu + ("&" if "?" in lu else "?") + "v=" + _LBIN["md5"][:12]
    return meta


# ----------------------------------------------------------------------------
# Cuentas: leemos la MISMA users(username, pass_hash) de clean.db (solo lectura).
def verify_account(user, pass_sha256_upper):
    if modo_pase():  # pase:
        return None  # pase:
    if not user or not pass_sha256_upper or len(pass_sha256_upper) != 64:
        return None
    try:
        c = sqlite3.connect(CFG["clean_db"])
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()
        c.close()
    except Exception as e:
        log("DB error:", e)
        return None
    if row and row["pass_hash"].upper() == pass_sha256_upper.upper():
        # user_id puede llamarse distinto segun la version del esquema; tomamos lo que haya.
        uid = row["user_id"] if "user_id" in row.keys() else (row["id"] if "id" in row.keys() else 0)
        return {"uid": uid, "user": row["username"]}
    return None


# Verificacion local de pases firmados (Ed25519 RFC 8032, stdlib pura)  # pase:
_ED_P = 2 ** 255 - 19  # pase:
_ED_Q = 2 ** 252 + 27742317777372353535851937790883648493  # pase:
_ED_D = -121665 * pow(121666, _ED_P - 2, _ED_P) % _ED_P  # pase:
_ED_RM1 = pow(2, (_ED_P - 1) // 4, _ED_P)  # pase:


def _ed_rec_x(y, s):  # pase:
    if y >= _ED_P:  # pase:
        return None  # pase:
    x2 = (y * y - 1) * pow(_ED_D * y * y + 1, _ED_P - 2, _ED_P)  # pase:
    if x2 == 0:  # pase:
        return None if s else 0  # pase:
    x = pow(x2, (_ED_P + 3) // 8, _ED_P)  # pase:
    if (x * x - x2) % _ED_P:  # pase:
        x = x * _ED_RM1 % _ED_P  # pase:
    if (x * x - x2) % _ED_P:  # pase:
        return None  # pase:
    return (_ED_P - x) if (x & 1) != s else x  # pase:


_ED_GY = 4 * pow(5, _ED_P - 2, _ED_P) % _ED_P  # pase:
_ED_GX = _ed_rec_x(_ED_GY, 0)  # pase:
_ED_G = (_ED_GX, _ED_GY, 1, _ED_GX * _ED_GY % _ED_P)  # pase:


def _ed_add(a, b):  # pase:
    A = (a[1] - a[0]) * (b[1] - b[0]) % _ED_P  # pase:
    B = (a[1] + a[0]) * (b[1] + b[0]) % _ED_P  # pase:
    C = 2 * a[3] * b[3] * _ED_D % _ED_P  # pase:
    D = 2 * a[2] * b[2] % _ED_P  # pase:
    E, F, G, H = B - A, D - C, D + C, B + A  # pase:
    return (E * F % _ED_P, G * H % _ED_P, F * G % _ED_P, E * H % _ED_P)  # pase:


def _ed_mul(s, pt):  # pase:
    r = (0, 1, 1, 0)  # pase:
    while s > 0:  # pase:
        if s & 1:  # pase:
            r = _ed_add(r, pt)  # pase:
        pt = _ed_add(pt, pt)  # pase:
        s >>= 1  # pase:
    return r  # pase:


def _ed_dec(b):  # pase:
    if len(b) != 32:  # pase:
        return None  # pase:
    y = int.from_bytes(b, "little")  # pase:
    x = _ed_rec_x(y & ((1 << 255) - 1), y >> 255)  # pase:
    return None if x is None else (x, y & ((1 << 255) - 1), 1, x * (y & ((1 << 255) - 1)) % _ED_P)  # pase:


def _ed25519_verify(pub, msg, sig):  # pase:
    if len(pub) != 32 or len(sig) != 64:  # pase:
        return False  # pase:
    A, R = _ed_dec(pub), _ed_dec(sig[:32])  # pase:
    s = int.from_bytes(sig[32:], "little")  # pase:
    if A is None or R is None or s >= _ED_Q:  # pase:
        return False  # pase:
    h = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _ED_Q  # pase:
    P1, P2 = _ed_mul(s, _ED_G), _ed_add(R, _ed_mul(h, A))  # pase:
    return (P1[0] * P2[2] - P2[0] * P1[2]) % _ED_P == 0 and (P1[1] * P2[2] - P2[1] * P1[2]) % _ED_P == 0  # pase:


def _b64u_dec(txt):  # pase:
    s = str(txt or "").strip()  # pase:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # pase:


def modo_pase():  # pase:
    m = (CFG.get("login_mode") or os.environ.get("PARCHES_LOGIN") or "").strip().lower()  # pase:
    return m == "pase"  # pase:


def parse_public_key(valor):  # pase:
    if isinstance(valor, (bytes, bytearray)):  # pase:
        return bytes(valor) if len(valor) == 32 else None  # pase:
    txt = str(valor or "").strip()  # pase:
    if not txt:  # pase:
        return None  # pase:
    if txt.startswith("{"):  # pase:
        try:  # pase:
            d = json.loads(txt)  # pase:
            if isinstance(d.get("keys"), list) and d["keys"]:  # pase:
                d = d["keys"][0]  # pase:
            txt = str(d.get("x") or "").strip()  # pase:
        except Exception:  # pase:
            return None  # pase:
    if len(txt) == 64:  # pase:
        try:  # pase:
            return bytes.fromhex(txt)  # pase:
        except ValueError:  # pase:
            pass  # pase:
    try:  # pase:
        raw = _b64u_dec(txt)  # pase:
        return raw if len(raw) == 32 else None  # pase:
    except Exception:  # pase:
        return None  # pase:


def init_pase_key():  # pase:
    raw = (CFG.get("cuentas_public_key") or os.environ.get("PARCHES_CUENTAS_CLAVE_PUBLICA") or "").strip()  # pase:
    pub = parse_public_key(raw)  # pase:
    if pub:  # pase:
        _PUB_CACHE.update(raw=raw, pub=pub)  # pase:
        return pub  # pase:
    url = (CFG.get("cuentas_url") or os.environ.get("PARCHES_CUENTAS_URL") or os.environ.get("R2_CUENTAS_URL") or "").strip().rstrip("/")  # pase:
    if url:  # pase:
        for suf in ("/clave-publica", "/cuentas/clave-publica"):  # pase:
            try:  # pase:
                with urllib.request.urlopen(url + suf, timeout=5) as r:  # pase:
                    pub = parse_public_key(r.read().decode("utf-8", "replace"))  # pase:
                if pub:  # pase:
                    _PUB_CACHE.update(raw=url, pub=pub)  # pase:
                    return pub  # pase:
            except Exception:  # pase:
                continue  # pase:
    _PUB_CACHE.update(raw=None, pub=None)  # pase:
    log("AVISO: PARCHES_LOGIN=pase pero no hay clave publica de Cuenta Enenos")  # pase:
    return None  # pase:


def get_public_key():  # pase:
    raw = (CFG.get("cuentas_public_key") or os.environ.get("PARCHES_CUENTAS_CLAVE_PUBLICA") or "").strip()  # pase:
    if raw:  # pase:
        if _PUB_CACHE["raw"] != raw or not _PUB_CACHE["pub"]:  # pase:
            _PUB_CACHE.update(raw=raw, pub=parse_public_key(raw))  # pase:
        return _PUB_CACHE["pub"]  # pase:
    return _PUB_CACHE["pub"]  # pase:


def verify_pase(pase_txt, ahora=None, aud="parches"):  # pase: (★ 16-nov: aud = «r2beat2013-subir» para los AUTORIZADOS a subir)
    pub = get_public_key()  # pase:
    if not pub or not isinstance(pase_txt, str):  # pase:
        return None  # pase:
    partes = pase_txt.strip().split(".")  # pase:
    if len(partes) != 3:  # pase:
        return None  # pase:
    try:  # pase:
        if partes[0] != "r2p1":  # pase:
            cab = json.loads(_b64u_dec(partes[0]))  # pase:
            if cab.get("alg") != "EdDSA" or cab.get("typ") != "JWT":  # pase:
                return None  # pase:
        firma = _b64u_dec(partes[2])  # pase:
        msg = f"{partes[0]}.{partes[1]}".encode("ascii")  # pase:
        if not _ed25519_verify(pub, msg, firma):  # pase:
            return None  # pase:
        carga = json.loads(_b64u_dec(partes[1]))  # pase:
    except Exception:  # pase:
        return None  # pase:
    ahora = time.time() if ahora is None else float(ahora)  # pase:
    if not isinstance(carga, dict) or carga.get("iss") != "r2beat-portero" or carga.get("aud") != aud:  # pase:
        return None  # pase:
    if int(carga.get("exp") or 0) <= ahora:  # pase:
        return None  # pase:
    try:  # pase:
        uid = int(carga.get("sub"))  # pase:
    except (TypeError, ValueError):  # pase:
        return None  # pase:
    jti = carga.get("jti")  # pase:
    if uid <= 0 or not isinstance(jti, str) or not jti:  # pase:
        return None  # pase:
    with LOCK:  # pase:
        for k in [k for k, v in USED_PASE_JTIS.items() if v <= ahora]:  # pase:
            USED_PASE_JTIS.pop(k, None)  # pase:
        if jti in USED_PASE_JTIS:  # pase:
            return None  # pase:
        if len(USED_PASE_JTIS) >= 50000:  # pase:
            USED_PASE_JTIS.pop(next(iter(USED_PASE_JTIS)), None)  # pase:
        USED_PASE_JTIS[jti] = int(carga.get("exp") or (ahora + 300))  # pase:
    return {"uid": uid, "user": str(uid), "nombre": str(carga.get("nombre") or "")[:40]}  # pase: (★ §37 el nombre visible, para firmar las subidas)


# ----------------------------------------------------------------------------
# Editor admin: edita SOLO chars.nickname / chars.exp / chars.coin (rcoin).
# Queries PARAMETRIZADAS. NO toca server-clean.py: el game relee la DB al re-login.
def admin_update(uid, nickname, exp, coin):
    try:
        c = sqlite3.connect(CFG["clean_db"], timeout=10)
        c.row_factory = sqlite3.Row
    except Exception as e:
        return None, "DB error: %s" % e
    try:
        ch = c.execute("SELECT uid, nickname, exp, coin FROM chars WHERE uid=?", (uid,)).fetchone()
        if not ch:
            return None, "ese uid no tiene personaje (chars)"
        changes = []
        if nickname is not None:
            nickname = str(nickname).strip()
            if not (1 <= len(nickname) <= 16):
                return None, "el apodo debe tener entre 1 y 16 caracteres"
            dup = c.execute("SELECT uid FROM chars WHERE nickname=? COLLATE NOCASE AND uid<>?",
                            (nickname, uid)).fetchone()
            if dup:
                return None, "ese apodo ya lo usa el uid %s" % dup["uid"]
            if nickname != (ch["nickname"] or ""):
                c.execute("UPDATE chars SET nickname=? WHERE uid=?", (nickname, uid))
                changes.append("nick -> " + nickname)
        # exp y coin (rcoin): mismo patron, columna de lista fija (no user input) -> sin inyeccion
        for field, val in (("exp", exp), ("coin", coin)):
            if val is None:
                continue
            try:
                val = int(val)
            except Exception:
                return None, field + " invalido"
            if not (0 <= val <= 2_000_000_000):
                return None, field + " fuera de rango (0 .. 2.000.000.000)"
            if val != (ch[field] or 0):
                c.execute("UPDATE chars SET %s=? WHERE uid=?" % field, (val, uid))
                changes.append(("rcoin" if field == "coin" else field) + " -> " + str(val))
        if not changes:
            return None, "no cambiaste nada"
        c.commit()
        prof = dict(c.execute("SELECT uid, nickname, exp, coin FROM chars WHERE uid=?", (uid,)).fetchone())
        return {"profile": prof, "changes": changes}, None
    finally:
        c.close()


# ----------------------------------------------------------------------------
# Baneos / cuotas
def is_banned(*keys):
    now = time.time()
    for k in keys:
        u = BANS.get(k)
        if u and u > now:
            return int(u - now)
    return 0


def ban(key, why):
    until = time.time() + CFG["ban_minutes"] * 60
    BANS[key] = until
    log(f"BAN {key} por {CFG['ban_minutes']}min ({why})")


def ip_window(ip):
    now = time.time()
    st = IP_STATE.get(ip)
    if not st or now - st["win"] >= 3600:
        st = {"bytes": 0, "auth": 0, "win": now}
        IP_STATE[ip] = st
    return st


# ----------------------------------------------------------------------------
# Manifest del release activo (cache simple, se recalcula si cambia el archivo)
_MANIFEST_CACHE = {}          # (ruta del manifest, de quién) -> (mtimes, data)


SUBIDAS = None                # ★ 16-nov: lo que suben los amigos al server de prueba (subidas.py)
AUD_SUBIR = "r2beat2013-subir"  # el pase de los AUTORIZADOS a subir directo (Cuenta Eñeños lo da sólo a los aprobados)


def subidas():
    global SUBIDAS
    if SUBIDAS is None:
        try:
            import subidas as _s
        except ImportError:                                     # (en la imagen va al lado)
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import subidas as _s
        SUBIDAS = _s.Subidas(CFG["releases_dir"], CFG)
    return SUBIDAS


def release_de(canal=None):
    """★ 16-nov (dos servers por juego): la release de la lista pedida. `prueba` = la del server de PRUEBA (la última
    armada con lo que subieron los amigos, o `current_prueba`); si no hay ninguna, la de prod. Otra cosa = prod."""
    if canal == "prueba":
        rel = subidas().release_prueba() if os.path.isdir(CFG.get("releases_dir") or "") else CFG.get("current_prueba")
        if rel:
            return rel, ("prueba" if rel != CFG["current"] else "prod")
    return CFG["current"], "prod"


def current_manifest(canal=None):
    rel, de_quien = release_de(canal)
    return manifest_de_release(rel, de_quien)


def release_en_r2():
    """La release que `r2_al_dia.py` dejó ENTERA y verificada en R2 (o None). Sin `file_base_url_r2`, ninguna."""
    if not CFG.get("file_base_url_r2"):
        return None
    try:
        with open(os.path.join(CFG["releases_dir"], "r2.json"), "r", encoding="utf-8") as f:
            return json.load(f).get("release") or None
    except (OSError, ValueError):
        return None


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0


def manifest_de_release(rel, de_quien):
    mpath = os.path.join(CFG["releases_dir"], rel, "manifest.json")
    if not os.path.isfile(mpath):
        return None
    # (r2.json también cuenta: al cambiar, la base cambia sin tocar el manifest)
    mt = (os.path.getmtime(mpath), _mtime(os.path.join(CFG["releases_dir"], "r2.json")))
    c = _MANIFEST_CACHE.get((mpath, de_quien))   # (★ 18-nov: y de quién: la base depende de eso)
    if c and c[0] == mt:
        return c[1]
    with open(mpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["canal"] = de_quien
    fb = CFG.get("file_base_url")
    # base absoluta (CDN Cloudflare, sin token -> cacheable) o relativa al patch server
    # ★ 18-nov: un ENVÍO sin aprobar (vista previa de un mod) NO va a la CDN: sigue por /files, con sesión (en la CDN
    #   quedaría público y guardado un año)
    data["base"] = (fb.rstrip("/") + "/" + rel + "/") if fb and de_quien != "envio" else f"/files/{rel}/"
    # ★ 18-nov: sólo PROD va a R2, y sólo si está entera allá; la de prueba y los envíos nunca. `respaldo` = la CDN
    #   (el launcher baja de ahí lo que R2 no le dio; uno viejo lo ignora)
    if fb and de_quien == "prod" and rel == release_en_r2():
        data["respaldo"] = data["base"]
        data["base"] = CFG["file_base_url_r2"].rstrip("/") + "/" + rel + "/"
    _MANIFEST_CACHE[(mpath, de_quien)] = (mt, data)
    return data


def safe_join(release, rel_path):
    """Evita path traversal: el resultado debe quedar dentro de releases_dir/release."""
    base = os.path.realpath(os.path.join(CFG["releases_dir"], release))
    root = os.path.realpath(CFG["releases_dir"])
    if os.path.commonpath([base, root]) != root:
        return None
    rel_path = posixpath.normpath("/" + rel_path).lstrip("/")
    full = os.path.realpath(os.path.join(base, rel_path))
    if os.path.commonpath([full, base]) != base:
        return None
    return full


# ----------------------------------------------------------------------------
ADMIN_HTML = r"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>R2Beat · Panel</title>
<style>
:root{
  --bg:#121212;--surface:#1e1e1e;--surface2:#242424;--surface3:#2c2c2c;
  --border:#2e2e2e;--line:#2a2a2a;
  --text:rgba(255,255,255,.87);--muted:rgba(255,255,255,.55);--faint:rgba(255,255,255,.38);
  --primary:#82b1ff;--btn:#2d5fb5;--btn-h:#3a72d0;
  --green:#69f0ae;--amber:#ffca6a;--error:#cf6679;
}
*{box-sizing:border-box;margin:0;padding:0;font-family:Roboto,"Segoe UI",Arial,sans-serif}
body{background:var(--bg);color:var(--text);min-height:100vh;padding:18px;-webkit-font-smoothing:antialiased}
h1{color:var(--text);font-size:21px;font-weight:500;margin-bottom:2px;letter-spacing:.2px}
.sub{color:var(--muted);font-size:12px;margin-bottom:16px}
.wrap{max-width:1180px;margin:0 auto}
input{background:var(--surface2);border:1px solid #3a3a3a;color:var(--text);border-radius:6px;padding:9px 12px;font-size:14px}
input:focus{outline:0;border-color:var(--primary)}
button{background:var(--btn);border:0;color:#fff;border-radius:6px;padding:8px 16px;font-weight:500;cursor:pointer;text-transform:uppercase;font-size:13px;letter-spacing:.4px}
button:hover{background:var(--btn-h);box-shadow:0 2px 6px rgba(0,0,0,.4)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin:0 auto 14px;box-shadow:0 1px 2px rgba(0,0,0,.5)}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.stat{flex:1;min-width:130px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,.5)}
.stat .n{font-size:30px;font-weight:500;color:var(--primary)}
.stat.on .n{color:var(--green)}.stat.warn .n{color:var(--error)}
.stat .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:3px}
.toolbar{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.toolbar input{flex:0 0 260px}
.chip{background:var(--surface2);border:1px solid var(--border);color:var(--muted);border-radius:18px;padding:6px 13px;font-size:12px;cursor:pointer;user-select:none}
.chip:hover{border-color:var(--primary);color:var(--text)}
.chip.on{background:var(--btn);border-color:var(--btn);color:#fff}
.tw{overflow:auto;max-height:72vh;border-radius:6px;border:1px solid var(--line)}
table.grid{width:100%;border-collapse:collapse}
.grid th,.grid td{padding:8px 11px;border-bottom:1px solid var(--line);font-size:13px;text-align:left;white-space:nowrap}
.grid th{position:sticky;top:0;background:var(--surface3);cursor:pointer;user-select:none;color:var(--primary);font-size:11px;font-weight:500;text-transform:uppercase;letter-spacing:.5px;z-index:1}
.grid th:hover{color:#fff}.grid th .ar{color:#fff}
.grid td.num{text-align:right;font-family:"Roboto Mono",Consolas,monospace}
.grid td.dt{font-family:"Roboto Mono",Consolas,monospace;color:var(--muted)}
tr.grp:nth-child(even){background:rgba(255,255,255,.022)}
tr.grp.multi{cursor:pointer}
tr.grp:hover{background:var(--surface2)}
tr.sub td{background:rgba(0,0,0,.28);font-size:12px;color:var(--muted);border-bottom:1px solid var(--line)}
tr.sub td.ix{color:var(--text)}
.chev{display:inline-block;width:13px;color:var(--muted);font-size:11px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#4a4a4a;margin-right:7px;vertical-align:middle}
.dot.on{background:var(--green);box-shadow:0 0 8px var(--green)}
.b{display:inline-block;padding:1px 8px;border-radius:12px;font-size:11px;font-weight:500}
.lobby{background:#1e3a5f;color:#9fc9ff}.sala{background:#5a3a1e;color:#ffce9f}.jugando{background:#1e5a37;color:#9fffc4}
.ipchip{font-family:"Roboto Mono",Consolas,monospace;font-size:12px;padding:2px 7px;border-radius:5px;background:hsl(var(--h),45%,21%);border:1px solid hsl(var(--h),55%,45%);color:hsl(var(--h),80%,82%)}
.ipchip.none{background:var(--surface2);border-color:#383838;color:var(--muted)}
.ipchip b{color:#fff;background:rgba(0,0,0,.35);padding:0 5px;border-radius:8px;margin-left:3px}
.muted{color:var(--muted);font-size:12px}.stale{color:var(--amber)}.err{color:var(--error);text-align:center;margin:8px 0}
#login{max-width:420px;text-align:center}#panel{display:none}
button.mini{padding:3px 10px;font-size:12px;background:var(--surface3);text-transform:none;letter-spacing:0;font-weight:400}
button.mini:hover{background:var(--btn)}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.62);z-index:20;align-items:center;justify-content:center}
.modal .card{max-width:390px;width:92%;margin:0}
.fld{display:block;margin-bottom:11px}
.fld span{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.fld input{width:100%}
</style></head><body>
<div class="wrap">
<h1>R2Beat · Panel de gestión</h1><div class="sub">solo lectura · 1 fila por IP · click/hover para ver todas las cuentas · se actualiza cada 4s</div>
<div class="card" id="login">
  <p style="margin-bottom:10px">Ingresá la contraseña del panel:</p>
  <input type="password" id="pw" placeholder="contraseña" autofocus>
  <button onclick="entrar()">Entrar</button>
  <div class="err" id="lerr"></div>
</div>
<div id="panel">
  <div class="stats">
    <div class="stat on"><div class="n" id="s_online">0</div><div class="l">🟢 Online ahora</div></div>
    <div class="stat"><div class="n" id="s_acc">0</div><div class="l">Cuentas</div></div>
    <div class="stat"><div class="n" id="s_ips">0</div><div class="l">IPs distintas</div></div>
    <div class="stat warn"><div class="n" id="s_mip">0</div><div class="l">⚠ IPs multi-cuenta</div></div>
  </div>
  <div class="card">
    <div class="toolbar">
      <input id="q" placeholder="🔍 buscar usuario, nick o IP…" oninput="Q=this.value;render()">
      <span class="chip on" data-f="all" onclick="setFilter('all')">Todas</span>
      <span class="chip" data-f="online" onclick="setFilter('online')">🟢 Online</span>
      <span class="chip" data-f="multi" onclick="setFilter('multi')">⚠ Multi-cuenta</span>
      <span style="flex:1"></span>
      <span class="muted" id="count"></span>
      <button onclick="salir()">Salir</button>
    </div>
    <div id="warnbar" class="muted" style="margin-bottom:6px"></div>
    <div class="tw"><table class="grid">
      <thead><tr>
        <th data-k="online" onclick="setSort('online')">Estado<span class="ar"></span></th>
        <th data-k="last_ip" onclick="setSort('last_ip')">IP (cuentas)<span class="ar"></span></th>
        <th data-k="user" onclick="setSort('user')">Último login<span class="ar"></span></th>
        <th data-k="nick" onclick="setSort('nick')">Nick<span class="ar"></span></th>
        <th data-k="reg_time" onclick="setSort('reg_time')">Registrado<span class="ar"></span></th>
        <th data-k="last_time" onclick="setSort('last_time')">Última act.<span class="ar"></span></th>
        <th data-k="count" onclick="setSort('count')">Ctas.<span class="ar"></span></th>
        <th data-k="logins" onclick="setSort('logins')">Ses.<span class="ar"></span></th>
        <th data-k="exp" onclick="setSort('exp')">Exp<span class="ar"></span></th>
        <th style="cursor:default;color:var(--muted)">✎</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table></div>
    <div class="muted" style="margin-top:8px">Cada IP aparece <b>una vez</b> con su <b>color propio</b> · la fila muestra el <b>último que logueó</b> desde esa IP · <b>×N</b> = N cuentas (click en la fila o pasá el mouse para desplegarlas) · 🟢 = alguien de esa IP conectado ahora.</div>
  </div>
</div>
</div>
<div class="modal" id="editModal">
  <div class="card">
    <h1 style="font-size:17px;margin-bottom:2px">✎ Editar jugador</h1>
    <div class="sub" id="em_sub" style="margin-bottom:12px">—</div>
    <label class="fld"><span>Nick</span><input id="em_nick" maxlength="16"></label>
    <label class="fld"><span>Exp</span><input id="em_exp" type="number" min="0"></label>
    <label class="fld"><span>RCoin</span><input id="em_coin" type="number" min="0"></label>
    <div class="err" id="em_err" style="text-align:left;margin:0 0 8px"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button class="mini" onclick="cerrarEdit()">Cancelar</button>
      <button onclick="guardarEdit()">Guardar</button>
    </div>
    <div class="muted" style="margin-top:10px">Los cambios aplican cuando el jugador re-loguea.</div>
  </div>
</div>
<script>
var KEY=localStorage.getItem('r2pw')||'';var TIMER=null;
var DATA={accounts:[],ips:[],totals:{},online:{},onlineCount:0,stale:false};
var SK='last_time',SD=-1,FILTER='all',Q='',OPEN={};
function esc(s){return (''+(s==null?'':s)).replace(/[<>&]/g,function(c){return{'<':'&lt;','>':'&gt;','&':'&amp;'}[c];});}
function shortdt(s){if(!s)return '—';return (''+s).replace('T',' ').slice(5,16);}
function ipHue(ip){var h=0,i;ip=''+(ip||'');for(i=0;i<ip.length;i++)h=(h*31+ip.charCodeAt(i))%360;return h;}
function entrar(){KEY=document.getElementById('pw').value;if(!KEY)return;localStorage.setItem('r2pw',KEY);document.getElementById('lerr').textContent='';if(!TIMER)TIMER=setInterval(refresh,4000);refresh();}
function paro(){if(TIMER){clearInterval(TIMER);TIMER=null;}}
function salir(){paro();localStorage.removeItem('r2pw');KEY='';location.reload();}
function setSort(k){if(SK===k)SD=-SD;else{SK=k;SD=(k==='user'||k==='nick'||k==='last_ip')?1:-1;}render();}
function setFilter(f){FILTER=f;var c=document.querySelectorAll('.chip');for(var i=0;i<c.length;i++)c[i].classList.toggle('on',c[i].getAttribute('data-f')===f);render();}
function toggleIp(k){if(OPEN[k])delete OPEN[k];else OPEN[k]=1;render();}
function lt(a){return a.last_time||a.last_seen||'';}
async function refresh(){
  if(!KEY)return;
  try{
    var pr=await Promise.all([
      fetch('/accounts?key='+encodeURIComponent(KEY),{cache:'no-store'}),
      fetch('/status?key='+encodeURIComponent(KEY),{cache:'no-store'})
    ]);
    if(pr[0].status===401){paro();localStorage.removeItem('r2pw');KEY='';document.getElementById('login').style.display='block';document.getElementById('lerr').textContent='Contraseña incorrecta';return;}
    if(pr[0].status===429){var d=await pr[0].json().catch(function(){return{};});paro();document.getElementById('login').style.display='block';document.getElementById('lerr').textContent='Demasiados intentos. Espera '+Math.ceil((d.retry_sec||0)/60)+' min (el server banea la IP a los 8 fallos).';return;}
    if(pr[0].status===503){document.getElementById('lerr').textContent='Panel deshabilitado en el server';return;}
    var a=await pr[0].json();
    var s=pr[1].ok?await pr[1].json():{users:[],counts:{},online:0,stale:true};
    DATA.accounts=a.accounts||[];DATA.ips=a.ips||[];DATA.totals=a.totals||{};
    DATA.online={};DATA.onlineCount=s.online||0;DATA.stale=!!s.stale;
    (s.users||[]).forEach(function(u){DATA.online[u.nick]={state:u.state,online_s:u.online_s};});
    document.getElementById('login').style.display='none';
    document.getElementById('panel').style.display='block';
    render();
  }catch(e){var w=document.getElementById('warnbar');if(w)w.innerHTML='<span class="err">error de conexión</span>';}
}
function buildGroups(){
  var g={};
  DATA.accounts.forEach(function(a){
    var ip=a.last_ip||'';var key=ip||'(sin IP)';
    var grp=g[key];
    if(!grp){grp=g[key]={ip:ip,key:key,accs:[],sessions:0,last:'',online:false,rep:null};}
    grp.accs.push(a);grp.sessions+=a.logins||0;
    if(lt(a)>grp.last)grp.last=lt(a);
    if(DATA.online[a.nick])grp.online=true;
    if(!grp.rep||lt(a)>lt(grp.rep))grp.rep=a;
  });
  var arr=Object.keys(g).map(function(k){return g[k];});
  arr.forEach(function(grp){grp.accs.sort(function(x,y){return lt(y).localeCompare(lt(x));});});
  return arr;
}
function gval(grp){
  var r=grp.rep||{};
  switch(SK){
    case'online':return grp.online?1:0;
    case'last_ip':return grp.ip;
    case'user':return r.user||'';
    case'nick':return r.nick||'';
    case'reg_time':return r.reg_time||'';
    case'last_time':return grp.last;
    case'count':return grp.accs.length;
    case'logins':return grp.sessions;
    case'exp':return r.exp==null?-1:r.exp;
  }
  return '';
}
function render(){
  document.getElementById('s_online').textContent=DATA.onlineCount||0;
  document.getElementById('s_acc').textContent=DATA.totals.accounts||0;
  document.getElementById('warnbar').innerHTML=DATA.stale?'<span class="stale">⚠ online en vivo desactualizado (¿game server apagado?)</span>':'';
  var groups=buildGroups();
  document.getElementById('s_ips').textContent=groups.filter(function(g){return g.ip;}).length;
  document.getElementById('s_mip').textContent=groups.filter(function(g){return g.ip&&g.accs.length>1;}).length;
  var ql=Q.toLowerCase();
  groups=groups.filter(function(g){
    if(FILTER==='online'&&!g.online)return false;
    if(FILTER==='multi'&&g.accs.length<2)return false;
    if(ql){return g.ip.toLowerCase().indexOf(ql)>=0||g.accs.some(function(a){
      return (''+a.user).toLowerCase().indexOf(ql)>=0||(''+(a.nick||'')).toLowerCase().indexOf(ql)>=0;});}
    return true;
  });
  groups.sort(function(x,y){
    var vx=gval(x),vy=gval(y);if(vx==null)vx='';if(vy==null)vy='';
    if(typeof vx==='number'&&typeof vy==='number')return (vx-vy)*SD;
    return (''+vx).localeCompare(''+vy)*SD;
  });
  var html='';
  groups.forEach(function(g){
    var rep=g.rep||{},n=g.accs.length,hue=ipHue(g.ip),open=!!OPEN[g.key],multi=n>1;
    var bd=g.ip?('border-left:4px solid hsl('+hue+',65%,55%)'):'border-left:4px solid #3a3a3a';
    var chev=multi?('<span class="chev">'+(open?'▾':'▸')+'</span>'):'<span class="chev" style="opacity:.2">·</span>';
    var ipc=g.ip?('<span class="ipchip" style="--h:'+hue+'">'+esc(g.ip)+(multi?' <b>×'+n+'</b>':'')+'</span>')
                :('<span class="ipchip none">(sin IP)'+(multi?' <b>×'+n+'</b>':'')+'</span>');
    var ro=DATA.online[rep.nick];
    var dot='<span class="dot'+(g.online?' on':'')+'"></span>';
    var st=ro?('<span class="b '+ro.state+'">'+esc(ro.state)+'</span>'):(g.online?'<span class="b jugando">online</span>':'<span class="muted">offline</span>');
    var title=multi?('Cuentas ('+n+'): '+g.accs.map(function(a){return a.user;}).join(', ')):'';
    html+='<tr class="grp'+(multi?' multi':'')+'" style="'+bd+'"'+(multi?(' onclick="toggleIp(\''+g.key.replace(/'/g,"")+'\')" title="'+esc(title)+'"'):'')+'>'+
      '<td>'+dot+st+'</td><td>'+chev+ipc+'</td><td><b>'+esc(rep.user||'—')+'</b></td><td>'+esc(rep.nick||'—')+
      '</td><td class="dt">'+esc(shortdt(rep.reg_time))+'</td><td class="dt">'+esc(shortdt(g.last))+
      '</td><td class="num">'+n+'</td><td class="num">'+g.sessions+'</td><td class="num">'+(rep.exp==null?'—':rep.exp)+
      '</td><td>'+(rep.uid!=null?'<button class="mini" onclick="openEdit(event,'+rep.uid+')">✎</button>':'')+'</td></tr>';
    if(open&&multi){
      g.accs.forEach(function(a){
        var ao=DATA.online[a.nick];
        var adot='<span class="dot'+(ao?' on':'')+'"></span>';
        var ast=ao?('<span class="b '+ao.state+'">'+esc(ao.state)+'</span>'):'<span class="muted">offline</span>';
        html+='<tr class="sub" style="'+bd+'"><td>'+adot+ast+'</td><td></td><td class="ix">'+esc(a.user)+
          '</td><td>'+esc(a.nick||'—')+'</td><td class="dt">'+esc(shortdt(a.reg_time))+'</td><td class="dt">'+esc(shortdt(lt(a)))+
          '</td><td></td><td class="num">'+(a.logins||0)+'</td><td class="num">'+(a.exp==null?'—':a.exp)+
          '</td><td><button class="mini" onclick="openEdit(event,'+a.uid+')">✎</button></td></tr>';
      });
    }
  });
  document.getElementById('rows').innerHTML=html||'<tr><td colspan=10 class="muted">sin resultados</td></tr>';
  document.getElementById('count').textContent=groups.length+' IPs · '+DATA.accounts.length+' cuentas';
  var ths=document.querySelectorAll('th[data-k]');
  for(var i=0;i<ths.length;i++)ths[i].querySelector('.ar').textContent=(ths[i].getAttribute('data-k')===SK)?(SD>0?' ▲':' ▼'):'';
}
var EDIT_UID=null;
function openEdit(ev,uid){
  if(ev&&ev.stopPropagation)ev.stopPropagation();
  var a=DATA.accounts.filter(function(x){return x.uid===uid;})[0];
  if(!a)return;
  EDIT_UID=uid;
  document.getElementById('em_sub').textContent='uid '+uid+' · '+a.user+(a.nick?(' · '+a.nick):'');
  document.getElementById('em_nick').value=a.nick==null?'':a.nick;
  document.getElementById('em_exp').value=a.exp==null?0:a.exp;
  document.getElementById('em_coin').value=a.coin==null?0:a.coin;
  document.getElementById('em_err').textContent='';
  document.getElementById('editModal').style.display='flex';
}
function cerrarEdit(){document.getElementById('editModal').style.display='none';EDIT_UID=null;}
async function guardarEdit(){
  if(EDIT_UID==null)return;
  var er=document.getElementById('em_err');er.style.color='';er.textContent='guardando…';
  var body={key:KEY,uid:EDIT_UID,
    nickname:document.getElementById('em_nick').value,
    exp:parseInt(document.getElementById('em_exp').value,10),
    coin:parseInt(document.getElementById('em_coin').value,10)};
  try{
    var r=await fetch('/admin/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var d=await r.json();
    if(!r.ok){er.style.color='var(--error)';er.textContent=d.error||'error';return;}
    cerrarEdit();refresh();
  }catch(e){er.style.color='var(--error)';er.textContent='error de conexión';}
}
document.getElementById('editModal').addEventListener('click',function(e){if(e.target===this)cerrarEdit();});
if(KEY)refresh();
TIMER=setInterval(refresh,4000);
document.getElementById('pw').addEventListener('keydown',function(e){if(e.key==='Enter')entrar();});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "R2BeatPatch/1.0"

    def _ip(self):
        # Caddy manda la IP real del cliente en X-Forwarded-For.
        xff = self.headers.get("X-Forwarded-For", "")
        return xff.split(",")[0].strip() if xff else self.client_address[0]

    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bearer(self):
        h = self.headers.get("Authorization", "")
        return h[7:].strip() if h.startswith("Bearer ") else None

    def log_message(self, *a):
        pass  # silenciamos el log ruidoso por defecto

    # -------- Panel admin (read-only, password) --------
    def _qs_get(self, key):
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        for kv in q.split("&"):
            if kv.startswith(key + "="):
                from urllib.parse import unquote
                return unquote(kv[len(key) + 1:])
        return None

    def _panel_auth(self):
        """Auth del panel de LECTURA (/status, /accounts) con el MISMO anti-fuerza-bruta que
        el editor de escritura: compare_digest (timing-safe) + baneo por IP a los 8 intentos.
        Comparte la ventana "admin:<ip>" con /admin/update -> los intentos SUMAN entre rutas.

        ★ 2026-07-26 (auditoría): antes estas dos rutas comparaban con `!=` y **sin ningún
        límite de intentos**, mientras /admin/update sí estaba protegido. Y /accounts devuelve
        username + last_ip de TODOS los jugadores -> era un leak de datos personales a un
        password adivinable sin freno. Ver deploy/RECUPERACION.md y el informe de seguridad."""
        pw = CFG.get("status_password")
        if not pw:
            self._json(503, {"error": "panel deshabilitado (sin status_password)"}); return False
        ip = self._ip()
        left = is_banned("admin:" + ip)
        if left:
            self._json(429, {"error": "demasiados intentos, espera", "retry_sec": left}); return False
        intento = str(self._qs_get("key") or "")
        if not hmac.compare_digest(intento, str(pw)):
            # ★ 2026-07-26: se cuentan CLAVES DISTINTAS, no peticiones. El panel se refresca
            #   solo cada 4 s: con una clave mal escrita mandaba 2 intentos cada 4 s y baneaba
            #   al admin en 14 s (una pestana vieja abierta bastaba para re-banearlo). Repetir
            #   la MISMA clave mala no acerca a nadie a adivinar, asi que no suma. Adivinar
            #   exige claves DISTINTAS y esas siguen contando igual -> proteccion intacta.
            huella = hashlib.sha256(intento.encode("utf-8", "replace")).hexdigest()[:16]
            with LOCK:
                st = ip_window("admin:" + ip)
                vistas = st.setdefault("keys", set())
                if huella not in vistas:
                    if len(vistas) < 64:        # tope: no crecer sin limite con un atacante real
                        vistas.add(huella)
                    st["auth"] += 1
                    if st["auth"] >= 8:
                        ban("admin:" + ip, "fuerza bruta en el panel")
            log(f"PANEL auth FALLIDA ip={ip} ruta={self.path.split('?')[0]}")
            self._json(401, {"error": "password incorrecta"}); return False
        return True

    def _serve_status(self):
        if not self._panel_auth():
            return
        path = CFG.get("status_file") or "/opt/r2beat/data/status.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # marca si el snapshot está viejo (server caído): >15s sin actualizar
            data["stale"] = (time.time() - data.get("ts", 0)) > 15
        except Exception:
            data = {"online": 0, "counts": {}, "users": [], "stale": True, "error": "sin datos (server apagado?)"}
        return self._json(200, data)

    def _serve_online(self):
        """PUBLICO y sin password: SOLO la cantidad de conectados, para el contador de la web.
        A proposito NO reusa /status: ese devuelve nicks, uids y estados (datos personales) y
        por eso pide contrasena. Aca sale un unico numero. Cache corto: lo absorbe Cloudflare."""
        path = CFG.get("status_file") or "/opt/r2beat/data/status.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            viejo = (time.time() - d.get("ts", 0)) > 60      # game caido o sin escribir
            n = 0 if viejo else int(d.get("online", 0) or 0)
        except Exception:
            n, viejo = 0, True
        body = json.dumps({"online": n, "stale": viejo}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=15")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_accounts(self):
        # READ-ONLY: deriva gestion (registros/IP/sesiones) de la MISMA clean.db.
        if not self._panel_auth():
            return
        try:
            c = sqlite3.connect(CFG["clean_db"])
            c.row_factory = sqlite3.Row
            users = c.execute(
                "SELECT uid, username, reg_time, last_ip, last_time FROM users").fetchall()
            chars = {r["uid"]: r for r in c.execute(
                "SELECT uid, nickname, exp, coin FROM chars")}
            sess = {}
            for r in c.execute("SELECT uid, ip, created_at FROM sessions"):
                d = sess.setdefault(r["uid"], {"n": 0, "ips": set(), "first": None, "last": None})
                d["n"] += 1
                if r["ip"]:
                    d["ips"].add(r["ip"])
                ca = r["created_at"]
                if ca:
                    d["first"] = ca if d["first"] is None else min(d["first"], ca)
                    d["last"] = ca if d["last"] is None else max(d["last"], ca)
            c.close()
        except Exception as e:
            return self._json(500, {"error": "DB error: %s" % e})

        # cuantas cuentas comparten cada last_ip (para marcar multi-cuenta)
        ip_accounts = {}
        for u in users:
            if u["last_ip"]:
                ip_accounts.setdefault(u["last_ip"], []).append(u["username"])

        accounts = []
        for u in users:
            uid = u["uid"]
            ch = chars.get(uid)
            s = sess.get(uid, {})
            ip = u["last_ip"]
            accounts.append({
                "uid": uid, "user": u["username"],
                "nick": ch["nickname"] if ch else None,
                "exp": ch["exp"] if ch else None,
                "coin": ch["coin"] if ch else None,
                "reg_time": u["reg_time"], "last_time": u["last_time"], "last_ip": ip,
                "logins": s.get("n", 0), "ips": len(s.get("ips", ())),
                "first_seen": s.get("first"), "last_seen": s.get("last"),
                "shared": bool(ip and len(ip_accounts.get(ip, [])) > 1),
            })
        accounts.sort(key=lambda a: (a["reg_time"] or ""), reverse=True)

        # agrupado por IP (todas las IP vistas en sessions, mas el last_ip)
        ip_map = {}
        for u in users:
            uid = u["uid"]
            ips = set(sess.get(uid, {}).get("ips", ()))
            if u["last_ip"]:
                ips.add(u["last_ip"])
            s = sess.get(uid, {})
            for ip in ips:
                g = ip_map.setdefault(ip, {"ip": ip, "users": set(), "first": None, "last": None})
                g["users"].add(u["username"])
                if s.get("first"):
                    g["first"] = s["first"] if g["first"] is None else min(g["first"], s["first"])
                if s.get("last"):
                    g["last"] = s["last"] if g["last"] is None else max(g["last"], s["last"])
        ips = [{"ip": g["ip"], "accounts": len(g["users"]), "users": sorted(g["users"]),
                "first": g["first"], "last": g["last"], "multi": len(g["users"]) > 1}
               for g in ip_map.values()]
        ips.sort(key=lambda x: (x["accounts"], x["last"] or ""), reverse=True)

        return self._json(200, {
            "accounts": accounts, "ips": ips,
            "totals": {"accounts": len(accounts), "chars": len(chars),
                       "ips": len(ips), "multi_ips": sum(1 for x in ips if x["multi"])},
        })

    def _serve_admin_html(self):
        body = ADMIN_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # -------- Editor admin (POST /admin/update, password en el body) --------
    def _admin_auth(self, body):
        pw = CFG.get("status_password")
        if not pw:
            self._json(503, {"error": "editor deshabilitado (sin status_password)"}); return False
        ip = self._ip()
        left = is_banned("admin:" + ip)
        if left:
            self._json(429, {"error": "demasiados intentos, espera", "retry_sec": left}); return False
        if not hmac.compare_digest(str(body.get("key", "")), str(pw)):
            with LOCK:
                st = ip_window("admin:" + ip)
                st["auth"] += 1
                if st["auth"] >= 8:
                    ban("admin:" + ip, "fuerza bruta en /admin")
            self._json(401, {"error": "password incorrecta"}); return False
        return True

    def _admin_update(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json(400, {"error": "json invalido"})
        if not self._admin_auth(body):
            return
        try:
            uid = int(body.get("uid"))
        except Exception:
            return self._json(400, {"error": "uid invalido"})
        res, err = admin_update(uid, body.get("nickname", None), body.get("exp", None), body.get("coin", None))
        if err:
            return self._json(400, {"error": err})
        log(f"ADMIN update uid={uid} {res['changes']} ip={self._ip()}")
        return self._json(200, res)

    # -------- POST: /auth  +  /admin/update --------
    def do_POST(self):
        if self.path == "/admin/update":
            return self._admin_update()
        if self.path.split("?")[0].startswith("/subidas/"):      # ★ 16-nov: los amigos suben al server de prueba
            return self._subidas()
        if self.path != "/auth":
            return self._json(404, {"error": "not found"})
        ip = self._ip()
        left = is_banned(ip)
        if left:
            return self._json(429, {"error": "baneado temporalmente", "retry_sec": left})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json(400, {"error": "json invalido"})

        with LOCK:
            st = ip_window(ip)
            st["auth"] += 1
            if st["auth"] > CFG["per_ip_auth_per_hour"]:
                ban(ip, "demasiados intentos de login")
                return self._json(429, {"error": "demasiados intentos, intenta mas tarde"})

        if modo_pase():  # pase:
            if not body.get("pase") or body.get("user") or body.get("username") or body.get("pass_sha256_upper") or body.get("password"):  # pase:
                return self._json(401, {"error": "pase invalido o vencido"})  # pase:
            acc = verify_pase(body.get("pase", ""))  # pase:
            if not acc:  # pase:
                return self._json(401, {"error": "pase invalido o vencido"})  # pase:
        else:  # pase:
            if "pase" in body:  # pase:
                return self._json(401, {"error": "usuario o contrasena incorrectos"})  # pase:
            acc = verify_account(body.get("user", ""), body.get("pass_sha256_upper", ""))
            if not acc:
                return self._json(401, {"error": "usuario o contrasena incorrectos"})

        token = secrets.token_hex(16)
        with LOCK:
            TOKENS[token] = {
                "uid": acc["uid"], "user": acc["user"], "nombre": acc.get("nombre") or "",
                "exp": time.time() + CFG["token_ttl_sec"],
                "used": 0, "ip": ip,
            }
        log(f"AUTH ok user={acc['user']} ip={ip}")
        if modo_pase():  # pase:
            return self._json(200, {  # pase:
                "ok": True,  # pase:
                "token": token,  # pase:
                "session_token": token,  # pase:
                "ttl": CFG["token_ttl_sec"],  # pase:
                "expires_in": CFG["token_ttl_sec"],  # pase:
                "quota_mb": CFG["quota_mb_per_token"],  # pase:
                "max_files": CFG.get("max_files", 0),  # pase:
                "user": acc["user"],  # pase:
                "uid": acc["uid"],  # pase:
            })  # pase:
        return self._json(200, {
            "token": token,
            "ttl": CFG["token_ttl_sec"],
            "quota_mb": CFG["quota_mb_per_token"],
            "user": acc["user"],
        })

    # -------- GET --------
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            return self._json(200, {"ok": True, "version": CFG.get("current")})

        # -------- Panel admin READ-ONLY (online/estado), protegido con password --------
        if self.path == "/admin":
            return self._serve_admin_html()
        if self.path.split("?")[0] == "/online":
            return self._serve_online()
        if self.path.split("?")[0] == "/status":
            return self._serve_status()
        if self.path.split("?")[0] == "/accounts":
            return self._serve_accounts()

        # Auto-update del PROPIO launcher (publico: no necesita login, pero cuenta cuota por IP).
        if self.path == "/launcher/meta":
            return self._launcher_meta()
        if self.path == "/launcher/bin":
            return self._launcher_bin()

        if self.path.split("?")[0] == "/manifest":       # ★ 16-nov: ?canal=prueba = la lista del server de prueba
            return self._serve_manifest()

        if self.path.startswith("/files/"):
            return self._serve_file()

        if self.path.split("?")[0].startswith("/offline/"):     # ★ 16-nov: el MINI SERVER del modo offline
            return self._serve_offline()

        return self._json(404, {"error": "not found"})

    # ★ 16-nov ─ EL MINI SERVER DEL MODO OFFLINE del launcher (`offline.rs`: `{patch}/offline/manifest.json` y
    #   `…/offline/archivos/<ruta>`). PÚBLICO y de sólo lectura (se baja antes o sin la cuenta), desde
    #   `<releases>/_offline/` (o `offline_dir`). ⛔ Lo que se pone ahí lo ve cualquiera: el paquete se arma con el
    #   código BARRIDO como el del repo público (`_trabajo/offline/limpiar_servidor.py`), nunca el `servidor/` privado.
    def _serve_offline(self):
        base = os.path.realpath(CFG.get("offline_dir") or os.path.join(CFG.get("releases_dir") or "", "_offline"))
        rel = urllib.parse.unquote(self.path.split("?")[0][len("/offline/"):])
        if not rel or "\\" in rel or "\0" in rel:
            return self._json(404, {"error": "not found"})
        full = os.path.realpath(os.path.join(base, *rel.split("/")))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            return self._json(404, {"error": "not found"})
        size = os.path.getsize(full)
        self.send_response(200)
        self.send_header("Content-Type", "application/json" if full.endswith(".json") else "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-cache" if rel == "manifest.json" else "public, max-age=3600")
        self.end_headers()
        with open(full, "rb") as f:
            while True:
                b = f.read(1 << 16)
                if not b:
                    break
                self.wfile.write(b)

    # ★ 16-nov ─ SUBIR ARCHIVOS AL SERVER DE PRUEBA (subidas.py, TOPOLOGIA §36) ─────────────────────────────────
    #   POST /subidas/archivo   (X-Ruta: ruta dentro del cliente, url-encoded) cuerpo = el archivo → al borrador
    #   POST /subidas/enviar    {nota, pase?}  → propuesta. Con el pase de AUTORIZADO (aud r2beat2013-subir) se aplica.
    #   POST /subidas/lista     {pase?}        → mi borrador + mis envíos (+ todas las pendientes si soy autorizado)
    #   POST /subidas/revisar   {pase, id, accion: aprobar|rechazar}   (sólo autorizados)
    #   POST /subidas/descartar                → borra mi borrador
    #   ★ §37 POST /subidas/estados {pase?}   → el historial de la lista de prueba (la vigente + 5), para todos
    #   ★ §37 POST /subidas/volver  {pase, release}   → deja vigente un estado del historial (sólo autorizados)
    #   ⛔ El NOMBRE de quien sube sale del pase (token), nunca del cuerpo: antes cualquiera podía firmar como otro.
    def _subidas(self):
        subidas()                                                 # (deja `subidas` importable)
        import subidas as S
        r = self._check_token()
        if not r:
            return
        _tok, t = r
        uid = int(t.get("uid") or 0)
        quien = S.nombre_limpio(t.get("nombre"), uid)       # (el login es privado: si el pase no trae nombre, el uid)
        accion = self.path.split("?")[0][len("/subidas/"):]
        try:
            if accion == "archivo":
                ruta = urllib.parse.unquote(self.headers.get("X-Ruta") or "")
                largo = int(self.headers.get("Content-Length") or 0)
                return self._json(200, subidas().recibir(uid, ruta, self.rfile, largo))
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}") if n <= 65536 else {}
            except Exception:
                return self._json(400, {"error": "json invalido"})
            pase = body.get("pase") or ""
            autorizado = bool(pase) and (verify_pase(pase, aud=AUD_SUBIR) or {}).get("uid") == uid
            if pase and not autorizado:
                return self._json(403, {"error": "El pase no autoriza la subida directa."})
            if autorizado:
                subidas().marcar_autorizado(uid, quien)          # ★ un autorizado queda invitado solo
            if accion == "invitacion":                           # ★ 16-nov: cualquiera SOLICITA invitación para subir
                inv = subidas().solicitar_invitacion(uid, quien, body.get("nota"))
                log(f"SUBIDA invitación solicitada por {uid}")
                return self._json(200, inv)
            if accion == "invitar":                              # ★ y un autorizado la aprueba / rechaza / quita
                if not autorizado:
                    return self._json(403, {"error": "Solo las cuentas autorizadas pueden gestionar invitaciones."})
                inv = subidas().revisar_invitacion(int(body.get("uid") or 0), str(body.get("accion") or ""), uid)
                log(f"SUBIDA invitación de {inv['uid']}: {inv['estado']} por {uid}")
                return self._json(200, inv)
            if accion == "enviar":
                p = subidas().enviar(uid, quien, body.get("nota"), autorizado)
                log(f"SUBIDA #{p['id']} de {uid} ({len(p['archivos'])} archivos, {len(p.get('ejecutables') or [])} "
                    f"sensibles) -> {p['estado']} {p.get('release') or ''}")
                return self._json(200, p)
            if accion == "lista":
                return self._json(200, {"uid": uid, "autorizado": autorizado, "borrador": subidas().borrador(uid),
                                        "propuestas": subidas().lista(uid, autorizado),
                                        "release_prueba": subidas().release_prueba(),
                                        "estados": subidas().estados(), "apagado": subidas().apagado(),
                                        "invitado": subidas().invitado(uid), "invitacion": subidas().invitacion(uid),
                                        "invitaciones": subidas().invitaciones() if autorizado else [],
                                        "dos_llaves": S.DOS_LLAVES, "pendientes_total": subidas().pendientes(),
                                        "limites": {"envio_mb": S.TAM_MAX_BORRADOR // 2**20,
                                                    "pendientes_total": S.PENDIENTES_MAX_TOTAL,
                                                    "pendientes_cuenta": S.PENDIENTES_MAX_POR_CUENTA}})
            if accion in ("cancelar", "editar"):        # ★ 16-nov: SÓLO el envío propio (el de otro, 403)
                id_ = int(body.get("id") or 0)
                p = subidas().cancelar(id_, uid) if accion == "cancelar" else subidas().editar(id_, uid, body.get("nota"))
                log(f"SUBIDA #{p['id']} {accion} por su dueño {uid}")
                return self._json(200, p)
            if accion == "estados":
                return self._json(200, {"estados": subidas().estados(), "autorizado": autorizado})
            if accion == "revisar":
                if not autorizado:
                    return self._json(403, {"error": "Solo las cuentas autorizadas pueden aprobar o rechazar envíos."})
                p = subidas().revisar(int(body.get("id") or 0), str(body.get("accion") or ""), uid, quien=quien)
                log(f"SUBIDA #{p['id']} {p['estado']} por {uid} {p.get('release') or ''}")
                return self._json(200, p)
            if accion == "volver":
                if not autorizado:
                    return self._json(403, {"error": "Solo las cuentas autorizadas pueden restaurar versiones."})
                v = subidas().volver(str(body.get("release") or ""), uid, quien=quien)
                log(f"SUBIDA volver: prueba {v['antes']} -> {v['release']} por {uid}")
                return self._json(200, v)
            if accion == "descartar":
                subidas().descartar(uid)
                return self._json(200, {"ok": True})
            return self._json(404, {"error": "not found"})
        except S.Error as e:
            if accion == "archivo":
                self.close_connection = True                     # el cuerpo puede no haberse leído entero
            return self._json(e.codigo, {"error": e.motivo})

    def _check_token(self):
        tok = self._bearer()
        if not tok:
            self._json(401, {"error": "falta token"}); return None
        with LOCK:
            t = TOKENS.get(tok)
            if not t or t["exp"] < time.time():
                TOKENS.pop(tok, None)
                self._json(401, {"error": "token vencido, volve a entrar"}); return None
        left = is_banned(tok, t["ip"])
        if left:
            self._json(429, {"error": "baneado temporalmente", "retry_sec": left}); return None
        return tok, t

    def _serve_manifest(self):
        r = self._check_token()
        if not r:
            return
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        canal = (q.get("canal") or [""])[0]
        envio = (q.get("envio") or [""])[0]
        if canal == "prueba" and envio.isdigit() and int(envio) > 0:
            # ★ 16-nov (Benja): PROBAR un envío pendiente = la lista de prueba + sus archivos, aparte (vista previa)
            import subidas as S
            try:
                rel = subidas().release_de_envio(int(envio), int(r[1].get("uid") or 0))
                man = manifest_de_release(rel, "envio")
                if man:
                    return self._json(200, dict(man, envio=int(envio)))
            except S.Error as e:
                man = current_manifest("prueba")
                if man:   # ya no se puede probar: la lista de prueba normal, con el motivo (el launcher lo avisa)
                    return self._json(200, dict(man, envio=None, envio_no_disponible=e.motivo))
        man = current_manifest(canal)
        if not man:
            return self._json(503, {"error": "no hay release publicado"})
        return self._json(200, man)

    def _serve_file(self):
        r = self._check_token()
        if not r:
            return
        tok, t = r
        # /files/<release>/<path...>
        parts = self.path[len("/files/"):].split("/", 1)
        if len(parts) != 2:
            return self._json(400, {"error": "ruta invalida"})
        release, rel_path = parts[0], parts[1]
        full = safe_join(release, rel_path)
        if not full or not os.path.isfile(full):
            return self._json(404, {"error": "archivo no existe"})

        size = os.path.getsize(full)
        ip = t["ip"]
        # Cuota por token y por IP (chequeo previo)
        with LOCK:
            st = ip_window(ip)
            if t["used"] + size > CFG["quota_mb_per_token"] * MB:
                ban(tok, "token excedio su cuota de descarga")
                return self._json(429, {"error": "cuota de descarga excedida (baneo temporal)"})
            if st["bytes"] + size > CFG["per_ip_quota_mb_per_hour"] * MB:
                ban(ip, "IP excedio su cuota horaria")
                return self._json(429, {"error": "cuota por IP excedida (baneo temporal)"})

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        sent = 0
        try:
            with open(full, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    sent += len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with LOCK:
                t["used"] += sent
                ip_window(ip)["bytes"] += sent

    # -------- auto-update del launcher --------
    def _launcher_meta(self):
        ip = self._ip()
        left = is_banned(ip)
        if left:
            return self._json(429, {"error": "baneado temporalmente", "retry_sec": left})
        meta = launcher_meta()
        if not meta:
            return self._json(503, {"error": "no hay launcher publicado"})
        return self._json(200, meta)

    def _launcher_bin(self):
        ip = self._ip()
        left = is_banned(ip)
        if left:
            return self._json(429, {"error": "baneado temporalmente", "retry_sec": left})
        path = CFG.get("launcher_bin", "")
        if not path or not os.path.isfile(path):
            return self._json(404, {"error": "launcher no disponible"})
        size = os.path.getsize(path)
        with LOCK:
            st = ip_window(ip)
            if st["bytes"] + size > CFG["per_ip_quota_mb_per_hour"] * MB:
                ban(ip, "IP excedio su cuota horaria (launcher)")
                return self._json(429, {"error": "cuota por IP excedida (baneo temporal)"})
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        sent = 0
        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    sent += len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with LOCK:
                ip_window(ip)["bytes"] += sent


# ----------------------------------------------------------------------------
def cleaner():
    while True:
        time.sleep(120)
        now = time.time()
        with LOCK:
            for k in [k for k, v in TOKENS.items() if v["exp"] < now]:
                TOKENS.pop(k, None)
            for k in [k for k, v in BANS.items() if v < now]:
                BANS.pop(k, None)
            for k in [k for k, v in USED_PASE_JTIS.items() if v < now]:  # pase:
                USED_PASE_JTIS.pop(k, None)  # pase:


def main():
    if len(sys.argv) < 2:
        print("uso: python3 patchserver.py <config.json>"); sys.exit(1)
    load_cfg(sys.argv[1])
    if not modo_pase() and not os.path.isfile(CFG["clean_db"]):  # pase:
        log("AVISO: clean_db no existe todavia:", CFG["clean_db"])
    threading.Thread(target=cleaner, daemon=True).start()
    srv = ThreadingHTTPServer((CFG["listen"], CFG["port"]), Handler)
    log(f"patchserver escuchando en http://{CFG['listen']}:{CFG['port']}  release={CFG.get('current')}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
