import * as THREE from 'three';

export class Walker {
  constructor(position) { this.position=position.clone(); this.velocityY=0; this.grounded=false; this.heading=0; this.moving=false; }
  step(dt,input,yaw,world) {
    const forward=Number(input.has('KeyW')||input.has('ArrowUp'))-Number(input.has('KeyS')||input.has('ArrowDown'));
    const side=Number(input.has('KeyD')||input.has('ArrowRight'))-Number(input.has('KeyA')||input.has('ArrowLeft'));
    const movement=new THREE.Vector3(side,0,-forward).applyAxisAngle(new THREE.Vector3(0,1,0),yaw);
    if(movement.lengthSq()>0) movement.normalize();
    const speed=input.has('ShiftLeft')||input.has('ShiftRight')?6.8:3.2;
    movement.multiplyScalar(speed*dt);
    this.moving=movement.lengthSq()>0;
    if(this.moving) this.heading=Math.atan2(-movement.x,-movement.z);
    const x=new THREE.Vector3(movement.x,0,0), z=new THREE.Vector3(0,0,movement.z);
    if(!world.blocked(this.position,x)) this.position.add(x);
    if(!world.blocked(this.position,z)) this.position.add(z);
    if(input.has('Space')&&this.grounded) {this.velocityY=7;this.grounded=false;}
    this.velocityY-=20*dt;
    const ceiling=world.ground(this.position,1.8,0);
    if(this.velocityY>0 && ceiling!==null && ceiling>this.position.y+0.15 && ceiling<this.position.y+1.65) this.velocityY=0;
    this.position.y+=this.velocityY*dt;
    const ground=world.ground(this.position,0.8,Math.max(2,Math.abs(this.velocityY)*dt+0.3));
    if(ground!==null && this.position.y<=ground+0.12 && this.velocityY<=0) {
      this.position.y=ground+0.04; this.velocityY=0; this.grounded=true;
    } else this.grounded=false;
  }
}
export class CarController {
  constructor(position,heading=0,bicycle=false) {this.bicycle=bicycle;this.position=position.clone();this.heading=heading;this.speed=0;this.steer=0;this.health=100;this.wheelAngle=0;}
  step(dt,input,world) {
    const throttle=Number(input.has('KeyW')||input.has('ArrowUp'))-Number(input.has('KeyS')||input.has('ArrowDown'));
    const steer=Number(input.has('KeyA')||input.has('ArrowLeft'))-Number(input.has('KeyD')||input.has('ArrowRight'));
    const brake=input.has('Space');
    this.speed+=throttle*(throttle<0&&this.speed>1?17:this.bicycle?5:11)*dt;
    this.speed*=Math.exp(-(brake?4.2:throttle?0.12:0.75)*dt);
    this.speed=THREE.MathUtils.clamp(this.speed,this.bicycle?-3:-11,this.health<=0?0:this.bicycle?12:42);
    this.steer=THREE.MathUtils.damp(this.steer,steer,12,dt);
    this.heading+=this.steer*this.speed*(this.bicycle?0.15:0.026)*dt;
    const delta=new THREE.Vector3(-Math.sin(this.heading),0,-Math.cos(this.heading)).multiplyScalar(this.speed*dt);
    const front=this.position.clone().add(new THREE.Vector3(-Math.sin(this.heading),0,-Math.cos(this.heading)).multiplyScalar(Math.sign(this.speed)*(this.bicycle?0.7:1.7)));
    if(world.blocked(front,delta,this.bicycle?0.3:0.92,1.35)) {
      this.health=Math.max(0,this.health-Math.abs(this.speed)*0.4);
      this.speed*=-0.15;
    } else this.position.add(delta);
    const ground=world.ground(this.position,2.5,9);
    if(ground!==null) this.position.y=THREE.MathUtils.damp(this.position.y,ground+0.03,18,dt);
    else this.position.y-=8*dt;
    this.wheelAngle+=this.speed*dt/0.36;
  }
}
