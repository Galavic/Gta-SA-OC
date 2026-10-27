import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../../cloudflare/worker.mjs';

const BUILD = 'build123';
const COOP = 'same-origin';
const COEP = 'require-corp';

function makeEnv(overrides = {}) {
  return {
    RUNTIME_BUILD: BUILD,
    ASSETS: {
      async fetch() {
        return new Response('<html></html>', { headers: { 'Content-Type': 'text/html' } });
      },
    },
    GTA_RUNTIME: {
      async get() {
        return { size: 4, httpEtag: '"etag"', body: 'wasm' };
      },
      async head() {
        return { size: 4, httpEtag: '"etag"' };
      },
    },
    ...overrides,
  };
}

function request(path, init) {
  return new Request(`https://gta.galavic.world${path}`, init);
}

test('redirects plain HTTP to HTTPS before serving anything', async () => {
  const response = await worker.fetch(
    new Request('http://gta.galavic.world/gtasa-singleplayer/?x=1'),
    makeEnv(),
  );
  assert.equal(response.status, 301);
  assert.equal(response.headers.get('Location'), 'https://gta.galavic.world/gtasa-singleplayer/?x=1');
  assert.equal(response.headers.get('Cross-Origin-Opener-Policy'), COOP);
});

test('serves a versioned runtime object with COOP/COEP and immutable caching', async () => {
  const response = await worker.fetch(request(`/runtime/${BUILD}/GTASASingleplayer.wasm`), makeEnv());
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('Content-Type'), 'application/wasm');
  assert.equal(response.headers.get('Cache-Control'), 'public, max-age=31536000, immutable');
  assert.equal(response.headers.get('Cross-Origin-Embedder-Policy'), COEP);
  assert.equal(await response.text(), 'wasm');
});

test('answers HEAD for a runtime object without a body', async () => {
  const response = await worker.fetch(
    request(`/runtime/${BUILD}/GTASASingleplayer.data`, { method: 'HEAD' }),
    makeEnv(),
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('Content-Type'), 'application/octet-stream');
  assert.equal(await response.text(), '');
});

test('rejects unknown builds, unknown runtime names and local endpoints', async () => {
  for (const path of [
    '/runtime/other/GTASASingleplayer.wasm',
    '/runtime/' + BUILD + '/other.bin',
    '/install',
    '/install/file',
    '/log',
    '/seed-manifest',
  ]) {
    const response = await worker.fetch(request(path), makeEnv());
    assert.equal(response.status, 404, path);
    assert.equal(response.headers.get('Cross-Origin-Opener-Policy'), COOP, path);
  }
});

test('rejects non-read methods with Allow', async () => {
  const response = await worker.fetch(request('/', { method: 'POST' }), makeEnv());
  assert.equal(response.status, 405);
  assert.equal(response.headers.get('Allow'), 'GET, HEAD');
});

test('passes static assets through with the isolation headers', async () => {
  const response = await worker.fetch(request('/menu.css'), makeEnv());
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('Content-Type'), 'text/html');
  assert.equal(response.headers.get('Cross-Origin-Opener-Policy'), COOP);
  assert.equal(response.headers.get('Cross-Origin-Embedder-Policy'), COEP);
});

function hostedEnv() {
  const env = makeEnv({ GAME_BUILD: "hosted" });
  const keys = [];
  env.ASSETS.fetch = async () => Response.json({ build: "hosted", entries: [
    { path: "sound.dll", size: 4 },
    { path: "models/world.img", size: 8, chunks: [{ path: "__chunks/hash/0000", size: 4 }] },
  ] });
  env.GTA_RUNTIME.get = async key => { keys.push(key); return { size: 4, httpEtag: '"game"', body: "data" }; };
  env.GTA_RUNTIME.head = async key => { keys.push(key); return { size: 4, httpEtag: '"game"' }; };
  return { env, keys };
}
test('hosted game streams only inventoried files and transfer chunks', async () => {
  const { env, keys } = hostedEnv();
  for (const path of ['sound.dll', '__chunks/hash/0000']) {
    const r = await worker.fetch(request('/game/hosted/' + path), env);
    assert.equal(r.status, 200);
    assert.equal(await r.text(), 'data');
    assert.equal(r.headers.get('Cross-Origin-Embedder-Policy'), COEP);
  }
  assert.deepEqual(keys, ['game/hosted/sound.dll', 'game/hosted/__chunks/hash/0000']);
});
test('hosted game rejects unknown builds, unlisted files and unchunked archive URLs', async () => {
  const { env, keys } = hostedEnv();
  for (const path of ['/game/other/sound.dll', '/game/hosted/save.b', '/game/hosted/models/world.img',
    '/game/hosted/%2e%2e%2fsound.dll', '/game/hosted/%FF']) {
    assert.equal((await worker.fetch(request(path), env)).status, 404, path);
  }
  assert.equal(keys.length, 0);
});
test('hosted HEAD checks object size without downloading and handles missing objects', async () => {
  const { env } = hostedEnv();
  const r = await worker.fetch(request('/game/hosted/sound.dll', { method: 'HEAD' }), env);
  assert.equal(r.status, 200);
  assert.equal(await r.text(), '');
  env.GTA_RUNTIME.get = async () => null;
  assert.equal((await worker.fetch(request('/game/hosted/sound.dll'), env)).status, 503);
});

test('hosted byte ranges use bounded R2 reads and return the original object size', async () => {
  const { env } = hostedEnv();
  let options;
  env.GTA_RUNTIME.get = async (key, value) => {
    options = value;
    return { size: 4, httpEtag: '"game"', body: 'at' };
  };
  const r = await worker.fetch(request('/game/hosted/sound.dll', { headers: { Range: 'bytes=1-2' } }), env);
  assert.equal(r.status, 206);
  assert.deepEqual(options, { range: { offset: 1, length: 2 } });
  assert.equal(r.headers.get('Content-Range'), 'bytes 1-2/4');
  assert.equal(r.headers.get('Content-Length'), '2');
  assert.equal(r.headers.get('Accept-Ranges'), 'bytes');
  assert.equal(r.headers.get('Cross-Origin-Embedder-Policy'), COEP);
  assert.equal(await r.text(), 'at');
});
test('invalid hosted byte ranges are rejected before R2 is touched', async () => {
  const { env, keys } = hostedEnv();
  for (const range of ['bytes=0-4', 'bytes=3-1', 'bytes=-2', 'bytes=0-1,2-3', 'bytes=0-9007199254740992']) {
    const r = await worker.fetch(request('/game/hosted/sound.dll', { headers: { Range: range } }), env);
    assert.equal(r.status, 416, range);
    assert.equal(r.headers.get('Content-Range'), 'bytes */4');
  }
  assert.equal(keys.length, 0);
});
