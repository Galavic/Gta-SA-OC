// Lector de archivos .img v2 de GTA SA (VER2, directorio embebido).
// Entrada de 32 bytes: offset (sectores de 2048) + tamaño + nombre (24B).
// El campo tamaño de SA viene en bytes; si la validación RW falla se
// reinterpreta como sectores. Uso: node tools/img-reader.js <archivo.img> [--extract nombre]
'use strict';
const fs = require('fs');
const path = require('path');

const SECTOR = 2048;
const RW_CLUMP = 0x10;
const RW_TEXDICTIONARY = 0x16;

function readImg(imgPath) {
  const fd = fs.openSync(imgPath, 'r');
  const head = Buffer.alloc(8);
  fs.readSync(fd, head, 0, 8, 0);
  if (head.toString('ascii', 0, 4) !== 'VER2') throw new Error('no es VER2: ' + imgPath);
  const count = head.readUInt32LE(4);
  const entries = [];
  const buf = Buffer.alloc(32);
  for (let i = 0; i < count; i++) {
    fs.readSync(fd, buf, 0, 32, 8 + i * 32);
    const offset = buf.readUInt32LE(0);
    const size = buf.readUInt32LE(4);
    const name = buf.toString('ascii', 8, 32).split('\0')[0].toLowerCase();
    entries.push({ name, offset, size });
  }
  fs.closeSync(fd);
  return { count, entries };
}

// El campo tamaño del .img de SA viene en SECTORES (asignación en disco),
// no en bytes: el tamaño real sale del header del chunk raíz (12 + size).
// Se valida con la firma RenderWare (clump 0x10 o texdict 0x16).
function extract(imgPath, entry) {
  const fd = fs.openSync(imgPath, 'r');
  const head = Buffer.alloc(12);
  fs.readSync(fd, head, 0, 12, entry.offset * SECTOR);
  const magic = head.readUInt32LE(0);
  const claimed = 12 + head.readUInt32LE(4);
  const maxBytes = entry.size * SECTOR;
  const ok = magic === RW_CLUMP || magic === RW_TEXDICTIONARY;
  const n = ok ? Math.min(claimed, maxBytes) : maxBytes;
  const data = Buffer.alloc(n);
  fs.readSync(fd, data, 0, n, entry.offset * SECTOR);
  fs.closeSync(fd);
  return { data, realSize: n, valid: ok };
}

if (typeof require !== 'undefined' && require.main === module) {
  const [, , imgPath, flag, wanted] = process.argv;
  if (!imgPath) { console.error('uso: node tools/img-reader.js <archivo.img> [--list|--extract nombre]'); process.exit(1); }
  const { count, entries } = readImg(imgPath);
  console.log(`entradas: ${count}`);
  if (flag === '--extract' && wanted) {
    const e = entries.find((x) => x.name === wanted.toLowerCase());
    if (!e) { console.error('no encontrado: ' + wanted); process.exit(1); }
    const { data, realSize, valid } = extract(imgPath, e);
    const out = path.join(process.cwd(), e.name);
    fs.writeFileSync(out, data);
    console.log(`extraído ${e.name} (${realSize} B reales, firma ${valid ? 'OK' : 'DUDOSA'}) -> ${out}`);
  } else {
    const dff = entries.filter((e) => e.name.endsWith('.dff')).length;
    const txd = entries.filter((e) => e.name.endsWith('.txd')).length;
    console.log(`.dff: ${dff}, .txd: ${txd}`);
    console.log('primeros 10: ' + entries.slice(0, 10).map((e) => e.name).join(', '));
  }
}

module.exports = { readImg, extract };
