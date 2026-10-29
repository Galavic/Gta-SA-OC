/** Serve the launcher and stream versioned runtime artifacts from private R2. */
export { PlayerPresence } from './presence.mjs';
const GAME = 'GTASASingleplayer';
const files = new Map([[`${GAME}.wasm`, 'application/wasm'], [`${GAME}.data`, 'application/octet-stream']]);
const security = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
  'Cross-Origin-Resource-Policy': 'same-origin',
  'X-Content-Type-Options': 'nosniff',
};
function secured(response, precompressed = false) {
  const headers = new Headers(response.headers);
  for (const [key, value] of Object.entries(security)) headers.set(key, value);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers,
    encodeBody: precompressed ? 'manual' : 'automatic' });
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    // The custom domain is served over both schemes; force HTTPS so the page
    // always boots in the secure context required for SharedArrayBuffer.
    if (url.protocol === 'http:') {
      url.protocol = 'https:';
      return secured(new Response(null, { status: 301, headers: { Location: url.href } }));
    }
    if (url.pathname === '/api/presence' || url.pathname.startsWith('/api/presence/')) {
      if (request.method !== 'GET') return secured(new Response('Method not allowed', { status: 405 }));
      if (request.headers.has('Origin') && request.headers.get('Origin') !== url.origin)
        return secured(new Response('Forbidden', { status: 403 }));
      if (!env.LIVE_PLAYERS) return secured(new Response('Presence unavailable', { status: 503 }));
      const response = await env.LIVE_PLAYERS.get(env.LIVE_PLAYERS.idFromName('gtasa-live-v1')).fetch(request);
      // A WebSocket upgrade must retain its platform-owned socket.
      return response.status === 101 ? response : secured(response);
    }
    if (request.method !== 'GET' && request.method !== 'HEAD')
      return secured(new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } }));
    if (url.pathname.startsWith('/game/')) {
      let path;
      try { path = decodeURIComponent(url.pathname); }
      catch { return secured(new Response('Not found', { status: 404 })); }
      const prefix = `/game/${env.GAME_BUILD}/`;
      if (!env.GAME_BUILD || !path.startsWith(prefix))
        return secured(new Response('Not found', { status: 404 }));
      const relative = path.slice(prefix.length);
      const inventoryResponse = await env.ASSETS.fetch(new Request(new URL('/game-assets.json', url)));
      if (!inventoryResponse.ok) return secured(new Response('Game inventory unavailable', { status: 503 }));
      const inventory = await inventoryResponse.json();
      const entry = inventory.build === env.GAME_BUILD && inventory.entries
        .flatMap(file => file.chunks || [file]).find(file => file.path === relative);
      if (!entry) return secured(new Response('Not found', { status: 404 }));
      const key = `game/${env.GAME_BUILD}/${relative}`;
      // Bounded ranges let the importer verify/download several small blocks
      // concurrently without buffering multi-gigabyte archives in the browser.
      let range;
      if (request.method === 'GET' && request.headers.has('Range')) {
        const match = /^bytes=(\d+)-(\d+)$/.exec(request.headers.get('Range'));
        const start = match && Number(match[1]), end = match && Number(match[2]);
        if (!match || !Number.isSafeInteger(start) || !Number.isSafeInteger(end) ||
            start > end || end >= entry.size)
          return secured(new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${entry.size}` } }));
        range = { offset: start, length: end - start + 1 };
      }
      const object = request.method === 'HEAD'
        ? await env.GTA_RUNTIME.head(key) : await env.GTA_RUNTIME.get(key, range ? { range } : undefined);
      if (!object || object.size !== entry.size)
        return secured(new Response('Game file unavailable', { status: 503 }));
      const headers = new Headers({
        'Content-Type': 'application/octet-stream',
        'Content-Length': String(range ? range.length : object.size),
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'public, max-age=31536000, immutable',
        'ETag': object.httpEtag,
      });
      if (!range && request.headers.get('If-None-Match') === object.httpEtag)
        return secured(new Response(null, { status: 304, headers }));
      if (range) headers.set('Content-Range', `bytes ${range.offset}-${range.offset + range.length - 1}/${object.size}`);
      return secured(new Response(request.method === 'HEAD' ? null : object.body, { status: range ? 206 : 200, headers }));
    }
    if (url.pathname.startsWith('/runtime/')) {
      const parts = url.pathname.split('/');
      if (parts.length !== 4 || parts[2] !== env.RUNTIME_BUILD || !files.has(parts[3]))
        return secured(new Response('Not found', { status: 404 }));
      // Cloudflare can normalize the header sent to Workers. Negotiate against
      // the client's original value when the platform supplies it.
      const accepted = request.cf?.clientAcceptEncoding ?? request.headers.get('Accept-Encoding') ?? '';
      const acceptsGzip = accepted.split(',').some(part => {
        const [encoding, ...parameters] = part.trim().toLowerCase().split(';');
        const q = parameters.find(value => value.trim().startsWith('q='));
        return encoding === 'gzip' && (!q || Number(q.trim().slice(2)) > 0);
      });
      let gzip = env.RUNTIME_GZIP === '1' && acceptsGzip;
      const key = `${env.RUNTIME_BUILD}/${parts[3]}`;
      // Keep the R2 body as a stream: never buffer the large Wasm inside a Worker.
      const read = name => request.method === 'HEAD' ? env.GTA_RUNTIME.head(name) : env.GTA_RUNTIME.get(name);
      let object = await read(key + (gzip ? '.gz' : ''));
      if (!object && gzip) { gzip = false; object = await read(key); }
      if (!object) return secured(new Response('Runtime unavailable', { status: 503 }));
      const headers = new Headers({
        'Content-Type': files.get(parts[3]),
        'Content-Length': String(object.size),
        'Cache-Control': 'public, max-age=31536000, immutable',
        'ETag': object.httpEtag,
      });
      headers.set('Vary', 'Accept-Encoding');
      if (gzip) headers.set('Content-Encoding', 'gzip');
      if (request.headers.get('If-None-Match') === object.httpEtag)
        return secured(new Response(null, { status: 304, headers }), gzip);
      return secured(new Response(request.method === 'HEAD' ? null : object.body, { headers }), gzip);
    }
    if (url.pathname === '/install' || url.pathname.startsWith('/install/') ||
        url.pathname === '/seed-manifest' || url.pathname === '/log')
      return secured(new Response('Not found', { status: 404 }));
    return secured(await env.ASSETS.fetch(request));
  },
};
