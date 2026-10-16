// Índice textura -> archivo .txd (solo nombres, sin decodificar píxeles).
// uso: node tools/txd-index.mjs <gta3.img> [salida.json]
// Tarda minutos la primera vez; el JSON se reutiliza en el visor.
import { writeFileSync } from 'fs';
import reader from './img-reader.js';
const { readImg, extract } = reader;
import { readChunks } from '../public/js/rw.mjs';

const [imgPath, outPath] = [process.argv[2], process.argv[3] || 'tools/txd-index.json'];
const { entries } = readImg(imgPath);
const txds = entries.filter((e) => e.name.endsWith('.txd'));
const index = {};
let done = 0;
for (const e of txds) {
  try {
    const { data, valid } = extract(imgPath, e);
    if (!valid) continue;
    const v = new DataView(data.buffer.slice(data.byteOffset, data.byteOffset + data.length));
    // dict -> hijos: leer solo structs de raster/native para el nombre
    const root = readChunks(v);
    const dict = root.find((c) => c.type === 0x16);
    if (!dict) continue;
    for (const n of readChunks(new DataView(dict.body.buffer, dict.body.byteOffset, dict.body.byteLength))) {
      if (n.type !== 0x15 && n.type !== 0x17) continue;
      const st = readChunks(new DataView(n.body.buffer, n.body.byteOffset, n.body.byteLength)).find((c) => c.type === 1);
      if (!st || st.body.byteLength < 40) continue;
      const at = n.type === 0x15 ? 8 : 6;
      const name = new TextDecoder().decode(new Uint8Array(st.body.buffer, st.body.byteOffset + at, 32)).split('\0')[0].toLowerCase();
      if (name && !index[name]) index[name] = e.name;
    }
  } catch (err) { /* txd roto: saltar */ }
  if (++done % 250 === 0) console.log(`${done}/${txds.length}...`);
}
writeFileSync(outPath, JSON.stringify(index));
console.log(`indexadas ${Object.keys(index).length} texturas de ${txds.length} packs -> ${outPath}`);
