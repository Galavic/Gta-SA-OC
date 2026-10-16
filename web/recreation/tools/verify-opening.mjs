// Local installed assets and CPU movement. This does not verify browser gameplay.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as THREE from 'three';
import {AssetStore} from '../public/js/assets.mjs';
import {WorldStream} from '../public/js/world.mjs';
import {createCharacter} from '../public/js/character.mjs';
import {CarController,Walker} from '../public/js/controller.mjs';
import {Mission,START,BIKE_START,ROUTE,HOME} from '../public/js/missions.mjs';
const nativeFetch=globalThis.fetch,base=process.env.PREVIEW_URL||'http://127.0.0.1:8084';
globalThis.fetch=(url,options)=>nativeFetch(new URL(url,base),options);
const warnings=[],assets=new AssetStore(w=>warnings.push(w));
const bike=await assets.model('bmx','bmx');assert(bike.children.length);
const rider=await createCharacter(assets);assert(rider.actions.has('ride'));assert(rider.actions.has('pedal'));
for(let i=0;i<60;i++)rider.animate('pedal',1/60);
rider.object.updateMatrixWorld(true);
const size=new THREE.Box3().setFromObject(rider.object,true).getSize(new THREE.Vector3());
assert(size.toArray().every(Number.isFinite));assert(size.y>0.5&&size.y<3.5);
const world=new WorldStream(new THREE.Scene(),assets,()=>{});
await world.update(new THREE.Vector3(...START),true);
const grounds=[START,BIKE_START,...ROUTE.map(p=>p.position),HOME.position].map(p=>{
  const g=world.ground(new THREE.Vector3(...p),1.5,8);assert.notEqual(g,null,'Route ground missing');return g;
});
const controller=new CarController(new THREE.Vector3(...BIKE_START),-Math.PI/2,true);
controller.position.y=grounds[1]+0.03;
const mission=new Mission();mission.start();mission.update(controller.position,true,1/60);
let steps=0;
while(mission.stage==='ride'&&steps<60*180){
  const target=mission.target().position,dx=target[0]-controller.position.x,dz=target[2]-controller.position.z;
  const desired=Math.atan2(-dx,-dz),angle=Math.atan2(Math.sin(desired-controller.heading),Math.cos(desired-controller.heading));
  const keys=new Set();
  if(Math.abs(angle)>0.05)keys.add(angle>0?'KeyA':'KeyD');
  const distance=Math.hypot(dx,dz),last=mission.index===ROUTE.length-1;
  if(last&&distance<8)keys.add('Space');else if(Math.abs(controller.speed)<(Math.abs(angle)>0.4?2:5))keys.add('KeyW');
  controller.step(1/60,keys,world);
  mission.update(controller.position,true,1/60,{speed:controller.speed,health:controller.health});steps++;
}
assert.equal(mission.stage,'home',JSON.stringify({stage:mission.stage,index:mission.index,position:controller.position.toArray(),speed:controller.speed}));
const walker=new Walker(controller.position.clone().add(new THREE.Vector3(-2.3,0,0)));
for(let i=0;i<60*30&&mission.stage==='home';i++){
  const dx=HOME.position[0]-walker.position.x,dz=HOME.position[2]-walker.position.z;
  walker.step(1/60,new Set(['KeyW']),Math.atan2(-dx,-dz),world);
  mission.update(walker.position,false,1/60);
}
assert.equal(mission.stage,'complete','Could not walk from bike to home');
const report={scope:'recreated opening, CPU only',bikeLoaded:true,riderAnimationBounds:size.toArray(),grounds,routeSeconds:steps/60,mission:mission.serialize(),worldObjects:world.loaded.size,failedObjects:world.failed.size,warnings:warnings.slice(0,5),browserGameplayVerified:false};
fs.mkdirSync('checks',{recursive:true});fs.writeFileSync('checks/opening.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
