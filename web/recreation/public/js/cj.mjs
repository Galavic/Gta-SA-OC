import * as THREE from 'three';
import { buildGeometry, fetchOK, frameMatrix } from './assets.mjs';
import { parseDFF, parseTXD } from './rw.mjs';

const PARTS = [
  {model:'torso', skin:'torso', clothing:'vest'},
  {model:'jeans', skin:'jeansdenim'},
  {model:'head', skin:'head'},
  {model:'hands', skin:'hands'},
  {model:'sneaker', skin:'sneakerbincblk'},
];

async function file(name) {
  return (await fetchOK('/api/player-file?name='+encodeURIComponent(name))).arrayBuffer();
}
async function texture(name) {
  const textures=parseTXD(await file(name+'.txd'));
  const raster=textures.find(t=>t.rgba&&!t.error);
  if(!raster) throw new Error('Textura original de CJ no válida: '+name);
  return raster;
}

// The original vest is an alpha layer over CJ's skin atlas. Combining these
// source rasters keeps uncovered arms/neck rather than making them transparent.
export function compositeClothing(skin, clothing) {
  const rgba=skin.rgba.slice();
  for(let y=0;y<skin.height;y++) for(let x=0;x<skin.width;x++) {
    const a=(y*skin.width+x)*4;
    const b=(Math.min(clothing.height-1,Math.floor(y*clothing.height/skin.height))*clothing.width+
             Math.min(clothing.width-1,Math.floor(x*clothing.width/skin.width)))*4;
    const alpha=clothing.rgba[b+3]/255;
    for(let c=0;c<3;c++) rgba[a+c]=Math.round(clothing.rgba[b+c]*alpha+rgba[a+c]*(1-alpha));
    rgba[a+3]=255;
  }
  return {...skin,rgba,hasAlpha:false};
}

export async function createCJ({cutscene=false}={}) {
  // The installed clothes.dat CUTS rules replace head/hands for cutscene CJ.
  const definitions=PARTS.map(part=>cutscene&&['head','hands'].includes(part.model)?{...part,model:'cs_'+part.model}:part);
  const pieces=await Promise.all(definitions.map(async definition=>{
    const [buffer,skin,clothing]=await Promise.all([
      file(definition.model+'.dff'),texture(definition.skin),
      definition.clothing?texture(definition.clothing):null,
    ]);
    return {definition,data:parseDFF(buffer),raster:clothing?compositeClothing(skin,clothing):skin};
  }));
  // Clothing files have an authoring rig with 37 joints. GTA assembles them
  // onto the 32-joint player.dff rig and remaps each piece by bone ID.
  const base=parseDFF(await (await fetchOK('/api/img-file?name='+(cutscene?'csplay.dff':'player.dff'))).arrayBuffer());
  const baseSkin=base.geometries.find(geometry=>geometry.skin)?.skin;
  if(!baseSkin)throw new Error('Esqueleto original del jugador no disponible');
  const model=new THREE.Group(); model.name='CJ';
  const frames=base.frames.map(frame=>{
    const bone=new THREE.Bone(); bone.name=frame.name;
    bone.userData.boneId=frame.boneId;
    bone.applyMatrix4(frameMatrix(frame.matrix));
    return bone;
  });
  base.frames.forEach((frame,i)=>{
    if(frame.parent>=0&&frame.parent<i) frames[frame.parent].add(frames[i]);
    else model.add(frames[i]);
  });
  const hierarchy=base.frames.find(frame=>frame.bones.length)?.bones;
  if(!hierarchy) throw new Error('CJ no contiene su jerarquía original');
  const bonesById=new Map(frames.filter(frame=>frame.userData.boneId!==null)
    .map(frame=>[frame.userData.boneId,frame]));
  const playerIndices=new Map(hierarchy.map(entry=>[entry.id,entry.index]));
  for(const {definition,data,raster} of pieces) {
    const map=new THREE.DataTexture(raster.rgba,raster.width,raster.height);
    map.colorSpace=THREE.SRGBColorSpace;
    map.wrapS=map.wrapT=THREE.RepeatWrapping;
    map.magFilter=THREE.LinearFilter; map.minFilter=THREE.LinearMipmapLinearFilter;
    map.generateMipmaps=true; map.needsUpdate=true;
    for(const source of data.geometries) {
      if(!source.skin) throw new Error('Pieza de CJ sin skin: '+definition.model);
      const geometry=buildGeometry(source);
      const pieceHierarchy=data.frames.find(frame=>frame.bones.length)?.bones;
      if(!pieceHierarchy)throw new Error('Pieza de CJ sin jerarquía');
      const pieceIds=new Map(pieceHierarchy.map(entry=>[entry.index,entry.id]));
      const indices=new Uint16Array(source.skin.indices.length);
      for(let i=0;i<indices.length;i++){
        const id=pieceIds.get(source.skin.indices[i]),index=playerIndices.get(id);
        if(index===undefined&&source.skin.weights[i]>0)throw new Error('Hueso de ropa sin equivalente: '+id);
        indices[i]=index??0;
      }
      geometry.setAttribute('skinIndex',new THREE.BufferAttribute(indices,4));
      geometry.setAttribute('skinWeight',new THREE.BufferAttribute(source.skin.weights,4));
      const materials=source.materials.map(material=>new THREE.MeshLambertMaterial({
        map,color:new THREE.Color(...material.color.slice(0,3)),side:THREE.DoubleSide,
      }));
      const mesh=new THREE.SkinnedMesh(geometry,materials.length?materials:new THREE.MeshLambertMaterial({map}));
      mesh.name='CJ_'+definition.model;
      const bones=new Array(baseSkin.numBones);
      for(const entry of hierarchy) if(entry.index<bones.length) bones[entry.index]=bonesById.get(entry.id);
      if(bones.filter(Boolean).length!==bones.length) throw new Error('Esqueleto de CJ incompleto');
      model.add(mesh); model.updateMatrixWorld(true);
      mesh.bind(new THREE.Skeleton(bones,baseSkin.inverses.map(matrix=>new THREE.Matrix4().fromArray(matrix))),new THREE.Matrix4());
      mesh.normalizeSkinWeights(); mesh.frustumCulled=false;
    }
  }
  model.userData.originalCharacter='Carl Johnson';
  model.userData.originalPieces=definitions.map(part=>part.model);
  return model;
}
