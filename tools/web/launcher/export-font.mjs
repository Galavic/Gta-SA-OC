// Decode only the user's local font textures. Output stays in the ignored site.
import fs from "node:fs";
import path from "node:path";
import { deflateSync } from "node:zlib";
import { parseTXD } from "../../../web/recreation/public/js/rw.mjs";
import { glyphRect } from "../../../web/recreation/public/js/font-layout.mjs";

const [installation, output] = process.argv.slice(2);
fs.mkdirSync(output, { recursive: true });
const crcTable = Array.from({ length: 256 }, (_, i) => {
  let c = i;
  for (let j = 0; j < 8; j++) c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function chunk(name, bytes) {
  const type = Buffer.from(name), length = Buffer.alloc(4), check = Buffer.alloc(4);
  let crc = 0xffffffff;
  for (const byte of Buffer.concat([type, bytes])) crc = crcTable[(crc ^ byte) & 255] ^ (crc >>> 8);
  length.writeUInt32BE(bytes.length); check.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
  return Buffer.concat([length, type, bytes, check]);
}
const raw = fs.readFileSync(path.join(installation, "models/fonts.txd"));
const textures = parseTXD(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength));
for (const texture of textures) {
  if (!/^font[12]$/.test(texture.name)) continue;
  if (!texture.rgba) throw new Error("Could not decode local font " + texture.name);
  const { width, height, rgba } = texture, header = Buffer.alloc(13);
  header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 6;
  const rows = Buffer.alloc(height * (width * 4 + 1));
  for (let y = 0; y < height; y++)
    Buffer.from(rgba.buffer, rgba.byteOffset + y * width * 4, width * 4).copy(rows, y * (width * 4 + 1) + 1);
  fs.writeFileSync(path.join(output, texture.name + ".png"), Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", header),
    chunk("IDAT", deflateSync(rows)), chunk("IEND", Buffer.alloc(0)),
  ]));
}
const widths = [];
let font = -1, reading = false;
for (const original of fs.readFileSync(path.join(installation, "data/fonts.dat"), "utf8").split(/\r?\n/)) {
  const line = original.replace(/#.*/, "").trim();
  if (!line) continue;
  if (line === "[FONT_ID]") { reading = false; font = -1; continue; }
  if (line === "[PROP]") { reading = true; continue; }
  if (line.startsWith("[")) { reading = false; continue; }
  if (font < 0 && /^\d+$/.test(line)) { font = Number(line); if (font < 2) widths[font] ||= []; continue; }
  if (reading && font < 2) widths[font].push(...line.split(/\s+/).map(Number));
}
if (widths.length !== 2 || widths.some(row => row.length < 100)) throw new Error("Invalid local font metrics");
const glyphs = [];
for (let code = 32; code < 384; code++) {
  const character = String.fromCodePoint(code);
  const base = character.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  if (base.length === 1 && base.charCodeAt(0) >= 32 && base.charCodeAt(0) < 127)
    glyphs.push({ code, ...glyphRect(character, 2) });
}
fs.writeFileSync(path.join(output, "metrics.json"), JSON.stringify({ widths, glyphs }));
console.log("Prepared local San Andreas menu fonts");
