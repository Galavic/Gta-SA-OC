// Visor local: lista del gta3.img + render three.js del DFF con su TXD.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { parseDFF, parseTXD } from './rw.mjs';

const info = document.getElementById('info');
const listEl = document.getElementById('list');
const q = document.getElementById('q');
const view = document.getElementById('view');

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(view.clientWidth, view.clientHeight);
view.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87a5c8);
const camera = new THREE.PerspectiveCamera(60, view.clientWidth / view.clientHeight, 0.1, 2000);
camera.position.set(8, 6, 8);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.5);
sun.position.set(30, 50, 20);
scene.add(sun);
let current = null;
let loadId = 0;

async function fetchOK(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  return response;
}

function disposeGroup(group) {
  group.traverse((obj) => {
    obj.geometry?.dispose();
    if (obj.material) obj.material.dispose();
  });
}

async function loadList() {
  const r = await fetchOK('/api/img-list?ext=.dff&q=' + encodeURIComponent(q.value));
  const { count, shown, files } = await r.json();
  listEl.innerHTML = '';
  info.textContent = `${count} entradas en gta3.img, mostrando ${shown}`;
  for (const f of files) {
    const d = document.createElement('div');
    d.textContent = f;
    d.onclick = () => showModel(f).catch(showError);
    listEl.appendChild(d);
  }
}

let texIndex = null;
const packCache = new Map(); // pack -> {texName: DataTexture}
async function texMap(names) {
  if (!texIndex) texIndex = await (await fetchOK('/api/tex-index')).json();
  const want = [...new Set(names.filter(Boolean))];
  const missing = new Map(); // pack -> true
  for (const n of want) {
    const pack = texIndex[n];
    if (pack && !packCache.has(pack)) missing.set(pack, true);
  }
  for (const pack of missing.keys()) {
    const r = await fetch('/api/img-file?name=' + pack);
    if (!r.ok) continue;
    const texs = parseTXD(await r.arrayBuffer());
    const m = {};
    for (const t of texs) {
      if (t.error || !t.rgba) continue;
      const dt = new THREE.DataTexture(t.rgba, t.width, t.height);
      dt.needsUpdate = true;
      dt.colorSpace = THREE.SRGBColorSpace;
      dt.wrapS = dt.wrapT = THREE.RepeatWrapping;
      m[t.name] = dt;
    }
    packCache.set(pack, m);
  }
  const out = {};
  for (const n of want) {
    const pack = texIndex[n];
    if (pack && packCache.get(pack)?.[n]) out[n] = packCache.get(pack)[n];
  }
  return out;
}

async function showModel(name) {
  const requestId = ++loadId;
  info.textContent = 'cargando ' + name + '...';
  const r = await fetchOK('/api/img-file?name=' + encodeURIComponent(name));
  const { geometries } = parseDFF(await r.arrayBuffer());
  const wantTex = geometries.flatMap((g) => g.materials.map((m) => m.textureName));
  const maps = await texMap(wantTex);
  const group = new THREE.Group();
  let verts = 0, tris = 0;
  for (const g of geometries) {
    if (!g.positions) continue;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(g.positions, 3));
    if (g.normals) geo.setAttribute('normal', new THREE.BufferAttribute(g.normals, 3));
    if (g.uvs?.length) geo.setAttribute('uv', new THREE.BufferAttribute(g.uvs[0], 2));
    if (g.colors) geo.setAttribute('color', new THREE.BufferAttribute(g.colors, 4));
    geo.setIndex(new THREE.BufferAttribute(g.index, 1));
    // Un material por cada material RW con su textura (grupos por material).
    const byMat = new Map();
    for (let i = 0; i < g.matIndex.length; i++) {
      if (!byMat.has(g.matIndex[i])) byMat.set(g.matIndex[i], []);
      byMat.get(g.matIndex[i]).push(g.index[i * 3], g.index[i * 3 + 1], g.index[i * 3 + 2]);
    }
    for (const [mi, idxArr] of byMat) {
      const gg = geo.clone();
      gg.setIndex(idxArr);
      if (!g.normals) gg.computeVertexNormals();
      const mdef = g.materials[mi] || {};
      const map = mdef.textureName && maps ? maps[mdef.textureName] || null : null;
      const mat = new THREE.MeshStandardMaterial({
        map, vertexColors: !!g.colors,
        color: map ? 0xffffff : new THREE.Color(...(mdef.color || [1, 1, 1]).slice(0, 3)),
        roughness: 0.9, metalness: 0, side: THREE.DoubleSide, alphaTest: 0.1,
      });
      group.add(new THREE.Mesh(gg, mat));
    }
    geo.dispose();
    verts += g.numVerts; tris += g.numTris;
  }
  // RenderWare uses Z up; Three.js uses Y up.
  group.rotation.x = -Math.PI / 2;
  const box = new THREE.Box3().setFromObject(group);
  if (box.isEmpty()) { disposeGroup(group); throw new Error('El DFF no contiene geometría visible'); }
  if (requestId !== loadId) { disposeGroup(group); return; }
  const c = box.getCenter(new THREE.Vector3());
  group.position.sub(c);
  if (current) { scene.remove(current); disposeGroup(current); }
  current = group;
  scene.add(group);
  const radius = box.getSize(new THREE.Vector3()).length() / 2;
  const verticalFov = THREE.MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
  const distance = Math.max(radius, 0.1) / Math.sin(Math.min(verticalFov, horizontalFov) / 2) * 1.15;
  camera.near = Math.max(distance / 1000, 0.01);
  camera.far = Math.max(distance * 20, 2000);
  camera.position.copy(new THREE.Vector3(1, 0.65, 1).normalize().multiplyScalar(distance));
  camera.updateProjectionMatrix();
  controls.target.set(0, 0, 0);
  controls.maxDistance = distance * 10;
  controls.update();
  info.textContent = `${name}: ${geometries.length} geometrías, ${verts} verts, ${tris} tris`;
}

function showError(error) {
  info.textContent = 'Error: ' + error.message;
  console.error(error);
}
q.oninput = () => loadList().catch(showError);
addEventListener('resize', () => {
  camera.aspect = view.clientWidth / view.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(view.clientWidth, view.clientHeight);
});
(function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
loadList().then(() => showModel(new URLSearchParams(location.search).get('model') || 'des_farmhouse1_.dff')).catch(showError);
