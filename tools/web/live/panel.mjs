const connection = document.getElementById('connection');
const rows = document.getElementById('rows');
const empty = document.getElementById('empty');
const table = document.getElementById('table');
const updated = document.getElementById('updated');
let socket, retry, heartbeat, stopped = false, backoff = 1000, state = null, receivedAt = 0;
const duration = seconds => seconds < 60 ? `${seconds} s` : seconds < 3600 ? `${Math.floor(seconds / 60)} min` : `${Math.floor(seconds / 3600)} h ${Math.floor(seconds % 3600 / 60)} min`;
function render() {
  if (!state) return;
  for (const key of ['total', 'running', 'loading']) document.getElementById(key).textContent = state[key];
  empty.hidden = !!state.total; table.hidden = !state.total;
  empty.textContent = 'Todavía no hay sesiones conectadas. Abre el juego para aparecer aquí.';
  const now = state.at + Date.now() - receivedAt;
  updated.textContent = `Actualizado a las ${new Date(receivedAt).toLocaleTimeString('es')}`;
  const fragment = document.createDocumentFragment();
  for (const session of state.sessions) {
    const row = document.createElement('tr');
    const values = [`Jugador ${session.id.slice(0, 8)}`, session.phase === 'running' ? 'Juego abierto' : 'Cargando', session.visible ? 'En primer plano' : 'En segundo plano', duration(Math.max(0, Math.floor((now - session.joinedAt) / 1000)))];
    for (const value of values) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
    fragment.append(row);
  }
  rows.replaceChildren(fragment);
}
function disconnected() {
  state = null; connection.dataset.state = 'offline'; connection.textContent = 'Reconectando…';
  for (const key of ['total', 'running', 'loading']) document.getElementById(key).textContent = '—';
  rows.replaceChildren(); table.hidden = true; empty.hidden = false;
  empty.textContent = 'La conexión se ha interrumpido. Intentando reconectar…';
  updated.textContent = 'Esperando datos del servidor';
}
function connect() {
  if (stopped) return;
  const url = new URL('/api/presence/watch', location.href); url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const current = socket = new WebSocket(url);
  current.onopen = () => { backoff = 1000; heartbeat = setInterval(() => { if (current.readyState === WebSocket.OPEN) current.send('ping'); }, 25_000); };
  current.onmessage = event => {
    if (current !== socket || event.data === 'pong') return;
    let data; try { data = JSON.parse(event.data); } catch { return; }
    if (data.type !== 'presence' || !Array.isArray(data.sessions)) return;
    state = data; receivedAt = Date.now(); connection.dataset.state = 'live'; connection.textContent = 'En vivo'; render();
  };
  current.onclose = () => {
    if (current !== socket) return;
    clearInterval(heartbeat); disconnected();
    if (!stopped) { retry = setTimeout(connect, backoff + Math.random() * 500); backoff = Math.min(backoff * 2, 30_000); }
  };
  current.onerror = () => current.close();
}
window.addEventListener('pagehide', () => { stopped = true; clearTimeout(retry); clearInterval(heartbeat); const current = socket; socket = null; current?.close(); });
window.addEventListener('pageshow', () => { if (stopped) { stopped = false; connect(); } });
setInterval(render, 1000);
connect();
