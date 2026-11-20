# El panel del Coordinador Eñeños — fase A

> **19-nov-2026 · rama `panel-fase-a` · EN LOCAL, NO publicado.** El diseño es el prototipo aprobado por Benja
> (`_trabajo/coordinador/prototipo/` en la PC de Benja); esto lo vuelve real **sólo** en tres pantallas: ENTRAR,
> ELEGIR JUEGO y LA RED. ⛔ Ningún dato inventado: si algo todavía no existe, no se muestra.
>
> Código: `servidor/coordinador.py` (el backend, dentro del portero) + `servidor/panel/` (la página).
> Prueba: `pruebas/probar_coordinador.py` (104 ✔, cada regla con su control al revés).

## 1 · Cómo entra uno

Sólo con **Discord o Google**, y sólo si ese Discord/Google está **vinculado** a un Eñeños-ID que tiene **rol**
(`admin.txt` o `moderadores.txt`). Nada de usuario y contraseña.

Google y Discord sólo aceptan las vueltas **ya registradas** (`<R2_OAUTH_BASE>/oauth/vuelta`, en el dominio de auth).
Por eso el panel no recibe la vuelta: la recibe Cuenta Eñeños, y le pasa al panel un **ticket**.

```
1. panel ── POST /api/oauth {proveedor} (X-R2) ──────────▶ cuentas: crea el flujo (modo «panel»), guarda el DESTINO
   (el primero de R2_PANEL_URL, o uno pedido que esté EXACTO en esa lista) y la huella de una cookie nueva del
   navegador `coordinador_flujo` (HttpOnly · Secure · SameSite=Strict · 10 min) → {url del proveedor}
2. navegador ──▶ Discord / Google ──▶ <auth>/oauth/vuelta?code&state
3. cuentas: ¿quién es? (su id en Discord/Google) → ¿vinculado? ¿activo? ¿con rol? → guarda un TICKET
   (un solo uso, 60 s, sólo su huella, atado al uid y a la cookie del flujo) → 302 a <destino>/entrar?ticket=…
4. panel: borra el ticket de la barra de direcciones y lo canjea: POST /api/canjear {ticket} (X-R2, con la cookie
   del flujo) → cookie `coordinador` (HttpOnly · Secure · SameSite=Strict · Path=/ · 8 h), o el porqué:
     no_vinculada  (muestra el nombre de esa cuenta de Discord/Google y cómo vincularla desde el launcher)
     sin_permisos  (muestra su Eñeños-ID para que se lo pase a un Admin)
     suspendida · cancelada · vencido · otro_navegador
```

- El destino **nunca** sale del pedido: se guarda en la ida (validado contra la lista blanca) y en la vuelta se vuelve a
  mirar que siga en la lista. Un `destino` metido en la vuelta no cambia nada.
- En el canje se **vuelve a mirar** el rol y el estado (si a alguien le sacan el rol entre la vuelta y el canje, no entra).
- Cada pedido del panel vuelve a mirar el rol (`portero.admin_de`): sacarlo de `admin.txt` / `moderadores.txt` lo deja
  afuera **al instante**. La sesión es la misma tabla que la del panel chico (`sesiones_admin`).
- Cada ingreso queda en la auditoría («entrar al Coordinador · con Discord»).
- La página va con CSP estricta (sin scripts de afuera, sin marcos) y `Referrer-Policy: no-referrer` (el ticket no se
  filtra por el referer).

## 2 · Roles y juegos asignados

| rol | dónde | qué ve | qué toca |
|---|---|---|---|
| **admin** | `admin.txt` (a mano) | todo | todo + «Moderadores y permisos» |
| **moderador con juegos** | `moderadores.txt`: `uid juego1,juego2` | sólo sus juegos (tarjetas, personas, invitaciones, lanzamientos, auditoría) | aprobar, quitar, **banear y desbanear por juego**, decidir invitaciones — sólo en sus juegos |
| **moderador formato viejo** | `moderadores.txt`: `uid` (sin lista) | todos los juegos (como hasta hoy) | aprobar y quitar (como hasta hoy: «sin banear») |

El formato de `moderadores.txt` (compatible con el de antes; `#` comenta; la identidad puede ser uid, login o `@apodo`):

```
110                    # sin lista = como siempre: todos los juegos, sólo aprobar / quitar
10000231 gunbound      # sólo GunBound (PROD y TEST, y sus pases «gunbound-…»)
mod1 eda,r2beat2013    # dos juegos
10000300 -             # en el equipo, pero sin juegos todavía (entra y no ve ninguno)
```

- Los ids son los de `juegos.json` (`r2beat2013`, `gunbound`, `eda`, `r2beat-moderno`, `wolfteam`). Un juego abarca su
  pase `live`, su `test` y los que empiecen con `<live>-` (`r2beat2013-subir` es de R2Beat).
- ⚠ **Decisión a confirmar con Benja:** con juegos asignados el moderador **puede banear por juego** en esos juegos
  (lo pide «ni puede banear ahí» del encargo). El del formato viejo sigue sin banear, como decidió Benja el 12-nov.
- Los cambia el ADMIN desde **La red → Moderadores y permisos** (agregar por Eñeños-ID, tocar las etiquetas de los
  juegos, sacar del equipo). El panel reescribe **sólo la línea de esa cuenta** (los comentarios y las demás quedan),
  de forma atómica, y cada cambio queda en la auditoría. Pasar a alguien del formato viejo al nuevo pide confirmación.
- Los admins no se tocan desde el panel (siguen en `admin.txt`, a mano).
- La misma regla vale en el panel chico (`/cuentas/admin`): `admin_accion` y `lanzamientos.decidir` miran el juego.

### 2.1 · ★ Los baneos con tiempo (20-nov-2026 · EN LOCAL, rama `baneos-con-tiempo`, NO en prod)

Benja: *«baneos en X juegos, por X horas, por X días, X motivo; el launcher baneado, al presionar "Jugar" en X juego,
debe recibir un popup con el motivo de su ban + el tiempo»*.

- **`baneos.hasta`** (epoch; `NULL` = permanente). La columna se agrega sola (`ALTER`) al abrir una `portero.db` de
  antes: **los baneos viejos quedan permanentes**, como eran.
- **Un baneo vencido deja de contar solo**, al chequear (`portero.baneo_vigente`). No se borra: la fila queda como
  historial. **Desbanear antes de tiempo** = `hasta` pasa a «ahora» (tampoco se borra). Todo va a la auditoría, un
  renglón por servidor, con la duración y el motivo (`por 3 días · Insultos en el chat`).
- **Varios juegos de una vez**: `juegos: [...]` (ids del catálogo: cada uno con TODOS sus servidores — PROD, TEST y los
  `<live>-…`), o `pases: [...]`, o `pase` (uno, como antes). **Todo o nada**: si uno no se puede, no se toca ninguno.
- **Duración**: `horas: n`, `dias: n`, `meses: n` (un mes = 30 días justos) o `permanente: true` (una sola). **Motivo obligatorio, ≤ 200**: lo ve la persona.
- **Sólo ADMIN**: permanente y `red: true` (toda la red = todos los pases de los juegos del catálogo; `parches` y `web`
  no). Un ADMIN sin duración = permanente (como antes).
- **Moderador con juegos**: sólo en sus juegos, siempre con duración y hasta `portero.BANEO_TOPE_MODERADOR_SEG`.
  ★ **El tope se ajusta** con `R2_BANEO_TOPE_MODERADOR_DIAS` (de fábrica **365 = 12 meses**; entre 1 y 3650; se
  lee al arrancar). Benja, 20-nov: *«que los mod puedan banear horas, días, meses, tiempo ajustable»*.
  El moderador de formato viejo sigue sin banear.
- **El panel**: en la ficha de la persona, «Banear en varios juegos…» (casillas de juegos, «Toda la red» sólo admin,
  Horas / Días / Meses / Permanente, motivo con contador) y el «Banear» de cada servidor abre el mismo formulario para ese solo
  servidor; cada servidor baneado dice «vence en 2 d 3 h» o «permanente». En **La red**, la caja **Baneos vigentes**
  (los que vencen antes primero) con «Desbanear» antes de tiempo.
- **El pase negado** (`POST /pase`): el MISMO **403** de «no permitido», con los campos nuevos:

  ```json
  {"error": "baneado", "juego": "gunbound", "nombre": "GunBound", "motivo": "Insultos en el chat",
   "hasta": 1795151433, "restante_seg": 183600,
   "texto": "No puedes entrar a GunBound: Insultos en el chat. Vence en 2 días y 3 horas."}
  ```

  (`hasta` y `restante_seg` en `null` = permanente). ⚠ Un launcher VIEJO muestra `error` tal cual: dirá «baneado»
  en vez de «Tu cuenta todavía no tiene acceso…». `/manifiesto/<juego>` (EDA) devuelve la frase en `error` y el resto
  con `baneado: true`. `/entrar` y `/yo` marcan el juego con `baneo: {motivo, hasta, restante_seg}`.
- **El launcher** (rama `launcher-tauri`, `src-tauri/src/baneo.rs`): con `error: "baneado"` muestra el popup
  «No puedes entrar a <juego>», el motivo (como texto, escapado), «Vence en 2 días y 3 horas» / «Este bloqueo es
  permanente» y «Entendido»; no arranca el juego. Sin los campos nuevos, el mensaje de siempre.
- Pruebas: `pruebas/probar_baneos.py` (cada regla con su control al revés).

**Lo que nunca le llega a un moderador:** el login de nadie (las personas se muestran por Ñ2-ID o «Eñeños #id»; en la
auditoría los ADMIN, la consola y lo interno salen «ADMIN»), el nombre de la cuenta de Google/Discord (suele ser el
nombre real), las cuentas con rol (ni en el buscador ni en la ficha), IPs, correos (no se guardan) ni nada de la
contraseña. Busca por Eñeños-ID, por Ñ2-ID o por el login **exacto** (el admin, por el comienzo del login).

## 3 · Las rutas (en Cuenta Eñeños; Caddy del dominio del panel les antepone `/coordinador`)

| ruta | qué |
|---|---|
| `GET /coordinador/` · `/coordinador/entrar` | la página |
| `GET /coordinador/panel.js` · `panel.css` · `assets/…` | lo de la página (en el repo; sin datos) |
| `GET /coordinador/arte/<archivo>` | el arte de los juegos, de la carpeta `R2_PANEL_ARTE` (**fuera del repo**) |
| `GET /coordinador/api/estado` | `{proveedores, configurado, sesion}` — sin sesión |
| `GET /coordinador/api/catalogo` | lo visual de las tarjetas (para el login) — sin sesión |
| `GET /coordinador/api/juegos` | las tarjetas de sus juegos: servidores, lanzamiento, invitaciones pendientes |
| `GET /coordinador/api/personas?q=` | buscar personas |
| `GET /coordinador/api/persona/<uid>` | vínculos, estado y permisos por juego y servidor |
| `GET /coordinador/api/invitaciones` · `lanzamientos` · `auditoria` | filtrados por sus juegos |
| `GET /coordinador/api/equipo` | admins y moderadores con sus juegos (sólo admin) |
| `POST /coordinador/api/oauth {proveedor, destino?}` | empezar a entrar |
| `POST /coordinador/api/canjear {ticket}` | ticket → cookie de sesión |
| `POST /coordinador/api/salir` | |
| `POST /coordinador/api/accion {accion, uid, pase, detalle}` | aprobar · quitar · banear · desbanear (por pase) |
| ★ `POST /coordinador/api/accion {accion: banear, uid, juegos \| pases \| pase \| red, horas \| dias \| permanente, motivo}` | banear en VARIOS juegos de una vez, con tiempo (ver §2.1) |
| ★ `GET /coordinador/api/baneos` | los baneos vigentes de sus juegos, con `hasta` y `restante_seg` |
| `POST /coordinador/api/invitacion {id, accion}` | aprobar · rechazar |
| `POST /coordinador/api/equipo {accion, uid, juegos}` | juegos · agregar · quitar (sólo admin) |

Todo POST pide `X-R2: 1` (lo mira el portero). Todo lo demás reusa las funciones del portero (`admin_accion`,
`permitido`, `lanzamientos.pendientes / decidir`, `_auditar`…). Sin `R2_CUENTAS_DUENA=1`, todo `/coordinador` da 404.

**«Jugando ahora» y el estado de cada servidor** salen SÓLO de dos fuentes que ya existen y no tocan los juegos:
- la presencia que ya lee `social.py` (`R2_PRESENCIA`, hoy R2Beat): cuántos contó el juego en los últimos 20 s;
- el `/salud` de cada servidor por la red de adentro (`R2_PANEL_SALUD`, ej. GunBound: `{"ok": true, "en_linea": n}`),
  con caché de 15 s y 2 s de espera.

Sin fuente, la tarjeta dice «sin datos» y **no** muestra un número. Una fuente que no contesta: «Sin respuesta».

**El arte de los juegos** (`fondo-r2beat.jpg`, `r2beat-logo.png`, `fondo-gunbound.jpg`, `eda-fondo.jpg`,
`wolf-team-portada.jpg`, los nombres del prototipo) **no está en el repo**: es arte de cada juego (el de GunBound y Wolf
Team es de Softnyx, y GunBound se publicó «sin arte de Softnyx»). El panel lo busca en `R2_PANEL_ARTE` (por omisión
`panel_arte/` al lado de `portero.db`; en el contenedor, `/datos/panel_arte/`); si no está, la tarjeta usa el color del
juego. En el repo sólo van el logo de Eñeños Team y las fuentes (OFL / Apache). Los nombres y colores salen de
`juegos.json` (campos opcionales nuevos `corto` y `panel`).

## 4 · Variables nuevas

| variable | en | qué |
|---|---|---|
| `R2_PANEL_URL` | `cuentas` | la lista blanca de destinos: `https://coordinador.xn--eeos-gqab.link` (coma entre varios). Vacía = nadie entra |
| `R2_PANEL_SALUD` | `cuentas` | `gunbound=http://gunbound:8371/salud;gunbound-prueba=http://gunbound-prueba:9371/gunbound-prueba/salud` (si están en la misma red de Docker) |
| `R2_PANEL_ARTE` | `cuentas` | opcional: otra carpeta para el arte |
| `R2_JUEGOS_CATALOGO` | `cuentas` | opcional: otro `juegos.json` (la imagen trae el del repo en `/app/juegos.json`) |
| `WEB_COORDINADOR_NOMBRE` | `web` (Caddy) | `coordinador.xn--eeos-gqab.link` |

## 5 · Para publicarlo (⛔ NO hecho: sólo cuando Benja lo pida)

1. **DNS** (Cloudflare): un registro `coordinador` → la IP del VPS donde corre `web`/`cuentas` (hoy el de USA),
   **sin nube** (gris) como `auth`, para que Caddy saque el certificado solo. (Con nube naranja también anda, pero
   entonces hay que mirar que Cloudflare no guarde `/api/*` en caché: el panel ya manda `no-store`.)
2. **Imagen `cuentas`**: rearmarla desde este repo (`docker compose build cuentas` o `publicar_imagenes.sh`): ahora
   trae `servidor/coordinador.py`, `servidor/panel/` y `juegos.json`.
3. **Imagen `web`** (la arma el repo del R2Beat 2013 con el `Caddyfile` de ESTE repo): rearmarla para que tome el
   bloque nuevo `{$WEB_COORDINADOR_NOMBRE}` y los 404 de `/cuentas/coordinador` en los otros dos nombres.
   Antes de recargar: `caddy validate --config /etc/caddy/Caddyfile` dentro del contenedor nuevo
   (⚠ un Caddyfile roto tira también la CDN y auth).
4. **`.env` del VPS**: `R2_PANEL_URL=https://coordinador.xn--eeos-gqab.link`,
   `WEB_COORDINADOR_NOMBRE=coordinador.xn--eeos-gqab.link` y, si GunBound está en la misma red,
   `R2_PANEL_SALUD=…` (ver §4). No hace falta tocar Google ni Discord: la vuelta sigue siendo la de auth.
5. **El arte**: copiar los 5 archivos del prototipo (`assets/`) al volumen `cuentas_datos` en `panel_arte/`
   (dueño uid 10013).
6. **Los roles**: que cada admin/moderador tenga Discord o Google **vinculado** desde el launcher (si no, ve «no
   vinculada»); revisar `moderadores.txt` y, si hace falta, asignar juegos desde el panel.
7. `docker compose up -d cuentas web` (recrea los dos; `cuentas` no corta partidas de nadie: los pases ya dados siguen
   valiendo). Probar: entrar con Discord, un moderador con un juego, y un Discord sin vincular.

## 6 · Lo que falta (fases B, C y D)

- **Fase B — adentro de cada juego (PROD/TEST)**: resumen, conectados, salas, fichas de jugador y sus personajes,
  sanciones dentro del juego (mute / echar / ban con tiempo), alertas, gráficos. Pide que cada juego exponga su API
  interna según su `enenos.json` (`capacidades`) — hoy GunBound sólo tiene `/salud`.
- **Fase C — contenido**: el contenido dinámico del launcher (asistencia, ruleta, avisos), cambiar la fecha de un
  lanzamiento desde el panel (hoy: `config/lanzamientos.json` a mano), Novedades, cupones, tira, avisos a todos.
- **Fase D — la red entera**: suspender / reactivar una cuenta en toda la red desde el panel (hoy por consola), la
  auditoría completa con filtros, el botón «Generar backup» (sólo admin, ítem 3 de PENDIENTES), «Conectar un juego»,
  la paleta Ctrl+K y las notificaciones.
