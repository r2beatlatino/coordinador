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
       cambioJc({dataset:{jc:'pg-idioma-nombre', i:'1'}, value:'Português', type:'text'}, false);
       cambioJc({dataset:{jc:'pg-idioma-avance', i:'1'}, value:'39', type:'text'}, false);
       cambioJc({dataset:{jc:'pg-idioma-avance', i:'0'}, value:'250', type:'text'}, false);`);
  ok(run(`J.borr.pagina.idiomas[1].avance === 39 && J.borr.pagina.idiomas[0].avance === 100`),
    'el % de traducción se guarda como número y se recorta a 0..100');
  run(`cambioJc({dataset:{jc:'pg-idioma-avance', i:'0'}, value:'', type:'text'}, false);`);
  ok(run(`!('avance' in J.borr.pagina.idiomas[0])`), '⟲ vaciar el % lo quita (no se muestra en el launcher)');
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
  // ★ 26-nov · la SEGURIDAD de R2Beat 2013: pestaña con permiso, interruptores sólo ADMIN, todo escapado
  run(`const mkS = acciones => { const X = {jid:'r2beat2013', env:'live', d:{}, g:nuevoG({tipo:'r2beat', rol:'moderador', acciones})}; X.g.ok = true; return X; };
    var JS1 = mkS(['ver','seguridad']), JS0 = mkS(['ver']), JSA = mkS(['ver','seguridad','seguridad/ajustes']);
    var segR = {ajustes:{max_cuentas_maquina:0, baneo_maquina:false, max_cuentas_ip:0}, maquina:{pcs:38, cuentas:39, pcs_compartidas:1, max_cuentas_en_una_pc:2, pcs_baneadas:0},
      eventos_hoy:{total:3, cuentas:2, riesgo:{alto:1, bajo:2}}};
    var segEv = [{evento:'ab'.repeat(16), cuando:'2026-11-26 18:30:00', uid:7, nick:'<img src=x onerror=alert(1)>', regla:'<b>proceso</b>', categoria:'herramienta',
        riesgo:'alto', estado:'nuevo', repeticiones:2, descripcion:'<script>x</script>'},
      {evento:'cd'.repeat(16), cuando:'2026-11-26 18:31:00', uid:8, nick:'Ana', regla:'reloj', riesgo:'bajo', estado:'descartado'}];
    for (const X of [JS1, JSA]) X.g.seg = {estado:'nuevo', riesgo:'', jugador:'', r: segR, ev: segEv, t: 1};`);
  ok(run(`tabsJc(JS1).includes('seguridad') && !tabsJc(JS0).includes('seguridad')`), 'Seguridad: la pestaña sólo con el permiso «seguridad» (⟲ sin él no aparece)');
  ok(run(`!cuerpoSeguridad(JS1).includes('data-accion="g-seg-ajustes"') && cuerpoSeguridad(JS1).includes('Sólo ADMIN')
      && cuerpoSeguridad(JSA).includes('data-accion="g-seg-ajustes"')`), 'Seguridad: «Cambiar» los interruptores sólo ADMIN (⟲ el moderador lo ve apagado)');
  ok(run(`const h1 = cuerpoSeguridad(JS1); !h1.includes('<img') && !h1.includes('<script>') && !h1.includes('<b>proceso') && h1.includes('&lt;img')`),
    'Seguridad: apodo, regla y descripción de un evento van escapados (no se ejecutan)');
  ok(run(`cuerpoSeguridad(JS1).includes('sólo <b>anota</b>')`), 'Seguridad: con los topes en 0 avisa que la máquina sólo anota');
  run(`JS1.g.seg.r = Object.assign({}, segR, {ajustes:{max_cuentas_maquina:2, baneo_maquina:true, max_cuentas_ip:0}});`);
  ok(run(`!cuerpoSeguridad(JS1).includes('sólo <b>anota</b>') && cuerpoSeguridad(JS1).includes('<b>2</b> a la vez')`), '⟲ con tope 2 ya no dice que sólo anota');
  ok(run(`const h2 = cuerpoSeguridad(JS1); (h2.match(/data-accion="g-seg-ev"/g) || []).length === 2 && h2.includes('data-ev="' + 'ab'.repeat(16))
      && !h2.includes('data-ev="' + 'cd'.repeat(16))`), 'Seguridad: botones sólo en el evento abierto (⟲ el descartado no tiene)');
  run(`var Fpc = {pc:{pcs:[{pc:'02fab1d8', primera:'2026-11-26 13:10', ultima:'2026-11-26 13:11', veces:3, baneada:false,
      otras_cuentas:[{uid:9, nick:'<i>Beto</i>'}]}], alguna_baneada:false}};`);
  ok(run(`const h3 = pcHtml(JS1, Fpc); h3.includes('#/j/r2beat2013/live/personas/9') && h3.includes('&lt;i&gt;Beto') && !h3.includes('g-pc-perdonar')`),
    'Ficha: sus PC con link a la otra cuenta, escapado (⟲ sin baneo no ofrece perdonar)');
  run(`Fpc.pc.alguna_baneada = true; Fpc.pc.pcs[0].baneada = true;`);
  ok(run(`pcHtml(JS1, Fpc).includes('g-pc-perdonar') && pcHtml(JS0, Fpc) === ''`), 'Ficha: con una PC baneada ofrece perdonar (⟲ sin permiso, nada)');
  // ★ 27-nov · los CUPONES DE ROPA: pestaña con permiso, sólo ropa, sólo los plazos de la tienda, todo escapado
  run(`var JC1 = mkS(['ver','cupones']), JC0 = mkS(['ver']);
    JC1.g.cup = {q:'pelo', filas:[{id:30220852, nombre:'<img src=x onerror=alert(1)>Pelo', familia:'wardrobe_hair', cargas:false, duraciones:['P7','P30','PI']},
      {id:1000961, nombre:'Pose', familia:'dance_emote', cargas:false, duraciones:['P7','P30']},
      {id:1000200, nombre:'Campana', cargas:true, duraciones:[]}, {id:777, nombre:'Pack', cargas:false, duraciones:[]}],
      elegido:null, dias:0, cantidad:1, usos:1, nota:'', hecho:null, lista:[], lt:1};`);
  ok(run(`tabsJc(JC1).includes('cupones') && !tabsJc(JC0).includes('cupones')`), 'Cupones: la pestaña sólo con el permiso «cupones» (⟲ sin él no aparece)');
  ok(run(`const hc1 = cuerpoCupones(JC1); (hc1.match(/data-cup-it=/g) || []).length === 1 && hc1.includes('data-cup-it="30220852"') && !hc1.includes('data-cup-it="1000200"')`),
    'Cupones: en la búsqueda sólo la ropa (⟲ la campana, el pack y la pose no aparecen)');
  ok(run(`const hc2 = cuerpoCupones(JC1); !hc2.includes('<img') && hc2.includes('&lt;img')`), 'Cupones: el nombre del ítem va escapado');
  ok(run(`cuerpoCupones(JC1).includes('data-accion="g-cup-generar" disabled')`), '⟲ sin prenda elegida, «Generar» está apagado');
  run(`JC1.g.cup.elegido = JC1.g.cup.filas[0]; JC1.g.cup.cantidad = 3; JC1.g.cup.usos = 2;`);
  ok(run(`const hc3 = cuerpoCupones(JC1); (hc3.match(/data-accion="g-cup-dias"/g) || []).length === 3 && hc3.includes('data-k="0"') && hc3.includes('data-k="30"')
      && hc3.includes('data-k="7"') && !hc3.includes('data-k="365"') && !hc3.includes('data-accion="g-cup-generar" disabled')`),
    'Cupones: con la prenda, sólo SUS plazos (permanente, 30, 7; ⟲ no 365) y «Generar» prendido');
  ok(run(`cuerpoCupones(JC1).includes('<b>3</b> códigos') && cuerpoCupones(JC1).includes('hasta <b>6</b> personas')`), 'Cupones: el resumen dice cuántos y cuántas personas en total');
  run(`JC1.g.cup.cantidad = 0;`);
  ok(run(`cuerpoCupones(JC1).includes('data-accion="g-cup-generar" disabled') && cuerpoCupones(JC1).includes('van de 1 a')`), '⟲ con 0 cupones, «Generar» se apaga y lo dice');
  run(`JC1.g.cup.cantidad = 1; JC1.g.cup.hecho = {codigos:['AB<script>CD'], txt:'x'}; JC1.g.cup.lista = [{codigo:'Z<q>1', premios:[{item:1, dias:0, nombre:'<i>P</i>'}], usos:2, usados:1, activo:true, creado:1, creador:'<u>yo</u>'}];`);
  ok(run(`const hc4 = cuerpoCupones(JC1); !hc4.includes('<script>') && !hc4.includes('<q>1') && hc4.includes('Z&lt;q&gt;1') && !hc4.includes('<i>P') && !hc4.includes('<u>yo') && hc4.includes('1/2 usos')`),
    'Cupones: códigos, lista y creador van escapados; la lista dice usados/usos');
  // ★ 27-nov · las cuentas GM NPC: pestaña con permiso, los 6 NPC, la clave sólo en «Lista», todo escapado
  run(`var JG1 = mkS(['ver','gm_npc']), JG0 = mkS(['ver','cupones']);`);
  ok(run(`tabsJc(JG1).includes('gmnpc') && !tabsJc(JG0).includes('gmnpc')`), 'GM NPC: la pestaña sólo con el permiso «gm_npc» (⟲ sin él no aparece)');
  ok(run(`const hg1 = cuerpoGmNpc(JG1); (hg1.match(/data-accion="g-gmn-npc"/g) || []).length === 6 && hg1.includes('aria-checked="true"') && hg1.includes('Crear GM-King')
      && !hg1.includes('Usuario</dt>')`), 'GM NPC: los 6 NPC, King elegido, y ⟲ sin cuenta creada no hay usuario ni clave');
  run(`JG1.g.gmn.npc = 'sue';`);
  ok(run(`cuerpoGmNpc(JG1).includes('Crear GM-Sue')`), 'GM NPC: elegir otro NPC cambia el botón');
  run(`JG1.g.gmn.hecho = {usuario:'gmnpc_<b>x', clave:'<img src=x onerror=alert(1)>', nick:'GM-<i>Sue'};
       JG1.g.gmn.lista = [{usn:9, nick:'<u>GM-Sue</u>', estado:'en uso', creado:1, creado_por:'coordinador:<s>mod', motivo:''},
                          {usn:8, nick:'GM-King', estado:'cerrada', creado:1, creado_por:'coordinador:mod', motivo:'salió del juego'}];`);
  ok(run(`const hg2 = cuerpoGmNpc(JG1); !hg2.includes('<img') && hg2.includes('&lt;img') && !hg2.includes('<b>x') && !hg2.includes('<i>Sue')
      && !hg2.includes('<u>GM') && !hg2.includes('<s>mod')`), 'GM NPC: usuario, clave, apodos y creador van escapados');
  ok(run(`const hg3 = cuerpoGmNpc(JG1); (hg3.match(/data-accion="g-gmn-cerrar"/g) || []).length === 1 && hg3.includes('data-k="9"') && !hg3.includes('data-k="8"')`),
    'GM NPC: «Cerrar ya» sólo en la abierta (⟲ la cerrada no lo tiene)');
  run(`JG1.g.gmn.hecho = null;`);
  ok(run(`!cuerpoGmNpc(JG1).includes('&lt;img')`), 'GM NPC: con «Ya la anoté» la clave desaparece de la pantalla');
  process.stdout.write(`\n✔ probar_paginas_panel: ${controles} controles, 0 fallas\n`);
})().catch(e => { console.error(e); process.exitCode = 1; });
