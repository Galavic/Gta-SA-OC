import * as THREE from 'three';
import {loadCutscene} from './cutscene.mjs';
import {AssetStore} from './assets.mjs';
import {WorldStream} from './world.mjs';
const $=id=>document.getElementById(id),canvas=$('cinematic');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
const scene=new THREE.Scene();scene.background=new THREE.Color(0x9cbdcf);scene.add(new THREE.HemisphereLight(0xffffff,0x756957,1.5));
const sun=new THREE.DirectionalLight(0xffefcf,1.2);sun.position.set(-300,500,200);scene.add(sun);
const camera=new THREE.PerspectiveCamera(65,1,0.08,1400),assets=new AssetStore(console.warn),world=new WorldStream(scene,assets,()=>{});
const audio=new Audio();audio.preload='auto';let clip=null,active=false,loading=false,audioReady=false,time=0,previous=performance.now();
function resize(){const width=innerWidth,height=canvas.clientHeight;renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();}
addEventListener('resize',resize);resize();
async function load(){
  if(loading)return;loading=true;active=false;audio.pause();$('watch').disabled=true;$('pause').disabled=true;$('scene').disabled=true;
  if(clip){scene.remove(clip.group);clip=null;}
  try{
    const name=$('scene').value;
    clip=await loadCutscene(name,message=>{$('status').textContent=message;});scene.add(clip.group);clip.update(0,camera);
    world.reset();while(world.busy)await new Promise(resolve=>setTimeout(resolve,30));
    $('status').textContent='Cargando escenario…';await world.update(clip.origin,true);
    time=0;
    const response=await fetch('/api/cutscene-audio?scene='+name);audioReady=response.ok;
    if(audioReady){audio.src='/api/cutscene-audio?scene='+name;audio.load();}
    $('watch').textContent=audioReady?'Reproducir':'Ver animaciones sin audio';
    $('status').textContent=audioReady?'Escena cargada · '+Math.round(clip.duration)+' segundos.':await response.text();
    $('watch').disabled=false;
  }catch(error){$('status').textContent='No se pudo cargar la escena original: '+error.message;console.error(error);}
  finally{loading=false;$('scene').disabled=false;}
}
$('scene').onchange=load;
$('watch').onclick=async()=>{
  if(!clip)return;
  try{time=0;if(audioReady){audio.currentTime=0;await audio.play();}active=true;$('pause').disabled=false;$('pause').textContent='Pausar';$('status').textContent=audioReady?'Reproduciendo escena…':'Prueba de animaciones originales sin audio; la introducción completa aún no está lista.';}
  catch(error){$('status').textContent='No se pudo iniciar el audio original: '+error.message;}
};
$('pause').onclick=async()=>{
  if(active){audio.pause();active=false;$('pause').textContent='Continuar';}
  else{try{if(audioReady)await audio.play();active=true;$('pause').textContent='Pausar';}catch(error){$('status').textContent=error.message;}}
};
addEventListener('pagehide',()=>audio.pause());
function loop(now){requestAnimationFrame(loop);const dt=Math.min((now-previous)/1000,0.25);previous=now;if(clip){
  if(active)time=Math.min(audioReady?audio.currentTime:time+dt,clip.duration);clip.update(time,camera);
  if(active&&time>=clip.duration-0.01){audio.pause();active=false;$('pause').disabled=true;$('status').textContent='Fin de la escena. La misión original todavía no está implementada.';}
}renderer.render(scene,camera);}
requestAnimationFrame(loop);load();
