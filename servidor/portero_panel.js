// portero_panel.js — el panel de aprobaciones de EDA (12-nov). Lo sirve el portero en `/cuentas/admin` (Chile) y, por
// proxy, en `eñeños.link/admin`. Sesión por cookie HttpOnly; todo POST lleva X-R2 (lo exige el portero).
'use strict';
const BASE = location.pathname.replace(/\/+$/, '');          // «/cuentas/admin» o «/admin»
const JUEGO = 'eda';
let ROL = 'admin';                                            // ★ 12-nov: o 'moderador' (sólo aprueba / quita)
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(metodo, ruta, cuerpo) {
  const op = { method: metodo, credentials: 'same-origin', headers: { 'X-R2': '1' } };
  if (cuerpo !== undefined) { op.headers['Content-Type'] = 'application/json'; op.body = JSON.stringify(cuerpo); }
  let r, d = {};
  try { r = await fetch(BASE + ruta, op); } catch (e) { return [0, { error: 'Sin conexión con el servidor.' }]; }
  try { d = await r.json(); } catch (e) { /* sin cuerpo */ }
  return [r.status, d];
}
function aviso(texto, error) {
  $('msg').textContent = error ? '' : texto; $('error').textContent = error ? texto : '';
  if (texto) setTimeout(() => { if ($(error ? 'error' : 'msg').textContent === texto) $(error ? 'error' : 'msg').textContent = ''; }, 6000);
}
function mostrar(panel) { $('login').classList.toggle('hid', panel); $('panel').classList.toggle('hid', !panel); }

function chips(c) {
  let s = '';
  if (c.aprobada) s += '<span class="chip si">APROBADA</span>';
  if (c.baneada) s += '<span class="chip ban">BANEADA EN EDA</span>';
  if (c.r2beat !== 'ok') s += `<span class="chip r2">R2BEAT: ${esc(c.r2beat.toUpperCase())}</span>`;
  return s || '<span class="tenue">sin acceso</span>';
}
function botones(c) {
  const b = [];
  b.push(c.aprobada ? `<button class="peligro" data-a="quitar" data-u="${c.uid}">Quitar</button>`
                    : `<button class="ok" data-a="aprobar" data-u="${c.uid}">Aprobar</button>`);
  if (ROL === 'admin') b.push(c.baneada ? `<button data-a="desbanear" data-u="${c.uid}">Desbanear</button>`
                                       : `<button class="peligro" data-a="banear" data-u="${c.uid}">Banear</button>`);
  return b.join('');
}
const nombre = c => `<b>${esc(c.usuario)}</b> <span class="tenue">#${c.uid}</span>`;

function entro(d) {
  ROL = d.rol === 'moderador' ? 'moderador' : 'admin';
  $('quien').textContent = d.admin + (ROL === 'moderador' ? ' · moderador' : '');
  mostrar(true); cargar(); invitacion(); listaInvitaciones();
}

// ★ 18-nov: la solicitud de invitación anticipada que llegó por Discord. El enlace trae «#invitacion=N&accion=…»,
//   pero NO decide solo (Discord abre los enlaces para la vista previa): muestra la solicitud y se aprieta acá.
const INV_ESTADO = { pendiente: 'Pendiente', aprobada: 'Aprobada', rechazada: 'Rechazada' };
async function invitacion() {
  const h = new URLSearchParams(location.hash.replace(/^#/, ''));
  const id = h.get('invitacion');
  if (!id) return $('invCaja').classList.add('hid');
  const [st, d] = await api('GET', '/invitacion?id=' + encodeURIComponent(id));
  $('invCaja').classList.remove('hid');
  $('invNum').textContent = '#' + id;
  if (st !== 200) { $('invTexto').textContent = d.error || 'No se pudo cargar la solicitud.'; $('invBotones').classList.add('hid'); return; }
  const f = d.invitacion;
  $('invTexto').innerHTML = `<b>${esc(f.apodo || 'Sin Ñ2-ID')}</b> <span class="tenue">(${esc(f.usuario)} · Eñeños ID ${f.uid})</span>` +
    ` pide entrar antes a <b>${esc(f.nombre_juego)}</b> <span class="tenue">${esc(f.etiqueta)}</span>.`;
  const pend = f.estado === 'pendiente';
  $('invBotones').classList.toggle('hid', !pend);
  const sug = h.get('accion');
  $('invAprobar').classList.toggle('sugerido', sug === 'aprobar'); $('invRechazar').classList.toggle('sugerido', sug === 'rechazar');
  $('invEstado').textContent = pend ? (sug ? `Llegó desde Discord para ${sug === 'aprobar' ? 'APROBAR' : 'RECHAZAR'}: confírmelo con el botón.` : '')
                                    : `${INV_ESTADO[f.estado] || f.estado} por ${f.quien || '—'}.`;
}
async function listaInvitaciones() {
  const [st, d] = await api('GET', '/invitaciones');
  if (st !== 200) return;
  const fs = d.invitaciones || [];
  $('nInv').textContent = `(${fs.length})`;
  const fecha = t => new Date(t * 1000).toLocaleString('es', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  $('tInvitaciones').tBodies[0].innerHTML = fs.map(f =>
    `<tr><td><b>${esc(f.usuario)}</b> <span class="tenue">#${f.uid}</span></td><td>${esc(f.apodo || '—')}</td>` +
    `<td>${esc(f.nombre_juego)} <span class="tenue">${esc(f.etiqueta)}</span></td><td class="ocultable tenue">${fecha(f.creada)}</td>` +
    `<td class="acc"><button data-inv="${f.id}" data-acc="aprobar">Aprobar</button><button class="peligro" data-inv="${f.id}" data-acc="rechazar">Rechazar</button></td></tr>`
  ).join('') || '<tr><td colspan="5" class="tenue">No hay solicitudes pendientes.</td></tr>';
}
$('tInvitaciones').addEventListener('click', async e => {
  const b = e.target.closest('button[data-inv]'); if (!b) return;
  b.disabled = true;
  const [st, d] = await api('POST', '/invitacion', { id: Number(b.dataset.inv), accion: b.dataset.acc });
  if (st !== 200) aviso(d.error || 'No se pudo.', true);
  else aviso(b.dataset.acc === 'aprobar' ? 'Aprobada: ya puede entrar antes de la fecha.' : 'Rechazada.');
  listaInvitaciones(); invitacion(); cargar();
});
async function decidirInvitacion(accion) {
  const id = new URLSearchParams(location.hash.replace(/^#/, '')).get('invitacion');
  $('invAprobar').disabled = $('invRechazar').disabled = true;
  const [st, d] = await api('POST', '/invitacion', { id: Number(id), accion });
  $('invAprobar').disabled = $('invRechazar').disabled = false;
  if (st !== 200) aviso(d.error || 'No se pudo.', true);
  else aviso(accion === 'aprobar' ? 'Aprobada: ya puede entrar antes de la fecha.' : 'Rechazada.');
  invitacion(); cargar(); listaInvitaciones();
}
$('invAprobar').addEventListener('click', () => decidirInvitacion('aprobar'));
$('invRechazar').addEventListener('click', () => decidirInvitacion('rechazar'));
window.addEventListener('hashchange', invitacion);

async function cargar() {
  const [st, d] = await api('GET', '/lista?juego=' + JUEGO);
  if (st === 401) return mostrar(false);
  if (st !== 200) return aviso(d.error || 'No se pudo cargar la lista.', true);
  $('nApr').textContent = `(${d.aprobadas.length})`; $('nBan').textContent = `(${d.baneadas.length})`;
  $('tAprobadas').tBodies[0].innerHTML = d.aprobadas.map(c =>
    `<tr><td>${nombre(c)}</td><td>${esc(c.apodo)}</td><td class="ocultable tenue">${esc(c.desde)}</td>` +
    `<td class="ocultable tenue">${esc(c.quien)}</td><td class="acc"><button class="peligro" data-a="quitar" data-u="${c.uid}">Quitar</button></td></tr>`
  ).join('') || '<tr><td colspan="5" class="tenue">Todavía no hay cuentas aprobadas.</td></tr>';
  $('tBaneadas').tBodies[0].innerHTML = d.baneadas.map(c =>
    `<tr><td>${nombre(c)}</td><td>${esc(c.motivo)}</td><td class="ocultable tenue">${esc(c.desde)}</td>` +
    `<td class="ocultable tenue">${esc(c.quien)}</td><td class="acc">${ROL === 'admin' ? `<button data-a="desbanear" data-u="${c.uid}">Desbanear</button>` : ''}</td></tr>`
  ).join('') || '<tr><td colspan="5" class="tenue">Nadie baneado en EDA.</td></tr>';
  $('lAuditoria').innerHTML = d.auditoria.map(a =>
    `<li>${esc(a.cuando)} · <b>${esc(a.quien)}</b> ${esc(a.accion)}${a.usuario ? ` <b>${esc(a.usuario)}</b>` : ''}` +
    `${a.detalle ? ` — ${esc(a.detalle)}` : ''}</li>`).join('') || '<li>Sin movimientos.</li>';
}

async function buscar() {
  const q = $('inBuscar').value.trim();
  if (q.length < 2) return aviso('Escribí al menos 2 letras.', true);
  $('btnBuscar').disabled = true;
  const [st, d] = await api('GET', '/buscar?juego=' + JUEGO + '&q=' + encodeURIComponent(q));
  $('btnBuscar').disabled = false;
  if (st === 401) return mostrar(false);
  if (st !== 200) return aviso(d.error || 'No se pudo buscar.', true);
  const filas = d.cuentas.map(c => `<tr><td>${nombre(c)}</td><td>${esc(c.apodo)}</td><td>${chips(c)}</td><td class="acc">${botones(c)}</td></tr>`);
  $('tResultados').tBodies[0].innerHTML = filas.join('');
  $('tResultados').classList.toggle('hid', !filas.length); $('sinResultados').classList.toggle('hid', !!filas.length);
}

async function accion(a, uid, boton) {
  let detalle = '';
  if (a === 'banear') {
    detalle = prompt('¿Por qué se banea de EDA? (queda anotado)') ?? null;
    if (detalle === null) return;
  } else if (a === 'quitar' && !confirm('¿Quitarle el acceso a EDA a esta cuenta?')) return;
  boton.disabled = true;
  const [st, d] = await api('POST', '/' + a, { uid: Number(uid), juego: JUEGO, detalle });
  boton.disabled = false;
  if (st === 401) return mostrar(false);
  if (st !== 200) return aviso(d.error || 'No se pudo.', true);
  aviso({ aprobar: 'Aprobada', quitar: 'Acceso quitado', banear: 'Baneada de EDA', desbanear: 'Desbaneada' }[a] + ': ' + d.cuenta.usuario);
  await cargar();
  if (!$('tResultados').classList.contains('hid')) await buscar();
}

document.addEventListener('click', e => {
  const b = e.target.closest('button[data-a]');
  if (b) accion(b.dataset.a, b.dataset.u, b);
});
$('btnBuscar').addEventListener('click', buscar);
$('inBuscar').addEventListener('keydown', e => { if (e.key === 'Enter') buscar(); });
$('btnEntrar').addEventListener('click', async () => {
  $('errorLogin').textContent = '';
  const u = $('inUsuario').value.trim(), c = $('inClave').value;
  if (!u || !c) { $('errorLogin').textContent = 'Faltan usuario o contraseña.'; return; }
  $('btnEntrar').disabled = true;
  const [st, d] = await api('POST', '/entrar', { usuario: u, clave: c });
  $('btnEntrar').disabled = false; $('inClave').value = '';
  if (st !== 200) { $('errorLogin').textContent = d.error || 'No se pudo entrar.'; return; }
  entro(d);
});
$('inClave').addEventListener('keydown', e => { if (e.key === 'Enter') $('btnEntrar').click(); });
$('btnSalir').addEventListener('click', async () => { await api('POST', '/salir', {}); mostrar(false); });

(async () => {
  const [st, d] = await api('GET', '/yo');
  if (st === 200) entro(d);
  else { mostrar(false); $('inUsuario').focus(); }
})();
