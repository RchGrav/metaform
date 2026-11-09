// Isolated reproduction: every fixture lives under review/round2.
import {createTools} from '../../adapters/openrouter-acp/dist/tools.js';
import {mkdir, realpath, symlink, unlink, readFile} from 'node:fs/promises';
import path from 'node:path';
const fixture=path.resolve('review/round2/symlink-fixture');
await mkdir(path.join(fixture,'root'),{recursive:true});
const root=await realpath(path.join(fixture,'root'));
const outside=path.join(fixture,'outside.txt');
const link=path.join(root,'link');
for(const f of [link,outside]) await unlink(f).catch(e=>{if(e.code!=='ENOENT')throw e});
await symlink(outside,link);
const tool=createTools({sessionId:'review',root,client:{
  notify:async()=>{}, request:async()=>({outcome:{outcome:'selected',optionId:'allow'}}),
}}).find(t=>t.function.name==='write_file');
await tool.function.execute({path:'link',content:'escaped'}, {callId:'review',signal:new AbortController().signal});
console.log(JSON.stringify({root,outside,written:await readFile(outside,'utf8')}));
await unlink(link); await unlink(outside);
