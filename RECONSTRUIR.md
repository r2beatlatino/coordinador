# Reconstruir Eñeños desde cero

> Para quien llega **sin ningún contexto** (una persona o una sesión nueva de Claude) con dos cosas:
> **estos repos** y **el respaldo cifrado de Eñeños** (`enenos_respaldo_<fecha>.age`) más su clave.
> ⚠ Esta guía se va completando a medida que el código del Coordinador se muda a este repo (ver «Estado»).

## 0 · Qué hay en cada lado

| dónde | qué | quién lo tiene |
|---|---|---|
| este repo | el Coordinador: cuentas, panel, catálogo, contenedores, dominio, mudanza | público, GitHub |
| los repos hijos (ver `juegos.json`) | el server de cada juego | público, GitHub |
| **el respaldo** | las bases (cuentas + cada juego), la configuración viva y **los secretos** | **sólo Eñeños** |
| los clientes de los juegos | instaladores y paks | aparte (no van en ninguno de los dos) |

**Los secretos van en el respaldo y no se pueden perder**: la llave que firma el pase del Eñeños-ID y la que firma
las listas de descarga. El launcher instalado de cada jugador confía en ellas; si se pierden hay que sacar un
launcher nuevo y que todos lo reinstalen.

## 1 · Generar el respaldo (Eñeños, a mano)

Todo está en `herramientas/respaldo/` (cómo es por dentro: el encabezado de `respaldo.py`).

**Una sola vez — la llave.** En la PC de Eñeños: `sh herramientas/respaldo/crear_llave.sh <carpeta>`. Deja la llave
PRIVADA cifrada con su contraseña (`enenos_respaldo_llave.age`: guardarla en dos lugares fuera de la PC) y la PÚBLICA
en `herramientas/respaldo/llave_publica.txt` (va al repo: sólo sirve para cifrar).

**Cada respaldo.** En el VPS, como root, parado en este repo:

```sh
sh herramientas/respaldo/generar_backup.sh        # → /opt/enenos/respaldos/enenos_respaldo_<fecha>.tar.gz.age
```

Qué guarda lo dice `herramientas/respaldo/respaldo_vps.json` (un juego nuevo = sus líneas ahí): las bases de cuentas y
de cada juego (copiadas EN VIVO con la API de SQLite y comprobadas), las llaves que firman los pases y el manifiesto de
EDA, los `.env`, Caddy con su certificado de origen y las tareas programadas. Los clientes de los juegos NO van.
Si falta algo obligatorio, NO se arma. El VPS sólo tiene la llave pública: puede cifrar, nunca leer.
Después: bajarlo (`scp`) a dos lugares y borrarlo del VPS.

**Abrirlo / comprobarlo** (en cualquier máquina con `age`, o con la imagen `enenos-respaldo`; pide la contraseña):

```sh
python herramientas/respaldo/respaldo.py ver   --archivo <respaldo>.age --llave enenos_respaldo_llave.age
python herramientas/respaldo/respaldo.py abrir --archivo <respaldo>.age --llave enenos_respaldo_llave.age --destino <carpeta>
```

`abrir` deja `<carpeta>/respaldo/datos/<la misma ruta que tenía en el VPS>` y comprueba cada cosa contra su
`MANIFIESTO.json` (sha256, integridad y filas por tabla).

**Los secretos de la PC de Eñeños** (no viven en el VPS): `herramientas/respaldo/respaldo_pc.bat` arma
`enenos_respaldo_pc_<fecha>.tar.gz.age` con lo de `respaldo_pc.json`: las llaves que firman las listas de descarga
(`~/.enenos`), Cloudflare (`~/.cloudflare`), las llaves SSH de los VPS y la del grabador. Misma llave pública.
Al reconstruir, cada cosa vuelve a su lugar en la carpeta del usuario.

`ver_respaldo.bat` comprueba el más nuevo de cada uno (VPS y PC).

⏳ Falta: el botón en el panel.

## 2 · Levantar todo

La guía larga, con lo medido en cada paso: `documentacion/TOPOLOGIA_CONTENEDORES.md`. Lo que sigue es el orden.
⚠ El paso 5 depende de «Generar backup» (todavía no existe): hoy el estado se lleva con `mudanza.py`.

1. **Un VPS Linux** (x86_64 o arm64: las imágenes de la casa son Python puro) con Docker y `docker compose`.
2. **Clonar este repo** y los hijos que figuran en `juegos.json`.
3. **Las imágenes.** Cada una se arma en SU repo (la cabecera de `herramientas/contenedores/docker-compose.yml` lo dice):
   - las de la casa, acá: `cd herramientas/contenedores && docker compose build` (arma `cuentas` y `parches`;
     `puerta` también, con `COMPOSE_PROFILES=prueba`). Sueltas, parado en la raíz:
     `docker build -f herramientas/contenedores/cuentas.Dockerfile -t enenos-cuentas:local .` (ídem `parches`, `puerta`);
   - las del R2Beat 2013 (`r2beat2013-juego`, `r2beat2013-web`), en el repo PRIVADO del juego, con su
     `herramientas/contenedores/juego.Dockerfile` y `web.Dockerfile` (llevan el exe, los charts y las tablas);
   - EDA y GunBound, con el `despliegue/Dockerfile` de su repo (`eda-server:local`, `gunbound-server:local`);
   - o se bajan hechas del registro privado (`ghcr.io/r2beatlatino/<pieza>:<fecha>`; se suben con
     `publicar_imagenes.sh`) y se nombran en el `.env` (`CUENTAS_IMAGEN`, `JUEGO_IMAGEN`, `WEB_IMAGEN`…).
4. **El `.env`**: `cp herramientas/contenedores/ejemplo.env herramientas/contenedores/.env` y completar
   `R2_IP_PUBLICA`, `COMPOSE_PROFILES` (`prueba`, `eda`, `gunbound`: los que corran en esta máquina), `WEB_NOMBRE` /
   `WEB_AUTH_NOMBRE` y, del respaldo, los secretos (`R2_OAUTH_*`, `R2_DISCORD_EVENTOS_WEBHOOK`, `R2_CUENTAS_FICHA_INTERNA`,
   `R2_CUENTAS_CLAVE_PUBLICA`).
5. **El estado** (bases y la clave que firma los pases), a los volúmenes, ANTES de levantar nada:
   `python3 herramientas/contenedores/mudanza.py importar --proyecto enenos --origen <carpeta>` (las piezas `cuentas` y
   `r2beat2013`; se niega a pisar un volumen que ya tiene base). La carpeta sale de `mudanza.py exportar` en la máquina
   vieja. Los volúmenes de EDA y GunBound los lleva su repo.
6. **Levantar**: `cd herramientas/contenedores && docker compose up -d` y `docker compose ps` (cada servicio tiene su
   chequeo de salud: `cuentas` contesta `GET /salud` en el 48195, sólo hacia el proxy).
7. **El dominio**: apuntar en Cloudflare los nombres (el del sitio y el de auth) al VPS nuevo.
8. **Comprobar**: entrar con una cuenta de prueba a cada juego. La prueba con Docker de la casa:
   `R2BEAT2013_REPO=<repo del juego> python3 pruebas/probar_contenedores.py --docker --imagenes <juego> <cuentas>`.

## 3 · El simulacro

Un respaldo que nunca se restauró no es un respaldo. ⏳ Se prueba levantando todo en una máquina vacía sólo con los
repos y el archivo, y se anota acá la fecha del último simulacro que salió bien.

## Estado

| paso | estado |
|---|---|
| repo padre + catálogo `juegos.json` + guardia | ✅ 19-nov |
| repo GunBound público | ✅ 19-nov |
| mudar el código de las cuentas y la casa a este repo | 🟡 19-nov copiado y con pruebas verdes; falta lo de `PENDIENTES.md` 1 y 2 |
| «Generar backup» | 🟡 1.er respaldo real 20-nov 01:54 UTC, abierto y comprobado por Eñeños (24 cosas sanas); falta el botón y los secretos de la PC |
| guía completa + simulacro | ⏳ |
