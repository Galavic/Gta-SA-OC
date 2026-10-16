import test from 'node:test';
import assert from 'node:assert/strict';
import {Mission,ROUTE,HOME} from '../public/js/missions.mjs';
import {readSave,writeSave} from '../public/js/save.mjs';
const at=a=>({x:a[0],y:a[1],z:a[2]});
test('opening requires the bike, ordered route, stopping, then returning home on foot',()=>{
  const m=new Mission();m.start();
  m.update(at(HOME.position),false,1);assert.equal(m.stage,'bike');
  m.update(at(HOME.position),true,1,{vehicle:'greenwoo'});assert.equal(m.stage,'bike');
  m.update(at(ROUTE[0].position),true,1);assert.equal(m.stage,'ride');
  m.update(at(ROUTE[3].position),true,1);assert.equal(m.index,0);
  for(const point of ROUTE.slice(0,-1))m.update(at(point.position),true,1);
  m.update(at(ROUTE[3].position),true,1,{speed:5});assert.equal(m.stage,'ride');
  m.update(at(ROUTE[3].position),true,1,{speed:0});assert.equal(m.stage,'home');
  m.update(at(HOME.position),true,1);assert.equal(m.stage,'home');
  assert.equal(m.update(at(HOME.position),false,1).complete,true);
  assert.equal(m.update(at(HOME.position),false,1),null);
});
test('checkpoint at another elevation cannot advance; destroyed BMX fails and restart resets',()=>{
  const m=new Mission();m.start();m.update(at(ROUTE[0].position),true,1);
  const p=at(ROUTE[0].position);p.y+=10;m.update(p,true,1);assert.equal(m.index,0);
  assert.equal(m.update(p,true,1,{health:0}).failed,true);
  m.start();assert.equal(m.stage,'bike');assert.equal(m.index,0);assert.equal(m.elapsed,0);
});
test('BMX and mid-mission progress survive save reload; corrupt states are bounded',()=>{
  const m=new Mission();m.start();m.update(at(ROUTE[0].position),true,1);m.update(at(ROUTE[0].position),true,1);
  const storage={setItem(k,v){this.value=v;},getItem(){return this.value;}};
  writeSave(storage,{region:'grove',position:ROUTE[0].position,inCar:true,car:{model:'bmx',position:ROUTE[0].position},mission:m.serialize()});
  const data=readSave(storage,{grove:{}});assert.equal(data.inCar,true);
  const restored=new Mission();restored.restore(data.mission);assert.deepEqual(restored.serialize(),m.serialize());
  restored.restore({stage:'ride',index:Infinity,elapsed:Infinity});assert.equal(restored.index,0);assert.equal(restored.elapsed,0);
  restored.restore({stage:'injected',index:-1});assert.equal(restored.stage,'idle');
});
