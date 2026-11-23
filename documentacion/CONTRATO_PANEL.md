# Contrato del panel — cómo un juego se deja gestionar desde el Coordinador

> 20-nov-2026. Eñeños: *«GunBound y EDA aún no tienen muchos comandos: lee sus servers y haz ambos a la vez; cuando
> maduren en un futuro corto se editarán sus secciones»*.
>
> R2Beat 2013 NO usa este contrato: expone su panel viejo entero (`/api/interno/panel/<ruta>`, ver `gestion.py`).
> Todo juego NUEVO usa este, que es chico a propósito y crece agregando acciones.

## La idea

- El server del juego abre una **puerta interna** (sólo la red de adentro; nunca publicada en internet).
- El **Coordinador decide quién puede qué** (admin, moderador con ese juego, permisos asignables, cupos). El juego sólo
  **ejecuta** y **anota** quién lo pidió.
- El juego declara **lo que sabe hacer hoy** en `capacidades`. El panel muestra sólo eso. Cuando el juego madura, se
  agrega una acción acá, en el juego y en `gestion.py`.

## Seguridad (obligatorio)

- Toda ruta exige la cabecera `X-Ficha-Interna` igual a la variable de entorno `R2_CUENTAS_FICHA_INTERNA` del juego
  (comparación de tiempo constante). Sin variable, o con otra ficha: **404** (como si no existiera).
- Todo POST exige además `X-R2: 1` (si falta: 403).
- `X-Coordinador-Quien` = quién lo pidió («coordinador:<login>»). El juego lo anota en su log / auditoría con cada
  acción que CAMBIA algo. `X-Coordinador-Admin: 1|0` es informativo (el Coordinador ya filtró).
- Cuerpos JSON con tope de tamaño; errores siempre `{"error": "<texto en español neutro, de usted>"}`.

## Las rutas (prefijo `/interno/panel`)

| método y ruta | qué devuelve / hace | acción que pide en el Coordinador |
|---|---|---|
| `GET capacidades` | `{"juego", "version": 1, "acciones": [...], "monedas": [{"id", "nombre"}], "entorno"}` | ver |
| `GET salud` | `{"en_linea": bool, "jugando": n, "detalle": [{"nombre", "valor"}]}` (versión, salas, uptime… lo que tenga) | ver |
| `GET conectados` | `{"filas": [{"id", "nick", "enenos_id", "donde", "desde", "ip"?}]}` (`desde` = epoch; `donde` = sala/canal en palabras) | ver |
| `GET buscar?q=` | `{"filas": [{"id", "nick", "enenos_id", "conectado", "resumen"}]}`: por apodo (parte), por id del juego o por Eñeños ID (número). Tope 50 | ver |
| `GET ficha/<id>` | `{"id", "nick", "enenos_id", "conectado", "baneado"?, "campos": [{"nombre", "valor"}], "monedas": {"<id>": n}, "personajes": [{"id", "nick"}]?, "movimientos": [{"cuando", "que", "quien"}]?}` | ver |
| `POST aviso {texto, a: "todos"|"uno", id?}` | `{"ok": true, "llego_a": n}` | aviso |
| `POST echar {id, motivo?}` | desconecta. `{"ok": true}` (404 si no está conectado) | echar |
| `POST moneda {id, moneda, cantidad}` | suma (o resta si es negativa) una moneda del juego. `{"ok": true, "antes", "despues"}`. Nunca deja negativo | moneda |

- `id` = el identificador del personaje/cuenta **en ese juego** (número o texto, el que use el juego).
- `enenos_id` = el Eñeños ID de la cuenta, si el juego lo conoce (si no, `null`). Con él el Coordinador junta a la
  persona con sus personajes en todos los juegos.
- `capacidades.acciones` lista SÓLO lo implementado (p. ej. `["ver", "aviso", "moneda"]`). Una ruta no implementada
  responde **404**.
- `ip` sólo si el juego la tiene; el Coordinador la entrega sólo a ADMIN incluidos por Eñeños-ID en `R2_VEN_IPS`.
  Vacía o ausente = nadie. El filtro también quita logins, geoip y datos de IP compartida (incluidos contadores),
  en cualquier nivel y en pares `{nombre, valor}` rotulados como IP/login; conserva el país independiente.
- Nada de contraseñas, hashes, correos ni claves en ninguna respuesta.

## Del lado del Coordinador

- `R2_PANEL_GESTION` = «`pase=contrato1:http://…/interno/panel`;…» (sin `contrato1:` = el panel viejo de R2Beat).
- `gestion.py` tiene la lista cerrada de cada tipo, y los cupos por moneda (`moneda:<id>`) para los moderadores.

## En el panel (lo que ve el equipo)

- La página del juego (`#/j/<juego>/<live|test>/…`) pide `capacidades` UNA vez y arma todo con eso: un botón aparece
  sólo si el juego lo sabe hacer **y** la cuenta tiene el permiso. Si el juego todavía no sabe algo (EDA sin `echar`),
  el tablero lo dice en «Lo que se puede hacer aquí» («Este juego todavía no»).
- **Tablero**: `salud` + `conectados` (se actualiza solo cada 15 s). «Dónde están» agrupa por `donde` y filtra al tocarlo.
  `detalle` se muestra tal cual como pares nombre/valor. «Aviso a todos» si hay `aviso`.
- **Personas**: `buscar` agrupado por Eñeños ID; la ficha muestra `campos` como pares, `monedas` con los nombres de
  `capacidades.monedas`, `personajes` para saltar entre ellos y `movimientos` como «Últimos cambios». Aviso a uno,
  «Desconectar» (`echar`) y «Dar o quitar» por moneda. Un `id` de texto sirve (`#/j/eda/live/personas/eda-7f30`).
- **La red → Permisos**: lo asignable sale de `asignables_de[juego]`. Con «moneda» marcada, una casilla de cupo por
  cada moneda que el juego declara (si el juego no contesta, se escriben los ids a mano). Desmarcar deja los cupos en 0
  sin borrar lo ya dado.
- El moderador ve lo que le queda de cada moneda («Le queda: Oro 300 · Cash 500»); el formulario no deja pasarse del
  cupo ni quitar más de lo que el jugador tiene (y el Coordinador lo vuelve a controlar igual).
