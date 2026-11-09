// Live map view. Reads a copy of the database, so it never locks the one being written.
import http from 'node:http';import fs from 'node:fs';import path from 'node:path';import {execFile} from 'node:child_process';
const here=path.dirname(new URL(import.meta.url).pathname);const [db,port='4173']=process.argv.slice(2);
const main=path.join(here,'..','..','mcp-server','src','main.ts');fs.mkdirSync(path.join(here,'snap'),{recursive:true});let latest='{}',clients=[];
const page=()=>fs.readFileSync(path.join(here,'index.html'));
const publish=out=>{if(out!==latest){latest=out;for(const c of clients)c.write(`data: ${JSON.stringify(out)}\n\n`)}};
function poll(){const snap=path.join(here,'snap','s.lbug');if(!fs.existsSync(db)){publish('{}');return setTimeout(poll,1000)}
 try{for(const f of fs.readdirSync(here+'/snap'))fs.rmSync(path.join(here,'snap',f),{recursive:true});
  const dir=path.dirname(db),base=path.basename(db);for(const f of fs.readdirSync(dir))if(f.startsWith(base)&&!f.endsWith('.lock'))fs.copyFileSync(path.join(dir,f),path.join(here,'snap',f.replace(base,'s.lbug')));
 }catch{return setTimeout(poll,1500)}
 execFile('node',[main,'--database',snap,'--export'],{maxBuffer:1<<26},(e,out,err)=>{
    if(!e&&out.trim()){try{JSON.parse(out);publish(out)}catch{}}
  setTimeout(poll,1500)})}
http.createServer((q,r)=>{if(q.url==='/events'){r.writeHead(200,{'content-type':'text/event-stream','cache-control':'no-cache'});r.write(`data: ${JSON.stringify(latest)}\n\n`);clients.push(r);q.on('close',()=>clients=clients.filter(c=>c!==r));return}
 for(const[u,f]of[['/mermaid.js','mermaid.min.js'],['/elk-worker.js','elk-worker.min.js']])if(q.url===u){r.writeHead(200,{'content-type':'text/javascript','cache-control':'max-age=3600'});return r.end(fs.readFileSync(path.join(here,f)))}
 r.writeHead(200,{'content-type':'text/html'});r.end(page())}).listen(+port,'127.0.0.1',()=>console.log('http://localhost:'+port));poll();
