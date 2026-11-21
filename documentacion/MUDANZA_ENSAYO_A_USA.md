# La mudanza del ensayo al VPS de USA (18-nov-2026)

> 📦 **Copiado al Coordinador el 19-nov-2026** desde el repo del R2Beat 2013 (rama `claude/topologia-docker-99488b`),
> sin su historial. Lo que nombra del JUEGO (`juego.Dockerfile`, `web.Dockerfile`, `servidor/api_web.py`, `servidor/pase.py`,
> `datos.db`, el panel viejo…) sigue en ese repo. Las rutas `servidor/`, `pruebas/` y `herramientas/contenedores/` de acá
> son las mismas que allá.

> Benja: *«no hay mucho espacio, así que cambiaremos de VPS: usaremos el de USA (Miami), donde está EDA»* ·
> *«mudar todo»* · ⛔ *«no tocamos Chile»*. Los scripts: `herramientas/contenedores/usa/`.

## 1 · Dónde está cada cosa

| | VPS de ensayo VIEJO | VPS de USA (el nuevo) |
|---|---|---|
| IP | 103.90.160.237 | 185.147.157.33 |
| entrar | `ssh root@…` (con la llave de Benja, fuera del repo) | `ssh root@…` (con la llave de Benja, fuera del repo) |
| máquina | 4 núcleos · 3,4 GB · 8,5 GB libres | 2 núcleos · 3,9 GB · ~47 GB libres |
| ya tenía | — | el **EDA real** (`eda-prod` 25900, `eda-prueba` 35900, red host) y el **Caddy del sistema** con `eñeños.link` (sólo por Cloudflare) |
| estado (noche 18-nov) | **la pila ANDANDO**, es la que usa el DNS hoy | **la copia completa ANDANDO** (8 servicios + EDA del ensayo), esperando el DNS |

## 2 · Cómo convive la pila del ensayo en USA

- **La web** (`enenos-web`, su Caddy) NO toma 80/443: escucha en `127.0.0.1:8088` (HTTP; `docker-compose.override.yml`).
  El Caddy del SISTEMA le pasa `ensayo.*` y `auth.*` (`/etc/caddy/enenos-ensayo.caddy`, que se PRENDE con
  `activar_dns.sh`: si se prende antes de cambiar el DNS, Caddy pide el certificado y falla). La imagen de la web es
  `r2beat2013-web:ensayo13-usa` = la 13 + `trusted_proxies` (para que la IP real del jugador llegue al portero).
- **EDA del ensayo** en OTROS puertos (el 25900 y el relay 26000+ son del EDA real): juego **25910**, canje 25911,
  relay UDP **26400-26440**. Su lista firmada se volvió a firmar (`refirmar_eda.py`: cambia SÓLO `servidor` →
  `185.147.157.33:25910`; la del ensayo viejo quedó como `eda_web/manifiesto.jws.del-ensayo`).
- **GunBound** prod (8370/8372) y prueba (9370/9372), tal como en el ensayo viejo.
- `R2_IP_PUBLICA=185.147.157.33` (la anuncian R2Beat, GunBound y el relay de EDA).
- ufw de esa máquina: los puertos que publica Docker pasan igual (Docker va antes que ufw). `activar_dns.sh` abre el
  **443 a todos** (`ensayo` va sin la nube); el sitio de `eñeños.link` sigue rechazando lo que no venga de Cloudflare
  (su `@no_cf`). `activar_dns.sh` también agrega el `import` a `/opt/eda/caddy.sh`, que regenera el Caddyfile.

## 3 · El cambio (a la mañana)

1. **Cloudflare**: los registros A `ensayo` y `auth` → `185.147.157.33`, **sin nube** (gris).
2. En el VPS de USA: `sh /opt/enenos/mudar_final.sh`. Trae lo último de `/opt/enenos`, APAGA la pila vieja, copia
   las bases en frío, levanta acá, prende el sitio si el DNS ya apunta y borra la llave temporal del VPS viejo.
3. Comprobar con el Launcher de ENSAYO (R2Beat 2013, GunBound, EDA).

**Volver atrás**: en USA `docker compose stop` + `sh activar_dns.sh volver`; DNS de nuevo a 103.90.160.237; en el
viejo `cd /opt/enenos && docker compose start`.

## 4 · Comprobado esta noche (por dentro, con el nombre del ensayo)

- Todas las rutas: cuentas, la clave pública, GunBound prod y prueba (salud, lista firmada), la lista de EDA (con el
  servidor nuevo), la API del launcher, la zona y la web: 200 (`parches` 401 sin sesión, como debe).
- Puertos de juego desde internet: 48004, 48005, 49005 (R2Beat), 8370, 8372, 9372 (GunBound) abiertos.
- Con la cuenta de prueba: entrar → 8 juegos habilitados → pases de r2beat2013, gunbound y eda → la pantalla de
  personajes de GunBound. **Igual que en el ensayo viejo.**

## 5 · ⚠ El incidente de la noche

El primer `rsync` de `/opt/enenos` **llenó el disco del VPS de USA al 100 %** durante ~2 min: las versiones de
`releases` comparten archivos con enlaces duros (8 GB contados una vez) y `rsync -a` sin `-H` los copió enteros por
cada versión (57 GB). Se borró la copia (todo `/opt/enenos` era de la mudanza), y se repitió con `rsync -aH` (8,8 GB).
EDA real no registró errores y su base pasa `quick_check`. ⇒ **Entre máquinas, siempre `rsync -aH`**, y mirar `df`.

## 5b · ✅ HECHA (18-nov, tarde)

- **DNS** (Benja: «usa el token, solo dominio eñeños, y vps usa, no tocamos chile»): con el token de Cloudflare de Benja (fuera del repo)
  se cambiaron SÓLO `ensayo` y `auth` → 185.147.157.33, sin nube. `juego` (Chile) y `eda` quedaron igual.
- `mudar_final.sh` corrió entero hasta el paso 4: el DNS del propio VPS todavía daba la IP vieja (caché) y salió sin
  prender el sitio, como estaba previsto. Se corrió `activar_dns.sh` a mano y se borró la llave temporal del viejo.
  ⚠ Entre el fin del script (16:37 UTC) y eso (18:09) el ensayo **no respondió por HTTPS**: hay que mirar el final
  del log (`/root/mudar_final.log`) apenas termina, no esperar.
- ⚠ **El certificado.** Caddy NO sacó uno para `ensayo`/`auth`: el sitio de EDA carga el certificado de ORIGEN de
  Cloudflare (`*.eñeños.link`), y Caddy no pide otro para un nombre que ya cubre un certificado cargado. Sin la nube,
  nadie confía en ese certificado (`SEC_E_UNTRUSTED_ROOT`). `tls { issuer acme }` en el sitio NO alcanza. La
  solución fue la opción global `auto_https disable_redirects ignore_loaded_certs` (en `/etc/caddy/Caddyfile` y en
  `/opt/eda/caddy.sh`, que lo regenera; respaldos `.antes-ignore`). Con eso Caddy sacó Let's Encrypt para `ensayo`,
  `auth` y también para el sitio de EDA, que Cloudflare acepta igual (su lista sigue 200).
- Comprobado por internet: cuentas, `auth`, la lista de GunBound y la API del launcher dan 200 con certificado
  válido. Con la cuenta de prueba: entrar → pases de r2beat2013, gunbound y eda → personajes de GunBound (los datos
  del momento). Puertos 48004, 8372, 9372 y 25910 abiertos. EDA real: sano.
- El VPS viejo (103.90.160.237) quedó con la pila APAGADA (no borrada). Se puede dar de baja cuando Benja confirme.

## 5c · La lista de EDA del ensayo se queda vieja (18-nov)

El ensayo es la foto de prod del 14/15-nov: su lista de EDA seguía en **2026.11.14** (la `d3d9.dll` sin el popup de
Opciones; el botón mandaba «/opciones» y el server contestaba «abre EDA-Opciones en tu PC»). Prod ya iba por
**2026.11.18**. Cada vez que el autor de EDA publica en prod, la del ensayo NO se entera.
⇒ `herramientas/contenedores/usa/eda_al_dia.py <prod.jws> <ensayo.jws> <salida.jws>`: toma version, base y files de
prod y deja el server y el canje del ensayo; firma con la clave de publicación (la del ensayo: prod firma con otra).
Se hizo el 18-nov (sólo cambiaban `d3d9.dll` y `eda_d3d9.ini`, nada del server); la anterior quedó como
`eda_web/manifiesto.jws.2026.11.14`. ⚠ El SERVER de EDA del ensayo (`eda-server:ensayo3`) NO se cambia por el de prod:
el de prod no trae el ingreso con Cuenta Eñeños (`EDA_CUENTAS_CLAVE_PUBLICA`, `EDA_PREFIJO_CUENTA`…).

## 5d · El EDA del ensayo sigue a prod SOLO (18-nov, noche)

Benja: «que eda ensayo use el mismo repo que usa el viejo launcher» · «su trabajo manda: sólo adaptar el server lo
necesario para nuestro dueño de cuentas».
- **El código**: la rama `cuenta-enenos` (3 commits, apagados por omisión) va al repo de EDA como
  [r2beatlatino/EDA#49](https://github.com/r2beatlatino/EDA/pull/49) a `develop`, con el contexto para su agente de IA
  (quién da los pases, que el ensayo ya no usa Chile, las claves de la lista). CI 4/4 verde. Lo aprueban ellos.
- **La tarea** `herramientas/contenedores/usa/eda_ensayo.sh` → `/opt/enenos/eda_ensayo.sh`, en
  `/etc/cron.d/enenos-eda-ensayo` cada 5 min, con el MISMO candado que el actualizador de prod (`/tmp/eda-prod.lock`).
  Su log está en `/opt/enenos/eda_ensayo.log`.
  1. Cuando cambia `/opt/eda/manifiesto/eda.json`, rearma la lista del ensayo: los mismos archivos, con `servidor` y
     `canje` del ensayo. La firma con la clave de EDA del VPS, dentro de un contenedor descartable de `eda-server:prod`
     (el sistema no tiene pycryptodome). Desde el 18-nov 18:49 la lista del ensayo la firma `d033b53012b0a91f`.
  2. Cuando `main` traiga Cuenta Eñeños (el PR), arma `eda-server:ensayo-<commit>` desde `/opt/eda/prod` y reinicia
     sólo el EDA del ensayo. Si no contesta, vuelve a la imagen de antes (`.env.antes-eda-<commit>`).
  Hasta que el PR llegue a `main`, el paso 2 no hace nada y el server sigue en `eda-server:ensayo3`.
- `eda_al_dia.py` (5c) queda para firmar a mano con la clave de publicación, si algún día hiciera falta.

## 5e · La CDN del sistema nuevo y el PRECALENTADO (18-nov, noche)

- `cdn.eñeños.link` CON la nube de Cloudflare: el VPS de USA le entrega SÓLO a Cloudflare (a lo demás, 403). Caché de
  1 año por regla de la zona, la caché en niveles prendida. Rutas: `/r2beat2013/<release>/`, `/gunbound/<versión>/`,
  `/eda/<versión>/` (`herramientas/contenedores/usa/enenos-cdn.caddy`). El 2013 la usa por `PARCHES_URL_ARCHIVOS`,
  GunBound por la `base` de su lista firmada, EDA por la tarea `eda_ensayo.sh`, N2launcher por `PARCHES_LAUNCHER_URL`.
- Lo de más de 512 MB (el plan gratis no lo guarda) va en PARTES de 256 MiB (el `graphics.xfs` de GunBound).
- ⛔⛔ **REGLA (Benja: «que siempre funcione así durante parches»): cada publicación se PRECALIENTA antes de anunciarla**:
  `python3 /opt/enenos/precalentar_cdn.py` en el VPS de USA (sin argumentos: la release activa y la de prueba del 2013,
  GunBound y EDA; o `--r2beat <release>`, `--gunbound`, `--eda`). 12 a la vez: 8 GB en ~50 s. EDA lo hace solo
  (`eda_ensayo.sh`). Llena el nivel alto de Cloudflare: cualquier nodo del mundo (Río, Europa, Asia) se sirve de ahí la
  primera vez, no del VPS. Lo que NO hace (el plan gratis no lo permite): copiar a todos los nodos por adelantado.
- ⛔ Una carpeta de versión ya publicada NO se reusa con otros archivos (la CDN la guarda 1 año): versión nueva = carpeta nueva.

## 5f · R2 = la descarga principal del 2013 de PROD (18-nov, noche)

Benja: «R2 descarga principal — CDN del VPS secundaria; el launcher sigue en el VPS; que se actualice recién cuando
el cliente de prod se actualice; que no se choque con el del test server; que no se exceda de los 10 GB por accidente».

- **Bucket `r2beat-2013`** (cuenta de la zona eñeños), dominio **`r2.eñeños.link`**, regla de caché de 1 año como la CDN
  (sin ella salía `DYNAMIC`: 43 Mbps por conexión; con ella, HIT a 164). Llaves S3 en el archivo de `R2_LLAVES_ARCHIVO` del VPS (600)
  y en la PC de Benja, fuera del repo — salen del token de cuenta (id del token + sha256 del valor). ⛔ No se imprimen.
- **Sólo la release de PROD, y sólo cuando está ENTERA allá**: el server de parches (`ensayo15`) pone
  `base` = R2 y `respaldo` = la CDN si `releases/r2.json` nombra la release de prod (`PARCHES_URL_R2` en el `.env`).
  La de PRUEBA, los envíos y una release recién activada siguen por la CDN (`pruebas/probar_parches_r2.py`).
- **`/opt/enenos/r2_al_dia.py`, cron cada 10 min** (`/etc/cron.d/enenos-r2`, log `r2_al_dia.log`). Es el ÚNICO que
  escribe `r2.json`, y lo hace al final: después de verificar largo + md5 de cada objeto y de bajar uno por la URL pública
  (entero y por rango). Al cambiar prod: 1) borra `r2.json` (todos a la CDN), 2) lo que no cambió lo MUEVE adentro de R2
  (no se vuelve a subir), 3) borra lo que no es de prod, 4) sube lo que falta — si el bucket pasaría de 9,5 GB, NO sube y
  prod sigue por la CDN. Después precalienta R2 (`precalentar_cdn.py` ya pide de R2 lo que se baja de R2).
- ⇒ **Publicar una release de prod no cambia nada del procedimiento**: se activa como siempre, a los ≤10 min R2 se pone
  al día solo (unos minutos), y mientras tanto se baja de la CDN. Para forzarlo ya: `python3 /opt/enenos/r2_al_dia.py`.
- El **launcher** se sigue bajando de la CDN (`PARCHES_LAUNCHER_URL`), no de R2.
- El launcher NUEVO baja de `respaldo` lo que R2 no le dio (2ª pasada). Uno viejo ignora `respaldo`: si R2 fallara, reintenta.
- Primera carga (18-nov 23:19): `r2beat2013_2026-11-16-candado`, 2555 archivos, 8,53 GB, en 4 min desde el VPS.

## 5g · Las cuentas viejas → Eñeños ID, con sus AMIGOS (18-nov, noche)

Benja: «haremos la transformación de cuentas viejas a Eñeños ID; quienes estén agregados en el R2Beat viejo deberán
estar ya agregados como amigos». Hecho en el ensayo de USA (Cuenta Eñeños `ensayo19`), con la base de prod del 18-nov
(respaldo por `.backup()` en `_trabajo/respaldos/prod_2026-11-18/`, ⛔ con `pass_hash`: no va al repo; la copia
temporal se borró de los dos VPS). Respaldo de antes en el VPS de USA: `/root/conversion_1118/` (cuentas + portero).

- `python -m servidor.portero importar <datos.db>` → 64 cuentas nuevas (las 6730 de antes, igual).
- `python -m servidor.portero importar-amigos <datos.db> --apodos` (`social.importar_amistades`) → 6914 amistades.
  Cada personaje a su cuenta de HOY (la mudanza de personajes manda; los borrados no), la cuenta a su Eñeños ID; sólo
  cuentas activas; nadie amigo de sí mismo; idempotente. `--apodos`: a quien no tiene Ñ2-ID le pone el nombre de su
  personaje del casillero 1 — ⛔ salvo que sea igual a su LOGIN (el login es privado; se quitaron 985 así).
  Prueba: `pruebas/probar_amigos_viejos.py`.
- **«Visto por última vez»** (`cuentas.visto`): la última vez en el launcher NUEVO (su latido) o en el JUEGO (la
  presencia). Se guarda como mucho cada 5 min por persona; NADA de la historia vieja (Benja).
- **Agregar en el juego → también en el launcher** (por ahora R2Beat): el juego da `/api/interno/amistades?desde=`
  (`presencia.amistades`, con la ficha) y Cuenta Eñeños lo pide cada 5 s (`social.traer_amistades`, cursor en
  `sincro_amigos` = «fecha de alta|fila»: el número de fila SOLO se reusa al borrar — la prueba lo agarró).
  Borrar NO viaja en ningún sentido. Prueba: `pruebas/probar_amigos_del_juego.py`. ⏳ El juego del ensayo necesita
  la imagen `r2beat2013-juego:ensayo28` (armada, sin arrancar: reiniciarlo corta a quien esté jugando).
- **Launcher 3.0.5**: sonido de mensaje (`sonido-mensaje.mp3`) con el launcher abierto y fuera del juego; no suena
  en el juego ni con el chat de esa persona abierto (sí minimizado o cerrado).

## 5h · ✅ EDA desconectado de Chile: el EDA viejo se RETIRÓ (20-nov)

Benja: *«desconectar EDA de Chile, para que el diagrama ya sea todo Miami USA, y que el repo autoactualizar esté
desconectado de Chile, sólo USA»*. Eligió **retirar** el EDA viejo (no pasarlo a Cuenta Eñeños) y que sus datos
**empiecen de cero** (1 cuenta y 3 inventarios `r2b_<uid>`: quedan sólo en el respaldo).

Lo que ataba EDA a Chile eran DOS cosas, ninguna en el código del repo de EDA:
- `eda-prod` validaba el pase con el JWKS de `https://r2beatlatino.com/cuentas/clave-publica` (`/opt/eda/prod.env`,
  `EDA_PORTERO_CLAVES`) — se entraba por el launcher VIEJO;
- el Caddy del sistema mandaba `https://eñeños.link/admin*` a `r2beatlatino.com/cuentas/admin` (el panel de
  aprobaciones del portero de R2Beat).

Lo que se hizo (`herramientas/contenedores/usa/retirar_eda_viejo.sh` → `/root/`, respaldo en `/root/respaldo_eda_viejo_20261120_1739`: el estado, el cron,
el Caddyfile, `prod.env` y la imagen/política del contenedor):
1. `eda-prod` **apagado, no borrado** (`docker update --restart=no` + `stop`). Volver: `docker update
   --restart=unless-stopped eda-prod && docker start eda-prod` y restaurar el cron del respaldo.
2. `/etc/cron.d/eda`: la línea de prod ya NO arma ni reinicia `eda-prod`: sólo baja `main` a `/opt/eda/prod`
   (`git fetch` + `reset --hard`, con el mismo candado). De ahí `eda_ensayo.sh` (§5d) arma el EDA de Miami: **el repo
   se sigue actualizando solo, y sólo en USA**. La de prueba (develop → `eda-prueba`, sin login de Chile) queda igual.
3. Caddy: `sh /opt/eda/caddy.sh xn--eeos-gqab.link 25901` SIN el tercer dato ⇒ sin `/admin` (ninguna línea con
   `r2beatlatino` queda en `/etc/caddy/Caddyfile`). `/eda/*` del dominio raíz era el canje de `eda-prod`: ahora da 502.
   Siguen: `/files-eda/*` y `/eda/manifiesto.jws` (los archivos los usa la CDN del EDA de Miami).
4. ⚠ La imagen `eda-server:prod` NO se borra: con ella `eda_ensayo.sh` firma la lista del cliente.

Comprobado: el EDA de Miami contesta, su lista (`ensayo…/eda/manifiesto.jws`) 200, sus archivos por la CDN 200, el
canje `POST /eda/pase` vivo (400 «formato» con un cuerpo vacío), `eñeños.link/admin` 404. **El launcher viejo ya no
entra a EDA** (era la condición de retirarlo).

## 5i · ✅ LA MUDANZA DE R2BEAT 2013: PROD = MIAMI (20-nov)

Benja: *«a Chile no avisaremos, solamente mandaremos nuestro nuevo launcher como actualización»*, *«la web seguirá
prendida, el servicio apagado»*. Antes: el respaldo validado con el ensayo del día del reemplazo (copia temporal: 15
chequeos, 0 mal) y el salto del launcher viejo probado de verdad (el 3.0.1 se actualiza solo al N2launcher y éste usa SU
carpeta `Data`: no hereda el `net.json` que apuntaba a Chile).

En orden:
1. **Chile**: `r2beat-game2013` apagado y deshabilitado. La web y el server de parches siguen prendidos.
2. **La base FINAL** (con el juego quieto: más fresca que un respaldo en caliente), bajada en pedazos de 2 MB con su
   sha256 (las transferencias largas por ssh desde la PC de desarrollo se cortan) y subida a Miami.
3. **Miami** (`herramientas/contenedores/usa/` → `cargar_chile_en_miami.sh`): respaldo de lo de antes, la base de Chile
   en el volumen del juego, `portero importar` (las cuentas nuevas), `importar-amigos --apodos`, `enlazar_cuentas` (todas
   enlazadas, ninguna suelta) y recién al final `vaciar-claves` (la base del juego deja de guardar contraseñas).
4. **GitHub** `v-latest` (el botón de la web y el auto-update del launcher viejo) con el N2launcher, la descarga pública
   comprobada por md5.
5. **El server de parches de Chile** anuncia el N2launcher: cada launcher viejo se muda solo al abrirse.

Lo que salió mal, y cómo se arregló:
- **El `importar` falló la 1.ª vez:** una base en modo WAL, en una carpeta de root, no se abre en sólo lectura desde el
  contenedor (SQLite necesita crear el `-shm`). Arreglo: `journal_mode=delete` sobre la copia y la carpeta a nombre del
  usuario del contenedor.
- **Las noticias y la tienda del launcher se pisaron:** viven DENTRO de `datos.db` (`launcher_contenido`) y la base de
  Chile traía las suyas. Se restauraron desde el respaldo de Miami con `launcher_contenido.guardar`. ⇒ antes de pisar
  una base, comparar clave por clave lo que el Coordinador editó.
- **El login se cayó a los 15 min** («error interno»): el proceso de `cuentas` llegó a 1023 archivos abiertos (tope 1024)
  — `cerrar_conexiones()` existía pero nadie la llamaba. Arreglo: el manejador la llama al terminar cada conexión
  (`probar_conexiones.py`) + `ulimits: nofile 65536` en el override. ⇒ **Los ensayos probaron los DATOS, nunca la
  CARGA**: después de un corte, mirar los errores ~30 min con la gente entrando.
- **Los accesos directos del launcher viejo** («R2Beat TEST») seguían con su ícono: Windows guarda el ícono POR RUTA y el
  exe se reemplaza en el mismo lugar. El launcher (3.0.23) escribe su ícono como `.ico` en una ruta nueva y apunta ahí
  los accesos que son suyos.

Después de la mudanza, en el Coordinador: **«Restablecer contraseña»** (sólo Admin; una provisoria al azar que se ve una
vez, sesiones cerradas, auditoría sin la contraseña).

## 5j · ✅ El server de PRUEBA de EDA, desde el launcher (21-nov)

Benja: «aquí no está saliendo el botón testserver» (EDA). No existía: `eda-prueba` (develop, red host, 35900) estaba
en `EDA_LOGIN=abierto` y nadie llegaba a él. Ahora es como el de GunBound:

| pieza | qué |
|---|---|
| EDA (r2beatlatino/EDA#63) | `EDA_PORTERO_AUDIENCIA`: cada server acepta sólo SU pase (vacío = `eda`) |
| `/opt/eda/prueba.env` | `EDA_LOGIN=pase` · `EDA_PORTERO_AUDIENCIA=eda-prueba` · `EDA_PREFIJO_CUENTA=en_` · `EDA_CUENTA_NUEVA=vacia` · la clave pública de Cuenta Eñeños (la misma que el EDA de la pila). Respaldo: `prueba.env.antes-pase-eda-prueba` |
| Cuenta Eñeños (`coord-k`) | el pase `eda-prueba`, cerrado por el lanzamiento de EDA (la invitación vale para los dos; un baneo de EDA cubre los dos). Puerta: `/datos/manifiestos/eda-prueba.json` |
| `eda_ensayo.sh` | firma también `eda_web/prueba.jws` (mismos archivos, server `185.147.157.33:35900`, canje `…/eda-prueba/pase`) |
| Caddy del sistema (`enenos-ensayo.caddy`) | `/eda-prueba/lista.jws` y `/eda-prueba/pase` → `127.0.0.1:35901` (el Caddy de la pila no llega a la red host) |
| launcher 3.0.25 | botón «Servidor de prueba» en las opciones de EDA |

Probado con pases de verdad: `eda-prueba` → server de prueba = ticket · ⟲ `eda` → prueba = «audiencia» · ⟲ `eda-prueba` →
prod = «audiencia». Las cuentas viejas del modo abierto del de prueba quedaron sin usar.

## 6 · Lo que queda

- El **R2Beat moderno** (server + cliente de ~15 GB) lo arma la sesión de Fluidez en este mismo VPS, cuando Benja
  le diga si va con su cuenta grabada o sólo con cuentas nuevas (lo pidió en SU sesión).
- `/opt/R2Beat_steam` (15 GB) sigue en el VPS viejo; no se copió.
- El VPS viejo es efímero: cuando Benja confirme que todo anda en USA, se puede apagar.
