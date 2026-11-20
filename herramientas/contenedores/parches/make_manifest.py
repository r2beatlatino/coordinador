#!/usr/bin/env python3
"""
make_manifest.py — Genera el manifest.json de un release (lista de archivos + MD5 + tamano).

El launcher usa este manifest para saber que bajar: compara el MD5 de cada archivo
local contra el del manifest y baja SOLO los que difieren.

Uso:
  python3 make_manifest.py <carpeta_release> [version]

Ej:
  python3 make_manifest.py /opt/r2beat/releases/clientetest_2026-06-23 clientetest_2026-06-23

Escribe <carpeta_release>/manifest.json. El propio manifest.json y cualquier .bak/.tmp
se excluyen del listado.
"""
import sys, os, json, hashlib, time

EXCLUDE_NAMES = {"manifest.json",
                 # Config.ini = ajustes LOCALES (resolucion/modo ventana que el launcher escribe).
                 # Se EXCLUYE del manifest: el launcher lo siembra byte-identico si falta
                 # (ensure_config_ini), asi el updater nunca lo toca -> sin "pendiente" perpetuo
                 # ni reset de resolucion tras jugar.
                 "Config.ini"}
EXCLUDE_EXT = {".bak", ".tmp", ".log"}


def md5_file(path, buf=1024 * 1024):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    if len(sys.argv) < 2:
        print("uso: python3 make_manifest.py <carpeta_release> [version]")
        sys.exit(1)
    root = os.path.abspath(sys.argv[1])
    version = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(root.rstrip("/\\"))
    if not os.path.isdir(root):
        print("no es carpeta:", root); sys.exit(1)

    files, total = [], 0
    for dirpath, _, names in os.walk(root):
        for name in names:
            if name in EXCLUDE_NAMES or os.path.splitext(name)[1].lower() in EXCLUDE_EXT:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")  # rutas estilo URL
            sz = os.path.getsize(full)
            files.append({"path": rel, "md5": md5_file(full), "size": sz})
            total += sz

    files.sort(key=lambda x: x["path"])
    manifest = {
        "version": version,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "file_count": len(files),
        "total_size": total,
        "files": files,
    }
    # ★Escribir a temp + os.replace (NO open(out,"w")): los releases se crean con `cp -al`
    # (hardlinks), asi que open("w") escribiria A TRAVES del inode compartido y corromperia
    # el manifest del release anterior. os.replace() reemplaza el NOMBRE por un inode nuevo,
    # rompiendo el hardlink de forma segura (atomico).
    out = os.path.join(root, "manifest.json")
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    os.replace(tmp, out)
    print(f"OK  {len(files)} archivos  {total/1024/1024:.1f} MB  -> {out}")


if __name__ == "__main__":
    main()
