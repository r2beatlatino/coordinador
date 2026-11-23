'use strict';
/* Sin dependencias ni red: ejecuta el JS real del panel con un DOM mínimo.
   Verifica el flujo de edición/publicación y que los datos jamás entren como HTML. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = vm.createContext({
  document: { querySelector: () => null, querySelectorAll: () => [], addEventListener: () => {} },
  window: { addEventListener: () => {} }, setInterval: () => {}, setTimeout, clearTimeout,
});
const fuente = fs.readFileSync(path.join(__dirname, '../servidor/panel/panel.js'), 'utf8');
assert.match(fuente, /\narrancar\(\);\s*$/);
vm.runInContext(fuente.replace(/\narrancar\(\);\s*$/, ''), context);
const run = code => vm.runInContext(code, context);
run(`
  pintarJ = () => {}; pintarAccJ = () => {}; pintarCuerpoJ = () => {}; pintarPreviaJ = () => {}; toast = () => {};
  let pendiente, pedidos = [], proxima;
  confirmar = d => { pendiente = d.alAceptar(); };
  api = async (ruta, cuerpo) => { pedidos.push({ruta, cuerpo}); return proxima; };
  const J = nuevoJc({pagina_local: true, puede_editar: true}, 'eda', 'live');
  J.tab = 'pagina'; S.jc = J;
  const limpio = {publicada: null, borradores: [], base: 'base-1', puede_editar: true};
  ponerPagina(J, limpio);
`);
let controles = 0;
function ok(cond, texto) {
  assert.ok(cond, texto); controles++;
  process.stdout.write(`  ✔ ${texto}\n`);
}

(async () => {
  ok(run(`tabsC(J).includes('pagina') && !suciasJc(J).length && J.borr.pagina.idiomas.map(x => x.id).join(',') === 'es,en'`),
    'Página inicia limpia, con idiomas EDA y pestaña propia');
  run(`cambioJc({dataset:{jc:'pg-sello'}, value:'BETA', type:'text'}, false);
       cambioJc({dataset:{jc:'pg-titulo'}, value:'EDA NOVIEMBRE', type:'text'}, false);
       accionJc({dataset:{accion:'jc-pg-agregar', t:'cajas'}});
       cambioJc({dataset:{jc:'pg-caja-titulo', i:'0'}, value:'Comunidad', type:'text'}, false);
       cambioJc({dataset:{jc:'pg-caja-texto', i:'0'}, value:'Texto de prueba', type:'text'}, false);
       cambioJc({dataset:{jc:'pg-idioma-id', i:'1'}, value:'pt', type:'text'}, false);
       cambioJc({dataset:{jc:'pg-idioma-nombre', i:'1'}, value:'Português', type:'text'}, false);`);
  ok(run(`J.borr.pagina.banner.sello === 'BETA' && J.borr.pagina.banner.titulo === 'EDA NOVIEMBRE'
       && J.borr.pagina.cajas[0].titulo === 'Comunidad' && J.borr.pagina.cajas[0].texto === 'Texto de prueba'
       && J.borr.pagina.idiomas[1].id === 'pt' && J.borr.pagina.idiomas[1].nombre === 'Português'`),
    'los campos de banner, cajas e idiomas cambian su dato correcto');
  ok(run(`suciasJc(J).includes('pagina') && /jc-pg-importar" disabled/.test(edPagina(J))`),
    '⟲ cambios sin guardar impiden importar y se marcan sin publicar');
  await run(`operacionPagina(J, 'importar')`);
  ok(run(`pedidos.length === 0`), '⟲ tampoco se importa desde la acción si hay cambios pendientes');
  run(`proxima = {ok: true, d: {publicada: clon(J.borr.pagina), borradores: [], base: 'base-2', puede_editar: true}};
       publicarJ();`);
  await run('pendiente');
  ok(run(`pedidos.length === 1 && pedidos[0].ruta === 'pagina' && pedidos[0].cuerpo.base === 'base-1'
       && pedidos[0].cuerpo.publicada.banner.titulo === 'EDA NOVIEMBRE' && J.pagina.base === 'base-2' && !suciasJc(J).length`),
    'Publicar usa POST pagina con su base y actualiza el estado confirmado');
  run(`J.d.puede_editar = false;
       cambioJc({dataset:{jc:'pg-titulo'}, value:'prohibido', type:'text'}, false);
       accionJc({dataset:{accion:'jc-pg-agregar', t:'cajas'}});`);
  ok(run(`J.borr.pagina.banner.titulo === 'EDA NOVIEMBRE' && J.borr.pagina.cajas.length === 1
       && /data-jc="pg-titulo"[^>]*disabled/.test(edPagina(J))`),
    '⟲ sólo lectura deshabilita campos y bloquea cambios y agregados');
  run(`J.d.puede_editar = true;
       for (let i=0; i<12; i++) { accionJc({dataset:{accion:'jc-pg-agregar',t:'cajas'}}); accionJc({dataset:{accion:'jc-pg-agregar',t:'idiomas'}}); }`);
  ok(run(`J.borr.pagina.cajas.length === 4 && J.borr.pagina.idiomas.length === 8`),
    '⟲ Agregar respeta máximos de cajas e idiomas');
  run(`descartarJ();`);
  await run('pendiente');
  ok(run(`!suciasJc(J).length && J.borr.pagina.cajas.length === 1`), 'Descartar restaura la página publicada');
  run(`const hostil = '<img src=x onerror=alert(1)>"&';
       const ver = {version:hostil,fecha:hostil,resumen:hostil,corregidos:[hostil],mejoras:[hostil],avisos:[hostil]};
       ponerPagina(J,{publicada:{banner:{sello:hostil,titulo:hostil},version_actual:hostil,versiones:[ver],
         cajas:[{titulo:hostil,texto:hostil}],idiomas:[{id:hostil,nombre:hostil}]}, borradores:[ver],base:'hostil'});
       J.pgInforme = [hostil]; J.err.pagina = hostil;`);
  ok(run(`![edPagina(J), previaPagina(J)].some(h => h.includes('<img src=x'))
       && edPagina(J).includes('&lt;img') && previaPagina(J).includes('&lt;img')`),
    '⟲ banner, cajas, idiomas, versiones, borradores e informes escapan HTML');
  run(`ponerPagina(J, {publicada:{...paginaVacia('eda'), version_actual:'2',versiones:[{version:'2'}, {version:'1'}]},borradores:[],base:'orden'});
       accionJc({dataset:{accion:'jc-pg-quitar',t:'versiones',i:'0'}});`);
  ok(run(`J.borr.pagina.version_actual === '1' && J.borr.pagina.versiones.length === 1`),
    'Quitar versión actual selecciona la siguiente del historial');
  run(`ponerPagina(J, limpio); cambioJc({dataset:{jc:'pg-titulo'},value:'local',type:'text'},false);
       proxima = {ok:false,status:409,d:{error:'Recargue la página'}}; publicarJ();`);
  await run('pendiente');
  ok(run(`J.err.pagina === 'Recargue la página' && J.pagina.base === 'base-1' && J.borr.pagina.banner.titulo === 'local'`),
    '⟲ 409 conserva lo escrito y muestra el error sin renovar la base');
  run(`proxima = {ok:true,d:limpio};`);
  await run(`operacionPagina(J,'recargar')`);
  ok(run(`!suciasJc(J).length && !J.err.pagina && J.borr.pagina.banner.titulo === ''`),
    'Recargar descarta los cambios locales y permite volver a editar');
  run(`proxima = {ok:true,d:{...limpio,base:'importada',borradores:[{version:'3'}],importadas:1,invalidas:[{entrada:2,error:'resumen inválido'}]}};`);
  await run(`operacionPagina(J,'importar')`);
  ok(run(`J.pagina.base === 'importada' && J.pagina.borradores[0].version === '3' && J.pgInforme.length === 2 && !J.pagina.publicada`),
    'Importar muestra resultados y borradores sin inventar una publicación');
  run(`proxima = {ok:true,d:{...limpio,base:'publicada',publicada:{...paginaVacia('eda'),version_actual:'3',versiones:[{version:'3'}]}}};
       accionJc({dataset:{accion:'jc-pg-version',i:'0'}});`);
  await run('pendiente');
  ok(run(`pedidos.at(-1).ruta === 'pagina/publicar' && pedidos.at(-1).cuerpo.base === 'importada'
       && pedidos.at(-1).cuerpo.version === '3' && J.borr.pagina.version_actual === '3'`),
    'Publicar borrador envía versión y base y refresca la versión actual');
  process.stdout.write(`\n✔ probar_paginas_panel: ${controles} controles, 0 fallas\n`);
})().catch(e => { console.error(e); process.exitCode = 1; });
