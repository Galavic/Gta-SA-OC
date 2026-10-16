import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const installation=process.env.SA_PATH||path.resolve(root,'../../original');
for(const args of [
  ['tools/export-ui.mjs'],
  ['tools/export-menu-audio.mjs'],
  ['tools/txd-index.mjs',path.join(installation,'models/gta3.img')],
]) {
  const result=spawnSync(process.execPath,args,{cwd:root,env:{...process.env,SA_PATH:installation},stdio:'inherit'});
  if(result.error)throw result.error;
  if(result.status!==0)process.exit(result.status||1);
}
