# La topología en contenedores — «Cuenta Eñeños» + un contenedor por juego

> 📦 **Copiado al Coordinador el 19-nov-2026** desde el repo del R2Beat 2013 (rama `claude/topologia-docker-99488b`),
> sin su historial. Lo que nombra del JUEGO (`juego.Dockerfile`, `web.Dockerfile`, `servidor/api_web.py`, `servidor/pase.py`,
> `datos.db`, el panel viejo…) sigue en ese repo. Las rutas `servidor/`, `pruebas/` y `herramientas/contenedores/` de acá
> son las mismas que allá.

> **14-nov-2026 · ETAPA 1 ARMADA Y PROBADA EN LOCAL (WSL) · ⛔ NADA EN PROD.**
> Pedido de Eñeños: cada juego en su contenedor de Docker, y un servicio central —**Cuenta Eñeños**— que sea el DUEÑO de
> las cuentas (usuario, contraseña, uid). El launcher le habla sólo a ese servicio, recibe un **pase firmado** y con ese
> pase entra a cualquier juego; cada juego comprueba la firma **solo**. Y todo tiene que poder **mudarse de máquina**.
>
> Archivos: `herramientas/contenedores/` · prueba: `pruebas/probar_contenedores.py` (parte A en el banco; parte B con
> `--docker`, dentro del WSL) · la semilla: `documentacion/PORTERO_CUENTAS.md`.

## 0 · En una pantalla

| | |
|---|---|
| **Qué quedó** | dos imágenes (`r2beat2013-juego`, `enenos-cuentas`), un `docker-compose.yml`, una herramienta de mudanza (`mudanza.py`) y la prueba. Levantan con `docker compose up`, en esta PC, dentro del WSL |
| **Qué cambia para el jugador** | **nada todavía.** El servicio de cuentas es el portero de hoy, tal cual. El juego sigue comprobando la contraseña él mismo |
| **Qué se tocó del server** | dos archivos, sólo para poder configurarlos desde afuera: `portero.py` y `api_web.py` aceptan `R2_PORTERO_HOST` / `R2_PORTERO_PROXIES` / `R2_API_HOST` / `R2_API_PROXIES`. **Sin esas variables se comportan igual que hoy** (lo comprueba la parte A de la prueba). No están en prod |
| **Lo que falta** | las etapas 2 a 5 de la mudanza de cuentas (§4): que R2Beat acepte el pase y que Cuenta Eñeños pase a ser la dueña. Están diseñadas acá, **no construidas** |
| **Lo que decide Eñeños** | qué va en qué máquina, y si prod entra a Docker (§8 y §9) |

## 1 · El dibujo

```
                         ┌────────────────────────────────────────────┐
                         │                LAUNCHER                    │
                         └───────┬───────────────────────┬────────────┘
              1· usuario y clave │                       │ 3· el pase (y después, el juego por TCP)
                 2· «dame un pase para <juego>»          │
                                 ▼                       │
      ┌──────────────────────────────────────┐           │
      │  CUENTA EÑEÑOS  (contenedor)         │           │
      │  dueña de: usuario · clave · uid     │           │
      │  aprobados y baneos por juego        │           │
      │  la CLAVE que firma los pases        │           │
      │  volumen: cuentas_datos              │           │
      └───────────────┬──────────────────────┘           │
                      │ clave PÚBLICA (JWKS): cada juego  │
                      │ la baja una vez y la guarda       │
          ┌───────────┴──────────────┬────────────────────┼─────────────────┐
          ▼                          ▼                    ▼                 ▼
  ┌────────────────┐        ┌────────────────┐    ┌────────────────┐   ┌──────────┐
  │ R2BEAT 2013    │        │ EDA            │    │ GunBound, …    │   │  (otro)  │
  │ (contenedor)   │        │ (contenedor,   │    │ (más adelante) │   │          │
  │ lo suyo, atado │        │  otro repo,    │    │                │   │          │
  │ al uid         │        │  otro VPS)     │    │                │   │          │
  │ volumen:       │        │                │    │                │   │          │
  │ r2beat2013_    │        │ comprueba el   │    │                │   │          │
  │ datos          │        │ pase SOLO      │    │                │   │          │
  └───────┬────────┘        └───────┬────────┘    └────────────────┘   └──────────┘
          │  avisos de eventos (ETAPA FUTURA, no construida)
          └──────────────┬──────────┘
                         ▼
                 ┌───────────────┐        ┌──────────────────┐
                 │ COLA DE AVISOS│ ─────▶ │  BOT DE DISCORD  │
                 └───────────────┘        └──────────────────┘
```

Las tres reglas del dibujo:

1. **El launcher habla con Cuenta Eñeños; los juegos NO.** Un juego nunca llama al servicio de cuentas mientras se
   juega: sólo necesita su clave pública, que guarda en su disco. Por eso un juego caído no afecta al login, y el servicio
   de cuentas caído no saca a nadie que ya esté jugando.
2. **Cada caja es un contenedor con UN volumen.** La imagen es el programa; el volumen es lo que no se puede volver a
   construir. Mudar una caja es llevar su volumen y volver a levantar su imagen (§5).
3. **Ninguna caja sabe en qué máquina está la otra.** Lo que une las piezas son nombres de dominio y variables del
   `.env`, no IPs escritas en el código.

## 2 · Lo que medí del server de hoy (medido, no deducido)

Todo esto salió de levantar el server dentro del contenedor, con el disco en **sólo lectura** salvo su volumen (así, lo
que escribiera en otro lado habría reventado).

### Los puertos (preguntado adentro del contenedor, en `/proc/net/tcp`)

| puerto | qué | hacia dónde se abre |
|---|---|---|
| 48004 | el login (`LoginServer`): el launcher y el exe | internet |
| 48005, 48015, 48025, 48035, 48045, 48055, 48065, 48075 | los 8 canales: Principiante, Novato, Novato Estrella, Estrella, Novato Luna, Luna, Novato Sol, Sol | internet |
| 48085 · 48095 | Libre · Sala de Charla | internet |
| 48190 | la API (web, panel, launcher) | **sólo el proxy** de la máquina |
| 48195 | el portero (hoy) / Cuenta Eñeños | **sólo el proxy** |

Son **12 del juego y 1 de cuentas**, y ninguno más. ⚠ Los puertos de los canales **no se pueden renumerar** al
publicarlos: el cliente los aprende del propio server (en el `FF02`), así que el número de adentro y el de afuera tienen
que ser el mismo.

### Los archivos de estado

| archivo | quién lo escribe | variable | ¿viaja en una mudanza? |
|---|---|---|---|
| `datos.db` (+ `-wal`, `-shm`) | el juego | `R2_BASE` | **sí** (copia de SQLite, no `cp`) |
| `panel.db` (+ `-wal`, `-shm`) | el panel (chat, IPs, auditoría) | `R2_PANEL_DB` (por omisión, al lado de `datos.db`) | sí |
| `sesiones.json` | el juego, en cada login del launcher | `R2_SESIONES` | sí (los que están jugando no tienen que volver a entrar) |
| `status.json` | el juego, cada 3 s | `R2_STATUS` | no: se rehace solo |
| `servidor.log` + uno por cada arranque | el juego | `R2_LOG` | no por omisión (`--todo` los lleva) |
| `respaldos/` | el respaldo diario de las 04:00 | `R2_RESPALDOS` | no por omisión |
| `gm.txt` · `admin.txt` · `streamers.txt` | Eñeños a mano; `streamers.txt` también lo escribe el panel | `R2_GM_ARCHIVO` · `R2_ADMIN_ARCHIVO` · `R2_STREAMERS_ARCHIVO` | sí (van a `config/`) |
| `portero.db` (+ `-wal`, `-shm`) | cuentas: aprobados, baneos, sesiones, pases, auditoría | `R2_PORTERO_BASE` | **sí** |
| `portero_clave.json` | cuentas, la primera vez | `R2_PORTERO_CLAVE` | **SÍ, es lo más importante** (§5) |
| `moderadores.txt` · `manifiestos/<juego>.json` | Eñeños a mano | `R2_MODERADOR_ARCHIVO` · `R2_PORTERO_MANIFIESTOS` | sí |

Fuera de su volumen el server **no escribe nada** (`docker diff` vacío, y un intento de escribir en `/app` rebota).

### Las rutas que son listas de candidatos (gana la primera que exista)

- `gm.txt`: `servidor/gm.txt`, después la raíz. `admin.txt`, `streamers.txt` y `moderadores.txt` lo siguen (van al lado).
  ⇒ En la imagen se fijan por variable a `/datos/config/`, así no dependen de dónde esté el código.
- la tabla del gacha: `servidor/tablas-cliente/`, `documentacion/tablas-cliente/`, `tablas-cliente/`.
- `music_lt.txt` (la dificultad de cada canción): cinco candidatos, el primero `R2Beat/rnr_script/`. ⚠ **Tampoco está
  en `servidor/`.** Sin él el picker anda igual, pero `notas.cargar_niveles` se queda sin niveles y el sorteo del
  cooperativo vuelve a ser **parejo**; el aviso sale en el log recién cuando alguien juega uno. La primera versión de la
  imagen no lo traía. ⇒ Ahora lo lleva en `R2Beat/rnr_script/`, el mismo lugar donde lo tiene prod, y la prueba (B1)
  comprueba que carga las 3.686 canciones con su nivel — y, tapando el archivo, que quedan 0.
- las tablas del catálogo: cinco candidatos, el último en `D:\R2Beat\…`. En la imagen gana el primero (`servidor/tablas-cliente/`).
- la tabla NIVEL↔EXP: se lee de `R2Beat/R2Beat.exe.pristino`. ⚠ **Tampoco está en `servidor/`.** Sin él no hay error:
  **todos quedan en nivel 1**. La imagen lo lleva (5 MB) y la prueba comprueba que el log diga «99 umbrales».

⇒ **`servidor/` no es del todo autosuficiente:** necesita esos dos archivos de `R2Beat/` (el exe prístino y
`music_lt.txt`), y los dos fallan **callados** si faltan. En prod están (la carpeta de allá tiene su `R2Beat/`); una
instalación nueva hecha copiando sólo `servidor/` arrancaría sin ellos y sin un error.

### Siete cosas que el contenedor destapó

1. ⛔ **La IP que el server le anuncia al cliente.** Sin `R2_PUBLIC_IP` anuncia la de la conexión, y adentro de un
   contenedor esa es una `172.x` que el jugador no puede alcanzar. ⇒ el compose **se niega a arrancar** sin
   `R2_IP_PUBLICA` en el `.env`.
2. ⛔ **`127.0.0.1` adentro del contenedor no es la máquina.** El portero y la API escuchaban fijos en `127.0.0.1`: en
   un contenedor eso los deja mudos. ⇒ `R2_PORTERO_HOST` / `R2_API_HOST` (en la imagen, `0.0.0.0`; el puerto se publica
   sólo hacia `127.0.0.1` de la máquina).
3. ⛔ **El freno de contraseñas frenaría a todos juntos.** El portero y la API le creen la IP del jugador
   (`CF-Connecting-IP`) sólo al vecino `127.0.0.1`. En un contenedor el proxy llega desde la red de Docker, así que
   todos los jugadores tendrían «la misma IP» y 8 claves malas de cualquiera bloquearían el login de todos por 15
   minutos. ⇒ `R2_PORTERO_PROXIES` / `R2_API_PROXIES`: la lista de vecinos a los que se les cree.
4. ⛔ **En un volumen nuevo, el login del juego quedaba ABIERTO.** `basedatos.sesion_valida` deja entrar a cualquiera
   si `sesiones.json` no existe (es a propósito, para lanzar el exe a mano). En prod el archivo existe; en un volumen
   recién creado, no. ⇒ la imagen arranca con `arranque_juego.py`, que lo crea vacío. Probado con su control: sin el
   archivo, un `vcode` inventado entra.
5. ⚠ **El volumen del juego no se puede montar en sólo lectura en cuentas.** SQLite en WAL necesita abrir el `-shm` de
   al lado: con `:ro`, si el juego se apagó limpio, el portero no puede ni abrir la base («unable to open database
   file»). La protección sigue siendo la del código (`mode=ro` + `query_only`).
6. ⚠ **Sobre una base vacía, cuentas no arranca.** El juego recién crea la tabla `users` con el primer login, y el
   portero se cae al arrancar si no la encuentra. Docker lo reintenta solo (medido: 3 reinicios). Sólo pasa en una
   instalación de cero; es un síntoma de que hoy cuentas depende del archivo del juego (lo saca la etapa 3).
7. ⚠ **Sin `init`, el contenedor tarda 10 s en apagarse** (Python, como proceso 1, ignora el aviso y Docker lo mata).
   Con `init: true` se apaga al instante, igual que con systemd.

Y dos de la red de Docker: desde la misma máquina el juego ve al jugador con la IP de la puerta de Docker (`172.x`), no
la real; y el proxy de Docker **acepta** una conexión aunque adentro todavía no escuche nadie (un «¿abre el puerto?» de
afuera no dice si el server está listo). Con la variante de red de la máquina (§8) no pasa ninguna de las dos.

## 3 · Quién es dueño de cada dato

| dato | hoy | destino |
|---|---|---|
| usuario, contraseña (`users.username`, `users.pass_hash`) | **R2Beat** (`datos.db`). El portero los lee | **Cuenta Eñeños** (`cuentas.db`, su volumen) |
| el **uid** (el número de cuenta, la identidad en todos los juegos) | R2Beat lo inventa al registrar (`basedatos.cuenta_crear`) | **Cuenta Eñeños** lo asigna, y **no cambia nunca** |
| «esta cuenta puede entrar a tal juego» (aprobados) y baneos por juego | el portero (`portero.db`) | Cuenta Eñeños |
| un ban de toda la cuenta | no existe como tal: hoy es el prefijo `BANNED:` en el `pass_hash` de R2Beat | Cuenta Eñeños (un estado de la cuenta) |
| la clave privada que firma los pases | el portero (`portero_clave.json`) | Cuenta Eñeños. ⛔ No sale de su volumen |
| la sesión del launcher (30 días) | el portero (`portero.db`) | Cuenta Eñeños |
| personajes, ropa, monedas, EXP, círculos, amigos, ranking, los 4 casilleros | R2Beat, por `usn` | **R2Beat**, atado al uid. No se mueve |
| el ban DENTRO de R2Beat, el mute, los GM, el chat y las IP del panel | R2Beat | R2Beat |
| el ticket con el que el exe entra (`vcode`, `sesiones.json`) | R2Beat | R2Beat (cada juego da su propio ticket corto, como EDA) |
| lo de EDA (personajes, progreso) | EDA, por `sub` = uid | EDA |
| el apodo que se muestra | R2Beat (el del casillero 1); viaja en el pase como `nombre` | cada juego el suyo; el pase lleva uno de cortesía |

La regla: **Cuenta Eñeños sabe QUIÉN sos y a QUÉ juegos podés entrar. Cada juego sabe QUÉ TENÉS en ese juego.**
Ningún juego guarda contraseñas, y Cuenta Eñeños no guarda nada de adentro de un juego.

## 4 · La mudanza de las cuentas, por etapas

> ⚠ **Nota (15-nov-2026):** este plan por etapas con «dos puertas» quedó reemplazado por **§20** (el día del reemplazo se copian las cuentas una sola vez a `cuentas.db` y Cuenta Eñeños pasa a ser la única dueña, sin convivencia con lo viejo). Se conserva acá como antecedente.

### Cómo es hoy el login de R2Beat (leído del código)

| paso | dónde | qué hace |
|---|---|---|
| el launcher entra | `lobby.handle_login`, el `FF01` con cuerpo de launcher (`[0][flag][usuario][sha256 en hex]`) | `basedatos.cuenta_verificar` compara el hash con `users.pass_hash` (por `almacen.cuenta_de`); si coincide, `sesion_abrir` sortea un `vcode` de 62 bits y lo anota en `sesiones.json` |
| el exe entra | el mismo `FF01`, con cuerpo de 12 bytes `[usn][vcode]` | `basedatos.sesion_valida`: mira `sesiones.json`. **Acá no hay contraseña.** Se repite en cada cambio de canal |
| registrarse | `FFF0` en el mismo puerto | `basedatos.cuenta_crear`: 3 a 16 letras o números, y el uid = el más alto de `users`, `chars` y `cuenta_personajes`, más 1 |
| los 4 personajes (launcher y web) | `FFF1`, `FFF2`, `FFF3`, `FFF5` → `cuenta_personajes.responder` | **cada orden trae usuario + hash** y se vuelve a comprobar con `cuenta_verificar` |
| el selector adentro del juego | `FFF6`…`FFFA`, y las monturas `FFFB` | con la sesión (`usn` + `vcode`), sin contraseña |
| la web y la API del launcher | `api_web.iniciar_sesion` (`/api/launcher/entrar`) | lee `users.pass_hash` directo; la sesión vive **en memoria** |
| el portero | `portero._validar` | lee `users.pass_hash` directo, en sólo lectura |
| cambiar la contraseña | **no hay autoservicio.** Sólo un ADMIN: `panel_admin._clave` y `herramientas/cambiar_clave.py` | un `UPDATE users SET pass_hash` |
| banear / fusionar cuentas | `panel_admin` · `almacen` | le ponen `BANNED:` o `FUSIONADA:` **delante del hash**. Y fusionar **cambia `users.uid`** (lo da vuelta a negativo) |

Tres cosas de esa tabla condicionan el plan:

- **El exe no manda contraseña**: entra con el ticket (`vcode`). O sea que la contraseña vive sólo entre el launcher
  y el server, y **el cliente del juego no se toca** en toda la mudanza.
- **El hash ES la contraseña**: `pass_hash` es SHA-256 sin sal, y el launcher manda ese mismo hash. Quien copie la
  tabla puede entrar como cualquiera sin descifrar nada. Mientras el juego la lea, no se puede guardar mejor.
- **El ban está escrito adentro del hash.** No se puede mudar la contraseña sin darle antes al ban su propio lugar.

### Las etapas

Cada una se puede dejar meses andando antes de la siguiente, y cada una tiene vuelta atrás.

**Etapa 0 — hoy, en prod.** El portero es un proceso de systemd al lado del juego y lee `datos.db` en sólo lectura.
R2Beat comprueba la contraseña él mismo. EDA ya entra con pase.

**Etapa 1 — lo mismo, en contenedores. ✅ Armada y probada en local.** Ningún cambio de comportamiento. El servicio de
cuentas sigue leyendo la base del juego, por un volumen compartido: **las dos piezas quedan atadas a la misma máquina**.
- *Vuelta atrás:* apagar los contenedores y volver a prender los servicios de systemd. Si se jugó sobre los
  contenedores, antes hay que traer el estado de vuelta (`mudanza.py exportar`).

**Etapa 2 — R2Beat ACEPTA el pase (sin dejar de aceptar la contraseña).** Las dos puertas abiertas a la vez.
- Cuenta Eñeños suma el juego `r2beat2013` (abierto a todas las cuentas, no sólo las aprobadas).
- R2Beat suma una entrada nueva: el launcher le manda el pase y el server comprueba **solo** la firma, `aud` =
  `r2beat2013`, el vencimiento y que no esté repetido (con `firma_ed25519.verificar`, que ya está en `servidor/`, y la
  clave pública guardada en su volumen). Si está bien, hace lo mismo que hoy tras `cuenta_verificar`: `sesion_abrir` y
  devolver `usn` + `vcode`. Lo mismo para `/api/launcher/entrar` y para `FFF1`…`FFF5`.
- Sale un launcher que entra una sola vez, a Cuenta Eñeños. Los launchers viejos siguen entrando con usuario y hash.
- Las cuentas **todavía viven en `datos.db`** y se siguen registrando en R2Beat.
- *Vuelta atrás:* una bandera en `ajustes.py` apaga la entrada nueva; la vieja nunca se cerró.

**Etapa 3 — Cuenta Eñeños pasa a ser la dueña.** Es el corte de verdad, y es el único con ventana de mantenimiento.
- Antes, en R2Beat: el ban sale del hash y pasa a una columna propia; `cuenta_personajes` deja de estar atada al
  nombre de usuario y pasa a estar atada al uid; y fusionar cuentas deja de cambiar `users.uid`.
- Cuenta Eñeños crea su `cuentas.db` y **copia** de `datos.db`: usuario, hash, uid, fecha, y el estado (baneada /
  fusionada, leído del prefijo). Al copiar puede guardar el hash envuelto en uno lento y con sal (`hashlib.scrypt`, que
  ya trae Python): nadie tiene que cambiar su clave y la tabla deja de servir para entrar si se filtra.
- **El registro** pasa a Cuenta Eñeños (`/cuentas/registrar`), que asigna el uid. R2Beat apaga `FFF0`.
- **El cambio de contraseña** pasa a Cuenta Eñeños: uno para el jugador (con la clave actual) y el reseteo del ADMIN.
  El botón «clave» del panel de R2Beat se quita o llama a ese.
- Cuenta Eñeños deja de leer `datos.db` ⇒ **recién acá las dos piezas pueden ir a máquinas distintas.**
- *Vuelta atrás:* `datos.db` no se modificó (sólo se copió de ella) y la puerta vieja sigue viva: se apaga la bandera y
  R2Beat vuelve a mandar. ⚠ Lo único que hay que devolver a mano son las cuentas que se registraron o cambiaron la clave
  mientras Cuenta Eñeños era la dueña; por eso conviene que R2Beat siga recibiendo una **copia** de esos cambios hasta
  cerrar la etapa 4.

**Etapa 4 — cerrar la puerta vieja.** Cuando ya no quedan launchers viejos: R2Beat deja de aceptar usuario + hash,
`users.pass_hash` deja de leerse (queda `users` como padrón local: uid y nombre, para el panel y `gm.txt`), y la web
entra con pase.
- *Vuelta atrás:* la bandera, mientras la columna `pass_hash` no se borre. Borrarla es el único paso sin vuelta, y no
  hay apuro en darlo.

**Etapa 5 — la cola de avisos y el bot de Discord.** No construida; el lugar previsto está en §10.

### Lo que hay que resolver antes de la etapa 3 (no está decidido)

- **Los números de cuenta.** Hoy R2Beat reserva, en el mismo rango que los uid de las cuentas, los `usn` de los
  personajes 2, 3 y 4 (`almacen.uids_usados` junta `chars` y `cuenta_personajes`). Si Cuenta Eñeños empieza a repartir
  uid por su lado, **van a chocar**. Hay que separar los rangos: o los personajes extra salen de un rango propio, o
  Cuenta Eñeños arranca desde un número alto.
- **El nombre de usuario dentro de R2Beat.** El pase no lo lleva (es privado: regla de `PORTERO_CUENTAS.md`). Pero el
  panel de R2Beat lo muestra a los ADMIN y `gm.txt` acepta logins. O el pase para R2Beat lo lleva, o los archivos pasan
  a usar sólo uid, o R2Beat se lo pregunta a Cuenta Eñeños por un canal interno (sólo el panel, nunca el juego).
- **Las cuentas con mayúsculas.** El login compara exacto (`Junior` ≠ `junior`, hay 60 pares). Cuenta Eñeños tiene que
  copiar eso tal cual.

## 5 · Cómo se muda cada pieza de una máquina a otra

### Qué es imagen y qué es volumen

| | qué es | cómo llega a la máquina nueva |
|---|---|---|
| **la imagen** | el programa y sus datos fijos (código, charts, tablas del cliente) | se **vuelve a construir** desde el repo (`docker compose build`), o viaja como archivo (`mudanza.py … --imagenes`) |
| **el volumen** | lo que no se puede volver a construir (§2) | `mudanza.py exportar` → copiar la carpeta por ssh → `mudanza.py importar` |
| **el `.env`** | dónde corre cada cosa en ESA máquina | se escribe de nuevo: es lo que cambia |

⚠ **Una imagen sirve para UNA arquitectura.** El VPS de prod es ARM (Ampere) y esta PC es x86: la imagen de acá no
arranca allá. El `Dockerfile` es el mismo para las dos (Python puro + Pillow); se construye en la máquina de destino, o
con `buildx` para las dos a la vez. `mudanza.py` se niega a cargar imágenes de otra arquitectura.

### Los pasos (una pieza o las dos)

```bash
# en la máquina VIEJA (con el server prendido: no lo frena ni lo corta)
python3 herramientas/contenedores/mudanza.py exportar --proyecto enenos --destino /root/mudanza
#   opciones:  --pieza cuentas   (una sola pieza)     --imagenes   (lleva también las imágenes)

# llevar /root/mudanza a la máquina NUEVA, por ssh (scp o rsync)

# en la máquina NUEVA: una carpeta con el docker-compose.yml y el .env de ESA máquina
python3 mudanza.py ver      --origen /root/mudanza          # qué trae, sin tocar nada
python3 mudanza.py importar --proyecto enenos --origen /root/mudanza
docker compose up -d
```

Y para salir de la instalación de hoy (una carpeta + systemd, sin Docker), el mismo paquete se arma leyendo la carpeta:

```bash
python3 mudanza.py desde-carpeta --pieza r2beat2013 --carpeta /opt/r2beat/game2013 --destino /root/mudanza
python3 mudanza.py desde-carpeta --pieza cuentas    --carpeta /opt/r2beat/game2013 --destino /root/mudanza \
                                 --manifiestos /opt/r2beat/portero/manifiestos
```

Sólo **lee** la carpeta (la prueba compara los archivos byte a byte antes y después). ⛔ Igual es «tocar la base de
prod» en el sentido de la regla: se hace cuando Eñeños lo pida.

Lo que hace `mudanza.py` y por qué no es un `cp`:
- cada `.db` se copia con la copia en caliente de SQLite (`backup()`), se abre, se le pide `integrity_check` y se
  cuentan sus filas. Copiar el archivo a mano con el WAL prendido trae una base vieja o ilegible (la prueba lo muestra);
- cada archivo viaja con su sha256 y se comprueba al llegar; un paquete con **un byte** cambiado se rechaza entero;
- no pisa un volumen que ya tiene una base (salvo `--pisar`);
- ⛔ lo que exporta es **secreto** (los hashes y la clave que firma): va a una carpeta fuera del repo, viaja por ssh y
  se borra al terminar.

### Qué cambia al mudar, pieza por pieza

| pieza | en su `.env` | afuera |
|---|---|---|
| **R2Beat 2013** | con `R2_NOMBRE_PUBLICO` puesto (§17), **nada**: el server saca su IP del DNS. `R2_IP_PUBLICA` (la IP nueva) queda como red de seguridad | ⚠ **la IP del juego está escrita en el launcher** (`GAME_HOST` en el de Python, `GAME_HOST_PROD` en el de Tauri) y se la pasa al exe (`test:<ip>`). Mudar el juego hoy pide **launcher nuevo**. ★ Medido (§11): el exe acepta un **NOMBRE** ahí. Con un nombre en el launcher, mudar el juego pasa a ser cambiar un registro de DNS y una variable |
| | | el proxy de la web (`/api/*`) tiene que apuntar a donde quedó la API |
| **Cuenta Eñeños** | `CUENTAS_PUBLICAR`, `CUENTAS_PROXIES` | la dirección `https://r2beatlatino.com/cuentas` está escrita en el launcher (`PORTERO_PROD`). **No hace falta cambiarla**: el Caddy de ese dominio reenvía `/cuentas/*` a donde esté el servicio. Mejor todavía, un dominio propio (§9) |
| | | ⛔ **la clave viaja con el volumen.** Si se pierde o se crea otra, todos los juegos rechazan los pases hasta bajar la clave pública nueva |
| **EDA** | (su repo) | su dominio ya va en su manifest, no en el launcher |

### Lo que comprobé (prueba B6)

Exporté con los dos servers prendidos, bajé todo, **borré las imágenes**, y en una carpeta limpia —sólo el compose, el
`.env` y el paquete— con **otro nombre de proyecto** importé y levanté. Las cuentas de prueba entraron con la misma
clave y el mismo uid; la sesión abierta en «la máquina vieja» siguió valiendo; y el pase nuevo verificó con la clave
pública **de antes**. El control: la misma carpeta **sin importar** no conoce la cuenta y firma con otra clave.

⚠ Lo que esa prueba **no** cubre: fue todo en la misma PC. No probé una mudanza entre dos máquinas de verdad, ni de x86
a ARM, ni con la base real (5.400 cuentas).

## 6 · Qué pasa cuando se cae cada pieza

| se cae… | hoy (etapas 0 y 1) | en el destino (etapa 3 en adelante) |
|---|---|---|
| **Cuenta Eñeños** | R2Beat **no se entera**: los que juegan siguen y entran jugadores nuevos (probado, B5). EDA: los que están adentro siguen; no entra nadie nuevo (no hay pase), y el botón de EDA del launcher queda apagado | **nadie puede INICIAR sesión en ningún juego.** Los que ya están jugando siguen, y en R2Beat siguen cambiando de canal (el `vcode` es del juego). Es la pieza que no se puede caer: por eso tiene que ser chica, sin dependencias, y con respaldo de su volumen |
| **R2Beat** (o en mantenimiento) | Cuenta Eñeños sigue dando pases y se reinicia sola (probado, B4). EDA no se entera. ⚠ Pero el servicio de cuentas necesita el **archivo** `datos.db`: si ese volumen no está, no arranca | Cuenta Eñeños ni lo nota |
| **EDA** | nada más se entera | igual |
| **el proxy (Caddy) de una máquina** | se cae lo que va por HTTPS en esa máquina: la web, la API, el servicio de cuentas, la descarga del cliente. El juego (TCP directo) sigue | igual: Cuenta Eñeños depende del proxy de SU máquina |
| **la máquina se reinicia** | los contenedores vuelven solos (`restart: unless-stopped`) y el estado está en los volúmenes | igual |
| **Docker se reinicia o se actualiza** | ⚠ **reinicia todos los contenedores, el juego incluido** (§8) | igual |
| **la cola de avisos o el bot** (futuro) | — | los juegos siguen; los avisos esperan en cada juego hasta que la cola vuelva |

Probado también: reiniciar el contenedor del juego **no** le hace volver a entrar a nadie por el launcher (el `vcode`
de antes sigue valiendo), y reiniciar cuentas **no** cierra las sesiones del launcher ni cambia la clave que firma.

## 7 · Pedidos para la sesión de EDA

EDA es otro repo (`C:\Game\EdaIS`): desde acá no se toca. Nada de esto es urgente; **la etapa 1 no le pide nada**: el
pase, el emisor y la clave son los mismos.

1. **La clave pública, con refresco.** Hoy la baja una vez. Pedido: guardarla en su volumen y, si llega un pase con un
   `kid` que no conoce, volver a bajarla (con un tope, por ejemplo una vez por minuto). Así se puede cambiar la clave o
   mudar el servicio de cuentas sin tocar EDA.
2. **La dirección del servicio de cuentas, por variable.** Ni la IP ni el dominio escritos en el código.
3. **El emisor (`iss`), por variable y como lista.** Hoy es `r2beat-portero`. Cuando el servicio pase a llamarse
   Cuenta Eñeños el emisor va a cambiar, y durante un tiempo tienen que valer los dos.
4. **La identidad es `sub` (el uid) y nada más.** `nombre` es de cortesía: puede cambiar o faltar. Nunca guardar nada
   atado al nombre.
5. **Confirmar** que guarda el `jti` 5 minutos y que no llama al servicio de cuentas mientras se juega (así es hoy).
6. **Su estado, mudable igual que éste:** todo en volúmenes, una forma de exportar e importar probada en una carpeta
   limpia, y sus dominios en el `.env`.
7. **Para la cola de avisos (futuro, no ahora):** que un aviso se anote primero en su disco y lo mande un hilo aparte,
   para que un aviso que no sale nunca frene al juego.
8. **Un ban de la cuenta entera** (cuando exista, etapa 3) no saca a quien ya está adentro de EDA: el pase es sólo para
   entrar. Si EDA quiere echar a un baneado en el momento, lo tiene que resolver de su lado.

## 8 · Los riesgos de llevar esto al VPS de prod

El VPS de prod: **1 núcleo ARM, 1.951 MB de RAM (~1,2 GB libres)**, 45 GB de disco, Ubuntu 24.04.

| riesgo | lo medido o sabido | qué hacer |
|---|---|---|
| **RAM** | medido acá (x86, sin jugadores): Docker solo, **~165 MB** (`dockerd` 95 + `containerd` 70); **+64 MB** por los 13 puertos publicados (un proceso por puerto); +22 MB por los dos contenedores. En total **~250 MB que hoy no se gastan**, un quinto de lo libre. Los servers pesan igual que sin Docker (juego 61 MB, cuentas 17 MB, vacíos) | con la red de la máquina se ahorran los 64 MB. Medir en el VPS nuevo antes |
| **CPU** | el programa corre igual de rápido (no hay máquina virtual). Lo que suma: Docker guardando lo que el server imprime | `R2_LOG_CONSOLA=0` (el log ya va a su archivo). El log de Docker tiene tope de 30 MB en el compose |
| ⛔ **iptables** | instalar Docker crea reglas de NAT, pone `FORWARD` en DROP y prende el reenvío. En la nube de Oracle la máquina ya trae reglas propias guardadas | **no instalarlo con gente jugando.** Mirar las reglas antes y después. No correr `netfilter-persistent save` con Docker prendido |
| ⛔ **Docker reinicia el juego sin que nadie lo pida** | si el paquete de Docker se actualiza solo (`unattended-upgrades`), reinicia el servicio y **todos los contenedores**. Rompe la regla 2 de `CLAUDE.md` | `"live-restore": true` en `/etc/docker/daemon.json` y dejar los paquetes de Docker fuera de las actualizaciones automáticas |
| ⛔ **`docker compose up -d` reinicia lo que cambió** | si se reconstruyó la imagen del juego, un `up -d` «para cuentas» también recrea el juego | **siempre nombrar el servicio**: `docker compose up -d cuentas` |
| **los puertos publicados saltean el cortafuegos** | Docker los abre por su propia cadena, sin pasar por `INPUT` | la API y cuentas se publican sólo en `127.0.0.1` (así está en el compose) |
| **la IP del jugador** | con la red de Docker, desde la misma máquina se ve `172.x`. Desde afuera Docker debería conservarla: **no lo pude probar acá** | el panel banea y registra por IP: comprobarlo antes, o usar la red de la máquina |
| **la arquitectura** | prod es ARM. ★ Medido (§14): la imagen arm64 se construye acá en 42 s y pasa la prueba entera, emulada | construirla acá con `buildx` y guardarla en el registro; el VPS sólo la baja |
| **la hora** | el contenedor usa la de `TZ`. Si no es la del VPS, las misiones del día y el respaldo de las 4 cambian de hora | mirar `timedatectl` en prod y poner eso en el `.env`. **No lo medí** |
| **el disco** | las dos imágenes, ~280 MB (comparten la base); el juego guarda un log por arranque y no los borra | prod ya llegó a 88 % de disco: revisar antes |

**La variante para prod: la red de la máquina** (`docker-compose.red-host.yml`, probada en B8). El juego abre sus
puertos directo en la máquina, como hoy: ve la IP real, no hay NAT ni un proceso por puerto, y la API y cuentas
escuchan sólo en `127.0.0.1`. Es lo más parecido a systemd con el programa empaquetado.

**Mi recomendación: no empezar por prod.** Ensayarlo entero en el VPS nuevo (3,3 GB, sin jugadores), con una copia de
la base, y medir ahí RAM, CPU e IP del jugador. Prod puede seguir con systemd todo el tiempo que haga falta: la
topología no necesita que R2Beat esté en Docker, necesita que **acepte el pase**. Lo único que conviene que nazca en
contenedor es Cuenta Eñeños.

## 9 · Lo que tiene que decidir Eñeños

> **Decidido el 14-nov (noche):** los nombres nuevos van bajo **`eñeños.link`** (en lo técnico, el punycode
> `xn--eeos-gqab.link`), no bajo `r2beatlatino.com` (punto 3) · las imágenes se guardan en **GitHub (`ghcr.io`),
> privadas** (punto 6) · **un repo por juego** y uno aparte para el «controlador» de la topología (§12) · y el OK para
> commitear la etapa 1 (punto 7). Siguen abiertos el 1, el 2, el 4 y el 5.

1. **Qué va en qué máquina.** Mi propuesta: R2Beat se queda donde está, con systemd; EDA se queda en USA; Cuenta
   Eñeños va al VPS nuevo **recién en la etapa 3** (antes no puede: lee el archivo de R2Beat).
2. **¿Prod entra a Docker?** No hace falta para la topología (§8). Si entra: con la red de la máquina y de madrugada.
3. **Un dominio propio para Cuenta Eñeños** (por ejemplo `cuentas.eñeños.link`), en vez de una ruta dentro del dominio
   de R2Beat. Así mudarla es cambiar un registro de DNS.
4. **El launcher:** la etapa 2 pide una versión nueva (entra una vez, a Cuenta Eñeños), y conviene que esa misma deje
   de traer la IP del juego escrita.
5. **Los números de cuenta** y **el nombre de usuario dentro de R2Beat** (§4, «lo que hay que resolver»).
6. **Las imágenes:** construirlas en cada máquina desde el repo, o guardarlas en un registro privado.
7. **El OK para commitear** lo de esta etapa (§10).

## 10 · Los archivos, y cómo se corre

```
herramientas/contenedores/
  juego.Dockerfile  (+ .dockerignore)      la imagen de R2Beat 2013: servidor/ + startserver.py + el exe prístino
                                           (la tabla de niveles) + music_lt.txt (la dificultad de las canciones)
  cuentas.Dockerfile (+ .dockerignore)     la imagen de cuentas: los 5 archivos del portero y nada del juego
  arranque_juego.py                        lo que corre el contenedor del juego (crea sesiones.json si falta)
  docker-compose.yml                       los dos servicios, sus volúmenes y sus puertos
  docker-compose.red-host.yml              la variante con la red de la máquina (§8)
  ejemplo.env                              las variables: copiar a `.env` y completar
  mudanza.py                               exportar · importar · ver · desde-carpeta
  sembrar_prueba.py                        cuentas de PRUEBA (corre adentro del contenedor)
pruebas/probar_contenedores.py             parte A (sin Docker, en el banco) · parte B (`--docker`)
```

```bash
# en esta PC, Docker vive DENTRO del WSL (Ubuntu-26.04), no en Windows
wsl -d Ubuntu-26.04 -u root
cd "<la carpeta del repo>/herramientas/contenedores"
cp ejemplo.env .env          # y poner R2_IP_PUBLICA=127.0.0.1
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f r2beat2013
docker compose down          # apaga; los volúmenes QUEDAN (con -v se borran: ⛔ es el estado)
```

La prueba completa (construye, levanta, apaga, muda; usa proyectos `enenos-prueba-*` y borra sólo esos):

```bash
python3 pruebas/probar_contenedores.py --docker
```

Las imágenes no traen bases, claves ni listas de cuentas: lo comprueba la prueba (B1) buscándolas adentro, con su
control. Lo que entra a cada imagen lo decide una lista blanca (`*.dockerignore`).

### El lugar previsto para la cola de avisos (no construida)

- un servicio más en el compose, `avisos`, con su volumen `avisos_datos`: una cola que sólo agrega (una tabla de
  SQLite: juego, tipo, datos, cuándo);
- los juegos le mandan cada aviso con una llave por juego (`AVISOS_URL`, `AVISOS_LLAVE` en su `.env`);
- el bot de Discord es otro contenedor que lee la cola desde donde quedó;
- la regla que la mantiene inofensiva: **el juego anota el aviso en su disco y lo manda después.** Si la cola está
  caída, el juego no se entera.

### Lo que NO se hizo en esta etapa

- nada de las etapas 2 a 5;
- Docker en prod, o cualquier cosa en prod;
- una mudanza entre dos máquinas de verdad, ni de x86 a ARM, ni con la base real;
- medir con jugadores (toda medición de RAM es con los servers vacíos);
- los contenedores de la web, de Caddy y del patch server: quedaron fuera a propósito (el pedido era el juego y
  cuentas). El compose publica la API y cuentas en `127.0.0.1`, para el Caddy que ya existe en la máquina.

## 11 · De dónde saca el cliente la dirección del server (medido el 14-nov)

Leído del exe prístino (`R2Beat.exe.pristino`) y **probado con el cliente de verdad** (`R2Beat_local.exe`) contra un
server de mentira que sólo anota por dónde llega cada conexión, y contra el server real con una base vacía. No se
parchó nada.

### El login: manda el argumento; la IP horneada es el plan B

| pregunta | respuesta | cómo se sabe |
|---|---|---|
| ¿cuál de las dos manda? | **el argumento `test:<host>`.** La IP horneada se usa sólo si el exe se abre sin ese argumento | código: `0x5C42FA` pregunta si hay host de argumento (`0x484DA0`); si hay, usa ése (`config+0x64D`), si no, la cadena horneada. **Probado:** sin argumento llegó por `192.168.1.50` (la horneada de `R2Beat_local.exe`); con `test:localhost` llegó por `127.0.0.1` |
| ¿acepta un NOMBRE? | **sí** | código: toda conexión del exe sale por una sola rutina (`0x67C400`), que primero prueba `gethostbyname` y recién después `inet_addr` (`0x67C250`). **Probado:** `test:localhost` y un nombre de 32 letras conectaron |
| ¿cuántas letras entran? | 32 probadas. La copia no tiene tope (`0x484D80` copia hasta el final) | no medí más de 32. `juego.xn--eeos-gqab.link` son 24: entra |
| ¿y si el nombre no existe? | **no conecta, y NO cae a la IP horneada** | probado: 45 s sin una sola conexión |
| ⚠ `test:127.0.0.1` | **no conecta** (`localhost` sí) | código: `0x5C4329` compara justo con `127.0.0.1` y se va. Probado: 45 s sin conexión. Es una trampa para probar en local, no para prod |
| el puerto del login | **fijo en 48004**, dentro del exe | `0x402FEB` y `0x5C43C8`. El tercer argumento no es el puerto de conexión |
| el `[SERVER] IP1` de un `.ini` | no cuenta: el exe lo lee y enseguida lo pisa | `0x5C42EE` … `0x5C431C` |

La IP horneada es una cadena de 16 bytes en el exe (15 letras): la del prístino es la del server original, y
`aplicar_parches.py` le pone la de la LAN. Como el launcher siempre pasa el argumento, **la horneada no hay que tocarla
para mudar el server**: sólo importa a quien abre el exe a mano.

### Los canales: los anuncia el server, y ahí entran 15 letras

Después del login el cliente pide la lista de canales (`FF02`) y conecta al canal que le toca. La dirección de esa
lista la pone el server (`lobby.handle_login`): **`R2_PUBLIC_IP` si está puesta; si no, la IP por la que ese cliente
llegó al login.** Los puertos son los suyos (48005, 48015, …).

| pregunta | respuesta | cómo se sabe |
|---|---|---|
| ¿puede ser un nombre? | **sí** | probado con el server real: anunciando `localhost` y `r2.localtest.me`, el cliente entró al canal Novato y pidió su ficha |
| ¿cuántas letras? | **15, ni una más** | el cliente guarda esa dirección en un campo de 16 bytes; el server ya lo sabe (`paquetes._entrada_canal`: `lenIP <=15`). **Probado:** con 18 letras el server revienta en cada `FF02` (`AssertionError`) y nadie pasa de la lista de canales |

⇒ **Un nombre de `eñeños.link` NO entra en los canales** (`xn--eeos-gqab.link` solo ya mide 18). Los canales se
anuncian con la IP, que siempre mide 15 o menos. No es un problema: es la variable que ya existe.

### Entonces, mudar R2Beat de máquina es…

1. en la máquina nueva, `R2_IP_PUBLICA` = su IP (lo que el server anuncia para los canales);
2. cambiar el registro de DNS del nombre del juego (por ejemplo `juego.eñeños.link`, **sin la nube de Cloudflare**:
   es TCP directo, como `eda.eñeños.link`);
3. nada en el exe, y nada en el launcher… **una vez que el launcher use el nombre en vez de la IP.** Ese cambio es una
   versión de launcher, una sola vez (los dos launchers traen hoy la IP escrita, y además la usan ellos mismos para
   el login).

Lo que queda por resolver, sin hacer:
- **Si `R2_IP_PUBLICA` se queda vacía**, el server anuncia la IP por la que llegó cada cliente, o sea la correcta sin
  configurar nada… pero sólo si la máquina ve su IP pública (el VPS de Oracle no la ve, y la red de Docker tampoco).
  Con la red de la máquina en un VPS que sí la ve, no haría falta ni la variable.
- ✅ **Hecho en local (§17):** el server **resuelve su propio nombre** (`R2_NOMBRE_PUBLICO`) y anuncia esa IP. Con
  eso, mudar es sólo el DNS.
- Mientras haya launchers viejos, siguen yendo a la IP de hoy. Se actualizan solos, pero la IP vieja tiene que seguir
  atendiendo (o reenviando) hasta que todos hayan cambiado.

Las dos sondas quedaron en `herramientas/sonda_direccion/` (abren la ventana del juego unos segundos y la cierran).

## 12 · El reparto en repos (propuesta — no se movió nada)

Eñeños, 14-nov: **un repo por juego** y un repo aparte para el **controlador** de la topología. Los de los juegos ya
existen (`r2beatlatino/R2beat-2013` y `r2beatlatino/EDA`, públicos). El del controlador también: **`r2beatlatino/enenos-atlas`**,
privado, rama `main`, por ahora sólo con su README (creado el 14-nov por orden de Eñeños). ⛔ Todavía no se le sube nada:
el reparto se hace cuando Eñeños vea esta propuesta. Las imágenes van a `ghcr.io`, privadas.

La regla del reparto: **el juego sabe construirse; el controlador sabe dónde corre cada cosa y cómo se muda.**

| archivo (hoy en `herramientas/contenedores/`) | va a | por qué |
|---|---|---|
| `juego.Dockerfile` + su `.dockerignore` | **el repo del juego** | describe qué archivos del juego entran a la imagen: cambia junto con el código |
| `arranque_juego.py` | el repo del juego | va adentro de la imagen |
| `sembrar_prueba.py` | el repo del juego | usa las funciones del server (`cuenta_crear`, `db_create_char`) |
| `cuentas.Dockerfile` + su `.dockerignore` | **por ahora, el repo del juego** | hoy el servicio de cuentas ES `servidor/portero.py`. Cuando sea dueño de las cuentas (etapa 3) se lleva su código y su Dockerfile a un repo propio |
| `docker-compose.yml`, `docker-compose.red-host.yml` | **el controlador** | dice qué piezas hay, sus volúmenes y sus puertos; no depende del código de ningún juego |
| `ejemplo.env` | el controlador | es el molde de «qué corre en ESTA máquina» |
| `mudanza.py` | el controlador | muda cualquier pieza; su tabla `PIEZAS` es la lista de piezas |
| `documentacion/TOPOLOGIA_CONTENEDORES.md` | el controlador | es la guía de la topología, no de un juego. En el repo del juego queda una hoja que apunte ahí |
| `pruebas/probar_contenedores.py` | **se parte en dos** | lo que mira UNA imagen (B1, B2, y la parte A de las variables) se queda con el juego; lo que cruza piezas (login + pase, apagar una y otra, mudanza, red de la máquina) va al controlador |
| el Caddy, el DNS, la cola de avisos (cuando existan) | el controlador | |

Lo que cambia al partir:

- **El compose deja de construir.** Hoy tiene `build:` apuntando al repo; en el controlador queda sólo
  `image: ghcr.io/r2beatlatino/<pieza>:<versión>`, y la versión de cada pieza va en el `.env`.
- **Subir una versión nueva** = el repo del juego construye las dos arquitecturas y las deja en el registro; en la
  máquina, `docker compose pull <pieza>` y `docker compose up -d <pieza>`. **Volver atrás** = poner la versión de antes.
  Es lo que pidió Eñeños: trabajar en local y que subir sea «bajar la imagen nueva».
- **El contrato entre los dos repos** pasa a ser lo que hoy está suelto en los comentarios: el volumen `/datos` y qué
  hay adentro, los nombres de las variables, los puertos y el chequeo de salud. Conviene escribirlo en la cabecera de
  cada Dockerfile; el controlador se fía de eso y de nada más.
- **Cada máquina necesita entrar al registro** (`docker login ghcr.io`) con una llave que sólo lea paquetes.
- ⚠ **Este repo no es el público.** `R2beat-2013` se arma desde acá con una herramienta que barre lo que no puede
  salir; **no la pude leer desde esta rama**, así que no sé qué de lo que la imagen necesita (los charts,
  `tablas-cliente/`, el exe prístino, `music_lt.txt`) está en el repo público. Hay que mirarlo antes de mover el
  Dockerfile: si algo de eso no está allá, la imagen **no se puede construir desde el repo público** y se construye
  desde este (ver §13).

## 13 · El exe prístino adentro de la imagen

La imagen del juego lleva `R2Beat/R2Beat.exe.pristino` (5,5 MB) porque el server lee de ahí la tabla NIVEL↔EXP: **99
números**. Es el ejecutable del juego original. Y no es lo único ajeno que lleva: también `music_lt.txt`, los 3.681
charts de `servidor/notes/` y las tablas de `servidor/tablas-cliente/`, todo sacado del cliente.

⇒ **La imagen del juego no puede ser pública, con o sin el exe.** Sacar el exe solo no la vuelve publicable.

| opción | qué es | qué cuesta |
|---|---|---|
| ✅ **A · imagen privada — LA ELEGIDA** (Eñeños, 14-nov: «lo que haya que subir, se sube nomás») | la imagen lleva todo, el exe incluido, y vive en `ghcr.io` como paquete **privado**. El exe NO va al repo público | **nada de código.** Cada máquina guarda una llave del registro (un secreto más, que se puede revocar). La imagen se construye desde donde estén los archivos (esta PC), no desde un repo público. ⚠ Tras la primera subida, **mirar que el paquete haya quedado privado**: un error ahí publica el exe |
| **B · el exe por volumen** (la alternativa, si algún día la imagen no puede llevarlo) | la imagen no lo trae; se copia a mano al volumen de cada máquina (`R2_EXE` ya permite apuntarlo) | alguien tiene que acordarse en cada máquina nueva, y `mudanza.py` tendría que llevarlo. Si falta, **no hay error: todos quedan en nivel 1**; habría que hacer que el arranque se niegue sin él. Y la imagen igual no queda publicable (los charts, las tablas) |
| **C · sacar el dato y dejar el exe afuera** | una herramienta lee los 99 números del exe y los deja en `servidor/tablas-cliente/` (y lo mismo con la dificultad de las canciones de `music_lt.txt`); el server lee eso primero | tocar el server (dos funciones: `cargar_umbrales_exp` y `cargar_niveles`), una prueba que compare el dato sacado con el del exe, y acordarse de regenerar el de las canciones cada vez que se importa música. A cambio, la imagen ya no trae ningún ejecutable y `servidor/` pasa a ser autosuficiente de verdad (hoy esos dos archivos fallan callados si faltan, §2). Va a prod como cualquier cambio del server |

**Cómo queda:** se va con **A**. El permiso para subir paquetes ya está en esta PC (`write:packages`), pero subir la
imagen es un paso que ordena Eñeños; no se hizo. **B** queda como alternativa: funciona, pero suma un paso manual que,
si se olvida, no avisa (antes de usarla habría que hacer que el arranque se niegue sin el exe). **C** sigue valiendo
como limpieza para más adelante: no por el registro, sino porque arregla el «falla callado» y deja `servidor/` completo.

Lo que A pide al subir por primera vez (para no olvidarlo):
1. construir las dos arquitecturas desde ESTE repo (el que tiene el exe, los charts y las tablas), no desde el público;
2. después de subir, **abrir el paquete en GitHub y comprobar que dice «Private»**; y que no quedó enlazado como
   público a `R2beat-2013`;
3. en cada máquina que la baje, una llave que sólo lea paquetes (`read:packages`), no la de esta PC.

## 14 · Las dos arquitecturas, medidas (14-nov, en esta PC)

Las de arm64 se construyeron y corrieron **emuladas** (`qemu-user-binfmt`, de los paquetes de Ubuntu, dentro del WSL).

| | amd64 (esta PC) | arm64 (emulada) |
|---|---|---|
| construir el juego, sin caché | 21 s | 42 s |
| construir cuentas, sin caché | 2 s | 2 s |
| lo que viaja al registro: juego · cuentas | 64 MB · 44 MB | 63 MB · 44 MB |
| lo que ocupa en el disco: juego · cuentas | 251 MB · 181 MB | 279 MB · 206 MB |
| Python de adentro | 3.13.18 | 3.13.18 |
| la prueba entera (`--docker --plataforma …`) | 98 chequeos en verde, 89 s | 100 en verde, 180 s |
| del `up` a escuchar en los 12 puertos | 3 s | 7 a 9 s |
| launcher + login + canal + ficha | 0,11 s | 0,9 s |
| entrar a cuentas + un pase firmado | 0,02 s | 0,07 s |

- **No hubo ninguna diferencia de comportamiento**: los mismos puertos, los mismos archivos, el mismo apagado (1,6 s
  con `init`), la misma mudanza. La de arm64 tiene dos chequeos más porque ahí se comprueba que la imagen corre de
  verdad como `aarch64` y que `mudanza.py` se niega a cargar imágenes de otra arquitectura (salvo
  `--otra-arquitectura`, que sólo sirve con emulación).
- En la **primera** corrida de arm64 un control dio rojo (el arranque de cuentas sobre una base vacía). Era de la
  prueba, no de ARM: esperaba mal, y con la PC cargada no llegaba. A mano anduvo; corregida la espera, la segunda
  corrida dio todo verde.
- ⚠ **Los tiempos de arm64 no son los de prod.** Emulado va entre 3 y 9 veces más lento que esta PC; el núcleo de
  prod rinde cerca de 0,40 de uno de acá. Estos números prueban que **funciona** en ARM, no cuánto tarda allá.
- ⚠ Bajar las imágenes de base costó muchos reintentos (la red de esta PC corta las descargas: «tls: bad record
  MAC»; la de arm64 entró al intento 23). No es de Docker ni de ARM.

```bash
# construir para las dos arquitecturas (sin subir nada)
docker buildx build --platform linux/arm64 -f herramientas/contenedores/juego.Dockerfile -t r2beat2013-juego:arm64 --load .
# la prueba entera contra las imágenes de ARM
python3 pruebas/probar_contenedores.py --docker --plataforma linux/arm64
```

## 15 · Las imágenes para el registro — ✅ SUBIDAS (15-nov, privadas, etiqueta `2026-11-14`)

> **Actualizado el 15-nov:** las imágenes ya se subieron a `ghcr.io` como paquetes **privados** con la etiqueta
> **`2026-11-14`**. Queda abajo el registro de cómo se prepararon en la madrugada y los comandos de verificación.

Eñeños ordenó subirlas (14-nov: «sube las imágenes»). En el primer intento de la madrugada, al ir a entrar al registro y subir, el
control de permisos de la sesión que hace este trabajo frenó la acción (la clasificó como comunicación hacia afuera
sin autorizar). No se forzó: no se ejecutó nada, no quedó ninguna credencial en el WSL y en `ghcr.io` no hay ningún
paquete. Falta que Eñeños lo corra él, o que habilite ese permiso en la sesión.

Lo que quedó hecho, todo en local:

| | |
|---|---|
| los nombres | **`ghcr.io/r2beatlatino/r2beat2013-juego`** y **`ghcr.io/r2beatlatino/enenos-cuentas`**, etiqueta **`2026-11-14`**. Sin `latest` (el script se niega) |
| construidas | las dos, cada una como UNA imagen con las dos arquitecturas (amd64 + arm64), desde este repo. Están en el Docker del WSL con esos nombres |
| sin enlace a ningún repo | las imágenes no traen ninguna etiqueta (`Labels: null`): no hay `org.opencontainers.image.source`, así GitHub no las enlaza a `R2beat-2013`. Tampoco viajan datos de la construcción (`--provenance=false --sbom=false`) |
| probadas | `probar_contenedores.py --docker --imagenes …` contra esa imagen de dos arquitecturas: amd64 98 chequeos en verde · arm64 100 en verde (emulada) |
| el script | `herramientas/contenedores/publicar_imagenes.sh` con tres órdenes: `construir` (hecho), `subir`, `bajar-y-probar` |

`r2beatlatino` en GitHub es una cuenta de **usuario**, no una organización: los paquetes quedan en
`github.com/r2beatlatino?tab=packages`, y se consultan con `/user/packages/…`.

### Lo que falta, en orden (son cuatro comandos)

```bash
# 1 · entrar al registro, desde Git Bash de Windows (el token no se muestra ni se guarda en ningún archivo)
gh auth token | wsl -d Ubuntu-26.04 -u root -- docker login ghcr.io -u r2beatlatino --password-stdin

# 2 · subir (dentro del WSL, parado en la raíz de este repo). Reintenta solo si la red corta
bash herramientas/contenedores/publicar_imagenes.sh subir 2026-11-14

# 3 · desde Windows: cada paquete tiene que decir "private" y repo = null
gh api /user/packages/container/r2beat2013-juego --jq '{name, visibility, repo: .repository.full_name}'
gh api /user/packages/container/enenos-cuentas   --jq '{name, visibility, repo: .repository.full_name}'

# 4 · bajar cada una POR SU DIGEST y correr la prueba contra lo bajado, en las dos arquitecturas; y salir
bash herramientas/contenedores/publicar_imagenes.sh bajar-y-probar 2026-11-14
wsl -d Ubuntu-26.04 -u root -- docker logout ghcr.io
```

- `subir` imprime el digest del índice y el de cada arquitectura: **son los que hay que anotar acá** (hoy no existen).
- `bajar-y-probar` primero **borra de esta máquina** todo nombre que apunte a lo construido acá y recién después baja:
  lo que prueba es lo que quedó en el registro.
- ⚠ Si el paso 3 dice `public`, o muestra un repo: **borrar el paquete** antes de seguir (lleva el exe del juego).
- ⚠ La red de esta PC corta las descargas de Docker; con las subidas puede pasar lo mismo. Si `subir` no entra tras
  sus 15 intentos lo dice y sale con error: no darlo por subido.

El nombre del juego ya existe: **`juego.xn--eeos-gqab.link`** → `161.153.192.100`, sin la nube, TTL 300 (lo creó la
sesión coordinadora el 14-nov a las 23:55). Todavía no lo usa nadie: los launchers siguen con la IP escrita.

## 16 · ¿Se puede pasar de 15 letras en la dirección de los canales? (investigado, **sin parchar nada**)

Pregunta de Eñeños: si el exe «se puede parchar» por la dll para que la dirección de los canales acepte más de 15
letras (y así poner ahí un nombre de `eñeños.link`).

### Primero, con franqueza: **no hace falta**

El nombre en los canales **no aporta nada para mudar de máquina**. Lo que el jugador necesita que sea un nombre es la
dirección del **login**, y ésa ya lo acepta (§11). La de los canales la anuncia el server **en cada login**, así que
basta con que el server sepa cuál es su IP… y hay una forma de que la sepa sin tocar el cliente (la opción 0 de abajo).

### Dónde vive el tope (leído del exe prístino)

- Cada canal es una ficha de **56 bytes** dentro de una lista (`std::vector`, en el objeto de `[0x9314AC]`, +0x12F8):
  puerto en +2, **la dirección en +8 (16 bytes)**, el nombre del canal (`std::string`) en +0x18, la categoría en +0x34.
- **La escriben dos funciones** (`0x4A8D80` y `0x4A9020`, llamadas desde el manejador del LoginServer, en `0x5C4694` y `0x5C46F8`),
  cada una en dos caminos (canal nuevo y canal que ya estaba): cuatro copias en total, y **ninguna mira el largo**
  (copian hasta el cero). Con más de 15 letras pisan lo que viene después: primero los 4 bytes con los que empieza el
  `std::string` del nombre y después su texto.
- **La lee UN solo sitio como dirección**: `0x4A6770`, que tiene **un único llamador** (`0x5C4E4E`), y de ahí va
  derecho a conectar (`0x67C400`). Pero la ficha entera se copia de a 56 bytes en 5 sitios más, y la lista se recorre
  en 14.
- El server ya frena antes: `paquetes._entrada_canal` revienta con más de 15 (`lenIP <=15`).

### Las opciones

| opción | qué es | qué cuesta | qué arriesga |
|---|---|---|---|
| ✅ **0 · no tocar el cliente** — LA ELEGIDA (Eñeños, 14-nov: «adelante») y **hecha en local, §17** | el server averigua su IP **resolviendo el nombre** que se le pone en `R2_PUBLIC_IP` (`juego.xn--eeos-gqab.link`) y anuncia la IP, que siempre mide 15 o menos | unas 10 líneas en `lobby.py` (resolver al arrancar y cada tanto; si el DNS falla, lo de hoy). Va con una subida del server | casi nada en el cliente: recibe una IP, como hoy. ⚠ Durante un cambio de DNS, el server VIEJO empezaría a anunciar la IP NUEVA: hay que decidir si eso se quiere (manda a todos a la máquina nueva) o si en la mudanza se fija la IP a mano |
| **0-bis · ni siquiera eso** | dejar `R2_PUBLIC_IP` vacía: el server anuncia la IP por la que llegó cada cliente, que es la que su propio DNS le dio para el login | nada | sólo sirve si la máquina ve su IP pública (con la red de la máquina, §8). El VPS de Oracle no la ve, y la red de Docker tampoco: ahí hace falta la opción 0 |
| **1 · un alias corto que la dll expande** | el server anuncia algo corto con una marca (`~juego`, 6 letras) y la dll, al resolver, lo cambia por el nombre largo. El gancho va en la tabla de importaciones (`gethostbyname`, casilla `0x873474`): no se escribe ni una instrucción del exe, igual que el gancho de `Sleep` que la dll ya tiene | unas 40 líneas en la dll y una subida de cdn. La regla alias → nombre queda escrita en la dll | **el orden de la subida:** primero la dll a TODOS, después el server; un cliente con la dll vieja recibe `~juego`, no lo resuelve y no entra a ningún canal. Y quien abra el exe sin nuestra dll queda afuera. `gethostbyname` tiene 4 llamadores (3 son para averiguar el nombre de la propia PC): el gancho sólo puede tocar lo que traiga la marca |
| **2 · agrandar el campo** | que la ficha del canal tenga más de 16 bytes para la dirección | **no es un parche, es una cirugía:** los 56 bytes están horneados en el código de la lista (la cuenta de elementos divide por 56, el avance suma 56, las copias mueven 56) y los corrimientos +0x18, +0x34 y +0x36 en todos los que la usan: 4 escritores, 5 copias, 14 recorridos | altísimo. Un sitio sin tocar corrompe la lista de canales en silencio. **No la recomiendo** |
| **2-bis · guardar la dirección larga aparte** | la dll intercepta a los escritores (`0x4A8D80`, `0x4A9020`), guarda la dirección larga en una tabla suya y deja en la ficha una clave corta; e intercepta el único lector (`0x4A6770`) para devolver la larga | tres ganchos en la entrada de funciones del exe (la dll ya sabe hacerlos y comprueba los bytes de fábrica), más cambiar el tope del server | medio: los escritores copian sin tope, así que el gancho tiene que cortar ANTES de que copien; y es mucha maquinaria para lo mismo que logra la opción 1 con un gancho |

### En una línea

**Poder, se puede (la opción 1 es limpia y la dll ya tiene las dos herramientas que necesita). Convenir, no:** la
opción 0 da lo mismo —mudar el juego cambiando el DNS— tocando 10 líneas del server y nada del cliente. Y agrandar el
campo de verdad (opción 2) no vale lo que arriesga.

Nada de esto se construyó: es lectura del exe. Lo único medido con el cliente es lo de §11 (un nombre de hasta 15
letras en los canales funciona; con 18 el server revienta antes de mandarlo).

## 17 · El nombre público: el server saca su IP del DNS (hecho en local el 15-nov · NO en prod)

Aprobado por Eñeños el 14-nov («adelante»): es la opción 0 de §16. Código: `servidor/nombre_publico.py` (nuevo), tres
líneas en `servidor/lobby.py` y las constantes en `servidor/ajustes.py`. Prueba: `pruebas/probar_nombre_publico.py`
(40 chequeos) y el paso B3b de `probar_contenedores.py`.

### Qué hace

Con **`R2_NOMBRE_PUBLICO=juego.xn--eeos-gqab.link`**, el server resuelve ese nombre y anuncia **esa IP** en la lista de
canales. Sin la variable no existe nada de esto: ni un hilo, ni una consulta, y los canales se anuncian como siempre.

El orden, de mayor a menor: **la IP del nombre** (si se adoptó) → **`R2_PUBLIC_IP`** → la IP por la que llegó el cliente.
O sea que `R2_PUBLIC_IP` pasa a ser la red de seguridad: lo que se anuncia mientras el DNS no contesta bien.

### La regla: el server sólo le cree al DNS si por esa IP se llega a ÉL

Antes de adoptar la IP que dio el DNS, el server se conecta a `<esa IP>:48004` y se manda un «eco» (`FFEC`) con un
desafío al azar. Sólo él puede contestarlo bien: la respuesta se arma con una ficha secreta que nace con el proceso y
no viaja nunca. Si la respuesta cierra, adopta la IP; si no, no. Con esa sola regla quedan resueltos los casos feos:

| pasa esto | qué anuncia el server |
|---|---|
| el DNS no contesta, o el nombre no existe | la última IP que comprobó; y si nunca comprobó ninguna, lo de siempre (`R2_PUBLIC_IP`) |
| el DNS devuelve algo raro: vacío, una IPv6, una IP privada o de la propia máquina | lo mismo: no la adopta |
| **mudanza, el server VIEJO**, cuando el nombre ya apunta al nuevo | **sigue anunciando la suya.** El eco no le vuelve, así que no adopta la IP nueva: nunca manda a sus jugadores a otra máquina por su cuenta. Lo deja escrito en el log |
| **mudanza, el server NUEVO**, prendido antes de cambiar el DNS | el nombre todavía apunta al viejo: no lo adopta y anuncia lo de siempre. Cuando el DNS cambia, lo adopta solo en la vuelta siguiente (30 s) |
| alguien rompe el registro (lo pone «con nube», o con otra IP) | el server sigue igual: no adopta una IP por la que no se llega a él |

⛔ **Nunca revienta un `FF02`:** lo que sale de ahí es una IPv4 escrita por Python (15 letras como mucho) o nada.

### Cada cuánto, y lo que cuesta

- **En el login no se resuelve nada**: se lee una variable (20.000 lecturas = 1 ms, medido).
- Un hilo aparte hace **una consulta de DNS y una conexión a sí mismo cada 300 s** (el TTL del registro). Mientras
  todavía no adoptó ninguna IP, cada 30 s.
- En el log deja una línea **sólo cuando algo cambia**, no una cada cinco minutos.

### Las variables

| variable | qué | por omisión |
|---|---|---|
| `R2_NOMBRE_PUBLICO` | el nombre del juego | vacío = no se usa |
| `R2_NOMBRE_PUBLICO_PRIVADAS=1` | acepta IPs privadas o de la propia máquina (una LAN, las pruebas) | no. ⛔ En prod, no |
| `R2_NOMBRE_PUBLICO_SIN_COMPROBAR=1` | le cree al DNS sin el eco | no. ⚠ Con esto el server viejo de una mudanza **sí** sigue al nombre, y un registro roto rompe la entrada a los canales |

En el compose ya están las tres (vacías); en `ejemplo.env`, las dos primeras.

### La mudanza, con esto

1. la máquina nueva se levanta con el mismo `R2_NOMBRE_PUBLICO` (y, si se quiere, su `R2_IP_PUBLICA` como red);
2. se cambia el registro del DNS;
3. en la vuelta siguiente (30 s, más lo que tarde el DNS) el server nuevo se reconoce y anuncia su IP. El viejo, si
   sigue prendido, sigue anunciando la suya hasta que se apague.

No hay que escribir la IP nueva en ningún lado, ni tocar el cliente, ni el launcher (una vez que use el nombre).

### ⚠ Lo que hay que medir antes de prod (no lo medí: no me conecté a ningún VPS)

**¿El VPS de prod puede conectarse a su propia IP pública?** En la nube de Oracle la máquina no tiene esa IP en su
placa (por eso existe `R2_PUBLIC_IP`), y el eco depende de que la red la deje salir y volver a entrar. Se mide con un
comando, allá: `nc -vz 161.153.192.100 48004`.
- Si puede: todo lo de arriba vale tal cual.
- Si **no** puede: el eco nunca vuelve, el server nunca adopta la IP del nombre y anuncia `R2_PUBLIC_IP`, **igual que
  hoy** (no se rompe nada, pero la función no hace nada). La salida es `R2_NOMBRE_PUBLICO_SIN_COMPROBAR=1`, sabiendo
  lo que se pierde.

Con la red de Docker pasa algo parecido: el eco sale del contenedor y tiene que volver por el puerto publicado. En la
prueba se midió con el nombre `localhost` DENTRO del contenedor, no con una IP pública de verdad.

### Lo probado

- `probar_nombre_publico.py`: sin la variable no pasa nada · 13 respuestas raras del DNS que no se adoptan · el DNS
  que falla · **el eco con sockets y con el `handle_login` de verdad** (se reconoce a sí mismo; a otro server, a uno
  que contesta «sí» a todo y a un puerto vacío, no) · la mudanza de los dos lados · que nunca revienta la lista de
  canales · que el login no consulta el DNS. Cada cosa con su control.
- `probar_contenedores.py` B3b, con el contenedor de verdad y `R2_IP_PUBLICA` puesta en una IP de mentira para ver
  quién manda: sin nombre anuncia la de la variable · con nombre anuncia la del DNS · IP privada sin permiso, nombre
  que no existe y nombre que apunta a OTRO contenedor: anuncia la de la variable y la lista de canales sale igual ·
  y con `SIN_COMPROBAR`, se cree la IP del otro contenedor (por eso existe el eco).

Al subir esto a prod **reinicia el juego** (`lobby.py`, `ajustes.py` y el módulo nuevo). Sin poner la variable, el
comportamiento no cambia en nada.

## 18 · El ensayo en el VPS efímero (15-nov-2026)

Eñeños pidió usar el VPS `103.90.160.237` como prueba de que el sistema se puede mudar. Ese VPS es **efímero** (dura
30 días o menos). **No es prod.**

| | |
|---|---|
| **máquina nueva (VPS)** | Ubuntu 26.04, `x86_64`, 4 núcleos, 3,4 GB de RAM, 19 GB libres. Sin Docker ni cortafuegos |
| **máquina vieja** | Docker del WSL de la PC de desarrollo: proyecto `enenos-viejo`, imágenes construidas del código de ese día y 3 cuentas inventadas (`prueba1`…`prueba3`) con clave sorteada (`prueba1` aprobada para EDA). **Ninguna cuenta real, nada de la base de prod** |
| **medido en el VPS** | los dos contenedores sanos a los 12 s · abiertos hacia afuera sólo el `48004` y los 10 puertos de canales · juego 51 MB de RAM, cuentas 16 MB · quedaron **2.557 MB libres** |

### Los pasos, tal como se hicieron

1. en la máquina vieja, con el server prendido: `mudanza.py exportar --proyecto enenos-viejo --destino … --imagenes`
   → paquete de 62 MB (`r2beat2013.tar` 450 KB, `cuentas.tar` 60 KB, `imagenes.tar` 61 MB);
2. en el VPS: `apt-get install docker.io docker-compose-v2` (Docker 29.1.3, Compose 2.40.3);
3. DNS nuevo: `ensayo.eñeños.link` (`ensayo.xn--eeos-gqab.link`) → `103.90.160.237`, sin la nube de Cloudflare, TTL 300;
4. copiar por `scp` el paquete, `docker-compose.yml` y `mudanza.py` a `/opt/enenos`, y escribir el `.env` de esa máquina
   (`R2_IP_PUBLICA=103.90.160.237`, `R2_NOMBRE_PUBLICO=ensayo.xn--eeos-gqab.link`, `JUEGO_PUBLICAR=0.0.0.0` y las dos imágenes);
5. `mudanza.py ver`, `mudanza.py importar --proyecto enenos --origen /root/mudanza --imagenes`, `docker compose up -d`;
6. borrar el paquete de las dos máquinas.

### `R2_NOMBRE_PUBLICO` con una IP pública de verdad

El log dijo: *«los canales se anuncian con 103.90.160.237 · comprobado: por esa IP se llega a este server»*. En **este**
VPS la máquina sí puede conectarse a su propia IP pública. ⚠ **Sigue sin medirse en el VPS de prod** (la nube de
Oracle), que es donde estaba la duda.

### Lo comprobado desde la PC de desarrollo, por internet (17 chequeos, todos bien, con sus controles)

- el nombre resuelve;
- `prueba1`, `prueba2` y `prueba3` entran por el launcher con la clave de la máquina vieja; con la clave mal o una
  cuenta que no existe, no entra;
- el login del juego da los 10 canales, anunciados con la IP del VPS; entra al canal Libre y recibe su ficha;
- el puerto de cuentas **no** se abre desde internet;
- por un túnel de `ssh`: la clave que firma los pases es la misma que en la máquina vieja, `prueba1` recibe su pase y
  verifica con la clave pública de antes, un pase con la firma tocada no verifica, y `prueba2` sigue sin pase.

### Lo que el ensayo NO cubrió

- no se usó la base real ni cuentas reales;
- no se probó con el cliente del juego de verdad ni con el launcher publicado (sólo con los clientes de la prueba);
- no están en contenedores la web, el servidor de parches y la CDN, ni Caddy con sus certificados;
- EDA no participó;
- fue de x86 a x86 (prod es ARM);
- las imágenes viajaron dentro del paquete, no se bajaron del registro (para eso hace falta una llave de sólo lectura en la máquina).

### Lo que destapó

- **`mudanza.py` buscaba `:local` aunque el conjunto usara otra etiqueta** (el conjunto corría con `:ensayo` en su `.env`
  y hubo que exportar `JUEGO_IMAGEN` / `CUENTAS_IMAGEN` a mano). Arreglado en `mudanza.py`: ahora busca en entorno,
  contenedor del proyecto, paquete con `--imagenes`, `.env` local y `:local`.
- **Endurecer el `ssh` del VPS** (que entre sólo con llave): pendiente, lo decide Eñeños.

### Dónde quedó y cómo desarmarlo

- El sistema sigue prendido en el VPS (`/opt/enenos`), con sus cuentas de prueba. Los guiones del ensayo están en
  `_trabajo/ensayo_migracion/` (fuera del repo): `1_maquina_vieja.sh`, `1b_exportar.sh`, `3_verificar.py`.
- Para desarmarlo: en el VPS `cd /opt/enenos && docker compose down -v`, y borrar el registro `ensayo` del DNS.

### El launcher y el juego de verdad contra el ensayo (15-nov, después)

Eñeños pidió probarlo con el launcher y el juego reales. Se abrió el launcher nuevo (rama `launcher-tauri`, gemelo LOCAL
apuntado a `ensayo.xn--eeos-gqab.link`) con `prueba1`, se apretó JUGAR AHORA y arrancó el cliente INSTALADO
(`C:\Game\R2beatTEST0\R2BeatMultiTest.exe`, el exe de prod).

- El launcher entró y la API del VPS le dio el personaje de la cuenta.
- Le pasó al exe **el nombre** (`test:ensayo.xn--eeos-gqab.link`, 25 letras), no un número.
- El exe de prod resolvió el nombre solo, hizo el login y llegó hasta el lobby de un canal: en el log del VPS quedó
  `usn=1` pidiendo la lista de salas y «Lobby asentado». A los 35 s seguía abierto.
- ⇒ Queda medido con el **exe de prod** lo que el 14-nov se había medido sólo con el de local: acepta un nombre.
- No hay foto del juego (la captura sacó lo que había adelante en la pantalla). No se entró a una sala ni se corrió.
- El launcher tocó tres archivos del cliente instalado (`d3d9_proxy.ini` y registros); se devolvieron como estaban.
- ⚠ En medio, un guion de esta PC pisó la clave de prueba y la clave pública de referencia; se les puso una clave nueva a
  las tres cuentas inventadas del VPS y se repuso la referencia comprobando su identificador. Los guiones ya no las pisan.

## 19 · El servidor de parches y la web en contenedores (15-nov-2026 · armado, SIN CORRER)

Las dos piezas que faltaban en `herramientas/contenedores/` para tener las cuatro en el mismo `docker-compose.yml`:
el **servidor de parches** (`parches`) y la **web + proxy Caddy** (`web`).

### Qué hace cada pieza nueva

| pieza | archivos en `herramientas/contenedores/` | qué lleva adentro | cómo sale hacia afuera |
|---|---|---|---|
| **`parches`** (`r2beat2013-parches`) | `parches.Dockerfile` (+ `.dockerignore`), `parches/arranque.py`, `parches/patchserver.py`, `parches/make_manifest.py` | `python:3.13-slim-bookworm`, usuario `r2` (`10013`), y los 3 `.py` (copia intacta de `_trabajo/parches_fuente/`). `arranque.py` arma `/tmp/config.json` (modo `0600`) desde las variables `PARCHES_*` y arranca `patchserver.py` | **no abre ningún puerto en la máquina**: escucha en `8080` sólo adentro de la red de Docker y sale por `web` (Caddy) |
| **`web`** (`r2beat2013-web`) | `web.Dockerfile` (+ `.dockerignore`), `Caddyfile` | construcción en 2 etapas: `node:22-bookworm-slim` corre `npm ci && npm run build` sobre `web/`, y la etapa final (`caddy:2-alpine`, usuario `r2` `10013`) lleva **sólo `dist/`** (en `/srv`) y el `Caddyfile` | publica **`80`** y **`443`** (TCP y UDP). Con un dominio en `WEB_NOMBRE` saca HTTPS solo; con `WEB_NOMBRE=:80` sirve HTTP liso |

### Cómo reparte las rutas `Caddyfile`

Un solo bloque `{$WEB_NOMBRE::80}` atiende todo bajo el mismo nombre (sin pedir un subdominio extra en el DNS ni
certificados separados, y andando igual con `:80` en local):

| ruta que pide el cliente | a dónde la manda Caddy | detalle |
|---|---|---|
| `/api/*` | `r2beat2013:48190` (`WEB_JUEGO_DESTINO`) | `handle /api/*`: conserva el prefijo `/api` porque `servidor/api_web.py` espera las rutas así |
| `/cuentas`, `/cuentas/*` | `cuentas:48195` (`WEB_CUENTAS_DESTINO`) | `handle @cuentas`: `servidor/portero.py` acepta las rutas con o sin `/cuentas` |
| `/parches/*` | `parches:8080` (`WEB_PARCHES_DESTINO`) | **`handle_path /parches/*`**: le quita `/parches` antes de pasarlo (`/parches/auth` → `/auth`, `/parches/manifest` → `/manifest`, `/parches/files/…` → `/files/…`). Así convive en el mismo dominio sin chocar con `/admin` de la web nueva |
| `/files/*` | `parches:8080` (`WEB_PARCHES_DESTINO`) | `handle /files/*`: pasa directo `/files/<release>/<archivo>`, por si `manifest.json` usa su `base` por omisión (`/files/<release>/`) en la raíz del dominio |
| todo lo demás (`/`, `/ranking/*`, `/admin/*`, …) | `/srv` (los estáticos de `web/dist/`) | `try_files {path} {path}/index.html {path}.html` + `file_server` |

### Las variables nuevas (`ejemplo.env` y `docker-compose.yml`)

| variable | pieza | por omisión | qué hace |
|---|---|---|---|
| `PARCHES_IMAGEN` | compose | `r2beat2013-parches:local` | nombre/etiqueta de la imagen del servidor de parches |
| `PARCHES_RELEASES_ORIGEN` | compose | `parches_releases` | volumen con nombre o ruta absoluta de la máquina donde están las releases del cliente |
| `PARCHES_HOST` | `parches` | `0.0.0.0` (en la imagen) | interfaz donde escucha `patchserver.py` adentro del contenedor (`config.json` → `listen`) |
| `PARCHES_PUERTO` | `parches` | `8080` | puerto interno de `patchserver.py` (`config.json` → `port`) |
| `PARCHES_BASE` | `parches` | `/juego/datos.db` | ruta a la base SQLite del juego que lee `/auth` (`config.json` → `clean_db`) |
| `PARCHES_STATUS` | `parches` | `/juego/status.json` | ruta al `status.json` del juego (`config.json` → `status_file`) |
| `PARCHES_RELEASES` | `parches` | `/releases` | carpeta de las releases adentro del contenedor (`config.json` → `releases_dir`) |
| `PARCHES_RELEASE_ACTIVA` | `parches` | vacío | nombre de la carpeta de la release activa (`config.json` → `current`) |
| `PARCHES_URL_ARCHIVOS` | `parches` | vacío | URL base de la CDN para los archivos del manifest (`file_base_url`); vacío = `/files/<release>/` |
| `PARCHES_LAUNCHER_VERSION` | `parches` | `0` | versión publicada del launcher para `/launcher/meta` (`launcher_version`) |
| `PARCHES_LAUNCHER_BIN` | `parches` | vacío | ruta al ejecutable del launcher dentro del contenedor para `/launcher/bin` (`launcher_bin`) |
| `PARCHES_LAUNCHER_URL` | `parches` | vacío | URL externa (CDN/GitHub) para bajar el launcher en `/launcher/meta` (`launcher_url`) |
| `PARCHES_TOKEN_TTL_SEG` | `parches` | `3600` | duración en segundos del token que entrega `/auth` (`token_ttl_sec`) |
| `PARCHES_CUOTA_TOKEN_MB` | `parches` | `1500` | tope de descarga en MB por token (`quota_mb_per_token`) |
| `PARCHES_CUOTA_IP_MB_HORA` | `parches` | `3000` | tope de descarga en MB por IP por hora (`per_ip_quota_mb_per_hour`) |
| `PARCHES_AUTH_IP_HORA` | `parches` | `30` | tope de intentos en `/auth` por IP por hora (`per_ip_auth_per_hour`) |
| `PARCHES_BAN_MINUTOS` | `parches` | `30` | minutos de bloqueo temporal al pasar las cuotas (`ban_minutes`) |
| `PARCHES_CLAVE_PANEL` | `parches` | vacío | `status_password` del panel viejo (`/status`, `/accounts`, `/admin/update`); vacío = panel apagado (503). ⛔ Nunca se imprime |
| `PARCHES_CLAVE_PANEL_ARCHIVO` | `parches` | vacío | ruta a un archivo con `status_password` (para secretos de Docker); se usa si `PARCHES_CLAVE_PANEL` está vacía |
| `WEB_IMAGEN` | compose | `r2beat2013-web:local` | nombre/etiqueta de la imagen de la web + Caddy |
| `WEB_NOMBRE` | `web` | `:80` | nombre del sitio (ej. `ensayo.xn--eeos-gqab.link` para HTTPS automático de Caddy, o `:80` para HTTP liso en local) |
| `WEB_PUBLICAR` | compose | `0.0.0.0` | IP de la máquina en la que se publican los puertos 80 y 443 |
| `WEB_JUEGO_DESTINO` | `web` | `r2beat2013:48190` | destino interno para `/api/*` |
| `WEB_CUENTAS_DESTINO` | `web` | `cuentas:48195` | destino interno para `/cuentas/*` |
| `WEB_PARCHES_DESTINO` | `web` | `parches:8080` | destino interno para `/parches/*` y `/files/*` |

### Qué es imagen, qué es volumen y qué pasa en una mudanza (`mudanza.py` no se toca)

| cosa | dónde vive | ¿va en `mudanza.py`? | cómo se muda o se rehace |
|---|---|---|---|
| código de `parches` y estáticos de `web/dist/` | **en cada imagen** (`r2beat2013-parches`, `r2beat2013-web`) | no (es programa) | se vuelve a construir desde el repo (`docker compose build`) o se baja del registro |
| **las releases del cliente** (`/releases`, varios GB) | volumen `parches_releases` o carpeta de la máquina en `PARCHES_RELEASES_ORIGEN` | **no** (meter GB en el `.tar` de `mudanza.py` sería lento e inútil) | se llevan aparte con **`rsync -aH`** (conservando los enlaces duros `cp -al` entre releases). Si falta `manifest.json`, se regenera con `docker compose exec parches python make_manifest.py /releases/<release>` |
| **los certificados TLS de Caddy** (`/data` en `web`) | volumen **`web_datos`** | **no hace falta** | **se rehacen solos:** cuando el DNS apunta a la máquina nueva, Caddy pide el certificado nuevo solo. El volumen existe para que **en la misma máquina** no los pida de nuevo en cada reinicio (Let's Encrypt bloquea tras pocos pedidos repetidos) |
| tokens y cuotas de `parches` (`TOKENS`, `IP_STATE`, `BANS`) | en memoria de `patchserver.py` | no | duran 30–60 min; al reiniciar el contenedor el launcher pide otro token en el próximo arranque |
| lectura de cuentas en `parches` (`/juego/datos.db`) | el volumen **`r2beat2013_datos`** del juego | ya lo muda la pieza `r2beat2013` | ⚠ igual que en `cuentas`, **no se puede montar `:ro`**: SQLite en WAL necesita abrir el `-shm` de al lado (medido en §2 punto 5 y B7), y además `patchserver.py` abre la base con `sqlite3.connect()` común |

### Qué pasa cuando se cae cada pieza nueva

| se cae… | qué sigue andando | qué deja de andar |
|---|---|---|
| **`parches`** | **el juego entero** (los que están adentro y los que entran con el cliente ya al día), **la web**, el panel `/admin` y **Cuenta Eñeños** | comprobar o bajar actualizaciones del cliente (`/parches/auth`, `/parches/manifest`, `/parches/files/*`, `/parches/launcher/*`). Caddy devuelve `502` en esas rutas hasta que `parches` vuelva |
| **`web` (Caddy)** | **los que ya están jugando en R2Beat** siguen en sus salas y cambiando de canal (el juego va por TCP directo a 48004 y 48005…48095, sin pasar por Caddy) | todo lo que entra por HTTP/HTTPS en esa máquina: la web pública, `/api/*` (el panel y el login web del launcher nuevo), `/cuentas/*` (pases nuevos para EDA) y `/parches/*` (descargas del cliente) |

### Cuando `/auth` de `parches` pase a Cuenta Eñeños (anotado, sin hacer)

Hoy `patchserver.py` (`verify_account`) abre `/juego/datos.db` y mira `users.pass_hash` directo. Eso obliga a montar
`r2beat2013_datos:/juego` en `parches` y **ata el servidor de parches a la misma máquina que el juego** (igual que pasa
hoy con `cuentas` en las etapas 0 y 1).

Cuando Cuenta Eñeños sea la dueña de las cuentas (etapa 3 de §4), para desatar `parches` habrá que cambiar:

1. **En `patchserver.py` (`verify_account` / `do_POST /auth`):** en vez de abrir `CFG["clean_db"]` con SQLite, aceptar
   un **pase firmado** por Cuenta Eñeños (con `aud = "parches"` o `"r2beat-patch"`, verificado localmente con
   `firma_ed25519.verificar` y la clave pública JWKS de Cuenta Eñeños guardada en disco) o validar usuario y hash contra
   el endpoint `/cuentas/entrar` de Cuenta Eñeños.
2. **En el panel viejo de `patchserver.py` (`/status`, `/accounts`, `/admin/update`):** ya está tapado en prod desde el
   25-sep y reemplazado por `/admin` de la web nueva (`servidor/panel_admin.py`). Sacarlo (o dejarlo apagado) elimina
   el último motivo por el que `patchserver.py` tocaba `datos.db` y `status.json`.
3. **En `docker-compose.yml` y `parches.Dockerfile`:** quitar el montaje `r2beat2013_datos:/juego` y las variables
   `PARCHES_BASE` y `PARCHES_STATUS`. Desde ese momento `parches` sólo necesita su carpeta `/releases` y puede correr
   en cualquier VPS.

### ⛔ Lo que NO se pudo comprobar en esta entrega

En la sesión que escribió esta sección **estaba prohibido ejecutar cualquier comando de terminal** (ni `docker`, ni
`npm`, ni `python`, ni `caddy`). Todo quedó escrito por lectura de código y siguiendo las piezas que ya andan. Antes de
darlo por bueno hay que correr y comprobar:

- `python3 pruebas/probar_contenedores.py` (parte A: que ningún archivo nuevo tenga una IP o dominio clavado, y sumar
  `parches.Dockerfile`, `web.Dockerfile`, `Caddyfile` y los `.dockerignore` nuevos a la lista de `A3`);
- `docker compose build parches web`: que `npm ci && npm run build` compile `web/dist/` dentro de `node:22-bookworm-slim`
  y que `caddy:2-alpine` valide el `Caddyfile` (`caddy validate --config /etc/caddy/Caddyfile`);
- que en la máquina de Docker donde corra `web` con `r2` (`uid 10013`), Caddy pueda abrir los puertos `80` y `443` sin
  privilegios (`net.ipv4.ip_unprivileged_port_start=0` en la red de Docker) y escribir en el volumen `web_datos:/data`;
- levantar los 4 servicios con `WEB_NOMBRE=:80` y comprobar por HTTP en el puerto 80: `/` (HTML de Astro), `/api/salud`
  (200 del juego), `/cuentas/salud` (200 de cuentas), `/parches/health` (200 de parches), `POST /parches/auth` con una
  cuenta sembrada y `GET /parches/manifest` con una release de prueba en `parches_releases`;
- comparar `_trabajo/parches_fuente/patchserver.py` (copia de julio) contra el `/opt/r2beat/patchserver/patchserver.py`
  que corre hoy en prod (por ejemplo, si en prod se agregó la ruta `/online` o se corrigió `row["uid"]`).

### Construido y probado el 15-nov (lo que la sección de arriba no había podido comprobar)

- **En local (WSL):** las cuatro imágenes construyen (juego 61 MB, cuentas 42, parches 42, web 25) y los cuatro
  contenedores quedan sanos juntos. Por la web (Caddy, puerto 80): el sitio, `/api/launcher/publico`,
  `/cuentas/salud`, `/parches/health`, y `/parches/auth` con una cuenta de prueba (con la clave mal, 401). El
  banco de contenedores siguió en verde (107).
- ⚠ En la PC de desarrollo la web no construía: la red corta las descargas (`ERR_SSL_CIPHER_OPERATION_FAILED` en
  `npm ci`). `web.Dockerfile` ahora reintenta `npm ci` hasta 10 veces.
- **En el VPS de ensayo:** las dos imágenes nuevas viajaron con `docker save` (66 MB), se agregó al `.env`
  `WEB_NOMBRE=ensayo.xn--eeos-gqab.link` y Caddy sacó solo el certificado de Let's Encrypt (reto `tls-alpn-01`).
  Desde afuera, por HTTPS, 11 chequeos bien: certificado válido, el sitio, la API, cuentas, parches, el login del
  launcher en parches y en la API, y los puertos 48190, 48195 y 8080 cerrados hacia internet.
  Los cuatro contenedores usan 128 MB de RAM entre todos.
- **Falta:** cargar una release de verdad en el servidor de parches (hoy contesta «no hay release publicado»), el
  auto-update del launcher contra este servidor, y comparar `patchserver.py` (copia de julio) con el de prod.

### El launcher baja una release del servidor de parches del ensayo (15-nov, después)

Se cargó en el VPS una release de PRUEBA (`ensayo_r1`: tres archivos inventados, 2,2 MB, con su `manifest.json` hecho
por `make_manifest.py`) en una carpeta de la máquina (`PARCHES_RELEASES_ORIGEN=/opt/enenos/releases`,
`PARCHES_RELEASE_ACTIVA=ensayo_r1`). El launcher nuevo, en su modo de verdad y con un `net.json` que le dice que su
servidor de parches es `https://ensayo.xn--eeos-gqab.link/parches`, con una carpeta de cliente vacía:

- entra con `prueba1` (el servidor de parches anota `AUTH ok`, y ve la IP real del jugador a través de Caddy);
- ve «Nueva version (3 archivos, 2.2 MB)», se aprieta ACTUALIZAR y los tres archivos quedan con el mismo md5 que en el VPS;
- **el control:** se rompe un archivo a mano → «Verificar y reparar» dice «Reparar: 1 archivos» y lo vuelve a bajar.
- ⛔ No se apretó JUGAR: en ese modo el launcher apunta al server de prod. Guion: `_trabajo/ensayo_migracion/6_actualizar.py`.
- Falta: una release con el cliente de verdad (GB, por `rsync`), `PARCHES_URL_ARCHIVOS` con una CDN delante, y el
  auto-update del propio launcher (`/launcher/meta`, `/launcher/bin`).

## 20 · Cuenta Eñeños, dueña de las cuentas (parte 1: el servicio)

El **15-nov-2026** se decidió descartar la convivencia de «dos puertas» (§4): en la versión nueva **Cuenta Eñeños (`servidor/portero.py`) es la única dueña de las cuentas y la única que guarda contraseñas**. El launcher inicia sesión una sola vez contra Cuenta Eñeños y pide pases firmados (`Ed25519`); el juego, la web y el servidor de parches sólo verifican el pase con la clave pública. El día del reemplazo se copian las cuentas una sola vez desde `datos.db` y se pisa todo.

Todo el modo nuevo vive detrás del interruptor **`R2_CUENTAS_DUENA=1`**. Sin esa variable (o con cualquier valor distinto de `1`), `servidor/portero.py` se comporta exactamente igual que antes (lee `datos.db` en sólo lectura) y las pruebas anteriores (`pruebas/probar_portero.py` y `pruebas/probar_contenedores.py`) siguen pasando sin cambios.

### Qué guarda (`cuentas.db`)

Con `R2_CUENTAS_DUENA=1`, Cuenta Eñeños **no abre nunca `datos.db`** (`_juego()` lanza `RuntimeError` si alguien intenta llamarla y `servidor()` arranca aunque `datos.db` no exista). En la misma carpeta donde guarda `portero.db` abre su base de cuentas propia, **`cuentas.db`** (en WAL), con la tabla `cuentas`:

| columna | tipo y reglas | qué guarda |
|---|---|---|
| `uid` | `INTEGER PRIMARY KEY` | Las cuentas importadas conservan su `uid` histórico de R2Beat. Las cuentas **nuevas** arrancan desde `UID_NUEVAS_DESDE` (`10.000.000` por omisión, configurable por `R2_CUENTAS_UID_DESDE`) y siempre por encima de `MAX(uid)`, para no chocar con los `usn` que R2Beat reserva para los personajes 2, 3 y 4 |
| `usuario` | `TEXT UNIQUE NOT NULL COLLATE BINARY` | El nombre de login tal cual lo escribió el jugador (`3` a `16` caracteres alfanuméricos o `_`, mismas reglas que `basedatos.cuenta_crear`). Se compara **exacto** (`Junior` ≠ `junior`, preservando los 60 pares que ya existen en prod) |
| `clave` | `TEXT NOT NULL` | El hash SHA-256 en hex mayúscula envuelto en `scrypt` con sal aleatoria por cuenta (`scrypt$16384$8$1$<sal_hex>$<dk_hex>`) |
| `estado` | `TEXT NOT NULL` (`activa` / `baneada` / `fusionada`) | El estado de la cuenta (en vez de los prefijos `BANNED:` y `FUSIONADA:` pegados delante del hash) |
| `creada` | `TEXT NOT NULL` | Fecha de alta (`reg_time` al importar, o fecha actual al registrar) |

### Cómo se protege la contraseña (`scrypt` sobre el SHA-256)

Hoy el launcher calcula y manda el SHA-256 en hex mayúscula de la contraseña (`basedatos.hash_pass`), que era lo mismo que estaba guardado en `users.pass_hash`. Para que **ningún jugador tenga que cambiar su contraseña** al migrar y a la vez el archivo `cuentas.db` no tenga ningún SHA-256 utilizable si alguien lo copia:

1. Al importar, registrar o cambiar la clave, se toma el SHA-256 en hex mayúscula (64 caracteres) y se lo pasa por `hashlib.scrypt` (librería estándar) con una **sal aleatoria de 16 bytes por cuenta** (`SCRYPT_N = 16384`, `SCRYPT_R = 8`, `SCRYPT_P = 1`, `SCRYPT_LARGO = 32`).
2. En `cuentas.db` sólo se escribe `scrypt$16384$8$1$<sal_hex>$<dk_hex>`. El SHA-256 nunca queda guardado en disco.
3. Al verificar (`POST /cuentas/entrar` o `POST /cuentas/cambiar-clave`), se obtiene el SHA-256 en hex mayúscula de lo que mandó el jugador, se recalcula `hashlib.scrypt` con la sal de esa fila y se compara en tiempo constante con `hmac.compare_digest`.

### Rutas HTTP (con `R2_CUENTAS_DUENA=1`)

Todas las rutas aceptan el prefijo `/cuentas` o sin él, exigen `X-R2: 1` en los `POST` y mantienen el freno de intentos (`8` en `15` minutos):

- **`POST /cuentas/entrar`** (`{usuario, clave}` o `{usuario, pass_sha256_upper}`): valida contra `cuentas.db`. Da el mismo `401` (`«Usuario o contraseña incorrectos.»`) cuando el usuario no existe o la contraseña está mal. Si la clave coincide pero la cuenta está `baneada`, devuelve `403` (`«Esta cuenta está suspendida.»`); si está `fusionada`, devuelve `403` (`«Esta cuenta se unió a otra: entrá con aquélla.»`) — los mismos mensajes que `api_web.iniciar_sesion`.
- **`POST /cuentas/pase`** (`{juego}` + `Bearer <sesion>`): emite el JWT `EdDSA` (`iss = "r2beat-portero"`, `aud = <juego>`, `sub = "<uid>"`, `exp = iat + 300`, `jti` único).
  - **`eda`**: sigue pidiendo que la cuenta esté en `aprobados`.
  - **`r2beat2013`**, **`parches`** y **`web`**: abiertos a cualquier cuenta con `estado = 'activa'` (y no baneada en ese juego).
  - ⛔ **Privacidad:** el nombre de login (`usuario`) **nunca** va en el pase.
- **`POST /cuentas/registrar`** (`{usuario, clave}` o `{usuario, pass_sha256_upper}`): crea la cuenta en `cuentas.db` con `uid >= UID_NUEVAS_DESDE` y `> MAX(uid)`. Tiene freno por IP (`8` intentos por ventana), valida el formato (`3..16` alfanumérico o `_`) y rechaza duplicados exactos con `409`.
- **`POST /cuentas/cambiar-clave`** (`Bearer <sesion>` + `{clave_actual, clave_nueva}` o `{actual_sha256_upper, nueva_sha256_upper}`): comprueba la sesión viva y la contraseña actual antes de envolver y guardar la nueva en `cuentas.db`.
- **`GET /cuentas/interno/cuenta/<uid>`** (interno, para el panel del juego): protegido por la ficha compartida `R2_CUENTAS_FICHA_INTERNA` (en `Authorization: Bearer <ficha>` o `X-Ficha-Interna`). Devuelve `200` con `{"uid": <int>, "usuario": "<str>", "estado": "<str>"}` y **nunca** incluye datos de la contraseña. Si `R2_CUENTAS_FICHA_INTERNA` no está definida, la ruta devuelve `404` como inexistente.

### Variables nuevas

| variable | por omisión | para qué sirve |
|---|---|---|
| `R2_CUENTAS_DUENA` | *(apagada)* | Con `1`, prende el modo dueño: usa `cuentas.db`, habilita `registrar`, `cambiar-clave`, el pedido interno y los pases para `r2beat2013`, `parches` y `web`, y **no abre nunca `datos.db`** |
| `R2_CUENTAS_BASE` | `cuentas.db` al lado de `portero.db` | Ruta al archivo SQLite de cuentas (`cuentas.db`) |
| `R2_CUENTAS_UID_DESDE` | `10000000` (`UID_NUEVAS_DESDE`) | Número mínimo de `uid` para las cuentas nuevas creadas con `registrar` |
| `R2_CUENTAS_FICHA_INTERNA` | *(vacía = ruta apagada)* | Ficha secreta compartida para que el panel del juego consulte `GET /cuentas/interno/cuenta/<uid>` |

### Comandos de consola y la copia del día del reemplazo

```bash
# 1. El día del reemplazo: copiar las cuentas de una datos.db vieja a cuentas.db
R2_CUENTAS_DUENA=1 python -m servidor.portero importar /ruta/a/datos.db

# 2. Administración de cuentas en cuentas.db (por consola del VPS)
R2_CUENTAS_DUENA=1 python -m servidor.portero cambiar-clave <usuario> <nueva_clave>
R2_CUENTAS_DUENA=1 python -m servidor.portero banear <usuario> [motivo…]
R2_CUENTAS_DUENA=1 python -m servidor.portero desbanear <usuario>
```

Cómo funciona **`importar <ruta a datos.db>`**:
- Abre la `datos.db` vieja en **sólo lectura** (`mode=ro` + `PRAGMA query_only = 1`; la prueba comprueba que su `md5` no cambia).
- Lee `users (uid, username, pass_hash, reg_time)`: separa los prefijos `BANNED:` (`estado = 'baneada'`) y `FUSIONADA:` (`estado = 'fusionada'`) del SHA-256 de 64 hex, envuelve cada hash en `scrypt` con sal propia y guarda la fila en `cuentas.db` conservando el `uid` y las mayúsculas/minúsculas exactas de `username`.
- Es **idempotente**: si se corre dos veces, saltea las cuentas cuyo `uid` o `usuario` ya estén en `cuentas.db` sin duplicar ni pisar claves.
- Imprime sólo el resumen (`✔ importar: X copiada(s), Y ya estaba(n), Z baneada(s), W fusionada(s).`) y **nunca imprime ningún hash**.

### Lo que falta (partes 2 y 3)

Esta entrega cubre **sólo la parte 1 (el servicio de cuentas)** y su banco de pruebas (`pruebas/probar_cuenta_duena.py`). No se tocaron el juego, la web, el servidor de parches ni el launcher:

- **Parte 2 (juego, web y servidor de parches):** que el servidor de R2Beat (`lobby` / `cuenta_personajes`), la web (`api_web`) y el servidor de parches (`patchserver.py`) acepten y verifiquen el pase firmado (`aud = "r2beat2013"`, `"web"` y `"parches"`) con la clave pública de Cuenta Eñeños, que el panel del juego consulte el nombre de usuario por el pedido interno (`R2_CUENTAS_FICHA_INTERNA`) y que los contenedores de `cuentas` y `parches` dejen de montar el volumen de `datos.db`.
- **Parte 3 (el launcher):** que el launcher inicie sesión, registre cuentas y cambie contraseñas únicamente contra Cuenta Eñeños, y pida allí los pases para actualizar el cliente (`parches`), entrar al juego (`r2beat2013`), usar la web (`web`) o entrar a `eda`.

## 21 · Cuenta Eñeños, dueña de las cuentas (parte 2: el juego, la web y parches entran con el pase)

El **15-nov-2026** se armó la **parte 2 de 3**: el servidor del juego (`servidor/pase.py`, `servidor/lobby.py`, `servidor/cuenta_personajes.py`, `servidor/basedatos.py`, `servidor/almacen.py`), la API web y el panel (`servidor/api_web.py`, `servidor/launcher_api.py`, `servidor/panel_admin.py`) y el servidor de parches (`herramientas/contenedores/parches/patchserver.py` + `arranque.py`) aceptan y verifican localmente los pases firmados (`Ed25519`) por Cuenta Eñeños.

Todo queda detrás de los interruptores **`R2_LOGIN=pase`** (juego y web) y **`PARCHES_LOGIN=pase`** (parches). Por omisión (vacíos), el comportamiento actual con usuario + hash no cambia en nada y todas las pruebas existentes siguen pasando.

### Formato byte a byte del `FF01` y `FFF1`…`FFF5` con pase

El cliente del juego (`R2Beat.exe`) **no se toca**: sigue recibiendo `(usn, vcode)` del launcher por línea de comandos y entrando al puerto `48004` con su `FF01` de `12` bytes (`[usn:u32 (<I)][vcode:u64 (<Q)]`, con `usn != 0`).

Lo que cambia cuando `R2_LOGIN=pase` es lo que manda **el launcher** al puerto `48004`:

1. **`FF01` del launcher con pase (`lobby.armar_login_pase` / `leer_login_pase` / `bot_carga.ff01_pase`)**:
   - Cabecera de trama: `0xFF 0x01 <largo:u16 (<H)>`
   - Carga útil (`payload`):
     ```text
     [0:u32 (<I)] [0x50 ('P'):u8] [plen:u16 (<H)] [pase_ascii:plen]
     ```
   - Los primeros 4 bytes en `0` lo distinguen del `FF01` del exe (`usn != 0`), y el quinto byte `0x50` (`'P'`) lo distingue sin ambigüedad del `FF01` viejo del launcher (`payload[4] == 0x00`).
   - El largo `plen` va en `u16` (`<H`) porque el pase JWT `EdDSA` mide ~200–280 caracteres ASCII (supera los 255 bytes de un `u8` en formato JWT de 3 partes).
   - El server verifica el pase con `aud = "r2beat2013"`, asegura la fila de la cuenta en `users` (`almacen.asegurar_cuenta_uid(uid)`), abre la sesión (`sesion_abrir(uid)`) y contesta el mismo `resp_login_launcher(usn, vcode, ok=True)` de siempre.
   - Con `R2_LOGIN=pase`, el `FF01` viejo con `usuario` + `hash` y el registro por TCP (`FFF0`) se rechazan.

2. **`FFF1` (lista), `FFF2` (crear), `FFF3` (entrar) y `FFF5` (borrar) en `servidor/cuenta_personajes.py`**:
   - Donde antes empezaban con `[ulen:u8][usuario][hlen:u8][sha256_hex]`, cuando `R2_LOGIN=pase` empiezan con el bloque `cuenta_pase(pase)`:
     ```text
     [0x50 ('P'):u8] [plen:u16 (<H)] [pase_ascii:plen]
     ```
     seguido exactamente por los mismos bytes de antes (`ranura`, `sexo`, `apodo`, `prendas` en `FFF2`; `ranura [+ crear]` en `FFF3`; `ranura` en `FFF5`).
   - El primer byte `0x50` (80 decimal) nunca puede confundirse con un `ulen` válido de `leer_cuenta` (que exige `1 <= ulen <= 32`).
   - Para una cuenta nueva creada en Cuenta Eñeños (`uid >= 10_000_001`), el casillero 1 usa ese mismo `uid`, y los casilleros 2–4 reservan `uid < 10_000_000` (`almacen.reservar_ranura`), sin chocar nunca con las cuentas nuevas de Cuenta Eñeños.
   - El selector **adentro del juego** (`FFF6`…`FFFA`) ya se autenticaba por `(usn, vcode)` de la sesión activa y no necesitaba contraseña (`FFF7` ahora arma la lista directo con `_armar_lista(usuario)`).

### Web, launcher API, panel y servidor de parches

- **`POST /api/sesion` (`api_web.iniciar_sesion`) y `POST /api/launcher/entrar` (`launcher_api.py`)**: con `R2_LOGIN=pase`, reciben `{"pase": "<jwt>"}`, verifican `aud = "web"`, aseguran la fila en `users` para ese `uid`, abren la sesión web y devuelven los datos y personajes de la cuenta. Rechazan `usuario` + `clave` cuando `R2_LOGIN=pase` (y rechazan `{pase}` cuando `R2_LOGIN` está vacío).
- **El nombre de usuario en `servidor/panel_admin.py`**: con `R2_LOGIN=pase`, `_login_panel(uid)` consulta a `pase.nombre_usuario_interno(uid)` (`GET /cuentas/interno/cuenta/<uid>` con `R2_CUENTAS_FICHA_INTERNA` y cache en memoria de 60 s). Si Cuenta Eñeños no contesta o no está configurada, devuelve `str(uid)` sin romper ninguna vista del panel.
- **`POST /auth` en `herramientas/contenedores/parches/patchserver.py`**: con `PARCHES_LOGIN=pase`, recibe `{"pase": "<jwt>"}`, verifica localmente la firma `Ed25519` y `aud = "parches"` sin abrir `datos.db` ni llamar a Cuenta Eñeños, guarda el `jti` para impedir reuso y devuelve el token de descarga (`token` / `session_token`).

### Variables nuevas (parte 2)

| variable | dónde aplica | por omisión | qué hace |
|---|---|---|---|
| `R2_LOGIN` | `r2beat2013` (juego + web) | *(vacía)* | Vacía = login tradicional por `usuario` + `hash` contra `datos.db`. Con `pase`, sólo acepta pases firmados por Cuenta Eñeños (`aud = "r2beat2013"` en TCP y `"web"` en HTTP) |
| `R2_CUENTAS_CLAVE_PUBLICA` | `r2beat2013` | *(vacía)* | Clave pública `Ed25519` de Cuenta Eñeños (base64url de 32 bytes, hex de 64 o JSON JWKS). Si está puesta, no hace falta consultar la red al arrancar |
| `R2_CUENTAS_URL` | `r2beat2013` | *(vacía)* | URL base interna de Cuenta Eñeños (ej. `http://cuentas:48195`): sirve para bajar `/clave-publica` una vez al arranque (si falta `R2_CUENTAS_CLAVE_PUBLICA`) y para que `panel_admin` consulte `/cuentas/interno/cuenta/<uid>` |
| `PARCHES_LOGIN` | `parches` | *(vacía)* | Vacía = `/auth` valida `user` + `pass_sha256_upper` en `datos.db`. Con `pase`, `/auth` sólo acepta `{pase}` firmado con `aud = "parches"` |
| `PARCHES_CUENTAS_CLAVE_PUBLICA` | `parches` | *(vacía)* | Clave pública `Ed25519` de Cuenta Eñeños para que `patchserver.py` verifique pases localmente en memoria |

### Qué pasa si Cuenta Eñeños se cae después de arrancar

- **El juego (`r2beat2013`) y el servidor de parches (`parches`) tienen la clave pública de 32 bytes en memoria** desde el arranque (leída de `R2_CUENTAS_CLAVE_PUBLICA` / `PARCHES_CUENTAS_CLAVE_PUBLICA` o bajada una sola vez de `R2_CUENTAS_URL/clave-publica`).
- **Ningún login del juego (`FF01`), de la web (`/api/sesion`, `/api/launcher/entrar`) ni de parches (`/auth`) llama por red a Cuenta Eñeños**: todo pase ya emitido (vigente y no usado) se sigue verificando localmente aunque Cuenta Eñeños esté apagada, y los jugadores que ya están adentro del juego siguen jugando sin cortes.
- En el panel de administración (`panel_admin.py`), si Cuenta Eñeños no responde al pedido interno `/cuentas/interno/cuenta/<uid>`, las fichas y tablas muestran el `uid` como texto y siguen funcionando.
- Si el juego o parches arrancan con `R2_LOGIN=pase` / `PARCHES_LOGIN=pase` y no tienen ni clave pública en variable ni respuesta de `R2_CUENTAS_URL`, dejan un aviso claro en el log y rechazan los logins sin caerse.

### Lo que queda para la parte 3 (el launcher)

- Que el launcher (`launcher-tauri`) hable con Cuenta Eñeños (`/cuentas/entrar`, `/cuentas/registrar`, `/cuentas/cambiar-clave` y `/cuentas/pase`) para obtener los pases de `parches`, `web`, `r2beat2013` y `eda`, y los mande a `/parches/auth`, `/api/launcher/entrar` y al puerto `48004` (`FF01` / `FFF1`…`FFF5`).

## 22 · Las partes 1 y 2 prendidas en el VPS de ensayo (15-nov-2026 · probado por internet)

⛔ Sólo en el VPS **efímero** de ensayo (`ensayo.eñeños.link`). **Nada de esto está en prod.**

**Qué se hizo** (los guiones quedaron en `_trabajo/ensayo_migracion/`, que no va al repo):

| paso | guion | qué hace |
|---|---|---|
| 7 | `7_construir_parte2.sh` | arma en el WSL las tres imágenes con las partes 1 y 2 (`juego`, `cuentas`, `parches`); la web no cambió |
| 8 | `8_prender_pase.sh` | en el VPS: resguarda `.env` y el compose, carga las imágenes, **copia las cuentas una vez** (`portero importar /juego/datos.db`), saca la clave pública y prende `R2_CUENTAS_DUENA=1`, `R2_LOGIN=pase` y `PARCHES_LOGIN=pase`. `bash 8_prender_pase.sh volver` deja todo como antes |
| 9 | `9_verificar_pase.py` | desde esta PC, por internet: 24 chequeos, cada uno con su control al revés |

**Lo que dio (24 bien, 0 mal):**

- La copia de cuentas: 3 copiadas; corrida de nuevo, 0 copiadas y 3 «ya estaban». La clave que firma es la misma de
  antes de la mudanza (`kid 4e1fe705c450c45c`): EDA no tiene que cambiar nada.
- **El juego:** con el pase entra (el `usn` es el `sub` del pase), recibe los 10 canales, entra al canal Libre y le
  llega su ficha. ⟲ No entra: el mismo pase dos veces, el login de antes con usuario + contraseña, un pase hecho para
  la web, un pase con la firma tocada.
- **La API:** `/api/launcher/entrar` y `/api/sesion` con `{pase}` abren sesión y dan los personajes. ⟲ Con usuario +
  contraseña, 401; el mismo pase otra vez, 401.
- **Parches:** `/auth` con `{pase}` da la sesión y con ella baja el manifiesto de la release. ⟲ El mismo pase otra
  vez y usuario + contraseña: 401.
- **Una cuenta nueva:** se registra en Cuenta Eñeños y recibe el uid `10000000` (el primero de las nuevas); entra al
  juego con su pase sin haber jugado nunca, y la API la recibe con 0 personajes. ⟲ El mismo nombre otra vez: 409.
- El pedido interno (`/cuentas/interno/cuenta/<uid>`) sin su ficha contesta 401.

**Lo que queda anotado:**

- ⚠ **El launcher todavía no sabe pedir pases** (es la parte 3): mientras el ensayo esté en `R2_LOGIN=pase`, el
  launcher de la rama `launcher-tauri` **no entra** a ese VPS. Para volver a probar el launcher viejo contra el
  ensayo: `bash 8_prender_pase.sh volver`.
- ⚠ `/cuentas/interno/*` sale a internet por Caddy (lo protege la ficha, y sin la variable no existe). Mejor que
  Caddy ni lo pase: una regla `respond 404` para esa ruta en el `Caddyfile`, la próxima vez que se rearme la web.
- `basedatos.cuenta_verificar` ahora rechaza cualquier hash que no mida 64: una cuenta con `pass_hash` vacío (las que
  crea el login con pase) no se puede abrir mandando el hash vacío, tampoco si un día se vuelve a `R2_LOGIN` vacío.

## 23 · Parte 3: el launcher entra una vez y usa pases (15-nov-2026 · probado contra el ensayo · NO publicado)

El código vive en la rama `launcher-tauri` (commit `0a2ac642`); su guía, `taller/launcher_tauri/LEEME.md`.

- **El interruptor del launcher:** `R2_ENTRAR=pase`. Sin la variable vale una constante que hoy está en `false`
  (**se da vuelta el día del reemplazo**): apagado, el launcher hace exactamente lo de siempre.
- **Prendido:** la contraseña va a un solo lugar, `{cuentas}/entrar`. Después pide un pase por pieza: `parches`
  para `/auth`, `web` para `/api/launcher/entrar`, `r2beat2013` para el `FF01` al apretar JUGAR, `eda` para EDA.
  Registrarse va a `{cuentas}/registrar`. Si la sesión venció, vuelve a entrar solo una vez.

**La prueba** (`_trabajo/ensayo_migracion/10_launcher_con_pase.py`, el launcher de verdad contra el VPS de ensayo,
que sólo acepta pases):

| parte | qué | resultado |
|---|---|---|
| A | entra una vez → parches le muestra la actualización → la API le da sus personajes → ACTUALIZAR baja los 3 archivos (mismo md5) | 5 de 5 |
| B | JUGAR con el cliente instalado y el exe de prod: el server anota `LAUNCHER PASE OK -> usn=1` y el exe llega a «Lobby asentado» | 6 de 6 |
| C | ⟲ contraseña mala; ⟲ el mismo launcher SIN pases contra este VPS | no entran (2 de 2) |
| D | registrarse desde el launcher (uid de los nuevos), ⟲ el nombre repetido, y entrar con la cuenta recién creada | 4 de 4 |

**Lo que apareció al probar:** a una cuenta nueva el juego la llama `uid_<n>` (no conoce el nombre de login), y la
API devolvía eso como nombre de la cuenta. Con pases, el launcher muestra el nombre que escribió el jugador.

**Con esto el circuito está completo en el ensayo:** Cuenta Eñeños (dueña) → pases → juego, API, parches y EDA, con
el launcher y el exe de verdad. **Lo que falta para el reemplazo** (nada de esto se hizo): publicar las imágenes
nuevas, cortar `/cuentas/interno/*` en Caddy, comparar `patchserver.py` con el de prod, una release de cliente de
verdad en el servidor de parches del ensayo, la auto-actualización del launcher, y el visto bueno de Eñeños.

## 24 · Cuenta Eñeños, dueña de las cuentas (parte 4: el panel administra las cuentas a través de Cuenta Eñeños)

Con `R2_LOGIN=pase` (`pase.modo_pase()`), `panel_admin.py` no abre nunca `cuentas.db`: cada cambio administrativo de
estado, contraseña, búsqueda por usuario o creación de cuenta separada viaja por HTTP interno a Cuenta Eñeños usando
`R2_CUENTAS_URL` y `R2_CUENTAS_FICHA_INTERNA`. Sin `R2_LOGIN=pase`, el panel sigue operando sobre `datos.db` exactamente
como antes.

### Pedidos internos nuevos en `servidor/portero.py` (y cliente en `servidor/pase.py`)

Exigen `R2_CUENTAS_DUENA=1` y `R2_CUENTAS_FICHA_INTERNA` (404 si falta alguno, 401 si la ficha no coincide, y `X-R2: 1`
en todo `POST`): nunca devuelven ni anotan en el log o en `auditoria` contraseñas ni hashes. Caddy ya bloquea
`/cuentas/interno/*` con 404 desde afuera.

| método y ruta | cliente (`pase.py`) | qué hace en `portero.py` |
|---|---|---|
| `GET /cuentas/interno/usuario/<usuario>` | `buscar_usuario_interno(usuario)` | Busca por usuario EXACTO (`COLLATE BINARY`, `Junior` != `junior`) → `{uid, usuario, estado}` o 404 |
| `POST /cuentas/interno/cuenta/<uid>/estado` | `poner_estado_interno(uid, estado, motivo)` | Fija `activa`, `baneada` o `fusionada`; si pasa a `baneada` o `fusionada`, borra `sesiones` de ese `uid` en `portero.db` |
| `POST /cuentas/interno/cuenta/<uid>/clave` | `poner_clave_interna(uid, pass_sha256_upper)` | Envuelve el SHA-256 en `scrypt`, actualiza `cuentas.clave`, borra `sesiones` de ese `uid` en `portero.db` |
| `POST /cuentas/interno/cuenta` | `crear_cuenta_interna(uid, usuario, pass_sha256_upper)` | Crea una cuenta activa con ese `uid` (`0 < uid < _uid_nuevas_desde()`) y las mismas reglas de usuario que `registrar`; 409 si repite `uid` o `usuario` |

### Qué toca cada acción del panel con `R2_LOGIN=pase`

| acción en `panel_admin.py` | juego (`datos.db` / `panel.db`) | Cuenta Eñeños (`cuentas.db` / `portero.db`) |
|---|---|---|
| Ban / desban (`accion` y `barrer` cuando vence un ban temporal) | Actualiza `users.pass_hash` (`BANNED:`) y tabla `bans` de `panel.db` | `_avisar_estado_cuenta` calcula el estado desde `users.pass_hash` (`baneada` > `fusionada` > `activa`) y llama a `poner_estado_interno` |
| Cambio de clave (`_clave` / `accion`) | No escribe clave ni hash en `datos.db`; cierra sesiones web locales si sale bien | Va directo a `poner_clave_interna`. Si Cuenta Eñeños rechaza o no contesta, falla con ese error sin escribir nada en ningún lado |
| `cuentas_accion`: `fusionar`, `separar`, `mover` | `almacen.*` aplica el movimiento/bloqueo en `datos.db` | `_avisar_estado_cuenta` sincroniza el estado resultante de cada cuenta positiva tocada (`fusionar`: origen y destino; `separar`: origen y destinos; `mover`: origen y destino) |
| `cuentas_accion`: `separar_nueva` | Luego mueve el personaje del casillero 2-4 a `(usuario, 1)` con `users.pass_hash = ""` | **Primero** crea la cuenta en Cuenta Eñeños con el `uid` del personaje (`crear_cuenta_interna`). Si falla, no toca el juego |
| `buscar_usuarios(q)` | Consulta `users` y `chars` como siempre | Además consulta `buscar_usuario_interno(q)` y suma o completa la fila coincidente (incluso si todavía no entró al juego) |

### Qué pasa si Cuenta Eñeños no contesta durante una acción del panel

- **Estado (`ban`, `desban`, `fusionar`, `separar`, `mover`):** el cambio del juego **no se deshace**. El panel devuelve
  `200` con el campo `"aviso"` indicando repetir la acción y escribe una advertencia en el log (`servidor.log`). Al
  repetir la acción con Cuenta Eñeños arriba, `_avisar_estado_cuenta` vuelve a calcular el estado desde `users.pass_hash`
  y empareja `cuentas.db` (en `desban` repetido detecta si Cuenta Eñeños sigue `baneada`). En `barrer()` deja el aviso en
  el log sin bloquear el vencimiento local.
- **Cambio de clave (`_clave`):** la acción falla (`400`) con el error de conexión o rechazo, sin tocar `cuentas.db`,
  `datos.db` ni sesiones.
- **`separar_nueva`:** si falla Cuenta Eñeños al principio, no se toca el juego. Si Cuenta Eñeños crea la cuenta y luego
  falla `almacen.separar_a_cuenta_nueva`, el panel devuelve `400` con `creada_en_cuentas: True`, anota el aviso en el log
  y explica en el error que la cuenta ya quedó creada en Cuenta Eñeños con ese `uid` y `usuario`.

### Lo que queda anotado para después

- Ejecutar `pruebas/probar_panel_y_cuentas.py` y el resto de la batería en un entorno con terminal/Python (en este encargo
  no se ejecutó código).
- `cuentas_ver(q)` y `cuentas_accion` siguen buscando/recibiendo el `username` de `datos.db` (donde cuentas nacidas con
  pase figuran como `uid_<uid>` si nunca pasaron por `almacen`); y `casillero1` intercambia `users.uid` localmente sin
  tocar `cuentas.db`. Si hace falta operar cuentas nacidas con pase por su nombre real desde la pestaña Cuentas, conviene
  resolverlo en un paso específico.
- `servidor/gm.py` no tiene comandos de ban ni cambio de clave (y el resto de los módulos del juego tampoco llama a
  `_poner_ban` ni `_clave` fuera de `panel_admin.py`); sólo la consola de `servidor/portero.py` ya administraba
  `cuentas.db` cuando `R2_CUENTAS_DUENA=1`.

## 25 · Lo que falta para el reemplazo: lo hecho el 15-nov a la tarde y lo que queda por decidir

**Probado ese día** (guiones en `_trabajo/ensayo_migracion/`, que no va al repo; nada de esto tocó prod):

| paso | qué | resultado |
|---|---|---|
| 11 | la copia de cuentas con la FOTO DE PROD (en local, sólo lectura, sólo conteos; la `cuentas.db` se borra) | 5.398 de 5.398 en 4 min; cada una con su número; una muestra entra con su contraseña de siempre; 49 ms por login |
| 12 | el launcher 3.0.1 PUBLICADO se actualiza solo al launcher nuevo que anuncia el ensayo, abre y entra con pase | sí. ⚠ En esta PC la bajada (12 MB de un tirón) se cortó dos veces por la red; el 3.0.1 quedó intacto y al tercer intento se actualizó |
| — | la fusión de cuentas con pases (`pruebas/probar_pase_y_fusion.py`) | hecha antes o después de la copia, anda; ver abajo |
| — | las pruebas de las partes 1, 2 y 4 | `probar_cuenta_duena` 69, `probar_login_pase` 61, `probar_panel_y_cuentas` 38, `probar_pase_y_fusion` 30 |

**Arreglado ese día:**

- Un pase con el número de un PERSONAJE de casillero 2-4 abría la cuenta de su dueño (`almacen.asegurar_cuenta_uid`).
  Cuenta Eñeños nunca da un pase así, pero se cerró.
- El `patchserver.py` de la imagen era de julio; el de prod es del 26-jul (anuncia `base` e `ips` al launcher y tiene
  el freno de intentos en el panel de lectura). La imagen lleva ahora **el de prod + las líneas marcadas
  `# contenedor:` y `# pase:`** (unión de tres sin conflictos). Variables nuevas: `PARCHES_LAUNCHER_BASE` y
  `PARCHES_LAUNCHER_IPS`. ⚠ De prod sólo se leyeron los dos `.py`; el `config.json` no.
- `Caddyfile`: `/cuentas/interno/*` contesta 404 hacia internet (el juego le habla a `cuentas` por la red de adentro).

**Decisión cerrada (parte 5, §26):** se eligió la **opción A — identidad fija (el Eñeños ID)** de la tabla de abajo, dejando `casillero 1` destrabado con `R2_LOGIN=pase`.

### ⚠ POR DECIDIR: el número de la cuenta puede CAMBIAR («pasar al casillero 1»)

Desde el parche de los 4 personajes, el número de una cuenta (`users.uid`, el usn con el que entra) **no es fijo**:
`almacen.pasar_a_casillero_1` (panel, 07-nov) hace que otro personaje pase a ser el casillero 1, y entonces el número
de la cuenta pasa a ser el de ese personaje; a una cuenta fusionada le deja el número **dado vuelta en negativo**
(`6361 → -6361`). Con pases, ese número es la identidad con la que Cuenta Eñeños firma (`sub`), y también la que ve
EDA. Si cambia en el juego y no en Cuenta Eñeños, la cuenta no entra más (probado en `probar_pase_y_fusion.py` §4).

**Hoy, con `R2_LOGIN=pase`, la acción «casillero 1» está FRENADA** (400 con el motivo). Sin pases, como siempre.

Dos caminos para destrabarla (no se hizo ninguno):

| | qué es | a favor | en contra |
|---|---|---|---|
| **A · identidad fija** (la recomendada) | el juego guarda aparte, por cuenta, el número con el que la conoce Cuenta Eñeños (una columna nueva), y ese no cambia nunca; «casillero 1» sigue cambiando el personaje con el que se entra | Cuenta Eñeños y EDA ven siempre el mismo número; «casillero 1» no necesita avisarle nada a nadie | toca el esquema y el login del juego; hay que rellenar la columna el día del reemplazo |
| B · avisar el cambio | «casillero 1» le pide a Cuenta Eñeños que renumere la cuenta | el juego casi no cambia | dos bases que tienen que cambiar juntas (si una falla, la cuenta queda rota); en EDA el jugador pasa a ser «otro» |

⚠ Lo mismo le pasa HOY a EDA con el portero viejo: el pase de EDA lleva `users.uid`, así que una cuenta aprobada
en EDA a la que se le hizo «casillero 1» cambió de identidad para EDA.

**También anotado:** una cuenta fusionada con el número en negativo se copia tal cual (no entra, está bien); si
después se la separa, hay que ver que su número vuelva a coincidir en los dos lados (va con la decisión de arriba).
La pestaña Cuentas del panel sigue mostrando `uid_<n>` como nombre de las cuentas nacidas con pase.

- Rearmar las cuatro imágenes con todo esto, llevarlas al ensayo y repetir los guiones 9, 10 y 12.
- Publicar las imágenes (privadas) en ghcr.io.
- Una release de cliente DE VERDAD en el servidor de parches del ensayo: el cliente instalado pesa 8 GB y esta PC
  corta las subidas largas; lo natural es traerla de VPS a VPS, que lee de prod y por eso espera la orden de Eñeños.
- El número de versión del launcher nuevo (sigue diciendo 3.0.1).
- Decidir A o B, y el visto bueno de Eñeños.

## 26 · Cuenta Eñeños — parte 5: el Eñeños ID (identidad fija vs. personaje del juego)

Se adoptó la **opción A**: separar para toda la vida el número de la **persona** en Cuenta Eñeños (`cuentas.uid` =
**el Eñeños ID**, secuencial desde `UID_NUEVAS_DESDE = 10_000_000`) del número del **personaje en casillero 1** dentro
de R2Beat (`users.uid` / `usn` en `datos.db`, que sigue `< 10_000_000` o negativo si la cuenta quedó fusionada).

### Ejemplo (identidad vs. casilleros en R2Beat)

| Eñeños ID (`cuentas.uid` / `users.enenos_id`) | usuario (`cuentas.usuario`) | `users.uid` (casillero 1 / `usn`) | casilleros del juego (`1..4`) |
|---|---|---|---|
| `10000000` | `Junior` | `101` | `1: 101`, `2: 3402` |
| `10000001` | `junior` | `102` | `1: 102` |
| `10000002` | `fundida` (fusionada) | `-204` | *(ninguno; `204` pasó a otra cuenta y conserva `enenos_id=10000002`)* |
| `10000003` | `nueva_web` (nacida con pase) | `5401` (`< 10_000_000`) | `1: 5401`, `2: 5402` |

### Qué cambió

- **En Cuenta Eñeños (`servidor/portero.py`)**:
  - Todas las cuentas —importadas desde `datos.db` (en `ORDER BY rowid`, incluidas las baneadas y las fusionadas con
    `uid` negativo), registradas por web/launcher o creadas internamente desde el panel (`POST /cuentas/interno/cuenta`)—
    reciben un **Eñeños ID secuencial e inmutable desde `UID_NUEVAS_DESDE` (`10_000_000`)**. `cuentas.uid` nunca
    hereda `users.uid` ni `uid` negativos.
  - `importar` guarda el mapa `(uid_viejo, uid, usuario)` en `cuentas.db` (`importadas`) de forma idempotente (sin
    duplicar ni imprimir hashes), traduce una sola vez `aprobados` y `baneos` en `portero.db` usando
    `traducciones_uid`, limpia `sesiones` y `pases` anteriores y conserva `auditoria` como registro histórico.
  - `python -m servidor.portero traduccion [archivo]` exporta `uid_viejo,enenos_id` en CSV (sin usuarios ni claves).
  - `GET /cuentas/interno/enlaces` (protegido por `R2_CUENTAS_FICHA_INTERNA`) entrega `{"cuentas": [{usuario, uid}]}`.
  - `POST /cuentas/interno/cuenta` ya no acepta ni pide `uid`: recibe `{usuario, pass_sha256_upper}` y asigna el
    próximo Eñeños ID secuencial.
  - Los roles de `admin.txt` / `moderadores.txt` en `portero.py` se resuelven al Eñeños ID (por `usuario` en
    `cuentas.db`, o Eñeños ID numérico directo, con traducción transitoria desde `importadas` si quedó un número viejo).

- **En R2Beat (`servidor/`)**:
  - `esquema.py` + `almacen._migrar_esquema()` agregan `users.enenos_id INTEGER` e índice único parcial
    `idx_users_enenos_id ON users(enenos_id) WHERE enenos_id IS NOT NULL` sobre bases nuevas o existentes sin
    romper el arranque.
  - **Enlace inicial (`python -m servidor.enlazar_cuentas`)**: consulta `GET /cuentas/interno/enlaces`, empareja
    `users.username` exacto (`COLLATE BINARY`), rellena `users.enenos_id` preservando intacto `users.uid` (incluidos
    negativos de cuentas fusionadas), es idempotente, no imprime usuarios ni claves y devuelve código distinto de `0`
    si falla el HTTP, hay conflicto o queda alguna fila con `enenos_id IS NULL`.
  - **Login con pase (`R2_LOGIN=pase`)**: `almacen.asegurar_cuenta_uid` busca por `users.enenos_id = sub`. Si existe
    y está activa entra con su `users.uid` (`usn`, `< 10_000_000`, nunca con el Eñeños ID). Si no existe aún en el
    juego, crea la fila con `enenos_id = sub`, `pass_hash = ""`, `username` local `uid_<enenos_id>` y un `usn` local
    libre `< 10_000_000`. `api_web.iniciar_sesion` guarda ese `usn` real en `_sesiones[token]` y en `datos_sesion`.
  - **Panel admin y casillero 1**: todas las consultas y sincronizaciones internas (`_login_panel`, `_avisar_estado_cuenta`,
    `_clave`, `desban`, `buscar_usuarios`) usan `users.enenos_id` para hablar con Cuenta Eñeños; si falta el enlace lo
    informan claro y en `buscar_usuarios` una cuenta de Cuenta Eñeños que nunca entró al juego devuelve
    `uid: None, enenos_id: <eid>` sin buscar personaje inexistente. `separar_nueva` obtiene el próximo Eñeños ID de
    Cuenta Eñeños y lo guarda en `users.enenos_id`. Con la identidad separada del personaje, **`casillero1` queda
    habilitado con `R2_LOGIN=pase`** (sólo rota `users.uid`, mientras `users.enenos_id` no cambia nunca).

### Pasos del día del reemplazo (en orden)

1. **Copiar las cuentas (en sólo lectura desde `datos.db`)**: correr `python -m servidor.portero importar <ruta/datos.db>` con `R2_CUENTAS_DUENA=1` — asigna los Eñeños IDs secuenciales desde `10_000_000`, llena `importadas`, traduce `aprobados`/`baneos` en `portero.db` y limpia sesiones/pases viejos.
2. **Levantar Cuenta Eñeños**: iniciar el contenedor/servicio `cuentas` (`R2_CUENTAS_DUENA=1`, `R2_CUENTAS_FICHA_INTERNA`, clave Ed25519).
3. **Enlazar el juego**: sobre `datos.db` (con `R2_CUENTAS_URL` y `R2_CUENTAS_FICHA_INTERNA`), correr `python -m servidor.enlazar_cuentas` y verificar código de salida `0` (`sin_enlazar=0`).
4. **Prender `R2_LOGIN=pase` en el juego** (y `PARCHES_LOGIN=pase` en parches): reiniciar el contenedor `juego` para que web, launcher y lobby TCP validen pases usando `users.enenos_id`.
5. **Pasarle la traducción a EDA**: exportar `python -m servidor.portero traduccion traduccion_eda.csv` (`uid_viejo,enenos_id`, sin usuarios ni claves) para actualizar referencias externas que todavía usen el `uid` viejo de `datos.db`.

### Lo que queda pendiente

- Correr toda la batería de pruebas (`probar_cuenta_duena.py`, `probar_login_pase.py`, `probar_pase_y_fusion.py`, `probar_panel_y_cuentas.py`, `probar_enlazar_cuentas.py`) en un entorno con Python/terminal y repetir los guiones 9, 10 y 12 del ensayo.
- Revisar/limpiar `admin.txt` y `moderadores.txt` cuando corresponda para dejar sólo nombres de usuario o Eñeños IDs definitivos.

## 27 · El Eñeños ID prendido en el VPS de ensayo, y el sitio web con pases (15-nov-2026 · probado · nada en prod)

**El recorrido del día del reemplazo, hecho en el ensayo** (`_trabajo/ensayo_migracion/14_prender_enenos_id.sh`,
imágenes `:ensayo3`): copiar las cuentas → levantar Cuenta Eñeños → `python -m servidor.enlazar_cuentas` (dos
veces: la segunda no cambia nada) → prender `R2_LOGIN=pase`. Quedó: `prueba1` usn 1 · Eñeños ID 10000000 (y
`aprobados` de EDA traducido a ese número), `prueba2` y `prueba3` igual con los suyos.

| guion | qué prueba | resultado |
|---|---|---|
| 9 | pases por internet: juego, API, parches, cuenta nueva (Eñeños ID 10000003 → el juego le da el usn 4); los pedidos internos dan 404 desde afuera | 25 de 25 |
| 10 | el launcher de verdad: entrar, actualizar, JUGAR con el exe de prod hasta el lobby, registrarse, controles | 17 de 17 |
| 13 | lo mismo que el 14 pero EN LOCAL con la foto de prod (5.398 cuentas; sólo conteos; todo se borra) | 15 de 15 |
| 15 | el formulario «Mi cuenta» del sitio, en un navegador de verdad (Edge sin ventana) | 10 de 10 |

**El sitio web** tenía su propio login con usuario + contraseña contra la API, que con pases ya no entra. Ahora
`GET /api/sesion` le dice al sitio cómo se entra (`"entrar": "pase"`, sólo con `R2_LOGIN=pase`) y
`web/src/scripts/sesion.ts` hace: contraseña a `/cuentas/entrar` → `/cuentas/pase {juego: web}` → `/api/sesion
{pase}` → cierra la sesión de Cuenta Eñeños. El guion 15 mira los pedidos de la página: la contraseña viaja a un
solo lugar. El panel de administración usa el mismo `entrar()`.

**Publicadas el 15-nov en ghcr.io, PRIVADAS y sin repo enlazado** (comprobado con `gh api`), etiqueta `2026-11-15`,
para amd64 y arm64: `r2beat2013-juego`, `enenos-cuentas`, `r2beat2013-parches` y `r2beat2013-web` (las dos últimas,
por primera vez). La de la web costó 60 intentos fallidos: para arm64 bajaba un Node entero y la red de la PC de
desarrollo corta esa bajada; ahora el sitio se compila una sola vez (`FROM --platform=$BUILDPLATFORM`). Y el guion
de publicar ya no frena por una etiqueta `image.source` heredada de la imagen base de otro (Caddy): sólo si
apunta a un repo nuestro.

**Lo que sigue faltando para el reemplazo:**

- Una release de cliente DE VERDAD en el servidor de parches del ensayo (8 GB: de VPS a VPS; espera la orden de Eñeños).
- Una foto NUEVA de la base de prod para repetir el guion 13 con las fusiones reales (la de `legacy-server/` es del
  16-sep, anterior a las fusiones). Es leer prod: espera la orden de Eñeños.
- El número de versión del launcher nuevo (sigue diciendo 3.0.1) y dar vuelta su constante el día del reemplazo.
- EDA: pasarle la tabla de `portero traduccion` (número viejo → Eñeños ID) a quien lo maneje.
- La pestaña Cuentas del panel muestra `uid_<n>` como nombre de las cuentas nacidas con pase.
- El visto bueno de Eñeños, y recién ahí el plan de la subida (con respaldo, como manda `COMO_SE_SUBE_A_PROD.md`).

## 28 · La copia de prod del 15-nov, convertida a la forma nueva, en el VPS de ensayo (pedido de Eñeños)

> Eñeños (15-nov): «tener la copia completa de la db —hoy— y ya editada en la forma nueva de trabajo en el VPS de ensayo».

**De prod sólo se LEYÓ** (nada se escribió en `/opt/r2beat`, nada se reinició): un `.backup()` de SQLite de
`datos.db` y `portero.db`, de a trozos y a prioridad baja (0,5 s), a una carpeta de `/tmp` que se borró al terminar.
La bajada entera se corta siempre desde esta PC: se bajó en pedazos de 1 MB, cada uno con su md5.

- **La copia quedó en `_trabajo/respaldos/prod_2026-11-15/`** (fuera del repo): 6.730 cuentas, 6.670 personajes, 359
  casilleros extra, 1 fusionada (con su número en negativo), 6 baneadas; md5 idéntico al de Chile; `integrity_check` ok.
  ⛔ Es la única copia con los `pass_hash` reales: no va al repo.
- `panel.db` (298 MB: bitácora, IPs) **no** se trajo: no hace falta para esto.

**El paso que faltaba en la conversión — `python -m servidor.enlazar_cuentas vaciar-claves`:** después de copiar y
enlazar, la base del juego borra el SHA-256 de `users.pass_hash` y deja sólo la marca de estado (`BANNED:`,
`FUSIONADA:`); rearma el archivo (WAL asentado + `VACUUM`) para que no queden los bytes viejos. Sólo corre si todas
las cuentas tienen Eñeños ID y Cuenta Eñeños confirma que las tiene. ⛔ No tiene vuelta atrás sobre esa base: la
vuelta atrás es el respaldo de antes.

**Los pasos del día del reemplazo, como quedaron** (`_trabajo/ensayo_migracion/17_copia_de_prod_al_ensayo.sh`):

| # | paso | en el ensayo, con la copia de hoy |
|---|---|---|
| 1 | poner la base | la copia en el volumen del juego (lo de prueba quedó aparte, en `_ensayo_antes_1115_2157`) |
| 2 | `portero importar /juego/datos.db` | 6.730 copiadas en 341 s (6 baneadas, 1 fusionada); los 6 aprobados de EDA traducidos |
| 3 | levantar Cuenta Eñeños + `enlazar_cuentas` | 6.730 enlazadas, 0 sin enlazar |
| 4 | `enlazar_cuentas vaciar-claves` | 6.730 vaciadas |
| 5 | prender `R2_LOGIN=pase` y `PARCHES_LOGIN=pase` | los cuatro contenedores sanos (imágenes `:ensayo4`) |

**Comprobado** (`13_…` en local con la copia: 14 de 15, y el que falló era un falso positivo del control — una
cuenta cuyo nombre son sólo números; `18_verificar_la_copia_de_prod.py` contra el ensayo: 16 de 16):
las mismas 6.730 cuentas, cada una con el MISMO usn que en la copia y su Eñeños ID (10.000.000 a 10.006.729); los
mismos 6.670 personajes; en los bytes de la base del juego, su WAL y sus respaldos (descomprimidos) no aparece
ninguna de las contraseñas buscadas; las copias crudas de `/root` borradas; una cuenta de prueba nueva
(Eñeños ID 10.006.730 → usn 13.473) entra a Cuenta Eñeños, al juego, a la API y a parches con pases.

**Para tener en cuenta:**

- El ensayo quedó en internet con las cuentas reales: cualquiera puede entrar ahí con SU usuario y contraseña de
  siempre (el freno de intentos es el mismo de prod). No hay ningún GM ni ADMIN configurado en el ensayo.
- Lo que un jugador haga en el ensayo no existe en prod, y al revés: es una foto del 15-nov a las 18:48.
- ⚠ **Pendiente que apareció al leer el código:** borrar un personaje desde el selector de ADENTRO del juego
  (`FFF9`) pide la contraseña y la comprueba contra la base del juego; con pases ya no puede. Hay que hacer que
  esa comprobación la haga Cuenta Eñeños (un pedido interno más). Crear, elegir y cambiar de personaje no cambian.

## 29 · Lo que encontró Eñeños al entrar al ensayo con su cuenta (15-nov, a la noche)

Con el acceso «Launcher de ENSAYO» (`D:\Game\R2beatENSAYO_datos\Launcher de ENSAYO.bat`: el launcher nuevo con su
propia copia del cliente en `D:\Game\R2beatENSAYO` y sus propias preferencias; no toca el launcher ni el cliente de
siempre; `_trabajo/ensayo_migracion/19_probar_el_acceso_de_ensayo.py` lo prueba leyendo las variables del `.bat`).

| lo que vio | la causa | el arreglo |
|---|---|---|
| no aparecía el selector de personaje, y cambiar de canal daba «Imposible conectarse con el servidor» | el launcher le pasaba al exe el NOMBRE del server (sólo resolvía el de prod). El exe entra al login con un nombre, pero el selector y el cambio de canal guardan la dirección en 16 bytes: con `ensayo.xn--eeos-gqab.link` (25 letras) el juego ni le llegaba a preguntar al server | launcher (`juego.rs`, commit `a357e64c`): al exe SIEMPRE un número, sea el nombre que sea |
| borrar un personaje desde el selector de adentro: «contraseña incorrecta» | el `FFF9` pide la contraseña y la comprobaba contra la base del juego, que con pases ya no la guarda | pedido interno `comprobar-clave` en Cuenta Eñeños (con freno por cuenta) y el `FFF9` que le pregunta (commit `845a8e86`, `pruebas/probar_borrar_con_pase.py`, 22) |

Con su cuenta de verdad anduvo: entrar, el selector, elegir, crear y cambiar de personaje, cambiar de canal.

⚠ Dos cosas aprendidas: (1) las pruebas automáticas abren el juego EN LA PANTALLA de Eñeños con una cuenta de prueba
vacía: lo que vio como «mi selector sin personajes» era esa prueba; avisar antes de correrlas. (2) El reporte de
caída `0x5552C7` que manda el juego es el de SALIDA, preexistente e inofensivo (`CAJAS_NEGRAS_2026-10-22.md`): no
explica un cierre.

## 30 · EDA, quinta pieza del VPS de ensayo (15-nov-2026 · probado · nada en prod ni en el VPS de EDA)

> Eñeños: «fabriquemos el contenedor de EDA en el VPS de ensayo — ya vamos conectando más piezas».

EDA (Espada del Alma) es **otro juego y otro repo** (`r2beatlatino/EDA`; su server es Python y corre hoy en un VPS
de USA). **A su repo no se le tocó nada:** su imagen se arma con SU `despliegue/Dockerfile`, de la rama `main` (la
de su prod), y al armarse corre las pruebas de su server. Acá sólo se la enchufa.

| qué | dónde | cómo |
|---|---|---|
| el servicio `eda` | `herramientas/contenedores/docker-compose.yml` | con **perfil**: no arranca en un `docker compose up` común; se prende con `COMPOSE_PROFILES=eda`. Publica TCP 25900 (el juego) y el relay UDP (un puerto por jugador). Su estado, en el volumen `eda_estado` |
| el login | `EDA_LOGIN=pase` + `EDA_PORTERO_CLAVES=https://<sitio>/cuentas/clave-publica` | EDA comprueba el pase solo, con la clave pública de Cuenta Eñeños (⛔ sólo la acepta por `https` o de un archivo). La cuenta de EDA es `r2b_<Eñeños ID>` |
| el canje del pase | `Caddyfile`: `/eda/*` → `eda:25901` | el puerto 25901 NO se publica: sale sólo por Caddy, con https (el ticket que devuelve es un secreto) |
| la lista del cliente | `Caddyfile`: `/eda/manifiesto.jws` (estático, sin caché, de `EDA_WEB_ORIGEN`) | es la lista de archivos del cliente de EDA, **firmada**; trae a qué server y a qué canje va |
| la puerta | `manifiestos/eda.json` en el volumen de cuentas | `GET /cuentas/manifiesto/eda` da 200 sólo a una cuenta aprobada para EDA |

**La firma, en el ensayo.** El launcher de verdad sólo acepta la lista firmada por EDA (su clave privada vive en el
VPS de USA y no se trajo). Para el ensayo: `21_manifiesto_eda_ensayo.py` baja la lista de verdad (es pública), le
cambia `servidor` (el número del ensayo) y `canje`, y la firma con una **clave sólo de ensayo** (la privada no sale
de esta PC). El launcher de ensayo se compila con `--features ensayo` (rama `launcher-tauri`, `a5aada5c`) y recibe
esa clave pública por `R2_EDA_CLAVES_PRUEBA`; el que se publica no tiene esa opción.

**En el ensayo** (`22_prender_eda.sh`): imagen `eda-server:ensayo` (EDA `main` `a28fe16`), web `:ensayo6`, relay
de 26000 a 26040 (`EDA_MAX_CONEXIONES=40`). R2Beat, cuentas y parches no se reiniciaron.

| guion | qué prueba | resultado |
|---|---|---|
| 23 | por internet, sin abrir juegos: la prueba del propio EDA contesta; el canje por https y el 25901 cerrado; el manifiesto verifica sólo con la clave de ensayo; cuenta nueva → sin aprobar no hay pase → se la aprueba → pase `eda` a nombre de su Eñeños ID → EDA lo canjea por su ticket; ⟲ pase repetido, pase de otro juego, firma tocada | 18 de 18 |
| 24 | el launcher de ensayo: acepta la lista y ve el cliente al día (`D:\Game\EDA`); ⟲ sin aprobar «sin acceso»; ⟲ sin la clave de ensayo la rechaza | 6 de 6 |

**Lo que NO se probó todavía:** entrar al juego de EDA de verdad (abrir `EDA_limpio.exe` con el ticket) y jugar
entre dos PCs por el relay. **Lo que falta decidir:** los personajes de EDA de prod (`/opt/eda/estado-prod` en el
VPS de USA) se llaman `r2b_<número viejo>`; con el Eñeños ID pasan a `r2b_<Eñeños ID>`. Para llevarlos hay que
renombrarlos con la tabla de `portero traduccion`. En el ensayo EDA arrancó vacío (Eñeños: «EDA es beta, todo se
puede rehacer»).

## 31 · EDA se adapta a nuestro diseño (15-nov-2026, a la noche · probado en el ensayo)

> Eñeños: «puedes rehacer la forma como se conecta, para que se adapte a nuestro diseño y no nosotros a él. Total
> libertad, porque es beta y se puede rehacer.»

En la §30 EDA quedó enchufado **tal cual era**, y lo nuestro se acomodó alrededor. Esto es lo que se dio vuelta:

| antes (a la manera de EDA) | ahora | dónde |
|---|---|---|
| la lista del cliente la firmaba EDA con SUS claves (la privada, en su VPS), y esas dos claves estaban en el launcher. Para el ensayo hubo que compilar un launcher aparte (`--features ensayo`) | **una sola autoridad: las claves de PUBLICACIÓN de la plataforma** (actual y reserva). Firman la lista de cualquier juego, en prod o en un ensayo. El launcher de ensayo es el mismo exe que se publica | launcher `eda.rs` `CLAVES_DE_PUBLICACION` (rama `launcher-tauri`, `eff0c5c7`). Las de EDA siguen aceptadas hasta el día del reemplazo |
| EDA sólo recibía la clave de las cuentas por un JWKS (https o archivo) | la recibe **por configuración, con la misma variable que R2Beat** (`R2_CUENTAS_CLAVE_PUBLICA` → `EDA_CUENTAS_CLAVE_PUBLICA`): no sale a la red para arrancar ni para comprobar un pase | repo de EDA, rama local `cuenta-enenos` |
| la cuenta de EDA era `r2b_<número de R2Beat>` | `en_<Eñeños ID>` (`EDA_PREFIJO_CUENTA`; por omisión sigue `r2b_`) | ídem |

- **Las claves de publicación** viven en una carpeta privada de la PC de Eñeños (`ENENOS_CLAVES`; fuera de todo repo y de todo VPS):
  `publicacion_actual.pem` (kid `140674dc24472102`), `publicacion_reserva.pem` (kid `ad9f8409624a111a`; conviene
  moverla a un pendrive) y las dos públicas. Con la actual se firmó la lista del ensayo (`21_manifiesto_eda_ensayo.py`).
- **La rama `cuenta-enenos` del repo de EDA** está sólo en `_trabajo/eda_repo/` (2 commits sobre `develop`): **no se
  subió a GitHub** (ese repo es público y lo trabajan otras personas: el momento lo decide Eñeños). Las pruebas de
  su server: 322 bien, 9 nuevas, cada una con su revés.
- **En el ensayo:** imagen `eda-server:ensayo2` (de esa rama). Guion 23: 19 de 19 (el ticket sale para `en_<Eñeños
  ID>`). Guion 24, con el launcher común: 6 de 6.

**Lo que sigue dado vuelta a medias** (los próximos pasos): el cliente de EDA todavía se reparte por su lado (su
CDN, su `manifiesto.jws`, la «puerta» `manifiestos/eda.json`) en vez de salir del servicio de parches como el de
R2Beat; y en el launcher EDA sigue siendo un bloque de código aparte (`eda.rs`) en vez de una ficha.

## 32 · El diseño: cada juego corre DOS servers, y el launcher elige (decisión de Eñeños, 15-nov-2026)

> Eñeños: «los contenedores de X juego correrán 2 servers, uno de prod y otro de develop. En el develop mis amigos
> podrán hacer PR y el contenedor se autoactualiza cada 5 minutos, como ya estaba haciendo EDA; la versión prod sí
> requiere mi aprobación. En el launcher, en la configuración del juego, una opción "test server" para marcar y
> jugar. Así podremos trabajar libremente en develop, romper las cosas sin temor.»

| | **prod** | **prueba** (test server) |
|---|---|---|
| rama del repo del juego | `main` | `develop` |
| quién lo cambia | sólo con la aprobación de Eñeños | los amigos, por PR a `develop` |
| cuándo se actualiza | cuando Eñeños lo aprueba | solo, a los ~5 min de cada cambio en `develop` (y sólo si las pruebas del server pasan) |
| sus datos | los de verdad | **los suyos, aparte**: romper el de prueba no toca nada de prod |
| las cuentas | Cuenta Eñeños (las mismas personas) | Cuenta Eñeños (las mismas personas) |
| en el launcher | lo de siempre | la casilla «Servidor de prueba» en la configuración de ese juego |

⚠ Esto **corrige** lo que decía la primera tabla de la respuesta a Eñeños: la auto-actualización de EDA no se saca;
se queda para el server de prueba. Lo que requiere aprobación es prod.

**Lo que hay que construir (nada de esto está hecho):**

1. **En el conjunto:** cada juego pasa de un servicio a dos (`<juego>` y `<juego>-prueba`), cada uno con su
   volumen y sus puertos. EDA ya lo hace así en su VPS (25900 / 35900, relay 26000 / 36000).
2. **En Cuenta Eñeños:** el server de prueba es «otro juego» para el pase (`eda-prueba`, `r2beat2013-prueba`): un
   pase de prod no sirve en prueba ni al revés, y la lista de quién puede entrar al de prueba es propia.
3. **La auto-actualización del de prueba:** EDA ya la tiene (`despliegue/actualizar.sh` + cron: arma la imagen
   nueva, corre las pruebas y sólo reemplaza si pasan). ⚠ R2Beat es distinto: su repo público no alcanza para armar
   la imagen (faltan el exe, los charts y las tablas), así que hay que resolver de dónde sale lo privado.
4. **En el launcher:** la ficha de cada juego trae sus dos entornos, y la casilla elige. Por decidir: si el server
   de prueba usa el MISMO cliente instalado o una copia aparte (si `develop` trae paks o una dll distintos, tiene
   que ser aparte).
5. **prod con aprobación:** definir qué es «aprobar» en concreto (que Eñeños fusione a `main`, o que además apriete
   algo para que suba). ⛔ En R2Beat subir a prod reinicia el server y corta a los que están en carrera: el momento
   lo sigue eligiendo él.

## 33 · Dónde quedó todo al cierre del 15-nov-2026 (para retomar sin adivinar)

**Lo último que se hizo esa noche** (pedidos de Eñeños, probados en el ensayo):

- **EDA: quien entra por primera vez nace SIN personajes** y los crea él en el juego («Eñeños ID da pase a EDA,
  pero sin chars creados»). Variable `EDA_CUENTA_NUEVA` (`vacia` por omisión en el conjunto; `personaje` = lo de
  antes). Rama local de EDA `cdd39a9`, compose `13991f41`, imagen `eda-server:ensayo3`. Eñeños entró al juego de EDA
  con su cuenta y creó la suya (`en_10006659`).
- **Launcher: JUGAR se puede apretar aunque la cuenta no tenga personajes** («los chars en el launcher son
  informativos; la gestión está dentro del juego; si no, los nuevos no pueden entrar»). Rama `launcher-tauri`
  `878a8fa5`; el botón depende de la sesión, no de los personajes. `prueba_tablero.py` 72 (su control falla con el
  código viejo) y guion 27 del ensayo (cuenta recién registrada → botón prendido).
- En `D:\Game\EDA` se apagaron los arreglos de Eñeños (`eda_d3d9.ini` → `[rui] activo=0`; el original quedó en
  `eda_d3d9.ini.con_rui_prendido`).

**Las ramas** (ninguna subida a GitHub; nada en prod):

| rama | dónde | último commit |
|---|---|---|
| `claude/topologia-docker-99488b` | worktree `affectionate-torvalds-1c438f` | este documento (§21–§33) |
| `launcher-tauri` | worktree `launcher-tauri` | `878a8fa5` · el exe release mide md5 `471b1216…` |
| `cuenta-enenos` (repo de EDA) | `_trabajo/eda_repo/`, sobre `develop` | `cdd39a9` (3 commits; pruebas de EDA 328 bien) |

**El VPS de ensayo** (`103.90.160.237`, `/opt/enenos`, `ensayo.eñeños.link`), las cinco piezas sanas:
cuentas `enenos-cuentas:ensayo5` · juego `r2beat2013-juego:ensayo5` · parches `r2beat2013-parches:ensayo4` · web
`r2beat2013-web:ensayo6` · eda `eda-server:ensayo3`. Corre la copia real de prod del 15-nov convertida (~6.740
cuentas con Eñeños ID; último 10006745). `.env`: `R2_CUENTAS_DUENA=1`, `R2_LOGIN=pase`, `PARCHES_LOGIN=pase`,
`COMPOSE_PROFILES=eda`, `EDA_LOGIN=pase`, relay 26000–26040, release activa `ensayo_r0` (vacía), launcher anunciado
`ensayo-3.1`. Resguardos `.env.antes-*`. En ghcr.io están las cuatro nuestras con etiqueta `2026-11-15` (privadas).

**En esta PC:** acceso «Launcher de ENSAYO» del Escritorio → `D:\Game\R2beatENSAYO_datos\` (el `.bat` +
`LauncherEnsayo.exe`, que NO se auto-actualiza: se reemplaza a mano) y el cliente en `D:\Game\R2beatENSAYO`.
⚠ Al cierre, el `LauncherEnsayo.exe` instalado era el anterior (`f6fb245e`): falta ponerle el `471b1216` (JUGAR
sin personajes) cuando Eñeños lo tenga cerrado. Respaldo de prod del 15-nov en `_trabajo/respaldos/prod_2026-11-15/`
del repo principal (⛔ trae los `pass_hash` reales).

**Lo que falta, en orden de importancia:**

1. **Cada juego, dos servers** (§32), empezando por EDA: servicios `<juego>` / `<juego>-prueba`, pase con
   `aud=<juego>-prueba`, auto-actualización del de prueba, casilla «Servidor de prueba» en el launcher. Eñeños tiene
   que decidir: qué es «aprobar prod»; si el de prueba usa el mismo cliente o una copia; de dónde sale lo privado de
   R2Beat para armar su imagen de prueba sola.
2. **EDA a medio dar vuelta** (§31): su cliente todavía se reparte por su CDN y no por nuestro servicio de parches,
   y en el launcher sigue siendo un bloque aparte (`eda.rs`) en vez de una ficha.
3. **Sin probar todavía:** una cuenta nueva que aprieta JUGAR → selector vacío → crea su primer personaje de punta a
   punta en R2Beat; una partida de EDA entre dos casas por el relay. Sin explicar: el cierre raro de la primera
   sesión de R2Beat de Eñeños en el ensayo (no se repitió).
4. **Del launcher, anotado para después:** botón INSTALAR por juego, elegir y recordar la carpeta, «¿ya está
   instalado?»; chat y campana; noticias/torneo/supporters escondidos; logo; número de versión (sigue en 3.0.1).
5. **Decisiones de Eñeños:** subir la rama `cuenta-enenos` al repo de EDA; publicar todo y el día del reemplazo
   (pasos en §26–§28); mover `publicacion_reserva.pem` a un pendrive; renovar («Roll») el token de Cloudflare.

### 33.1 · Lo que decidió Eñeños sobre los dos servers (15-nov, después del cierre)

- **prod = rama `main`**, y es lo que abre **JUGAR** mientras la casilla «test server» de ese juego esté apagada.
- **Un solo cliente instalado para los dos.** No dos copias: en la CDN hay **dos listas** (la de prod y la de
  prueba) que apuntan a los mismos archivos guardados una sola vez por su huella (hash). Al marcar o desmarcar la
  casilla, el launcher compara su carpeta con la otra lista y baja **sólo lo que cambia** (normalmente un par de
  archivos). Las listas pueden vivir en git: cada cambio de lista es un commit.
- Las dos claves de publicación se quedan, por ahora, en su PC.
- Sin decidir todavía: de dónde sale lo privado de R2Beat (exe, charts, tablas) para armar solo el server de prueba.
- ★ **Corrección (lo marcó Eñeños):** lo privado de R2Beat **ya estaba resuelto** en el repo público
  `r2beatlatino/R2beat-2013` desde el 11-nov. Su `despliegue/` corre los dos entornos con un solo compose: prod
  (`master`, se actualiza a mano) y prueba (`develop`, `actualizar.sh` por cron cada 5 min, puertos +1000). La
  imagen corre `pruebas/probar_login.py` al armarse: si falla, no se arma y sigue el contenedor anterior. Las
  tablas, las notas y `shop_lt.txt` (de Softnyx) **no van en la imagen**: se suben una vez a una carpeta del VPS
  (`/opt/r2b2013/juego/`) y se montan sólo lectura; `arrancar.sh` las copia sin pisar las nuestras. Para el
  conjunto nuevo se copia ese modelo. ⚠ La rama de prod se llama `master`, no `main`. ⚠ Ese repo quedó en el
  12-nov: no tiene pases ni Eñeños ID; refrescarlo (`publicar_2013.py`) lo decide Eñeños.
- ✅ **Probado por Eñeños (15-nov, noche):** con el Launcher de ENSAYO nuevo (`471b1216`) y una cuenta sin
  personajes, JUGAR se prende, entra al juego y crea sus personajes normalmente. Se cierra el «sin probar» de la
  §33 punto 3 para R2Beat (queda la partida de EDA entre dos casas).
- ✅ **Repo público actualizado (orden de Eñeños, 15-nov ~23:30):** `r2beatlatino/R2beat-2013` master = develop =
  `97ca743`, pruebas de GitHub en verde (server + Docker). Ya trae los pases y el Eñeños ID (apagados por omisión)
  y las variables de Cuenta Eñeños en su `despliegue/`, así que el server de prueba armado desde `develop` puede
  usar Cuenta Eñeños. Para eso `pase.py` dejó de importar `portero.py` (`9d69f332`): cada juego comprueba el pase solo.

## 34 · Los dos servers de R2Beat, armados en el VPS de ensayo (16-nov-2026, pedido de Eñeños · probado · nada en prod)

> Eñeños: «arma los 2 servers en el VPS de ensayo».

```
                       ┌── pase aud=r2beat2013 ──────────► r2beat2013          (prod: login 47004 adentro, canales 48005…48095)
launcher / exe ─► :48004 PUERTA
                       └── pase aud=r2beat2013-prueba ───► r2beat2013-prueba   (develop del repo público: login 49004, canales 49005…49095)
```

**El problema que resuelve la puerta:** el exe entra SIEMPRE por el 48004 (el puerto que le pasa el launcher no lo
usa); sólo los canales siguen al server (los aprende del FF02). Dos servers en una máquina chocaban ahí. En vez de
tocar el exe, el 48004 lo atiende `herramientas/contenedores/puerta/puerta_login.py` (Python puro, imagen
`enenos-puerta`): lee el primer paquete de cada conexión y la pasa entera.
- Con un pase (el launcher): mira el `aud` (sin comprobar la firma; eso lo hace el server). `-prueba` → prueba, y
  anota el `(usn, permiso)` que contesta el de prueba.
- El `FF01` del exe (12 bytes `[usn][permiso]`): va adonde se anotó ese par. El permiso es al azar de 62 bits, así
  que el mismo usn en las dos bases no se confunde. Lo demás (o lo desconocido) → prod.
- Lo anotado se guarda en `/datos/mapa.json` (volumen `puerta_datos`): reiniciar la puerta no saca a nadie.
- El server ve la IP de la puerta sólo en el LOGIN (la usa para el log); los canales van directo.

**Las piezas:**

| | qué | dónde |
|---|---|---|
| pase propio | `R2_PASE_JUEGO` (`pase.juego()`): cada server acepta sólo su `aud`. Cuenta Eñeños da `r2beat2013-prueba`, abierto a toda cuenta activa | `servidor/pase.py`, `lobby.py`, `cuenta_personajes.py`, `portero.py` (también en el repo público, `develop` `5dba98c`) |
| el nombre público por la puerta | `R2_NOMBRE_PUBLICO_PUERTO=48004`: prod escucha en 47004 adentro pero se comprueba por afuera | `servidor/nombre_publico.py` |
| el conjunto | servicios `puerta` y `r2beat2013-prueba` con el perfil `prueba`; el login de prod configurable (`JUEGO_LOGIN_PUERTO`, `JUEGO_LOGIN_PUBLICAR`) | `docker-compose.yml`, `ejemplo.env` |
| se actualiza solo | `actualizar_prueba.sh` por cron cada 5 min: si `develop` cambió, arma la imagen con el Dockerfile DEL REPO (corre sus pruebas: si fallan no se arma y sigue el anterior) y recrea sólo el de prueba | `/opt/enenos/actualizar_prueba.sh`, log en `/opt/enenos/prueba/actualizar.log` |
| ★ la dll, sola (21-nov) | `dll_prueba.py`, desde `actualizar_prueba.sh` en cada vuelta: si cambió la `exe/d3d9.dll` de `develop` y la prueba «dll» de GitHub de ESE commit dio verde (GitHub compila el fuente con Zig 0.16.0 y tiene que dar exacto esa dll), arma `<prod>-dll<commit>` = la lista de prueba vigente + esa dll, con la maquinaria de las subidas (enlaces duros, historial, «volver» en el launcher). Sin reiniciar nada. ⚠ Mientras haya historial de subidas, `PARCHES_RELEASE_PRUEBA` del `.env` sólo es la BASE: la vigente es la de `_subidas/estado.json` | `/opt/enenos/dll_prueba.py`, estado en `/opt/enenos/prueba/dll_estado.json`, log en `prueba/actualizar.log`; prueba: `pruebas/probar_dll_prueba.py` |
| lo privado | las tablas, notas, `music_lt.txt` (dentro de `tablas-cliente/`) y el exe prístino en una carpeta de la máquina, sólo lectura | `/opt/enenos/prueba/juego` (`PRUEBA_JUEGO_DIR`) |
| el launcher | casilla «Servidor de prueba» (naranja cuando está marcada): cambia SÓLO el pase de JUGAR. Mismo exe, mismo cliente | rama `launcher-tauri` `5b976b8e` (exe md5 `debb07fc…`, instalado en el Launcher de ENSAYO) |

**Probado:** `probar_puerta_login.py` 16 (con reveses: mismo usn con otro permiso, sin el archivo, prueba apagado);
`probar_login_pase.py` §0b (prod rechaza el pase de prueba y al revés); por internet, guion 30: 16 de 16 (los dos
pases entran por el mismo 48004; el exe de cada uno recibe SUS 10 canales y ninguno del otro; 47004 y 49004 cerrados
desde afuera; prod adopta su IP por la puerta; el de prueba corre lo último de develop; el cron está). Guion 31 con el
launcher de verdad: 6 de 6 (la casilla se ve, arranca desmarcada, se guarda, sobrevive a reabrir). EDA sigue 19/19.
Las 6.730 cuentas de la copia de prod siguen intactas (el guion 18 da rojo sólo porque se sumaron 13 cuentas de prueba).

**Sin probar todavía:** apretar JUGAR con la casilla marcada y jugar de verdad en el de prueba (lo prueba Eñeños).

**En el VPS:** imágenes `r2beat2013-juego:ensayo6`, `enenos-cuentas:ensayo6`, `enenos-puerta:ensayo6`,
`r2b2013-server:prueba` (etiqueta `enenos.commit`). `.env`: `COMPOSE_PROFILES=eda,prueba`, `JUEGO_LOGIN_PUERTO=47004`,
`JUEGO_LOGIN_PUBLICAR=127.0.0.1:47004`, `JUEGO_NOMBRE_PUBLICO_PUERTO=48004`. Guion `/root/prueba/29_prender_prueba.sh`;
**vuelta atrás:** `bash /root/prueba/29_prender_prueba.sh volver` (resguardos `.env.antes-prueba`,
`docker-compose.yml.antes-prueba`).

**Lo que falta / por decidir:**
- **La lista del cliente de prueba en la CDN** (§33.1: un cliente, dos listas): hoy el de prueba usa la misma release
  que prod. Hace falta cuando `develop` traiga paks o una dll distintos.
- **Los personajes que muestra el launcher** salen de la API de prod aunque la casilla esté marcada (son
  informativos; en el juego se ve lo del de prueba).
- **GM/ADMIN en el de prueba:** su base es aparte, nadie es GM ahí todavía (`gm.txt` va en su volumen de datos).
- **Prod = `master`**: el server de prod del ensayo sigue saliendo de la rama privada (con el panel, la API, etc.), no
  del `master` público. Unir las dos («una sola copia») es la mudanza pendiente del repo público.
- La misma forma para EDA (`eda` / `eda-prueba`).

**Lo que encontró Eñeños al jugar en el de prueba (16-nov) — los dos eran de la PUERTA:**
1. *«No me mandó al char select»*: el HOLA del selector (`FFF6`, de la dll) lleva la SESIÓN adelante, no un pase, y
   caía en prod. Además, ELEGIR/VOLVER (`FFF8`/`FFFA`) abren otra sesión en medio de la conexión. Ahora la puerta
   reconoce la sesión en `FFF6`…`FFFB` y anota toda sesión que da prueba (`5e28ce87`, `puerta:ensayo7`).
2. *«Al cambiar de canal se quedó en "nos estamos conectando..."»*: el exe le SUMA 10 al permiso en cada re-login
   (`…90cc` → `…90d6`). La puerta buscaba el exacto. Ahora usa la misma regla que el server
   (`basedatos._mismo_vcode`: +10, hasta 64 veces) (`9997e9d7`, `puerta:ensayo8`). Guion 30: 17 de 17.
⚠ Lección: la puerta tiene que entender del protocolo del login TODO lo que entiende el server para decidir de quién
es una conexión. Si se agrega otra orden con la sesión adelante, va también en `CON_SESION`.

## 35 · La prueba «de verdad»: el cliente y el server de PRUEBA distintos de prod (16-nov-2026, pedido de Eñeños)

> Eñeños: «quiero una prueba de que realmente funcione la lista de la CDN: el test server con la isla de nieve y
> prod el estado actual; si no se subió el cliente al ensayo, lo subes. Que el test server y el cliente del test
> server sean diferentes: le añades cambios a ambos».

**El cliente real en el ensayo.** La release de prod `r2beat2013_2026-11-15` se bajó al VPS de ensayo de la CDN
pública (como un jugador que instala; su `manifest.json` también es público): 2.555 archivos, 8,5 GB, en 37 s (la
CDN la tenía en caché), **cada archivo con su md5 comprobado** contra la lista de prod. `/opt/enenos/releases/`.

**La release de prueba** `r2beat2013_2026-11-15-nieve` = la de prod con **enlaces duros** (no ocupa: 8,0 GB las dos)
+ la isla de NIEVE en `rnr_ui_bg_isla_hw.pak`. La isla sale del propio cliente (`rnr_ui_bg/weimarpark_winter`, la
misma animación que la isla del lobby) puesta en `rnr_ui_bg/front/` (`_trabajo/isla_nieve_prueba/armar.py`, el de
`_trabajo/isla_invierno/` del 30-sep con otro nombre de salida). Va con el MISMO nombre de archivo que la isla de
noche de prod a propósito: así el launcher cambia una por la otra en las dos direcciones (el launcher no borra
archivos que sobran: un pak aparte quedaría puesto al volver a prod). ⛔ Con enlaces duros, para cambiar un archivo
se BORRA el enlace y se pone otro: escribir encima cambiaría también el de prod (el guion 32 lo comprueba).

| | isla de noche (prod) | isla de nieve (prueba) | diferencia |
|---|---|---|---|
| `rnr_ui_bg_isla_hw.pak` | 4.650.023 B (`eacefe8c`) | 4.447.141 B (`b483c5a8`) | **−202.882 B (−4,4 %)** |

Lo que baja el launcher al marcar o desmarcar la casilla: ese UN archivo (4,4 MB / 4,2 MB). Lo demás es igual.

**Las dos listas.** El servidor de parches sirve `GET /manifest` (prod, `PARCHES_RELEASE_ACTIVA`) y
`GET /manifest?canal=prueba` (`PARCHES_RELEASE_PRUEBA`; vacía = la de prod). El launcher (`4ea1ced1`) pide la de
prueba con la casilla marcada y, al cambiarla, vuelve a revisar el cliente (`revisar_lista`): lo que cambia se baja al
tocar JUGAR. Probado: `probar_parches_dos_listas.py` 12 (8 fallan con el server viejo); guion 33 por internet 9/9.

**El server distinto.** `R2_AVISO_TIRA`: un aviso fijo que va primero en la tira del lobby (no es una fila de la
base: el panel no lo ve). El de prueba lo trae en el compose («SERVIDOR DE PRUEBA - lo nuevo de develop…»). El código
llega al de prueba por `develop` del repo público y la auto-actualización del cron (§34).

⚠ La cuota del servidor de parches del ensayo es 1.500 MB por permiso: una instalación desde cero (8,5 GB) no entra.
En prod no pasa porque los archivos salen de la CDN sin permiso (`PARCHES_URL_ARCHIVOS`).

## 36 · Los amigos SUBEN archivos del cliente al server de prueba (16-nov-2026, pedido de Eñeños · probado en el ensayo)

> Eñeños: «arma el botón para que mis amigos suban archivos, y que sólo los autorizados, tipo EDA, puedan subir
> directamente; que otros tengan que ser aprobados, así como las PR que abran otras personas, por ser público».

**Cómo se usa (launcher → Configuración → «SERVIDOR DE PRUEBA · SUBIR ARCHIVOS»):**
1. El amigo cambia archivos en SU carpeta del juego y los prueba ahí.
2. «Subir archivos del cliente…» → elige esos archivos (sólo de adentro de la carpeta del juego) → escribe qué cambia
   (como la descripción de un PR) → Enviar.
3. **Autorizado** → entra en el acto a la lista del server de prueba. **Cualquier otro** → queda «esperando
   aprobación» hasta que un autorizado lo apruebe o lo rechace desde la misma pantalla (ve la nota, los archivos y,
   en rojo, si trae ejecutables).
4. Quien tenga «Servidor de prueba» marcado lo baja al tocar JUGAR. Prod no se toca nunca.

**Quién es autorizado:** el permiso cerrado `r2beat2013-subir` de Cuenta Eñeños, que se aprueba por cuenta igual que
EDA: `docker compose exec cuentas python -m servidor.portero aprobar <usuario> r2beat2013-subir` (y `quitar`). En el
ensayo están aprobadas las dos cuentas de Eñeños (Eñeños ID 10000570 y 10006659).

**Cómo está hecho:** `herramientas/contenedores/parches/subidas.py` + `POST /subidas/{archivo,enviar,lista,revisar,
descartar}` en el servidor de parches (con su permiso de descarga; el de autorizado viaja como pase
`r2beat2013-subir`, de un solo uso, de la MISMA cuenta). Cada archivo se guarda una vez por su md5
(`<releases>/_subidas/blobs/`). Aplicar = una release de prueba NUEVA (`<prod>-p<n>`, nunca se reusa un nombre) con
enlaces duros sobre la de prueba vigente; `_subidas/estado.json` recuerda cuál es (si cambia prod, vuelve a la de la
configuración: lo subido se armó sobre la vieja). Topes: 300 MB por archivo, 1 GB por envío, 5 pendientes por cuenta.
⚠ Los archivos de las releases tienen que ser del usuario del contenedor (uid 10013): Linux no deja hacer enlaces
duros de archivos ajenos (`chown -R 10013:10013 /opt/enenos/releases`).

**Probado:** `probar_subidas.py` 28 (rutas tramposas, pendiente, quién aprueba —⟲ sin pase, con otro pase, con el
pase de otro—, aplicar sobre la anterior, directo, rechazar, topes, reinicio, prod y la release anterior intactas).
Por internet, guion 34: 14 de 14 (una cuenta común sube y queda pendiente; una autorizada de prueba la ve, la aprueba y
sube directo; al final se le quita el permiso). Launcher `9932c22f` (exe `39744cb8`), `prueba_tablero` 72.
Quedó en la lista de prueba un `LEEME_SERVIDOR_DE_PRUEBA.txt` (la prueba): quien marque la casilla lo baja.

**Lo que falta:** borrar un archivo desde una subida (hoy sólo se agregan o reemplazan); que lo aprobado sobreviva a
un cambio de la release de prod (rearmar prueba = prod nueva + lo aprobado); un tope de disco general; ver la
diferencia de un archivo antes de aprobar; y en prod, Cloudflare corta los pedidos de más de 100 MB (subir por el
nombre sin nube, o en pedazos).

## 37 · Subir archivos, segunda vuelta: botones propios, VOLVER ATRÁS y el JUEZ (16-nov-2026, pedido de Eñeños · probado en el ensayo)

Eñeños, después de subir la isla y la sala de Halloween (envío #3, entró bien): «que test server tenga su propio
botón; que subir archivos tenga su propio menú desplegable hacia la derecha; que si algo no gustó se pueda volver al
estado anterior, o hasta 5 estados pasados; y pruebas de seguridad para que no puedan subir malware o archivos
malintencionados: un juez que valide los archivos, que sea barato».

**Launcher** (`28626a0e`):
- «Servidor de prueba» deja la Configuración: botón propio al lado (APAGADO / PRENDIDO, naranja).
- «Subir archivos» abre su menú hacia la derecha: elegir (de cualquier carpeta, `0c8eadb6`), nota, avance; los
  **estados** del server de prueba con «↶ Volver a este estado» (autorizados); los envíos con las alertas del juez.
  El numerito del botón = lo que espera mi aprobación. Aprobar algo con programas pide confirmación.
- Defensa de más: `parches::entradas` descarta rutas inseguras de la lista. ⚠ `carpeta.join(ruta)` con una ruta
  ABSOLUTA reemplaza la carpeta entera: una lista con `C:\Windows\x.dll` habría escrito ahí.

**Server de parches** (`juez.py` nuevo, `subidas.py`, `patchserver.py`; imagen `r2beat2013-parches:ensayo7`):

| riesgo | lo que hay |
|---|---|
| un programa o script cualquiera | **el juez**: sólo entran extensiones que el cliente usa; `.bat .ps1 .lnk .vbs .js .msi …` nunca |
| un programa DISFRAZADO (`fondo.png` que es un .exe) | el juez lee la cabeza: `MZ` en un recurso = rechazo; cada imagen/sonido tiene que tener SU firma (BM, DDS, OggS, ID3…) |
| un .pak trucho o con un programa adentro | el juez lee la TABLA del .pak (la cola, no el archivo entero): tiene que encuadrar, nada que salga para afuera, ninguna `.exe/.dll` adentro |
| una dll/exe/ini (que sí hacen falta a veces) | entran como **sensibles**: nunca directo, ni para un autorizado; las aprueba **OTRO** autorizado (dos llaves). El juez avisa si un .ini apunta a la RED (`\servidor\…`, `http://`) o nombra dlls |
| trampas de Windows en el NOMBRE | `x.dll.` / `x.dll ` (Windows borra el punto y queda `.dll`), `nul`/`com1` (dispositivos), `~` (nombre corto 8.3 de OTRO archivo), `:` (flujos NTFS): 400 |
| `Pack/X.pak` y `pack/x.pak` (en Windows, el mismo archivo) | se guarda con las letras que ya tiene la lista |
| firmar como otro | el nombre lo pone el SERVER (el del pase de Cuenta Eñeños); el `quien` del launcher se ignora. ⚠ Antes de esto el envío #3 quedó firmado con el LOGIN (privado) |
| llenar el disco / spamear | 5 GB en total para subidas (`PARCHES_SUBIDA_TOTAL_MAX_GB`), 400 archivos por hora por cuenta, y lo rechazado o fuera del historial se borra solo |
| algo malo YA entró | **volver atrás**: el historial guarda la vigente + 5, cualquier autorizado vuelve a una (y se puede deshacer). **Interruptor**: `touch /opt/enenos/releases/_subidas/apagado` y nadie sube ni envía (volver sigue andando) |

El **control** del juez: los 2.559 archivos del cliente de verdad (`D:\Game\R2beatENSAYO`) pasan, en 0,7 s. ⚠ La primera
versión rechazaba 35 paks reales: tienen nombres en coreano/chino adentro (la tabla no es ASCII). Sin el control no se
veía.

⚠ **Lo que un juez barato NO hace:** probar que un archivo es inofensivo. Un .pak bien formado puede traer contenido
feo, y una dll aprobada puede ser un virus. Por eso es UNA capa de cinco: juez + aprobación (dos llaves para programas)
+ historial para volver + interruptor + topes. Lo que se podría sumar si hace falta: consultar el md5 de los programas
en VirusTotal (sólo el hash, gratis, ⚠ es mandar algo afuera: decisión de Eñeños) o un ClamAV (≈1 GB de RAM: no es
barato para este VPS).

**Probado:** `probar_subidas.py` 86 (los ataques en las secciones 8 a 14, cada uno con su revés) + dos listas,
portero, cuenta dueña, login con pase en verde; `cargo test` 20 (con `prueba_rutas`). Por internet, guion 35:
17 de 17 (juez, nombre, dos llaves, volver; deja la lista como estaba: el Halloween de Eñeños, `p3`).

### 37.1 · Las reglas de la cola y PROBAR cualquier envío (16-nov, Eñeños)

Eñeños: «sólo puede haber un máximo de 5; el que subió algo no puede tener 2 abiertos al mismo tiempo, sí puede
reemplazar lo que subió; límite por subida 500 MB entre archivo o archivos» y «el que envió puede ejecutar su
modificación o la de otro, rotar lanzamiento/descarga entre los 5 que hay, pero no puede editar/borrar/cancelar el de
otro; sí puede borrar/editar el de él mismo».

- **5 pendientes en total**; **1 por cuenta**: un envío nuevo deja al anterior «reemplazado» (y borra sus archivos).
  Con la cola llena, el dueño de uno de los 5 SÍ puede reemplazarlo. Un autorizado sin programas entra directo igual.
- **500 MB por envío**, sumando sus archivos (`PARCHES_SUBIDA_ENVIO_MAX_MB`). El launcher lo frena ANTES de subir.
- **Probar** (`GET /manifest?canal=prueba&envio=N`): la lista de prueba vigente + los archivos de ese envío, en una
  release aparte `<vigente>-v<N>` (enlaces duros; se borra sola cuando el envío deja de estar pendiente o cambia la
  base). No cambia la lista de nadie. En el launcher: «▶ Probar este envío» (prende el servidor de prueba; JUGAR baja
  lo que cambie), y se rota entre los pendientes. ⛔ Un envío con PROGRAMAS sin aprobar sólo lo prueba quien lo subió.
- **Editar descripción / Cancelar**: sólo el dueño (`/subidas/editar`, `/subidas/cancelar`; el de otro, 403). Todos
  ven los pendientes de todos (como los PR públicos).

Probado: `probar_subidas.py` 105; guion 35 por internet 20/20 (otra cuenta prueba un pendiente, no lo puede cancelar,
su dueño lo edita y lo cancela). Parches `ensayo9`, launcher `ea44d877`.

### 37.2 · Subir es POR INVITACIÓN (16-nov, Eñeños: «test server pueden entrar; subir archivos, solicitar invitación»)

Jugar en el servidor de prueba y PROBAR envíos siguen abiertos a toda cuenta. Subir y enviar, sólo con invitación
(sin ella: 403). Se pide desde el menú del launcher («Solicitar invitación», con un motivo opcional; hasta 50
solicitudes esperando); un AUTORIZADO la ve en «INVITACIONES» y la aprueba, rechaza o después la quita. Los
autorizados quedan invitados solos (la primera vez que muestran su pase). Vive en el server de parches
(`_subidas/invitaciones.json`, `/subidas/invitacion` y `/subidas/invitar`), sin tocar Cuenta Eñeños.
Probado: `probar_subidas.py` 114; guion 35 por internet 24/24. Parches `ensayo10`.

### 37.3 · Sin versiones: las 5 MODIFICACIONES del cliente (16-nov, Eñeños, con captura)

Eñeños: «nombre de la cuenta, no sólo su id: Eñeños ID + login + breve descripción (si ponen); ya no versionar sino
poder elegir y probar entre las 5 modificaciones; el que sube: modificar / borrar; el que ve: probar = empieza la
descarga del cliente de esa subida». Y eligió mostrar el LOGIN (Cuenta Eñeños no tiene apodo).

- El menú ya no muestra historial ni «aplicar»: muestra las hasta 5 modificaciones pendientes como tarjetas
  («login · Eñeños ID», #, fecha, descripción opcional, archivos). «▶ Probar» elige esa modificación Y empieza la
  descarga ya; «Volver al cliente del servidor de prueba» la deshace. El dueño: «Modificar» (archivos y/o
  descripción) y «Borrar». Un autorizado: «Habilitar programas» (los de OTRO: así los demás la pueden probar; sigue
  pendiente) y «Quitar».
- El launcher envía SIN el pase de autorizado: nada se aplica directo a la lista de todos. (El server conserva
  aplicar/volver para un administrador, pero el launcher ya no los usa.)
- El nombre: el pase del servidor de PARCHES lleva el login como `nombre` (`portero.JUEGOS_CON_LOGIN`); los pases
  de los juegos siguen sin él (la guarda de `probar_cuenta_duena` se ajustó a eso).
- Probado: `probar_subidas` 118; cuenta dueña, portero y login con pase en verde; guion 35 por internet 24/24.
  Cuentas `ensayo8`, parches `ensayo12`.
