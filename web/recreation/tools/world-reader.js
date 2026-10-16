'use strict';
const fs = require('fs');
const path = require('path');
const { readImg, extract } = require('./img-reader');

function sections(text, visit) {
  let section = '';
  for (let line of text.split(/\r?\n/)) {
    line = line.replace(/#.*/, '').trim();
    if (!line) continue;
    if (line.toLowerCase() === 'end') { section = ''; continue; }
    if (!line.includes(',')) { section = line.toLowerCase(); continue; }
    visit(section, line.split(',').map(s => s.trim()));
  }
}
function parseIDE(text, definitions, parents) {
  sections(text, (section, f) => {
    if (section === 'txdp') { parents[f[0].toLowerCase()] = f[1].toLowerCase(); return; }
    if (!['objs', 'tobj', 'anim', 'cars', 'peds'].includes(section) || f.length < 3) return;
    const id = Number(f[0]);
    if (!Number.isInteger(id)) return;
    // Older object definitions carry mesh count before their draw distances.
    const old = ['objs', 'tobj'].includes(section) && Number(f[3]) >= 1 && Number(f[3]) <= 3 && f.length >= 6;
    const flagIndex = old ? 4 + Number(f[3]) : 4;
    definitions.set(id, { id, model: f[1].toLowerCase(), txd: f[2].toLowerCase(),
      drawDistance: ['cars', 'peds'].includes(section) ? 150 : Number(f[old ? 4 : 3]) || 150,
      flags: ['cars', 'peds'].includes(section) ? 0 : Number(f[flagIndex]) || 0,
      kind: section });
  });
}
function parseTextIPL(text, source) {
  const instances = [], cars = [];
  sections(text, (section, f) => {
    if (section === 'inst' && f.length >= 11) {
      const nums = f.slice(2).map(Number);
      if (!nums.every(Number.isFinite)) return;
      instances.push({ key: `${source}:${instances.length}`, id: Number(f[0]), interior: nums[0] & 255,
        position: nums.slice(1, 4), rotation: nums.slice(4, 8), lod: nums[8] });
    }
    if (section === 'cars' && f.length >= 5) {
      cars.push({ position: f.slice(0, 3).map(Number), angle: Number(f[3]), id: Number(f[4]) });
    }
  });
  return { instances, cars };
}
function parseBinaryIPL(buffer, source) {
  if (buffer.toString('ascii', 0, 4) !== 'bnry') throw new Error('IPL no binario: ' + source);
  if (buffer.length < 76) throw new Error('Cabecera IPL truncada: ' + source);
  const count = buffer.readUInt32LE(4), offset = buffer.readUInt32LE(28);
  const carCount = buffer.readUInt32LE(20), carOffset = buffer.readUInt32LE(60);
  if (offset + count * 40 > buffer.length || carOffset + carCount * 48 > buffer.length) throw new Error('IPL truncado: ' + source);
  const instances = [], cars = [];
  for (let i = 0; i < count; i++) {
    const o = offset + i * 40;
    instances.push({ key: `${source}:${i}`, position: [0,4,8].map(j => buffer.readFloatLE(o+j)),
      rotation: [12,16,20,24].map(j => buffer.readFloatLE(o+j)), id: buffer.readInt32LE(o+28),
      interior: buffer.readInt32LE(o+32) & 255, lod: buffer.readInt32LE(o+36) });
  }
  for (let i = 0; i < carCount; i++) {
    const o = carOffset + i * 48;
    cars.push({ position: [0,4,8].map(j => buffer.readFloatLE(o+j)), angle: buffer.readFloatLE(o+12), id: buffer.readInt32LE(o+16) });
  }
  return { instances, cars };
}

function readWorld(saRoot) {
  const definitions = new Map(), parents = {}, all = [], cars = [], warnings = [];
  const gtaDat = fs.readFileSync(path.join(saRoot, 'data', 'gta.dat'), 'utf8');
  const files = gtaDat.split(/\r?\n/).map(line => line.replace(/#.*/, '').trim()).filter(Boolean);
  function gameFile(relative) { return path.join(saRoot, ...relative.split(/[\\/]/)); }
  for (const relative of ['data/default.ide', 'data/vehicles.ide', 'data/peds.ide',
      ...files.filter(line => /^IDE\s/i.test(line)).map(line => line.slice(4).trim())]) {
    try { parseIDE(fs.readFileSync(gameFile(relative), 'utf8'), definitions, parents); }
    catch (e) { warnings.push(e.message); }
  }
  for (const line of files.filter(line => /^IPL\s/i.test(line))) {
    const relative = line.slice(4).trim();
    if (!relative.toLowerCase().endsWith('.ipl')) continue;
    const parsed = parseTextIPL(fs.readFileSync(gameFile(relative), 'utf8'), relative.toLowerCase());
    all.push(...parsed.instances); cars.push(...parsed.cars);
  }
  const imgPath = path.join(saRoot, 'models', 'gta3.img');
  const { entries } = readImg(imgPath);
  const available = new Set(entries.map(e => e.name));
  for (const entry of entries.filter(e => e.name.endsWith('.ipl'))) {
    const parsed = parseBinaryIPL(extract(imgPath, entry).data, entry.name);
    all.push(...parsed.instances); cars.push(...parsed.cars);
  }
  const instances = [];
  for (const inst of all) {
    const def = definitions.get(inst.id);
    if (!def || inst.interior !== 0 || /^lod/i.test(def.model) || !available.has(def.model + '.dff')) continue;
    if (!inst.position.every(Number.isFinite) || !inst.rotation.every(Number.isFinite)) continue;
    instances.push({ ...inst, ...def });
  }
  const cells = new Map(), cellSize = 256;
  for (const inst of instances) {
    const key = `${Math.floor(inst.position[0]/cellSize)},${Math.floor(inst.position[1]/cellSize)}`;
    if (!cells.has(key)) cells.set(key, []);
    cells.get(key).push(inst);
  }
  function nearby(x, y, radius = 450) {
    const result = [], range = radius + 350;
    for (let cx = Math.floor((x-range)/cellSize); cx <= Math.floor((x+range)/cellSize); cx++) {
      for (let cy = Math.floor((y-range)/cellSize); cy <= Math.floor((y+range)/cellSize); cy++) {
        for (const inst of cells.get(`${cx},${cy}`) || []) {
          const distance = Math.hypot(inst.position[0]-x, inst.position[1]-y);
          if (distance <= radius + Math.min(inst.drawDistance, 350)) result.push({ ...inst, distance });
        }
      }
    }
    return result.sort((a,b) => a.distance-b.distance);
  }
  return { instances, definitions, parents, cars: cars.filter(c => c.position.every(Number.isFinite)), warnings, nearby,
    stats: { definitions: definitions.size, placements: all.length, exteriorInstances: instances.length,
      binaryFiles: entries.filter(e => e.name.endsWith('.ipl')).length, parkedCars: cars.length } };
}
module.exports = { readWorld, parseIDE, parseTextIPL, parseBinaryIPL };
