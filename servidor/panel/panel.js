'use strict';
/* ══════════════════════════════════════════════════════════════════════════════════════════════
   panel.js — el Coordinador Eñeños, FASE A (19-nov-2026). El diseño es el del prototipo aprobado por Benja;
   los datos son los de verdad (servidor/coordinador.py). ⛔ Nada inventado: si un dato no existe, no se muestra.
     #/entrar          sólo Discord o Google vinculados a un Eñeños ID con rol
     #/juegos          las tarjetas de juegos.json, con PROD / TEST
     #/red             personas, invitaciones, lanzamientos, moderadores y permisos, auditoría
     #/persona/<uid>   vínculos, estado y permisos por juego (★ 20-nov: banear en varios juegos, con tiempo y motivo)
     #/j/…             lo de adentro de cada juego: fases B y C («Próximamente»)
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
  const d = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60); return h ? `${d} d ${h} h` : `${d} ${d === 1 ? 'día' : 'días'}`;
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
    S.sesion = null; toast({ t: 'La sesión terminó', sub: 'Vuelva a entrar con Discord o Google.', tipo: 'info' }); go('#/entrar', true);
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
    <nav class="barra-nav" aria-label="Secciones">${nav('juegos', 'Juegos')}${nav('red', 'La red')}</nav>
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
    + `<div class="tenue" style="padding:10px 16px 14px;border-top:1px solid var(--line);font-size:12px">${ic('info', 's14')} Antes de la fecha sólo entran el equipo y los aprobados. La fecha se cambia en <code>config/lanzamientos.json</code> (desde el panel, en una fase siguiente).</div>`
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
   (cada uno con TODOS sus servidores). Duración: horas / días / permanente (sólo Admin); un moderador, hasta su tope.
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
        <div class="chips" role="group" aria-label="Duración"><button type="button" class="chipb" data-bn="horas" aria-pressed="true">Horas</button><button type="button" class="chipb" data-bn="dias" aria-pressed="false">Días</button>${lim.permanente ? '<button type="button" class="chipb" data-bn="permanente" aria-pressed="false">Permanente</button>' : ''}</div>
        <label class="campo" id="bnCantCampo" style="margin-top:8px;max-width:200px"><span class="sr">Cantidad</span><input id="bnCant" type="number" min="1" step="1" value="24" inputmode="numeric"><span class="tenue" id="bnUnidad" style="font-size:13px">horas</span></label>
        ${lim.tope_seg ? `<div class="tenue" style="font-size:12px;margin-top:6px">Como moderador puede banear hasta ${fmtDur(lim.tope_seg / 60)}. Más largo, o permanente: un Admin.</div>` : ''}</div>
      <div><span class="lab">Motivo (lo ve la persona y queda en la auditoría)</span>
        <label class="campo"><span class="sr">Motivo</span><input id="bnMotivo" maxlength="${Number(lim.motivo_max) || 200}" autocomplete="off" placeholder="Por ejemplo: insultos en el chat"></label>
        <div class="cuenta-txt"><span id="bnErr" style="color:var(--red)"></span><span id="bnCuenta">0/${Number(lim.motivo_max) || 200}</span></div></div>
    </div>
    <div class="modal-pie"><button type="button" class="btn" data-accion="cerrar-capa">Cancelar</button><button type="button" class="btn peligro lleno" id="bnOk">Banear</button></div></div>`);
  let tipo = 'horas';
  const err = t => { $('#bnErr', pn).textContent = t || ''; };
  $$('[data-bn]', pn).forEach(b => b.addEventListener('click', () => {
    tipo = b.dataset.bn;
    $$('[data-bn]', pn).forEach(x => x.setAttribute('aria-pressed', x === b));
    $('#bnCantCampo', pn).hidden = tipo === 'permanente';
    $('#bnUnidad', pn).textContent = tipo === 'dias' ? 'días' : 'horas';
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
      if (lim.tope_seg && n * (tipo === 'dias' ? 86400 : 3600) > lim.tope_seg) return err(`Como moderador, hasta ${fmtDur(lim.tope_seg / 60)}.`);
      cuerpo[tipo] = n;
    }
    if (!cuerpo.motivo) { mot.focus(); return err('Escriba el motivo.'); }
    const b = $('#bnOk', pn); b.disabled = true;
    const r = await api('accion', cuerpo);
    b.disabled = false;
    if (!r.ok) return err((r.d && (r.d.texto || r.d.error)) || `Error ${r.status}`);
    cerrarCapa();
    pintarPersona(r.d.persona);
    const dur = tipo === 'permanente' ? 'de forma permanente' : `por ${fmtDur(Number(cuerpo[tipo]) * (tipo === 'dias' ? 1440 : 60))}`;
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
   Lo de adentro de cada juego: fases B y C
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
function vistaProx(jid, env) {
  const j = S.catalogo.find(x => x.id === jid);
  document.body.classList.toggle('test', env === 'test');
  document.title = `${j ? j.nombre : 'Juego'} · Coordinador Eñeños`;
  raiz.innerHTML = barraHub('juegos') + `<main class="hub" id="contenido">
    <a class="volver" href="#/juegos" style="margin-bottom:12px;display:inline-flex">${ic('left', 's14')}Juegos</a>
    <section class="caja" style="max-width:560px;margin:24px auto">${vacio(`${j ? esc(j.nombre) : 'Este juego'} · ${ENV_TXT[env] || 'PROD'} — próximamente`,
      'Lo de adentro de cada juego (resumen, conectados, fichas, gráficos y contenido dinámico) llega en la próxima fase del Coordinador.',
      '<a class="btn chico" href="#/red">Ir a La red</a>')}</section>
  </main>`;
}

/* ══════════════════════════════════════════════════════════════════════════════════════════════
   Navegación, clics y reloj
   ══════════════════════════════════════════════════════════════════════════════════════════════ */
function go(h, reemplazar) {
  S.ruta = h;
  try { if (reemplazar) history.replaceState(null, '', h); else if (location.hash !== h) history.pushState(null, '', h); } catch (err) { /* nada */ }
  ruta();
}
function ruta() {
  cerrarCapa(); cerrarPop();
  const h = S.ruta.replace(/^#\/?/, '').split('/');
  window.scrollTo(0, 0);
  if (!S.sesion) { vistaLogin(); return; }
  if (h[0] === 'entrar' || !h[0]) { go('#/juegos', true); return; }
  if (h[0] === 'j') vistaProx(h[1], h[2] === 'test' ? 'test' : 'live');
  else if (h[0] === 'persona' && /^\d+$/.test(h[1] || '')) vistaPersona(h[1]);
  else if (h[0] === 'red') vistaRed();
  else { if (h[0] !== 'juegos') { S.ruta = '#/juegos'; try { history.replaceState(null, '', '#/juegos'); } catch (err) { /* nada */ } } vistaJuegos(); }
}
async function salir() {
  await api('salir', {});
  S.sesion = null; S.errorLogin = null; document.body.className = '';
  go('#/entrar', true);
  toast({ t: 'Sesión cerrada', tipo: 'info' });
}
let buscarReloj = null;
document.addEventListener('input', e => { if (e.target.id === 'qCuenta') { clearTimeout(buscarReloj); const v = e.target.value; buscarReloj = setTimeout(() => pintarCuentas(v), 250); } });
document.addEventListener('click', async e => {
  if (pop && !pop.contains(e.target) && !(pop._ancla && pop._ancla.contains(e.target))) cerrarPop();
  const prov = e.target.closest('[data-prov]'); if (prov) { if (!prov.disabled) entrarCon(prov.dataset.prov); return; }
  const tab = e.target.closest('[data-tab]'); if (tab) { S.tabRed = tab.dataset.tab; $$('[data-tab]').forEach(b => b.setAttribute('aria-selected', b === tab)); $('#panInv').hidden = S.tabRed === 'lanz'; $('#panLanz').hidden = S.tabRed !== 'lanz'; return; }
  const ir = e.target.closest('[data-ir]'); if (ir) { go(ir.dataset.ir); return; }
  const enlace = e.target.closest('a[href^="#/"]'); if (enlace && !e.ctrlKey && !e.metaKey && !e.shiftKey) { e.preventDefault(); go(enlace.getAttribute('href')); return; }
  const a = e.target.closest('[data-accion]'); if (!a) return;
  switch (a.dataset.accion) {
    case 'cerrar-capa': cerrarCapa(); break;
    case 'salir': cerrarPop(); salir(); break;
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
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { if (pop) { const an = pop._ancla; cerrarPop(); if (an) an.focus(); } else if (capas.innerHTML) cerrarCapa(); return; }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('li[role="link"]')) { e.preventDefault(); e.target.click(); return; }
  if (e.key === 'Enter' && e.target.id === 'mdExtra') { const b = $('#mdOk'); if (b) b.click(); return; }
  if (e.key === 'Tab' && capas.innerHTML) {
    const f = $$('button:not(:disabled), a[href], input:not(:disabled)', capas.children[1]).filter(x => x.offsetParent !== null);
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
  }
});
['mouseover', 'focusin'].forEach(ev => document.addEventListener(ev, e => { const c = e.target.closest && e.target.closest('[data-fx-id]'); if (c && $('.fx')) setFx(c.dataset.fxId); }));
/* sin arte en el servidor (o un archivo que no carga): la tarjeta queda con su color, sin ícono roto */
document.addEventListener('error', e => { const t = e.target; if (t && t.tagName === 'IMG' && t.closest('.gc-arte, .lanz .ic')) t.style.visibility = 'hidden'; }, true);
let carruselReloj = null;
window.addEventListener('resize', () => { if (pop) cerrarPop(); ajustarGrilla(); clearTimeout(carruselReloj); carruselReloj = setTimeout(montarCarruseles, 150); });

function falta(ms) { let s = Math.max(0, Math.floor((ms - Date.now()) / 1000)); const d = Math.floor(s / 86400); s %= 86400; return [d, Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60]; }
function tic() {
  $$('[data-cuenta]').forEach(el => { const t = Number(el.dataset.cuenta); if (t <= Date.now()) { el.textContent = 'Abierto'; return; } const [d, h, m, s] = falta(t); el.textContent = `${d ? d + ' d ' : ''}${dos(h)}:${dos(m)}:${dos(s)}`; });
}
setInterval(tic, 1000);
/* «Elegir juego» se refresca solo cada 30 s (estado y jugando ahora) */
setInterval(() => { if (S.sesion && S.ruta === '#/juegos' && !capas.innerHTML && document.visibilityState === 'visible') vistaJuegos(true); }, 30000);
const alVolver = () => { if (location.hash && location.hash !== S.ruta) { S.ruta = location.hash; ruta(); } };
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
