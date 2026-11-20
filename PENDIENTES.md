# Lo que falta en el Coordinador

> La lista viva. Se marca **en el momento** en que algo queda hecho (con la fecha), no después.
> Orden y decisiones de Benja, 19-nov-2026.

## Para poder levantar Eñeños desde cero

- [x] **Repo padre público** + catálogo `juegos.json` (la tabla del README se arma sola) + guardia de lo que nunca entra — 19-nov
- [x] **GunBound** con repo público propio (sin arte de Softnyx, sin correos personales) — 19-nov
- [x] **Licencia AGPL-3.0** en el padre y en GunBound (como R2beat-2013) — 19-nov
- [ ] **1 · El código de las cuentas** acá: login, Google/Discord, el pase firmado, el panel chico, lanzamientos, amigos y presencia (hoy en una rama del repo privado del 2013; se copia SIN su historial)
  - [x] copiado SIN historial de la rama `claude/topologia-docker-99488b`: `servidor/` (portero, vínculos, social, lanzamientos, firma, panel) y sus pruebas, verdes solas acá — 19-nov
  - [ ] que la FUENTE sea este repo: dejar de editar esos archivos en la rama del 2013 (si cambian allá, esta copia queda vieja)
  - (del lado de cada juego quedan, a propósito, en su repo: `pase.py`, `presencia.py`, `enlazar_cuentas.py`)
- [ ] **2 · La casa** acá: compose, Caddy, scripts del VPS, mudanza, server de parches del launcher, la página de login
  - [x] copiado: compose (+ red-host), Dockerfile de `cuentas`/`parches`/`puerta`, `Caddyfile`, `auth/`, `parches/`, `puerta/`, `mudanza.py`, `publicar_imagenes.sh`, `actualizar_prueba.sh`, `usa/` — 19-nov
  - [ ] la imagen `web` (Caddy) todavía la arma el repo del 2013 (junta su sitio Astro con el `Caddyfile` y `auth/`): separar el proxy de la casa del sitio del juego, para que el `Caddyfile` viva en un solo lugar
  - [ ] la parte B de `pruebas/probar_contenedores.py` (con Docker) corrida desde acá: pide `R2BEAT2013_REPO` y la imagen del juego (`--imagenes`)
  - [ ] `pruebas/probar_puerta_login.py` se salta sin `R2BEAT2013_REPO` (arma los paquetes con el generador del juego): correrla con él
- [ ] **3 · «Generar backup»**: botón manual (sólo admin) + comando; UN archivo cifrado con la clave de Benja con las bases (cuentas + cada juego), la configuración y los secretos (llaves de firma, `.env`, OAuth, tokens)
  - [x] el comando (`herramientas/respaldo/`): bases en vivo con la API de SQLite, cifrado con `age` a la llave PÚBLICA, MANIFIESTO con sha256 y filas; prueba con controles (16 verdes, corrida en el VPS) — 19-nov
  - [x] la lista del VPS de Miami (`respaldo_vps.json`, 24 cosas, todas medidas ahí) — 19-nov
  - [x] Benja creó SU llave (privada cifrada con su contraseña, fuera del repo; la pública en el repo) — 19-nov
  - [x] el primer respaldo de verdad: 24 cosas, 18,3 MB cifrado, bajado a la PC de Benja (sha256 igual) y borrado del VPS — 20-nov 01:54 UTC
  - [x] Benja lo abrió en su PC con `ver_respaldo.bat` y su contraseña: «✔ respaldo sano · 24 cosas» (el control de punta a punta) — 19-nov
  - [ ] los secretos de la PC de Benja (llave de las listas de GunBound, Cloudflare, SSH)
  - [ ] el botón en el panel (sólo admin)
- [ ] **6 · La ficha `enenos.json`** de cada juego (qué sabe hacer su server, para que el panel muestre sólo lo que funciona)
  - [x] GunBound — 19-nov
  - [ ] R2beat-2013 — PR #3 listo (pruebas en verde), falta fusionarlo
  - [x] EDA — 19-nov (PR #58, aprobado por Benja)

## Pendientes (esperan otra cosa)

- [ ] **5 · El panel nuevo** — el prototipo está en la PC de Benja; falta que él lo moldee
- [ ] **4 · `RECONSTRUIR.md` completo + el simulacro** (levantar todo en una máquina vacía sólo con los repos y el respaldo) — espera al panel nuevo
