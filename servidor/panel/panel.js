'use strict';
/* ══════════════════════════════════════════════════════════════════════════════════════════════
   panel.js — el Coordinador Eñeños, FASE A (19-nov-2026). El diseño es el del prototipo aprobado por Benja;
   los datos son los de verdad (servidor/coordinador.py). ⛔ Nada inventado: si un dato no existe, no se muestra.
     #/entrar          sólo Discord o Google vinculados a un Eñeños ID con rol
     #/juegos          las tarjetas de juegos.json, con PROD / TEST
     #/red             personas, invitaciones, lanzamientos, moderadores y permisos, auditoría
     #/persona/<uid>   vínculos, estado y permisos por juego (★ 20-nov: banear en varios juegos, con tiempo y motivo)
     #/j/<juego>/<live|test>/<parte>   ★ fase B (20-nov): el contenido dinámico del launcher de ese juego
                       (asistencia · ruleta · avisos del lobby · lanzamiento). El tablero (fase C) todavía no.
     #/novedades       ★ fase B: el acordeón de noticias de todos los launchers
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const ic = (n, c = '') => `<svg class="i ${c}" aria-hidden="true"><use href="#i-${n}"/></svg>`;
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const dos = n => String(n).padStart(2, '0');
const DIAS_L = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const iniciales = n => { const l = String(n).replace(/[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9]/g, ' ').trim().split(/\s+|(?=[A-Z][a-z])/); return ((l[0] || '?')[0] + ((l[1] || l[0] || '')[l[1] ? 0 : 1] || '')).toUpperCase(); };
const ava = (n, c = '') => `<span class="ava ${c}" style="--h:${hashStr(String(n)) % 360}" aria-hidden="true">${esc(iniciales(n))}</span>`;
const okColor = c => /^\d{1,3},\d{1,3},\d{1,3}$/.test(String(c || '')) ? c : '81,216,229';
const okPos = p => /^[\d.]+% [\d.]+%$/.test(String(p || '')) ? p : '50% 50%';
const okArte = a => /^arte\/[A-Za-z0-9][A-Za-z0-9._-]*$/.test(String(a || '')) ? a : '';
function fmtDur(min) {
  min = Math.max(0, Math.round(min));
  if (min < 60) return `${min} min`;
  if (min < 1440) { const h = Math.floor(min / 60), m = min % 60; return m ? `${h} h ${m} min` : `${h} h`; }
  const d = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60);
  if (d >= 60 || (d >= 30 && d % 30 === 0)) { const me = Math.floor(d / 30), r = d % 30; return `${me} ${me === 1 ? 'mes' : 'meses'}${r ? ` ${r} d` : ''}`; }
  return h ? `${d} d ${h} h` : `${d} ${d === 1 ? 'día' : 'días'}`;
}
/* ★ 20-nov: el tiempo de un baneo, de los segundos que faltan (los da el servidor: no depende del reloj de esta PC) */
const venceTxt = s => s == null ? 'permanente' : `vence en ${fmtDur(Math.ceil(Number(s) / 60))}`;
const haceSeg = s => { const min = (Date.now() / 1000 - Number(s)) / 60; return min < 1 ? 'ahora' : `hace ${fmtDur(min)}`; };
const fechaEpoch = s => { const d = new Date(Number(s) * 1000); return `${DIAS_L[d.getDay()]} ${d.getDate()} ${MESES[d.getMonth()]} · ${dos(d.getHours())}:${dos(d.getMinutes())}`; };
/* «2026-11-19 21:40:05» (hora del servidor) -> «19 nov 21:40» */
const fechaTxt = t => { const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(t || '')); return m ? `${Number(m[3])} ${MESES[Number(m[2]) - 1]} ${m[4]}:${m[5]}` : esc(t || ''); };
const SVG_DISCORD = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.32 4.37a19.8 19.8 0 0 0-4.89-1.52.07.07 0 0 0-.08.04c-.21.38-.44.87-.61 1.25a18.27 18.27 0 0 0-5.49 0 12.6 12.6 0 0 0-.62-1.25.08.08 0 0 0-.08-.04 19.74 19.74 0 0 0-4.88 1.52.07.07 0 0 0-.03.03C.53 9.05-.32 13.58.1 18.06a.08.08 0 0 0 .03.06 19.9 19.9 0 0 0 5.99 3.03.08.08 0 0 0 .09-.03c.46-.63.87-1.3 1.22-2a.08.08 0 0 0-.04-.1 13.1 13.1 0 0 1-1.87-.9.08.08 0 0 1 0-.12l.37-.3a.07.07 0 0 1 .08 0c3.93 1.8 8.18 1.8 12.06 0a.07.07 0 0 1 .08 0l.37.3a.08.08 0 0 1 0 .12c-.6.35-1.22.65-1.88.9a.08.08 0 0 0-.04.1c.36.7.77 1.37 1.23 2a.08.08 0 0 0 .08.03 19.84 19.84 0 0 0 6-3.03.08.08 0 0 0 .03-.06c.5-5.18-.84-9.67-3.55-13.66a.06.06 0 0 0-.03-.03zM8.02 15.33c-1.18 0-2.16-1.08-2.16-2.42 0-1.33.96-2.42 2.16-2.42 1.21 0 2.18 1.1 2.16 2.42 0 1.34-.96 2.42-2.16 2.42zm7.97 0c-1.18 0-2.15-1.08-2.15-2.42 0-1.33.95-2.42 2.15-2.42 1.21 0 2.18 1.1 2.16 2.42 0 1.34-.94 2.42-2.16 2.42z"/></svg>';
const SVG_GOOGLE = '<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>';
const PROV = { discord: 'Discord', google: 'Google' };
const logoProv = (p, w = 15) => p === 'discord' ? `<span style="width:${w}px;display:flex;color:#8b95ff">${SVG_DISCORD}</span>` : `<span style="width:${w - 1}px;display:flex">${SVG_GOOGLE}</span>`;
const ENV_TXT = { live: 'PROD', test: 'TEST', extra: 'EXTRA' };

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   Estado y API (todo POST lleva X-R2: 1; la sesión es una cookie HttpOnly que JS no ve)
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
const S = { sesion: null, proveedores: {}, configurado: false, catalogo: [], juegos: [], ruta: '#/juegos', errorLogin: null, tabRed: 'inv', equipo: null };
const esAdmin = () => !!(S.sesion && S.sesion.rol === 'admin');
const raiz = $('#raiz'), capas = $('#capas');

async function api(ruta, datos) {
  const op = { method: datos ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', headers: {} };
  if (datos) { op.headers = { 'Content-Type': 'application/json', 'X-R2': '1' }; op.body = JSON.stringify(datos); }
  let r, d = {};
  try { r = await fetch('api/' + ruta, op); } catch (e) { return { ok: false, status: 0, d: { error: 'red', texto: 'No hay conexión con el Coordinador.' } }; }
  try { d = await r.json(); } catch (e) { d = {}; }
  if (r.status === 401 && S.sesion && ruta !== 'estado') {
    S.sesion = null; S.jc = null; S.nov = null; toast({ t: 'La sesión terminó', sub: 'Vuelva a entrar con Discord o Google.', tipo: 'info' }); go('#/entrar', true, true);
  }
  return { ok: r.ok, status: r.status, d };
}
const errTxt = r => esc((r.d && (r.d.texto || r.d.error)) || `Error ${r.status}`);

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   Toasts, capas, menús
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
function toast({ t, sub = '', tipo = 'ok', ms = 5000 }) {
  const cont = $('#toasts');
  while (cont.children.length > 3) cont.firstElementChild.remove();
  const el = document.createElement('div');
  el.className = 'toast ' + tipo;
  const icono = { ok: 'check', err: 'alert', info: 'info' }[tipo] || 'check';
  el.innerHTML = `<span class="ic">${ic(icono, 's16')}</span><div class="t">${t}${sub ? `<small>${sub}</small>` : ''}</div>` +
    `<button type="button" class="btn icono chico fantasma" aria-label="Cerrar aviso">${ic('x', 's14')}</button>`;
  const fuera = () => { if (!el.isConnected) return; el.classList.add('sale'); setTimeout(() => el.remove(), 200); };
  el.querySelector('button').addEventListener('click', fuera);
  cont.appendChild(el);
  setTimeout(fuera, ms);
}
let focoPrevio = null;
function abrirCapa(html) {
  if (!capas.innerHTML) focoPrevio = document.activeElement;
  capas.innerHTML = `<div class="velo-capa" data-accion="cerrar-capa"></div>${html}`;
  const panel = capas.children[1];
  const primero = panel.querySelector('[autofocus]') || panel.querySelector('input:not(:disabled), button:not(:disabled), a[href]');
  if (primero) setTimeout(() => primero.focus(), 30);
  return panel;
}
function cerrarCapa() {
  if (!capas.innerHTML) return;
  capas.innerHTML = '';
  if (focoPrevio && document.body.contains(focoPrevio)) focoPrevio.focus();
  focoPrevio = null;
}
let pop = null;
function abrirPop(ancla, html, ancho = 280) {
  cerrarPop();
  const r = ancla.getBoundingClientRect();
  pop = document.createElement('div');
  pop.className = 'menu-juegos';
  pop.setAttribute('role', 'menu');
  Object.assign(pop.style, { position: 'fixed', width: ancho + 'px', top: (r.bottom + 6) + 'px', right: 'auto',
    left: Math.max(8, Math.min(window.innerWidth - ancho - 8, r.right - ancho)) + 'px' });
  pop.innerHTML = html;
  document.body.appendChild(pop);
  ancla.setAttribute('aria-expanded', 'true');
  pop._ancla = ancla;
  const b = pop.querySelector('button, a'); if (b) b.focus();
}
function cerrarPop() { if (!pop) return; if (pop._ancla) pop._ancla.setAttribute('aria-expanded', 'false'); pop.remove(); pop = null; }
function confirmar({ titulo, txt, ok = 'Confirmar', icono = 'alert', peligro = true, extra = '', alAceptar }) {
  const p = abrirCapa(`<div class="modal" role="alertdialog" aria-modal="true" aria-labelledby="mdTit">
    <div class="modal-cab"><span class="ic" ${peligro ? '' : 'style="background:rgba(81,216,229,.12);color:var(--cyan)"'}>${ic(icono, 's20')}</span><div><h2 id="mdTit">${titulo}</h2><p>${txt}</p></div></div>
    ${extra ? `<div class="modal-cuerpo">${extra}</div>` : ''}
    <div class="modal-pie"><button type="button" class="btn" data-accion="cerrar-capa">Cancelar</button><button type="button" class="btn ${peligro ? 'peligro lleno' : 'prim'}" id="mdOk">${ok}</button></div></div>`);
  $('#mdOk', p).addEventListener('click', () => { const v = $('#mdExtra', p); cerrarCapa(); alAceptar(v ? v.value : ''); });
}
function ilus() {
  return `<svg class="ilus" viewBox="0 0 120 90" aria-hidden="true"><rect x="18" y="40" width="70" height="18" rx="5" fill="var(--panel-2)" stroke="var(--line-2)"/><rect x="18" y="62" width="70" height="18" rx="5" fill="var(--panel-2)" stroke="var(--line-2)"/>
    <circle cx="28" cy="49" r="2.5" fill="var(--cyan)" opacity=".8"/><circle cx="28" cy="71" r="2.5" fill="var(--tx-4)"/><path d="M38 49h22M38 71h30" stroke="var(--line-2)" stroke-width="3" stroke-linecap="round"/>
    <circle cx="84" cy="27" r="17" fill="var(--bg)" stroke="var(--line)"/><circle cx="84" cy="27" r="9" stroke="var(--cyan)" stroke-width="2" fill="none"/><path d="m91 34 6 6" stroke="var(--cyan)" stroke-width="2.2" stroke-linecap="round"/></svg>`;
}
const vacio = (titulo, txt, acc = '') => `<div class="vacio">${ilus()}<b>${titulo}</b><p>${txt}</p>${acc}</div>`;

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   Las tarjetas de juego (login: sólo para mirar · elegir: con lo que se sabe de cada servidor)
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
function arte2027() {
  const r = rng(2027); let rects = '';
  for (let c = 0; c < 40; c++) {
    const h = Math.floor(2 + r() * 5 + 6 * Math.pow(Math.sin(c / 4.2), 2) * (0.6 + r() * 0.6));
    const col = c < 14 ? '#f32686' : c < 27 ? '#51d8e5' : '#6fdc9c';
    for (let k = 0; k < h; k++) rects += `<rect x="${c * 8 + 1}" y="${130 - k * 8}" width="6" height="6" rx="1" fill="${k === h - 1 ? '#e3bb67' : col}" opacity="${(0.18 + 0.62 * (k / h)).toFixed(2)}"/>`;
  }
  return `<svg class="fondo" viewBox="0 0 320 138" preserveAspectRatio="xMidYMax slice" style="width:100%;height:100%;display:block" aria-hidden="true"><defs><linearGradient id="g27" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b1229"/><stop offset="1" stop-color="#071318"/></linearGradient></defs><rect width="320" height="138" fill="url(#g27)"/>${rects}</svg>`;
}
/* sin arte en la carpeta del servidor: el color del juego (el arte de terceros no va al repo público) */
const arteColor = x => `<div style="width:100%;height:100%;background:radial-gradient(circle at 30% 30%,rgba(${okColor(x.color)},.55),transparent 60%),radial-gradient(circle at 75% 75%,rgba(${okColor(x.color)},.25),transparent 55%),#121623"></div>`;
const arteDe = x => okArte(x.arte) ? `<img src="${esc(x.arte)}" style="object-position:${okPos(x.pos)}" alt="" loading="lazy">` : x.id === 'r2beat-moderno' ? arte2027() : arteColor(x);
function nombreTarjeta(x) {
  if (okArte(x.logo)) return `<img class="gc-logo" src="${esc(x.logo)}" alt="${esc(x.nombre)}">`;
  const anio = /^(.*\S)\s+(\d{4})$/.exec(x.nombre || '');
  const sub = String(x.nombre_largo || '').split(' · ')[1];
  if (anio) return `<b class="gc-nom">${esc(anio[1])}<small>${esc(anio[2])}</small></b>`;
  return `<b class="gc-nom">${esc(x.nombre)}${sub ? `<small>${esc(sub)}</small>` : ''}</b>`;
}
function estadoSrv(s) {
  if (!s) return '<span class="estado tenue">sin datos</span>';
  return s.estado === 'en_linea' ? '<span class="estado"><span class="punto vivo"></span>En línea</span>' : '<span class="estado"><span class="punto caido"></span>Sin respuesta</span>';
}
function tarjetaJuego(x, modo, i) {
  let top = x.etiqueta ? `<span class="chip mayus gc-etq">${esc(x.etiqueta)}</span>` : '<span></span>';
  let extra = '';
  if (modo === 'elegir') {
    if (x.invitaciones) top += `<a class="chip oro gc-alertas" href="#/red" title="Invitaciones anticipadas por aprobar">${ic('mail', 's14')}${x.invitaciones} por aprobar</a>`;
    const live = (x.servidores || {}).live, lz = x.lanzamiento;
    const n = live && typeof live.jugando === 'number' ? live.jugando : null;
    if (n !== null) extra += `<div class="gc-dato"><b class="num">${n}</b><span>jugando ahora</span></div>`;
    if (x.tiene_servidor) {
      extra += `<div class="gc-srvs">${['live', 'test'].filter(e => x.pases && x.pases[e]).map(e => { const s = x.servidores[e];
        return `<span class="gc-srv"><span class="etq-env ${e}">${ENV_TXT[e]}</span>${estadoSrv(s)}${s && typeof s.jugando === 'number' ? `<span class="tenue num">· ${s.jugando}</span>` : ''}</span>`; }).join('')}</div>`;
      if (lz && !lz.libre) extra += `<div class="gc-srvs"><span class="gc-srv tenue" title="Abre el ${fechaEpoch(lz.desde)}">${ic('clock', 's14')}Abre en <span data-cuenta="${lz.desde * 1000}">--</span></span></div>`;
      extra += `<div class="gc-botones"><a class="btn prim gc-btn" href="#/j/${esc(x.id)}/live/resumen" aria-label="Entrar a ${esc(x.nombre)} en PROD, con jugadores reales">${ic('radio', 's16')}PROD</a>` +
        (x.pases && x.pases.test ? `<a class="btn gc-btn gc-test" href="#/j/${esc(x.id)}/test/resumen" aria-label="Entrar a ${esc(x.nombre)} en TEST, el servidor de prueba">${ic('flask', 's16')}TEST</a>` : `<span class="btn gc-btn gc-test" aria-disabled="true" title="Todavía no tiene servidor de prueba" style="opacity:.45">${ic('flask', 's16')}TEST</span>`) + '</div>';
    } else {
      extra += `<div class="gc-srvs"><span class="gc-srv tenue">${ic('info', 's14')}Se conecta cuando tenga servidor</span></div>`;
    }
  }
  return `<article class="gc ${modo} ${x.tiene_servidor ? '' : 'prox apagada'}" style="--g:${okColor(x.color)};animation-delay:${i * 70}ms" data-fx-id="${esc(x.id)}" ${modo === 'login' ? 'tabindex="-1"' : ''}>
    <div class="gc-arte">${arteDe(x)}</div><div class="gc-velo"></div>
    <div class="gc-top">${top}</div>
    <div class="gc-cuerpo">${nombreTarjeta(x)}<span class="gc-gen">${esc(x.genero)}</span><p class="gc-desc">${esc(x.desc)}</p>${extra}</div>
  </article>`;
}
function fondoFx(lista, inicial) {
  inicial = inicial || (lista[0] && lista[0].id);
  const capasFx = lista.map(x => `<div class="fx-capa ${x.id === inicial ? 'on' : ''}" data-fx="${esc(x.id)}" style="${okArte(x.arte) ? `background-image:url('${esc(x.arte)}');background-position:${okPos(x.pos)}` : `background:radial-gradient(circle at 30% 40%,rgb(${okColor(x.color)}),transparent 55%),radial-gradient(circle at 70% 60%,#51d8e5,transparent 55%),#1b1229`}"></div>`).join('');
  const r = rng(77); let est = '';
  for (let i = 0; i < 24; i++) {
    const s = (3 + r() * 8).toFixed(1), c = ['#f32686', '#51d8e5', '#e3bb67', '#ffffff'][i % 4];
    est += `<svg class="fx-est" style="left:${(r() * 100).toFixed(1)}%;top:${(r() * 100).toFixed(1)}%;width:${s * 2}px;height:${s * 2}px;animation-delay:-${(r() * 6).toFixed(1)}s;--o:${(.12 + r() * .28).toFixed(2)}" viewBox="-10 -10 20 20"><path d="M0-10C1-1 1-1 10 0C1 1 1 1 0 10C-1 1-1 1-10 0C-1-1-1-1 0-10Z" fill="${c}"/></svg>`;
  }
  return `<div class="fx" aria-hidden="true">${capasFx}<div class="fx-brillos"></div><div class="fx-rayas"><i></i><i></i><i></i></div>${est}<div class="fx-vineta"></div></div>`;
}
const setFx = id => $$('.fx-capa').forEach(c => c.classList.toggle('on', c.dataset.fx === id));
function carrusel(html, cls, etiqueta) {
  return `<div class="gc-carrusel ${cls}"><button type="button" class="gc-flecha izq" data-accion="carrusel-mover" data-dir="-1" aria-label="Ver las anteriores">${ic('left', 's16')}</button>
    <section class="gc-fila" aria-label="${etiqueta}"><div class="gc-pista"><div class="gc-grupo">${html}</div></div></section>
    <button type="button" class="gc-flecha der" data-accion="carrusel-mover" data-dir="1" aria-label="Ver las siguientes">${ic('right', 's16')}</button></div>`;
}
/* el carrusel infinito: dos copias del grupo, -50 %; quieto y centrado si todas entran; con «reducir movimiento», flechas */
function montarCarrusel(fila) {
  const caja = fila.closest('.gc-carrusel'), pista = fila.querySelector('.gc-pista'), grupo = fila.querySelector('.gc-grupo');
  $$('.gc-grupo.copia', pista).forEach(g => pista.removeChild(g));
  fila.classList.remove('anda', 'centrado', 'flechas'); caja.classList.remove('con-flechas');
  if (grupo.scrollWidth <= fila.clientWidth + 2) { fila.classList.add('centrado'); return; }
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { fila.classList.add('flechas'); caja.classList.add('con-flechas'); return; }
  const copia = grupo.cloneNode(true);
  copia.classList.add('copia'); copia.setAttribute('aria-hidden', 'true'); copia.inert = true;
  pista.appendChild(copia);
  pista.style.setProperty('--dur', Math.round(grupo.children.length * 9) + 's');
  fila.classList.add('anda');
}
const montarCarruseles = () => $$('.gc-fila').forEach(montarCarrusel);
/* «Elegir juego»: todas en una fila mientras cada tarjeta mida al menos 175 px; si no, filas parejas */
function ajustarGrilla() {
  const g = $('.gc-grilla'); if (!g) return;
  const n = g.children.length, W = g.clientWidth, gap = parseFloat(getComputedStyle(g).columnGap) || 14;
  let filas = 1, cols = n;
  while (cols > 1 && (W - gap * (cols - 1)) / cols < 175) { filas++; cols = Math.ceil(n / filas); }
  g.style.setProperty('--cols', cols);
}

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   Página 1 · ENTRAR
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
function botonProv(p) {
  const on = S.configurado && S.proveedores[p];
  return `<button type="button" class="lg-prov ${p}" data-prov="${p}" ${on ? '' : 'disabled title="Todavía no está disponible"'}><span class="logo">${p === 'discord' ? SVG_DISCORD : SVG_GOOGLE}</span>Continuar con ${PROV[p]}<span class="fl">${on ? ic('arrow', 's16') : '<small class="tenue">pronto</small>'}</span></button>`;
}
function resultadoLogin(e) {
  if (!e) return '';
  const N = PROV[e.proveedor] || 'el proveedor';
  if (e.error === 'no_vinculada') return `<div class="lg-resultado" role="alert">
    <div class="cab">${ic('link', 's16')}<div><b>Esta cuenta de ${N} no está vinculada a ningún Eñeños-ID</b><span>${N} la reconoció, pero ningún Eñeños-ID tiene este ${N} vinculado.</span></div></div>
    ${e.nombre ? `<div class="lg-quien">${logoProv(e.proveedor, 18)}<span class="t"><b>${esc(e.nombre)}</b><span>cuenta de ${N}</span></span></div>` : ''}
    <div class="lg-como">Para vincularla:
      <ol><li><span>En el <b>launcher Eñeños</b>: su perfil → <code>Cuentas vinculadas</code> → Vincular ${N}.</span></li>
      <li><span>Vuelva aquí y toque «Continuar con ${N}» otra vez.</span></li></ol></div>
    <div class="acc"><button type="button" class="btn chico" data-accion="lg-otra">Probar con otra cuenta</button></div></div>`;
  if (e.error === 'sin_permisos') return `<div class="lg-resultado sin-permiso" role="alert">
    <div class="cab">${ic('lock', 's16')}<div><b>Su Eñeños-ID no tiene permisos en el Coordinador</b><span>La cuenta existe y está vinculada, pero nadie le dio un rol del equipo.</span></div></div>
    <div class="lg-quien">${ava(e.nombre || String(e.eid), 'redondo')}<span class="t"><b>${esc(e.nombre)}</b><span>Eñeños-ID ${esc(e.eid)} · vinculado con ${N}</span></span></div>
    <div class="lg-como">Si es del equipo:
      <ol><li><span>Pídale a un Admin que lo agregue en <b>Moderadores y permisos</b> con su Eñeños-ID <code>${esc(e.eid)}</code>.</span></li>
      <li><span>Cuando le asigne un juego, vuelva a entrar. No hace falta nada más.</span></li></ol></div>
    <div class="acc"><button type="button" class="btn chico" data-accion="lg-otra">Usar otra cuenta</button><button type="button" class="btn chico fantasma" data-accion="lg-copiar" data-txt="${esc(e.eid)}">${ic('copy', 's14')}Copiar mi Eñeños-ID</button></div></div>`;
  return `<div class="lg-resultado" role="alert"><div class="cab">${ic('alert', 's16')}<div><b>No se pudo entrar</b><span>${esc(e.texto || 'Vuelva a intentarlo.')}</span></div></div>
    <div class="acc"><button type="button" class="btn chico" data-accion="lg-otra">Volver a intentar</button></div></div>`;
}
function vistaLogin() {
  document.body.className = '';
  document.title = 'Coordinador Eñeños';
  raiz.innerHTML = `<div id="vLogin">${fondoFx(S.catalogo)}
    <div class="lg-bloque">
      <aside class="lg-col">
        <div class="lg-marca"><img src="assets/enenos-team.png" alt="Eñeños Team"><span class="coord">COORDINADOR</span></div>
        <div class="lg-form">
          <span class="rayas" aria-hidden="true"><i></i><i></i><i></i></span>
          <h1 style="margin-top:14px">Entre al Coordinador</h1>
          <p class="lg-sub">Con el Discord o el Google que vinculó a su Eñeños-ID.</p>
          <div class="lg-proveedores" id="lgProv">${botonProv('discord')}${botonProv('google')}</div>
          <div class="lg-esperando" id="lgEsp" aria-live="polite">${S.configurado ? '' : 'El ingreso todavía no está configurado en este servidor.'}</div>
          <div id="lgRes" aria-live="assertive">${resultadoLogin(S.errorLogin)}</div>
          <div class="lg-equipo">${ic('lock', 's14')}<span>Acceso sólo para el equipo de Eñeños. Cada ingreso queda registrado en la auditoría.</span></div>
        </div>
      </aside>
      ${S.catalogo.length ? carrusel(S.catalogo.map((x, i) => tarjetaJuego(x, 'login', i)).join(''), 'login', 'Los juegos de la red Eñeños') : ''}
    </div>
  </div>`;
  montarCarruseles();
}
async function entrarCon(prov) {
  const cont = $('#lgProv');
  if (!cont || cont.classList.contains('esperando')) return;
  const btn = $(`.lg-prov[data-prov="${prov}"]`);
  cont.classList.add('esperando'); btn.classList.add('activo');
  $$('.lg-prov').forEach(b => { b.disabled = true; });
  const fl = btn.querySelector('.fl'); if (fl) fl.outerHTML = '<span class="giro" aria-hidden="true"></span>';
  $('#lgEsp').textContent = `Lo llevamos a ${PROV[prov]}…`;
  $('#lgRes').innerHTML = '';
  S.errorLogin = null;
  const r = await api('oauth', { proveedor: prov });
  if (r.ok && r.d.url && /^https:\/\//.test(r.d.url)) { location.assign(r.d.url); return; }
  S.errorLogin = { error: 'fallo', texto: (r.d && r.d.error) || 'No se pudo empezar.' };
  vistaLogin();
}
async function canjearTicket(ticket) {
  const r = await api('canjear', { ticket });
  if (r.ok) { toast({ t: `Hola, ${esc(r.d.nombre)}`, sub: `Entró con ${PROV[r.d.via] || ''} · Eñeños-ID ${esc(r.d.uid)}` }); return true; }
  S.errorLogin = r.d || { error: 'fallo' };
  return false;
}

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   La barra de arriba
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
function rolTxt() {
  if (esAdmin()) return 'Admin · toda la red';
  if (S.sesion.lista_vieja) return 'Moderador · todos los juegos';
  const ns = (S.sesion.juegos || []).map(id => (S.catalogo.find(j => j.id === id) || { nombre: id }).nombre);
  return 'Moderador · ' + (ns.join(', ') || 'sin juegos');
}
function barraHub(activa) {
  const nav = (id, t) => `<a href="#/${id}" class="${activa === id ? 'on' : ''}" ${activa === id ? 'aria-current="page"' : ''}>${t}</a>`;
  return `<header class="barra">
    <a class="marca-chica" href="#/juegos" aria-label="Coordinador Eñeños, elegir juego"><img src="assets/enenos-team.png" alt=""><span class="coord">COORDINADOR</span></a>
    <nav class="barra-nav" aria-label="Secciones">${nav('juegos', 'Juegos')}${nav('red', 'La red')}<a href="#/novedades" class="pill-nov ${activa === 'novedades' ? 'on' : ''}" ${activa === 'novedades' ? 'aria-current="page"' : ''}>${ic('mega', 's14')}Novedades${novSucio() ? '<span class="pt" title="Hay cambios sin publicar"></span>' : ''}</a></nav>
    <span class="esp"></span>
    <button type="button" class="yo" data-accion="yo" aria-haspopup="true" aria-expanded="false">${ava(S.sesion.nombre, 'm')}<span class="t"><b>${esc(S.sesion.nombre)}</b><span>${esAdmin() ? 'Admin' : 'Moderador'}</span></span>${ic('down', 's14 tenue')}</button>
  </header>`;
}
const etqJuego = jid => { const j = S.catalogo.find(x => x.id === jid); return j ? `<span class="etq-juego" style="--g:${okColor(j.color)}">${esc(j.nombre)}</span>` : ''; };

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   Página 2 · ELEGIR JUEGO
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
async function vistaJuegos(silencioso) {
  document.body.classList.remove('test', 'menu-abierto');
  document.title = 'Elegir juego · Coordinador Eñeños';
  const r = await api('juegos');
  if (!r.ok) { if (r.status !== 401) toast({ t: 'No se pudieron leer los juegos', sub: errTxt(r), tipo: 'err' }); return; }
  if (S.ruta !== '#/juegos') return;
  const vis = S.juegos = r.d.juegos || [];
  const h = new Date().getHours(), sal = h < 12 ? 'Buenos días' : h < 20 ? 'Buenas tardes' : 'Buenas noches';
  const nums = vis.map(j => j.servidores && j.servidores.live && typeof j.servidores.live.jugando === 'number' ? j.servidores.live.jugando : null).filter(n => n !== null);
  const invs = vis.reduce((a, j) => a + (j.invitaciones || 0), 0);
  const y = window.scrollY;
  raiz.innerHTML = barraHub('juegos') + fondoFx(vis.length ? vis : S.catalogo) + `<main class="pag-elegir" id="contenido">
    <header class="el-cab">
      <span class="rayas" aria-hidden="true"><i></i><i></i><i></i></span>
      <h1>${sal}, ${esc(S.sesion.nombre)}</h1>
      <p><span class="rol ${esAdmin() ? '' : 'mod'}">${ic(esAdmin() ? 'crown' : 'shieldok', 's14')}${esc(rolTxt())}</span><span>Elija un juego: <b style="color:var(--tx)">PROD</b> es el servidor real y <b style="color:var(--amber)">TEST</b>, el de prueba.</span></p>
    </header>
    ${vis.length ? `<section class="gc-grilla" style="--n:${vis.length}" aria-label="Sus juegos">${vis.map((j, i) => tarjetaJuego(j, 'elegir', i)).join('')}</section>`
      : `<section class="caja" style="max-width:520px;margin:0 auto">${vacio('Todavía no tiene juegos asignados', 'Cuando un Admin le asigne un juego en «Moderadores y permisos», aparece aquí.')}</section>`}
    <footer class="el-pie">
      ${nums.length ? `<span><span class="punto vivo"></span> <b class="num">${nums.reduce((a, b) => a + b, 0)}</b> jugando ahora${nums.length < vis.filter(j => j.tiene_servidor).length ? ' <span class="tenue">(de los juegos que lo informan)</span>' : ''}</span>` : ''}
      <span>${ic('mail', 's14')} <b class="num">${invs}</b> ${invs === 1 ? 'invitación' : 'invitaciones'} por aprobar</span>
      <a class="btn chico" href="#/red">${ic('globe', 's14')}La red: personas, invitaciones${esAdmin() ? ', equipo' : ''} y auditoría ${ic('arrow', 's14')}</a>
    </footer>
  </main>`;
  if (silencioso) window.scrollTo(0, y);
  tic();
  ajustarGrilla();
}

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   Página 3 · LA RED
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
const ACC_TXT = { aprobar: ['aprobó a', 'check', 'verde'], quitar: ['le quitó la aprobación a', 'x', ''], banear: ['baneó a', 'ban', 'rojo'],
  desbanear: ['desbaneó a', 'check', 'verde'], 'rechazar invitación': ['rechazó la invitación de', 'x', ''],
  'entrar al Coordinador': ['entró al Coordinador', 'logout', 'verde'], 'entrar al panel': ['entró al panel chico', 'logout', 'verde'],
  'equipo: agregar moderador': ['sumó al equipo a', 'shieldok', 'rosa'], 'equipo: juegos del moderador': ['cambió los juegos de', 'shieldok', 'rosa'],
  'equipo: quitar moderador': ['sacó del equipo a', 'shieldok', 'rosa'] };
function tlItem(a) {
  const [txt, icono, c] = ACC_TXT[a.accion] || [esc(a.accion), 'history', 'cian'];
  const quien = a.persona ? ` <b>${a.uid ? `<a href="#/persona/${esc(a.uid)}">${esc(a.persona)}</a>` : esc(a.persona)}</b>${a.usuario ? ` <span class="tenue">(${esc(a.usuario)})</span>` : ''}` : '';
  const det = a.detalle ? ` · <span class="tenue">«${esc(a.detalle)}»</span>` : '';
  const env = a.pase && a.juego ? (/-prueba$/.test(a.pase) ? '<span class="etq-env test">TEST</span>' : '') : '';
  return `<li><span class="ic ${c}">${ic(icono, 's14')}</span><div class="txt"><b>${esc(a.quien)}</b> ${txt}${quien}${det}<div class="meta">${a.juego ? etqJuego(a.juego) : '<span class="etq-juego" style="--g:81,216,229">Red</span>'}${env}</div></div><span class="cuando">${fechaTxt(a.cuando)}</span></li>`;
}
function vistaRed() {
  document.body.classList.remove('test', 'menu-abierto');
  document.title = 'La red · Coordinador Eñeños';
  raiz.innerHTML = barraHub('red') + `<main class="hub" id="contenido">
    <section class="red-cab" aria-label="La red ahora">
      <h1>La red</h1>
      <span class="rol ${esAdmin() ? '' : 'mod'}">${ic(esAdmin() ? 'crown' : 'shieldok', 's14')}${esc(rolTxt())}</span>
      <span class="dato">${ic('mail', 's14')}<b id="kpiInv">…</b> invitaciones</span>
    </section>
    <section class="red">
      <div style="display:flex;flex-direction:column;gap:16px;min-width:0">
        <section class="caja" id="cajaCuentas" aria-labelledby="tCuentas">
          <div class="caja-cab"><h3 id="tCuentas">${ic('globe', 's16')}Personas</h3><span class="sub">un Eñeños-ID, sus vínculos y sus permisos</span></div>
          <div class="caja-cuerpo"><label class="campo">${ic('search', 's16')}<span class="sr">Buscar persona</span><input id="qCuenta" placeholder="${esAdmin() ? 'Eñeños-ID, Ñ2-ID (apodo) o usuario…' : 'Eñeños-ID, Ñ2-ID (apodo) o usuario exacto…'}" autocomplete="off" spellcheck="false"></label></div>
          <ul class="lista" id="resCuentas"><li style="justify-content:center;padding:18px 16px;color:var(--tx-3);font-size:13px">Escriba para buscar.</li></ul>
        </section>
        <section class="caja" aria-labelledby="tBan">
          <div class="caja-cab"><h3 id="tBan">${ic('ban', 's16')}Baneos vigentes <span class="n rosa" id="nBan">…</span></h3><span class="sub">cuánto falta para que venza cada uno</span></div>
          <ul class="lista" id="listaBan"><li><div class="t tenue">Cargando…</div></li></ul>
        </section>
        <section class="caja" aria-labelledby="tAud">
          <div class="caja-cab"><h3 id="tAud">${ic('history', 's16')}Auditoría ${esAdmin() ? 'de la red' : ''}</h3><span class="sub">${esAdmin() ? 'todo lo que hizo el equipo' : 'los movimientos en sus juegos'}</span></div>
          <ul class="tl" id="tlRed"><li><div class="txt tenue">Cargando…</div></li></ul>
        </section>
      </div>
      <div style="display:flex;flex-direction:column;gap:16px;min-width:0">
        <section class="caja" id="cajaLanz" aria-label="Lanzamientos e invitaciones">
          <div class="pest" role="tablist">
            <button type="button" role="tab" data-tab="inv" aria-selected="${S.tabRed !== 'lanz'}">${ic('mail', 's14')}Invitaciones <span class="n rosa" id="nInv">…</span></button>
            <button type="button" role="tab" data-tab="lanz" aria-selected="${S.tabRed === 'lanz'}">${ic('rocket', 's14')}Lanzamientos <span class="n" id="nLanz">…</span></button>
          </div>
          <div id="panInv" ${S.tabRed === 'lanz' ? 'hidden' : ''}></div>
          <div id="panLanz" ${S.tabRed === 'lanz' ? '' : 'hidden'}></div>
        </section>
        ${esAdmin() ? `<section class="caja" aria-labelledby="tMods">
          <div class="caja-cab"><h3 id="tMods">${ic('shieldok', 's16')}Moderadores y permisos</h3><span class="sub" id="subMods"></span>
            <div class="der"><button type="button" class="btn chico" data-accion="agregar-mod">${ic('plus', 's14')}Agregar</button></div></div>
          <ul class="lista" id="listaMods"></ul>
          <div class="tenue" style="padding:10px 16px 14px;border-top:1px solid var(--line);font-size:12px">Toque un juego para asignarlo o quitarlo. Cada moderador ve sólo sus juegos, y ahí puede aprobar, quitar y banear por juego.</div>
        </section>` : `<section class="caja"><div class="caja-cab"><h3>${ic('shieldok', 's16')}Sus permisos</h3></div>
          <div class="caja-cuerpo" style="font-size:13px;color:var(--tx-2);display:flex;flex-direction:column;gap:8px">${tusPermisos()}</div></section>`}
      </div>
    </section>
  </main>`;
  pintarInvitaciones(); pintarLanzamientos(); pintarAuditoria(); pintarBaneos();
  if (esAdmin()) pintarMods();
}
function tusPermisos() {
  const ns = (S.sesion.juegos || []).map(id => (S.catalogo.find(j => j.id === id) || { nombre: id }).nombre).join(', ');
  if (S.sesion.lista_vieja) return `<span>${ic('check', 's14')} Buscar personas y aprobar o quitar el acceso en todos los juegos</span>
    <span class="tenue">${ic('lock', 's14')} Banear, y las cuentas del equipo: sólo Admin</span>`;
  return `<span>${ic('check', 's14')} Ver y buscar personas en ${esc(ns) || '—'}</span>
    <span>${ic('check', 's14')} Aprobar, quitar, banear y desbanear por juego en ${esc(ns) || '—'}</span>
    <span>${ic('check', 's14')} Decidir las invitaciones anticipadas de sus juegos</span>
    <span class="tenue">${ic('lock', 's14')} Las cuentas del equipo y la red entera: sólo Admin</span>`;
}
let reqBuscar = 0;
async function pintarCuentas(q) {
  const ul = $('#resCuentas'); if (!ul) return;
  q = q.trim();
  if (!q) { ul.innerHTML = '<li style="justify-content:center;padding:18px 16px;color:var(--tx-3);font-size:13px">Escriba para buscar.</li>'; return; }
  const n = ++reqBuscar;
  const r = await api('personas?q=' + encodeURIComponent(q));
  if (n !== reqBuscar || !$('#resCuentas')) return;
  if (!r.ok) { ul.innerHTML = `<li style="justify-content:center;padding:18px 16px;color:var(--tx-3);font-size:13px">${errTxt(r)}</li>`; return; }
  const ps = r.d.personas || [];
  ul.innerHTML = ps.length ? ps.map(p => `<li class="click" tabindex="0" role="link" data-ir="#/persona/${esc(p.uid)}">
      ${ava(p.nombre, 'redondo')}
      <div class="t"><b>${esc(p.nombre)} ${p.estado !== 'activa' ? `<span class="chip rojo" style="height:18px;font-size:10px;margin-left:4px">${p.estado === 'baneada' ? 'SUSPENDIDA' : esc(p.estado.toUpperCase())}</span>` : ''}${p.rol ? `<span class="chip" style="height:18px;font-size:10px;margin-left:4px">${p.rol === 'admin' ? 'ADMIN' : 'MODERADOR'}</span>` : ''}</b>
        <span>Eñeños-ID ${esc(p.uid)}${p.usuario ? ` · usuario ${esc(p.usuario)}` : ''}</span></div>
      <span class="mini-juegos">${(p.vias || []).map(v => `<span class="mj on" title="${PROV[v] || esc(v)} vinculado">${logoProv(v, 14)}</span>`).join('')}</span>
    </li>`).join('') : `<li style="justify-content:center;padding:22px 16px;color:var(--tx-3);font-size:13px">Ninguna persona coincide con «${esc(q)}».</li>`;
}
async function pintarInvitaciones() {
  const pan = $('#panInv'); if (!pan) return;
  const r = await api('invitaciones');
  if (!$('#panInv')) return;
  if (!r.ok) { pan.innerHTML = `<div class="caja-cuerpo tenue">${errTxt(r)}</div>`; return; }
  const invs = r.d.invitaciones || [];
  $('#nInv').textContent = invs.length; $('#kpiInv').textContent = invs.length;
  pan.innerHTML = invs.length ? `<ul class="lista">${invs.map(v => `<li data-inv="${esc(v.id)}">${ava(v.nombre, 'redondo')}
      <div class="t"><b><a href="#/persona/${esc(v.uid)}">${esc(v.nombre)}</a> <span class="tenue" style="font-weight:500">Eñeños-ID ${esc(v.uid)}${v.usuario ? ` · ${esc(v.usuario)}` : ''}</span></b><span style="margin-top:3px">${etqJuego(v.juego)} <span class="chip mayus" style="height:18px;font-size:10px">${esc(v.etiqueta)}</span> <span class="muy-tenue">· ${haceSeg(v.creada)}</span></span></div>
      <button type="button" class="btn chico" data-accion="inv-decidir" data-dec="aprobar" data-id="${esc(v.id)}" aria-label="Aprobar a ${esc(v.nombre)}">${ic('check', 's14')}<span>Aprobar</span></button>
      <button type="button" class="btn icono chico fantasma" data-accion="inv-decidir" data-dec="rechazar" data-id="${esc(v.id)}" aria-label="Rechazar a ${esc(v.nombre)}" title="Rechazar">${ic('x', 's14')}</button></li>`).join('')}</ul>`
    : vacio('Nada por aprobar', 'Las solicitudes llegan desde el botón «Solicitar invitación anticipada» del launcher.');
}
async function pintarLanzamientos() {
  const pan = $('#panLanz'); if (!pan) return;
  const r = await api('lanzamientos');
  if (!$('#panLanz')) return;
  if (!r.ok) { pan.innerHTML = `<div class="caja-cuerpo tenue">${errTxt(r)}</div>`; return; }
  const ls = r.d.lanzamientos || [];
  $('#nLanz').textContent = ls.length;
  pan.innerHTML = ls.length ? ls.map(l => `<div class="lanz">
      <span class="ic">${okArte(l.arte) ? `<img src="${esc(l.arte)}" style="object-position:${okPos(l.pos)}" alt="">` : l.juego === 'r2beat-moderno' ? arte2027() : arteColor(l)}</span>
      <div style="min-width:0"><b style="font-weight:600">${esc(l.nombre)}</b> <span class="chip mayus" style="margin-left:4px;--g:0">${esc(l.etiqueta)}</span>
        <div class="tenue" style="font-size:12.5px;margin-top:3px">${l.libre ? 'Abierto desde el' : 'Abre el'} ${fechaEpoch(l.desde)} (su hora)${l.pendientes ? ` · ${l.pendientes} por aprobar` : ''}</div></div>
      <div class="reloj">${l.libre ? `<span style="color:var(--green)">Abierto</span>` : `<span data-cuenta="${l.desde * 1000}">--</span><small>para abrir</small>`}</div></div>`).join('')
    + `<div class="tenue" style="padding:10px 16px 14px;border-top:1px solid var(--line);font-size:12px">${ic('info', 's14')} Antes de la fecha sólo entran el equipo y los aprobados. La fecha la cambia un Admin en la página de cada juego, en «Lanzamiento».</div>`
    : vacio('Sin lanzamientos', 'Ningún juego suyo tiene una fecha de apertura programada.');
  tic();
}
async function pintarAuditoria() {
  const ul = $('#tlRed'); if (!ul) return;
  const r = await api('auditoria');
  if (!$('#tlRed')) return;
  if (!r.ok) { ul.innerHTML = `<li><div class="txt tenue">${errTxt(r)}</div></li>`; return; }
  const as = (r.d.auditoria || []).slice(0, 25);
  ul.innerHTML = as.length ? as.map(tlItem).join('') : `<li><div class="txt tenue">Todavía nada.</div></li>`;
}
async function pintarMods(datos) {
  const ul = $('#listaMods'); if (!ul) return;
  let d = datos;
  if (!d) { const r = await api('equipo'); if (!r.ok) { ul.innerHTML = `<li class="tenue">${errTxt(r)}</li>`; return; } d = r.d; }
  S.equipo = d;
  if (!$('#listaMods')) return;
  $('#subMods').textContent = `${d.admins.length + d.moderadores.length} personas · ${d.juegos.length} juegos`;
  const fila = (m, i) => {
    const admin = m.rol === 'admin', vieja = !admin && m.juegos === null;
    const tiene = jid => admin || vieja || (m.juegos || []).includes(jid);
    return `<li>${ava(m.nombre, 'redondo')}
      <div class="t"><b><a href="#/persona/${esc(m.uid)}">${esc(m.nombre)}</a>${m.yo ? ' <span class="tenue" style="font-weight:500">(usted)</span>' : ''}</b><span>${admin ? 'Admin' : 'Moderador'} · Eñeños-ID ${esc(m.uid)}${m.usuario ? ` · ${esc(m.usuario)}` : ''}${m.vias.length ? '' : ' · <span style="color:var(--gold)">sin Discord ni Google: no puede entrar</span>'}${vieja ? ' · <span class="tenue">formato viejo: todos los juegos, sin banear</span>' : ''}</span></div>
      <span class="mini-juegos" role="group" aria-label="Juegos de ${esc(m.nombre)}">${d.juegos.map(j => `<button type="button" class="mj ${tiene(j.id) ? 'on' : ''}" style="--g:${okColor(j.color)}" data-accion="mod-juego" data-i="${i}" data-j="${esc(j.id)}" aria-pressed="${tiene(j.id)}" ${admin ? 'disabled title="Un Admin ve todos los juegos"' : ''}><span class="p"></span>${esc(j.nombre)}</button>`).join('')}
      ${admin ? '' : `<button type="button" class="btn icono chico fantasma" data-accion="quitar-mod" data-i="${i}" aria-label="Sacar a ${esc(m.nombre)} del equipo" title="Sacar del equipo">${ic('x', 's14')}</button>`}</span></li>`;
  };
  const todos = [...d.admins, ...d.moderadores];
  S.equipoLista = todos;
  ul.innerHTML = todos.map(fila).join('') || `<li class="tenue">Sin nadie todavía.</li>`;
}
async function cambiarJuegosMod(i, jid) {
  const m = S.equipoLista[i]; if (!m || m.rol === 'admin') return;
  const ids = S.equipo.juegos.map(j => j.id);
  const actual = m.juegos === null ? ids : m.juegos;
  const nuevo = actual.includes(jid) ? actual.filter(x => x !== jid) : [...actual, jid];
  const hacer = async () => {
    const r = await api('equipo', { accion: 'juegos', uid: m.uid, juegos: nuevo });
    if (!r.ok) { toast({ t: 'No se pudo cambiar', sub: errTxt(r), tipo: 'err' }); return; }
    pintarMods(r.d);
    const j = S.equipo.juegos.find(x => x.id === jid);
    toast({ t: nuevo.includes(jid) ? `${esc(m.nombre)} ahora modera ${esc(j.nombre)}` : `${esc(m.nombre)} ya no modera ${esc(j.nombre)}`, sub: 'Vale desde su próximo pedido. Quedó en la auditoría.' });
  };
  if (m.juegos === null) confirmar({ titulo: `¿Asignarle juegos a ${esc(m.nombre)}?`, icono: 'shieldok', peligro: false, ok: 'Asignar',
    txt: 'Hoy está en el formato viejo (todos los juegos, sólo aprobar y quitar). Con juegos asignados ve <b>sólo esos juegos</b> y ahí también puede <b>banear y desbanear</b> por juego.', alAceptar: hacer });
  else hacer();
}

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   La PERSONA (#/persona/<uid>)
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
const ESTADO_CTA = { activa: ['verde', 'check', 'Activa'], baneada: ['rojo', 'ban', 'Suspendida en toda la red'], fusionada: ['', 'link', 'Unida a otra cuenta'] };
async function vistaPersona(uid) {
  document.body.classList.remove('test', 'menu-abierto');
  const r = await api('persona/' + encodeURIComponent(uid));
  if (!r.ok) { if (r.status !== 401) { toast({ t: 'No se puede abrir esa persona', sub: errTxt(r), tipo: 'err' }); go('#/red', true); } return; }
  if (S.ruta !== '#/persona/' + uid) return;
  pintarPersona(r.d.persona);
}
function pintarPersona(p) {
  document.title = `${p.nombre} · Coordinador Eñeños`;
  const [cc, ci, ct] = ESTADO_CTA[p.estado] || ['', 'info', p.estado];
  const fila = (j, x) => {
    const botones = [];
    const puede = a => p.acciones.includes(a);
    if (puede('aprobar') && !x.aprobada) botones.push(`<button type="button" class="btn chico" data-accion="persona-accion" data-acc="aprobar" data-pase="${esc(x.pase)}">${ic('check', 's14')}Aprobar</button>`);
    if (puede('quitar') && x.aprobada) botones.push(`<button type="button" class="btn chico fantasma" data-accion="persona-accion" data-acc="quitar" data-pase="${esc(x.pase)}">${ic('x', 's14')}Quitar aprobación</button>`);
    if (puede('banear') && !x.baneada) botones.push(`<button type="button" class="btn chico fantasma" data-accion="persona-accion" data-acc="banear" data-pase="${esc(x.pase)}">${ic('ban', 's14')}Banear</button>`);
    if (puede('desbanear') && x.baneada) botones.push(`<button type="button" class="btn chico" data-accion="persona-accion" data-acc="desbanear" data-pase="${esc(x.pase)}">${ic('check', 's14')}Desbanear</button>`);
    return `<li><span class="etq-env ${x.entorno === 'test' ? 'test' : 'live'}">${x.entorno === 'extra' ? 'OTRO' : ENV_TXT[x.entorno]}</span>
      <div class="t"><b>${esc(x.nombre)}</b><span>${x.permitido ? '<span style="color:var(--green)">Puede entrar</span>' : '<span style="color:var(--red)">No puede entrar</span>'}${x.abierto ? (!x.permitido && !x.baneada ? ' · todavía no abrió (lanzamiento): sólo el equipo y las aprobadas' : ' · para toda cuenta activa') : ' · sólo aprobadas'}${x.aprobada ? ' · aprobada' : ''}${x.baneada ? ` · <b style="color:var(--red)">baneada</b> <span style="color:var(--gold)">(${venceTxt(x.restante_seg)})</span>${x.motivo ? ` «${esc(x.motivo)}»` : ''}` : ''}</span></div>
      <span style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">${botones.join('')}</span></li>`;
  };
  raiz.innerHTML = barraHub('red') + `<main class="hub" id="contenido">
    <a class="volver" href="#/red" style="margin-bottom:12px;display:inline-flex">${ic('left', 's14')}La red</a>
    <section class="ficha-cab persona-cab"><div class="dentro">
      ${ava(p.nombre, 'g redondo')}
      <div style="min-width:0;flex:1">
        <div class="tenue" style="font:800 10.5px var(--sans);letter-spacing:1.5px;color:var(--cyan)">PERSONA · EÑEÑOS-ID ${esc(p.uid)}</div>
        <h1 style="margin-top:4px">${esc(p.nombre)} <span class="chip ${cc}">${ic(ci, 's14')}${esc(ct)}</span>${p.rol ? ` <span class="chip">${p.rol === 'admin' ? 'ADMIN' : 'MODERADOR'}</span>` : ''}</h1>
        <div class="ids"><span>Eñeños-ID <b>${esc(p.uid)}</b></span>${p.usuario ? `<span>usuario <b>${esc(p.usuario)}</b></span>` : ''}${p.creada ? `<span>alta <b>${fechaTxt(p.creada)}</b></span>` : ''}${p.visto ? `<span>visto ${haceSeg(p.visto)}</span>` : ''}</div>
        <div class="persona-vinc" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px">${p.vinculos.length ? p.vinculos.map(v => `<span class="chip" style="height:26px;padding:0 10px">${logoProv(v.proveedor)}${PROV[v.proveedor] || esc(v.proveedor)} vinculado${v.nombre ? ` · ${esc(v.nombre)}` : ''}</span>`).join('') : '<span class="tenue" style="font-size:13px">Sin Discord ni Google vinculado.</span>'}</div>
      </div>
    </div></section>
    <div class="titulo-sec"><h2>Permisos por juego</h2><span class="tenue">${p.acciones.length === 4 ? 'Aprobar, quitar, banear y desbanear, por servidor.' : 'Aprobar y quitar, por servidor.'}</span>${p.acciones.includes('banear') && p.juegos.some(j => j.pases.length) ? `<button type="button" class="btn chico" data-accion="banear-varios" style="margin-left:auto">${ic('ban', 's14')}Banear en varios juegos…</button>` : ''}</div>
    ${p.juegos.length ? p.juegos.map(j => `<section class="caja" style="margin-bottom:14px"><div class="caja-cab"><h3>${etqJuego(j.id)} ${esc(j.nombre)}</h3>${j.invitacion ? `<span class="sub">invitación anticipada: ${esc(j.invitacion)}</span>` : ''}</div>
      ${j.pases.length ? `<ul class="lista">${j.pases.map(x => fila(j, x)).join('')}</ul>` : '<div class="caja-cuerpo tenue" style="font-size:13px">Todavía no tiene servidor con pase.</div>'}</section>`).join('')
      : `<section class="caja">${vacio('Sin juegos para mostrar', 'No tiene juegos asignados en el Coordinador.')}</section>`}
    <div class="tenue" style="font-size:12px;margin-top:6px">${ic('info', 's14')} Personajes, sanciones dentro del juego y actividad: en la próxima fase.</div>
  </main>`;
  S.persona = p;
}
function accionPersona(acc, pase) {
  const p = S.persona; if (!p) return;
  const x = p.juegos.flatMap(j => j.pases).find(y => y.pase === pase); if (!x) return;
  const hacer = async motivo => {
    const r = await api('accion', { accion: acc, uid: p.uid, pase, detalle: motivo || '' });
    if (!r.ok) { toast({ t: 'No se pudo', sub: errTxt(r), tipo: 'err' }); return; }
    pintarPersona(r.d.persona);
    toast({ t: { aprobar: 'Aprobada', quitar: 'Aprobación quitada', banear: 'Baneada', desbanear: 'Desbaneada' }[acc] + ` en ${esc(x.nombre)}`, sub: 'Quedó en la auditoría.' });
  };
  if (acc === 'banear') formBaneo(pase);
  else if (acc === 'quitar') confirmar({ titulo: `¿Quitarle la aprobación en ${esc(x.nombre)}?`, ok: 'Quitar', icono: 'x', txt: 'Si el servidor es sólo para aprobadas, deja de poder entrar.', alAceptar: hacer });
  else hacer('');
}

/* ★ 20-nov — EL FORMULARIO DEL BANEO. `pase` = un solo servidor (el botón de la fila); sin él, casillas con los juegos
   (cada uno con TODOS sus servidores). Duración: horas / días / meses (30 d) / permanente (sólo Admin); un moderador, hasta su tope.
   El motivo es obligatorio (≤ 200): lo ve la persona en el launcher al apretar «Jugar». El servidor exige lo mismo. */
function formBaneo(pase) {
  const p = S.persona; if (!p) return;
  const lim = p.sancion || { permanente: false, red: false, tope_seg: null, motivo_max: 200 };
  const uno = pase ? p.juegos.flatMap(j => j.pases).find(y => y.pase === pase) : null;
  if (pase && !uno) return;
  const juegos = p.juegos.filter(j => j.pases.length);
  const pn = abrirCapa(`<div class="modal ancho" role="dialog" aria-modal="true" aria-labelledby="bnTit">
    <div class="modal-cab"><span class="ic">${ic('ban', 's20')}</span><div><h2 id="bnTit">Banear a ${esc(p.nombre)}</h2>
      <p>${uno ? `En ${esc(uno.nombre)}.` : 'Cada juego que marque, con todos sus servidores (PROD y TEST).'} Al apretar «Jugar», el launcher le muestra el motivo y cuánto falta.</p></div></div>
    <div class="modal-cuerpo" style="display:flex;flex-direction:column;gap:16px">
      ${uno ? '' : `<div><span class="lab">Juegos</span><div class="alcance" id="bnJuegos">${juegos.map(j => `<label class="radio"><input type="checkbox" value="${esc(j.id)}"><span><b>${esc(j.nombre)}</b><span>${j.pases.map(x => x.entorno === 'extra' ? 'OTRO' : ENV_TXT[x.entorno]).join(' · ')}${j.pases.some(x => x.baneada) ? ' · ya tiene un baneo (se reemplaza)' : ''}</span></span></label>`).join('')}
        ${lim.red ? `<label class="radio"><input type="checkbox" id="bnRed"><span><b>Toda la red</b><span>Todos los juegos de Eñeños, con todos sus servidores (sólo Admin)</span></span></label>` : ''}</div></div>`}
      <div><span class="lab">Duración</span>
        <div class="chips" role="group" aria-label="Duración"><button type="button" class="chipb" data-bn="horas" aria-pressed="true">Horas</button><button type="button" class="chipb" data-bn="dias" aria-pressed="false">Días</button><button type="button" class="chipb" data-bn="meses" aria-pressed="false">Meses</button>${lim.permanente ? '<button type="button" class="chipb" data-bn="permanente" aria-pressed="false">Permanente</button>' : ''}</div>
        <label class="campo" id="bnCantCampo" style="margin-top:8px;max-width:200px"><span class="sr">Cantidad</span><input id="bnCant" type="number" min="1" step="1" value="24" inputmode="numeric"><span class="tenue" id="bnUnidad" style="font-size:13px">horas</span></label>
        ${lim.tope_seg ? `<div class="tenue" style="font-size:12px;margin-top:6px">Como moderador puede banear hasta ${fmtDur(lim.tope_seg / 60)}. Más largo, o permanente: un Admin.</div>` : ''}</div>
      <div><span class="lab">Motivo (lo ve la persona y queda en la auditoría)</span>
        <label class="campo"><span class="sr">Motivo</span><input id="bnMotivo" maxlength="${Number(lim.motivo_max) || 200}" autocomplete="off" placeholder="Por ejemplo: insultos en el chat"></label>
        <div class="cuenta-txt"><span id="bnErr" style="color:var(--red)"></span><span id="bnCuenta">0/${Number(lim.motivo_max) || 200}</span></div></div>
    </div>
    <div class="modal-pie"><button type="button" class="btn" data-accion="cerrar-capa">Cancelar</button><button type="button" class="btn peligro lleno" id="bnOk">Banear</button></div></div>`);
  let tipo = 'horas';
  const UNI = { horas: { txt: 'horas', min: 60 }, dias: { txt: 'días', min: 1440 }, meses: { txt: 'meses (30 días)', min: 43200 } };
  const err = t => { $('#bnErr', pn).textContent = t || ''; };
  $$('[data-bn]', pn).forEach(b => b.addEventListener('click', () => {
    tipo = b.dataset.bn;
    $$('[data-bn]', pn).forEach(x => x.setAttribute('aria-pressed', x === b));
    $('#bnCantCampo', pn).hidden = tipo === 'permanente';
    $('#bnUnidad', pn).textContent = UNI[tipo] ? UNI[tipo].txt : '';
    err('');
  }));
  const red = $('#bnRed', pn);
  if (red) red.addEventListener('change', () => $$('#bnJuegos input[type=checkbox]:not(#bnRed)', pn).forEach(c => { c.disabled = red.checked; c.closest('.radio').classList.toggle('off', red.checked); }));
  const mot = $('#bnMotivo', pn);
  mot.addEventListener('input', () => { $('#bnCuenta', pn).textContent = `${mot.value.length}/${Number(lim.motivo_max) || 200}`; err(''); });
  $('#bnOk', pn).addEventListener('click', async () => {
    const cuerpo = { accion: 'banear', uid: p.uid, motivo: mot.value.trim() };
    if (uno) cuerpo.pase = pase;
    else if (red && red.checked) cuerpo.red = true;
    else {
      cuerpo.juegos = $$('#bnJuegos input[type=checkbox]:checked:not(#bnRed)', pn).map(c => c.value);
      if (!cuerpo.juegos.length) return err('Marque al menos un juego.');
    }
    if (tipo === 'permanente') cuerpo.permanente = true;
    else {
      const n = Number($('#bnCant', pn).value);
      if (!Number.isInteger(n) || n < 1) return err('La duración tiene que ser un número entero, 1 o más.');
      if (lim.tope_seg && n * UNI[tipo].min * 60 > lim.tope_seg) return err(`Como moderador, hasta ${fmtDur(lim.tope_seg / 60)}.`);
      cuerpo[tipo] = n;
    }
    if (!cuerpo.motivo) { mot.focus(); return err('Escriba el motivo.'); }
    const b = $('#bnOk', pn); b.disabled = true;
    const r = await api('accion', cuerpo);
    b.disabled = false;
    if (!r.ok) return err((r.d && (r.d.texto || r.d.error)) || `Error ${r.status}`);
    cerrarCapa();
    pintarPersona(r.d.persona);
    const dur = tipo === 'permanente' ? 'de forma permanente' : `por ${fmtDur(Number(cuerpo[tipo]) * UNI[tipo].min)}`;
    toast({ t: `Baneada ${dur}`, sub: (uno ? esc(uno.nombre) : cuerpo.red ? 'En toda la red' : esc(cuerpo.juegos.map(id => (juegos.find(j => j.id === id) || { nombre: id }).nombre).join(', '))) + ' · quedó en la auditoría.' });
  });
}

/* ★ 20-nov: los baneos VIGENTES de sus juegos, en la red: quién, dónde, cuánto falta, y desbanear antes de tiempo */
async function pintarBaneos() {
  const ul = $('#listaBan'); if (!ul) return;
  const r = await api('baneos');
  if (!$('#listaBan')) return;
  if (!r.ok) { ul.innerHTML = `<li><div class="t tenue">${errTxt(r)}</div></li>`; return; }
  const bs = r.d.baneos || [];
  S.baneos = bs;
  $('#nBan').textContent = bs.length;
  ul.innerHTML = bs.length ? bs.slice(0, 60).map((b, i) => `<li>${ava(b.persona, 'redondo')}
      <div class="t"><b><a href="#/persona/${esc(b.uid)}">${esc(b.persona)}</a>${b.usuario ? ` <span class="tenue" style="font-weight:500">${esc(b.usuario)}</span>` : ''}</b>
        <span style="margin-top:3px">${etqJuego(b.juego)} <span class="tenue">${esc(b.nombre)}</span> · <b style="color:${b.restante_seg == null ? 'var(--red)' : 'var(--gold)'};font-weight:600">${venceTxt(b.restante_seg)}</b> · «${esc(b.motivo)}» <span class="muy-tenue">· ${esc(b.quien)}</span></span></div>
      <button type="button" class="btn chico" data-accion="ban-levantar" data-i="${i}" aria-label="Desbanear a ${esc(b.persona)} en ${esc(b.nombre)}">${ic('check', 's14')}<span>Desbanear</span></button></li>`).join('')
    : `<li style="justify-content:center;padding:18px 16px;color:var(--tx-3);font-size:13px">Nadie está baneado ahora en sus juegos.</li>`;
}
function levantarBaneo(i) {
  const b = (S.baneos || [])[i]; if (!b) return;
  confirmar({ titulo: `¿Desbanear a ${esc(b.persona)} en ${esc(b.nombre)}?`, ok: 'Desbanear', icono: 'check', peligro: false,
    txt: `Hoy está baneada (${esc(venceTxt(b.restante_seg))}). Vuelve a poder entrar al instante; el baneo queda en la auditoría.`,
    alAceptar: async () => {
      const r = await api('accion', { accion: 'desbanear', uid: b.uid, pase: b.pase });
      if (!r.ok) { toast({ t: 'No se pudo', sub: errTxt(r), tipo: 'err' }); return; }
      toast({ t: `Desbaneada en ${esc(b.nombre)}`, sub: 'Quedó en la auditoría.' });
      pintarBaneos(); pintarAuditoria();
    } });
}

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   ★ 20-nov · FASE B — lo de adentro de cada juego: el CONTENIDO DINÁMICO del launcher (#/j/<juego>/<live|test>/<parte>)
   asistencia · ruleta · tira (avisos del lobby) · lanzamiento. El diseño es el del prototipo aprobado (v5); los
   modelos son los REALES (servidor/contenido.py → contenido_interno.py del juego). ⛔ Lo que el juego no soporta no
   se muestra. Cada parte es un BORRADOR hasta «Publicar»; «Descartar» vuelve a lo último que se leyó.
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
const MESES_L = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const DIAS_PL = ['domingos', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábados'];
const DIAS_C = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
const ORD_SEM = ['', 'primera', 'segunda', 'tercera', 'cuarta', 'quinta'];
const JC_TABS = { asistencia: ['Asistencia', 'ticket'], ruleta: ['Ruleta', 'refresh'], tira: ['Avisos del lobby', 'mega'], lanzamiento: ['Lanzamiento', 'rocket'] };
const miles = n => String(Math.round(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const corto = n => { n = Number(n) || 0; return n >= 1000 ? (n % 1000 ? (n / 1000).toFixed(1).replace('.', ',') : n / 1000) + 'k' : String(n); };
const clon = x => JSON.parse(JSON.stringify(x));
/* el borrador se compara SIN las claves internas (`_k`): ésas no viajan */
const ser = x => JSON.stringify(x, (k, v) => (k && k[0] === '_' ? undefined : v));
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const dis = ro => (ro ? ' disabled' : '');
const entre = (v, a, b) => Math.max(a, Math.min(b, Math.round(Number(v) || 0)));
const isoLocal = d => `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}T${dos(d.getHours())}:${dos(d.getMinutes())}`;
const hoyIso = () => { const d = new Date(); return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`; };
const cambiadoTxt = c => (c && c.cambiado ? `Cambiado por ${esc(c.quien || 'alguien')} · ${haceSeg(c.cambiado)}` : 'Sin cambios: rige lo de fábrica.');
/* «AAAA-MM-DDTHH:MM» en hora de Perú (UTC−5, sin horario de verano) -> epoch */
const epochPeru = s => { const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(s || ''); return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4] + 5, +m[5]) / 1000 : null; };
const pct = (p, tot) => { if (!tot) return '0 %'; const x = 100 * p / tot; return (x > 0 && x < 1 ? x.toFixed(2) : x.toFixed(1)).replace('.', ',').replace(/,0+$/, '') + ' %'; };
const errBox = t => (t ? `<div class="conclusion raro" role="alert">${ic('alert', 's20')}<div>${esc(t)}<small>Corríjalo para poder publicar.</small></div></div>` : '');

/* el arte del launcher (no va al repo: lo sirve /arte/). Sin él, las vistas previas usan colores. */
const ARTE = { asis: null };
function probarArte(lista, alTerminar) {
  let n = lista.length, ok = true;
  const uno = bien => { ok = ok && bien; if (!--n) alTerminar(ok); };
  lista.forEach(src => { const im = new Image(); im.addEventListener('load', () => uno(true)); im.addEventListener('error', () => uno(false)); im.src = src; });
}
/* un <img data-fallo="…"> que no carga se cambia por su ícono (ver el listener de 'error') */
const FALLO = {
  rcoin: c => `<span class="ip svg ${c}" style="--c:227,187,103">${ic('coins')}</span>`,
  gorila: c => `<span class="ip svg ${c}" style="--c:61,220,132">${ic('coins')}</span>`,
  npc: c => `<span class="ip svg ${c}" style="--c:81,216,229">${ic('mega')}</span>`,
};
const imgRcoin = (c = '') => `<img class="ip ${c}" src="arte/moneda-rcoin.png" alt="" data-fallo="rcoin">`;
const imgGorila = (c = '') => `<img class="ip ${c}" src="arte/moneda-gorila.png" alt="" data-fallo="gorila">`;

/* ── los premios de la asistencia: {rcoin} · {item, cant} · {item, dias} ── */
function nomItem(id, nombre) {
  if (nombre) return nombre;
  const J = S.jc;
  return (J && J.nombres[id]) || `Ítem ${id}`;
}
function icPremio(p, c = '') {
  if (!p) return '';
  if (p.rcoin != null) return imgRcoin(c);
  const col = hashStr(String(p.item)) % 2 ? '243,38,134' : '179,139,255';
  return `<span class="ip svg ${c}" style="--c:${col}">${ic(p.dias != null ? 'shirt' : 'gift')}</span>`;
}
function premioTxt(p) {
  if (!p) return '';
  if (p.rcoin != null) return `${miles(p.rcoin)} Rcoin`;
  const n = nomItem(p.item, p.nombre);
  if (p.dias != null) return `${n} · ${p.dias ? p.dias + ' días' : 'permanente'}`;
  return `${p.cant > 1 ? p.cant + '× ' : ''}${n}`;
}
const premioCorto = p => (!p ? '' : p.rcoin != null ? corto(p.rcoin) : p.dias != null ? (p.dias ? p.dias + 'd' : '∞') : '×' + (p.cant || 1));

/* ══════════════ el estado de la página del juego ══════════════ */
function nuevoJc(d, jid, env) {
  const J = { jid, env, d, tab: null, borr: {}, orig: {}, err: {}, nombres: {}, filas: {}, mes: null, mesVer: null, dia: null, alcance: null,
              modoRueda: 'gorila', seq: 0, publicando: false };
  const s = d.servidor;
  if (s) {
    ponerAsis(J, s.asistencia, s.asistencia_mes);
    J.borr.ruleta = clon(s.ruleta || {});
    ponerTira(J, s.tira);
  }
  if (d.lanzamiento) J.borr.lanzamiento = { desde_peru: d.lanzamiento.desde_peru, etiqueta: d.lanzamiento.etiqueta || '' };
  Object.keys(J.borr).forEach(k => { J.orig[k] = ser(J.borr[k]); });
  return J;
}
function ponerAsis(J, a, mes) {
  const A = clon(a || {});
  A.semana = A.semana || {}; A.semana_mes = A.semana_mes || {}; A.fechas = A.fechas || {};
  if (A.activa === undefined) A.activa = true;
  if (A.tardias_mes === undefined) A.tardias_mes = 5;
  J.borr.asistencia = A;
  J.mes = mes || null;
  J.mesVer = mes ? `${mes.anio}-${dos(mes.mes)}` : null;
  nombresDe(J, mes);
  if (mes && !mes.dias.some(x => x.fecha === J.dia)) J.dia = ((mes.dias.find(x => x.hoy) || mes.dias[0]) || {}).fecha || null;
}
function ponerTira(J, filas) {
  J.filas = {};
  (filas || []).forEach(f => { J.filas[f.id] = f; });
  J.borr.tira = (filas || []).map(f => ({ id: f.id, texto: f.texto, siempre: !!f.siempre, vence: f.siempre ? null : f.vence, activo: !!f.activo, _k: 'f' + f.id }));
}
function nombresDe(J, mes) {
  if (!mes) return;
  mes.dias.forEach(x => [...(x.premios || []), ...(x.si_no || [])].forEach(p => { if (p.item != null && p.nombre) J.nombres[p.item] = p.nombre; }));
}
const tabsJc = J => [...(J.d.servidor ? ['asistencia', 'ruleta', 'tira'] : []), ...(J.d.lanzamiento ? ['lanzamiento'] : [])];
const puedeJc = (J, k) => (k === 'lanzamiento' ? !!J.d.es_admin : !!J.d.puede_editar);
const suciasJc = J => Object.keys(J.borr).filter(k => puedeJc(J, k) && ser(J.borr[k]) !== J.orig[k]);
const juegoCat = jid => S.catalogo.find(x => x.id === jid) || S.juegos.find(x => x.id === jid) || { id: jid, nombre: jid, color: '' };
const envTxt = env => ENV_TXT[env] || 'PROD';

/* ══════════════ la página ══════════════ */
async function vistaJuego(jid, env, tab) {
  document.body.classList.remove('menu-abierto');
  document.body.classList.toggle('test', env === 'test');
  const j = juegoCat(jid);
  document.title = `${j.nombre} · ${envTxt(env)} · Coordinador Eñeños`;
  const ruta0 = S.ruta;
  raiz.innerHTML = barraHub('juegos') + `<main class="hub jc" id="contenido">${cabJuego(j, env)}
    <div class="caja jc-carga" aria-live="polite"><span class="esq" style="height:14px;width:40%"></span><span class="esq" style="height:180px"></span><span class="tenue">Cargando el contenido del launcher…</span></div></main>`;
  if (ARTE.asis === null) { ARTE.asis = false; probarArte(['arte/asistencia-ticket_gris.png', 'arte/asistencia-digitos.png'], ok => { ARTE.asis = ok; if (ok && S.jc && S.jc.tab === 'asistencia') pintarPreviaJ(); }); }
  const [r, jr] = await Promise.all([api(`contenido?juego=${encodeURIComponent(jid)}&entorno=${env}`), S.juegos.length ? null : api('juegos')]);
  if (S.ruta !== ruta0) return;
  if (jr && jr.ok) S.juegos = jr.d.juegos || [];
  if (!r.ok) {
    if (r.status === 401) return;
    $('#contenido').innerHTML = `<a class="volver" href="#/juegos" style="margin-bottom:12px;display:inline-flex">${ic('left', 's14')}Juegos</a>
      <section class="caja" style="max-width:560px;margin:24px auto">${vacio('No se puede abrir este juego', errTxt(r), '<a class="btn chico" href="#/juegos">Volver a los juegos</a>')}</section>`;
    return;
  }
  S.jc = nuevoJc(r.d, jid, env);
  const ts = tabsJc(S.jc);
  S.jc.tab = ts.includes(tab) ? tab : ts[0] || null;
  pintarJ();
}
function cabJuego(j, env, J) {
  const pases = (S.juegos.find(x => x.id === j.id) || {}).pases || {};
  const envBtn = (e, icono) => {
    if (e === env) return `<span class="jc-envb on ${e}" aria-current="page">${ic(icono, 's14')}${envTxt(e)}</span>`;
    if (!pases[e]) return `<span class="jc-envb off" title="${e === 'test' ? 'Todavía no tiene servidor de prueba' : 'Sin servidor'}">${ic(icono, 's14')}${envTxt(e)}</span>`;
    return `<a class="jc-envb ${e}" href="#/j/${esc(j.id)}/${e}/${esc((J && J.tab) || 'asistencia')}">${ic(icono, 's14')}${envTxt(e)}</a>`;
  };
  const mini = okArte(j.arte) ? `<img src="${esc(j.arte)}" style="object-position:${okPos(j.pos)}" alt="">` : j.id === 'r2beat-moderno' ? arte2027() : arteColor(j);
  return `<a class="volver" href="#/juegos">${ic('left', 's14')}Juegos</a>
    <section class="jc-cab" style="--g:${okColor(j.color)}">
      <span class="jc-min" aria-hidden="true">${mini}</span>
      <div class="jc-t"><span class="jc-sup">Contenido del launcher</span>
        <h1>${esc(j.nombre)} <span class="pill-env"><span class="punto"></span>${envTxt(env)}</span></h1>
        <p>${env === 'test' ? 'Servidor de PRUEBA: lo que publique aquí no les llega a los jugadores de PROD.' : 'Lo que ve el jugador en el launcher. Al publicar llega en vivo: no hace falta un launcher nuevo.'}</p></div>
      <nav class="jc-envs" aria-label="Servidor">${envBtn('live', 'radio')}${envBtn('test', 'flask')}</nav>
    </section>`;
}
function pintarJ(foco) {
  const J = S.jc, main = $('#contenido'); if (!J || !main) return;
  const j = juegoCat(J.jid), ts = tabsJc(J);
  const avisos = [];
  if (!J.d.puede_editar && J.d.servidor) avisos.push(`<div class="conclusion mirar jc-aviso">${ic('lock', 's20')}<div>Su cuenta puede mirar este juego, pero no cambiar su contenido.</div></div>`);
  if (!J.d.servidor && J.d.sin_servidor) avisos.push(`<div class="conclusion mirar jc-aviso">${ic('info', 's20')}<div>${esc(J.d.sin_servidor)}${ts.length ? '<small>Por ahora, de este servidor sólo se puede ver el lanzamiento.</small>' : ''}</div></div>`);
  main.innerHTML = cabJuego(j, J.env, J) + avisos.join('') +
    (ts.length ? `<div class="jc-barra"><div class="pest jc-pest" role="tablist" aria-label="Contenido del launcher" id="jcTabs"></div><div class="jc-acc" id="jcAcc"></div></div>
      <div id="jcCuerpo"></div>` : `<section class="caja" style="max-width:560px;margin:8px auto 0">${vacio('Sin contenido dinámico', esc(J.d.sin_servidor || 'Este servidor todavía no tiene contenido dinámico.'), '<a class="btn chico" href="#/juegos">Volver a los juegos</a>')}</section>`) +
    `<p class="jc-fase">${ic('info', 's14')}<span>El tablero del juego (resumen, conectados y gráficos) llega en la próxima fase del Coordinador.</span></p>`;
  if (!ts.length) return;
  const h = `#/j/${J.jid}/${J.env}/${J.tab}`;
  if (S.ruta !== h) { S.ruta = h; try { history.replaceState(null, '', h); } catch (err) { /* nada */ } }
  pintarAccJ();
  pintarCuerpoJ(foco);
}
function pintarAccJ() {
  const J = S.jc, tabs = $('#jcTabs'), acc = $('#jcAcc'); if (!J || !tabs) return;
  const sucias = suciasJc(J);
  tabs.innerHTML = tabsJc(J).map(k => `<button type="button" role="tab" id="jcTab-${k}" aria-controls="jcCuerpo" aria-selected="${J.tab === k}" tabindex="${J.tab === k ? 0 : -1}" data-accion="jc-tab" data-k="${k}">${ic(JC_TABS[k][1], 's14')}${JC_TABS[k][0]}${sucias.includes(k) ? '<span class="lc-pt" title="Sin publicar"></span><span class="sr"> (sin publicar)</span>' : ''}</button>`).join('');
  const alguno = tabsJc(J).some(k => puedeJc(J, k));
  if (!alguno) { acc.innerHTML = `<span class="chip">${ic('eye', 's14')}Sólo lectura</span>`; return; }
  const n = sucias.length, env = envTxt(J.env);
  acc.innerHTML = `<span class="chip ${n ? 'oro' : 'verde'}" role="status">${ic(n ? 'clock' : 'check', 's14')}${n ? `${n} ${n === 1 ? 'parte' : 'partes'} sin publicar` : 'Todo publicado'}</span>
    <button type="button" class="btn fantasma" data-accion="jc-descartar" ${n && !J.publicando ? '' : 'disabled'}>Descartar</button>
    <button type="button" class="btn prim" data-accion="jc-publicar" ${n && !J.publicando ? '' : 'disabled'}>${J.publicando ? '<span class="giro-btn" aria-hidden="true"></span>Publicando…' : `${ic('send', 's16')}Publicar<span class="vc-largo"> en ${env}</span>`}</button>`;
}
function pintarCuerpoJ(foco) {
  const J = S.jc, c = $('#jcCuerpo'); if (!J || !c) return;
  const ed = { asistencia: edAsistencia, ruleta: edRuleta, tira: edTira, lanzamiento: edLanz }[J.tab](J);
  c.innerHTML = `<div class="lc-grid" role="tabpanel" aria-labelledby="jcTab-${J.tab}"><div class="lc-ed">${ed}</div>
    <aside class="lc-previa" aria-label="Vista previa"><div class="lc-previa-cab">${ic('eye', 's14')}Así lo ve el jugador <span class="etq-env ${J.env === 'test' ? 'test' : 'live'}">${envTxt(J.env)}</span></div><div id="jcPrevia">${previaJ(J)}</div></aside></div>`;
  if (foco) { const f = $(foco); if (f) f.focus(); }
  tic();
}
const previaJ = J => ({ asistencia: previaAsis, ruleta: previaRuleta, tira: previaTira, lanzamiento: previaLanz }[J.tab](J));
function pintarPreviaJ() { const J = S.jc, p = $('#jcPrevia'); if (J && p) { p.innerHTML = previaJ(J); tic(); } }
function cambioJ() { pintarAccJ(); pintarPreviaJ(); }

/* ══════════════ ASISTENCIA ══════════════ */
/* «semana_mes 2» -> «semana_mes:2». ⛔ Sólo valores conocidos (va a clases y atributos) */
const claveOrigen = o => { const m = /^semana_mes (\d|ultima)$/.exec(String(o || '')); return m ? 'semana_mes:' + m[1] : ['fecha', 'semana', 'base'].includes(o) ? o : 'base'; };
function alcances(x, L) {
  const pl = DIAS_PL[x.dow], n = Math.floor((x.dia - 1) / 7) + 1;
  const out = [{ k: 'fecha', t: 'Sólo este día', s: `El ${x.dia} de ${MESES_L[Number(x.fecha.slice(5, 7)) - 1]}` }];
  if (x.dia > L - 7) out.push({ k: 'semana_mes:ultima', t: `Los ${pl} de la última semana`, s: 'Los últimos 7 días de cada mes' });
  out.push({ k: `semana_mes:${n}`, t: `Los ${pl} de la ${ORD_SEM[n]} semana`, s: `Días ${7 * n - 6} al ${Math.min(7 * n, 31)} de cada mes` });
  out.push({ k: 'semana', t: `Todos los ${pl}`, s: 'Todo el mes, si no hay una regla más precisa' });
  out.push({ k: 'base', t: 'Todos los días', s: 'Los días que no tienen otra regla' });
  return out;
}
function pagaTxt(k, x) {
  const pl = DIAS_PL[x.dow];
  if (k === 'fecha') return 'una regla sólo para este día';
  if (k === 'semana_mes:ultima') return `la regla de los ${pl} de la última semana`;
  if (k.startsWith('semana_mes:')) return `la regla de los ${pl} de la ${ORD_SEM[Number(k.split(':')[1])] || ''} semana`;
  if (k === 'semana') return `la regla de los ${pl}`;
  return 'la regla de todos los días';
}
function regla(A, k, x) {
  if (k === 'base') return A.base;
  if (k === 'fecha') return A.fechas[x.fecha];
  if (k === 'semana') return A.semana[String(x.dow)];
  return (A.semana_mes[k.split(':')[1]] || {})[String(x.dow)];
}
function fijarRegla(A, k, x, r) {
  if (k === 'base') { if (r) A.base = r; return; }
  let obj, key = String(x.dow);
  if (k === 'fecha') { obj = A.fechas; key = x.fecha; } else if (k === 'semana') obj = A.semana;
  else { const n = k.split(':')[1]; obj = A.semana_mes[n] = A.semana_mes[n] || {}; }
  if (r) obj[key] = r; else delete obj[key];
  Object.keys(A.semana_mes).forEach(n => { if (!Object.keys(A.semana_mes[n]).length) delete A.semana_mes[n]; });
}
function diaSel(J) { return J.mes ? J.mes.dias.find(x => x.fecha === J.dia) || null : null; }
function alcanceSel(J, x) {
  const o = claveOrigen(x.origen), ks = alcances(x, J.mes.dias.length).map(a => a.k);
  return J.alcance && ks.includes(J.alcance) ? J.alcance : ks.includes(o) ? o : 'base';
}
function edAsistencia(J) {
  const A = J.borr.asistencia, ro = !J.d.puede_editar, s = J.d.servidor;
  return `<section class="caja"><div class="caja-cab"><h3>${ic('ticket', 's16')}Asistencia</h3><span class="sub">${cambiadoTxt((s.cambiado || {}).asistencia)}</span></div>
    <div class="caja-cuerpo jc-cfg">
      <label class="lc-check en-linea"><input type="checkbox" data-jc="as-activa" ${A.activa !== false ? 'checked' : ''}${dis(ro)}><span><b>Asistencia activa</b></span></label>
      <label class="lc-mini">Asistencias tardías por mes <input type="number" class="lc-num" min="0" max="31" inputmode="numeric" data-jc="as-tardias" value="${entre(A.tardias_mes, 0, 31)}"${dis(ro)}></label>
      ${A.activa === false ? '<p class="jc-nota">Apagada: los jugadores no pueden marcar asistencia.</p>' : ''}
    </div></section>
    <section class="caja" id="asCal">${calAsis(J)}</section>
    <div id="asErr">${errBox(J.err.asistencia)}</div>
    <section class="caja" id="asDia">${diaAsis(J)}</section>`;
}
function calAsis(J) {
  const M = J.mes;
  if (!M || !M.dias || !M.dias.length) return `<div class="caja-cuerpo tenue" style="padding-top:16px">El servidor no mandó el calendario de este mes.</div>`;
  const pri = M.dias[0].dow || 0;
  const celdas = Array.from({ length: pri }, () => '<span aria-hidden="true"></span>').concat(M.dias.map(x => {
    const o = claveOrigen(x.origen).split(':')[0], p = (x.premios || [])[0];
    return `<button type="button" class="lc-dia o-${o} ${x.fecha === J.dia ? 'sel' : ''} ${x.hoy ? 'hoy' : ''}" data-accion="jc-dia" data-f="${esc(x.fecha)}" aria-pressed="${x.fecha === J.dia}" aria-label="${x.dia}${x.hoy ? ', hoy' : ''}: ${esc((x.premios || []).map(premioTxt).join(' + '))}${x.racha ? ', pide racha' : ''}">
      <span class="n">${x.dia}</span>${icPremio(p, 'chico')}<span class="c">${esc(premioCorto(p))}${x.premios.length > 1 ? `<b>+${x.premios.length - 1}</b>` : ''}</span>${x.racha ? '<span class="lc-racha" aria-hidden="true"></span>' : ''}</button>`;
  }));
  return `<div class="caja-cab"><h3>${ic('target', 's16')}<span>${cap(MESES_L[M.mes - 1])} ${M.anio}</span></h3><span class="sub" id="asEst">toque un día para ver qué paga</span>
      <div class="der"><button type="button" class="btn icono chico" data-accion="jc-mes" data-d="-1" aria-label="Mes anterior">${ic('left', 's14')}</button><button type="button" class="btn icono chico" data-accion="jc-mes" data-d="1" aria-label="Mes siguiente">${ic('right', 's14')}</button></div></div>
    <div class="caja-cuerpo"><div class="lc-cal">${DIAS_C.map(x => `<span class="cab">${x}</span>`).join('')}${celdas.join('')}</div>
      <div class="jc-ley"><span><i class="o-fecha"></i>Sólo ese día</span><span><i class="o-semana_mes"></i>Semana del mes</span><span><i class="o-semana"></i>Día de la semana</span><span><i class="o-base"></i>Todos los días</span><span><i class="racha"></i>Pide racha</span></div></div>`;
}
function pagaHtml(J, x) {
  const k = claveOrigen(x.origen);
  return `<div class="jc-paga-p">${(x.premios || []).map(p => `<span class="jc-prem">${icPremio(p, 'chico')}${esc(premioTxt(p))}</span>`).join('')}</div>
    <p>${x.titulo ? `<b>«${esc(x.titulo)}»</b> · ` : ''}Lo paga ${pagaTxt(k, x)}.${x.racha && x.si_no ? ` Pide racha: si el jugador no marcó todos los días anteriores del mes, cobra ${esc(x.si_no.map(premioTxt).join(' + '))}.` : ''}</p>`;
}
function diaAsis(J) {
  const x = diaSel(J);
  if (!x) return `<div class="caja-cuerpo tenue" style="padding-top:16px">Elija un día del calendario.</div>`;
  const A = J.borr.asistencia, M = J.mes, o = claveOrigen(x.origen), al = alcanceSel(J, x), r = regla(A, al, x), ro = !J.d.puede_editar;
  const ops = alcances(x, M.dias.length).map(a => {
    const tiene = !!regla(A, a.k, x);
    return `<label class="radio ${a.k === al ? 'on' : ''}"><input type="radio" name="asAl" value="${a.k}" data-jc="as-alcance" ${a.k === al ? 'checked' : ''}>
      <span><b>${a.t}${a.k === o ? ' <span class="chip verde jc-chipc">paga este día</span>' : ''}</b><span>${a.s} · ${tiene ? 'tiene regla' : '<i>sin regla propia</i>'}</span></span></label>`;
  }).join('');
  return `<div class="caja-cab"><h3>${ic('gift', 's16')}${cap(DIAS_L[x.dow])} ${x.dia} de ${MESES_L[M.mes - 1]}</h3>${x.hoy ? '<span class="chip cian">hoy</span>' : ''}</div>
    <div class="caja-cuerpo lc-form">
      <div class="jc-paga" id="asPaga">${pagaHtml(J, x)}</div>
      <div><span class="lab" id="lbAl">${ro ? 'Las reglas que tocan este día' : 'Cambiar la regla de'}</span><div class="alcance" role="radiogroup" aria-labelledby="lbAl">${ops}</div></div>
      ${r ? edRegla(J, r, al) : sinRegla(J, al, x, o)}
    </div>`;
}
function edRegla(J, r, al) {
  const ro = !J.d.puede_editar, base = al === 'base', n = r.premios.length;
  return `<div class="jc-regla">
    <span class="lab">Premios <span class="muy-tenue">(${n} de 6)</span></span>
    <div class="jc-premios">${r.premios.map((p, i) => filaPremio(p, i, n, ro)).join('')}</div>
    ${!ro && n < 6 ? `<button type="button" class="btn chico" data-accion="jc-p-agregar">${ic('plus', 's14')}Agregar premio</button>` : ''}
    <label class="lc-campo"><span class="lab">Título del día · opcional</span><input class="lc-in" maxlength="40" data-jc="as-titulo" value="${esc(r.titulo || '')}" placeholder="Por ejemplo: Miércoles de plata"${dis(ro)}></label>
    ${base ? '' : `<label class="lc-check"><input type="checkbox" data-jc="as-racha" ${r.racha ? 'checked' : ''}${dis(ro)}><span><b>Sólo con racha</b><span>La cobra quien marcó todos los días anteriores del mes. Si no, paga la regla siguiente.</span></span></label>`}
    ${base || ro ? '' : `<div><button type="button" class="btn chico peligro" data-accion="jc-regla-quitar">${ic('x', 's14')}Quitar esta regla</button></div>`}
  </div>`;
}
function filaPremio(p, i, n, ro) {
  const item = p.rcoin == null;
  let det;
  if (!item) det = `<label class="jc-unid"><span class="sr">Rcoin del premio ${i + 1}</span>${imgRcoin('chico')}<input type="number" class="lc-in jc-rc" min="1" max="1000000" inputmode="numeric" data-jc="as-p-rcoin" data-i="${i}" value="${Number(p.rcoin) || 0}"${dis(ro)}><span>Rcoin</span></label>`;
  else {
    det = `<button type="button" class="jc-item" data-accion="jc-p-buscar" data-i="${i}" aria-haspopup="true" aria-expanded="false" aria-label="${p.item ? `Cambiar el ítem del premio ${i + 1}: ${esc(nomItem(p.item))}` : `Elegir el ítem del premio ${i + 1}`}"${dis(ro)}>${p.item ? icPremio(p, 'chico') : ''}<span>${p.item ? `${esc(nomItem(p.item))} <small>#${Number(p.item)}</small>` : 'Elegir ítem…'}</span>${ro ? '' : ic('search', 's14')}</button>`;
    /* lo que se gasta va POR CANTIDAD; la ropa, las alas y los sets, POR DÍAS. El servidor lo corrige solo si sabe;
       si el ítem pide días puntuales (7 / 30…), lo dice en el error y aquí se elige «Días». */
    if (p.item) det += `<div class="seg jc-forma" role="group" aria-label="Cómo se da el premio ${i + 1}"><button type="button" data-accion="jc-p-forma" data-i="${i}" data-f="cant" aria-pressed="${p.dias == null}"${dis(ro)}>Cantidad</button><button type="button" data-accion="jc-p-forma" data-i="${i}" data-f="dias" aria-pressed="${p.dias != null}"${dis(ro)}>Días</button></div>` + (p.dias != null
      ? `<label class="jc-unid"><span class="sr">Días que dura el premio ${i + 1}</span><input type="number" class="lc-num" min="0" max="365" inputmode="numeric" data-jc="as-p-dias" data-i="${i}" value="${Number(p.dias) || 0}"${dis(ro)}><span>días</span><small class="muy-tenue">0 = permanente</small></label>`
      : `<label class="jc-unid"><span class="sr">Cantidad del premio ${i + 1}</span><span aria-hidden="true">×</span><input type="number" class="lc-num" min="1" max="999" inputmode="numeric" data-jc="as-p-cant" data-i="${i}" value="${Number(p.cant) || 1}"${dis(ro)}></label>`);
  }
  return `<div class="jc-premio">
    <div class="seg" role="group" aria-label="Tipo del premio ${i + 1}"><button type="button" data-accion="jc-p-tipo" data-i="${i}" data-t="rcoin" aria-pressed="${!item}"${dis(ro)}>Rcoin</button><button type="button" data-accion="jc-p-tipo" data-i="${i}" data-t="item" aria-pressed="${item}"${dis(ro)}>Ítem</button></div>
    <div class="jc-premio-d">${det}</div>
    ${!ro && n > 1 ? `<button type="button" class="btn icono chico fantasma" data-accion="jc-p-quitar" data-i="${i}" aria-label="Quitar el premio ${i + 1}" title="Quitar">${ic('x', 's14')}</button>` : ''}
  </div>`;
}
function sinRegla(J, al, x, o) {
  const ro = !J.d.puede_editar, a = alcances(x, J.mes.dias.length).find(y => y.k === al);
  return `<div class="jc-sin">${ic('info', 's16')}<div><b>«${a ? a.t : ''}» no tiene regla propia.</b><span>Este día lo paga ${pagaTxt(o, x)}.</span>
    ${ro ? '' : `<div class="jc-sin-acc"><button type="button" class="btn chico prim" data-accion="jc-regla-crear">${ic('plus', 's14')}Crear esta regla</button><small>Empieza con los premios que paga hoy; después se cambian.</small></div>`}</div></div>`;
}
/* después de la previa: un ítem que el juego da POR DÍAS (ropa) o POR CANTIDAD lo decide el servidor */
function adoptarForma(A, L) {
  let cambio = false;
  const par = (ra, rl) => {
    if (!ra || !rl) return;
    (ra.premios || []).forEach((p, i) => {
      const q = (rl.premios || [])[i];
      if (!q || p.item == null || Number(p.item) !== Number(q.item)) return;
      if ('dias' in q && !('dias' in p)) { delete p.cant; p.dias = q.dias; cambio = true; } else if ('cant' in q && !('cant' in p)) { delete p.dias; p.cant = q.cant; cambio = true; }
    });
  };
  par(A.base, L.base);
  Object.keys(A.semana).forEach(k => par(A.semana[k], (L.semana || {})[k]));
  Object.keys(A.semana_mes).forEach(n => Object.keys(A.semana_mes[n]).forEach(k => par(A.semana_mes[n][k], ((L.semana_mes || {})[n] || {})[k])));
  Object.keys(A.fechas).forEach(f => par(A.fechas[f], (L.fechas || {})[f]));
  return cambio;
}
let asisReloj = null;
function programarPreviaAsis(ms = 450) {
  clearTimeout(asisReloj);
  const e = $('#asEst'); if (e) e.textContent = 'actualizando…';
  asisReloj = setTimeout(previaAsistencia, ms);
}
async function previaAsistencia() {
  const J = S.jc; if (!J || !J.borr.asistencia) return;
  const n = ++J.seq, mesAntes = J.mesVer;
  const r = await api('contenido/previa', { juego: J.jid, entorno: J.env, clave: 'asistencia', valor: J.borr.asistencia, mes: J.mesVer });
  if (S.jc !== J || n !== J.seq) return;
  let forma = false;
  if (!r.ok) {
    J.err.asistencia = (r.d && (r.d.error || r.d.texto)) || `Error ${r.status}`;
    if (J.mesVer !== (J.mes ? `${J.mes.anio}-${dos(J.mes.mes)}` : null) && J.mes) J.mesVer = `${J.mes.anio}-${dos(J.mes.mes)}`;
  } else {
    J.err.asistencia = null;
    forma = adoptarForma(J.borr.asistencia, r.d.valor || {});
    J.mes = r.d.mes; J.mesVer = `${r.d.mes.anio}-${dos(r.d.mes.mes)}`;
    nombresDe(J, r.d.mes);
    if (!J.mes.dias.some(x => x.fecha === J.dia)) { J.dia = ((J.mes.dias.find(x => x.hoy) || J.mes.dias[0]) || {}).fecha; J.alcance = null; forma = true; }
  }
  if (J.tab !== 'asistencia') return;
  const cal = $('#asCal'); if (cal) cal.innerHTML = calAsis(J);
  const er = $('#asErr'); if (er) er.innerHTML = errBox(J.err.asistencia);
  if (forma || mesAntes !== J.mesVer) repintarDia(J);
  else { const x = diaSel(J), p = $('#asPaga'); if (x && p) p.innerHTML = pagaHtml(J, x); }
  cambioJ();
}
/* repinta la caja del día sin perder el foco del campo donde se estaba escribiendo */
function repintarDia(J) {
  const c = $('#asDia'); if (!c) return;
  const a = document.activeElement, sel = a && c.contains(a) && a.dataset ? (a.dataset.jc ? `[data-jc="${a.dataset.jc}"]${a.dataset.i ? `[data-i="${a.dataset.i}"]` : ''}${a.type === 'radio' ? `[value="${a.value}"]` : ''}` : a.dataset.accion ? `[data-accion="${a.dataset.accion}"]${a.dataset.i ? `[data-i="${a.dataset.i}"]` : ''}${a.dataset.t ? `[data-t="${a.dataset.t}"]` : ''}${a.dataset.f ? `[data-f="${a.dataset.f}"]` : ''}` : null) : null;
  c.innerHTML = diaAsis(J);
  if (sel) { const f = c.querySelector(sel); if (f) f.focus(); }
}
function reglaActual(J) {
  const x = diaSel(J); if (!x) return {};
  const al = alcanceSel(J, x);
  return { x, al, r: regla(J.borr.asistencia, al, x) };
}
function previaAsis(J) {
  const M = J.mes, A = J.borr.asistencia;
  if (!M || !M.dias || !M.dias.length) return '<div class="lp-vacia">Sin calendario.</div>';
  const pri = M.dias[0].dow || 0, arte = ARTE.asis === true;
  const num = n => (arte ? `<span class="lp-num" aria-hidden="true">${String(n).split('').map(c => `<i style="background-position:${-10 * Number(c)}px 0"></i>`).join('')}</span>` : `<span class="lp-num txt">${n}</span>`);
  const celdas = Array.from({ length: pri }, () => '<span></span>').concat(M.dias.map(x => {
    const esp = !!(x.titulo || x.racha), p = (x.premios || [])[0];
    const pasado = !x.hoy && x.fecha < M.hoy, estado = x.hoy ? (esp ? 'amarillo_vivo' : 'naranja_vivo') : pasado ? 'oscuro' : esp ? 'oliva' : 'gris';
    return `<div class="lp-dia t-${estado} ${x.hoy ? 'hoy' : ''} ${x.fecha === J.dia ? 'sel' : ''}"${arte ? ` style="background-image:url('arte/asistencia-ticket_${estado}.png')"` : ''} title="${x.dia}: ${esc((x.premios || []).map(premioTxt).join(' + '))}">
      <div class="lp-cuerpo">${num(x.dia)}${x.racha ? '<span class="lp-fuego" aria-hidden="true"></span>' : ''}</div>
      <div class="lp-talon">${icPremio(p, 'mini')}<span>${esc(premioCorto(p))}</span></div></div>`;
  }));
  const x = diaSel(J);
  return `<div class="lp-asis ${arte ? 'con-arte' : 'sin-arte'} ${A.activa === false ? 'apagada' : ''}">
      <div class="lp-cab"><div><b>ASISTENCIA <span>· ${MESES_L[M.mes - 1]} ${M.anio}</span></b>
        <div class="lp-chips"><span>Tardías <b>${entre(A.tardias_mes, 0, 31)}</b> por mes</span>${A.activa === false ? '<span>Apagada</span>' : ''}</div></div></div>
      <div class="lp-sem">${DIAS_C.map(d => `<span>${d}</span>`).join('')}</div>
      <div class="lp-grilla">${celdas.join('')}</div>
      <div class="lp-pie"><span class="lp-btn">Marcar asistencia tardía</span><span class="lp-btn lleno">Marcar hoy</span></div>
    </div>
    ${x ? `<div class="lp-detalle"><small>DÍA ${x.dia}${x.titulo ? ` · ${esc(x.titulo)}` : ''}${x.racha ? ' · PIDE RACHA' : ''}</small>${(x.premios || []).map(p => `<span class="jc-prem">${icPremio(p, 'chico')}${esc(premioTxt(p))}</span>`).join('')}</div>` : ''}
    <p class="lp-nota">El mes como lo ve un jugador que todavía no marcó ningún día.</p>`;
}

/* ══════════════ RULETA ══════════════ */
const pesoTotal = R => (R.casillas || []).reduce((a, c) => a + (Number(c.prob) || 0), 0) + (Number((R.mayor || {}).prob) || 0);
function edRuleta(J) {
  const R = J.borr.ruleta, ro = !J.d.puede_editar, s = J.d.servidor, tot = pesoTotal(R), rc = R.precio_rcoin > 0;
  let kRopa = 0;
  const filas = (R.casillas || []).map((c, i) => filaCasilla(R, c, i, tot, ro, c.tipo === 'ropa' ? kRopa++ : -1)).join('');
  const m = R.mayor || {};
  return `<section class="caja"><div class="caja-cab"><h3>${ic('refresh', 's16')}Ruleta</h3><span class="sub">${cambiadoTxt((s.cambiado || {}).ruleta)}</span></div>
    <div class="caja-cuerpo lc-form">
      <label class="lc-check en-linea" style="align-self:flex-start"><input type="checkbox" data-jc="ru-activa" ${R.activa !== false ? 'checked' : ''}${dis(ro)}><span><b>Ruleta abierta</b></span></label>
      <div class="lc-fila">
        <label class="lc-campo"><span class="lab">Precio por giro</span><span class="jc-unid">${imgGorila('chico')}<input type="number" class="lc-in" min="1" max="100" inputmode="numeric" data-jc="ru-precio" value="${entre(R.precio, 1, 100)}"${dis(ro)}><span>monedas</span></span></label>
        <label class="lc-campo"><span class="lab">Sin monedas, el giro cuesta</span><span class="jc-unid">${imgRcoin('chico')}<input type="number" class="lc-in" min="0" max="1000000" inputmode="numeric" data-jc="ru-precio_rcoin" value="${entre(R.precio_rcoin, 0, 1000000)}"${dis(ro)}><span>Rcoin</span></span><small class="jc-hint">0 = sin monedas gorila no se gira</small></label>
        <label class="lc-campo"><span class="lab">La ropa dura</span><span class="jc-unid"><input type="number" class="lc-in" min="0" max="365" inputmode="numeric" data-jc="ru-dias_ropa" value="${entre(R.dias_ropa, 0, 365)}"${dis(ro)}><span>días</span></span><small class="jc-hint">0 = permanente</small></label>
      </div>
    </div></section>
    ${statsRuleta(s.ruleta_resumen)}
    <section class="caja"><div class="caja-cab"><h3>${ic('target', 's16')}Casillas <span class="muy-tenue" style="font:500 12.5px var(--sans)">${(R.casillas || []).length} de 16</span></h3>
      <span class="sub">El <b>peso</b> decide cuánto sale cada una: su porcentaje es el peso sobre el total.</span></div>
      <div class="jc-cas" role="list">
        <div class="jc-cas-cab ${rc ? 'con-rc' : ''}" aria-hidden="true"><span>#</span><span>Premio</span><span>Peso</span><span>Sale</span>${rc ? '<span>Modo Rcoin</span>' : ''}<span></span></div>
        ${filas}
        <div class="jc-casilla mayor ${rc ? 'con-rc' : ''}" role="listitem"><span class="jc-cn">★</span>
          <div class="jc-cd"><b>Premio mayor</b><small>${Number(s.ruleta_mayor_total) || 0} premios en la lista (auras, monturas…): se cambian en el juego</small></div>
          <label class="jc-peso"><span class="sr">Peso del premio mayor</span><input type="number" class="lc-in corto" min="0" max="1000" inputmode="numeric" data-jc="ru-mayor-prob" value="${entre(m.prob, 0, 1000)}"${dis(ro)}></label>
          <span class="jc-pct" data-pct="mayor">${pct(m.prob, tot)}</span>${rc ? '<span></span>' : ''}<span class="jc-ord"></span></div>
      </div>
      <div class="pie-tabla">${ro ? '<span></span>' : `<button type="button" class="btn chico" data-accion="jc-ru-agregar" ${(R.casillas || []).length >= 16 ? 'disabled' : ''}>${ic('plus', 's14')}Agregar casilla</button>`}<span id="ruTot">${totRuleta(R)}</span></div>
      ${rc ? `<p class="jc-nota" style="margin:0 16px 14px">${ic('info', 's14')} <b>Modo Rcoin:</b> cuando el jugador gira con Rcoin, la casilla marcada se vuelve una prenda simple más (con su mismo peso).</p>` : ''}
    </section>
    <section class="caja"><div class="caja-cab"><h3>${ic('crown', 's16')}Premio mayor</h3><span class="sub">${Number(m.prob) > 0 ? `sale ${pct(m.prob, tot)} de las veces, sin contar la suerte` : 'apagado: peso 0'}</span></div>
      <div class="caja-cuerpo lc-form">
        <div class="lc-fila">
          <label class="lc-campo"><span class="lab">El premio mayor dura</span><span class="jc-unid"><input type="number" class="lc-in" min="0" max="365" inputmode="numeric" data-jc="ru-mayor-dias" value="${entre(m.dias, 0, 365)}"${dis(ro)}><span>días</span></span><small class="jc-hint">0 = permanente</small></label>
          <label class="lc-campo"><span class="lab">La suerte sube desde</span><span class="jc-unid">${imgRcoin('chico')}<input type="number" class="lc-in" min="0" max="10000000" inputmode="numeric" data-jc="ru-mayor-suerte_desde" value="${entre(m.suerte_desde, 0, 10000000)}"${dis(ro)}><span>Rcoin</span></span></label>
          <label class="lc-campo"><span class="lab">Y sale seguro en</span><span class="jc-unid">${imgRcoin('chico')}<input type="number" class="lc-in" min="0" max="10000000" inputmode="numeric" data-jc="ru-mayor-suerte_tope" value="${entre(m.suerte_tope, 0, 10000000)}"${dis(ro)}><span>Rcoin</span></span><small class="jc-hint">0 = sin suerte creciente</small></label>
        </div>
        <p class="jc-nota">${ic('info', 's14')} La <b>suerte creciente</b> cuenta el Rcoin que cada personaje pagó en la ruleta desde su último premio mayor (las monedas gorila no cuentan). Pasado el primer número, su probabilidad sube hasta que el premio sale seguro.</p>
      </div></section>
    <div id="ruErr">${errBox(J.err.ruleta)}</div>`;
}
function filaCasilla(R, c, i, tot, ro, k) {
  const rc = R.precio_rcoin > 0, n = R.casillas.length;
  const montos = Array.isArray(R.rcoin_sin_ropa) && R.rcoin_sin_ropa.length ? R.rcoin_sin_ropa : [0];
  const tipo = c.tipo === 'rcoin' ? 'rcoin' : c.nivel === 'detallada' ? 'detallada' : 'simple';
  const det = c.tipo === 'rcoin'
    ? `<label class="jc-unid"><span class="sr">Rcoin de la casilla ${i + 1}</span>${imgRcoin('chico')}<input type="number" class="lc-in corto" min="1" max="100000" inputmode="numeric" data-jc="ru-monto" data-i="${i}" value="${entre(c.monto, 0, 100000)}"${dis(ro)}><span>Rcoin</span></label>`
    : `<label class="jc-unid jc-sinropa" title="Lo que paga esta casilla cuando el personaje ya tiene toda la ropa"><span>Sin ropa para darle, paga</span><input type="number" class="lc-in corto" min="1" max="100000" inputmode="numeric" data-jc="ru-sinropa" data-k="${k}" value="${entre(montos[Math.min(k, montos.length - 1)], 0, 100000)}"${dis(ro || k >= 8)} aria-label="Rcoin que paga la casilla ${i + 1} cuando el personaje ya tiene toda la ropa"><span>Rcoin</span></label>`;
  return `<div class="jc-casilla ${c.tipo} ${rc ? 'con-rc' : ''}" role="listitem">
    <span class="jc-cn">${i + 1}</span>
    <div class="jc-cd"><label class="jc-tipo"><span class="sr">Qué da la casilla ${i + 1}</span><select class="sel" data-jc="ru-tipo" data-i="${i}"${dis(ro)}><option value="rcoin" ${tipo === 'rcoin' ? 'selected' : ''}>Rcoin</option><option value="simple" ${tipo === 'simple' ? 'selected' : ''}>Ropa simple</option><option value="detallada" ${tipo === 'detallada' ? 'selected' : ''}>Ropa detallada</option></select></label>${det}</div>
    <label class="jc-peso"><span class="sr">Peso de la casilla ${i + 1}</span><input type="number" class="lc-in corto" min="0" max="1000" inputmode="numeric" data-jc="ru-prob" data-i="${i}" value="${entre(c.prob, 0, 1000)}"${dis(ro)}></label>
    <span class="jc-pct" data-pct="${i}">${pct(c.prob, tot)}</span>
    ${rc ? (c.tipo === 'rcoin' ? `<label class="jc-rcm"><input type="radio" name="ruRc" data-jc="ru-rc" value="${i}" ${R.rcoin_casilla === i ? 'checked' : ''}${dis(ro)}><span class="sr">En el modo Rcoin, la casilla ${i + 1} se vuelve ropa</span><span aria-hidden="true" class="rc-corto">${R.rcoin_casilla === i ? 'ropa' : ''}</span><span aria-hidden="true" class="rc-largo">${R.rcoin_casilla === i ? 'En el modo Rcoin se vuelve ropa' : 'Volverla ropa en el modo Rcoin'}</span></label>` : '<span></span>') : ''}
    <span class="jc-ord">${ro ? '' : `<button type="button" class="btn icono chico fantasma" data-accion="jc-ru-mover" data-i="${i}" data-d="-1" aria-label="Subir la casilla ${i + 1}" ${i ? '' : 'disabled'}>${ic('up', 's14')}</button><button type="button" class="btn icono chico fantasma" data-accion="jc-ru-mover" data-i="${i}" data-d="1" aria-label="Bajar la casilla ${i + 1}" ${i < n - 1 ? '' : 'disabled'}>${ic('down', 's14')}</button><button type="button" class="btn icono chico fantasma" data-accion="jc-ru-quitar" data-i="${i}" aria-label="Quitar la casilla ${i + 1}" ${n > 2 ? '' : 'disabled'}>${ic('x', 's14')}</button>`}</span>
  </div>`;
}
const totRuleta = R => { const t = pesoTotal(R); return t ? `Peso total: <b class="num">${miles(t)}</b>` : '<b style="color:var(--red)">Todas las casillas tienen peso 0</b>'; };
function statsRuleta(rs) {
  rs = rs || {};
  const t = rs.total || {}, d = rs.ultimas_24h || {}, ropa = rs.ropa || {};
  const it = [['Giros', 'giros'], ['Monedas gorila gastadas', 'monedas'], ['Rcoin cobrado por giros', 'rcoin_cobrado'], ['Rcoin entregado en premios', 'rcoin'], ['Prendas entregadas', 'prendas']];
  return `<section class="jc-stats" aria-label="La ruleta en números">${it.map(([n, k]) => `<div><span>${n}</span><b class="num">${miles(t[k])}</b><small>${miles(d[k])} en las últimas 24 h</small></div>`).join('')}</section>
    ${ropa.chico != null ? `<p class="jc-nota" style="margin:-4px 2px 14px">${ic('shirt', 's14')} Ropa en la ruleta: <b>${miles(ropa.chico)}</b> prendas para chico y <b>${miles(ropa.chica)}</b> para chica.</p>` : ''}`;
}
function actualizarPcts(J) {
  const R = J.borr.ruleta, tot = pesoTotal(R);
  $$('[data-pct]').forEach(el => { const k = el.dataset.pct; el.textContent = pct(k === 'mayor' ? (R.mayor || {}).prob : (R.casillas[Number(k)] || {}).prob, tot); });
  const t = $('#ruTot'); if (t) t.innerHTML = totRuleta(R);
}
/* la rueda como la arma el juego (ruleta.rueda): casillas IGUALES; en el modo Rcoin la marcada es una prenda más; el mayor al final */
function ruedaDe(R, modo) {
  const cas = (R.casillas || []).map(c => Object.assign({}, c));
  if (modo === 'rcoin' && R.precio_rcoin > 0 && cas[R.rcoin_casilla] && cas[R.rcoin_casilla].tipo === 'rcoin') cas[R.rcoin_casilla] = { tipo: 'ropa', nivel: 'simple', prob: cas[R.rcoin_casilla].prob, extra: true };
  if (Number((R.mayor || {}).prob) > 0) cas.push({ tipo: 'mayor', prob: Number(R.mayor.prob) });
  return cas;
}
function previaRuleta(J) {
  const R = J.borr.ruleta, modo = R.precio_rcoin > 0 ? J.modoRueda : 'gorila', cas = ruedaDe(R, modo), n = cas.length || 1;
  const W = 300, c0 = W / 2, rr = 136, paso = 360 / n, tot = cas.reduce((a, c) => a + (Number(c.prob) || 0), 0);
  const rad = g => (g - 90) * Math.PI / 180, pt = (g, r) => `${(c0 + r * Math.cos(rad(g))).toFixed(1)} ${(c0 + r * Math.sin(rad(g))).toFixed(1)}`;
  const fs = n <= 8 ? 1 : n <= 12 ? .8 : .66;
  let segs = '', txt = '';
  cas.forEach((c, i) => {
    const a0 = i * paso - paso / 2, a1 = a0 + paso;
    const col = c.tipo === 'mayor' ? '#a8740f' : c.tipo === 'ropa' ? (c.nivel === 'detallada' ? '#7a2d6b' : '#5c2a63') : (i % 2 ? '#2b1f45' : '#3a2a5c');
    segs += `<path d="M${c0} ${c0}L${pt(a0, rr)}A${rr} ${rr} 0 0 1 ${pt(a1, rr)}Z" fill="${col}" stroke="rgba(255,215,106,.55)" stroke-width="2"/>`;
    const g = `transform="rotate(${(i * paso).toFixed(2)} ${c0} ${c0})"`;
    if (c.tipo === 'rcoin') txt += `<g ${g}><text x="${c0}" y="${c0 - rr + 30 * fs}" class="lp-r-monto" style="font-size:${20 * fs}px">${esc(corto(c.monto))}</text><image href="arte/moneda-rcoin.png" x="${c0 - 9 * fs}" y="${c0 - rr + 36 * fs}" width="${18 * fs}" height="${18 * fs}"/></g>`;
    else txt += `<g ${g}><use href="#i-${c.tipo === 'mayor' ? 'crown' : 'shirt'}" x="${c0 - 12 * fs}" y="${c0 - rr + 12 * fs}" width="${24 * fs}" height="${24 * fs}" fill="none" stroke="${c.tipo === 'mayor' ? '#fff1a8' : '#ff9ccb'}" stroke-width="1.6"/><text x="${c0}" y="${c0 - rr + 50 * fs}" class="lp-r-ropa ${c.tipo === 'mayor' ? 'mayor' : ''}" style="font-size:${(c.tipo === 'mayor' ? 9 : 10.5) * fs}px">${c.tipo === 'mayor' ? '★ MAYOR' : c.nivel === 'detallada' ? '★ ROPA' : 'ROPA'}</text></g>`;
  });
  const etiqueta = c => (c.tipo === 'mayor' ? '★ Premio mayor' : c.tipo === 'ropa' ? (c.extra ? 'Ropa simple (modo Rcoin)' : c.nivel === 'detallada' ? 'Ropa detallada' : 'Ropa simple') : `${miles(c.monto)} Rcoin`);
  return `<div class="lp-ruleta ${R.activa === false ? 'cerrada' : ''}">
      <div class="lp-r-titulo">RULETA <span>${modo === 'rcoin' ? `${imgRcoin('mini')} ${miles(R.precio_rcoin)} / giro` : `${imgGorila('mini')} ${entre(R.precio, 1, 100)} / giro`}</span></div>
      ${R.precio_rcoin > 0 ? `<div class="seg lp-r-modo" role="group" aria-label="Ver la rueda"><button type="button" data-accion="jc-ru-modo" data-m="gorila" aria-pressed="${modo === 'gorila'}">Con monedas gorila</button><button type="button" data-accion="jc-ru-modo" data-m="rcoin" aria-pressed="${modo === 'rcoin'}">Con Rcoin</button></div>` : ''}
      <svg viewBox="0 0 ${W} ${W + 8}" class="lp-rueda" role="img" aria-label="La rueda con ${cas.length} casillas"><circle cx="${c0}" cy="${c0}" r="${rr + 5}" fill="#ffd76a"/>${segs}${txt}
        <circle cx="${c0}" cy="${c0}" r="27" fill="#0b0e14" stroke="#e3bb67" stroke-width="3"/><text x="${c0}" y="${c0 + 4}" text-anchor="middle" class="lp-r-girar">GIRAR</text>
        <path d="M${c0 - 10} 2 L${c0 + 10} 2 L${c0} 22 Z" fill="#fff" stroke="#0b0e14" stroke-width="1.5"/></svg>
      ${R.activa === false ? '<div class="lp-r-cerrada">Cerrada por ahora</div>' : ''}
      <ul class="lp-r-ley">${cas.map((c, i) => `<li><i style="background:${c.tipo === 'mayor' ? '#a8740f' : c.tipo === 'ropa' ? (c.nivel === 'detallada' ? '#7a2d6b' : '#5c2a63') : (i % 2 ? '#2b1f45' : '#3a2a5c')}"></i>${etiqueta(c)}<b class="num">${pct(c.prob, tot)}</b></li>`).join('')}</ul>
    </div>
    <p class="lp-nota">Las casillas se ven del mismo tamaño; lo que sale lo decide el peso. Cada casilla de ropa muestra la próxima prenda que ese personaje todavía no tiene.</p>`;
}
let ruReloj = null;
function programarPreviaRuleta() {
  clearTimeout(ruReloj);
  ruReloj = setTimeout(async () => {
    const J = S.jc; if (!J || !J.borr.ruleta) return;
    const local = errRuleta(J.borr.ruleta);
    if (local) { J.err.ruleta = local; } else {
      const n = ++J.seq;
      const r = await api('contenido/previa', { juego: J.jid, entorno: J.env, clave: 'ruleta', valor: J.borr.ruleta });
      if (S.jc !== J || n !== J.seq) return;
      J.err.ruleta = r.ok ? null : (r.d && (r.d.error || r.d.texto)) || `Error ${r.status}`;
    }
    const e = $('#ruErr'); if (e) e.innerHTML = errBox(J.err.ruleta);
  }, 500);
}
function errRuleta(R) {
  const cs = R.casillas || [];
  if (cs.length < 2 || cs.length > 16) return 'La ruleta necesita entre 2 y 16 casillas.';
  if (!cs.reduce((a, c) => a + (Number(c.prob) || 0), 0)) return 'Todas las casillas tienen peso 0: alguna tiene que poder salir.';
  if (R.precio_rcoin > 0 && (cs[R.rcoin_casilla] || {}).tipo !== 'rcoin') return 'En el modo Rcoin, la casilla que se vuelve ropa tiene que ser una de Rcoin.';
  const m = R.mayor || {};
  if (m.suerte_tope && m.suerte_tope <= m.suerte_desde) return 'Premio mayor: «sale seguro en» tiene que ser más que «la suerte sube desde» (o 0).';
  return null;
}

/* ══════════════ TIRA (los avisos del lobby) ══════════════ */
/* como el juego la dibuja: en ASCII (sin tildes ni ñ) — aproximado; lo exacto lo da el servidor (`se_ve`) */
const aAscii = t => String(t || '').replace(/[·•]/g, '-').replace(/[«»“”]/g, '"').replace(/[‘’]/g, "'").replace(/[—–]/g, '-')
  .normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^\x20-\x7e]/g, '').replace(/\s+/g, ' ').trim();
function seVe(J, f) { const o = f.id != null ? J.filas[f.id] : null; return o && o.texto === f.texto ? o.se_ve : aAscii(f.texto); }
const vencida = f => !f.siempre && (!f.vence || f.vence <= Date.now() / 1000);
const enTira = f => f.activo && !vencida(f) && String(f.texto || '').trim();
function edTira(J) {
  const L = J.borr.tira, s = J.d.servidor, ro = !J.d.puede_editar, max = Number(s.tira_texto_max) || 300;
  return `<section class="caja"><div class="caja-cab"><h3>${ic('mega', 's16')}Avisos del lobby</h3><span class="sub">${L.length ? `${L.length} ${L.length === 1 ? 'aviso' : 'avisos'} · la tira que pasa arriba en el lobby del juego` : 'la tira que pasa arriba en el lobby del juego'}</span></div>
      <div class="caja-cuerpo"><p class="jc-cambiado" style="margin:0 0 12px">${(s.cambiado || {}).tira ? cambiadoTxt(s.cambiado.tira) : ''}</p><div id="tiMedidor">${medidorTira(J)}</div></div>
      ${L.length ? `<ol class="jc-tiras">${L.map((f, i) => filaTira(J, f, i, ro, max)).join('')}</ol>` : `<div style="border-top:1px solid var(--line)">${vacio('Sin avisos', 'La tira del lobby no muestra nada. Agregue uno para anunciar un evento o un mantenimiento.')}</div>`}
      ${ro ? '' : `<div class="pie-tabla"><button type="button" class="btn chico" data-accion="jc-ti-agregar" ${L.length >= 50 ? 'disabled' : ''}>${ic('plus', 's14')}Agregar aviso</button><span>Hasta 50 avisos · ${max} letras cada uno</span></div>`}
    </section>`;
}
function estadoTira(f) { return !f.activo ? ['Pausado', ''] : vencida(f) ? ['Venció', 'rojo'] : !String(f.texto || '').trim() ? ['Vacío', 'oro'] : ['Se ve', 'verde']; }
function filaTira(J, f, i, ro, max) {
  const o = f.id != null ? J.filas[f.id] : null, [t, c] = estadoTira(f), sv = seVe(J, f);
  return `<li class="jc-tira ${f.activo ? '' : 'off'} ${vencida(f) && f.activo ? 'venc' : ''}" data-fila="${i}">
    <div class="jc-tira-cab"><span class="chip ${c}" data-ti-est="${i}">${t}</span>${o ? `<span class="muy-tenue jc-quien">${esc(o.quien || '')}${o.creado ? ` · ${haceSeg(o.creado)}` : ''}</span>` : '<span class="chip cian">nuevo</span>'}
      <span class="esp"></span>
      <label class="lc-check en-linea"><input type="checkbox" data-jc="ti-activo" data-i="${i}" ${f.activo ? 'checked' : ''}${dis(ro)}><span><b>Activo</b></span></label>
      ${ro ? '' : `<button type="button" class="btn icono chico fantasma" data-accion="jc-ti-quitar" data-i="${i}" aria-label="Quitar el aviso ${i + 1}" title="Quitar">${ic('x', 's14')}</button>`}</div>
    <label class="lc-campo"><span class="sr">Texto del aviso ${i + 1}</span><textarea class="area jc-ti-txt" rows="2" maxlength="${max}" data-jc="ti-texto" data-i="${i}" placeholder="Por ejemplo: Evento de Halloween esta noche a las 21:00"${dis(ro)}>${esc(f.texto)}</textarea></label>
    <div class="cuenta-txt"><span data-ti-ascii="${i}">${sv && sv !== String(f.texto || '').replace(/\s+/g, ' ').trim() ? `En el juego se ve: «${esc(sv)}»` : ''}</span><span data-ti-cuenta="${i}">${String(f.texto || '').length}/${max}</span></div>
    <div class="jc-vence"><div class="seg" role="group" aria-label="Hasta cuándo se ve el aviso ${i + 1}"><button type="button" data-accion="jc-ti-siempre" data-i="${i}" data-v="1" aria-pressed="${f.siempre}"${dis(ro)}>Siempre</button><button type="button" data-accion="jc-ti-siempre" data-i="${i}" data-v="0" aria-pressed="${!f.siempre}"${dis(ro)}>Hasta una fecha</button></div>
      ${f.siempre ? '' : `<label class="jc-unid"><span>Vence</span><input type="datetime-local" class="lc-in" data-jc="ti-vence" data-i="${i}" value="${f.vence ? isoLocal(new Date(f.vence * 1000)) : ''}"${dis(ro)}><small class="muy-tenue">su hora</small></label>`}</div>
  </li>`;
}
function medidorTira(J) {
  const s = J.d.servidor, totMax = Number(s.tira_total_max) || 1800;
  const vis = J.borr.tira.filter(enTira), n = vis.reduce((a, f) => a + seVe(J, f).length + 9, 0), p = Math.min(100, Math.round(100 * n / totMax));
  return `<div class="jc-medidor ${n > totMax ? 'pasa' : ''}"><div class="medidor"><i style="width:${p}%"></i></div>
    <span><b class="num">${miles(n)}</b> de ${miles(totMax)} letras en la tira (${vis.length} ${vis.length === 1 ? 'aviso se ve' : 'avisos se ven'}, con sus espacios)</span></div>
    ${n > totMax ? `<p class="jc-nota" style="color:var(--gold)">${ic('alert', 's14')} Pasa del máximo de la tira. Conviene acortar o pausar algún aviso.</p>` : ''}`;
}
function previaTira(J) {
  const vis = J.borr.tira.filter(enTira).map(f => seVe(J, f));
  const txt = vis.join(' '.repeat(9)), seg = Math.max(12, Math.round(txt.length * 0.14));
  return `<div class="lp-lobby"><div class="lp-lobby-cab"><span>LOBBY</span><i></i><i></i><i></i></div>
      <div class="tira-previa jc-tira-prev">${vis.length ? `<span style="animation-duration:${seg}s;animation-delay:-${Math.round(seg * .3)}s">${esc(txt)}</span>` : '<em>La tira está vacía.</em>'}</div>
      <div class="lp-lobby-salas" aria-hidden="true"><i></i><i></i><i></i><i></i></div></div>
    <p class="lp-nota">${vis.length ? `Pasan ${vis.length} ${vis.length === 1 ? 'aviso' : 'avisos'}, uno detrás del otro, sin tildes (el juego dibuja sólo ASCII).` : 'Los avisos pausados o vencidos no se ven.'}</p>`;
}
function errTira(J) {
  const max = Number(J.d.servidor.tira_texto_max) || 300;
  if (J.borr.tira.length > 50) return 'Hasta 50 avisos.';
  for (let i = 0; i < J.borr.tira.length; i++) {
    const f = J.borr.tira[i];
    if (!aAscii(f.texto)) return `El aviso ${i + 1} está vacío (o sólo tiene letras que el juego no dibuja).`;
    if (f.texto.length > max) return `El aviso ${i + 1} pasa de ${max} letras.`;
    if (!f.siempre && !f.vence) return `Al aviso ${i + 1} le falta la fecha de vencimiento.`;
    if (vencida(f)) return `El aviso ${i + 1} ya venció: póngale «Siempre», otra fecha, o quítelo.`;
  }
  return null;
}
function refrescarFilaTira(J, i) {
  const f = J.borr.tira[i]; if (!f) return;
  const [t, c] = estadoTira(f), e = $(`[data-ti-est="${i}"]`);
  if (e) { e.className = 'chip ' + c; e.textContent = t; }
  const li = $(`[data-fila="${i}"]`); if (li) { li.classList.toggle('off', !f.activo); li.classList.toggle('venc', vencida(f) && f.activo); }
  const max = Number(J.d.servidor.tira_texto_max) || 300, sv = seVe(J, f);
  const a = $(`[data-ti-ascii="${i}"]`); if (a) a.textContent = sv && sv !== String(f.texto || '').replace(/\s+/g, ' ').trim() ? `En el juego se ve: «${sv}»` : '';
  const k = $(`[data-ti-cuenta="${i}"]`); if (k) k.textContent = `${f.texto.length}/${max}`;
  const m = $('#tiMedidor'); if (m) m.innerHTML = medidorTira(J);
}

/* ══════════════ LANZAMIENTO ══════════════ */
function edLanz(J) {
  const L = J.borr.lanzamiento, d = J.d.lanzamiento, ro = !J.d.es_admin, t = epochPeru(L.desde_peru);
  return `<section class="caja"><div class="caja-cab"><h3>${ic('rocket', 's16')}Lanzamiento</h3><span class="sub">${d.libre ? 'Ya abrió para todos.' : 'Hasta la fecha sólo entran el equipo y los aprobados.'}</span></div>
    <div class="caja-cuerpo lc-form">
      ${ro ? `<p class="jc-nota">${ic('lock', 's14')} La fecha de apertura la cambia un Admin.</p>` : ''}
      <div class="lc-fila">
        <label class="lc-campo"><span class="lab">Abre para todos el (hora de Perú)</span><input type="datetime-local" class="lc-in" data-jc="lz-desde" value="${esc(L.desde_peru)}"${dis(ro)}>
          <small class="jc-hint" id="lzSu">${t ? `En su hora: ${fechaEpoch(t)}` : 'Falta el día y la hora.'}</small></label>
        <div class="lc-campo"><span class="lab" id="lbEtq">Etiqueta</span><div class="seg" role="group" aria-labelledby="lbEtq">${['BETA', 'ALPHA', ''].map(e => `<button type="button" data-accion="jc-lz-etq" data-v="${e}" aria-pressed="${L.etiqueta === e}"${dis(ro)}>${e || 'Ninguna'}</button>`).join('')}</div></div>
      </div>
      <div class="conclusion ok" style="margin:0">${ic('mail', 's20')}<div>Las invitaciones anticipadas se aprueban en La red.<small><a href="#/red">Ir a La red</a></small></div></div>
    </div></section>`;
}
function previaLanz(J) {
  const L = J.borr.lanzamiento, t = epochPeru(L.desde_peru), j = juegoCat(J.jid), abierto = t && t * 1000 <= Date.now();
  return `<div class="lp-lz"><span class="lp-lz-pill">${esc(L.etiqueta)}</span><span class="lp-lz-txt">${esc(j.nombre)} ${abierto ? 'ya abrió' : 'abre el'} ${t ? fechaEpoch(t) : '—'}</span>
      ${t && !abierto ? `<span class="lp-lz-cuenta num" data-cuenta="${t * 1000}">--</span>` : ''}</div>
    <div class="lp-lz-jugar ${abierto ? 'abierto' : ''}">${abierto ? `<span>${ic('play', 's16')} JUGAR</span><small>Abierto para toda cuenta activa.</small>` : `<span>${ic('lock', 's16')} PRÓXIMAMENTE</span><small>El botón de jugar se libera solo en la fecha.</small>`}</div>
    <p class="lp-nota">La fecha se muestra en la hora de quien mira.</p>`;
}

/* ══════════════ publicar y descartar ══════════════ */
function errLocal(J, k) {
  if (k === 'tira') return errTira(J);
  if (k === 'ruleta') return errRuleta(J.borr.ruleta) || J.err.ruleta || null;
  if (k === 'asistencia') return J.err.asistencia || null;
  if (k === 'lanzamiento') return epochPeru(J.borr.lanzamiento.desde_peru) ? null : 'Falta el día y la hora de apertura.';
  return null;
}
function publicarJ() {
  const J = S.jc; if (!J || J.publicando) return;
  const partes = suciasJc(J), env = envTxt(J.env), j = juegoCat(J.jid);
  if (!partes.length) return;
  for (const k of partes) {
    const e = errLocal(J, k);
    if (e) { J.err[k] = e; if (J.tab !== k) { J.tab = k; pintarJ(); } else pintarCuerpoJ(); toast({ t: `${JC_TABS[k][0]}: falta corregir algo`, sub: esc(e), tipo: 'err' }); return; }
  }
  confirmar({ titulo: `¿Publicar en ${env}?`, icono: 'send', peligro: false, ok: `Publicar en ${env}`,
    txt: `Llega en vivo a ${J.env === 'test' ? 'el servidor de prueba' : 'los launchers de los jugadores'} de <b>${esc(j.nombre)}</b>.`,
    extra: `<span class="lab">Se publica</span><ul class="lc-cambios">${partes.map(k => `<li>${ic(JC_TABS[k][1], 's14')}${JC_TABS[k][0]}</li>`).join('')}</ul>`,
    alAceptar: async () => {
      J.publicando = true; pintarAccJ();
      const hechas = [];
      for (const k of partes) {
        const valor = k === 'tira' ? JSON.parse(ser(J.borr.tira)).map(f => (f.siempre ? Object.assign(f, { vence: null }) : f)) : JSON.parse(ser(J.borr[k]));
        const r = await api('contenido', { juego: J.jid, entorno: J.env, clave: k, valor });
        if (S.jc !== J) return;
        if (!r.ok) {
          J.publicando = false; J.err[k] = (r.d && (r.d.error || r.d.texto)) || `Error ${r.status}`;
          J.tab = k; pintarJ();
          toast({ t: `No se pudo publicar: ${JC_TABS[k][0].toLowerCase()}`, sub: errTxt(r) + (hechas.length ? ` · Sí se publicó: ${hechas.join(', ').toLowerCase()}.` : ''), tipo: 'err', ms: 9000 });
          return;
        }
        refrescarClave(J, k, r.d);
        hechas.push(JC_TABS[k][0]);
      }
      J.publicando = false;
      pintarJ();
      toast({ t: `Publicado en ${env} · ${esc(j.nombre)}`, sub: `${esc(hechas.join(', '))}. Quedó en la auditoría.`, tipo: J.env === 'test' ? 'test' : 'ok' });
    } });
}
function refrescarClave(J, k, d) {
  J.err[k] = null;
  if (k === 'lanzamiento') {
    J.d.lanzamiento = d.lanzamiento || J.d.lanzamiento;
    J.borr.lanzamiento = { desde_peru: J.d.lanzamiento.desde_peru, etiqueta: J.d.lanzamiento.etiqueta || '' };
  } else {
    const s = J.d.servidor;
    ['cambiado', 'ruleta_resumen', 'ruleta_mayor_total', 'tira_texto_max', 'tira_total_max'].forEach(x => { if (d[x] !== undefined) s[x] = d[x]; });
    if (k === 'asistencia') { s.asistencia = d.asistencia; s.asistencia_mes = d.asistencia_mes; ponerAsis(J, d.asistencia, d.asistencia_mes); J.alcance = null; }
    if (k === 'ruleta') { s.ruleta = d.ruleta; J.borr.ruleta = clon(d.ruleta); }
    if (k === 'tira') { s.tira = d.tira; ponerTira(J, d.tira); }
  }
  J.orig[k] = ser(J.borr[k]);
}
function descartarJ() {
  const J = S.jc; if (!J) return;
  confirmar({ titulo: '¿Descartar los cambios?', icono: 'refresh', ok: 'Descartar', txt: 'Todo vuelve a lo que está publicado ahora. Lo que cambió aquí se pierde.',
    alAceptar: () => {
      const s = J.d.servidor;
      suciasJc(J).forEach(k => {
        J.err[k] = null;
        if (k === 'asistencia') { ponerAsis(J, s.asistencia, s.asistencia_mes); J.alcance = null; } else if (k === 'tira') ponerTira(J, s.tira);
        else J.borr[k] = JSON.parse(J.orig[k]);
      });
      if (s && !suciasJc(J).includes('asistencia') && J.mesVer !== `${s.asistencia_mes.anio}-${dos(s.asistencia_mes.mes)}`) ponerAsis(J, J.borr.asistencia, s.asistencia_mes);
      pintarJ();
      toast({ t: 'Cambios descartados', tipo: 'info' });
    } });
}

/* ══════════════ los clics y los cambios del editor ══════════════ */
function accionJc(a) {
  const J = S.jc; if (!J) return;
  const i = Number(a.dataset.i), k = a.dataset.accion;
  if (k === 'jc-tab') { if (J.tab !== a.dataset.k) { J.tab = a.dataset.k; pintarJ(`#jcTab-${J.tab}`); } return; }
  if (k === 'jc-publicar') return publicarJ();
  if (k === 'jc-descartar') return descartarJ();
  if (k === 'jc-dia') { J.dia = a.dataset.f; J.alcance = null; $$('.lc-dia').forEach(b => { const on = b.dataset.f === J.dia; b.classList.toggle('sel', on); b.setAttribute('aria-pressed', on); }); repintarDia(J); pintarPreviaJ(); return; }
  if (k === 'jc-mes') { const [y, m] = J.mesVer.split('-').map(Number), d = new Date(y, m - 1 + Number(a.dataset.d), 1); J.mesVer = `${d.getFullYear()}-${dos(d.getMonth() + 1)}`; programarPreviaAsis(0); return; }
  if (k === 'jc-ru-modo') { J.modoRueda = a.dataset.m; pintarPreviaJ(); return; }
  if (!puedeJc(J, J.tab)) return;
  const A = J.borr.asistencia, R = J.borr.ruleta, T = J.borr.tira;
  switch (k) {
    case 'jc-p-tipo': { const { r } = reglaActual(J); if (!r) return; r.premios[i] = a.dataset.t === 'rcoin' ? { rcoin: 1000 } : { item: 0, cant: 1 }; repintarDia(J); if (a.dataset.t === 'item') abrirBuscarItem($(`[data-accion="jc-p-buscar"][data-i="${i}"]`), i); else programarPreviaAsis(); break; }
    case 'jc-p-agregar': { const { r } = reglaActual(J); if (!r || r.premios.length >= 6) return; r.premios.push({ rcoin: 1000 }); repintarDia(J); const f = $(`[data-jc="as-p-rcoin"][data-i="${r.premios.length - 1}"]`); if (f) f.focus(); programarPreviaAsis(); break; }
    case 'jc-p-quitar': { const { r } = reglaActual(J); if (!r || r.premios.length < 2) return; r.premios.splice(i, 1); repintarDia(J); programarPreviaAsis(); break; }
    case 'jc-p-buscar': abrirBuscarItem(a, i); return;
    case 'jc-p-forma': { const { r } = reglaActual(J); const p = r && r.premios[i]; if (!p || p.item == null) return;
      if (a.dataset.f === 'dias') { if (p.dias == null) { delete p.cant; p.dias = 30; } } else if (p.cant == null) { delete p.dias; p.cant = 1; }
      repintarDia(J); programarPreviaAsis(0); break; }
    case 'jc-regla-crear': { const { x, al } = reglaActual(J); if (!x) return; fijarRegla(A, al, x, { premios: (x.premios || []).map(p => { const q = Object.assign({}, p); delete q.nombre; return q; }) }); repintarDia(J); programarPreviaAsis(0); break; }
    case 'jc-regla-quitar': { const { x, al } = reglaActual(J); if (!x || al === 'base') return; fijarRegla(A, al, x, null); J.alcance = null; repintarDia(J); programarPreviaAsis(0); break; }
    case 'jc-ru-agregar': if (R.casillas.length < 16) { R.casillas.push({ tipo: 'rcoin', monto: 100, prob: 0 }); pintarCuerpoJ(`[data-jc="ru-prob"][data-i="${R.casillas.length - 1}"]`); programarPreviaRuleta(); } break;
    case 'jc-ru-quitar': if (R.casillas.length > 2) {
      R.casillas.splice(i, 1);
      if (R.rcoin_casilla === i) { const p = R.casillas.findIndex(c => c.tipo === 'rcoin'); R.rcoin_casilla = p < 0 ? 0 : p; } else if (R.rcoin_casilla > i) R.rcoin_casilla--;
      pintarCuerpoJ(); programarPreviaRuleta();
    } break;
    case 'jc-ru-mover': { const d = i + Number(a.dataset.d); if (d < 0 || d >= R.casillas.length) return; [R.casillas[i], R.casillas[d]] = [R.casillas[d], R.casillas[i]];
      if (R.rcoin_casilla === i) R.rcoin_casilla = d; else if (R.rcoin_casilla === d) R.rcoin_casilla = i;
      pintarCuerpoJ(`[data-accion="jc-ru-mover"][data-i="${d}"][data-d="${a.dataset.d}"]`); programarPreviaRuleta(); break; }
    case 'jc-ti-agregar': if (T.length < 50) { T.push({ id: null, texto: '', siempre: true, vence: null, activo: true, _k: 'n' + Date.now() }); pintarCuerpoJ(`[data-jc="ti-texto"][data-i="${T.length - 1}"]`); } break;
    case 'jc-ti-quitar': T.splice(i, 1); pintarCuerpoJ(); break;
    case 'jc-ti-siempre': { const f = T[i]; if (!f) return; f.siempre = a.dataset.v === '1'; if (f.siempre) f.vence = null; else if (!f.vence) f.vence = Math.floor(Date.now() / 1000 / 3600 + 24 * 7) * 3600;
      pintarCuerpoJ(`[data-accion="jc-ti-siempre"][data-i="${i}"][data-v="${a.dataset.v}"]`); break; }
    case 'jc-lz-etq': J.borr.lanzamiento.etiqueta = a.dataset.v; $$('[data-accion="jc-lz-etq"]').forEach(b => b.setAttribute('aria-pressed', b === a)); break;
    default: return;
  }
  cambioJ();
}
function cambioJc(el, final) {
  const J = S.jc; if (!J) return;
  const k = el.dataset.jc, i = Number(el.dataset.i), v = el.type === 'checkbox' ? el.checked : el.value;
  if (k === 'as-alcance') { J.alcance = v; repintarDia(J); return; }
  if (!puedeJc(J, J.tab)) return;
  const A = J.borr.asistencia, R = J.borr.ruleta, T = J.borr.tira;
  const num = (a, b) => { if (v === '' && !final) return null; const n = entre(v, a, b); if (final && String(n) !== String(el.value)) el.value = n; return n; };
  switch (k) {
    case 'as-activa': A.activa = v; pintarCuerpoJ('[data-jc="as-activa"]'); break;
    case 'as-tardias': { const n = num(0, 31); if (n === null) return; A.tardias_mes = n; break; }
    case 'as-titulo': { const { r } = reglaActual(J); if (!r) return; if (String(v).trim()) r.titulo = v; else delete r.titulo; programarPreviaAsis(); break; }
    case 'as-racha': { const { r } = reglaActual(J); if (!r) return; if (v) r.racha = true; else delete r.racha; programarPreviaAsis(); break; }
    case 'as-p-rcoin': case 'as-p-cant': case 'as-p-dias': {
      const { r } = reglaActual(J); if (!r || !r.premios[i]) return;
      const campo = k.slice(5), n = num(campo === 'rcoin' ? 1 : campo === 'cant' ? 1 : 0, campo === 'rcoin' ? 1000000 : campo === 'cant' ? 999 : 365);
      if (n === null) return; r.premios[i][campo] = n; programarPreviaAsis(); break; }
    case 'ru-activa': R.activa = v; pintarCuerpoJ('[data-jc="ru-activa"]'); programarPreviaRuleta(); break;
    case 'ru-precio': { const n = num(1, 100); if (n === null) return; R.precio = n; programarPreviaRuleta(); break; }
    case 'ru-precio_rcoin': { const n = num(0, 1000000); if (n === null) return; const antes = R.precio_rcoin > 0; R.precio_rcoin = n;
      if (n > 0 && (R.casillas[R.rcoin_casilla] || {}).tipo !== 'rcoin') { const p = R.casillas.findIndex(c => c.tipo === 'rcoin'); if (p >= 0) R.rcoin_casilla = p; }
      if (antes !== n > 0) pintarCuerpoJ('[data-jc="ru-precio_rcoin"]'); programarPreviaRuleta(); break; }
    case 'ru-dias_ropa': { const n = num(0, 365); if (n === null) return; R.dias_ropa = n; programarPreviaRuleta(); break; }
    case 'ru-monto': { const n = num(1, 100000); if (n === null) return; R.casillas[i].monto = n; programarPreviaRuleta(); break; }
    case 'ru-tipo': { const c = R.casillas[i]; if (!c) return;
      R.casillas[i] = v === 'rcoin' ? { tipo: 'rcoin', monto: c.tipo === 'rcoin' ? c.monto : 100, prob: c.prob } : { tipo: 'ropa', nivel: v === 'detallada' ? 'detallada' : 'simple', prob: c.prob };
      if (R.precio_rcoin > 0 && (R.casillas[R.rcoin_casilla] || {}).tipo !== 'rcoin') { const q = R.casillas.findIndex(x => x.tipo === 'rcoin'); if (q >= 0) R.rcoin_casilla = q; }
      pintarCuerpoJ(`[data-jc="ru-tipo"][data-i="${i}"]`); programarPreviaRuleta(); break; }
    case 'ru-prob': { const n = num(0, 1000); if (n === null) return; R.casillas[i].prob = n; actualizarPcts(J); programarPreviaRuleta(); break; }
    case 'ru-mayor-prob': case 'ru-mayor-dias': case 'ru-mayor-suerte_desde': case 'ru-mayor-suerte_tope': {
      const campo = k.slice(9), n = num(0, campo === 'prob' ? 1000 : campo === 'dias' ? 365 : 10000000); if (n === null) return;
      R.mayor = R.mayor || {}; R.mayor[campo] = n; if (campo === 'prob') actualizarPcts(J); programarPreviaRuleta(); break; }
    case 'ru-sinropa': { const n = num(1, 100000), kk = Number(el.dataset.k); if (n === null || kk >= 8) return;
      const m = Array.isArray(R.rcoin_sin_ropa) && R.rcoin_sin_ropa.length ? R.rcoin_sin_ropa : [n];
      while (m.length <= kk) m.push(m[m.length - 1]);
      m[kk] = n; R.rcoin_sin_ropa = m; programarPreviaRuleta(); break; }
    case 'ru-rc': R.rcoin_casilla = Number(v); pintarCuerpoJ(`[data-jc="ru-rc"][value="${v}"]`); programarPreviaRuleta(); break;
    case 'ti-texto': T[i].texto = v; refrescarFilaTira(J, i); break;
    case 'ti-activo': T[i].activo = v; refrescarFilaTira(J, i); break;
    case 'ti-vence': { const t = v ? Math.floor(new Date(v).getTime() / 1000) : null; T[i].vence = Number.isFinite(t) ? t : null; refrescarFilaTira(J, i); break; }
    case 'lz-desde': { J.borr.lanzamiento.desde_peru = v; const t = epochPeru(v), s = $('#lzSu'); if (s) s.textContent = t ? `En su hora: ${fechaEpoch(t)}` : 'Falta el día y la hora.'; break; }
    default: return;
  }
  cambioJ();
}
/* buscar un ítem para un premio (por número o por nombre, en el catálogo del juego) */
let busqReloj = null;
function abrirBuscarItem(ancla, i) {
  if (!ancla) return;
  abrirPop(ancla, `<div class="jc-buscar"><label class="campo">${ic('search', 's16')}<span class="sr">Buscar ítem</span><input id="jcBusq" placeholder="Número o nombre del ítem" autocomplete="off" spellcheck="false"></label>
    <div id="jcBusRes" class="jc-bus-res" aria-live="polite"><p>Escriba el número o parte del nombre.</p></div></div>`, 320);
  pop._i = i;
  pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', 'Buscar ítem');
  const inp = $('#jcBusq'); if (inp) inp.focus();
}
async function buscarItem(q) {
  const J = S.jc, res = $('#jcBusRes'); if (!J || !res) return;
  q = q.trim();
  if (!q) { res.innerHTML = '<p>Escriba el número o parte del nombre.</p>'; return; }
  res.innerHTML = '<p>Buscando…</p>';
  const r = await api(`contenido/items?juego=${encodeURIComponent(J.jid)}&entorno=${J.env}&q=${encodeURIComponent(q)}`);
  if (!$('#jcBusRes') || $('#jcBusq').value.trim() !== q) return;
  if (!r.ok) { res.innerHTML = `<p>${errTxt(r)}</p>`; return; }
  const its = r.d.items || [];
  its.forEach(x => { J.nombres[x.item] = x.nombre; });
  res.innerHTML = its.length ? its.map(x => `<button type="button" data-accion="jc-item-elegir" data-item="${Number(x.item)}"><span class="ip svg chico" style="--c:${hashStr(String(x.item)) % 2 ? '243,38,134' : '179,139,255'}">${ic('gift')}</span><span>${esc(x.nombre)}</span><small>#${Number(x.item)}</small></button>`).join('')
    : `<p>Ningún ítem coincide con «${esc(q)}».</p>`;
}
function elegirItem(id) {
  const J = S.jc, i = pop ? pop._i : null; cerrarPop();
  const { r } = reglaActual(J); if (!r || i == null || !r.premios[i]) return;
  const p = r.premios[i], antes = p.dias != null ? { dias: p.dias } : { cant: p.cant || 1 };
  r.premios[i] = Object.assign({ item: Number(id) }, antes);
  repintarDia(J);
  const b = $(`[data-accion="jc-p-buscar"][data-i="${i}"]`); if (b) b.focus();
  programarPreviaAsis(0);
  cambioJ();
}

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   ★ 20-nov · NOVEDADES (#/novedades): el acordeón de noticias de TODOS los launchers. Una lista para toda la red.
   Las GENERALES se abren hacia abajo; las de cada juego (parches, ropa…), hacia la izquierda. Cada uno edita sólo
   las de sus juegos (`editable`); al publicar se mandan SÓLO ésas: el servidor conserva las demás.
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
const ETQ_NOV = { noticia: 'Noticia', parche: 'Parche', ropa: 'Ropa', evento: 'Evento', mantenimiento: 'Mantenimiento', fuera_de_servicio: 'Fuera de servicio', launcher: 'Launcher' };
const etqNov = e => ETQ_NOV[e] || esc(e);
const fechaNov = f => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(f || ''); return m ? `${Number(m[3])} ${MESES[Number(m[2]) - 1]} ${m[1]}` : ''; };
const ordenNov = l => l.slice().sort((a, b) => (Number(!!b.fijada) - Number(!!a.fijada)) || String(b.fecha || '').localeCompare(String(a.fecha || '')));
const serNov = l => ser(l.filter(n => n.editable).map(n => Object.assign({}, n, { editable: undefined })));
const novSucio = () => !!(S.nov && S.nov.lista && serNov(S.nov.lista) !== S.nov.orig);
const httpsOk = u => /^https:\/\/[^\s"'<>]{4,400}$/.test(u || '');
function nuevoNov(d, juegoSel) {
  const lista = (d.noticias || []).map((n, i) => Object.assign({}, n, { juego: n.juego || 'r2beat', activo: n.activo !== false, _k: 'n' + i }));
  const js = (d.juegos || []).filter(j => j.id !== 'general');
  const juego = js.some(j => j.id === juegoSel) ? juegoSel : ((js.find(j => j.editable) || js[0]) || {}).id || null;
  return { d, lista, orig: serNov(lista), juego, publicando: false };
}
async function vistaNovedades() {
  document.body.classList.remove('test', 'menu-abierto');
  document.title = 'Novedades · Coordinador Eñeños';
  raiz.innerHTML = barraHub('novedades') + `<main class="hub nov" id="contenido"><div class="caja jc-carga" aria-live="polite"><span class="esq" style="height:14px;width:40%"></span><span class="esq" style="height:180px"></span><span class="tenue">Cargando las novedades…</span></div></main>`;
  const r = await api('novedades');
  if (S.ruta !== '#/novedades') return;
  if (!r.ok) { if (r.status !== 401) $('#contenido').innerHTML = `<section class="caja" style="max-width:560px;margin:24px auto">${vacio('No se pudieron leer las novedades', errTxt(r))}</section>`; return; }
  S.nov = nuevoNov(r.d);
  pintarNov();
}
const juegoNov = id => (S.nov.d.juegos || []).find(j => j.id === id) || { id, nombre: id, editable: false, color: '81,216,229' };
function portadaNov(id, c = '') {
  const jn = juegoNov(id), cat = jn.juego ? juegoCat(jn.juego) : null;
  if (cat && okArte(cat.arte)) return `<img class="${c}" src="${esc(cat.arte)}" style="object-position:${okPos(cat.pos)}" alt="">`;
  return `<span class="nov-color ${c}" style="--g:${okColor(jn.color)}">${ic(id === 'general' ? 'mega' : 'sparkle', 's20')}</span>`;
}
function pintarNov() {
  const N = S.nov, d = N.d, main = $('#contenido'); if (!N || !main) return;
  const gen = juegoNov('general'), js = (d.juegos || []).filter(j => j.id !== 'general'), edita = (d.juegos || []).some(j => j.editable);
  const total = N.lista.length, max = Number(d.noticias_max) || 60, lleno = total >= max;
  const generales = ordenNov(N.lista.filter(n => n.juego === 'general'));
  const sel = juegoNov(N.juego), deJ = ordenNov(N.lista.filter(n => n.juego === N.juego));
  const nuevaBtn = (jid, txt, cls = 'nov-agregar') => juegoNov(jid).editable ? `<button type="button" class="${cls}" data-accion="nov-nueva" data-juego="${esc(jid)}" ${lleno ? `disabled title="Ya hay ${max} novedades: quite alguna"` : ''}>${ic('plus', 's14')}${txt}</button>` : '';
  main.innerHTML = `<section class="saludo nov-cab"><div><span class="rayas" aria-hidden="true"><i></i><i></i><i></i></span><h1>Novedades del launcher</h1>
      <p>Las noticias de <b>todos</b> los launchers de Eñeños. Lo que publique aquí llega en vivo, sin launcher nuevo.</p>
      <p class="jc-cambiado">${d.sin_servidor ? '' : `${cambiadoTxt(d.cambiado)} · ${total} de ${max} novedades`}</p></div>
      <div class="der lc-acc" id="novAcc"></div></section>
    ${d.sin_servidor ? `<section class="caja">${vacio('Las novedades no están disponibles', esc(d.sin_servidor))}</section>` : `
    ${edita ? '' : `<div class="conclusion mirar jc-aviso">${ic('lock', 's20')}<div>Su cuenta puede mirar las novedades, pero no cambiarlas.<small>Un moderador edita las de sus juegos; las generales, un Admin.</small></div></div>`}
    <div class="nov-grid">
      <section class="caja nov-col" aria-labelledby="tGen">
        <div class="caja-cab"><h3 id="tGen">${ic('down', 's16')}Noticias generales</h3></div>
        <p class="nov-sub">En el launcher se abren <b>hacia abajo</b>. Son para avisos de servicio: mantenimiento, fuera de servicio y el launcher.</p>
        <div class="nov-maqueta abajo"><div class="nov-acord" aria-hidden="true"><img src="arte/noticias-npc.png" alt="" data-fallo="npc"><b>Noticias</b>${generales.some(n => n.activo) ? '<span class="nov-nuevo"></span>' : ''}${ic('down', 's16')}</div>
          <div class="nov-lista">${generales.length ? generales.map(n => itemNov(n)).join('') : '<p class="tenue nov-nada">Sin noticias generales.</p>'}</div>
          ${gen.editable ? nuevaBtn('general', 'Nueva noticia general') : `<p class="tenue nov-lock">${ic('lock', 's14')} Las noticias generales las cambia un Admin.</p>`}</div>
      </section>
      <section class="caja nov-col" aria-labelledby="tPar">
        <div class="caja-cab"><h3 id="tPar">${ic('left', 's16')}Cada juego</h3></div>
        <p class="nov-sub">En el launcher, el acordeón de cada juego se abre <b>hacia la izquierda</b>: parches, ropa, eventos de ese juego.</p>
        <div class="nov-maqueta izq">
          <div class="nov-juegos" role="tablist" aria-label="Juego">${js.map(j => `<button type="button" role="tab" class="nov-jtab" style="--g:${okColor(j.color)}" data-accion="nov-juego" data-j="${esc(j.id)}" aria-selected="${j.id === N.juego}">${portadaNov(j.id, 'nov-jimg')}<span>${esc(j.nombre)}</span><span class="n">${N.lista.filter(n => n.juego === j.id).length}</span>${j.editable ? '' : ic('lock', 's14 tenue')}</button>`).join('') || '<p class="tenue">Ningún juego suyo sale en las noticias.</p>'}</div>
          ${N.juego ? `<div class="nov-cajitas">${deJ.map(n => cajitaNov(n)).join('')}${nuevaBtn(N.juego, `Nueva de ${esc(sel.nombre)}`, 'nov-cajita libre')}</div>
          ${deJ.length || sel.editable ? '' : '<p class="tenue nov-nada">Todavía nada para este juego.</p>'}
          ${sel.editable ? '' : `<p class="tenue nov-lock">${ic('lock', 's14')} Las de ${esc(sel.nombre)} las cambia un Admin o quien tiene ese juego asignado.</p>`}` : ''}
          <p class="tenue nov-orden">${ic('info', 's14')} Aquí se ordenan como en el panel: las fijadas primero, después las más nuevas.</p>
        </div>
      </section>
    </div>`}`;
  pintarAccNov();
}
function rapNov(n) {
  if (!n.editable) return `<span class="nov-lock-ic" title="Sólo lectura">${ic('lock', 's14')}</span>`;
  return `<span class="nov-rap"><button type="button" class="btn icono chico fantasma ${n.fijada ? 'on' : ''}" data-accion="nov-fijar" data-k="${n._k}" aria-pressed="${!!n.fijada}" aria-label="${n.fijada ? 'Desfijar' : 'Fijar'} «${esc(n.titulo)}»" title="${n.fijada ? 'Fijada: toque para desfijar' : 'Fijar arriba'}">${ic('pin', 's14')}</button><button type="button" class="btn icono chico fantasma" data-accion="nov-ver" data-k="${n._k}" aria-pressed="${!n.activo}" aria-label="${n.activo ? 'Ocultar' : 'Mostrar'} «${esc(n.titulo)}»" title="${n.activo ? 'Visible: toque para ocultar' : 'Oculta: toque para mostrar'}">${ic(n.activo ? 'eye' : 'eyeoff', 's14')}</button></span>`;
}
const metaNov = n => `<span class="nov-meta"><span class="chip mayus">${etqNov(n.etiqueta)}</span>${n.fijada ? `<span class="nov-pin" title="Fijada">${ic('pin', 's14')}</span>` : ''}${n.fecha ? `<span class="muy-tenue">${fechaNov(n.fecha)}</span>` : ''}${n.activo ? '' : '<span class="chip">Oculta</span>'}</span>`;
function itemNov(n) {
  return `<div class="nov-item ${n.activo ? '' : 'oculta'} ${n.editable ? '' : 'bloq'}"><button type="button" class="nov-abrir" data-accion="nov-abrir" data-k="${n._k}" aria-label="${n.editable ? 'Editar' : 'Ver'} «${esc(n.titulo)}»">
      ${portadaNov(n.juego, 'nov-ic')}<span class="t">${metaNov(n)}<b>${esc(n.titulo)}</b></span></button>${rapNov(n)}</div>`;
}
function cajitaNov(n) {
  return `<div class="nov-cajita ${n.activo ? '' : 'oculta'} ${n.editable ? '' : 'bloq'}"><button type="button" class="nov-abrir" data-accion="nov-abrir" data-k="${n._k}" aria-label="${n.editable ? 'Editar' : 'Ver'} «${esc(n.titulo)}»">
      <span class="nov-portada">${portadaNov(n.juego)}</span>${metaNov(n)}<b>${esc(n.titulo)}</b></button>${rapNov(n)}</div>`;
}
function pintarAccNov() {
  const N = S.nov, acc = $('#novAcc'); if (!N || !acc) return;
  const pt = $('.pill-nov'); if (pt) { const p = $('.pt', pt), s = novSucio(); if (s && !p) pt.insertAdjacentHTML('beforeend', '<span class="pt" title="Hay cambios sin publicar"></span>'); if (!s && p) p.remove(); }
  if (N.d.sin_servidor || !(N.d.juegos || []).some(j => j.editable)) { acc.innerHTML = ''; return; }
  const n = novSucio();
  acc.innerHTML = `<span class="chip ${n ? 'oro' : 'verde'}" role="status">${ic(n ? 'clock' : 'check', 's14')}${n ? 'Cambios sin publicar' : 'Todo publicado'}</span>
    <button type="button" class="btn fantasma" data-accion="nov-descartar" ${n && !N.publicando ? '' : 'disabled'}>Descartar</button>
    <button type="button" class="btn prim" data-accion="nov-publicar" ${n && !N.publicando ? '' : 'disabled'}>${N.publicando ? '<span class="giro-btn" aria-hidden="true"></span>Publicando…' : `${ic('send', 's16')}Publicar`}</button>`;
}
/* el texto del popup: se ESCAPA todo y recién después se arma el formato simple (# título · ## subtítulo · - lista · **negrita**) */
function formatoNov(t) {
  const out = []; let ul = false, par = [];
  const cerrarPar = () => { if (par.length) { out.push(`<p>${par.join('<br>')}</p>`); par = []; } };
  const cerrarUl = () => { if (ul) { out.push('</ul>'); ul = false; } };
  const linea = s => esc(s).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  for (const crudo of String(t || '').split(/\r?\n/)) {
    const r = crudo.trimEnd(); let m;
    if (!r.trim()) { cerrarPar(); cerrarUl(); continue; }
    if ((m = r.match(/^##\s+(.*)/))) { cerrarPar(); cerrarUl(); out.push(`<h4>${linea(m[1])}</h4>`); } else if ((m = r.match(/^#\s+(.*)/))) { cerrarPar(); cerrarUl(); out.push(`<h3>${linea(m[1])}</h3>`); } else if ((m = r.match(/^\s*[-•]\s+(.*)/))) { cerrarPar(); if (!ul) { out.push('<ul>'); ul = true; } out.push(`<li>${linea(m[1])}</li>`); } else { cerrarUl(); par.push(linea(r)); }
  }
  cerrarPar(); cerrarUl();
  return out.join('');
}
function opcionesEtq(n) {
  const d = S.nov.d, gen = n.juego === 'general';
  const lista = gen ? (d.etiquetas_general || []) : (d.etiquetas || Object.keys(ETQ_NOV));
  return lista.map(e => `<option value="${esc(e)}" ${n.etiqueta === e ? 'selected' : ''}>${etqNov(e)}</option>`).join('');
}
function editarNov(k, juegoNuevo) {
  const N = S.nov, d = N.d, orig = k ? N.lista.find(x => x._k === k) : null;
  if (k && !orig) return;
  const etqs = juegoNuevo === 'general' ? (d.etiquetas_general || []) : (d.etiquetas || []);
  const n = orig ? Object.assign({}, orig) : { juego: juegoNuevo, titulo: '', texto: '', imagen: '', etiqueta: juegoNuevo === 'general' ? (etqs[0] || 'mantenimiento') : (etqs.includes('parche') ? 'parche' : etqs[0] || 'noticia'),
    fecha: hoyIso(), fijada: false, activo: true, editable: true, _k: 'x' + Date.now().toString(36) };
  const ro = !n.editable, max = Number(d.texto_max) || 4000;
  const juegosEd = (d.juegos || []).filter(j => j.editable || j.id === n.juego);
  const pn = abrirCapa(`<aside class="cajon ancho" role="dialog" aria-modal="true" aria-labelledby="nTit">
    <div class="cajon-cab"><div style="min-width:0"><h2 id="nTit">${orig ? (ro ? 'Novedad' : 'Editar novedad') : 'Nueva novedad'}</h2><p>${ro ? (n.juego === 'general' ? 'Las noticias generales las cambia un Admin.' : 'Sólo la cambia un Admin o quien tiene ese juego asignado.') : 'Los cambios quedan listos para publicar con «Publicar».'}</p></div>
      <button type="button" class="btn icono chico fantasma cerrar" data-accion="cerrar-capa" aria-label="Cerrar">${ic('x', 's16')}</button></div>
    <div class="cajon-cuerpo nov-ed">
      <div class="lc-fila">
        <label class="lc-campo"><span class="lab">Dónde aparece</span><select class="sel" data-n="juego"${dis(ro)}>${juegosEd.map(j => `<option value="${esc(j.id)}" ${n.juego === j.id ? 'selected' : ''}>${j.id === 'general' ? 'General (todos los launchers)' : esc(j.nombre)}</option>`).join('')}</select></label>
        <label class="lc-campo"><span class="lab">Etiqueta</span><select class="sel" data-n="etiqueta" id="nEtq"${dis(ro)}>${opcionesEtq(n)}</select></label>
        <label class="lc-campo"><span class="lab">Fecha</span><input type="date" class="lc-in" data-n="fecha" value="${esc(n.fecha || '')}"${dis(ro)}></label>
      </div>
      <label class="lc-campo"><span class="lab">Título <span class="muy-tenue" id="nCuT"></span></span><input class="lc-in" maxlength="80" data-n="titulo" value="${esc(n.titulo)}" placeholder="Por ejemplo: Parche r187"${ro ? ' disabled' : ' autofocus'}></label>
      <label class="lc-campo"><span class="lab">Imagen · opcional</span><input class="lc-in" data-n="imagen" value="${esc(n.imagen || '')}" placeholder="https://…" inputmode="url" spellcheck="false"${dis(ro)}><span class="lc-error" id="nErrImg"></span></label>
      <label class="lc-campo"><span class="lab">Texto</span><textarea class="area" data-n="texto" maxlength="${max}" style="min-height:150px"${dis(ro)}>${esc(n.texto || '')}</textarea>
        <span class="cuenta-txt"><span># título · ## subtítulo · - lista · **negrita**</span><span id="nCuX"></span></span></label>
      <div class="lc-fila">
        <label class="lc-check"><input type="checkbox" data-n="fijada" ${n.fijada ? 'checked' : ''}${dis(ro)}><span><b>Fijada</b><span>Aparece primero, aunque haya otras más nuevas.</span></span></label>
        <label class="lc-check"><input type="checkbox" data-n="activo" ${n.activo ? 'checked' : ''}${dis(ro)}><span><b>Visible</b><span>Si la oculta, el launcher no la muestra.</span></span></label>
      </div>
      <div><span class="lab">Vista previa del popup</span><div id="nPrevia"></div></div>
    </div>
    <div class="cajon-pie">${orig && !ro ? `<span class="izq"><button type="button" class="btn chico peligro" id="nQuitar">${ic('x', 's14')}Quitar</button></span>` : '<span class="izq"></span>'}
      <button type="button" class="btn" data-accion="cerrar-capa">${ro ? 'Cerrar' : 'Cancelar'}</button>${ro ? '' : `<button type="button" class="btn prim" id="nOk">${orig ? 'Aplicar' : 'Agregar'}</button>`}</div></aside>`);
  const malo = () => {
    if (!String(n.titulo || '').trim()) return 'Falta el título.';
    if (n.imagen && !httpsOk(n.imagen)) return 'La imagen tiene que ser una dirección que empiece con https://';
    if (String(n.texto || '').length > max) return `El texto pasa de ${max} letras.`;
    if (n.juego === 'general' && !(d.etiquetas_general || []).includes(n.etiqueta)) return 'Esa etiqueta no va en lo general.';
    return null;
  };
  const previa = () => {
    const host = (() => { try { return new URL(n.imagen).host; } catch (e) { return ''; } })();
    $('#nPrevia', pn).innerHTML = `<div class="nv-pop"><div class="nv-img">${portadaNov(n.juego, 'nv-fondo')}${n.imagen && httpsOk(n.imagen) ? `<span class="nv-img-nota">${ic('eye', 's14')}En el launcher va la imagen de ${esc(host)}</span>` : ''}</div>
      <div class="nv-cuerpo">${metaNov(n)}${n.juego !== 'general' ? `<span class="muy-tenue" style="font-size:12px">${esc(juegoNov(n.juego).nombre)}</span>` : ''}
      <h2>${esc(n.titulo || 'Título de la novedad')}</h2><div class="nv-texto">${formatoNov(n.texto) || '<p class="tenue">El texto aparece aquí.</p>'}</div></div></div>`;
    $('#nCuT', pn).textContent = `${String(n.titulo || '').length}/80`;
    $('#nCuX', pn).textContent = `${String(n.texto || '').length}/${max}`;
    const err = n.imagen && !httpsOk(n.imagen);
    $('#nErrImg', pn).textContent = err ? 'Sólo direcciones que empiecen con https://' : '';
    pn.querySelector('[data-n="imagen"]').classList.toggle('mal', !!err);
  };
  pn.addEventListener('input', e => {
    const c = e.target.dataset.n; if (!c || ro) return;
    n[c] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    if (c === 'juego') { const ok = (n.juego === 'general' ? d.etiquetas_general : d.etiquetas) || []; if (!ok.includes(n.etiqueta)) n.etiqueta = n.juego === 'general' ? ok[0] : (ok.includes('parche') ? 'parche' : ok[0]); $('#nEtq', pn).innerHTML = opcionesEtq(n); }
    previa();
  });
  previa();
  const ok = $('#nOk', pn);
  if (ok) ok.addEventListener('click', () => {
    const e = malo(); if (e) { toast({ t: 'Falta corregir algo', sub: esc(e), tipo: 'err' }); return; }
    n.titulo = n.titulo.trim();
    if (orig) N.lista[N.lista.indexOf(orig)] = n; else N.lista.unshift(n);
    if (n.juego !== 'general') N.juego = n.juego;
    cerrarCapa(); pintarNov();
    toast({ t: orig ? 'Cambio listo' : 'Novedad agregada', sub: 'Se ve en los launchers cuando toque «Publicar».', tipo: 'info' });
  });
  const q = $('#nQuitar', pn);
  if (q) q.addEventListener('click', () => confirmar({ titulo: '¿Quitar esta novedad?', ok: 'Quitar', icono: 'x', txt: `«${esc(orig.titulo)}» deja de verse en los launchers cuando publique.`,
    alAceptar: () => { N.lista.splice(N.lista.indexOf(orig), 1); pintarNov(); } }));
}
function publicarNov() {
  const N = S.nov; if (!N || N.publicando || !novSucio()) return;
  const mias = N.lista.filter(n => n.editable);
  confirmar({ titulo: '¿Publicar las novedades?', icono: 'send', peligro: false, ok: 'Publicar',
    txt: 'Llegan en vivo a los launchers de toda la red. Las novedades de juegos que no son suyos quedan como están.',
    alAceptar: async () => {
      N.publicando = true; pintarAccNov();
      const r = await api('novedades', { noticias: mias.map(n => { const x = JSON.parse(ser(n)); delete x.editable; return x; }), base: N.d.base });
      if (S.nov !== N) return;
      N.publicando = false;
      if (r.ok && !r.d.sin_servidor) { S.nov = nuevoNov(r.d, N.juego); pintarNov(); toast({ t: 'Novedades publicadas', sub: 'Los launchers ya las muestran. Quedó en la auditoría.' }); return; }
      if (r.status === 409) {
        toast({ t: 'Alguien publicó mientras usted editaba', sub: errTxt(r), tipo: 'err', ms: 10000 });
        const r2 = await api('novedades');
        if (S.nov === N && r2.ok) { S.nov = nuevoNov(r2.d, N.juego); pintarNov(); }
        return;
      }
      pintarAccNov();
      toast({ t: 'No se pudieron publicar', sub: r.d && r.d.sin_servidor ? esc(r.d.sin_servidor) : errTxt(r), tipo: 'err', ms: 9000 });
    } });
}
function accionNov(a) {
  const N = S.nov; if (!N) return;
  const k = a.dataset.k, n = k ? N.lista.find(x => x._k === k) : null;
  switch (a.dataset.accion) {
    case 'nov-juego': N.juego = a.dataset.j; pintarNov(); { const t = $(`[data-accion="nov-juego"][data-j="${a.dataset.j}"]`); if (t) t.focus(); } break;
    case 'nov-abrir': editarNov(k); break;
    case 'nov-nueva': editarNov(null, a.dataset.juego); break;
    case 'nov-fijar': if (n && n.editable) { n.fijada = !n.fijada; pintarNov(); const b = $(`[data-accion="nov-fijar"][data-k="${k}"]`); if (b) b.focus(); } break;
    case 'nov-ver': if (n && n.editable) { n.activo = !n.activo; pintarNov(); const b = $(`[data-accion="nov-ver"][data-k="${k}"]`); if (b) b.focus(); } break;
    case 'nov-publicar': publicarNov(); break;
    case 'nov-descartar': confirmar({ titulo: '¿Descartar los cambios?', icono: 'refresh', ok: 'Descartar', txt: 'Las novedades vuelven a lo que está publicado ahora.',
      alAceptar: () => { S.nov = nuevoNov(N.d, N.juego); pintarNov(); toast({ t: 'Cambios descartados', tipo: 'info' }); } }); break;
  }
}

/* ══════════════ salir con cambios sin publicar ══════════════ */
const hayCambios = () => !!((S.jc && suciasJc(S.jc).length) || novSucio());
function mismaPagina(h) {
  if (S.jc) { const b = `#/j/${S.jc.jid}/${S.jc.env}`; return h === b || h.startsWith(b + '/'); }
  if (S.nov) return h === '#/novedades';
  return false;
}
function pedirSalir(seguir) {
  confirmar({ titulo: '¿Salir sin publicar?', icono: 'alert', ok: 'Salir y descartar', txt: 'Hay cambios sin publicar en esta página. Si sale ahora, se pierden.',
    alAceptar: () => { S.jc = null; S.nov = null; seguir(); } });
}
window.addEventListener('beforeunload', e => { if (hayCambios()) { e.preventDefault(); e.returnValue = ''; } });

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   Navegación, clics y reloj
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
function go(h, reemplazar, forzar) {
  if (!forzar && hayCambios() && !mismaPagina(h)) { pedirSalir(() => go(h, reemplazar, true)); return; }
  if (!forzar && mismaPagina(h)) {                        // ★ la misma página: cambiar de parte sin perder el borrador
    if (S.jc) { const t = h.split('/')[4]; if (tabsJc(S.jc).includes(t) && t !== S.jc.tab) { S.jc.tab = t; pintarJ(); } }
    return;
  }
  S.ruta = h;
  try { if (reemplazar) history.replaceState(null, '', h); else if (location.hash !== h) history.pushState(null, '', h); } catch (err) { /* nada */ }
  ruta();
}
function ruta() {
  cerrarCapa(); cerrarPop();
  S.jc = null; S.nov = null;
  const h = S.ruta.replace(/^#\/?/, '').split('/');
  window.scrollTo(0, 0);
  if (!S.sesion) { vistaLogin(); return; }
  if (h[0] === 'entrar' || !h[0]) { go('#/juegos', true); return; }
  if (h[0] === 'j' && h[1]) vistaJuego(h[1], h[2] === 'test' ? 'test' : 'live', h[3]);
  else if (h[0] === 'novedades') vistaNovedades();
  else if (h[0] === 'persona' && /^\d+$/.test(h[1] || '')) vistaPersona(h[1]);
  else if (h[0] === 'red') vistaRed();
  else { if (h[0] !== 'juegos') { S.ruta = '#/juegos'; try { history.replaceState(null, '', '#/juegos'); } catch (err) { /* nada */ } } vistaJuegos(); }
}
async function salir() {
  await api('salir', {});
  S.sesion = null; S.errorLogin = null; S.jc = null; S.nov = null; document.body.className = '';
  go('#/entrar', true, true);
  toast({ t: 'Sesión cerrada', tipo: 'info' });
}
let buscarReloj = null;
document.addEventListener('input', e => {
  if (e.target.id === 'qCuenta') { clearTimeout(buscarReloj); const v = e.target.value; buscarReloj = setTimeout(() => pintarCuentas(v), 250); return; }
  if (e.target.id === 'jcBusq') { clearTimeout(busqReloj); const v = e.target.value; busqReloj = setTimeout(() => buscarItem(v), 250); return; }
  if (e.target.dataset && e.target.dataset.jc && e.target.type !== 'radio' && e.target.type !== 'checkbox' && e.target.tagName !== 'SELECT') cambioJc(e.target, false);
});
/* los que terminan con «change»: casillas, radios, listas, fechas; y los números se ajustan a su rango al salir del campo */
document.addEventListener('change', e => { if (e.target.dataset && e.target.dataset.jc) cambioJc(e.target, true); });
document.addEventListener('click', async e => {
  if (pop && !pop.contains(e.target) && !(pop._ancla && pop._ancla.contains(e.target))) cerrarPop();
  const prov = e.target.closest('[data-prov]'); if (prov) { if (!prov.disabled) entrarCon(prov.dataset.prov); return; }
  const tab = e.target.closest('[data-tab]'); if (tab) { S.tabRed = tab.dataset.tab; $$('[data-tab]').forEach(b => b.setAttribute('aria-selected', b === tab)); $('#panInv').hidden = S.tabRed === 'lanz'; $('#panLanz').hidden = S.tabRed !== 'lanz'; return; }
  const ir = e.target.closest('[data-ir]'); if (ir) { go(ir.dataset.ir); return; }
  const enlace = e.target.closest('a[href^="#/"]'); if (enlace && !e.ctrlKey && !e.metaKey && !e.shiftKey) { e.preventDefault(); go(enlace.getAttribute('href')); return; }
  const a = e.target.closest('[data-accion]'); if (!a) return;
  switch (a.dataset.accion) {
    case 'cerrar-capa': cerrarCapa(); break;
    case 'salir': cerrarPop(); if (hayCambios()) pedirSalir(salir); else salir(); break;
    case 'lg-otra': S.errorLogin = null; $('#lgRes').innerHTML = ''; { const b = $('.lg-prov:not(:disabled)'); if (b) b.focus(); } break;
    case 'lg-copiar': { const t = a.dataset.txt; const ok = () => toast({ t: 'Copiado', sub: esc(t), tipo: 'info' }); try { navigator.clipboard.writeText(t).then(ok, ok); } catch (err) { ok(); } break; }
    case 'carrusel-mover': { const fila = a.closest('.gc-carrusel').querySelector('.gc-fila'), g = fila.querySelector('.gc'); fila.scrollBy({ left: Number(a.dataset.dir) * ((g ? g.offsetWidth : 240) + 18), behavior: 'smooth' }); break; }
    case 'yo': abrirPop(a, `<div style="display:flex;gap:10px;align-items:center;padding:8px 10px">${ava(S.sesion.nombre, 'redondo')}<span><b style="display:block;font-size:13px">${esc(S.sesion.nombre)}</b><span class="tenue" style="font-size:12px">Eñeños-ID ${esc(S.sesion.uid)}${S.sesion.vias.length ? ' · ' + S.sesion.vias.map(v => PROV[v] || esc(v)).join(' y ') : ''}</span></span></div><hr class="sep" style="margin:4px 0"><button type="button" data-accion="salir">${ic('logout', 's16')}Cerrar sesión</button>`, 260); break;
    case 'inv-decidir': {
      const li = a.closest('li'); $$('button', li).forEach(b => { b.disabled = true; });
      const r = await api('invitacion', { id: Number(a.dataset.id), accion: a.dataset.dec });
      if (!r.ok) { toast({ t: 'No se pudo', sub: errTxt(r), tipo: 'err' }); $$('button', li).forEach(b => { b.disabled = false; }); pintarInvitaciones(); break; }
      toast({ t: a.dataset.dec === 'aprobar' ? 'Invitación aprobada' : 'Invitación rechazada', sub: 'Se avisa en Discord y queda en la auditoría.', tipo: a.dataset.dec === 'aprobar' ? 'ok' : 'info' });
      pintarInvitaciones(); pintarLanzamientos(); pintarAuditoria(); break; }
    case 'mod-juego': cambiarJuegosMod(Number(a.dataset.i), a.dataset.j); break;
    case 'quitar-mod': { const m = S.equipoLista[Number(a.dataset.i)]; if (!m) break;
      confirmar({ titulo: `¿Sacar a ${esc(m.nombre)} del equipo?`, ok: 'Sacar', icono: 'shieldok', txt: 'Pierde el acceso al Coordinador al instante. Su cuenta sigue igual.',
        alAceptar: async () => { const r = await api('equipo', { accion: 'quitar', uid: m.uid }); if (!r.ok) { toast({ t: 'No se pudo', sub: errTxt(r), tipo: 'err' }); return; } pintarMods(r.d); toast({ t: `${esc(m.nombre)} ya no está en el equipo` }); pintarAuditoria(); } }); break; }
    case 'agregar-mod': confirmar({ titulo: 'Agregar al equipo', icono: 'shieldok', peligro: false, ok: 'Agregar',
      txt: 'Escriba su Eñeños-ID (el número). Para entrar necesita Discord o Google vinculado. Después, asígnele juegos tocando sus etiquetas.',
      extra: '<span class="lab">Eñeños-ID</span><label class="campo"><span class="sr">Eñeños-ID</span><input id="mdExtra" inputmode="numeric" placeholder="10000123" autocomplete="off"></label>',
      alAceptar: async v => { if (!v.trim()) return; const r = await api('equipo', { accion: 'agregar', uid: v.trim(), juegos: [] });
        if (!r.ok) { toast({ t: 'No se pudo agregar', sub: errTxt(r), tipo: 'err' }); return; }
        pintarMods(r.d); pintarAuditoria(); toast({ t: 'Se sumó al equipo', sub: r.d.aviso ? esc(r.d.aviso) : 'Asígnele juegos tocando sus etiquetas.', tipo: r.d.aviso ? 'info' : 'ok', ms: 8000 }); } }); break;
    case 'persona-accion': accionPersona(a.dataset.acc, a.dataset.pase); break;
    case 'banear-varios': formBaneo(''); break;
    case 'ban-levantar': levantarBaneo(Number(a.dataset.i)); break;
    case 'jc-item-elegir': elegirItem(a.dataset.item); break;
    default:
      if (a.dataset.accion.startsWith('jc-')) accionJc(a);
      else if (a.dataset.accion.startsWith('nov-')) accionNov(a);
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { if (pop) { const an = pop._ancla; cerrarPop(); if (an) an.focus(); } else if (capas.innerHTML) cerrarCapa(); return; }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('li[role="link"]')) { e.preventDefault(); e.target.click(); return; }
  if (e.key === 'Enter' && e.target.id === 'mdExtra') { const b = $('#mdOk'); if (b) b.click(); return; }
  if (e.key === 'Enter' && e.target.id === 'jcBusq') { e.preventDefault(); const b = $('#jcBusRes button'); if (b) b.click(); return; }
  if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && e.target.matches('[role="tab"][data-accion="jc-tab"], [role="tab"][data-accion="nov-juego"]')) {
    const ts = $$(`[role="tab"][data-accion="${e.target.dataset.accion}"]`), k = ts.indexOf(e.target), sig = ts[(k + (e.key === 'ArrowRight' ? 1 : ts.length - 1)) % ts.length];
    if (sig) { e.preventDefault(); sig.click(); } return;
  }
  if (e.key === 'Tab' && capas.innerHTML) {
    const f = $$('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled)', capas.children[1]).filter(x => x.offsetParent !== null);
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
  }
});
['mouseover', 'focusin'].forEach(ev => document.addEventListener(ev, e => { const c = e.target.closest && e.target.closest('[data-fx-id]'); if (c && $('.fx')) setFx(c.dataset.fxId); }));
/* sin arte en el servidor (o un archivo que no carga): la tarjeta queda con su color, sin ícono roto */
document.addEventListener('error', e => {
  const t = e.target; if (!t || t.tagName !== 'IMG') return;
  if (t.dataset.fallo && FALLO[t.dataset.fallo]) { t.outerHTML = FALLO[t.dataset.fallo](t.className.replace(/\bip\b/, '').trim()); return; }   // ★ fase B: el ícono de siempre
  if (t.closest('.gc-arte, .lanz .ic, .jc-min, .nov-jtab, .nov-portada, .nov-item, .nv-img')) t.style.visibility = 'hidden';
}, true);
let carruselReloj = null;
window.addEventListener('resize', () => { if (pop) cerrarPop(); ajustarGrilla(); clearTimeout(carruselReloj); carruselReloj = setTimeout(montarCarruseles, 150); });

function falta(ms) { let s = Math.max(0, Math.floor((ms - Date.now()) / 1000)); const d = Math.floor(s / 86400); s %= 86400; return [d, Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60]; }
function tic() {
  $$('[data-cuenta]').forEach(el => { const t = Number(el.dataset.cuenta); if (t <= Date.now()) { el.textContent = 'Abierto'; return; } const [d, h, m, s] = falta(t); el.textContent = `${d ? d + ' d ' : ''}${dos(h)}:${dos(m)}:${dos(s)}`; });
}
setInterval(tic, 1000);
/* «Elegir juego» se refresca solo cada 30 s (estado y jugando ahora) */
setInterval(() => { if (S.sesion && S.ruta === '#/juegos' && !capas.innerHTML && document.visibilityState === 'visible') vistaJuegos(true); }, 30000);
const alVolver = () => {
  if (!location.hash || location.hash === S.ruta) return;
  const destino = location.hash;
  if (mismaPagina(destino)) { go(destino, true); return; }
  if (hayCambios()) { try { history.pushState(null, '', S.ruta); } catch (err) { /* nada */ } pedirSalir(() => go(destino, false, true)); return; }
  S.ruta = destino; ruta();
};
window.addEventListener('hashchange', alVolver);
window.addEventListener('popstate', alVolver);

async function arrancar() {
  let ticket = null;
  try { ticket = new URLSearchParams(location.search).get('ticket'); } catch (err) { /* nada */ }
  if (ticket) {
    // ⛔ el ticket sale de la barra de direcciones YA: que no quede en el historial ni en una captura
    const base = location.pathname.replace(/entrar\/?$/, '');
    try { history.replaceState(null, '', base + '#/juegos'); } catch (err) { /* nada */ }
  }
  const [cat, ok] = await Promise.all([api('catalogo'), ticket ? canjearTicket(ticket) : Promise.resolve(false)]);
  S.catalogo = (cat.ok && cat.d.juegos) || [];
  const est = await api('estado');
  if (est.ok) { S.proveedores = est.d.proveedores || {}; S.configurado = !!est.d.configurado; S.sesion = est.d.sesion || null; }
  if (ticket && !ok) { S.sesion = null; try { history.replaceState(null, '', location.pathname + '#/entrar'); } catch (err) { /* nada */ } }
  S.ruta = location.hash && location.hash !== '#/entrar' ? location.hash : '#/juegos';
  ruta();
}
arrancar();
