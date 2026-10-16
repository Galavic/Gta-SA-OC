export class OriginalAudio {
  constructor(){this.context=null;this.buffers=new Map();this.enabled=true;this.music=null;this.inMenu=true;}
  async unlock(){
    if(!this.enabled)return;
    if(!this.context){this.context=new AudioContext();this.ready=this.load();}
    await this.context.resume();await this.ready;
    if(this.inMenu&&!this.music)this.startMusic();
  }
  async load(){
    const response=await fetch('/original-audio/manifest.json');if(!response.ok)throw new Error('Audio original no disponible');
    const manifest=await response.json();
    await Promise.all(Object.entries(manifest.sounds).map(async([name,info])=>{
      const response=await fetch(info.url);if(!response.ok)throw new Error('No se pudo cargar '+name);
      this.buffers.set(name,await this.context.decodeAudioData(await response.arrayBuffer()));
    }));
  }
  startMusic(){
    if(!this.enabled||!this.context||!this.buffers.has('loading'))return;
    const source=this.context.createBufferSource(),gain=this.context.createGain();
    source.buffer=this.buffers.get('loading');source.loop=true;gain.gain.value=0.23;
    source.connect(gain);gain.connect(this.context.destination);source.start();this.music=source;
  }
  menu(active){this.inMenu=active;if(!active||!this.enabled){this.music?.stop();this.music=null;}else if(this.context&&!this.music)this.startMusic();}
  async effect(name){
    if(!this.enabled)return;
    try{await this.unlock();const buffer=this.buffers.get(name);if(!buffer)return;
      const source=this.context.createBufferSource(),gain=this.context.createGain();source.buffer=buffer;gain.gain.value=0.35;
      source.connect(gain);gain.connect(this.context.destination);source.start();
    }catch(error){console.warn(error);}
  }
  toggle(){this.enabled=!this.enabled;if(!this.enabled){this.music?.stop();this.music=null;}else this.unlock().catch(console.warn);return this.enabled;}
}
