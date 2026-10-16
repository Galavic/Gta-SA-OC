import * as THREE from 'three';
import { fetchOK } from './assets.mjs';

export const GROVE = new THREE.Vector3(2490,13.5,1670);
export const REGIONS = {
  grove: { name: 'Grove Street', position: [2490,13.5,1670] },
  beach: { name: 'Santa Maria Beach', position: [370,8,2080] },
  sf: { name: 'San Fierro', position: [-1980,28,150] },
  lv: { name: 'Las Venturas', position: [2030,11,-1340] },
  desert: { name: 'Las Payasadas', position: [-240,29,-2600] },
};

export class WorldStream {
  constructor(scene,assets,onProgress) {
    this.scene=scene; this.assets=assets; this.onProgress=onProgress;
    this.loaded=new Map(); this.failed=new Set(); this.cells=new Map();
    this.lastPosition=new THREE.Vector3(Infinity,0,Infinity);
    this.busy=false; this.radius=260; this.stats=null; this.generation=0;
    this.raycaster=new THREE.Raycaster(); this.raycaster.firstHitOnly=true;
  }
  async update(position,force=false) {
    if (this.busy || (!force && position.distanceTo(this.lastPosition)<65)) return;
    this.busy=true;
    const center=position.clone(), generation=this.generation;
    try {
      const response=await fetchOK(`/api/world?x=${center.x}&y=${-center.z}&radius=${this.radius}`);
      const data=await response.json();
      if (generation!==this.generation) return;
      this.assets.parents=data.parents; this.stats=data.stats;
      const desired=new Set(data.instances.map(item=>item.key));
      for (const [key,item] of this.loaded) {
        if (!desired.has(key)) { this.scene.remove(item.object); this.loaded.delete(key); }
      }
      this.rebuildCells();
      const pending=data.instances.filter(item=>!this.loaded.has(item.key)&&!this.failed.has(item.key));
      let next=0, completed=0;
      this.onProgress({completed,total:pending.length,loaded:this.loaded.size,stats:this.stats});
      const worker=async()=>{
        while (next<pending.length && generation===this.generation) {
          const item=pending[next++];
          try {
            const template=await this.assets.model(item.model,item.txd);
            if (generation!==this.generation) break;
            const object=new THREE.Group();
            const content=template.clone(true);
            const rotation=new THREE.Quaternion(-item.rotation[0],-item.rotation[1],-item.rotation[2],item.rotation[3]).normalize();
            content.quaternion.premultiply(rotation);
            object.rotation.x=-Math.PI/2;
            object.position.set(item.position[0],item.position[2],-item.position[1]);
            object.add(content); this.scene.add(object); object.updateMatrixWorld(true);
            const box=new THREE.Box3().setFromObject(object);
            const meshes=[]; object.traverse(obj=>{if(obj.isMesh) meshes.push(obj);});
            // Transparent overlays and foliage are visual, not solid walls.
            const solid=!/alpha|trans|veg_|tree|bush|grass|nitelite|corona/i.test(item.model);
            const record={...item,object,box,meshes,solid,assetKey:template.userData.assetKey};
            this.loaded.set(item.key,record); this.addToCells(record);
          } catch(error) {
            this.failed.add(item.key); console.warn('Modelo no cargado',item.model,error);
          }
          completed++;
          this.onProgress({completed,total:pending.length,loaded:this.loaded.size,failed:this.failed.size,stats:this.stats});
          // Yield between assets so input and rendering remain responsive.
          await new Promise(resolve=>setTimeout(resolve,0));
        }
      };
      await Promise.all([worker(),worker(),worker(),worker()]);
      if (generation===this.generation) {
        this.lastPosition.copy(center);
        await this.assets.trim(new Set([...this.loaded.values()].map(item=>item.assetKey)));
      }
    } finally { this.busy=false; }
  }
  addToCells(item) {
    if (!item.solid || item.box.isEmpty()) return;
    const size=48;
    for (let x=Math.floor(item.box.min.x/size);x<=Math.floor(item.box.max.x/size);x++) {
      for (let z=Math.floor(item.box.min.z/size);z<=Math.floor(item.box.max.z/size);z++) {
        const key=`${x},${z}`;
        if (!this.cells.has(key)) this.cells.set(key,new Set());
        this.cells.get(key).add(item);
      }
    }
  }
  rebuildCells() { this.cells.clear(); for(const item of this.loaded.values()) this.addToCells(item); }
  candidates(position,range=2) {
    const items=new Set();
    for(let x=Math.floor((position.x-range)/48);x<=Math.floor((position.x+range)/48);x++)
      for(let z=Math.floor((position.z-range)/48);z<=Math.floor((position.z+range)/48);z++)
        for(const item of this.cells.get(`${x},${z}`)||[]) items.add(item);
    return [...items].flatMap(item=>item.meshes);
  }
  ground(position,up=1.2,down=5) {
    const origin=position.clone(); origin.y+=up;
    this.raycaster.set(origin,new THREE.Vector3(0,-1,0));
    this.raycaster.far=up+down;
    const hits=this.raycaster.intersectObjects(this.candidates(position),false);
    for(const hit of hits) {
      const normal=hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
      if(Math.abs(normal.y)>0.45) return hit.point.y;
    }
    return null;
  }
  blocked(position,delta,radius=0.35,height=1.7) {
    const distance=delta.length(); if(distance<1e-6) return false;
    const direction=delta.clone().normalize();
    const meshes=this.candidates(position,distance+radius+1);
    const lateral=new THREE.Vector3(-direction.z,0,direction.x).multiplyScalar(radius*0.8);
    for(const h of [0.45,height*0.8]) for(const sign of [-1,0,1]) {
      const origin=position.clone().addScaledVector(lateral,sign); origin.y+=h;
      this.raycaster.set(origin,direction); this.raycaster.far=distance+radius;
      const hit=this.raycaster.intersectObjects(meshes,false)[0];
      if(hit) {
        const normal=hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
        if(Math.abs(normal.y)<0.65) return true;
      }
    }
    return false;
  }
  reset() {
    this.generation++;
    for(const item of this.loaded.values()) this.scene.remove(item.object);
    this.loaded.clear(); this.cells.clear(); this.failed.clear();
    this.lastPosition.set(Infinity,0,Infinity);
  }
}
