import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {parseIFP} from '../public/js/ifp.mjs';
import {parseCUT,parseCamera,sampleCamera,bindAnimation} from '../public/js/cutscene.mjs';
import assets from '../tools/cutscene-assets.js';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
function chunk(tag,bytes){
  const b=Buffer.alloc(8+Math.ceil(bytes.length/4)*4);b.write(tag);b.writeUInt32LE(bytes.length,4);bytes.copy(b,8);return b;
}
function animationFixture(){
  const anim=Buffer.alloc(44);anim.write('root');anim.writeUInt32LE(3,28);
  const frames=Buffer.alloc(96);[0,2,1].forEach((time,i)=>{
    frames.writeFloatLE(0.5,i*32);frames.writeFloatLE(0.5,i*32+12);
    frames.writeFloatLE(12+i,i*32+16);frames.writeFloatLE(time,i*32+28);
  });
  const seq=chunk('CPAN',Buffer.concat([chunk('ANIM',anim),chunk('KRT0',frames)]));
  const info=Buffer.alloc(8);info.writeUInt32LE(1);
  const rootInfo=Buffer.alloc(8);rootInfo.writeUInt32LE(1);rootInfo.write('TEST',4);
  return chunk('ANPK',Buffer.concat([chunk('INFO',rootInfo),chunk('NAME',Buffer.from('actor\0')),chunk('DGAN',Buffer.concat([chunk('INFO',info),seq]))]));
}
test('ANPK keeps source keyframe times and translations and conjugates rotations',()=>{
  const b=animationFixture(),data=parseIFP(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength));
  assert.equal(data.packageName,'TEST');const a=data.animations.get('actor'),t=a.tracks[0];
  assert.deepEqual(Array.from(t.times),[0,2,1]);assert.equal(t.nonMonotonic,true);
  assert.equal(t.rotations[0],-0.5);assert.equal(t.rotations[3],0.5);
  assert.deepEqual(Array.from(t.positions),[12,0,0,13,0,0,14,0,0]);assert.equal(a.duration,2);
  assert.throws(()=>parseIFP(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength-4)),/truncado/);
});
test('source camera cuts choose the later keyframe at duplicate timestamps',()=>{
  const c=[{time:0,value:[1,1,1]},{time:1,value:[2,2,2]},{time:1,value:[8,8,8]},{time:2,value:[8,8,8]}];
  assert.deepEqual(sampleCamera(c,1),[8]);assert.deepEqual(sampleCamera(c,2),[8]);
  assert.throws(()=>parseCamera('1,\n0f,1,2;'),/cuatro canales/);
  assert.throws(()=>parseCUT('model\n1, actor, actor\nend'),/CUT inválido/);
});
test('visible weighted channels with non-finite original transforms fail explicitly',()=>{
  const model=new THREE.Group(),bone=new THREE.Bone();bone.userData.boneId=0;model.add(bone);
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute([0,0,0],3));
  geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute([0,0,0,0],4));
  geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute([1,0,0,0],4));
  const mesh=new THREE.SkinnedMesh(geometry,new THREE.MeshBasicMaterial());model.add(mesh);mesh.bind(new THREE.Skeleton([bone]));
  assert.throws(()=>bindAnimation(model,{name:'actor',duration:1,tracks:[{boneId:0,boneName:'root',invalidTransform:true}]}),/influencia visible/);
});
test('Vorbis reader rejects truncated pages instead of treating them as original audio',()=>{
  const b=Buffer.alloc(58);b.write('OggS');b[5]=6;b.writeBigInt64LE(32000n,6);b.writeUInt32LE(5,14);b[26]=1;b[27]=30;
  b[28]=1;b.write('vorbis',29);b.writeUInt32LE(32000,40);
  b.writeUInt32LE(assets.oggCRC(b),22);
  assert.equal(assets.validateVorbis(b).duration,1);
  assert.throws(()=>assets.validateVorbis(b.subarray(0,40)),/truncada/);
  const corrupted=Buffer.from(b);corrupted[45]^=1;
  assert.throws(()=>assets.validateVorbis(corrupted),/Checksum/);
});
test('a separate audio installation is read with its own lookup table without replacing game files',()=>{
  const prefix=path.join(os.tmpdir(),'gtasa-opening-audio-'),folder=fs.mkdtempSync(prefix);
  try{
    const root=path.join(folder,'game'),alternate=path.join(folder,'full-audio');
    fs.mkdirSync(path.join(root,'anim'),{recursive:true});
    const img=Buffer.alloc(4096);img.write('VER2');img.writeUInt32LE(1,4);img.writeUInt32LE(1,8);img.writeUInt32LE(1,12);img.write('prolog1.dat',16);
    img.write('1,\n0.0f,50,50,50,\n22.333332f,50,50,50,\n;',2048);fs.writeFileSync(path.join(root,'anim/cuts.img'),img);
    const writeAudio=(install,seconds)=>{
      const config=path.join(install,'audio/CONFIG'),streams=path.join(install,'audio/streams');
      fs.mkdirSync(config,{recursive:true});fs.mkdirSync(streams,{recursive:true});
      const ogg=Buffer.alloc(58);ogg.write('OggS');ogg[5]=6;ogg.writeBigInt64LE(BigInt(Math.round(seconds*32000)),6);ogg.writeUInt32LE(5,14);ogg[26]=1;ogg[27]=30;
      ogg[28]=1;ogg.write('vorbis',29);ogg.writeUInt32LE(32000,40);ogg.writeUInt32LE(assets.oggCRC(ogg),22);
      const packs=Buffer.alloc(16);packs.write('CUTSCENE');fs.writeFileSync(path.join(config,'StrmPaks.dat'),packs);
      const lookup=Buffer.alloc(707*12);lookup.writeUInt32LE(ogg.length,706*12+8);fs.writeFileSync(path.join(config,'TrakLkup.dat'),lookup);
      const bytes=Buffer.alloc(8068+ogg.length),key=[234,58,196,161,154,168,20,243,72,176,215,35,157,232,255,241];
      for(let i=0;i<ogg.length;i++)bytes[8068+i]=ogg[i]^key[(8068+i)&15];fs.writeFileSync(path.join(streams,'CUTSCENE'),bytes);
      return {ogg,bytes};
    };
    const original=writeAudio(root,1.18),full=writeAudio(alternate,22.333332);
    assert.equal(assets.inspectSceneAudio(root,'prolog1').compatible,false);
    assert.throws(()=>assets.sceneAudio(root,'prolog1'),/la pista dura/);
    assert.deepEqual(assets.sceneAudio(root,'prolog1',{audioRoot:alternate}),full.ogg);
    assert.deepEqual(fs.readFileSync(path.join(root,'audio/streams/CUTSCENE')),original.bytes);
  }finally{
    assert(path.resolve(folder).startsWith(path.resolve(prefix)),'Unexpected temporary fixture directory');
    fs.rmSync(folder,{recursive:true,force:true});
  }
});
