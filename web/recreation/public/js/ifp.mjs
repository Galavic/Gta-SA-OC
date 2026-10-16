// GTA SA ANP3 compressed animation container. Values are decoded from the
// user's ped.ifp; no animation assets are embedded in this module.
export function parseIFP(buffer) {
  if(new TextDecoder().decode(new Uint8Array(buffer,0,Math.min(4,buffer.byteLength)))==='ANPK')return parseANPK(buffer);
  const view=new DataView(buffer), decoder=new TextDecoder(); let offset=0;
  const string=length=>{
    if(offset+length>view.byteLength) throw new Error('IFP truncado');
    const result=decoder.decode(new Uint8Array(buffer,offset,length)).split('\0')[0]; offset+=length; return result;
  };
  const uint=()=>{const result=view.getUint32(offset,true);offset+=4;return result;};
  if(string(4)!=='ANP3') throw new Error('Se requiere IFP ANP3');
  uint(); const packageName=string(24), count=uint(), animations=new Map();
  for(let a=0;a<count;a++) {
    const name=string(24), boneCount=uint(); uint(); uint();
    const tracks=[]; let duration=0;
    for(let b=0;b<boneCount;b++) {
      const boneName=string(24), type=uint(), frameCount=uint(), boneId=uint();
      if(type!==3 && type!==4) throw new Error(`Tipo IFP no soportado: ${type}`);
      const times=new Float32Array(frameCount), rotations=new Float32Array(frameCount*4);
      const positions=type===4?new Float32Array(frameCount*3):null;
      for(let f=0;f<frameCount;f++) {
        for(let q=0;q<4;q++,offset+=2) rotations[f*4+q]=view.getInt16(offset,true)/4096;
        times[f]=view.getInt16(offset,true)/60; offset+=2;
        if(positions) for(let p=0;p<3;p++,offset+=2) positions[f*3+p]=view.getInt16(offset,true)/4096;
        duration=Math.max(duration,times[f]);
      }
      tracks.push({boneName,boneId,times,rotations,positions});
    }
    animations.set(name.toLowerCase(),{name,tracks,duration});
  }
  return {packageName,animations};
}

// ANPK cutscene keyframes: quaternions, optional translation/scale, absolute time.
// Format reference: gta-reversed Animation/AnimManager.cpp (LoadAnimFile_ANPK).
export function parseANPK(buffer) {
  const v=new DataView(buffer),decoder=new TextDecoder();
  const str=(p,n)=>decoder.decode(new Uint8Array(buffer,p,n)).split('\0')[0];
  const chunks=(start,end)=>{
    const result=[];
    for(let p=start;p<end;){
      if(p+8>end)throw new Error('Cabecera ANPK truncada');
      const tag=str(p,4),size=v.getUint32(p+4,true),body=p+8;
      if(body+size>end)throw new Error('Chunk ANPK truncado');
      result.push({tag,size,body});p=body+Math.ceil(size/4)*4;
      if(p>end&&body+size!==end)throw new Error('Alineación ANPK inválida');
    }
    return result;
  };
  if(v.byteLength<8||str(0,4)!=='ANPK')throw new Error('Se requiere ANPK');
  const end=8+v.getUint32(4,true);if(end>v.byteLength)throw new Error('ANPK truncado');
  const root=chunks(8,end),info=root.shift();
  if(info?.tag!=='INFO'||info.size<5)throw new Error('INFO ANPK inválido');
  const count=v.getUint32(info.body,true),packageName=str(info.body+4,info.size-4),animations=new Map();
  if(root.length!==count*2)throw new Error('Conteo ANPK inválido');
  for(let a=0;a<count;a++){
    const nameChunk=root[a*2],data=root[a*2+1];
    if(nameChunk.tag!=='NAME'||data.tag!=='DGAN')throw new Error('Animación ANPK inválida');
    const name=str(nameChunk.body,nameChunk.size),parts=chunks(data.body,data.body+data.size),header=parts.shift();
    if(header?.tag!=='INFO'||header.size<4||parts.length!==v.getUint32(header.body,true))throw new Error('Secuencias ANPK inválidas');
    const tracks=[];let duration=0;
    for(const part of parts){
      if(part.tag!=='CPAN')throw new Error('Falta CPAN');
      const [anim,keys]=chunks(part.body,part.body+part.size);
      if(anim?.tag!=='ANIM'||![40,44].includes(anim.size))throw new Error('ANIM inválido');
      const frames=v.getUint32(anim.body+28,true);if(!frames)continue;
      const stride={KR00:20,KRT0:32,KRTS:44}[keys?.tag];
      if(!stride||keys.size!==frames*stride)throw new Error('Keyframes ANPK inválidos');
      const times=new Float32Array(frames),rotations=new Float32Array(frames*4),positions=stride>=32?new Float32Array(frames*3):null;
      for(let i=0;i<frames;i++){
        const p=keys.body+i*stride;
        for(let q=0;q<4;q++)rotations[i*4+q]=v.getFloat32(p+q*4,true)*(q<3?-1:1);
        if(positions)for(let j=0;j<3;j++)positions[i*3+j]=v.getFloat32(p+16+j*4,true);
        times[i]=v.getFloat32(p+stride-4,true);
        if(!Number.isFinite(times[i])||times[i]<0)throw new Error('Tiempo ANPK inválido');
      }
      const invalidTransform=!rotations.every(Number.isFinite)||Boolean(positions&&!positions.every(Number.isFinite));
      for(const time of times)duration=Math.max(duration,time);
      const nonMonotonic=times.some((t,i)=>i>0&&t<times[i-1]);
      tracks.push({boneName:str(anim.body,28),boneId:anim.size===44?v.getInt32(anim.body+40,true):null,times,rotations,positions,nonMonotonic,invalidTransform});
    }
    animations.set(name.toLowerCase(),{name,tracks,duration});
  }
  return {packageName,animations};
}
