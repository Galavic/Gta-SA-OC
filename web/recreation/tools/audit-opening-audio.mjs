// Reproducible read-only evidence for the actual installed prologue audio.
// Original bytes, generated PCM and private paths remain outside publication.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import assets from './cutscene-assets.js';
const project=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=process.env.SA_PATH||path.resolve(project,'../../original');
const audioRoot=process.env.SA_AUDIO_PATH||root;
const fingerprint=relative=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,relative))).digest('hex');
const scenes=['prolog1','prolog3'].map(scene=>assets.inspectSceneAudio(root,scene,{audioRoot}));
const report={scope:'Original prologue audio source, Ogg page CRC and duration verification',
  installedExecutableSha256:fingerprint('gta_sa.exe'),cutsceneArchiveSha256:fingerprint('anim/cuts.img'),
  scenes,identicalSceneAudio:scenes[0].payloadSha256===scenes[1].payloadSha256,
  allSceneAudioCompatible:scenes.every(scene=>scene.compatible),
  originalFilesModified:false,browserVerified:false};
const output=path.join(project,'checks/opening-audio.json');fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
