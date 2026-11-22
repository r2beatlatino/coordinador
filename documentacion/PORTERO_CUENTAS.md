# El portero — las cuentas de R2Beat para EDA (y los juegos que vengan)

> 📦 **Copiado al Coordinador el 19-nov-2026** desde el repo del R2Beat 2013 (rama `claude/topologia-docker-99488b`),
> sin su historial. Lo que nombra del JUEGO (`juego.Dockerfile`, `web.Dockerfile`, `servidor/api_web.py`, `servidor/pase.py`,
> `datos.db`, el panel viejo…) sigue en ese repo. Las rutas `servidor/`, `pruebas/` y `herramientas/contenedores/` de acá
> son las mismas que allá.

> **11-nov-2026 · (174) · NO en prod.** Eñeños: *«una capa arriba de ambos juegos para los accountid»* ·
> *«¿habría que reiniciar el servidor de r2beat?»* (no) · *«solo las cuentas aprobadas tendrán acceso a eda por ahora»* ·
> *«solo las aprobadas podrán descargar / jugar»*.
> Código: `servidor/portero.py` + `servidor/firma_ed25519.py` · prueba `pruebas/probar_portero.py` (33 ✔).

## 1 · La idea, en criollo

- **La cuenta es la de R2Beat.** El número de cuenta (`users.uid`) es la identidad en todos los juegos. No se crean cuentas
  nuevas ni se mudan las que hay: se entra con el mismo usuario y la misma clave.
- **El portero es un programa aparte** que corre al lado del juego en el VPS de Chile. Revisa usuario y clave y, si la
  cuenta está **aprobada** para ese juego, le da un **pase firmado** que vale 5 minutos.
- **El otro juego comprueba el pase solo**, con la clave pública. No le pregunta nada a Chile: si R2Beat se reinicia o
  se cae, el que ya está jugando EDA sigue.
- **Las no aprobadas no reciben el pase (no juegan) ni la lista de archivos del cliente (no saben qué bajar).**

## 2 · Por qué no hace falta reiniciar R2Beat

| | |
|---|---|
| el server de juego | **no se toca**: el portero es otro proceso (`python -m servidor.portero`) y no lo importa nadie |
| `datos.db` | ⛔ **sólo lectura** (`mode=ro` + `query_only`). La prueba lo comprueba por md5 y con un `UPDATE` que tiene que rebotar |
| lo suyo | `portero.db` (aprobados, baneos por juego, sesiones, pases emitidos) y `portero_clave.json` (la clave privada). Los dos al lado de `datos.db` y gitignorados |
| Caddy | una ruta nueva `/cuentas/*` → `127.0.0.1:48195`. Se aplica con `reload`, que no corta a nadie |

## 3 · Las rutas

Las rutas andan con o sin el prefijo `/cuentas`. Todo POST pide `X-R2: 1`.

| ruta | qué |
|---|---|
| `GET /salud` | `{"ok": true}` |
| `GET /clave-publica` | la JWKS: la clave pública. El server de EDA la baja una vez |
| `POST /entrar {usuario, clave}` o `{usuario, pass_sha256_upper}` | → `{sesion, uid, vence, juegos:[{id, nombre, permitido}]}`. La sesión dura 30 días, se guarda en `portero.db` y sobrevive a un reinicio |
| `POST /pase {juego}` + `Bearer` | → `{pase, vence}`. **403** si la cuenta no está aprobada, está baneada en ese juego, está baneada en R2Beat o fue fusionada. ★ 20-nov: baneada en ese juego → `{"error": "baneado", juego, nombre, motivo, hasta, restante_seg, texto}` (ver `PANEL_COORDINADOR.md` §2.1) |
| `GET /manifiesto/<juego>` + `Bearer` | → el manifest del cliente, **sólo a aprobadas**. Sale de `R2_PORTERO_MANIFIESTOS/<juego>.json` y se lee del disco en cada pedido |
| `GET /yo` + `Bearer` | → `{uid, juegos}` |
| `POST /salir` + `Bearer` | cierra la sesión |

Freno de intentos y mensajes como `api_web`: 8 fallos por IP y por usuario en 15 minutos, y el mismo 401 para
«no existe» y para «clave mala».

## 4 · El pase: el contrato con EDA

Es un JWT compacto con firma **EdDSA (Ed25519, RFC 8037)**:

```
header  {"alg":"EdDSA","typ":"JWT","kid":"<16 hex>"}
payload {"iss":"r2beat-portero","aud":"eda","sub":"<uid>","iat":…,"exp":iat+300,"jti":"<único>"}
```

El server de EDA tiene que comprobar:
- la firma, con la JWKS;
- que `alg` sea `EdDSA` y `iss` sea `r2beat-portero`;
- que `aud` sea `eda`;
- que `exp` no haya pasado (hasta 30 s de tolerancia);
- y guardar el `jti` 5 minutos para no aceptar el mismo pase dos veces.

`portero.comprobar_pase` es el modelo, y la prueba también lo comprueba con Node.
⛔ **El pase no lleva el nombre de login**, porque es privado. La identidad es `sub`.

La firma está escrita en **Python puro** (`firma_ed25519.py`), porque el VPS no tiene `cryptography` y el server sólo
usa la biblioteca estándar. Tarda 3 ms por pase. No es de tiempo constante, pero sólo firma el portero, con su clave.

## 5 · El flujo con EDA

```
launcher ─ POST /cuentas/entrar ─────────▶ portero (Chile)   {sesion, juegos}
launcher ─ GET  /cuentas/manifiesto/eda ─▶ portero           (sólo aprobadas) → baja de la CDN
launcher ─ POST /cuentas/pase {eda} ─────▶ portero           {pase}
launcher ─ el pase ──────────────────────▶ server de EDA (USA): comprueba → ticket corto (≤ 21 caracteres)
launcher ─ abre EDA con «usuario ticket»   (el campo del juego no entra el pase entero: por eso el canje)
```

**Lo lleva la sesión de EDA:** el canje pase → ticket en su server y cómo recibe el juego el ticket.

## 6 · Las descargas: la puerta está en la LISTA, no en cada archivo

Sin aprobación no hay manifest. Sin manifest, el launcher no sabe qué bajar ni de dónde, porque la `base` de la CDN lleva
un tramo al azar: `/files-eda/<release>-<azar>/`.

⚠ **Un aprobado que pase la dirección deja bajar a cualquiera.** Para cerrar cada archivo hay dos caminos:
- servir los archivos desde el VPS sin caché, que gasta el ancho de banda de Chile;
- un token firmado de Cloudflare (Worker o regla), que es trabajo aparte.

**Para jugar, la puerta sí es completa:** sin pase firmado, el server de EDA no deja entrar.

## 7 · La lista de aprobados (se maneja por consola, en el VPS)

```bash
python -m servidor.portero aprobar <usuario> [eda]
python -m servidor.portero quitar <usuario> [eda]
python -m servidor.portero banear <usuario> [eda] [--horas N | --dias N] [motivo…]   # ★ 20-nov: sin tiempo = permanente
python -m servidor.portero desbanear <usuario> [eda]     # levanta antes de tiempo (la fila queda como historial)
python -m servidor.portero lista [eda]
python -m servidor.portero clave            # la clave PÚBLICA (JWKS), para pasársela a EDA
```

~~Un botón en el panel queda para más adelante.~~ ✅ Desde el 12-nov hay **panel web propio del portero**:
`/cuentas/admin` (Chile) y, por proxy, `eñeños.link/admin`. Entran los ADMIN de `admin.txt`.

### ★ Los MODERADORES (12-nov, ✅ EN PROD)

Eñeños: dos colaboradores de EDA (jugador2 y jugador3) que aprueben cuentas sin depender de él; «2, tu
recomendación» = **sin banear**.

- `moderadores.txt` **al lado de `admin.txt`** (en prod: `/opt/r2beat/game2013/moderadores.txt`), mismo formato: uid,
  login o `@apodo`, `#` comenta. ⛔ Gitignorado: son cuentas reales.
- Entran al **mismo panel** con su cuenta de R2Beat. Pueden **buscar, aprobar y quitar**. Nada más:
  - banear / desbanear → 403 (y el panel no les muestra esos botones);
  - una cuenta con rol (ADMIN o moderador) → 403, y el buscador ni se la muestra;
  - el login de los ADMIN no lo ven: en la lista y en la auditoría sale «ADMIN»; de la auditoría ven sólo movimientos
    de cuentas (no quién entró al panel).
- Todo lo que hacen queda en la auditoría con SU login. Sacarlo del archivo le corta la sesión al instante (se mira en
  cada pedido, como `admin.txt`).
- Prueba: `probar_portero.py` §11 (con sus controles al revés y los controles del ADMIN).
- ★ **19-nov · juegos asignados** (`10000231 gunbound,eda`; sin lista = como antes). Con lista, el moderador sólo ve y
  toca esos juegos y ahí también banea por juego. Lo maneja el panel del Coordinador: **`PANEL_COORDINADOR.md`**.

## 8 · El launcher — ✅ hecho en local (11-nov), SIN COMPILAR, NO en prod

La lógica está en `taller/launcher_webui/eda_juego.py`, sin ventana, para poder probarla sola
(`pruebas/probar_launcher_eda.py`, 33 ✔). Arriba va la pantalla (`launcher_webui_core.Api.eda_*`, `ui/launcher.html` +
`launcher.js`). Lo que mide y pide EDA está en su `EDA_PARA_EL_LAUNCHER.md`.

1. **Un solo login.** Después de ENTRAR, el launcher también entra al portero con el `pass_sha256_upper`. Va en un hilo
   aparte, así que R2Beat no espera.
2. ★ **El BOTÓN de EDA** (12-nov, el dibujo de Eñeños), al lado de la frase y debajo del logo. Lleva la pareja recortada
   del arte (`ui/eda-boton.jpg`) y el logo «E.D.A».
   - **Apagado** (gris, 🔒 BETA): sin sesión, cuenta no aprobada o sin portero. Si lo tocan, se explica por qué.
   - **Prendido** (color y latido rosa): cuenta aprobada.
   - **Activo** (borde celeste, «◀ R2BEAT»): estás en EDA; si lo tocás, volvés.

   La **transición**: lo de R2Beat se desliza y se apaga, y entra el arte de EDA (`ui/eda-fondo.jpg`, 1548×672) con un
   destello y un acercamiento. Ocupa toda la derecha con `cover` y foco en 55,5 % / arriba, para no perder a la pareja.
   Abajo a la izquierda va el sello «BETA CERRADA · Ñ2-EDA NOVIEMBRE». Con «Sin animaciones», todo es instantáneo.
   Sin portero (red caída, server viejo), el botón queda apagado y R2Beat queda igual.
   - Una cuenta **no aprobada** ve EDA con 🔒 y el aviso «Todavía no tenés acceso», sin botón ni carpeta.
   - La pestaña elegida se recuerda en `ui.juego` de las prefs.
3. **La carpeta**: al lado de la de R2Beat, no adentro. `C:\Game\R2beatTEST0` → `C:\Game\EDA`.
   - «Cambiar» abre el diálogo de Windows. Si la carpeta elegida no se llama EDA, se crea una `EDA` adentro.
   - Se recuerda en `eda_dir`.
   - El sello es propio: `sello-eda-<hash>.json`, al lado de `launcher.json`.
4. **Bajar**: `GET /cuentas/manifiesto/eda`, después `pendientes` y después `bajar`, con el mismo `download_file` del
   launcher, desde la CDN y sin token.
   - Cada archivo se comprueba por md5: si llega dañado, se borra y es error.
   - Lo comprobado va al sello, para no releer los 338 MB.
   - `autoexec.cfg` y `eda_d3d9.ini` son del jugador: se bajan sólo si faltan.
5. **JUGAR EDA** (o «BAJAR Y JUGAR»): pase → `POST <canje>` {pase} → {usuario, ticket} → `"<carpeta>\EDA_limpio.exe"
   <usuario> <ticket> <servidor>`.
   - La línea es una cadena, con la ruta entre comillas, y `cwd` es la carpeta.
   - ⛔ Lo que llega de los servers se valida con regex antes de pegarlo en la línea (usuario: dígitos; ticket:
     20 alfanuméricos; servidor: `host:puerto`). Un ticket con espacio sería un argumento inyectado.
6. **Las opciones**. ★ Desde el 12-nov se eligen también ANTES de instalar: quedan en las prefs (`eda_opc`) y se escriben
   apenas termina la bajada.
   - tope de FPS (60 / 120 / 144 / 165 / 240 / sin tope) y contador de FPS, en `eda_d3d9.ini [video]`;
   - modo ventana, música y efectos, en `autoexec.cfg`.

   Se cambia **sólo esa línea**, porque el juego reescribe `autoexec.cfg` al cerrarse con las teclas en otro orden.
   ⛔ Las técnicas (`tope_estricto`, `red_inmediata`, `buferes_rapidos`, `bombeo_red`) no se muestran ni se dejan tocar.
7. **«Dejar abierto»** vale para los dos juegos.

### ★ El manifest de EDA trae DOS campos más que el de R2Beat

```
{"version": "...", "base": "https://.../files-eda/<release>-<azar>/", "files": [{path, size, md5}, ...],
 "servidor": "<host EDA>:25900",                    ← el 3er argumento del exe
 "canje":    "https://<dominio EDA>/eda/pase"}      ← dónde se cambia el pase por el ticket (tiene que ser https)}
```

Así el dominio y el puerto de EDA se cambian en el VPS, **sin recompilar el launcher**. El launcher rechaza un manifest
sin esos dos campos o con rutas que se salgan de la carpeta (`..`, absolutas).

### ★★ Launcher 2.6 (12-nov): el manifest lo FIRMA EDA — ⏳ compilado, NO publicado

Eñeños: que EDA no dependa de su «aprueba, aprueba» para cada versión del cliente. Desde el 2.6:

1. **El portero es la PUERTA:** `GET /cuentas/manifiesto/eda` sigue haciendo falta (200 sólo a una aprobada), pero su
   contenido ya no se usa. Sin aprobación no se pide nada más.
2. **La LISTA la firma EDA:** `https://xn--eeos-gqab.link/eda/manifiesto.jws` (no-store, Cloudflare no lo guarda), un JWS
   compacto Ed25519: cabecera `{"alg":"EdDSA","typ":"eda-manifiesto","kid":sha256(pub)[:16]}`, carga = el manifest de
   arriba + `"aud":"eda-launcher"` + `"iat"`. Lo firma EDA en su VPS (`herramientas/firmar_manifiesto.py` del repo de EDA).
3. **Las claves públicas van FIJAS en el launcher** (`eda_juego.CLAVES_EDA`): la ACTUAL `d033b53012b0a91f` (privada en
   el VPS de EDA) y la de RESERVA `d4a9aeb1576fb27b` (privada fuera de línea, en la PC de Eñeños). Si se pierde o se filtra
   la actual, EDA firma con la de reserva sin otro launcher. Si se pierden las dos: launcher nuevo.
4. **Rechaza** (y no baja nada): sin firma, otro `alg`/`typ`, `kid` desconocido, firma que no verifica, otro `aud`, y una
   `version` MENOR que la última aceptada (`eda_ver_ok` en las prefs; se compara por número). ⇒ Para volver atrás un
   cliente roto, EDA publica el viejo con un número MAYOR.
5. La verificación es `firma_ed25519.py`, **copia idéntica** de la del server (la prueba compara los md5). 3 ms.

Prueba: `probar_launcher_eda.py` §9 (12 controles al revés) + el manifiesto real de EDA verificado con las claves fijas.
Compilado: `_trabajo/deploy_eda26/` (launcher `b38f59a5`, instalador `df01f074`; el exe trae las 2 claves, comprobado
dentro del PYZ). Publicar: `powershell -File _trabajo\deploy_eda26\publicar_launcher.ps1` (GitHub → descarga pública por
md5 → exe al VPS → `launcher_switch.sh nuevo`); volver: `… -Volver` (= el 2.5 `fc82eed9`). ⛔ Sólo a la orden de Eñeños.
⚠ Mientras haya launchers 2.5 dando vueltas, siguen leyendo el manifest del PORTERO: el `eda.json` de
`/opt/r2beat/portero/manifiestos/` tiene que seguir al día (o quedar en una versión que funcione) hasta que todos sean 2.6.

### ⏳ Lo que falta
- ✅ **El dominio de EDA** (Eñeños, 11-nov): **`eñeños.link`** con la nube de Cloudflare (la web y el canje HTTPS) y
  **`eda.eñeños.link`** sin nube (el juego, TCP 25900), los dos al VPS de USA. ⛔ En el manifest y en lo técnico va el
  PUNYCODE: `xn--eeos-gqab.link` y `eda.xn--eeos-gqab.link`, porque el launcher valida `[A-Za-z0-9.-]` y el exe del 2009
  resuelve el host en ANSI. Medido: el 25900 abre en `eda.`; `https://xn--eeos-gqab.link` todavía da 403 (falta Caddy).
  ✅ **Los archivos de EDA** (Eñeños): en el VPS de USA, **sólo por la CDN de Cloudflare**: «ip directa no se entrega».
  `base = https://xn--eeos-gqab.link/files-eda/<release>-<azar>/`. Caddy de EDA: `/files-eda/*` y `/eda/*` sólo a las
  IPs de Cloudflare (como el `cf_only` de Chile); el 25900 del juego, abierto a todos.
  ⛔ **Cloudflare no guarda por defecto `.dat .dll .flt .asi .ini .cfg`** (`.exe` sí): sin una **Cache Rule**
  (host `xn--eeos-gqab.link`, ruta que empieza en `/files-eda/` → Eligible for cache, Edge TTL largo), el `Data.dat` de
  329 MB saldría del VPS en cada descarga. Comprobar con `cf-cache-status: HIT` en la 2.ª bajada.
- **Armar la release de EDA**: los 16 archivos (338 MB) a `/files-eda/<release>-<azar>/` en la CDN, y el `eda.json` en
  `R2_PORTERO_MANIFIESTOS`. `Data.dat` mide 345 MB y entra en el tope de 512 MB por archivo de la caché de Cloudflare.
- **Compilar el launcher** (PyInstaller toma `eda_juego.py` solo, porque lo importa el core) y probarlo con el exe de
  verdad contra el server de prueba de EDA.

## 9 · Para subirlo (⛔ sólo cuando Eñeños lo pida — no reinicia el juego)

1. Subir `servidor/portero.py` y `servidor/firma_ed25519.py`. Lo que ya corre no los importa, así que no cambia nada
   del juego.
2. Crear el servicio `r2beat-portero`:
   - mismo usuario y misma carpeta que `r2beat-game2013`;
   - `ExecStart=python3 -m servidor.portero`;
   - `Environment=R2_PORTERO_MANIFIESTOS=…`.

   La primera vez crea `portero.db` y la clave. ⛔ La clave no se baja ni se imprime; la pública sale con
   `… portero clave`.
3. Caddy: agregar `handle /cuentas/* { reverse_proxy 127.0.0.1:48195 }` en el bloque de `r2beatlatino.com`, **antes** del
   último `handle`. Después `caddy validate` y `reload`. ⚠ Un Caddyfile roto tira también la CDN.
4. Aprobar las cuentas con la consola.
5. Respaldo: `portero.db` no está en el respaldo diario de `datos.db`. Hay que sumarla (`respaldo.py`) o copiarla con
   `.backup()`.

## 10 · El portero en contenedor y dos variables nuevas (14-nov-2026 · EN LOCAL, NO en prod)

El portero es la semilla de **Cuenta Eñeños**, el servicio que va a ser el dueño de las cuentas de todos los juegos. El
plan entero (las etapas, la mudanza de máquina, los riesgos) está en **`TOPOLOGIA_CONTENEDORES.md`**. Acá, sólo lo que
cambió del portero:

| variable | qué | por omisión (= como siempre) |
|---|---|---|
| `R2_PORTERO_HOST` | dónde escucha | `127.0.0.1` |
| `R2_PORTERO_PROXIES` | a quién se le cree la IP del jugador (`CF-Connecting-IP` / `X-Forwarded-For`): IPs o redes separadas por coma | `127.0.0.1,::1` |

- **Sin las variables el portero hace exactamente lo de antes.** En prod no están puestas y no hace falta ponerlas.
- **Para qué existen:** adentro de un contenedor `127.0.0.1` no es la máquina, y el proxy (Caddy) llega desde la red de
  Docker. Sin `R2_PORTERO_PROXIES`, todos los jugadores tendrían «la misma IP» (la del proxy) y el freno de 8 claves
  malas en 15 minutos **bloquearía el login de todos juntos**.
- ⛔ `R2_PORTERO_HOST=0.0.0.0` sólo dentro de un contenedor, con el puerto publicado hacia `127.0.0.1` de la máquina:
  acá adentro no hay HTTPS.
- La imagen (`herramientas/contenedores/cuentas.Dockerfile`) trae los 5 archivos del portero y nada del juego. Su
  estado (`portero.db`, `portero_clave.json`, `admin.txt`, `moderadores.txt`, los manifiestos) vive en un volumen.
- ⚠ **Medido en contenedor:** el portero todavía necesita el **archivo** `datos.db` del juego (no el proceso): con el
  juego apagado sigue dando pases y hasta se reinicia solo; sobre una base vacía no arranca hasta que exista la tabla
  `users`; y ese volumen no se puede montar en sólo lectura (SQLite en WAL necesita abrir el `-shm`).
- ⛔ **La clave que firma viaja con el volumen.** Si al mudar el portero se pierde o se crea otra, EDA rechaza los
  pases hasta bajar la clave pública nueva. `mudanza.py` la lleva, y la prueba comprueba que un pase de «la máquina
  nueva» verifica con la clave pública de antes.

Prueba: `pruebas/probar_contenedores.py` (parte A, sin Docker: las dos variables con su control; parte B, `--docker`).
