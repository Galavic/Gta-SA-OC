// Parsers RenderWare (DFF geometría + TXD texturas) para GTA SA.
// Sin dependencias: funciona en Node (tests) y en el navegador (visor).
// Cobertura MVP: clump > framelist/geometrylist > geometry (verts, normales,
// 1er set UV, tris, prelit) + materiales con nombre de textura; TXD PC con
// DXT1/DXT3/DXT5, RGBA8888/RGB888 y PAL8. Sin skin, sin night-vertex-colors.

const CH = {
  STRUCT: 1, STRING: 2, EXTENSION: 3, TEXTURE: 6, MATERIAL: 7, MATLIST: 8,
  FRAMELIST: 0x0e, GEOMETRY: 0x0f, CLUMP: 0x10, ATOMIC: 0x14,
  TEXDICT: 0x16, NATIVETEX: 0x17, GEOMLIST: 0x1a,
};
const GF = { TRISTRIP: 1, POSITIONS: 2, TEXTURED: 4, PRELIT: 8, NORMALS: 16 };

// Lector de chunks: [{type, size, version, body: DataView, offset}]
export function readChunks(view, start = 0, end = view.byteLength) {
  const out = [];
  let o = start;
  while (o + 12 <= end) {
    const type = view.getUint32(o, true);
    const size = view.getUint32(o + 4, true);
    const version = view.getUint32(o + 8, true);
    if (type === 0 && size === 0) break; // relleno a sector: fin real
    if (o + 12 + size > end + 1) break; // chunk corrupto: parar
    out.push({ type, size, version, body: new DataView(view.buffer, view.byteOffset + o + 12, size) });
    o += 12 + size;
  }
  return out;
}
const find = (chunks, type) => chunks.find((c) => c.type === type);
const children = (c) => readChunks(c.body);

// ---- DFF ----
export function parseDFF(buffer) {
  const view = buffer instanceof DataView ? buffer : new DataView(buffer);
  const root = readChunks(view);
  const clump = find(root, CH.CLUMP);
  if (!clump) throw new Error('DFF sin CLUMP');
  const cl = children(clump);
  const geoms = [];
  const gl = find(cl, CH.GEOMLIST);
  if (gl) for (const g of children(gl).filter((c) => c.type === CH.GEOMETRY)) geoms.push(parseGeometry(g));
  const frames = [];
  const fl = find(cl, CH.FRAMELIST);
  if (fl) {
    const parts = children(fl);
    const st = find(parts, CH.STRUCT)?.body;
    if (st) {
      const count = st.getUint32(0, true);
      if (4 + count * 56 > st.byteLength) throw new Error('FRAMELIST truncado');
      const extensions = parts.filter(p => p.type === CH.EXTENSION);
      for (let i = 0; i < count; i++) {
        const offset = 4 + i * 56;
        const matrix = Array.from({ length: 12 }, (_, j) => st.getFloat32(offset + j * 4, true));
        const name = extensions[i] && find(children(extensions[i]), 0x253f2fe);
        const hanim = extensions[i] && find(children(extensions[i]), 0x11e)?.body;
        const bones = [];
        if (hanim && hanim.byteLength >= 12) {
          const n = hanim.getUint32(8,true);
          for (let j=0; j<n && 20+j*12+12<=hanim.byteLength; j++) bones.push({
            id: hanim.getInt32(20+j*12,true), index: hanim.getUint32(24+j*12,true) });
        }
        frames.push({ matrix, parent: st.getInt32(offset + 48, true),
          name: name ? new TextDecoder().decode(name.body).split('\0')[0] : '',
          boneId: hanim && hanim.byteLength >= 12 ? hanim.getInt32(4,true) : null, bones });
      }
    }
  }
  const atomics = cl.filter(p => p.type === CH.ATOMIC).map(p => {
    const st = find(children(p), CH.STRUCT)?.body;
    if (!st || st.byteLength < 16) throw new Error('ATOMIC truncado');
    return { frame: st.getUint32(0, true), geometry: st.getUint32(4, true), flags: st.getUint32(8, true) };
  });
  return { geometries: geoms, frames, atomics };
}

function parseGeometry(g) {
  const parts = children(g);
  const st = find(parts, CH.STRUCT);
  if (!st) throw new Error('GEOMETRY sin STRUCT');
  const v = st.body;
  let o = 0;
  const flags = v.getUint32(o, true); o += 4;
  const numTris = v.getUint32(o, true); o += 4;
  const numVerts = v.getUint32(o, true); o += 4;
  const numMorphs = v.getUint32(o, true); o += 4;
  // SA es RW 3.6 (chunk 0x1803FFFF): sin bloque ambient/diffuse/specular (<0x34000).
  const NATIVE = 0x01000000;
  let colors = null;
  const uvSets = [];
  const tris = [];
  if (!(flags & NATIVE)) {
    if (flags & GF.PRELIT) {
      colors = new Float32Array(numVerts * 4);
      for (let i = 0; i < numVerts; i++) {
        colors[i * 4] = v.getUint8(o) / 255; colors[i * 4 + 1] = v.getUint8(o + 1) / 255;
        colors[i * 4 + 2] = v.getUint8(o + 2) / 255; colors[i * 4 + 3] = v.getUint8(o + 3) / 255;
        o += 4;
      }
    }
    let sets = (flags >> 16) & 0xff;
    if (sets === 0) sets = (flags & 0x80) ? 2 : ((flags & GF.TEXTURED) ? 1 : 0);
    for (let s = 0; s < sets; s++) {
      const arr = new Float32Array(numVerts * 2);
      // TXD DataTextures retain the native top-to-bottom rows (flipY=false).
      // Keep RenderWare UVs in that same convention; flipping V swaps clothing.
      for (let i = 0; i < numVerts; i++) { arr[i * 2] = v.getFloat32(o, true); arr[i * 2 + 1] = v.getFloat32(o + 4, true); o += 8; }
      uvSets.push(arr);
    }
    for (let i = 0; i < numTris; i++) {
      const v2 = v.getUint16(o, true), v1 = v.getUint16(o + 2, true), mat = v.getUint16(o + 4, true), v3 = v.getUint16(o + 6, true);
      o += 8;
      tris.push(v1, v2, v3, mat);
    }
  }
  // Morph targets (SA: siempre 1): esfera + flags + arrays.
  let positions = null, normals = null;
  for (let m = 0; m < numMorphs; m++) {
    o += 16; // bounding sphere
    const hasVerts = v.getUint32(o, true); o += 4;
    const hasNormals = v.getUint32(o, true); o += 4;
    if (m === 0) {
      if (hasVerts) { positions = new Float32Array(numVerts * 3); for (let i = 0; i < numVerts * 3; i++) { positions[i] = v.getFloat32(o, true); o += 4; } }
      if (hasNormals) { normals = new Float32Array(numVerts * 3); for (let i = 0; i < numVerts * 3; i++) { normals[i] = v.getFloat32(o, true); o += 4; } }
    } else {
      if (hasVerts) o += numVerts * 12;
      if (hasNormals) o += numVerts * 12;
    }
  }
  const materials = [];
  const ml = find(parts, CH.MATLIST);
  if (ml) for (const mc of children(ml).filter((c) => c.type === CH.MATERIAL)) materials.push(parseMaterial(mc));
  const index = new Uint32Array(numTris * 3);
  const matIndex = new Uint16Array(numTris);
  for (let i = 0; i < numTris; i++) { index[i * 3] = tris[i * 4]; index[i * 3 + 1] = tris[i * 4 + 1]; index[i * 3 + 2] = tris[i * 4 + 2]; matIndex[i] = tris[i * 4 + 3]; }
  let skin = null;
  const ext = find(parts,CH.EXTENSION);
  const sk = ext && find(children(ext),0x116)?.body;
  if (sk && sk.byteLength>=4 && !(flags & NATIVE)) {
    const numBones=sk.getUint8(0), used=sk.getUint8(1);
    let p=4+used;
    const indices=new Uint16Array(numVerts*4), weights=new Float32Array(numVerts*4);
    for(let i=0;i<indices.length;i++) indices[i]=sk.getUint8(p++);
    for(let i=0;i<weights.length;i++,p+=4) weights[i]=sk.getFloat32(p,true);
    const inverses=[];
    for(let i=0;i<numBones;i++) {
      if(!used) p+=4;
      const matrix=Array.from({length:16},(_,j)=>sk.getFloat32(p+j*4,true)); p+=64;
      matrix[3]=matrix[7]=matrix[11]=0; matrix[15]=1;
      inverses.push(matrix);
    }
    skin={numBones,indices,weights,inverses};
  }
  return { flags, numVerts, numTris, positions, normals, uvs: uvSets, colors, index, matIndex, materials, skin };
}

function parseMaterial(mc) {
  const parts = children(mc);
  const st = find(parts, CH.STRUCT);
  let color = [1, 1, 1, 1], textured = false;
  // RpMaterial struct: flags u32, color RGBA, unused u32, isTextured u32, ...
  if (st && st.body.byteLength >= 16) {
    const v = st.body;
    textured = v.getUint32(12, true) !== 0;
    color = [v.getUint8(4) / 255, v.getUint8(5) / 255, v.getUint8(6) / 255, v.getUint8(7) / 255];
  }
  let textureName = null;
  const tex = parts.map((p) => p.type === CH.TEXTURE ? p : null).filter(Boolean);
  if (tex.length) {
    const t = readChunks(tex[0].body);
    const nameChunk = t.find((c) => c.type === CH.STRING);
    if (nameChunk) textureName = new TextDecoder().decode(nameChunk.body).split('\0')[0].toLowerCase();
  }
  return { color, textured, textureName };
}

// ---- TXD (PC Direct3D: Raster 0x15 y NativeTexture 0x17) ----
export function parseTXD(buffer) {
  const view = buffer instanceof DataView ? buffer : new DataView(buffer);
  const root = readChunks(view);
  const dict = find(root, CH.TEXDICT);
  if (!dict) throw new Error('TXD sin TEXDICTIONARY');
  const out = [];
  for (const n of children(dict).filter((c) => c.type === 0x15 || c.type === CH.NATIVETEX)) {
    try { out.push(n.type === 0x15 ? parseRaster(n) : parseNative(n)); } catch (e) { out.push({ name: '?', error: String(e) }); }
  }
  return out;
}

// Flags RasterFormat reales (GTAMods): PAL8=0x2000, PAL4=0x4000, MIPMAP=0x8000.
const RF = { F1555: 0x100, F565: 0x200, F4444: 0x300, LUM8: 0x400, F8888: 0x500, F888: 0x600, F555: 0xa00, PAL8: 0x2000, PAL4: 0x4000, MIPMAP: 0x8000 };
const rstr = (v, o, n) => new TextDecoder().decode(new Uint8Array(v.buffer, v.byteOffset + o, n)).split('\0')[0].toLowerCase();

// Raster PC: header de 88 B (platform, filtro, name[32]@8, mask[32]@40,
// rasterFormat@72, d3dFormat@76, w@80, h@82, depth@84, levels@85, flags@87),
// paleta opcional RGBA y niveles con prefijo u32 de tamaño. Solo nivel 0.
function parseRaster(n) {
  const parts = children(n);
  const st = find(parts, CH.STRUCT).body;
  if (st.byteLength < 92) throw new Error('Raster PC truncado');
  const name = rstr(st, 8, 32);
  const rasterFormat = st.getUint32(72, true);
  const fourCC = rstr(st, 76, 4);
  const width = st.getUint16(80, true), height = st.getUint16(82, true);
  const depth = st.getUint8(84);
  const cflags = st.getUint8(87);
  const compressed = (cflags & 8) !== 0 || fourCC.startsWith('dxt');
  let p = 88;
  const base = rasterFormat & 0x0f00;
  let palette = null;
  if (rasterFormat & (RF.PAL8 | RF.PAL4)) {
    const nPal = (rasterFormat & RF.PAL8) ? 256 : 32;
    palette = new Uint8Array(nPal * 4);
    for (let i = 0; i < nPal * 4; i++) palette[i] = st.getUint8(p + i); // RGBA (wiki)
    p += nPal * 4;
  }
  const levelSize = st.getUint32(p, true);
  p += 4;
  if (levelSize > st.byteLength - p) throw new Error('Nivel TXD truncado: ' + name);
  const data = new Uint8Array(st.buffer, st.byteOffset + p, levelSize);
  let rgba;
  if (!compressed) {
    const bpp = depth === 32 ? 4 : depth === 24 ? 3 : depth === 16 ? 2 : depth === 8 ? 1 : depth === 4 ? 0.5 : 4;
    const pitch = Math.ceil(width * bpp / 4) * 4; // filas alineadas a 4 B (D3D)
    if (levelSize < pitch * height) throw new Error('Píxeles TXD truncados: ' + name);
    rgba = decodeRaw(data, width, height, pitch, base, depth, palette);
  } else {
    const blocks = Math.ceil(width / 4) * Math.ceil(height / 4);
    const per = fourCC === 'dxt1' ? 8 : 16;
    if (levelSize < blocks * per) throw new Error('Bloques DXT truncados: ' + name);
    rgba = decodeDXT(data, width, height, fourCC.toUpperCase());
  }
  return { name, width, height, hasAlpha: (cflags & 1) !== 0, rgba };
}

function decodeRaw(data, w, h, pitch, base, depth, palette) {
  const out = new Uint8Array(w * h * 4);
  const px = (x, y) => (y * w + x) * 4;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const o = px(x, y), r = y * pitch + (depth === 4 ? x >> 1 : x * (depth === 32 ? 4 : depth === 16 ? 2 : depth === 24 ? 3 : 1));
    if (palette) {
      const idx = depth === 4 ? ((x % 2 === 0) ? data[r] & 0x0f : data[r] >> 4) : data[r];
      out.set(palette.subarray(idx*4,idx*4+4),o);
    }
    else if (base === RF.F8888) { out[o] = data[r + 2]; out[o + 1] = data[r + 1]; out[o + 2] = data[r]; out[o + 3] = data[r + 3]; }
    else if (base === RF.F888) {
      if (depth === 32) { out[o] = data[r + 2]; out[o + 1] = data[r + 1]; out[o + 2] = data[r]; out[o + 3] = 255; }
      else { out[o] = data[r + 2]; out[o + 1] = data[r + 1]; out[o + 2] = data[r]; out[o + 3] = 255; }
    }
    else if (base === RF.F565 || base === RF.F555 || base === RF.F1555 || base === RF.F4444) {
      const v = data[r] | (data[r + 1] << 8);
      if (base === RF.F565) { out[o] = ((v >> 11) & 31) * 255 / 31 | 0; out[o + 1] = ((v >> 5) & 63) * 255 / 63 | 0; out[o + 2] = (v & 31) * 255 / 31 | 0; out[o + 3] = 255; }
      else if (base === RF.F555) { out[o] = ((v >> 10) & 31) * 255 / 31 | 0; out[o + 1] = ((v >> 5) & 31) * 255 / 31 | 0; out[o + 2] = (v & 31) * 255 / 31 | 0; out[o + 3] = 255; }
      else if (base === RF.F1555) { out[o] = ((v >> 10) & 31) * 255 / 31 | 0; out[o + 1] = ((v >> 5) & 31) * 255 / 31 | 0; out[o + 2] = (v & 31) * 255 / 31 | 0; out[o + 3] = (v >> 15) ? 255 : 0; }
      else { out[o] = ((v >> 8) & 15) * 17; out[o + 1] = ((v >> 4) & 15) * 17; out[o + 2] = (v & 15) * 17; out[o + 3] = ((v >> 12) & 15) * 17; }
    }
    else if (base === RF.LUM8) { const g = data[r]; out[o] = out[o + 1] = out[o + 2] = g; out[o + 3] = 255; }
    else throw new Error(`raster base 0x${base.toString(16)} depth ${depth} sin soporte`);
  }
  return out;
}

function parseNative(n) {
  const parts = children(n);
  const st = find(parts, CH.STRUCT).body;
  let o = 0;
  o += 4; // platformId
  const filterFlags = st.getUint16(o, true); o += 2;
  const hasAlpha = (filterFlags & 1) !== 0;
  const name = new TextDecoder().decode(new Uint8Array(st.buffer, st.byteOffset + o, 32)).split('\0')[0].toLowerCase(); o += 32;
  o += 32; // maskName
  const rasterFormat = st.getUint32(o, true); o += 4;
  const d3dFormat = new TextDecoder().decode(new Uint8Array(st.buffer, st.byteOffset + o, 4)); o += 4;
  const width = st.getUint16(o, true); o += 2;
  const height = st.getUint16(o, true); o += 2;
  const depth = st.getUint8(o); o += 1;
  const mipmaps = st.getUint8(o); o += 1;
  o += 1; // rasterType
  const compression = st.getUint8(o); o += 1;
  const dataChunks = parts.filter((c) => c.type !== CH.STRUCT && c.type !== CH.EXTENSION);
  const palChunk = dataChunks.length > 1 ? dataChunks[0] : null;
  const imgChunk = dataChunks.length > 1 ? dataChunks[1] : dataChunks[0];
  if (!imgChunk) throw new Error('sin datos: ' + name);
  const raw = new Uint8Array(imgChunk.body.buffer, imgChunk.body.byteOffset, imgChunk.body.byteLength);
  const fmt = (rasterFormat & 0x0f00);
  let rgba;
  if (d3dFormat.startsWith('DXT')) rgba = decodeDXT(raw, width, height, d3dFormat);
  else if (fmt === 0x0500) rgba = raw.slice(0, width * height * 4); // 8888
  else if (fmt === 0x0600) { rgba = new Uint8Array(width * height * 4); for (let i = 0; i < width * height; i++) { rgba[i * 4] = raw[i * 3]; rgba[i * 4 + 1] = raw[i * 3 + 1]; rgba[i * 4 + 2] = raw[i * 3 + 2]; rgba[i * 4 + 3] = 255; } }
  else if (fmt === 0x1000 || fmt === 0x2000) { // PAL8/PAL4
    const pal = new Uint8Array(palChunk.body.buffer, palChunk.body.byteOffset, palChunk.body.byteLength);
    const bpp = fmt === 0x1000 ? 1 : 0.5;
    rgba = new Uint8Array(width * height * 4);
    for (let i = 0; i < width * height; i++) {
      const idx = bpp === 1 ? raw[i] : (i % 2 === 0 ? raw[i >> 1] & 0x0f : raw[i >> 1] >> 4);
      rgba[i * 4] = pal[idx * 4]; rgba[i * 4 + 1] = pal[idx * 4 + 1]; rgba[i * 4 + 2] = pal[idx * 4 + 2]; rgba[i * 4 + 3] = pal[idx * 4 + 3];
    }
  } else throw new Error(`formato no soportado ${name}: raster 0x${rasterFormat.toString(16)} d3d=${d3dFormat}`);
  return { name, width, height, hasAlpha, rgba };
}

function decodeDXT(raw, w, h, fourCC) {
  const out = new Uint8Array(w * h * 4);
  const bw = Math.ceil(w / 4), bh = Math.ceil(h / 4);
  let p = 0;
  for (let by = 0; by < bh; by++) for (let bx = 0; bx < bw; bx++) {
    let alphaBlock = null;
    if (fourCC === 'DXT3') { alphaBlock = raw.subarray(p, p + 8); p += 8; }
    else if (fourCC === 'DXT5') { alphaBlock = raw.subarray(p, p + 8); p += 8; }
    else if (fourCC !== 'DXT1') throw new Error('fourcc ' + fourCC);
    const c0 = raw[p] | (raw[p + 1] << 8); const c1 = raw[p + 2] | (raw[p + 3] << 8);
    const bits = raw[p + 4] | (raw[p + 5] << 8) | (raw[p + 6] << 16) | (raw[p + 7] << 24); p += 8;
    const pal = dxtPalette(c0, c1, fourCC === 'DXT1');
    for (let py = 0; py < 4; py++) for (let px = 0; px < 4; px++) {
      const x = bx * 4 + px, y = by * 4 + py;
      if (x >= w || y >= h) continue;
      const ci = (bits >>> (2 * (4 * py + px))) & 3;
      const o = (y * w + x) * 4;
      out[o] = pal[ci * 4]; out[o + 1] = pal[ci * 4 + 1]; out[o + 2] = pal[ci * 4 + 2];
      out[o + 3] = fourCC === 'DXT1' ? pal[ci * 4 + 3] : dxtAlpha(alphaBlock, fourCC, px, py);
    }
  }
  return out;
}
function dxtC(v) { return [(v >> 11) & 31, (v >> 5) & 63, v & 31].map((c, i) => Math.round(c * 255 / (i === 1 ? 63 : 31))); }
function dxtPalette(c0, c1, isDXT1) {
  const a = dxtC(c0), b = dxtC(c1), pal = new Uint8Array(16);
  const set = (i, r, g, bl, al) => { pal[i * 4] = r; pal[i * 4 + 1] = g; pal[i * 4 + 2] = bl; pal[i * 4 + 3] = al; };
  set(0, ...a, 255); set(1, ...b, 255);
  if (c0 > c1 || !isDXT1) { set(2, (2 * a[0] + b[0] + 1) / 3 | 0, (2 * a[1] + b[1] + 1) / 3 | 0, (2 * a[2] + b[2] + 1) / 3 | 0, 255); set(3, (a[0] + 2 * b[0] + 1) / 3 | 0, (a[1] + 2 * b[1] + 1) / 3 | 0, (a[2] + 2 * b[2] + 1) / 3 | 0, 255); }
  else { set(2, (a[0] + b[0] + 1) / 2 | 0, (a[1] + b[1] + 1) / 2 | 0, (a[2] + b[2] + 1) / 2 | 0, 255); set(3, 0, 0, 0, 0); }
  return pal;
}
function dxtAlpha(block, fourCC, px, py) {
  if (fourCC === 'DXT3') { const v = block[(4 * py + px) >> 1]; return ((4 * py + px) % 2 === 0 ? v & 0x0f : v >> 4) * 17; }
  const a0 = block[0], a1 = block[1];
  let bits = 0n;
  for (let i = 0; i < 6; i++) bits |= BigInt(block[2 + i]) << BigInt(8 * i);
  const idx = Number((bits >> BigInt(3 * (4 * py + px))) & 7n);
  const tab = [a0, a1];
  if (a0 > a1) for (let i = 1; i < 7; i++) tab.push(((7 - i) * a0 + i * a1) / 7 | 0);
  else { for (let i = 1; i < 5; i++) tab.push(((5 - i) * a0 + i * a1) / 5 | 0); tab.push(0, 255); }
  return tab[idx];
}
