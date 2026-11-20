# Coordinador Eñeños

El **padre** de los juegos de Eñeños. Acá vive todo lo que NO es de un juego en particular:

- **las cuentas** (el Eñeños-ID: registro, login, vínculo con Google y Discord, el pase firmado que cada juego verifica),
- **el panel** de administración de todos los juegos,
- **el catálogo de juegos** (`juegos.json`) — de ahí sale la tabla de abajo, y la leen el panel y el launcher,
- **la casa**: contenedores, nombres del dominio, la CDN y la mudanza entre máquinas.

Cada juego tiene **su propio repo** (los hijos). Este repo los cita; no los copia.

## Qué hay acá

| dónde | qué |
|---|---|
| `servidor/` | **las cuentas** (Cuenta Eñeños, «el portero»): `portero.py` (registro, login, el pase firmado Ed25519 y el panel chico `/cuentas/admin`), `vinculos.py` (Google y Discord), `social.py` (amigos, estado y chat), `lanzamientos.py` (cuándo abre cada juego e invitaciones anticipadas), `firma_ed25519.py`, y **el panel del Coordinador** (`coordinador.py` + `panel/`, fase A: ver `documentacion/PANEL_COORDINADOR.md`) |
| `herramientas/contenedores/` | **la casa**: `docker-compose.yml`, los Dockerfile de `cuentas`, `parches` y `puerta`, el `Caddyfile` y `auth/` (las páginas de auth), `parches/` (el servidor de parches del launcher), `puerta/` (el repartidor del 48004), `mudanza.py`, `publicar_imagenes.sh`, `actualizar_prueba.sh` y `usa/` (los scripts del VPS de USA) |
| `pruebas/` | las pruebas de todo lo anterior: `python pruebas/correr_todas.py` |
| `documentacion/` | `PORTERO_CUENTAS.md`, `PANEL_COORDINADOR.md` (el panel: cómo se entra, roles, rutas, cómo se publica), `TOPOLOGIA_CONTENEDORES.md` (la guía larga de la casa) y `MUDANZA_ENSAYO_A_USA.md` |

Las imágenes de cada juego (`r2beat2013`, `web`, EDA, GunBound) se arman **en el repo de ese juego**: la cabecera de
`herramientas/contenedores/docker-compose.yml` dice de dónde sale cada una.

## Los juegos

<!-- juegos:inicio (la arma herramientas/catalogo.py desde juegos.json; no editar a mano) -->
| juego | estado | repo | pase live / test | nota |
|---|---|---|---|---|
| **R2Beat 2013** | 🟢 en producción | [`r2beatlatino/R2beat-2013`](https://github.com/r2beatlatino/R2beat-2013) | `r2beat2013` / `r2beat2013-prueba` | El más completo. Su panel viejo (sólo R2Beat) es la base del panel del Coordinador. |
| **GunBound** | 🟡 beta | [`r2beatlatino/GunBound`](https://github.com/r2beatlatino/GunBound) | `gunbound` / `gunbound-prueba` | Server propio en Python. Admin hoy: /salud y comandos de chat. |
| **EDA · Espada del Alma** | 🟡 beta | [`r2beatlatino/EDA`](https://github.com/r2beatlatino/EDA) | `eda` / — | Corre en el VPS de USA (eda-prod y eda-prueba). Su prueba todavía no tiene pase propio. |
| **Eñeñosbit 2027** | 🔧 en preparación | — (todavía no) | `r2beat-moderno` / — | El server lo está montando la sesión de fluidez. El repo se crea cuando esté. |
| **Wolf Team** | 💭 en planes | [`r2beatlatino/Wolf-Team`](https://github.com/r2beatlatino/Wolf-Team) | — / — | Va a tardar. |
<!-- juegos:fin -->

**Sumar un juego:** agregar su bloque a `juegos.json` → `python herramientas/catalogo.py` → commit.
Su repo lleva un `enenos.json` (qué soporta) y la línea «Parte de Eñeños · coordinado por `r2beatlatino/coordinador`».

## Si se pierde todo

Este repo (y los hijos) más **el respaldo cifrado** que guarda Benja alcanzan para levantar Eñeños desde cero.
La guía, escrita para alguien sin ningún contexto: **[`RECONSTRUIR.md`](RECONSTRUIR.md)**.

**Qué falta:** la lista de checks en [`PENDIENTES.md`](PENDIENTES.md).

## Lo que nunca entra acá

Es un repo **público**: ni bases de datos, ni `.env`, ni llaves, ni listas de cuentas. Lo frena
`herramientas/guardia.py` (en cada commit con el hook de `.githooks/`, y en GitHub Actions).

```bash
git config core.hooksPath .githooks      # una vez, al clonar
python pruebas/probar_repo.py            # el catálogo y la guardia, con sus controles
python pruebas/correr_todas.py           # todas las pruebas (cuentas, casa, catálogo), con el resumen al final
```

## Licencia

[AGPL-3.0](LICENSE), como [R2beat-2013](https://github.com/r2beatlatino/R2beat-2013).
