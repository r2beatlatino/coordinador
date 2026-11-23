# -*- coding: utf-8 -*-
"""Páginas: portero, rutas y permisos reales; sin sockets ni red, fetch de NOVEDADES inyectado.

Cada regla tiene su control al revés (⟲): publicación vs borrador, límites exactos
vs exceso, base vigente vs vieja, moderador con EDA vs sin EDA, archivo sano vs roto.
"""
import contextlib
import copy
import io
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
fallos = []
cuenta = 0


def ok(cond, que):
    global cuenta
    cuenta += 1
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


def version(n="2026.11.23", fecha="2026-11-23"):
    return {"version": n, "fecha": fecha, "resumen": "Qué cambió", "corregidos": ["Corrección"],
            "mejoras": ["Mejora"], "avisos": ["Aviso"]}


def pagina():
    return {"banner": {"sello": "BETA CERRADA", "titulo": "Ñ2-EDA NOVIEMBRE"},
            "version_actual": "2026.11.23", "versiones": [version()],
            "cajas": [{"titulo": "Comunidad", "texto": "Novedades del juego"}]}


with tempfile.TemporaryDirectory(prefix="paginas_") as tmp:
    os.environ.update({
        "R2_CUENTAS_DUENA": "1", "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
        "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"), "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
        "R2_BASE": os.path.join(tmp, "no_existe.db"), "R2_ADMIN_ARCHIVO": os.path.join(tmp, "admin.txt"),
        "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "moderadores.txt"), "R2_PORTERO_PUERTO": "0",
    })
    for k in ("R2_JUEGOS_CATALOGO", "R2_PANEL_CONTENIDO", "R2_DISCORD_EVENTOS_WEBHOOK", "R2_UID_NUEVAS_DESDE"):
        os.environ.pop(k, None)
    from servidor import portero as P
    from servidor import contenido as CT
    from servidor import coordinador as CO
    from servidor import paginas as PG

    with contextlib.redirect_stdout(io.StringIO()):
        uid = [P.registrar(n, clave_txt="clave-de-prueba", ip=f"10.7.0.{i}")[1]["uid"]
               for i, n in enumerate(("adminprueba", "modeda", "modotro", "modviejo", "sinrol"))]
    ADMIN, EDA, OTRO, VIEJO, JUGADOR = uid
    Path(os.environ["R2_ADMIN_ARCHIVO"]).write_text(f"{ADMIN}\n", encoding="utf-8")
    Path(os.environ["R2_MODERADOR_ARCHIVO"]).write_text(f"{EDA} eda\n{OTRO} gunbound\n{VIEJO}\n", encoding="utf-8")
    sesiones = {u: P.abrir_sesion_admin(u) for u in uid[:-1]}
    ruta = Path(tmp) / "config" / "paginas.json"

    class Pedido(P._Manejador):
        """Ejecuta do_GET/do_POST de verdad, reemplazando sólo el transporte HTTP."""
        def __init__(self, path, cuerpo, viewer, x_r2):
            self.path = path
            raw = json.dumps(cuerpo or {}, ensure_ascii=False).encode("utf-8")
            self.rfile = io.BytesIO(raw)
            self.headers = {"Content-Length": str(len(raw))}
            if x_r2:
                self.headers["X-R2"] = "1"
            if viewer in sesiones:
                self.headers["Cookie"] = "coordinador=" + sesiones[viewer]

        def _ip(self):
            return "127.0.0.1"

        def _mandar(self, cod, datos, **kwargs):
            self.respuesta = cod, copy.deepcopy(datos)
            return self.respuesta

    def pedir(metodo="GET", path="/coordinador/api/pagina?juego=eda", cuerpo=None, viewer=ADMIN, x_r2=True):
        h = Pedido(path, cuerpo, viewer, x_r2)
        with contextlib.redirect_stdout(io.StringIO()):
            getattr(h, "do_" + metodo)()
        return h.respuesta

    def estado():
        return pedir()[1]

    def guardar(v, base=None, viewer=ADMIN, juego="eda"):
        return pedir("POST", "/coordinador/api/pagina", {"juego": juego, "base": base or estado()["base"], "publicada": v}, viewer)

    def launcher():
        return pedir(path="/lanzamientos", viewer=None)[1]["paginas"]

    try:
        print("1 · publicación pública y rutas del panel")
        cod, e = pedir()
        ok(cod == 200 and e["publicada"] is None and e["borradores"] == [] and e["base"] and e["puede_editar"],
           "GET pagina sin archivo: estado vacío editable, con base")
        ok(launcher() == {}, "⟲ GET /lanzamientos sin archivo: paginas = {} (ni siquiera eda)")
        with patch.object(P, "_log") as log:
            PG.publicadas(P)
            ok(log.called, "⟲ el archivo ausente se anota con _log")
        ok(pedir(viewer=None)[0] == 401, "⟲ sin sesión del panel: 401")
        ok(pedir("POST", "/coordinador/api/pagina", {}, x_r2=False)[0] == 403, "⟲ POST sin X-R2: 403")
        cod, e = guardar(pagina())
        publica = launcher()
        contrato = {"actualizada", "banner", "version_actual", "versiones", "cajas", "idiomas"}
        ok(cod == 200 and set(publica) == {"eda"} and set(publica["eda"]) == contrato,
           "guardar publica sólo el contrato en paginas.eda")
        ok(publica["eda"]["idiomas"] == PG.IDIOMAS_EDA, "EDA sin idiomas explícitos recibe es + en")
        ok(pedir(path="/cuentas/lanzamientos")[1]["paginas"] == publica
           and pedir(path="/cuentas/coordinador/api/pagina?juego=eda")[0] == 200,
           "también funcionan los prefijos /cuentas del portero")
        ok("base" not in publica["eda"] and "borradores" not in publica["eda"], "⟲ ni base ni borradores viajan al launcher")
        guardado = json.loads(ruta.read_text(encoding="utf-8"))["eda"]
        ok(guardado["base"] == e["base"], "base persistida coincide con la respuesta")

        print("2 · permisos por juego")
        anterior = ruta.read_bytes()
        ok(guardar(pagina(), viewer=OTRO)[0] == 403 and ruta.read_bytes() == anterior,
           "⟲ moderador SIN EDA: 403 y no edita")
        ok(pedir(viewer=OTRO)[0] == 404, "⟲ tampoco puede leer EDA")
        ok(pedir(viewer=VIEJO)[1]["puede_editar"] is False and guardar(pagina(), viewer=VIEJO)[0] == 403,
           "⟲ moderador de formato viejo puede mirar, pero no editar")
        ok(guardar(pagina(), viewer=EDA)[0] == 200, "moderador CON EDA: sí edita (200)")
        ok(guardar(pagina(), juego="inventado")[0] == 404, "⟲ ADMIN tampoco crea juegos fuera del catálogo")
        for acc in ("importar", "publicar"):
            ok(pedir("POST", "/coordinador/api/pagina/" + acc, {"juego": "eda"}, OTRO)[0] == 403,
               f"⟲ sin EDA tampoco puede {acc} (403)")
        cod, c = CT.leer(CO, P, ADMIN, "eda", "live", 0)
        ok(cod == 200 and c["pagina_local"], "EDA PROD sin fuente ofrece la pestaña Página")
        ok(not CT.leer(CO, P, ADMIN, "eda", "test", 0)[1]["pagina_local"], "⟲ TEST no publica la página de PROD")
        with patch.object(CT, "fuentes", return_value={"eda": "https://contenido.prueba"}), patch.object(CT, "_http", return_value=(200, {})):
            ok(not CT.leer(CO, P, ADMIN, "eda", "live", 0)[1]["pagina_local"], "⟲ una fuente propia mantiene su editor de contenido")

        print("3 · límites exactos y controles al revés")
        v = pagina()
        v["banner"] = {"sello": "s" * 24, "titulo": "t" * 48}
        v["versiones"] = [dict(version(f"2026.11.{i:02}", f"2026-11-{i:02}"), resumen="r" * 280,
                                corregidos=["c" * 160] * 8, mejoras=["m" * 160] * 8, avisos=["a" * 160] * 8)
                          for i in range(14, 24)]
        v["cajas"] = [{"titulo": "t" * 40, "texto": "x" * 200}] * 4
        v["idiomas"] = [{"id": x, "nombre": "n" * 24} for x in ("es", "en", "fr", "pt", "de", "it", "ja", "abcdefgh")]
        ok(guardar(v)[0] == 200 and launcher()["eda"]["versiones"][0]["version"] == "2026.11.23",
           "todos los máximos exactos se aceptan; historial más nuevo primero")
        ok(pedir("POST", "/coordinador/api/contenido", {"texto": "x" * 5000})[0] == 413,
           "⟲ otros POST conservan su límite de 4 KiB")
        ok(pedir("POST", "/coordinador/api/pagina", {"texto": "x" * (512 << 10)})[0] == 413,
           "⟲ guardar página también rechaza cuerpos mayores a 512 KiB")

        def exceso(nombre, cambiar):
            mala = copy.deepcopy(v)
            cambiar(mala)
            antes = ruta.read_bytes()
            cod, _ = guardar(mala)
            ok(cod == 400 and ruta.read_bytes() == antes, f"⟲ {nombre}: 400 y archivo intacto")

        for campo, maximo in (("sello", 24), ("titulo", 48)):
            exceso(f"banner {campo} > {maximo}", lambda p, k=campo, m=maximo: p["banner"].update({k: "x" * (m + 1)}))
        exceso("resumen > 280", lambda p: p["versiones"][0].update(resumen="x" * 281))
        for k in ("corregidos", "mejoras", "avisos"):
            exceso(k + " ítem > 160", lambda p, k=k: p["versiones"][0].update({k: ["x" * 161]}))
            exceso(k + " > 8 ítems", lambda p, k=k: p["versiones"][0].update({k: ["x"] * 9}))
        exceso("versiones > 10", lambda p: p["versiones"].append(version("otra")))
        exceso("cajas > 4", lambda p: p["cajas"].append({"titulo": "", "texto": ""}))
        exceso("caja título > 40", lambda p: p["cajas"][0].update(titulo="x" * 41))
        exceso("caja texto > 200", lambda p: p["cajas"][0].update(texto="x" * 201))
        exceso("idiomas > 8", lambda p: p["idiomas"].append({"id": "zz", "nombre": "Z"}))
        exceso("idioma nombre > 24", lambda p: p["idiomas"][0].update(nombre="x" * 25))
        for id_malo in ("e", "abcdefghi", "ES", "es-BO", "es\n", 123):
            exceso(f"idioma id inválido {id_malo!r}", lambda p, x=id_malo: p["idiomas"][0].update(id=x))
        exceso("idiomas repetidos", lambda p: p["idiomas"].__setitem__(1, p["idiomas"][0]))
        exceso("fecha imposible", lambda p: p["versiones"][0].update(fecha="2026-02-30"))
        exceso("versión actual fuera del historial", lambda p: p.update(version_actual="inexistente"))
        for texto in ("<b>HTML</b>", "a>b", "a\x00b", "a\nb", "a\tb", "a\x7fb", "a\x85b"):
            exceso(f"HTML/control {texto!r}", lambda p, x=texto: p["banner"].update(sello=x))
        exceso("HTML en ítem", lambda p: p["versiones"][0].update(avisos=["<script>"]))
        exceso("HTML en caja", lambda p: p["cajas"][0].update(texto="<img>"))
        exceso("HTML en idioma", lambda p: p["idiomas"][0].update(nombre="<b>"))

        print("4 · importar sin publicar, sin duplicados y con errores informados")
        ok(guardar(pagina())[0] == 200, "restablece una página pequeña")
        fuente = {"versiones": [version(), version("2026.11.24", "2026-11-24"),
                   dict(version("2026.11.25", "2026-11-25"), borrador=True),
                   dict(version("mala"), resumen="<html>"), version("2026.11.24", "2026-11-24"),
                   dict(version("2026.11.26", "2026-11-26"), borrador=False), "inválida"]}
        urls = []

        def fetch(url):
            urls.append(url)
            return copy.deepcopy(fuente)

        def importar(juego="eda"):
            with patch.object(PG, "_fetch", side_effect=fetch):
                return pedir("POST", "/coordinador/api/pagina/importar", {"juego": juego}, EDA if juego == "eda" else ADMIN)

        antes = launcher()
        cod, e = importar()
        ok(cod == 200 and e["importadas"] == 2 and len(e["invalidas"]) == 2
           and [x["version"] for x in e["borradores"]] == ["2026.11.24", "2026.11.26"],
           "sólo suma válidas no-borrador; informa inválidas y deduplica dentro del archivo")
        ok(urls == ["https://raw.githubusercontent.com/r2beatlatino/EDA/main/NOVEDADES.json"], "usa novedades_url del catálogo")
        ok(launcher() == antes and all(x.get("importada") for x in e["borradores"]),
           "⟲ importar no publica nada; cada borrador lleva importada")
        ok(importar()[1]["importadas"] == 0, "⟲ repetir la importación no duplica borradores ni versiones publicadas")
        ok(importar("gunbound")[0] == 400, "⟲ sin novedades_url no inventa una fuente")
        with patch.object(PG, "_fetch", side_effect=OSError("fuera de línea")):
            ok(pedir("POST", "/coordinador/api/pagina/importar", {"juego": "eda"})[0] == 502,
               "⟲ error de descarga: 502, sin publicar")
        with patch.object(PG, "_fetch", return_value={"versiones": "rota"}):
            ok(pedir("POST", "/coordinador/api/pagina/importar", {"juego": "eda"})[0] == 502,
               "⟲ NOVEDADES mal formado: 502")
        with patch.object(PG.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = b'{"versiones": []}'
            PG._fetch(urls[0])
            ok(urlopen.call_args.kwargs["timeout"] == 8, "fetch real usa timeout de 8 segundos")

        print("5 · publicar, base contra pisadas y auditoría")
        e = estado()
        base_vieja = e["base"]
        cod, e = pedir("POST", "/coordinador/api/pagina/publicar", {"juego": "eda", "version": "2026.11.24", "base": e["base"]}, EDA)
        ok(cod == 200 and e["publicada"]["version_actual"] == "2026.11.24"
           and e["publicada"]["versiones"][0]["version"] == "2026.11.24"
           and [x["version"] for x in e["borradores"]] == ["2026.11.26"], "publicar mueve el borrador al frente y pone version_actual")
        antes = ruta.read_bytes()
        ok(guardar(pagina(), base_vieja)[0] == 409 and ruta.read_bytes() == antes, "⟲ guardar con base vieja: 409 y no pisa")
        ok(pedir("POST", "/coordinador/api/pagina/publicar", {"juego": "eda", "version": "2026.11.26", "base": base_vieja})[0] == 409
           and ruta.read_bytes() == antes, "⟲ publicar con base vieja: 409 y no mueve nada")
        ok(pedir("POST", "/coordinador/api/pagina/publicar", {"juego": "eda", "version": "ausente", "base": e["base"]})[0] == 404,
           "⟲ publicar borrador inexistente: 404")
        viejo = estado()["base"]
        fuente["versiones"].append(version("2026.11.27", "2026-11-27"))
        importar()
        ok(guardar(pagina(), viejo)[0] == 409, "⟲ importar también cambia base y protege los borradores")
        guardar(v)
        e = estado()
        cod, e = pedir("POST", "/coordinador/api/pagina/publicar", {"juego": "eda", "version": "2026.11.26", "base": e["base"]})
        ok(cod == 200 and len(e["publicada"]["versiones"]) == 10 and e["publicada"]["versiones"][0]["version"] == "2026.11.26",
           "publicar recorta el historial a 10")
        quitar = copy.deepcopy(e["publicada"])
        quitar["versiones"] = quitar["versiones"][1:]
        quitar["version_actual"] = quitar["versiones"][0]["version"]
        ok(guardar(quitar)[0] == 200 and launcher()["eda"]["version_actual"] == quitar["version_actual"],
           "quitar versión publicada conserva una versión actual válida")
        base = estado()["base"]
        def concurrente(titulo):
            try:
                return PG.cambiar(CO, P, ADMIN, {"juego": "eda", "base": base,
                    "publicada": dict(pagina(), banner={"sello": "BETA", "titulo": titulo})})
            finally:
                P.cerrar_conexiones()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(concurrente, ["Uno", "Dos"]))
        ok(sorted(c for c, _ in resultados) == [200, 409], "⟲ dos guardados simultáneos con igual base: sólo uno gana")
        acciones = [r[0] for r in P._propia().execute("SELECT detalle FROM auditoria WHERE accion = 'contenido · pagina' AND juego = 'eda'")]
        ok(all(x in acciones for x in ("guardar", "importar", "publicar")), "guardar, importar y publicar quedan en la auditoría del Coordinador")

        print("6 · sólo lo publicado; archivo roto y reemplazo atómico")
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        datos["wolfteam"] = {"publicada": None, "borradores": [dict(version("futura"), importada=PG._ahora())]}
        ruta.write_text(json.dumps(datos), encoding="utf-8")
        ok(set(launcher()) == {"eda"}, "⟲ un juego con sólo borradores no aparece en paginas")
        antes = ruta.read_bytes()
        with patch.object(PG.os, "replace", side_effect=OSError("fallo de disco")):
            ok(guardar(pagina())[0] == 500 and ruta.read_bytes() == antes, "⟲ falla replace: no deja una publicación parcial")
        ok(not list(ruta.parent.glob("paginas-*.nuevo")), "se limpia el temporal después del fallo")
        for roto in ("{", "[]", '{"eda": []}', '{"eda": {"publicada": {}}}', '{"eda": {"borradores": "rota"}}'):
            ruta.write_text(roto, encoding="utf-8")
            with patch.object(P, "_log") as log:
                cod, respuesta = pedir(path="/lanzamientos")
                ok(cod == 200 and respuesta["paginas"] == {} and log.called, f"⟲ archivo roto {roto!r}: paginas vacío y _log")
            ok(guardar(pagina(), base="vieja")[0] == 500 and ruta.read_text(encoding="utf-8") == roto,
               "⟲ un archivo roto tampoco se pisa desde el panel")
        ruta.unlink()
        fuente = [version("primera")]
        cod, e = importar()
        ok(cod == 200 and e["publicada"] is None and launcher() == {}, "importar desde cero (lista raíz) sigue sin publicar EDA")
        cod, e = pedir("POST", "/coordinador/api/pagina/publicar", {"juego": "eda", "version": "primera", "base": e["base"]})
        ok(cod == 200 and launcher()["eda"]["idiomas"] == PG.IDIOMAS_EDA, "primera publicación de un borrador también recibe es + en")
        sin_idiomas = pagina()
        sin_idiomas["idiomas"] = []
        ok(guardar(sin_idiomas)[0] == 200 and launcher()["eda"]["idiomas"] == [], "⟲ una lista de idiomas explícita se respeta")
    finally:
        P.cerrar_conexiones()

print(f"\n{'✘' if fallos else '✔'} probar_paginas: {cuenta} controles, {len(fallos)} fallas")
sys.exit(1 if fallos else 0)
