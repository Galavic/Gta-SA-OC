// Independently written opening objective, not the original SCM mission.
export const START = [2395,13.5,1661];
export const BIKE_START = [2395,13.5,1658];
export const ROUTE = [
  {name:'Sigue la calle hacia Grove Street.',position:[2420,13.5,1658]},
  {name:'Continúa por Grove Street.',position:[2450,13.5,1658]},
  {name:'Sigue hasta el final de Grove Street.',position:[2470,13.5,1658]},
  {name:'Detén la BMX en el círculo frente a casa.',position:[2490,13.5,1670]},
];
export const HOME = {name:'Baja de la BMX con F y entra en el círculo de casa.',position:[2495,13.5,1687]};
const near=(p,t,r)=>Math.hypot(p.x-t[0],p.z-t[2])<r&&Math.abs(p.y-t[1])<4;
export class Mission {
  constructor(){this.stage='idle';this.index=0;this.elapsed=0;}
  get active(){return ['bike','ride','home'].includes(this.stage);}
  start(){this.stage='bike';this.index=0;this.elapsed=0;}
  target(bikePosition=BIKE_START){
    if(this.stage==='bike')return {name:'Acércate a la BMX y pulsa F para montar.',position:bikePosition};
    if(this.stage==='ride')return ROUTE[this.index];
    if(this.stage==='home')return HOME;
    return null;
  }
  update(position,mounted,dt,{vehicle='bmx',speed=0,health=100}={}){
    if(!this.active)return null;
    this.elapsed+=Math.max(0,Number.isFinite(dt)?dt:0);
    if(health<=0){this.stage='failed';return {failed:true};}
    if(this.stage==='bike'&&mounted&&vehicle==='bmx'){
      this.stage='ride';return {checkpoint:true};
    }
    if(this.stage==='ride'&&mounted&&vehicle==='bmx'&&near(position,ROUTE[this.index].position,9)){
      if(this.index===ROUTE.length-1){
        if(Math.abs(speed)>1.5)return null;
        this.stage='home';
      }else this.index++;
      return {checkpoint:true};
    }
    if(this.stage==='home'&&!mounted&&near(position,HOME.position,3)){
      this.stage='complete';return {complete:true,time:this.elapsed};
    }
    return null;
  }
  serialize(){return {stage:this.stage,index:this.index,elapsed:this.elapsed};}
  restore(data){
    const stages=['idle','bike','ride','home','complete','failed'];
    this.stage=stages.includes(data?.stage)?data.stage:'idle';
    const index=Number(data?.index);
    this.index=Number.isFinite(index)?Math.max(0,Math.min(ROUTE.length-1,Math.floor(index))):0;
    this.elapsed=Number.isFinite(data?.elapsed)?Math.max(0,data.elapsed):0;
  }
}
