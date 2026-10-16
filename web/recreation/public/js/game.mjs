import * as THREE from 'three';
import { AssetStore } from './assets.mjs';
import { WorldStream, GROVE, REGIONS } from './world.mjs';
import { Walker, CarController } from './controller.mjs';
import { createCharacter } from './character.mjs';
import { readSave as loadSaved, writeSave } from './save.mjs';
import { initOriginalUI, drawOriginalHUD, drawOriginalRadar, setOriginalLabel } from './ui.mjs';
import { Mission, START, BIKE_START } from './missions.mjs';
import { OriginalAudio } from './audio.mjs';

const $=id=>document.getElementById(id);
const canvas=$('game'), menu=$('menu'), loading=$('loading'), keys=new Set();
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5)); renderer.setSize(innerWidth,innerHeight);
renderer.outputColorSpace=THREE.SRGBColorSpace;
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x9cbdcf); scene.fog=new THREE.Fog(0x9cbdcf,180,600);
const camera=new THREE.PerspectiveCamera(65,innerWidth/innerHeight,0.08,1400);
const hemisphere=new THREE.HemisphereLight(0xe6f1ff,0x756957,0.95);scene.add(hemisphere);
const sun=new THREE.DirectionalLight(0xffefcf,0.65);sun.position.set(-300,500,200);scene.add(sun);
initOriginalUI().catch(error=>{loading.textContent=error.message;console.error(error);});
const water=new THREE.Mesh(new THREE.PlaneGeometry(16000,16000),new THREE.MeshLambertMaterial({color:0x386579,transparent:true,opacity:0.85}));
water.rotation.x=-Math.PI/2;water.position.y=-0.15;scene.add(water);
const assets=new AssetStore(message=>console.warn(message));
let ready=false,playing=false,region='grove',money=0,minutes=13*60,yaw=0,pitch=0.3,cameraDistance=5.5,lastMouse=0;
let character=null,car=null,inCar=false,dragging=false,noticeUntil=0,pendingJump=false,transitioning=false;
const pedestrians=[];let pedestriansStarted=false;
const originalAudio=new OriginalAudio();
let soundEnabled=true;
$('sound').textContent='Sonido: encendido';
document.addEventListener('pointerdown',()=>originalAudio.unlock().catch(console.warn),{once:true});
document.querySelectorAll('#menu button').forEach(button=>{
  button.addEventListener('pointerenter',()=>originalAudio.context&&originalAudio.effect('highlight'));
  button.addEventListener('focus',()=>originalAudio.context&&originalAudio.effect('highlight'));
  button.addEventListener('click',()=>originalAudio.effect(button.classList.contains('panel-back')?'back':'select'));
});
const mission=new Mission();
const walker=new Walker(new THREE.Vector3(...START));
const marker=new THREE.Mesh(new THREE.CylinderGeometry(3,3,2,32,1,true),new THREE.MeshBasicMaterial({color:0xffdd44,transparent:true,opacity:0.4,side:THREE.DoubleSide,depthWrite:false}));
scene.add(marker);marker.visible=false;
function missionTarget(){return mission.target(car?.controller.position.toArray());}
function missionHUD(){
  const target=missionTarget();
  $('objective').textContent=mission.stage==='complete'?'MISIÓN SUPERADA · El regreso':mission.stage==='failed'?'BMX destruida. Pulsa R para reintentar.':target?'EL REGRESO · '+target.name:'';
  if(target&&car){
    const position=inCar?car.controller.position:walker.position;
    $('objective').textContent+=' ('+Math.round(Math.hypot(position.x-target.position[0],position.z-target.position[2]))+' m)';
    marker.position.set(...target.position);
    const ground=world.ground(marker.position,1.5,8);if(ground!==null)marker.position.y=ground+1;
  }
  marker.visible=Boolean(target);
  $('prompt').style.display=playing&&car&&(inCar||walker.position.distanceTo(car.controller.position)<4)?'block':'none';
  $('prompt').textContent=inCar?(Math.abs(car.controller.speed)<1.5?'F · Bajar de la BMX':'Espacio · Frenar'):'F · Montar BMX';
}
async function restartMission(){
  if(transitioning)return;
  await travel('grove',START);
  if(car.model!=='bmx'){const previous=car;car=await buildCar(new THREE.Vector3(...BIKE_START),'bmx');scene.remove(previous.object);}
  car.controller.position.set(...BIKE_START);car.controller.heading=-Math.PI/2;car.controller.speed=0;car.controller.health=100;
  const ground=world.ground(car.controller.position,30,60);if(ground!==null)car.controller.position.y=ground+0.03;
  mission.start();missionHUD();play();
}
$('restart').onclick=()=>restartMission().catch(fail);
const world=new WorldStream(scene,assets,status=>{
  const text=`${status.loaded} objetos · ${status.completed}/${status.total} cargados${status.failed?' · '+status.failed+' fallos':''}`;
  $('stream').textContent=text;
  if(!ready) loading.textContent='Cargando '+REGIONS[region].name+': '+text;
  // Ground and nearby buildings arrive first. Background loading can continue while playing.
  if(!transitioning && character && car && status.loaded>60 && world.ground(walker.position,15,30)!==null) makeReady();
});

function notice(text) {$('notice').textContent=text;$('notice').style.display='block';noticeUntil=performance.now()+4000;}
function makeReady() {
  if(ready) return;
  ready=true;
  const ground=world.ground(walker.position,15,40);if(ground!==null) walker.position.y=ground+0.04;
  for(const id of ['play','save','travel','change-vehicle','restart']) $(id).disabled=false;
  $('restore').disabled=!readSave();
  loading.textContent='';
  loading.classList.add('hidden');
  if(!pedestriansStarted){pedestriansStarted=true;spawnPedestrians().catch(console.warn);}
}
async function spawnPedestrians(){
  for(const [index,name]of['fam1','fam2','fam3'].entries()){
    const pedestrian=await createCharacter(assets,name);
    const position=GROVE.clone().add(new THREE.Vector3(-4+index*4,0,-3));
    const ground=world.ground(position,40,100);if(ground!==null)position.y=ground+0.04;
    pedestrian.object.position.copy(position);scene.add(pedestrian.object);pedestrians.push(pedestrian);
  }
}
function play() {
  if(!ready) return;
  playing=true;menu.classList.add('hidden');canvas.focus();
  setOriginalLabel($('play'),'REANUDAR');
  try {const request=canvas.requestPointerLock();request?.catch?.(()=>{});}catch{}
  originalAudio.menu(false);
}
function pause() {playing=false;keys.clear();pendingJump=false;menu.classList.remove('hidden');originalAudio.menu(true);if(document.pointerLockElement)document.exitPointerLock();}
$('play').onclick=()=>{if(mission.stage==='idle'){mission.start();notice('El regreso · Encuentra la BMX y vuelve a casa.');}play();};
canvas.addEventListener('click',()=>{if(ready && menu.classList.contains('hidden')) play();});
document.addEventListener('pointerlockchange',()=>{if(!document.pointerLockElement && playing) pause();});
canvas.addEventListener('mousedown',()=>{dragging=true;});addEventListener('mouseup',()=>{dragging=false;});
addEventListener('mousemove',event=>{
  if(!playing || (!document.pointerLockElement&&!dragging))return;
  yaw-=event.movementX*0.0028;pitch=THREE.MathUtils.clamp(pitch+event.movementY*0.0028,-0.2,1.1);
  lastMouse=performance.now();
});
canvas.addEventListener('wheel',event=>{event.preventDefault();cameraDistance=THREE.MathUtils.clamp(cameraDistance+event.deltaY*0.008,2.5,12);},{passive:false});
addEventListener('blur',pause);
addEventListener('keydown',event=>{
  if(event.code==='Escape'){pause();return;}
  if(!playing)return;
  if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','KeyW','KeyA','KeyS','KeyD'].includes(event.code))event.preventDefault();
  keys.add(event.code);
  if(event.repeat)return;
  if(event.code==='KeyF')toggleCar();
  if(event.code==='KeyR'&&mission.stage==='failed')restartMission().catch(fail);
  if(event.code==='Space'&&!inCar)pendingJump=true;
});
addEventListener('keyup',event=>keys.delete(event.code));

async function buildCar(position,name='bmx') {
  const model=await assets.model(name,name);assets.protectedKeys.add(model.userData.assetKey);
  const object=new THREE.Group(), visual=new THREE.Group(), conversion=new THREE.Group();
  conversion.rotation.x=-Math.PI/2;conversion.add(model.clone(true));visual.add(conversion);object.add(visual);
  object.updateMatrixWorld(true);
  const box=new THREE.Box3().setFromObject(visual);visual.position.y=-box.min.y;
  const wheels=[];
  let originalWheel=null;
  conversion.traverse(frame=>{if(frame.name==='wheel'&&!frame.isMesh&&frame.children.some(child=>child.isMesh))originalWheel=frame;});
  if(!originalWheel&&name!=='bmx')throw new Error('El vehículo no contiene su rueda original');
  conversion.traverse(frame=>{
    if(name==='bmx'&&/^wheel_(front|rear)$/.test(frame.name)&&!frame.isMesh){
      wheels.push({object:frame,left:false,front:frame.name==='wheel_front',baseZ:frame.rotation.z});return;
    }
    if(!/^wheel_[lr][fb]_dummy$/.test(frame.name))return;
    let wheel=frame.children.find(child=>child.name==='wheel');
    if(!wheel&&originalWheel){wheel=originalWheel.clone(true);frame.add(wheel);}
    if(!wheel)return;
    const left=frame.name.startsWith('wheel_l');
    if(left)wheel.rotation.z+=Math.PI;
    wheels.push({object:wheel,left,front:/[lr]f_dummy$/.test(frame.name),baseZ:wheel.rotation.z});
  });
  object.updateMatrixWorld(true);
  let seat=null;
  conversion.traverse(frame=>{if(frame.name==='ped_frontseat')seat=object.worldToLocal(frame.getWorldPosition(new THREE.Vector3()));});
  scene.add(object);
  const controller=new CarController(position,name==='bmx'?-Math.PI/2:0,name==='bmx');
  return {object,visual,wheels,seat,controller,model:name,label:name==='bmx'?'BMX':name==='savanna'?'Savanna':'Greenwood'};
}
function toggleCar() {
  if(!car)return;
  if(inCar) {
    if(Math.abs(car.controller.speed)>2){notice('Frena antes de bajar.');return;}
    const right=new THREE.Vector3(Math.cos(car.controller.heading),0,-Math.sin(car.controller.heading));
    const exit=car.controller.position.clone().addScaledVector(right,-2.3);
    if(world.blocked(car.controller.position,new THREE.Vector3().subVectors(exit,car.controller.position),0.3,1.7)) {notice('No hay espacio para salir por este lado.');return;}
    walker.position.copy(exit);walker.velocityY=0;inCar=false;character.object.visible=true;
  } else if(walker.position.distanceTo(car.controller.position)<5) {
    inCar=true;character.object.visible=car.model==='bmx';yaw=car.controller.heading;notice('W / S pedalear y retroceder · A / D girar · Espacio frenar');
  }
}
function respawn() {
  if(mission.active){restartMission().catch(fail);return;}
  const spawn=new THREE.Vector3(...REGIONS[region].position);
  const ground=world.ground(spawn,100,300);
  if(ground===null) {const resume=playing;travel(region).then(()=>{if(resume&&ready)play();}).catch(fail);return;}
  spawn.y=ground+0.04;
  car.controller.position.copy(spawn).add(new THREE.Vector3(-8,0,region==='grove'?-10:0));car.controller.speed=0;car.controller.health=100;
  const carGround=world.ground(car.controller.position,100,300);if(carGround!==null)car.controller.position.y=carGround+0.03;
  walker.position.copy(spawn);walker.velocityY=0;notice('De vuelta al punto de inicio.');
}

function readSave() {
  try{return loadSaved(localStorage,REGIONS);}catch{return null;}
}
function save() {
  const position=inCar?car.controller.position:walker.position;
  const data={region,position:position.toArray(),money,minutes,inCar,mission:mission.serialize(),
    car:{model:car.model,position:car.controller.position.toArray(),heading:car.controller.heading,health:car.controller.health}};
  try {writeSave(localStorage,data);$('restore').disabled=false;notice('Partida guardada en este navegador.');}
  catch{notice('El navegador no permitió guardar la partida.');}
}
$('save').onclick=save;
async function travel(destination,position=null) {
  if(transitioning) return;
  transitioning=true;
  try {
  pause();ready=false;
  for(const id of ['play','save','travel','restore','change-vehicle','restart'])$(id).disabled=true;
  region=destination;$('region').value=region;
  $('region-name').textContent=REGIONS[region].name;
  loading.textContent='Cargando '+REGIONS[region].name+'…';
  world.reset();
  while(world.busy)await new Promise(resolve=>setTimeout(resolve,30));
  inCar=false;character.object.visible=true;
  walker.position.set(...(position||REGIONS[region].position));walker.velocityY=0;
  car.controller.position.copy(walker.position).add(new THREE.Vector3(-8,0,region==='grove'?-10:0));car.controller.speed=0;car.controller.health=100;
  yaw=0;pitch=0.3;
  await world.update(walker.position,true);
  const ground=world.ground(walker.position,50,100);
  if(ground===null) {loading.textContent='No se encontró suelo en este punto. Elige otro destino.';ready=false;$('travel').disabled=false;return;}
  walker.position.y=ground+0.04;
  const carGround=world.ground(car.controller.position,50,100);if(carGround!==null)car.controller.position.y=carGround+0.03;
  makeReady();
  } finally {transitioning=false;}
}
$('travel').onclick=()=>travel($('region').value).catch(fail);
$('restore').onclick=async()=>{
  const data=readSave();if(!data){notice('No hay una partida válida guardada.');return;}
  try {
    await travel(data.region,data.position);
    mission.restore(data.mission);
    money=THREE.MathUtils.clamp(Number(data.money)||0,0,99999999);
    minutes=THREE.MathUtils.clamp(Number(data.minutes)||780,0,1440);
    if(data.car) {
      if(car.model!==data.car.model) {const previous=car;car=await buildCar(new THREE.Vector3(...data.car.position),data.car.model);scene.remove(previous.object);}
      car.controller.position.set(...data.car.position);car.controller.heading=data.car.heading;car.controller.health=data.car.health;car.controller.speed=0;
      $('vehicle').value=car.model;inCar=data.inCar;character.object.visible=!inCar||car.model==='bmx';if(inCar)yaw=car.controller.heading;
    }
    if(ready)play();
  }catch(error){fail(error);}
};
$('distance').onchange=()=>{world.radius=Number($('distance').value);scene.fog.near=world.radius*0.65;scene.fog.far=world.radius+250;world.lastPosition.set(Infinity,0,Infinity);};
$('change-vehicle').onclick=async()=>{
  $('change-vehicle').disabled=true;
  try {
    const previous=car, next=await buildCar(previous.controller.position,$('vehicle').value);
    next.controller.heading=previous.controller.heading;scene.remove(previous.object);car=next;
    notice('Coche preparado: '+car.label);
  }catch(error){notice('No se pudo cargar el coche: '+error.message);}
  finally{$('change-vehicle').disabled=false;}
};
$('sound').onclick=()=>{
  soundEnabled=!soundEnabled;$('sound').textContent='Sonido: '+(soundEnabled?'encendido':'apagado');
  originalAudio.enabled=soundEnabled;
  originalAudio.menu(!playing);
  if(soundEnabled)originalAudio.unlock().catch(console.warn);
};

function updateCamera(dt,instant=false) {
  const position=inCar?car.controller.position:walker.position;
  if(inCar && performance.now()-lastMouse>1200) {
    const difference=Math.atan2(Math.sin(car.controller.heading-yaw),Math.cos(car.controller.heading-yaw));
    yaw+=difference*(1-Math.exp(-2.5*dt));
  }
  const target=position.clone().add(new THREE.Vector3(0,inCar?1.3:1.5,0));
  const distance=inCar?Math.max(8,cameraDistance):cameraDistance;
  const offset=new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch)).multiplyScalar(distance);
  const desired=target.clone().add(offset);
  const ray=world.raycaster;ray.set(target,offset.clone().normalize());ray.far=distance;
  const hit=ray.intersectObjects(world.candidates(target,distance),false)[0];
  if(hit)desired.copy(target).addScaledVector(offset.clone().normalize(),Math.max(0.5,hit.distance-0.2));
  if(instant)camera.position.copy(desired);else camera.position.lerp(desired,1-Math.exp(-12*dt));
  camera.lookAt(target);
}
const mapContext=$('map').getContext('2d');
function drawMap() {
  const position=inCar?car.controller.position:walker.position;
  drawOriginalRadar(mapContext,position,yaw,{inCar,car:car?.controller.position,target:missionTarget()});
}
let previous=performance.now(),accumulator=0,hudTimer=0;
function loop(now) {
  requestAnimationFrame(loop);
  const dt=Math.min((now-previous)/1000,0.05);previous=now;
  if(playing&&ready) {
    accumulator+=dt;
    while(accumulator>=1/60) {
      const currentPosition=inCar?car.controller.position:walker.position;
      if(world.busy && world.ground(currentPosition,15,80)===null) {
        $('stream').textContent='Cargando el suelo de esta zona…';
        accumulator=0;break;
      }
      if(inCar)car.controller.step(1/60,keys,world);
      else {
        const input=new Set(keys);if(!pendingJump)input.delete('Space');
        walker.step(1/60,input,yaw,world);pendingJump=false;
      }
      const event=mission.update(inCar?car.controller.position:walker.position,inCar,1/60,{vehicle:car.model,speed:car.controller.speed,health:car.controller.health});
      if(event?.complete){save();notice('MISIÓN SUPERADA · El regreso');}
      if(event?.failed)notice('BMX destruida · Pulsa R para reintentar.');
      accumulator-=1/60;
    }
    const position=inCar?car.controller.position:walker.position;
    if(position.y< -40)respawn();
    world.update(position).catch(error=>{console.warn(error);$('stream').textContent='Error de carga: '+error.message;});
    minutes=(minutes+dt*0.2)%1440;
  } else accumulator=0;
  if(character) {
    character.object.position.copy(inCar?car.controller.position:walker.position);character.object.rotation.y=inCar?car.controller.heading:walker.heading;
    character.animate(inCar&&car.model==='bmx'?(Math.abs(car.controller.speed)>0.5?'pedal':'ride'):!playing?'idle':!walker.grounded&&!inCar?'jump':walker.moving?(keys.has('ShiftLeft')||keys.has('ShiftRight')?'run':'walk'):'idle',playing?dt:0);
    if(inCar&&car.model==='bmx'&&car.seat&&character.bones.has(1)){
      character.object.updateMatrixWorld(true);
      const pelvis=character.bones.get(1).getWorldPosition(new THREE.Vector3());
      const seat=car.seat.clone().applyAxisAngle(new THREE.Vector3(0,1,0),car.controller.heading).add(car.controller.position);
      character.object.position.add(seat.sub(pelvis));
    }
  }
  if(car) {
    car.object.position.copy(car.controller.position);car.object.rotation.y=car.controller.heading;
    for(const wheel of car.wheels){wheel.object.rotation.x=car.controller.wheelAngle*(wheel.left?-1:1);wheel.object.rotation.z=wheel.baseZ+(wheel.front?car.controller.steer*0.4:0);}
  }
  for(const pedestrian of pedestrians){
    pedestrian.object.visible=region==='grove';
    pedestrian.animate('idle',playing?dt:0);
    if(playing&&region==='grove'){
      const ground=world.ground(pedestrian.object.position,15,40);if(ground!==null)pedestrian.object.position.y=ground+0.04;
      const relative=walker.position.clone().sub(pedestrian.object.position);
      if(relative.length()<15)pedestrian.object.rotation.y=Math.atan2(-relative.x,-relative.z);
    }
  }
  if(character)updateCamera(dt,!ready);
  hudTimer+=dt;
  if(hudTimer>0.15) {
    hudTimer=0;drawMap();missionHUD();
    $('clock').textContent=String(Math.floor(minutes/60)).padStart(2,'0')+':'+String(Math.floor(minutes%60)).padStart(2,'0');
    $('money').textContent='$'+String(Math.floor(money)).padStart(8,'0');
    drawOriginalHUD({clock:$('clock').textContent,money:$('money').textContent});
    $('health').firstElementChild.style.width='100%';
    if(now>noticeUntil)$('notice').style.display='none';
    const daylight=THREE.MathUtils.clamp(Math.sin((minutes/1440-0.25)*Math.PI*2)*1.4,0,1);
    scene.background.set(0x172536).lerp(new THREE.Color(0x9cbdcf),daylight);scene.fog.color.copy(scene.background);
    hemisphere.intensity=0.45+daylight*1.55;sun.intensity=0.12+daylight*1.48;
  }
  renderer.render(scene,camera);
}
requestAnimationFrame(loop);
addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);});
function fail(error) {console.error(error);loading.classList.remove('hidden');loading.textContent='Error: '+error.message;pause();$('travel').disabled=false;}

(async()=>{
  try {
    loading.textContent='Leyendo CJ, animaciones y BMX…';
    [character,car]=await Promise.all([createCharacter(assets),buildCar(new THREE.Vector3(...BIKE_START),'bmx')]);
    scene.add(character.object);updateCamera(0.01,true);
    await world.update(walker.position,true);
    if(world.ground(walker.position,20,50)===null)throw new Error('No se pudo cargar el suelo de Grove Street');
    const ground=world.ground(car.controller.position,20,50);if(ground!==null)car.controller.position.y=ground+0.03;
    makeReady();
  }catch(error){fail(error);}
})();
