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

⏳ Se escribe al mudar el código. Esqueleto:

1. Un VPS Linux x86_64 con Docker y compose.
2. Clonar este repo y los hijos que figuran en `juegos.json`.
3. Descifrar el respaldo y poner cada cosa en su lugar (bases → volúmenes, `.env`, llaves).
4. Armar las imágenes y `docker compose up -d`.
5. Apuntar el dominio (Cloudflare) al VPS nuevo.
6. Comprobar: entrar con una cuenta de prueba a cada juego.

## 3 · El simulacro

Un respaldo que nunca se restauró no es un respaldo. ⏳ Se prueba levantando todo en una máquina vacía sólo con los
repos y el archivo, y se anota acá la fecha del último simulacro que salió bien.

## Estado

| paso | estado |
|---|---|
| repo padre + catálogo `juegos.json` + guardia | ✅ 19-nov |
| repo GunBound público | ✅ 19-nov |
| mudar el código de las cuentas y la casa a este repo | ⏳ |
| «Generar backup» | ⏳ |
| guía completa + simulacro | ⏳ |
