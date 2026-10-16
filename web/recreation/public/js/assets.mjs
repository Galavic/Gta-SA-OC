import * as THREE from 'three';
import { computeBoundsTree, acceleratedRaycast } from 'three-mesh-bvh';
import { parseDFF, parseTXD } from './rw.mjs';

THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

export async function fetchOK(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response;
}
export function frameMatrix(m) {
  return new THREE.Matrix4().set(m[0],m[3],m[6],m[9], m[1],m[4],m[7],m[10], m[2],m[5],m[8],m[11], 0,0,0,1);
}
export function buildGeometry(g) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(g.positions, 3));
  if (g.normals) geo.setAttribute('normal', new THREE.BufferAttribute(g.normals, 3));
  if (g.uvs?.length) geo.setAttribute('uv', new THREE.BufferAttribute(g.uvs[0], 2));
  if (g.colors) {
    const colors = new Float32Array(g.numVerts * 3);
    for (let i=0; i<g.numVerts; i++) colors.set(g.colors.subarray(i*4,i*4+3),i*3);
    geo.setAttribute('color', new THREE.BufferAttribute(colors,3));
  }
  const byMaterial = new Map();
  for (let i=0; i<g.numTris; i++) {
    const mi = g.matIndex[i];
    if (!byMaterial.has(mi)) byMaterial.set(mi, []);
    byMaterial.get(mi).push(g.index[i*3],g.index[i*3+1],g.index[i*3+2]);
  }
  const index = [];
  for (const [mi, triangles] of byMaterial) {
    geo.addGroup(index.length,triangles.length,mi);
    for (const vertex of triangles) index.push(vertex);
  }
  geo.setIndex(index);
  if (!g.normals) geo.computeVertexNormals();
  geo.computeBoundingBox();
  geo.computeBoundingSphere();
  geo.computeBoundsTree({ maxLeafTris: 12 });
  return geo;
}

export class AssetStore {
  constructor(onWarning = console.warn,{archive='game'}={}) {
    this.archive=archive;
    this.models = new Map(); this.packs = new Map(); this.onWarning = onWarning;
    this.indexPromise = fetchOK('/api/tex-index').then(r => r.json());
    this.parents = {};
    this.protectedKeys = new Set();
  }
  async pack(name) {
    if (!name) return {};
    name = name.toLowerCase().replace(/\.txd$/, '') + '.txd';
    if (!this.packs.has(name)) {
      const promise = (async () => {
        const response = await fetchOK((name === 'vehicle.txd' ? '/api/shared-file?name=' : this.archive==='cutscene'?'/api/cutscene-model?name=':'/api/img-file?name=') + encodeURIComponent(name));
        const textures = {};
        for (const t of parseTXD(await response.arrayBuffer())) {
          if (t.error || !t.rgba) { this.onWarning(`TXD ${name}: ${t.error}`); continue; }
          const texture = new THREE.DataTexture(t.rgba,t.width,t.height);
          texture.colorSpace = THREE.SRGBColorSpace;
          texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
          texture.magFilter = THREE.LinearFilter;
          texture.minFilter = THREE.LinearMipmapLinearFilter;
          texture.generateMipmaps = true;
          texture.userData.hasAlpha = t.hasAlpha;
          texture.needsUpdate = true;
          textures[t.name] = texture;
        }
        return textures;
      })().catch(error => { this.onWarning(`${name}: ${error.message}`); return {}; });
      this.packs.set(name,promise);
    }
    return this.packs.get(name);
  }
  async textureMaps(names, preferred) {
    const maps = {}, chain = new Set();
    let pack = preferred;
    while (pack && !chain.has(pack)) {
      chain.add(pack);
      const textures = await this.pack(pack);
      for (const name of names) if (!maps[name] && textures[name]) maps[name] = textures[name];
      pack = this.parents[pack];
    }
    const index = await this.indexPromise;
    const missing = [...new Set(names.filter(name => name && !maps[name]).map(name => index[name]).filter(Boolean))];
    for (const packName of missing) {
      const textures = await this.pack(packName);
      for (const name of names) if (!maps[name] && textures[name]) maps[name] = textures[name];
    }
    return maps;
  }
  async model(name, txd) {
    const key = `${name}:${txd || ''}`;
    if (!this.models.has(key)) {
      const pending = this.loadModel(name,txd).catch(error => { this.models.delete(key); throw error; });
      this.models.set(key,pending);
    }
    return this.models.get(key);
  }
  async loadModel(name,txd) {
    const data = parseDFF(await (await fetchOK((this.archive==='cutscene'?'/api/cutscene-model?name=':'/api/img-file?name=') + encodeURIComponent(name + '.dff'))).arrayBuffer());
    const names = [...new Set(data.geometries.flatMap(g => g.materials.map(m => m.textureName)).filter(Boolean))];
    const maps = await this.textureMaps(names,txd);
    if (name === 'greenwoo' || name === 'savanna') {
      const shared = await this.pack('vehicle');
      for (const textureName of names) if (!maps[textureName] && shared[textureName]) maps[textureName] = shared[textureName];
    }
    const skinned = data.geometries.some(g => g.skin);
    const meshes = data.geometries.map(g => {
      if (!g.positions) return null;
      const geometry = buildGeometry(g);
      const materials = g.materials.map(m => {
        const map = maps[m.textureName];
        const primary=(name==='greenwoo'||name==='savanna') && Math.abs(m.color[0]-60/255)<0.01 && m.color[1]===1 && m.color[2]===0;
        const secondary=(name==='greenwoo'||name==='savanna') && m.color[0]===1 && m.color[1]===0 && Math.abs(m.color[2]-175/255)<0.01;
        return new THREE.MeshLambertMaterial({ map: map || null, color: primary?0x44665d:secondary?0xc9c5b6:map ? 0xffffff : new THREE.Color(...m.color.slice(0,3)),
          vertexColors: !!g.colors, side: THREE.DoubleSide,
          alphaTest: map?.userData.hasAlpha ? 0.35 : 0,
          transparent: m.color[3] < 0.95, opacity: m.color[3] });
      });
      const material = materials.length ? materials : new THREE.MeshLambertMaterial({color:0xaaaaaa});
      if (g.skin) {
        geometry.setAttribute('skinIndex',new THREE.BufferAttribute(g.skin.indices,4));
        geometry.setAttribute('skinWeight',new THREE.BufferAttribute(g.skin.weights,4));
        return new THREE.SkinnedMesh(geometry,material);
      }
      return new THREE.Mesh(geometry,material);
    });
    const root = new THREE.Group();
    const frames = data.frames.map(frame => {
      const group = skinned ? new THREE.Bone() : new THREE.Group(); group.name = frame.name;
      group.userData.boneId = frame.boneId;
      group.applyMatrix4(frameMatrix(frame.matrix));
      return group;
    });
    for (let i=0; i<frames.length; i++) {
      const parent = data.frames[i].parent;
      if (parent >= 0 && parent < i) frames[parent].add(frames[i]);
      else root.add(frames[i]);
    }
    if (data.atomics.length) {
      for (const atomic of data.atomics) {
        const mesh = meshes[atomic.geometry]?.clone();
        if (!mesh) continue;
        const frameName = frames[atomic.frame]?.name || '';
        // A vehicle carries damaged alternatives and a far-distance chassis.
        if (/_dam$|_vlo$/.test(frameName)) continue;
        mesh.name = frameName;
        if (mesh.isSkinnedMesh) {
          const skin = data.geometries[atomic.geometry].skin;
          const hierarchy = data.frames.find(f => f.bones.length)?.bones || [];
          const bones = new Array(skin.numBones);
          for (const entry of hierarchy) {
            const frameIndex = data.frames.findIndex(f => f.boneId === entry.id);
            if (frameIndex >= 0 && entry.index < bones.length) bones[entry.index] = frames[frameIndex];
          }
          if (bones.some(b => !b) || bones.filter(Boolean).length !== skin.numBones) throw new Error('Esqueleto DFF incompleto');
          root.add(mesh); root.updateMatrixWorld(true);
          mesh.bind(new THREE.Skeleton(bones,skin.inverses.map(m => new THREE.Matrix4().fromArray(m))),new THREE.Matrix4());
          mesh.normalizeSkinWeights();
          mesh.frustumCulled = false;
        } else (frames[atomic.frame] || root).add(mesh);
      }
    } else for (const mesh of meshes) if (mesh) root.add(mesh);
    root.updateMatrixWorld(true);
    root.userData.assetKey = `${name}:${txd || ''}`;
    root.userData.textureCount = Object.keys(maps).length;
    return root;
  }
  async trim(activeKeys) {
    // Keep nearby models and a modest reusable cache; dispose shared resources once.
    if (this.models.size <= 320) return;
    for (const [key,promise] of this.models) {
      if (this.models.size <= 240) break;
      if (activeKeys.has(key) || this.protectedKeys.has(key)) continue;
      this.models.delete(key);
      const model = await promise.catch(() => null);
      const geometries = new Set(), materials = new Set();
      model?.traverse(obj => {
        if (obj.geometry) geometries.add(obj.geometry);
        for (const material of Array.isArray(obj.material) ? obj.material : obj.material ? [obj.material] : []) materials.add(material);
      });
      for (const geometry of geometries) geometry.dispose();
      for (const material of materials) material.dispose();
    }
    const usedTextures = new Set();
    for (const promise of this.models.values()) {
      const model = await promise.catch(() => null);
      model?.traverse(obj => {
        for (const material of Array.isArray(obj.material) ? obj.material : obj.material ? [obj.material] : []) if (material.map) usedTextures.add(material.map);
      });
    }
    for (const [key,promise] of this.packs) {
      const textures = await promise;
      if (Object.values(textures).some(texture => usedTextures.has(texture))) continue;
      this.packs.delete(key);
      for (const texture of Object.values(textures)) texture.dispose();
    }
  }
}
