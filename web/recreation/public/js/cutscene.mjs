import * as THREE from 'three';
import {AssetStore,fetchOK} from './assets.mjs';
import {parseIFP} from './ifp.mjs';
import {createCJ} from './cj.mjs';

export function parseCUT(text){
  const result={offset:null,models:[],text:[]};let section='';
  for(const raw of text.split('\0')[0].split(/\r?\n/)){
    const line=raw.trim();if(!line)continue;
    if(line==='end'){section='';continue;}
    if(!section){section=line;continue;}
    if(section==='info'&&line.startsWith('offset '))result.offset=line.slice(7).trim().split(/\s+/).map(Number);
    if(section==='model'){
      const [,model,animation]=line.split(',').map(x=>x.trim().toLowerCase());
      if(!model||!animation)throw new Error('Modelo CUT inválido');result.models.push({model,animation});
    }
    if(section==='text'){
      const [start,duration,key]=line.split(',').map(x=>x.trim());result.text.push({start:Number(start),duration:Number(duration),key});
    }
  }
  if(result.offset?.length!==3||!result.offset.every(Number.isFinite)||!result.models.length)throw new Error('CUT inválido');
  return result;
}
export function parseCamera(text){
  const blocks=text.split('\0')[0].split(';').map(s=>s.trim()).filter(Boolean);
  if(blocks.length!==4)throw new Error('Se requieren cuatro canales de cámara');
  const channels=blocks.map((block,i)=>{
    const rows=block.split(/\r?\n/).map(s=>s.trim()).filter(Boolean),count=Number(rows.shift().replace(',',''));
    if(rows.length!==count)throw new Error('Conteo de cámara inválido');
    return rows.map(line=>{
      const row=line.split(',').filter(x=>x.trim()).map(x=>Number(x.replace(/f$/,'')));
      if(row.length!==(i<2?4:10)||!row.every(Number.isFinite))throw new Error('Canal de cámara inválido');
      return {time:row[0],value:row.slice(1)};
    });
  });
  for(const channel of channels)if(channel.some((row,i)=>i&&row.time<channel[i-1].time))throw new Error('Cámara fuera de orden');
  return {channels,duration:Math.max(...channels.map(c=>c.at(-1).time))};
}
export function sampleCamera(channel,time){
  let index=0;while(index+1<channel.length&&channel[index+1].time<=time)index++;
  const a=channel[index],b=channel[Math.min(index+1,channel.length-1)],n=a.value.length/3;
  if(a===b||time<=a.time)return a.value.slice(0,n);
  const u=Math.max(0,Math.min(1,(time-a.time)/(b.time-a.time))),v=1-u;
  return Array.from({length:n},(_,i)=>v*v*v*a.value[i]+3*v*v*u*a.value[2*n+i]+3*v*u*u*b.value[n+i]+u*u*u*b.value[i]);
}
const normalizedName=s=>s.toLowerCase().split(':').at(-1).trim();
function hasRenderInfluence(node,model){
  const descendants=new Set();node.traverse(child=>descendants.add(child));let used=false;
  model.traverse(mesh=>{
    if(!mesh.isMesh)return;
    if(!mesh.isSkinnedMesh){if(descendants.has(mesh))used=true;return;}
    const affected=new Set(mesh.skeleton.bones.flatMap((bone,i)=>descendants.has(bone)?[i]:[]));
    if(!affected.size)return;
    const indices=mesh.geometry.getAttribute('skinIndex'),weights=mesh.geometry.getAttribute('skinWeight');
    for(let i=0;i<indices.array.length;i++)if(weights.array[i]>0&&affected.has(indices.array[i])){used=true;break;}
  });
  return used;
}
export function bindAnimation(model,animation){
  const ids=new Map(),names=new Map();
  model.traverse(node=>{if(node.userData.boneId!==null&&node.userData.boneId!==undefined)ids.set(node.userData.boneId,node);if(node.name&&!node.isMesh)names.set(normalizedName(node.name),node);});
  const tracks=[],missing=[],ignoredTerminalTracks=[],ignoredUnweightedInvalidTracks=[];let reordered=0;
  for(const track of animation.tracks){
    const node=(track.boneId!==null&&track.boneId>=0?ids.get(track.boneId):null)||names.get(normalizedName(track.boneName));
    if(!node){
      // A terminal Nub absent from the source model has no children or skin
      // weights in that model. Keep an explicit audit of those inert channels.
      if(/nub$/i.test(track.boneName.trim()))ignoredTerminalTracks.push(track.boneName);
      else missing.push(track.boneName);
      continue;
    }
    if(track.invalidTransform){
      if(hasRenderInfluence(node,model))throw new Error('Transformación original no finita con influencia visible: '+track.boneName);
      ignoredUnweightedInvalidTracks.push(track.boneName);continue;
    }
    // Preserve every source timestamp/value. Stable ordering is needed by Three;
    // some installed ANPK sequences contain out-of-order exporter keyframes.
    const order=Array.from(track.times.keys()).sort((a,b)=>track.times[a]-track.times[b]);
    if(track.nonMonotonic)reordered++;
    const times=order.map(i=>track.times[i]);
    const quaternions=order.flatMap(i=>new THREE.Quaternion(...track.rotations.subarray(i*4,i*4+4)).normalize().toArray());
    tracks.push(new THREE.QuaternionKeyframeTrack(node.uuid+'.quaternion',times,quaternions));
    if(track.positions)tracks.push(new THREE.VectorKeyframeTrack(node.uuid+'.position',times,order.flatMap(i=>Array.from(track.positions.subarray(i*3,i*3+3)))));
  }
  if(missing.length)throw new Error('Canales originales sin hueso: '+missing.join(', '));
  const mixer=new THREE.AnimationMixer(model),action=mixer.clipAction(new THREE.AnimationClip(animation.name,animation.duration,tracks));
  action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();
  return {mixer,reordered,ignoredTerminalTracks,ignoredUnweightedInvalidTracks,trackCount:animation.tracks.length};
}
export async function loadCutscene(name,onProgress=()=>{}){
  const url=extension=>'/api/cutscene-file?scene='+name+'&ext='+extension;
  const [cut,ifp,dat]=await Promise.all([fetchOK(url('cut')).then(r=>r.text()),fetchOK(url('ifp')).then(r=>r.arrayBuffer()),fetchOK(url('dat')).then(r=>r.text())]);
  const definition=parseCUT(cut),animationData=parseIFP(ifp),camera=parseCamera(dat);
  const store=new AssetStore(console.warn,{archive:'cutscene'}),group=new THREE.Group(),actors=[];
  // GTA adds one unit to the CUT origin before starting actor/camera playback.
  const origin=new THREE.Vector3(definition.offset[0],definition.offset[2]+1,-definition.offset[1]);
  group.position.copy(origin);
  for(const item of definition.models){
    onProgress('Cargando '+item.model+'…');
    const model=item.model==='csplay'?await createCJ({cutscene:true}):await store.loadModel(item.model,item.model);
    const animation=animationData.animations.get(item.animation);if(!animation)throw new Error('Animación original ausente: '+item.animation);
    const binding=bindAnimation(model,animation),conversion=new THREE.Group();conversion.rotation.x=-Math.PI/2;conversion.add(model);group.add(conversion);
    actors.push({model,animation,binding});
  }
  function update(time,view){
    for(const actor of actors)actor.binding.mixer.setTime(Math.min(time,actor.animation.duration));
    const [fov,roll,position,target]=camera.channels.map(channel=>sampleCamera(channel,time));
    view.fov=fov[0];view.up.set(0,1,0);
    view.position.set(position[0],position[2],-position[1]).add(origin);
    view.lookAt(new THREE.Vector3(target[0],target[2],-target[1]).add(origin));
    view.rotateZ(-roll[0]*Math.PI/180);view.updateProjectionMatrix();
    group.updateMatrixWorld(true);
  }
  return {group,origin,definition,camera,actors,update,duration:camera.duration};
}
