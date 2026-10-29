export function startPlayerPresence() {
  let socket, timer, retry, stopped = false, phase = 'loading', backoff = 1000;
  const heartbeat = () => {
    if (socket?.readyState === WebSocket.OPEN)
      socket.send(JSON.stringify({ type: 'heartbeat', phase, visible: document.visibilityState === 'visible' }));
  };
  const connect = () => {
    if (stopped) return;
    const url = new URL('/api/presence/player', location.href);
    url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    let current;
    try { current = socket = new WebSocket(url); } catch { reconnect(); return; }
    current.onopen = () => { if (socket !== current) return; backoff = 1000; heartbeat(); timer = setInterval(heartbeat, 25_000); };
    current.onclose = () => { if (socket !== current) return; clearInterval(timer); reconnect(); };
    current.onerror = () => current.close();
  };
  const reconnect = () => {
    if (!stopped) { retry = setTimeout(connect, backoff + Math.random() * 500); backoff = Math.min(backoff * 2, 30_000); }
  };
  const suspend = () => { stopped = true; clearTimeout(retry); clearInterval(timer); const current = socket; socket = null; current?.close(1000, 'Leaving player'); };
  const resume = () => { if (stopped) { stopped = false; connect(); } };
  document.addEventListener('visibilitychange', heartbeat);
  window.addEventListener('pagehide', suspend);
  window.addEventListener('pageshow', resume);
  connect();
  return {
    markRunning() { phase = 'running'; heartbeat(); },
    stop() {
      suspend();
      document.removeEventListener('visibilitychange', heartbeat);
      window.removeEventListener('pagehide', suspend);
      window.removeEventListener('pageshow', resume);
    },
  };
}
