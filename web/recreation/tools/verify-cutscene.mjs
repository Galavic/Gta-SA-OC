// Installed-source inspection and CPU animation only; no browser fidelity claim.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as THREE from 'three';
import {loadCutscene} from '../public/js/cutscene.mjs';
const nativeFetch=fetch,base=process.env.PREVIEW_URL||'http://127.0.0.1:8084';
globalThis.fetch=(url,options)=>nativeFetch(new URL(url,base),options);
const scene=await loadCutscene('prolog3');assert.equal(scene.actors.length,11);assert(Math.abs(scene.duration-80)<0.001);
const camera=new THREE.PerspectiveCamera(),samples=[],unverifiedDeformations=[];
for(const time of [0,1,5,10,20,40,60,79.9]){
  scene.update(time,camera);assert(camera.position.toArray().every(Number.isFinite));
  const sample={time,actors:[]};
  for(const actor of scene.actors){
    const size=new THREE.Box3().setFromObject(actor.model,true).getSize(new THREE.Vector3()).toArray();
    assert(size.every(Number.isFinite),'Non-finite original actor geometry');
    sample.actors.push({name:actor.animation.name,size});
    if(/csplay|hernandez|pulaski|tenpenny/.test(actor.animation.name)&&Math.max(...size)>4)unverifiedDeformations.push({time,name:actor.animation.name,size});
  }
  samples.push(sample);
}
let airportBlocker=null;try{await loadCutscene('prolog1');}catch(error){airportBlocker=error.message;}
const audio=await fetch('/api/cutscene-audio?scene=prolog3');
const report={scope:'original cutscene asset decoding and experimental CPU binding',policeActorsLoaded:11,cameraDuration:scene.duration,actors:scene.actors.map(a=>({name:a.animation.name,sourceTracks:a.binding.trackCount,reorderedTracks:a.binding.reordered,ignoredTerminalTracks:a.binding.ignoredTerminalTracks})),samples,unverifiedDeformations,airportBlocker,audioStatus:audio.status,audioBlocker:audio.ok?null:await audio.text(),browserGameplayVerified:false,originalMissionVerified:false};
fs.mkdirSync('checks',{recursive:true});fs.writeFileSync('checks/cutscene.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({policeActorsLoaded:report.policeActorsLoaded,duration:report.cameraDuration,unverifiedDeformations,airportBlocker,audioStatus:report.audioStatus,audioBlocker:report.audioBlocker,browserGameplayVerified:false},null,2));
