# Páginas de los juegos en el launcher

El STAFF edita la página de EDA desde `#/j/eda/live/pagina`. La parte **Página**
aparece en PROD para los juegos del catálogo que no declaran una fuente propia en
`R2_PANEL_CONTENIDO`. Los juegos con fuente conservan su editor actual.

La página permite editar banner, cajas e idiomas, importar borradores de
`NOVEDADES.json`, publicar una versión y quitar versiones del historial. La vista
previa usa los mismos datos del formulario. Los cambios de banner, cajas e idiomas
y las eliminaciones llegan al launcher con el botón superior **Publicar**.
Antes de importar o publicar un borrador hay que publicar o descartar esos cambios.

Las rutas del panel requieren su cookie de sesión y cada POST lleva `X-R2: 1`:

| Método y ruta | Cuerpo / respuesta |
|---|---|
| `GET /coordinador/api/pagina?juego=eda` | `{publicada, borradores, base, puede_editar}` |
| `POST /coordinador/api/pagina` | `{juego, base, publicada}` |
| `POST /coordinador/api/pagina/importar` | `{juego}` |
| `POST /coordinador/api/pagina/publicar` | `{juego, version, base}` |

El portero también admite esas rutas con el prefijo `/cuentas`. La página es
común al juego y se publica en PROD; no hay una página TEST que escriba sobre ella.
ADMIN puede editar; MODERADOR sólo con el juego asignado. Un moderador de formato
viejo puede mirar. Cada guardado, importación y publicación deja `contenido · pagina`
en la auditoría del Coordinador, con el juego y la operación. Esta fuente es local:
no hay una escritura en el panel viejo de un servidor del juego.

`config/paginas.json`, junto a `portero.db`, contiene por juego `publicada` (o
`null`), `borradores` y `base`. El archivo se relee, se comprueba la base dentro
del lock y se escribe con un temporal en la misma carpeta, `fsync` y `os.replace`.
Una base vieja devuelve 409. **Recargar página y descartar cambios** permite leer
el estado vigente antes de volver a editar. Un archivo ilegible no se sobrescribe.

`GET /lanzamientos` añade `paginas`, sólo con páginas publicadas, sin borradores ni
bases. Sin archivo o con un archivo roto devuelve `{}` en esa clave y anota el
caso en el log. `actualizada` la pone el servidor en UTC al publicar. EDA recibe
Español (`es`) y English (`en`) cuando se omite `idiomas`; una lista explícita se
respeta. Sin página no se crea una entrada EDA para los idiomas.

La importación usa `novedades_url` del catálogo (`juegos.json` en la raíz), timeout
de 8 segundos y un máximo de descarga de 4 MiB. Acepta una lista raíz o un objeto
con `versiones`. Omite `borrador: true`, valida cada entrada y devuelve
`{importadas, invalidas}` junto al estado del panel. Deduplica por `version`
contra borradores y publicaciones; nunca publica por sí sola. La descarga se hace
fuera del lock y la mezcla relee el estado vigente antes de guardarlo.

El contrato usa texto plano, sin `<`, `>` ni controles, con los límites del
encargo. El historial se ordena por fecha descendente (versión como desempate),
con hasta 10 entradas. Las cajas tienen hasta 4 entradas y los idiomas hasta 8.
Sólo el POST de guardar página admite hasta 512 KiB para el historial completo y
su posible codificación JSON con Unicode escapado; los demás POST conservan su límite.

Verificación sin red: `pruebas/probar_paginas.py` ejecuta los manejadores reales
con transporte en memoria y el fetch inyectado. Prueba permisos, límites exactos,
HTML y controles, importación, publicación, bases viejas, dos guardados simultáneos,
archivos rotos y fallo del reemplazo atómico, siempre con controles al revés.
`node pruebas/probar_paginas_panel.js` verifica el flujo del editor y el escape
del contenido ejecutando el JavaScript real con un DOM mínimo, sin dependencias.
