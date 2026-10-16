// Local Three.js recreation; installed game resources are served read-only.
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = +(process.env.PORT || 8084);
const ROOT = path.join(__dirname, 'public');
const DATA = path.join(__dirname, 'data'); // assets de TU copia de SA (gta3.img, etc). No al repo.
// Carpeta de tu GTA SA instalado (solo lectura para el visor local).
const SA_ROOT = process.env.SA_PATH || path.resolve(__dirname, '../../original');
// A complete installed audio source can be read independently without replacing
// any game files. It uses the source installation's own track lookup tables.
const SA_AUDIO_ROOT = process.env.SA_AUDIO_PATH || SA_ROOT;
const { readImg, extract } = require('./tools/img-reader');
const { readWorld } = require('./tools/world-reader');
const cutscenes = require('./tools/cutscene-assets');
let worldCache;
const getWorld = () => worldCache || (worldCache = readWorld(SA_ROOT));
let imgCache = null; // {path, count, entries}
let playerIndex = null;
function getImg() {
  const p = path.join(SA_ROOT, 'models', 'gta3.img');
  if (!imgCache || imgCache.path !== p) imgCache = { path: p, ...readImg(p) };
  return imgCache;
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.wasm': 'application/wasm',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.img': 'application/octet-stream',
  '.dat': 'application/octet-stream',
  '.dff': 'application/octet-stream',
  '.txd': 'application/octet-stream',
  '.col': 'application/octet-stream',
  '.wav': 'audio/wav',
  '.css': 'text/css; charset=utf-8',
  '.ipl': 'text/plain; charset=utf-8',
  '.ide': 'text/plain; charset=utf-8',
};

function send(res, code, body, type) {
  res.writeHead(code, {
    'Content-Type': type || 'text/plain; charset=utf-8',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Cache-Control': 'no-cache',
  });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if(url.pathname.startsWith('/api/cutscene-')) {
    const scene=url.searchParams.get('scene')||'prolog3';
    try {
      if(url.pathname==='/api/cutscene-file')return send(res,200,cutscenes.sceneFile(SA_ROOT,scene,url.searchParams.get('ext')),'application/octet-stream');
      if(url.pathname==='/api/cutscene-model'){
        const bytes=cutscenes.sceneModel(SA_ROOT,(url.searchParams.get('name')||'').toLowerCase());
        return bytes?send(res,200,bytes,'application/octet-stream'):send(res,404,'Modelo ausente');
      }
      if(url.pathname==='/api/cutscene-audio'){
        const bytes=cutscenes.sceneAudio(SA_ROOT,scene,{audioRoot:SA_AUDIO_ROOT});
        return send(res,200,bytes,bytes.toString('ascii',0,4)==='OggS'?'audio/ogg':'audio/mpeg');
      }
      if(url.pathname==='/api/cutscene-audio-status')return send(res,200,JSON.stringify(cutscenes.inspectSceneAudio(SA_ROOT,scene,{audioRoot:SA_AUDIO_ROOT})),'application/json');
      return send(res,404,'Ruta desconocida');
    }catch(error){return send(res,400,error.message);}
  }
  if (url.pathname === '/api/player-file') {
    const name = (url.searchParams.get('name') || '').toLowerCase();
    if (!/^[a-z0-9_.-]+\.(dff|txd)$/.test(name)) return send(res,400,'nombre inválido');
    try {
      const archive = path.join(SA_ROOT,'models','player.img');
      const index = playerIndex || (playerIndex = readImg(archive));
      const entry = index.entries.find(e=>e.name===name);
      if (!entry) return send(res,404,'pieza de CJ no encontrada');
      return send(res,200,extract(archive,entry).data,'application/octet-stream');
    } catch(e) { return send(res,500,e.message); }
  }
  if (url.pathname === '/api/status') {
    return send(res,200,JSON.stringify({mode:'original-assets-reconstruction',
      originalExecutablePort:false,storyImplemented:false,recreatedOpeningMission:true}), 'application/json');
  }
  if (url.pathname === '/api/shared-file') {
    const known = { 'vehicle.txd': ['models','generic','vehicle.txd'], 'ped.ifp': ['anim','ped.ifp'] };
    const relative = known[url.searchParams.get('name')];
    if (!relative) return send(res,404,'archivo desconocido');
    try { return send(res,200,fs.readFileSync(path.join(SA_ROOT,...relative)),'application/octet-stream'); }
    catch(e) { return send(res,500,e.message); }
  }
  if (url.pathname === '/api/world') {
    try {
      const x = Number(url.searchParams.get('x') ?? 2490), y = Number(url.searchParams.get('y') ?? -1670);
      const radius = Math.min(900, Math.max(150, Number(url.searchParams.get('radius') ?? 400)));
      if (![x, y, radius].every(Number.isFinite)) return send(res, 400, 'coordenadas inválidas');
      const world = getWorld();
      const instances = world.nearby(x, y, radius);
      const cars = world.cars.filter(c => Math.hypot(c.position[0]-x, c.position[1]-y) < radius)
        .map(c => ({ ...c, ...world.definitions.get(c.id) })).filter(c => c.model);
      return send(res, 200, JSON.stringify({ instances, cars, stats: world.stats, parents: world.parents, warnings: world.warnings }), 'application/json; charset=utf-8');
    } catch (e) { return send(res, 500, 'world: ' + e.message); }
  }
  if (url.pathname === '/api/model-info') {
    try {
      const name = url.searchParams.get('name') || '';
      const definition = [...getWorld().definitions.values()].find(d => d.model === name.toLowerCase());
      return send(res, definition ? 200 : 404, JSON.stringify(definition || { error: 'modelo desconocido' }), 'application/json; charset=utf-8');
    } catch (e) { return send(res, 500, e.message); }
  }
  // API del visor: lista y extracción del gta3.img (solo lectura, solo tu copia local).
  if (url.pathname === '/api/img-list') {
    try {
      const { count, entries } = getImg();
      const q = (url.searchParams.get('q') || '').toLowerCase();
      const ext = (url.searchParams.get('ext') || '').toLowerCase();
      const list = entries.filter((e) =>
        (!q || e.name.includes(q)) && (!ext || e.name.endsWith(ext))).slice(0, 500)
        .map((e) => e.name);
      return send(res, 200, JSON.stringify({ count, shown: list.length, files: list }), 'application/json; charset=utf-8');
    } catch (e) { return send(res, 500, 'img-list: ' + e.message); }
  }
  if (url.pathname === '/api/img-file') {
    try {
      const name = (url.searchParams.get('name') || '').toLowerCase();
      if (!/^[a-z0-9_.-]+\.(dff|txd|col|ipl|ide|dat|ifp)$/.test(name)) return send(res, 400, 'nombre inválido');
      const { path: p, entries } = getImg();
      const entry = entries.find((e) => e.name === name);
      if (!entry) return send(res, 404, 'no encontrado en gta3.img');
      const { data } = extract(p, entry);
      res.writeHead(200, {
        'Content-Type': 'application/octet-stream',
        'Content-Length': data.length,
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Cross-Origin-Embedder-Policy': 'require-corp',
        'Cache-Control': 'no-cache',
      });
      return res.end(data);
    } catch (e) { return send(res, 500, 'img-file: ' + e.message); }
  }
  if (url.pathname === '/api/tex-index') {
    try {
      const idx = fs.readFileSync(path.join(__dirname, 'tools', 'txd-index.json'));
      return send(res, 200, idx, 'application/json; charset=utf-8');
    } catch (e) { return send(res, 500, 'tex-index: ' + e.message); }
  }
  let file;
  if (url.pathname.startsWith('/data/')) {
    file = path.join(DATA, decodeURIComponent(url.pathname.slice(6)));
  } else {
    let p = decodeURIComponent(url.pathname);
    // Open the reconstructed game, independently of the executable port.
    if (p === '/' || p === '/game.html' || p === '/index.html') p = '/sa.html';
    file = path.join(ROOT, p);
  }
  const resolved = path.resolve(file);
  const allowed = [path.resolve(ROOT), path.resolve(DATA)];
  if (!allowed.some((a) => resolved === a || resolved.startsWith(a + path.sep))) {
    return send(res, 403, 'forbidden');
  }
  fs.stat(resolved, (err, st) => {
    if (err || !st.isFile()) return send(res, 404, 'not found');
    const ext = path.extname(resolved).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Content-Length': st.size,
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Resource-Policy': 'same-origin',
      'Cache-Control': 'no-cache',
    });
    fs.createReadStream(resolved).pipe(res);
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`gtasa-web en http://localhost:${PORT}/ (aislado: COOP/COEP activos)`);
});
