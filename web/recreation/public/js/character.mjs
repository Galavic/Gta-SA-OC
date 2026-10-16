import * as THREE from 'three';
import { fetchOK } from './assets.mjs';
import { parseIFP } from './ifp.mjs';
import { createCJ } from './cj.mjs';

export async function createCharacter(assets,appearance='CJ') {
  const model=appearance==='CJ'?await createCJ():await assets.model(appearance,appearance);
  if(appearance!=='CJ')assets.protectedKeys.add(model.userData.assetKey);
  const root=new THREE.Group(), conversion=new THREE.Group();
  conversion.rotation.x=-Math.PI/2; conversion.add(model); root.add(conversion);
  const bones=new Map(); model.traverse(obj=>{
    if(obj.isBone&&obj.userData.boneId!==null) bones.set(obj.userData.boneId,obj);
  });
  const {animations}=parseIFP(await (await fetchOK('/api/shared-file?name=ped.ifp')).arrayBuffer());
  if(appearance==='CJ') {
    const bike=parseIFP(await (await fetchOK('/api/img-file?name=bmx.ifp')).arrayBuffer());
    for(const [name,animation] of bike.animations)animations.set(name,animation);
  }
  const mixer=new THREE.AnimationMixer(model), actions=new Map();
  for(const [state,names] of Object.entries({idle:['idle_stance','idle_tired'],walk:['walk_player','walk_civi'],run:['run_player','run_civi'],sprint:['sprint_civi','sprint_panic'],jump:['jump_launch','jump_glide'],ride:['bmx_still'],pedal:['bmx_pedal']})) {
    const animation=names.map(name=>animations.get(name)).find(Boolean);
    if(!animation) continue;
    const tracks=[];
    for(const track of animation.tracks) {
      const bone=bones.get(track.boneId); if(!bone) continue;
      const quaternions=track.rotations.slice();
      // ANP3 rotations match the local DFF bone basis directly.
      for(let i=0;i<quaternions.length;i+=4) {
        const q=new THREE.Quaternion(quaternions[i],quaternions[i+1],quaternions[i+2],quaternions[i+3]).normalize();
        q.toArray(quaternions,i);
      }
      tracks.push(new THREE.QuaternionKeyframeTrack(`${bone.uuid}.quaternion`,track.times,quaternions));
      if(track.positions && track.boneId!==0) tracks.push(new THREE.VectorKeyframeTrack(`${bone.uuid}.position`,track.times,track.positions));
    }
    const clip=new THREE.AnimationClip(state,animation.duration,tracks);
    actions.set(state,mixer.clipAction(clip));
  }
  let current=null;
  function animate(state,dt) {
    const next=actions.get(state)||actions.get('idle');
    if(next && next!==current) {
      next.reset().play();
      if(current) { next.crossFadeFrom(current,0.12,true); }
      current=next;
    }
    mixer.update(dt);
  }
  animate('idle',0.01);
  root.updateMatrixWorld(true);
  model.traverse(obj=>{if(obj.isSkinnedMesh){obj.skeleton.update();obj.computeBoundingBox();}});
  conversion.position.y=-new THREE.Box3().setFromObject(root).min.y;
  return {object:root,animate,bones,mixer,actions};
}
