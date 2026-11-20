# Reconstruir Eñeños desde cero

> Para quien llega **sin ningún contexto** (una persona o una sesión nueva de Claude) con dos cosas:
> **estos repos** y **el respaldo cifrado de Benja** (`enenos_respaldo_<fecha>.age`) más su clave.
> ⚠ Esta guía se va completando a medida que el código del Coordinador se muda a este repo (ver «Estado»).

## 0 · Qué hay en cada lado

| dónde | qué | quién lo tiene |
|---|---|---|
| este repo | el Coordinador: cuentas, panel, catálogo, contenedores, dominio, mudanza | público, GitHub |
| los repos hijos (ver `juegos.json`) | el server de cada juego | público, GitHub |
| **el respaldo** | las bases (cuentas + cada juego), la configuración viva y **los secretos** | **sólo Benja** |
| los clientes de los juegos | instaladores y paks | aparte (no van en ninguno de los dos) |

**Los secretos van en el respaldo y no se pueden perder**: la llave que firma el pase del Eñeños-ID y la que firma
las listas de descarga. El launcher instalado de cada jugador confía en ellas; si se pierden hay que sacar un
launcher nuevo y que todos lo reinstalen.

## 1 · Generar el respaldo (Benja, a mano)

⏳ Por fabricar: «Generar backup» en el panel (sólo admin) y su comando. Junta en UN archivo cifrado:
la base de cuentas, la de cada juego, la configuración (moderadores, lanzamientos…), los `.env` y las llaves.
El archivo se baja y no queda en el server.

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
| «Generar backup» | ⏳ |
| guía completa + simulacro | ⏳ |
