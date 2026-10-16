// Bitmap glyphs, interface sprites and radar tiles come from the local game.
import {fontKey,glyph,glyphRect} from './font-layout.mjs';
const images=new Map(),tints=new Map();let manifest=null,ready=false;
const loadImage=url=>new Promise((resolve,reject)=>{
  const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('No se pudo cargar '+url));image.src=url;
});
function tinted(font,color) {
  const key=font+':'+color;if(tints.has(key))return tints.get(key);
  const original=images.get(fontKey(font));if(!original)return null;
  const canvas=document.createElement('canvas');canvas.width=original.width;canvas.height=original.height;
  const ctx=canvas.getContext('2d');ctx.drawImage(original,0,0);ctx.globalCompositeOperation='source-in';ctx.fillStyle=color;ctx.fillRect(0,0,canvas.width,canvas.height);
  tints.set(key,canvas);return canvas;
}
function width(text,font,size,style=2) {
  return [...text].reduce((sum,char)=>sum+(manifest.fontWidths[font]?.[glyph(char,style)]||16)*size/40,0);
}
function text(ctx,label,x,y,{font=0,style=2,size=32,color='#fff',align='left',outline=2}={}) {
  if(!ready)return;
  const measure=width(label,font,size,style);if(align==='right')x-=measure;if(align==='center')x-=measure/2;
  const draw=(atlas,dx,dy)=>{
    let cursor=x;
    for(const character of label){const cell=glyphRect(character,style);if(character!==' ')ctx.drawImage(atlas,cell.x,cell.y,cell.width,cell.height,cursor+dx,y+dy,size*32/40,size*cell.height/40);cursor+=(manifest.fontWidths[font]?.[cell.id]||16)*size/40;}
  };
  if(outline){const black=tinted(font,'#000');for(const [dx,dy]of[[-outline,0],[outline,0],[0,-outline],[0,outline],[-outline,-outline],[outline,outline]])draw(black,dx,dy);}
  draw(tinted(font,color),0,0);
}
function label(element) {
  const value=element.dataset.label||element.textContent.trim();element.dataset.label=value;
  const size=Number(element.dataset.size||34),font=Number(element.dataset.font||0),style=Number(element.dataset.style??2);
  const canvas=document.createElement('canvas');const ratio=Math.min(devicePixelRatio||1,2);
  const w=Math.ceil(width(value,font,size,style)+10),h=size+12;
  canvas.width=w*ratio;canvas.height=h*ratio;canvas.style.width=w+'px';canvas.style.height=h+'px';canvas.setAttribute('aria-hidden','true');
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);
  text(ctx,value,5,4,{font,style,size,color:element.dataset.color||'#ddd5bf'});
  element.setAttribute('aria-label',value);element.replaceChildren(canvas);
}
export async function initOriginalUI() {
  const response=await fetch('/original-ui/manifest.json');if(!response.ok)throw new Error('Interfaz original no disponible');manifest=await response.json();
  await Promise.all(['fonts/font1','fonts/font2','hud/fist','hud/radardisc','hud/radar_centre','hud/radar_north'].map(async key=>{
    images.set(key,await loadImage(manifest.textures[key].url));
  }));
  ready=true;
  for(const element of document.querySelectorAll('[data-original-label]'))label(element);
  // Radar images load in the background while the nearby world is streamed.
  Promise.all(manifest.radar.map(async(url,index)=>{if(url)images.set('radar'+index,await loadImage(url));}))
    .then(()=>drawFullMap()).catch(console.warn);
  const options=document.getElementById('options-panel'),map=document.getElementById('map-panel');
  document.getElementById('options-toggle').onclick=()=>{options.classList.toggle('hidden');map.classList.add('hidden');};
  document.getElementById('map-toggle').onclick=()=>{map.classList.toggle('hidden');options.classList.add('hidden');drawFullMap();};
  for(const button of document.querySelectorAll('.panel-back'))button.onclick=()=>{options.classList.add('hidden');map.classList.add('hidden');};
  document.getElementById('exit-menu').onclick=()=>{
    document.getElementById('loading').textContent='Puedes cerrar esta pestaña para salir.';
  };
  addEventListener('keydown',event=>{
    if(document.getElementById('menu').classList.contains('hidden'))return;
    if(event.code==='Escape'){options.classList.add('hidden');map.classList.add('hidden');return;}
    if(!['ArrowDown','ArrowUp'].includes(event.code)||!options.classList.contains('hidden')||!map.classList.contains('hidden'))return;
    event.preventDefault();const buttons=[...document.querySelectorAll('.menu-buttons button:not(:disabled)')].filter(button=>button.offsetParent!==null);
    const current=buttons.indexOf(document.activeElement),delta=event.code==='ArrowDown'?1:-1;
    buttons[(current+delta+buttons.length)%buttons.length]?.focus();
  });
}
export function setOriginalLabel(element,value){element.dataset.label=value;if(ready)label(element);else element.textContent=value;}
function drawFullMap() {
  const canvas=document.getElementById('full-map'),ctx=canvas.getContext('2d');ctx.fillStyle='#59829a';ctx.fillRect(0,0,canvas.width,canvas.height);
  for(let index=0;index<144;index++){const image=images.get('radar'+index);if(image)ctx.drawImage(image,(index%12)*64,Math.floor(index/12)*64,64,64);}
}
export function drawOriginalRadar(ctx,position,yaw,{car=null,target=null,inCar=false}={}) {
  if(!ready)return false;
  // Original 12x12 atlas spans -3000..3000 in game X/Y. Three's Z is -Y.
  ctx.clearRect(0,0,336,336);ctx.save();ctx.beginPath();ctx.arc(168,168,159,0,Math.PI*2);ctx.clip();
  ctx.fillStyle='#5a7a86';ctx.fillRect(0,0,336,336);ctx.translate(168,168);ctx.rotate(yaw);
  const scale=1.2;
  const column=Math.floor((position.x+3000)/500),row=Math.floor((position.z+3000)/500);
  for(let y=Math.max(0,row-1);y<=Math.min(11,row+1);y++)for(let x=Math.max(0,column-1);x<=Math.min(11,column+1);x++){
    const image=images.get('radar'+(y*12+x));if(image)ctx.drawImage(image,(x*500-3000-position.x)*scale,(y*500-3000-position.z)*scale,500*scale,500*scale);
  }
  if(target){ctx.fillStyle='#ffef4b';ctx.beginPath();ctx.arc((target.position[0]-position.x)*scale,(target.position[2]-position.z)*scale,7,0,Math.PI*2);ctx.fill();}
  if(car&&!inCar){ctx.fillStyle='#67b8ff';ctx.fillRect((car.x-position.x)*scale-4,(car.z-position.z)*scale-4,8,8);}
  const north=images.get('hud/radar_north');if(north)ctx.drawImage(north,-9,-142,18,18);
  ctx.restore();
  // The original raster is one corner, mirrored into the other three.
  const disc=images.get('hud/radardisc');
  if(disc)for(const [sx,sy]of[[1,1],[-1,1],[1,-1],[-1,-1]]){ctx.save();ctx.translate(168,168);ctx.scale(sx,sy);ctx.drawImage(disc,-168,-168,168,168);ctx.restore();}
  const centre=images.get('hud/radar_centre');if(centre)ctx.drawImage(centre,151,151,34,34);
  return true;
}
export function drawOriginalHUD({clock,money}) {
  if(!ready)return;
  const canvas=document.getElementById('hud-numbers'),ratio=Math.min(devicePixelRatio||1,2);
  if(canvas.width!==340*ratio){canvas.width=340*ratio;canvas.height=190*ratio;}
  const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,340,190);
  text(ctx,clock,320,4,{font:1,style:1,size:38,align:'right',color:'#ddd5bd',outline:3});
  text(ctx,money,320,117,{font:1,style:1,size:31,align:'right',color:'#5da566',outline:3});
  ctx.drawImage(images.get('hud/fist'),246,47,75,75);
}
