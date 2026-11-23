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
  ok(run(`!('presentacion' in J.borr.pagina) && !('voces' in J.borr.pagina)
       && edPagina(J).includes('Presentación') && edPagina(J).includes('Voces del selector')
       && /<textarea[^>]*data-jc="pg-presentacion-texto"[^>]*maxlength="1200"/.test(edPagina(J))
       && !suciasJc(J).length`), 'renderizar los campos opcionales no cambia EDA ni agrega claves');
  run(`const contador = {textContent:''};
       document.querySelector = s => s === '#pgPresentacionCuenta' ? contador : null;
       cambioJc({dataset:{jc:'pg-presentacion-titulo'},value:'Eñeñosbit 2027',type:'text'},false);
       cambioJc({dataset:{jc:'pg-presentacion-texto'},value:'Primera línea.\\nOtra línea.\\n\\nSegundo párrafo.',type:'textarea'},false);
       cambioJc({dataset:{jc:'pg-presentacion-arte'},value:'2',type:'select-one'},true);
       accionJc({dataset:{accion:'jc-pg-agregar',t:'voces'}});
       cambioJc({dataset:{jc:'pg-voz-id',i:'0'},value:'original',type:'text'},false);
       cambioJc({dataset:{jc:'pg-voz-nombre',i:'0'},value:'Original',type:'text'},false);`);
  ok(run(`J.borr.pagina.presentacion.titulo === 'Eñeñosbit 2027' && J.borr.pagina.presentacion.arte === '2'
       && J.borr.pagina.presentacion.texto.includes('\\n\\n') && J.borr.pagina.voces[0].id === 'original'
       && J.borr.pagina.voces[0].nombre === 'Original' && contador.textContent === String(J.borr.pagina.presentacion.texto.length)
       && previaPagina(J).includes('Primera línea.<br>Otra línea.</p><p>Segundo párrafo.')
       && /value="2" selected/.test(edPagina(J))`),
    'presentación, arte y voces editan sus datos; contador y previa conservan líneas y párrafos');
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
       && pedidos[0].cuerpo.publicada.banner.titulo === 'EDA NOVIEMBRE'
       && pedidos[0].cuerpo.publicada.presentacion.arte === '2' && pedidos[0].cuerpo.publicada.voces[0].id === 'original'
       && J.pagina.base === 'base-2' && !suciasJc(J).length`),
    'Publicar usa POST pagina con su base y actualiza el estado confirmado');
  run(`J.d.puede_editar = false;
       cambioJc({dataset:{jc:'pg-titulo'}, value:'prohibido', type:'text'}, false);
       cambioJc({dataset:{jc:'pg-presentacion-texto'},value:'prohibido',type:'textarea'},false);
       cambioJc({dataset:{jc:'pg-voz-id',i:'0'},value:'prohibido',type:'text'},false);
       accionJc({dataset:{accion:'jc-pg-sin-presentacion'}});
       accionJc({dataset:{accion:'jc-pg-agregar',t:'voces'}});
       accionJc({dataset:{accion:'jc-pg-agregar', t:'cajas'}});`);
  ok(run(`J.borr.pagina.banner.titulo === 'EDA NOVIEMBRE' && J.borr.pagina.cajas.length === 1
       && /data-jc="pg-titulo"[^>]*disabled/.test(edPagina(J))`),
    '⟲ sólo lectura deshabilita campos y bloquea cambios y agregados');
  ok(run(`J.borr.pagina.presentacion.texto.startsWith('Primera') && J.borr.pagina.voces.length === 1
       && J.borr.pagina.voces[0].id === 'original'
       && /data-jc="pg-presentacion-texto"[^>]*disabled/.test(edPagina(J))
       && /data-jc="pg-presentacion-arte"[^>]*disabled/.test(edPagina(J))`),
    '⟲ sólo lectura también protege presentación, arte y voces');
  run(`J.d.puede_editar = true;
       for (let i=0; i<12; i++) { accionJc({dataset:{accion:'jc-pg-agregar',t:'cajas'}}); accionJc({dataset:{accion:'jc-pg-agregar',t:'idiomas'}}); accionJc({dataset:{accion:'jc-pg-agregar',t:'voces'}}); }`);
  ok(run(`J.borr.pagina.cajas.length === 4 && J.borr.pagina.idiomas.length === 8 && J.borr.pagina.voces.length === 8`),
    '⟲ Agregar respeta máximos de cajas, idiomas y voces');
  run(`descartarJ();`);
  await run('pendiente');
  ok(run(`!suciasJc(J).length && J.borr.pagina.cajas.length === 1`), 'Descartar restaura la página publicada');
  run(`accionJc({dataset:{accion:'jc-pg-sin-presentacion'}});
       accionJc({dataset:{accion:'jc-pg-quitar',t:'voces',i:'0'}});`);
  ok(run(`!('presentacion' in J.borr.pagina) && J.borr.pagina.voces.length === 0 && suciasJc(J).includes('pagina')`),
    'quitar presentación y voz elimina los datos del borrador');
  run(`const hostil = '<img src=x onerror=alert(1)>"&';
       const ver = {version:hostil,fecha:hostil,resumen:hostil,corregidos:[hostil],mejoras:[hostil],avisos:[hostil]};
       ponerPagina(J,{publicada:{banner:{sello:hostil,titulo:hostil},version_actual:hostil,versiones:[ver],
         cajas:[{titulo:hostil,texto:hostil}],idiomas:[{id:hostil,nombre:hostil}],
         presentacion:{titulo:hostil,texto:hostil,arte:hostil},voces:[{id:hostil,nombre:hostil}]}, borradores:[ver],base:'hostil'});
       J.pgInforme = [hostil]; J.err.pagina = hostil;`);
  ok(run(`![edPagina(J), previaPagina(J)].some(h => h.includes('<img src=x'))
       && edPagina(J).includes('&lt;img') && previaPagina(J).includes('&lt;img')`),
    '⟲ banner, presentación, arte, voces, cajas, idiomas, versiones, borradores e informes escapan HTML');
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

  run(`
    const pjLic = {uid:5, nick:'Jugador <5>', licencia:'luna', inventario:[]};
    const JL = {jid:'r2beat2013', env:'live', sel:5, tab:'personas', g:nuevoG({rol:'moderador', acciones:[], cupos:{}})};
    JL.g.fichas['5'] = {f:pjLic, h:{dias:[]}, pjs:[]};
    S.jc = JL; S.catalogo = [{id:'r2beat2013', nombre:'R2Beat 2013'}];
    let modalLic = '', confirmacionLic = null, clickLic, avisoLic, recargasLic = 0;
    const selectLic = {value:'luna'}, errorLic = {textContent:''}, diaLic = {innerHTML:''};
    const domLic = {querySelector:s => s === '#liOk' ? {addEventListener:(ev, f) => {clickLic=f;}}
      : s === '#liV' ? selectLic : s === '#liErr' ? errorLic : s === '#dCuerpo' ? diaLic : null};
    abrirCapa = html => {modalLic=html; return domLic;}; cerrarCapa = () => {};
    confirmar = d => {confirmacionLic=d;}; toast = d => {avisoLic=d;};
    cargarFicha = () => {recargasLic++;}; pedidos=[];
  `);
  ok(run(`herramientasHtml(JL,pjLic).includes('Cambiar la licencia')
      && !herramientasHtml(JL,pjLic).includes('data-accion="g-licencia"')
      && herramientasHtml(JL,pjLic).includes('#i-lock')`), 'Dar y cambiar: licencia con candado sin permiso');
  run(`accionFicha(JL,{dataset:{accion:'g-licencia'}}); formLicencia(JL,pjLic);`);
  ok(run(`modalLic === '' && pedidos.length === 0`), '⟲ sin permiso tampoco abre el formulario por acción directa');
  run(`JL.g.mios.acciones=['licencia']; accionFicha(JL,{dataset:{accion:'g-licencia'}});`);
  ok(run(`herramientasHtml(JL,pjLic).includes('data-accion="g-licencia"')
      && herramientasHtml(JL,pjLic).includes('#i-star') && modalLic.includes('Actual: <b>Luna</b>')
      && ['Ninguna','Estrella','Luna','Sol'].every(t=>modalLic.includes('>'+t+'</option>'))
      && modalLic.includes('value="luna" selected') && !modalLic.includes('Jugador <5>')`),
    'Licencia asignada: estrella, actual y cuatro opciones escapadas');
  run(`selectLic.value='luna'; clickLic();`);
  ok(run(`errorLic.textContent === 'Elija una licencia distinta.' && !confirmacionLic && !pedidos.length`),
    '⟲ elegir la misma licencia no confirma ni envía');
  run(`selectLic.value='inventada'; clickLic();`);
  ok(run(`!confirmacionLic && !pedidos.length`), '⟲ una licencia inventada no se envía');
  for (const licencia of ['ninguna', 'estrella', 'luna', 'sol']) {
    run(`pjLic.licencia=${JSON.stringify(licencia === 'luna' ? 'sol' : 'luna')};
      confirmacionLic=null; formLicencia(JL,pjLic); selectLic.value=${JSON.stringify(licencia)};
      proxima={ok:true,d:{antes:pjLic.licencia,despues:${JSON.stringify(licencia)}}};`);
    const antes = run('pedidos.length');
    run('clickLic();');
    ok(run(`pedidos.length === ${antes} && confirmacionLic.ok === 'Cambiar la licencia'
      && confirmacionLic.txt.includes('Antes:') && confirmacionLic.txt.includes('Ahora:')`),
      `${licencia}: pide confirmación antes de enviar`);
    await run('confirmacionLic.alAceptar()');
    ok(run(`pedidos.length === ${antes + 1} && pedidos.at(-1).ruta === 'gestion'
      && pedidos.at(-1).cuerpo.juego === 'r2beat2013' && pedidos.at(-1).cuerpo.entorno === 'live'
      && pedidos.at(-1).cuerpo.ruta === 'usuario/5/licencia'
      && pedidos.at(-1).cuerpo.cuerpo.licencia === ${JSON.stringify(licencia)}
      && avisoLic.t === 'Licencia cambiada'
      && avisoLic.sub.includes('Antes: '+licenciaTxt(pjLic.licencia)+' · Ahora: '+licenciaTxt(${JSON.stringify(licencia)}))`),
      `${licencia}: contrato correcto y resultado antes/ahora del servidor`);
  }
  ok(run(`recargasLic === 4 && ACC_TXT['gestión · licencia'][0] === 'cambió la licencia'
      && AUD_TXT.licencia === 'cambió la licencia'
      && audDet({accion:'licencia',detalle:{antes:'luna',despues:'sol'}}) === 'Luna → Sol'`),
    'Tras cambiar relee la ficha; ambas auditorías nombran la licencia y sus valores');
  run(`formLicencia(JL,pjLic); selectLic.value='estrella'; clickLic(); JL.g.mios.acciones=[];`);
  await run('confirmacionLic.alAceptar()');
  ok(run(`pedidos.length === 4 && recargasLic === 4`), '⟲ permiso retirado antes de confirmar: no envía');
  run(`JL.g.mios={rol:'admin',acciones:['licencia']}; formLicencia(JL,pjLic); selectLic.value='estrella';
      clickLic(); proxima={ok:false,status:400,d:{error:'Licencia rechazada'}};`);
  await run('confirmacionLic.alAceptar()');
  ok(run(`avisoLic.tipo === 'err' && avisoLic.sub === 'Licencia rechazada' && recargasLic === 4`),
    '⟲ ADMIN abre licencia; rechazo muestra el error y no anuncia éxito');

  ok(run(`conexionesHtml(JL,{}) === '' && conexionesHtml(JL,{ips:[],misma_ip:[]}) === ''
      && conexionesHtml(JL,{ips:[{pais:'PE'}]}) === ''`), 'Sin IPs ni derivados no hay caja vacía ni texto de IP oculta');
  ok(run(`conexionesHtml(JL,{ips:[{ip:'192.0.2.5',pais:'PE',veces:1,ultima:1}],misma_ip:[{uid:7,nick:'Jugador7'}]}).includes('192.0.2.5')
      && conexionesHtml(JL,{misma_ip:[{uid:7,nick:'Jugador7'}]}).includes('Comparten su IP')`),
    '⟲ los datos autorizados muestran IP y personajes que la comparten');
  run(`JL.g.con={filas:[{uid:5,nick:'Jugador5',estado:'lobby',pais:'PE'}]};`);
  ok(run(`!filasConectados(JL).includes('class="g-ip"') && !filasConectados(JL).includes('misma IP')`),
    'R2Beat sin IP: conectados sin hueco ni contador');
  run(`const JCip={jid:'gunbound',env:'live',g:nuevoG({tipo:'contrato1',acciones:[]})};
      JCip.g.con={filas:[{id:'5',nick:'Jugador5',pais:'PE'}]};`);
  ok(run(`!filasConectadosC(JCip).includes('class="g-ip"')`), 'Contrato1 sin IP: conectados sin hueco');
  run(`proxima={ok:true,d:{sesiones:[{inicio:1,fin:2}]}};`);
  await run(`abrirDia(JL,'2026-11-23')`);
  ok(run(`!diaLic.innerHTML.includes('<span></span>') && !diaLic.innerHTML.includes('oculta')
      && diaLic.innerHTML.includes('Cuándo entró')`), 'Sesiones sin IP: conserva horarios sin texto vacío');
  run(`proxima={ok:true,d:{sesiones:[{inicio:1,fin:2,ip:'192.0.2.5',pais:'PE'}]}};`);
  await run(`abrirDia(JL,'2026-11-23')`);
  ok(run(`diaLic.innerHTML.includes('PE 192.0.2.5')`), '⟲ sesiones autorizadas muestran país e IP');
  process.stdout.write(`\n✔ probar_paginas_panel: ${controles} controles, 0 fallas\n`);
})().catch(e => { console.error(e); process.exitCode = 1; });
