// Convert this user's original TXD rasters to browser images, without changing
// the installed files. Exports remain local under public/original-ui/.
import fs from 'node:fs';
import path from 'node:path';
import {deflateSync} from 'node:zlib';
import {fileURLToPath} from 'node:url';
import reader from './img-reader.js';
import {parseTXD} from '../public/js/rw.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const installation=process.env.SA_PATH||path.resolve(root,'../../original');
const output=path.join(root,'public/original-ui'); fs.mkdirSync(output,{recursive:true});
const crcTable=Array.from({length:256},(_,i)=>{
  let c=i;for(let j=0;j<8;j++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;return c>>>0;
});
function chunk(name,bytes) {
  const type=Buffer.from(name);let crc=0xffffffff;
  for(const byte of Buffer.concat([type,bytes]))crc=crcTable[(crc^byte)&255]^(crc>>>8);
  const size=Buffer.alloc(4),check=Buffer.alloc(4);size.writeUInt32BE(bytes.length);check.writeUInt32BE((crc^0xffffffff)>>>0);
  return Buffer.concat([size,type,bytes,check]);
}
function png(texture) {
  const {width,height,rgba}=texture;
  const header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=6;
  const rows=Buffer.alloc(height*(width*4+1));
  for(let row=0;row<height;row++)Buffer.from(rgba.buffer,rgba.byteOffset+row*width*4,width*4).copy(rows,row*(width*4+1)+1);
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),chunk('IDAT',deflateSync(rows)),chunk('IEND',Buffer.alloc(0))]);
}
const manifest={source:'Original local GTA textures',textures:{},fontWidths:[],radar:[]};
function exportPack(raw,pack,source) {
  const buffer=raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength);
  for(const texture of parseTXD(buffer)) {
    if(texture.error||!texture.rgba)throw new Error(`${source}: ${texture.error}`);
    const filename=`${pack}-${texture.name}.png`;
    fs.writeFileSync(path.join(output,filename),png(texture));
    manifest.textures[`${pack}/${texture.name}`]={url:'/original-ui/'+filename,width:texture.width,height:texture.height,source};
    if(pack.startsWith('radar'))manifest.radar[Number(pack.slice(5))]='/original-ui/'+filename;
  }
}
for(const name of ['fronten1','fronten2','fronten3','fonts','hud'])exportPack(fs.readFileSync(path.join(installation,'models',name+'.txd')),name,'models/'+name+'.txd');
const imgPath=path.join(installation,'models/gta3.img'),index=reader.readImg(imgPath);
for(const entry of index.entries.filter(entry=>/^radar\d{2,3}\.txd$/.test(entry.name))) {
  exportPack(reader.extract(imgPath,entry).data,entry.name.slice(0,-4),'gta3.img/'+entry.name);
}
let font=-1,reading=false;
for(const original of fs.readFileSync(path.join(installation,'data/fonts.dat'),'utf8').split(/\r?\n/)) {
  const line=original.replace(/#.*/,'').trim();if(!line)continue;
  if(line==='[FONT_ID]'){reading=false;font=-1;continue;}
  if(line==='[PROP]'){reading=true;continue;}
  if(line.startsWith('[')){reading=false;continue;}
  if(font<0&&/^\d+$/.test(line)){font=Number(line);if(font<2)manifest.fontWidths[font]||=[];continue;}
  if(reading&&font<2)manifest.fontWidths[font].push(...line.split(/\s+/).map(Number));
}
if(manifest.fontWidths.length!==2||manifest.fontWidths.some(widths=>widths.length<100))throw new Error('Original font metrics not parsed');
fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2));
console.log(`Exported ${Object.keys(manifest.textures).length} original textures, ${manifest.radar.filter(Boolean).length} radar tiles and original font widths.`);
