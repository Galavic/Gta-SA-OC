// Ephemeral player sessions. No IP addresses, names or browser fingerprints.
export const PRESENCE_TTL = 90_000;
export class PlayerPresence {
  constructor(ctx) { this.ctx = ctx; }

  sessions(now = Date.now()) {
    return this.ctx.getWebSockets('player').flatMap(socket => {
      const session = socket.deserializeAttachment();
      return session && !session.closed && now - session.lastSeen < PRESENCE_TTL ? [session] : [];
    });
  }

  snapshot(now = Date.now()) {
    const sessions = this.sessions(now).sort((a, b) => a.joinedAt - b.joinedAt);
    return { type: 'presence', at: now, total: sessions.length,
      running: sessions.filter(s => s.phase === 'running').length,
      loading: sessions.filter(s => s.phase === 'loading').length,
      sessions: sessions.map(({ id, joinedAt, lastSeen, phase, visible }) => ({ id, joinedAt, lastSeen, phase, visible })) };
  }

  broadcast() {
    const data = JSON.stringify(this.snapshot());
    for (const socket of this.ctx.getWebSockets('watch')) {
      try { socket.send(data); } catch { /* Disconnected watchers are removed by the runtime. */ }
    }
  }

  async schedule() {
    if (this.sessions().length && await this.ctx.storage.getAlarm() === null)
      await this.ctx.storage.setAlarm(Date.now() + 30_000);
  }

  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (request.method !== 'GET') return new Response('Method not allowed', { status: 405 });
    if (path === '/api/presence') return Response.json(this.snapshot(), { headers: { 'Cache-Control': 'no-store' } });
    const role = path === '/api/presence/player' ? 'player' : path === '/api/presence/watch' ? 'watch' : null;
    if (!role) return new Response('Not found', { status: 404 });
    if (request.headers.get('Upgrade')?.toLowerCase() !== 'websocket') return new Response('WebSocket required', { status: 426 });
    if (this.ctx.getWebSockets().length >= 1500) return new Response('Presence is busy', { status: 503 });
    const [client, server] = Object.values(new WebSocketPair());
    this.ctx.acceptWebSocket(server, [role]);
    const now = Date.now();
    server.serializeAttachment(role === 'player'
      ? { role, id: crypto.randomUUID(), joinedAt: now, lastSeen: now, phase: 'loading', visible: true }
      : { role });
    if (role === 'watch') server.send(JSON.stringify(this.snapshot()));
    else { this.broadcast(); await this.schedule(); }
    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(socket, message) {
    const session = socket.deserializeAttachment();
    if (!session || session.closed) return;
    if (typeof message !== 'string' || message.length > 256) { socket.close(1009, 'Invalid message'); return; }
    if (session.role === 'watch') { if (message === 'ping') socket.send('pong'); return; }
    let update;
    try { update = JSON.parse(message); } catch { socket.close(1008, 'Invalid heartbeat'); return; }
    if (update?.type !== 'heartbeat' || !['loading', 'running'].includes(update.phase) || typeof update.visible !== 'boolean') {
      socket.close(1008, 'Invalid heartbeat'); return;
    }
    const changed = update.phase !== session.phase || update.visible !== session.visible;
    // A rendering session cannot go backwards to loading during the same connection.
    session.phase = session.phase === 'running' ? 'running' : update.phase;
    session.visible = update.visible;
    session.lastSeen = Date.now();
    socket.serializeAttachment(session);
    if (changed) this.broadcast();
    await this.schedule();
  }

  webSocketClose(socket) {
    const session = socket.deserializeAttachment();
    if (session?.role === 'player') {
      socket.serializeAttachment({ ...session, closed: true });
      this.broadcast();
    }
    try { socket.close(1000, 'Closed'); } catch { /* Already closed. */ }
  }

  webSocketError(socket) { this.webSocketClose(socket); }

  async alarm() {
    const now = Date.now();
    for (const socket of this.ctx.getWebSockets('player')) {
      const session = socket.deserializeAttachment();
      if (session && !session.closed && now - session.lastSeen >= PRESENCE_TTL) {
        socket.serializeAttachment({ ...session, closed: true });
        try { socket.close(1001, 'Heartbeat expired'); } catch { /* Already disconnected. */ }
      }
    }
    this.broadcast();
    if (this.sessions().length) await this.ctx.storage.setAlarm(now + 30_000);
  }
}
