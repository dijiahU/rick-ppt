// Real 200 MB uploads and route handlers, with disposable SQLite + disk-backed R2.
// No production jobs, accounts, credentials, or quota are used.
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,createReadStream,createWriteStream,statSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as limits from '../lib/slide-limits.mjs';

const root=mkdtempSync(join(tmpdir(),'rickppt-200mb-')),objects=new Map();
const db=new DatabaseSync(':memory:');
db.exec(readFileSync(new URL('../drizzle/0000_absurd_mongoose.sql',import.meta.url),'utf8'));
db.exec(readFileSync(new URL('../drizzle/0001_misty_tyger_tiger.sql',import.meta.url),'utf8'));
let user='owner',streamCopies=0;
const binding={prepare(sql){let args=[];const s={bind(...values){args=values;return s;},async first(){return db.prepare(sql).get(...args)??null;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};}};return s;},async batch(items){return Promise.all(items.map(s=>s.run()));}};
const bucket={
 async put(key,value,options={}){
  const path=join(root,crypto.randomUUID());
  if(value instanceof ReadableStream){streamCopies++;await pipeline(Readable.fromWeb(value),createWriteStream(path));}
  else await pipeline(Readable.from([value]),createWriteStream(path));
  objects.set(key,{path,size:statSync(path).size,customMetadata:options.customMetadata??{}});
 },
 async head(key){const value=objects.get(key);return value?{size:value.size,customMetadata:value.customMetadata}:null;},
 async get(key){const value=objects.get(key);return value?{size:value.size,body:Readable.toWeb(createReadStream(value.path))}:null;},
 async delete(keys){for(const key of Array.isArray(keys)?keys:[keys]){const value=objects.get(key);if(value)rmSync(value.path,{force:true});objects.delete(key);}}
};
const base='https://test.local',modules={'./slide-limits.mjs':limits,'@/lib/slide-limits.mjs':limits,'@/lib/admin':{isAdmin:async()=>false},'cloudflare:workers':{env:{DB:binding,FILES:bucket,WORKER_TOKEN:'local-test-worker-token-more-than-thirty-two'}},'@/app/chatgpt-auth':{getChatGPTUser:async()=>user?{userId:user}:null}};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
for(const name of ['execution-backend','server','i18n','execution-backend-i18n','attachments','queries','task-mode','task-mode-i18n','page-count-i18n','upload-i18n','progress','conversation','admin-trace','staged-uploads','upload-client']){modules['@/lib/'+name]=load('lib/'+name+'.ts');modules['./'+name]=modules['@/lib/'+name];}
const {POST:stage,DELETE:discard}=load('app/api/uploads/route.ts'),submit=load('app/api/jobs/route.ts').POST;
const {POST:send,GET:read}=load('app/api/jobs/[id]/conversation/route.ts');
const download=load('app/api/jobs/[id]/attachments/[file]/route.ts').GET;
const {stagedKey}=modules['@/lib/staged-uploads'],{validFiles,parseAttachments,MAX_TOTAL_BYTES}=modules['@/lib/attachments'];
function upload(scope,bytes=Buffer.from('reference'),name='reference.txt',headers={}){return new Request(base+`/api/uploads?scope=${encodeURIComponent(scope)}&name=${encodeURIComponent(name)}`,{method:'POST',headers:{Origin:base,...headers},body:bytes});}
function json(url,body){return new Request(base+url,{method:'POST',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)});}
const key=crypto.randomUUID(),scope=`job:${key}`;
const fields=(requestKey=key,uploadIds=[])=>({title:'200 MB test',brief:'Use the supplied reference material.',mode:'create',pages:5,language:'en',style:'test',execution_backend:'codex',requestKey,uploadIds});
const remove=(scope,ids)=>discard(new Request(base+`/api/uploads?scope=${encodeURIComponent(scope)}`,{method:'DELETE',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({ids})}));
try{
 assert.equal(MAX_TOTAL_BYTES,200*1024*1024);
 user=null;assert.equal((await stage(upload(scope))).status,401);user='owner';
 assert.equal((await stage(upload(scope,undefined,undefined,{Origin:'https://evil.test'}))).status,403);
 assert.equal((await stage(upload('../escape'))).status,400);
 assert.equal((await stage(upload(scope,Buffer.from('bad'),'fake.png'))).status,400);
 assert.equal((await stage(upload(scope,Buffer.from('x'),'big.txt',{'Content-Length':String(20*1024*1024+1)}))).status,400);
 assert.equal((await stage(upload(`message:${crypto.randomUUID()}:${crypto.randomUUID()}`))).status,404);

 // Exercise the actual browser helper: raw per-file requests, sequential transfer,
 // progress and cached retry. No 200 MB browser-side FormData is constructed.
 let active=0,maximum=0,requests=0;
 globalThis.XMLHttpRequest=class{
  upload={};headers={};open(method,url){this.method=method;this.url=url;}
  setRequestHeader(name,value){this.headers[name]=value;}
  send(file){assert.ok(file instanceof File);requests++;active++;maximum=Math.max(maximum,active);
   stage(new Request(base+this.url,{method:this.method,headers:{Origin:base,...this.headers},body:file})).then(async response=>{
    this.status=response.status;this.responseText=await response.text();active--;
    this.upload.onprogress?.({lengthComputable:true,loaded:file.size,total:file.size});this.onload();
   }).catch(error=>{active--;this.onerror(error);});
  }
 };
 const smallFiles=[new File(['one'],'one.txt'),new File(['two'],'two.txt')],progress=[];
 const client=modules['@/lib/upload-client'];
 const small=await client.uploadFiles(smallFiles,scope,{locale:'en',onProgress:p=>progress.push(p)});
 assert.deepEqual(await client.uploadFiles(smallFiles,scope),small);assert.equal(requests,2);assert.equal(maximum,1);assert.equal(progress.at(-1),100);
 assert.equal((await remove(scope,small)).status,200);
 for(const id of small)assert.equal(await bucket.head(await stagedKey(user,scope,id)),null);
 delete globalThis.XMLHttpRequest;

 // Upload ten actual 20 MB bodies, then commit only their IDs as small JSON.
 const data=Buffer.alloc(20*1024*1024,32);Buffer.from('%PDF-1.4\n').copy(data);
 async function stageTen(target){const ids=[];for(let i=0;i<10;i++){const response=await stage(upload(target,data,`reference-${i}.pdf`));assert.equal(response.status,201);ids.push((await response.json()).id);}return ids;}
 const ids=await stageTen(scope);
 const lookup=await stagedKey(user,scope,ids[0]),original={...objects.get(lookup).customMetadata};
 objects.get(lookup).customMetadata.expires='0';assert.equal((await submit(json('/api/jobs',fields(key,ids)))).status,400);objects.get(lookup).customMetadata=original;
 assert.equal((await submit(json('/api/jobs',fields(crypto.randomUUID(),ids)))).status,400);
 user='other';assert.equal((await submit(json('/api/jobs',fields(key,ids)))).status,400);user='owner';
 assert.equal((await submit(json('/api/jobs',fields(key,[...ids,crypto.randomUUID()])))).status,400);
 assert.equal((await submit(json('/api/jobs',fields(key,[ids[0],ids[0]])))).status,400);
 assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs').get().n,0);
 const accepted=await submit(json('/api/jobs',fields(key,ids)));assert.equal(accepted.status,201);const id=(await accepted.json()).id;
 const metadata=parseAttachments(db.prepare('SELECT attachments FROM jobs WHERE id=?').get(id).attachments);
 assert.equal(metadata.length,10);assert.equal(metadata.reduce((sum,f)=>sum+f.size,0),200*1024*1024);assert.ok(validFiles(metadata));
 assert.equal(validFiles(metadata.map((file,i)=>({...file,size:file.size+(i===0?1:0)}))),false);
 assert.equal(streamCopies,10,'All final copies must stream');
 assert.ok(Buffer.byteLength(JSON.stringify(fields(key,ids)))<2000);
 assert.equal((await remove(scope,ids)).status,200);
 assert.equal(await bucket.head(lookup),null);
 assert.equal((await submit(json('/api/jobs',fields(key,ids)))).status,200,'Lost task acknowledgements remain idempotent after cleanup');
 assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs').get().n,1);
 const result=await download(new Request(base),{params:Promise.resolve({id,file:metadata[0].id})});
 assert.equal(result.status,200);assert.equal((await result.arrayBuffer()).byteLength,20*1024*1024);

 // The same aggregate limit applies to attachments in a task conversation.
 const messageId=crypto.randomUUID(),messageScope=`message:${id}:${messageId}`,messageIds=await stageTen(messageScope);
 const payload={id:messageId,kind:'revision',body:'',uploadIds:messageIds},params={params:Promise.resolve({id})};
 const sent=await send(json(`/api/jobs/${id}/conversation`,payload),params);assert.equal(sent.status,201);
 const message=(await sent.json()).message;assert.equal(message.attachments.length,10);assert.equal(message.attachments.reduce((sum,f)=>sum+f.size,0),200*1024*1024);
 assert.equal(streamCopies,20);
 const transcript=await (await read(new Request(base),params)).json();assert.equal(transcript.messages[0].attachments.length,10);
 await remove(messageScope,messageIds);
 assert.equal((await send(json(`/api/jobs/${id}/conversation`,payload),params)).status,200,'Message retry survives temporary-upload cleanup');
 assert.equal(db.prepare('SELECT COUNT(*) n FROM task_messages').get().n,1);
 assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs').get().n,1,'Uploading references does not charge task quota');
 console.log('PASS: actual 200 MB task + 200 MB message, 10 × 20 MB per-file requests, small JSON commits, streaming R2 copies, cleanup, retry idempotency, owner/scope/expiry validation and unchanged task quota');
}finally{db.close();rmSync(root,{recursive:true,force:true});}
