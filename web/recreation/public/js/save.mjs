export const SAVE_KEY='sa-web-save-v1';
const finite=(value,fallback=0)=>Number.isFinite(Number(value))?Number(value):fallback;
function positionOK(position) {
  return Array.isArray(position)&&position.length===3&&position.every(Number.isFinite)&&Math.abs(position[0])<=5000&&Math.abs(position[2])<=5000&&Math.abs(position[1])<=1500;
}
export function readSave(storage,regions) {
  try {
    const data=JSON.parse(storage.getItem(SAVE_KEY));
    if(data?.version!==1||!Object.hasOwn(regions,data.region)||!positionOK(data.position))return null;
    data.money=Math.max(0,Math.min(99999999,finite(data.money)));
    data.minutes=Math.max(0,Math.min(1440,finite(data.minutes,780)));
    if(data.car && (!['bmx','greenwoo','savanna'].includes(data.car.model)||!positionOK(data.car.position)))data.car=null;
    if(data.car) {
      data.car.heading=finite(data.car.heading);
      data.car.health=Math.max(0,Math.min(100,finite(data.car.health,100)));
    }
    data.inCar=Boolean(data.inCar && data.car);
    return data;
  }catch{return null;}
}
export function writeSave(storage,data) {storage.setItem(SAVE_KEY,JSON.stringify({...data,version:1,savedAt:Date.now()}));}
