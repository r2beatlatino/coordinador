# Contrato del panel — cómo un juego se deja gestionar desde el Coordinador

> 20-nov-2026. Benja: *«GunBound y EDA aún no tienen muchos comandos: lee sus servers y haz ambos a la vez; cuando
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
- `ip` sólo si el juego la tiene; el Coordinador se la saca a los moderadores.
- Nada de contraseñas, hashes, correos ni claves en ninguna respuesta.

## Del lado del Coordinador

- `R2_PANEL_GESTION` = «`pase=contrato1:http://…/interno/panel`;…» (sin `contrato1:` = el panel viejo de R2Beat).
- `gestion.py` tiene la lista cerrada de cada tipo, y los cupos por moneda (`moneda:<id>`) para los moderadores.
