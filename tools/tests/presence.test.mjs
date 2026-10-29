import test from 'node:test';
import assert from 'node:assert/strict';
import { PlayerPresence, PRESENCE_TTL } from '../../cloudflare/presence.mjs';
import worker from '../../cloudflare/worker.mjs';

function harness() {
  const sockets = [];
  const ctx = { getWebSockets: role => sockets.filter(s => !role || s.data.role === role),
    storage: { value: null, async getAlarm() { return this.value; }, async setAlarm(value) { this.value = value; } } };
  const add = data => {
    const socket = { data, messages: [], deserializeAttachment() { return this.data; },
      serializeAttachment(value) { this.data = value; }, send(value) { this.messages.push(JSON.parse(value)); },
      close(code) { this.closedCode = code; } };
    sockets.push(socket); return socket;
  };
  return { ctx, add, object: new PlayerPresence(ctx) };
}
const player = (overrides = {}) => ({ role: 'player', id: 'temporary-id', joinedAt: Date.now() - 2000,
  lastSeen: Date.now(), phase: 'loading', visible: true, ...overrides });

test('counts player sockets only; restored attachments survive object hibernation', () => {
  const h = harness(); h.add({ role: 'watch' }); h.add(player());
  const snapshot = new PlayerPresence(h.ctx).snapshot();
  assert.equal(snapshot.total, 1); assert.equal(snapshot.loading, 1);
  assert.deepEqual(Object.keys(snapshot.sessions[0]).sort(), ['id', 'joinedAt', 'lastSeen', 'phase', 'visible']);
});
test('heartbeat updates render/visibility status and broadcasts to watchers', async () => {
  const h = harness(), watch = h.add({ role: 'watch' }), session = h.add(player());
  await h.object.webSocketMessage(session, JSON.stringify({ type: 'heartbeat', phase: 'running', visible: false }));
  assert.equal(watch.messages.at(-1).running, 1); assert.equal(watch.messages.at(-1).sessions[0].visible, false);
  assert.ok(h.ctx.storage.value > Date.now());
  await h.object.webSocketMessage(session, JSON.stringify({ type: 'heartbeat', phase: 'loading', visible: true }));
  assert.equal(session.data.phase, 'running');
});
test('close removes a player immediately even while its socket remains in the context', () => {
  const h = harness(), watch = h.add({ role: 'watch' }), session = h.add(player());
  h.object.webSocketClose(session); assert.equal(watch.messages.at(-1).total, 0);
});
test('lost heartbeats expire and alarm retires stale sessions after hibernation', async () => {
  const h = harness(), watch = h.add({ role: 'watch' }), session = h.add(player({ lastSeen: Date.now() - PRESENCE_TTL - 1 }));
  assert.equal(h.object.snapshot().total, 0); await h.object.alarm();
  assert.equal(session.closedCode, 1001); assert.equal(watch.messages.at(-1).total, 0);
});
test('malformed and oversized player messages close instead of trusting supplied data', async () => {
  const h = harness(), session = h.add(player());
  await h.object.webSocketMessage(session, '{'); assert.equal(session.closedCode, 1008);
  await h.object.webSocketMessage(session, 'x'.repeat(257)); assert.equal(session.closedCode, 1009);
});
test('presence route rejects foreign origins and unsupported methods before forwarding', async () => {
  let calls = 0;
  const env = { LIVE_PLAYERS: { idFromName: x => x, get: () => ({ fetch: async () => { calls++; return Response.json({ total: 0 }); } }) } };
  const url = 'https://gta.galavic.world/api/presence';
  assert.equal((await worker.fetch(new Request(url, { headers: { Origin: 'https://other.example' } }), env)).status, 403);
  assert.equal((await worker.fetch(new Request(url, { method: 'POST' }), env)).status, 405);
  const response = await worker.fetch(new Request(url), env);
  assert.equal(calls, 1); assert.equal(response.headers.get('Cross-Origin-Embedder-Policy'), 'require-corp');
});
