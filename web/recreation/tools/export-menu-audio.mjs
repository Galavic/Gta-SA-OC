// Lossless extraction of local GTA's PCM banks. Layout/event identities:
// https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Audio/Loaders/AEBankLoader.h
// https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Audio/Entities/AEFrontendAudioEntity.cpp
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const installation=process.env.SA_PATH||path.resolve(root,'../../original');
const folder=path.join(installation,'audio'),output=path.join(root,'public/original-audio');
fs.mkdirSync(output,{recursive:true});
const lookup=fs.readFileSync(path.join(folder,'CONFIG/BankLkup.dat'));
const packs=fs.readFileSync(path.join(folder,'CONFIG/PakFiles.dat'));
function bank(id) {
  const item=id*12,pak=lookup[item],offset=lookup.readUInt32LE(item+4),size=lookup.readUInt32LE(item+8);
  const name=packs.subarray(pak*52,pak*52+12).toString().split('\0')[0];
  if(!/^[A-Z0-9_]+$/.test(name))throw new Error('Invalid bank filename');
  const fd=fs.openSync(path.join(folder,'SFX',name),'r'),header=Buffer.alloc(4804);
  if(fs.readSync(fd,header,0,header.length,offset)!==header.length)throw new Error('Truncated bank header');
  const count=header.readUInt16LE(0);if(count<1||count>400)throw new Error('Invalid sound count');
  const data=Buffer.alloc(size);if(fs.readSync(fd,data,0,size,offset+4804)!==size)throw new Error('Truncated sound data');fs.closeSync(fd);
  return Array.from({length:count},(_,index)=>{
    const at=4+index*12,start=header.readUInt32LE(at);
    const end=index+1<count?header.readUInt32LE(at+12):size;
    const sampleRate=header.readUInt16LE(at+8);
    if(start>end||end>size||sampleRate<4000||sampleRate>96000||(end-start)%2)throw new Error('Invalid PCM description');
    return {pcm:data.subarray(start,end),sampleRate,loopStart:header.readUInt32LE(at+4)};
  });
}
function stereo(left,right) {
  if(left.sampleRate!==right.sampleRate||left.pcm.length!==right.pcm.length)throw new Error('Unmatched stereo pair');
  const data=Buffer.alloc(left.pcm.length*2);
  for(let i=0;i<left.pcm.length/2;i++){
    data.writeInt16LE(left.pcm.readInt16LE(i*2),i*4);data.writeInt16LE(right.pcm.readInt16LE(i*2),i*4+2);
  }
  const header=Buffer.alloc(44);header.write('RIFF');header.writeUInt32LE(36+data.length,4);header.write('WAVEfmt ',8);
  header.writeUInt32LE(16,16);header.writeUInt16LE(1,20);header.writeUInt16LE(2,22);
  header.writeUInt32LE(left.sampleRate,24);header.writeUInt32LE(left.sampleRate*4,28);header.writeUInt16LE(4,32);header.writeUInt16LE(16,34);
  header.write('data',36);header.writeUInt32LE(data.length,40);return Buffer.concat([header,data]);
}
const menu=bank(60),loading=bank(82),sounds={
  highlight:{left:menu[4],right:menu[5],bank:60,ids:[4,5]},
  select:{left:menu[6],right:menu[7],bank:60,ids:[6,7]},
  back:{left:menu[0],right:menu[1],bank:60,ids:[0,1]},
  loading:{left:loading[0],right:loading[1],bank:82,ids:[0,1]},
};
const manifest={source:'Original local GTA PCM banks',sounds:{}};
for(const [name,sound] of Object.entries(sounds)){
  const filename=name+'.wav';fs.writeFileSync(path.join(output,filename),stereo(sound.left,sound.right));
  manifest.sounds[name]={url:'/original-audio/'+filename,bank:sound.bank,ids:sound.ids,
    sampleRate:sound.left.sampleRate,seconds:sound.left.pcm.length/(sound.left.sampleRate*2)};
}
fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2));
console.log('Extracted original stereo menu and loading sounds:',manifest.sounds);
