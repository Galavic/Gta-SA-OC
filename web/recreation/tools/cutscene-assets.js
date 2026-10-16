// Read-only original assets. No game data is embedded or written to the repository.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {readImg,extract}=require('./img-reader');
const cache=new Map();
function fromArchive(root,relative,name){
  const archive=path.join(root,relative);
  if(!cache.has(archive))cache.set(archive,readImg(archive));
  const entry=cache.get(archive).entries.find(e=>e.name===name);
  return entry?extract(archive,entry).data:null;
}
function sceneFile(root,scene,extension){
  if(!['prolog1','prolog3'].includes(scene)||!['cut','dat','ifp'].includes(extension))throw new Error('Cinemática no admitida');
  const bytes=fromArchive(root,'anim/cuts.img',scene+'.'+extension);
  if(!bytes)throw new Error('Archivo de cinemática ausente');return bytes;
}
function sceneModel(root,name){
  if(!/^[a-z0-9_-]+\.(dff|txd)$/.test(name))throw new Error('Modelo inválido');
  return fromArchive(root,'models/cutscene.img',name)||fromArchive(root,'models/gta3.img',name);
}
function readSceneAudio(root,scene){
  // References: gta-reversed CutSceneStreamsPC.h, AETrackLoader.h,
  // AEStreamTransformer.cpp. tTrackInfo is 0x1f84 bytes before the audio payload.
  const id={prolog1:706,prolog3:708}[scene];if(id===undefined)throw new Error('Cinemática inválida');
  const lookup=fs.readFileSync(path.join(root,'audio/CONFIG/TrakLkup.dat'));
  const packs=fs.readFileSync(path.join(root,'audio/CONFIG/StrmPaks.dat'));
  const at=id*12;if(at+12>lookup.length)throw new Error('Tabla de audio truncada');
  const pack=packs.toString('ascii',lookup[at]*16,lookup[at]*16+16).split('\0')[0];
  if(pack!=='CUTSCENE')throw new Error('Pack de audio inesperado');
  const offset=lookup.readUInt32LE(at+4)+0x1f84,size=lookup.readUInt32LE(at+8);
  const file=fs.openSync(path.join(root,'audio/streams',pack),'r');
  const bytes=Buffer.alloc(size);
  try{if(fs.readSync(file,bytes,0,size,offset)!==size)throw new Error('Audio truncado');}finally{fs.closeSync(file);}
  const table=[0xea,0x3a,0xc4,0xa1,0x9a,0xa8,0x14,0xf3,0x48,0xb0,0xd7,0x23,0x9d,0xe8,0xff,0xf1];
  for(let i=0;i<bytes.length;i++)bytes[i]^=table[(offset+i)&15];
  return {bytes,trackId:id,declaredBytes:size};
}
function sceneAudioSnapshot(root,scene,audioRoot){
  const {bytes,trackId,declaredBytes}=readSceneAudio(audioRoot,scene);
  const verified=validateVorbis(bytes);
  const camera=sceneFile(root,scene,'dat').toString('ascii');
  const duration=Math.max(...[...camera.matchAll(/(?:^|\n)([0-9.]+)f,/g)].map(m=>Number(m[1])));
  if(!Number.isFinite(duration)||duration<=0)throw new Error('Duración original de cámara inválida');
  const compatible=verified.duration>=duration-1&&verified.duration<=duration+3;
  const audit={scene,trackId,declaredBytes,oggBytes:verified.bytes,paddingBytes:bytes.length-verified.bytes,
    audioSeconds:verified.duration,cameraSeconds:duration,pages:verified.pages,compatible,
    payloadSha256:crypto.createHash('sha256').update(bytes.subarray(0,verified.bytes)).digest('hex')};
  return {bytes,audit};
}
function inspectSceneAudio(root,scene,{audioRoot=root}={}){
  return sceneAudioSnapshot(root,scene,audioRoot).audit;
}
function sceneAudio(root,scene,{audioRoot=root}={}){
  const {bytes,audit}=sceneAudioSnapshot(root,scene,audioRoot);
  if(!audit.compatible)throw new Error(`Audio ${scene}: la pista dura ${audit.audioSeconds.toFixed(2)} s; la escena requiere ${audit.cameraSeconds.toFixed(2)} s`);
  return bytes.subarray(0,audit.oggBytes);
}
// Xiph Ogg framing CRC: normal (not reflected), initial/final XOR zero.
const crcTable=Uint32Array.from({length:256},(_,index)=>{
  let value=(index<<24)>>>0;
  for(let bit=0;bit<8;bit++)value=((value<<1)^((value&0x80000000)?0x04c11db7:0))>>>0;
  return value;
});
function oggCRC(bytes){
  let crc=0;
  for(let i=0;i<bytes.length;i++){
    const byte=i>=22&&i<26?0:bytes[i];
    crc=((crc<<8)^crcTable[((crc>>>24)^byte)&255])>>>0;
  }
  return crc;
}
function validateVorbis(bytes){
  let p=0,rate=null,serial=null,lastGranule=0,eos=false,pages=0,sequence=0;
  while(p+27<=bytes.length&&bytes.toString('ascii',p,p+4)==='OggS'){
    if(bytes[p+4]!==0)throw new Error('Versión Ogg desconocida');
    const current=bytes.readUInt32LE(p+14);
    if(serial!==null&&serial!==current)throw new Error('Ogg encadenado no admitido');serial=current;
    const segments=bytes[p+26],body=p+27+segments;
    if(body>bytes.length)throw new Error('Cabecera Ogg truncada');
    let size=0;for(let i=0;i<segments;i++)size+=bytes[p+27+i];
    if(body+size>bytes.length)throw new Error('Página Ogg truncada');
    if(bytes.readUInt32LE(p+22)!==oggCRC(bytes.subarray(p,body+size)))throw new Error('Checksum Ogg inválido');
    if(bytes.readUInt32LE(p+18)!==sequence++)throw new Error('Secuencia de páginas Ogg inválida');
    if(pages===0&&!(bytes[p+5]&2))throw new Error('Falta inicio de pista Ogg');
    pages++;
    if(rate===null){
      if(size<16||bytes[body]!==1||bytes.toString('ascii',body+1,body+7)!=='vorbis')throw new Error('Se requiere Vorbis');
      rate=bytes.readUInt32LE(body+12);if(!rate)throw new Error('Frecuencia de audio inválida');
    }
    const granule=bytes.readBigInt64LE(p+6);if(granule>=0)lastGranule=Number(granule);
    eos=Boolean(bytes[p+5]&4);p=body+size;if(eos)break;
  }
  if(!eos||rate===null)throw new Error('Pista Ogg incompleta');
  if(bytes.subarray(p).some(byte=>byte!==0))throw new Error('Datos adicionales de audio no interpretados');
  return {duration:lastGranule/rate,bytes:p,pages};
}
module.exports={sceneFile,sceneModel,sceneAudio,inspectSceneAudio,validateVorbis,oggCRC};
