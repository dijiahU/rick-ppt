// Real handlers, isolated SQLite/R2 adapters. No production credentials or jobs.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
const modules={};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
const db=new DatabaseSync(':memory:');db.exec("CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,status TEXT,lease TEXT,result_key TEXT,summary TEXT,updated_at INTEGER);CREATE TABLE worker(id TEXT PRIMARY KEY,heartbeat INTEGER)");
const id=crypto.randomUUID(),lease=crypto.randomUUID();db.prepare("INSERT INTO jobs VALUES (?,'owner','running',?,NULL,NULL,100)").run(id,lease);
let user='owner',loseInsertResponse=false,failUpload=false,afterPut=null;const objects=new Map();
const binding={prepare(sql){let args=[];const s={bind(...v){args=v;return s;},async first(){const value=db.prepare(sql).get(...args)??null;if(loseInsertResponse&&sql.startsWith('INSERT INTO task_messages')){loseInsertResponse=false;throw Error('lost response');}return value;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};}};return s;},async batch(statements){const out=[];for(const s of statements)out.push(await s.run());return out;}};
modules['@/lib/server']={database:()=>binding,files:()=>({async put(key,bytes){if(failUpload)throw Error('R2 offline');objects.set(key,new Uint8Array(bytes));if(afterPut){const callback=afterPut;afterPut=null;callback();}},async get(key){return objects.has(key)?{body:new Response(objects.get(key)).body}:null;},async head(key){return objects.has(key)?{size:objects.get(key).length}:null;}}),json:(v,status=200)=>Response.json(v,{status}),userId:async()=>user,sameOrigin:r=>r.headers.get('Origin')===new URL(r.url).origin,workerAuthorized:async r=>r.headers.get('Authorization')==='Bearer synthetic-worker'};
modules['@/lib/attachments']=load('lib/attachments.ts');modules['@/lib/conversation']=load('lib/conversation.ts');
const {POST:send,GET:read}=load('app/api/jobs/[id]/conversation/route.ts');const worker=load('app/api/worker/[id]/conversation/route.ts').POST,resume=load('app/api/jobs/[id]/resume/route.ts').POST,download=load('app/api/jobs/[id]/versions/[version]/route.ts').GET;
const params={params:Promise.resolve({id})};
function request({clientId=crypto.randomUUID(),body='Make the kernel draggable.',kind='revision',files=[],origin='https://test.local'}={}){const form=new FormData();for(const [k,v] of Object.entries({id:clientId,body,kind}))form.set(k,v);for(const f of files)form.append('files',f);return new Request(`https://test.local/api/jobs/${id}/conversation`,{method:'POST',headers:{Origin:origin},body:form});}
function wr(action,body={},givenLease=lease){return worker(new Request(`https://test.local/api/worker/${id}/conversation?action=${action}`,{method:'POST',headers:{Authorization:'Bearer synthetic-worker','X-Job-Lease':givenLease,'Content-Type':'application/json'},body:JSON.stringify(body)}),params);}
const plain=new Request('https://test.local');
user=null;assert.equal((await send(request(),params)).status,401);user='other';assert.equal((await send(request(),params)).status,404);assert.equal((await read(plain,params)).status,404);user='owner';assert.equal((await send(request({origin:'https://evil.test'}),params)).status,403);
for(const options of [{body:''},{body:'x'.repeat(8001)},{kind:'admin'},{clientId:'../escape'},{files:[new File(['exe'],'x.exe')]},{files:[new File(['not png'],'x.png')]},{files:Array.from({length:4},()=>new File(['a'],'a.txt'))}])assert.equal((await send(request(options),params)).status,400);
const clientId=crypto.randomUUID(),file=new File(['kernel = [[1,0],[0,-1]]'],'kernel.txt');const accepted=await send(request({clientId,files:[file]}),params);assert.equal(accepted.status,201);const first=(await accepted.json()).message;assert.equal(first.status,'pending');assert.equal(first.attachments.length,1);
assert.equal((await send(request({clientId,files:[file]}),params)).status,200);
assert.equal((await send(request({clientId,body:'Different intent',files:[file]}),params)).status,409);
assert.equal((await send(request({clientId,files:[new File(['same size different bytes'],'kernel.txt')]}),params)).status,409);
assert.equal(db.prepare('SELECT COUNT(*) n FROM task_messages').get().n,1);
const parallelId=crypto.randomUUID();const parallel=await Promise.all(Array.from({length:6},()=>send(request({clientId:parallelId}),params)));assert.deepEqual(new Set(await Promise.all(parallel.map(async r=>(await r.json()).message.id))),new Set([parallelId]));
loseInsertResponse=true;const lostId=crypto.randomUUID();assert.equal((await send(request({clientId:lostId}),params)).status,200);assert.equal((await send(request({clientId:lostId}),params)).status,200);
failUpload=true;assert.equal((await send(request({files:[file]}),params)).status,503);failUpload=false;
assert.equal((await wr('poll',{},'old-lease')).status,409);
const pending=await (await wr('poll')).json();assert.equal(pending.messages.length,3);assert.equal(pending.revision,pending.messages.at(-1).seq);
assert.equal((await wr('ack',{ids:[crypto.randomUUID()]})).status,404);
assert.equal((await wr('ack',{ids:[clientId]})).status,200);assert.equal((await wr('ack',{ids:[clientId]})).status,200);
assert.equal(db.prepare('SELECT status FROM task_messages WHERE id=?').get(clientId).status,'received');
assert.equal((await wr('applied',{ids:[clientId],revision:0})).status,409);
assert.equal((await wr('applied',{ids:[clientId],revision:first.seq})).status,200);await wr('ack',{ids:[clientId]});assert.equal(db.prepare('SELECT status FROM task_messages WHERE id=?').get(clientId).status,'applied');
const assistantId=crypto.randomUUID();assert.equal((await wr('assistant',{id:assistantId,body:'I will add the draggable kernel.'})).status,200);assert.equal((await wr('assistant',{id:assistantId,body:'I will add the draggable kernel.'})).status,200);
const meta=first.attachments[0],fileUrl=`https://test.local/api/jobs/${id}/conversation?message=${clientId}&file=${meta.id}`;
assert.equal(await (await read(new Request(fileUrl),params)).text(),'kernel = [[1,0],[0,-1]]');user='other';assert.equal((await read(new Request(fileUrl),params)).status,404);user='owner';
const checkpoint={checkpointId:crypto.randomUUID(),runId:crypto.randomUUID(),phase:'author',pluginVersion:'0.2.0',revision:first.seq,lastMessageSeq:first.seq,resumable:true};
assert.equal((await wr('checkpoint',{...checkpoint,checkpointId:'../../outside'})).status,400);assert.equal((await wr('checkpoint',checkpoint)).status,200);assert.equal((await wr('checkpoint',{...checkpoint,revision:0})).status,409);
const snapshot=await (await read(plain,params)).json();assert.equal(snapshot.recovery.resumable,true);assert.ok(!JSON.stringify(snapshot).includes(checkpoint.runId));assert.ok(!JSON.stringify(snapshot).includes(checkpoint.checkpointId));
function resumeRequest(at=100){return new Request(`https://test.local/api/jobs/${id}/resume`,{method:'POST',headers:{Origin:'https://test.local','Content-Type':'application/json'},body:JSON.stringify({expectedUpdatedAt:at})});}
db.prepare("UPDATE jobs SET status='failed'").run();user='other';assert.equal((await resume(resumeRequest(),params)).status,404);user='owner';assert.equal((await resume(resumeRequest(99),params)).status,409);
const resumed=await Promise.all(Array.from({length:5},()=>resume(resumeRequest(),params)));assert.equal(resumed.filter(r=>r.status===200).length>=1,true);assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs').get().n,1);assert.equal(db.prepare('SELECT status FROM jobs').get().status,'queued');
assert.equal((await wr('ack',{ids:[parallelId]})).status,409);
const resultKey=`results/${id}/${lease}.pptx`;db.prepare("UPDATE jobs SET status='complete',lease=?,result_key=?").run(lease,resultKey);objects.set(resultKey,new Uint8Array([80,75,3,4]));objects.set(`bundles/${id}/${lease}.zip`,new Uint8Array([80,75,3,4]));
assert.equal((await wr('version',{revision:first.seq})).status,200);assert.equal((await wr('version',{revision:first.seq})).status,200);assert.equal(db.prepare('SELECT COUNT(*) n FROM task_versions').get().n,1);
const versionParams={params:Promise.resolve({id,version:lease})};assert.equal((await download(new Request('https://test.local?kind=bundle'),versionParams)).headers.get('Content-Type'),'application/zip');user='other';assert.equal((await download(plain,versionParams)).status,404);user='owner';
// Fence the last upload against input accepted while R2 is storing the candidate.
db.exec('ALTER TABLE jobs ADD COLUMN attachments TEXT');
modules['@/lib/slide-limits.mjs']={MAX_SLIDES:50,MAX_PROGRESS_BYTES:1000000};
modules['@/lib/progress']={parseProgress:()=>null};modules['@/lib/queries']={RETRY_JOB:'SELECT 1'};modules['@/lib/admin-trace']={storeTrace:()=>Response.json({ok:true})};
const complete=load('app/api/worker/[id]/route.ts').POST;
const second=crypto.randomUUID(),secondLease=crypto.randomUUID(),lateMessage=crypto.randomUUID();
db.prepare("INSERT INTO jobs(id,user_id,status,lease,updated_at) VALUES (?,'owner','running',?,100)").run(second,secondLease);
function finish(revision,givenLease=secondLease){return complete(new Request(`https://test.local/api/worker/${second}?action=complete&revision=${revision}`,{method:'POST',headers:{Authorization:'Bearer synthetic-worker','X-Job-Lease':givenLease,'Content-Length':'4'},body:new Uint8Array([80,75,3,4])}),{params:Promise.resolve({id:second})});}
assert.equal((await finish(-1)).status,400);assert.equal((await finish(0,'old-lease')).status,409);
afterPut=()=>db.prepare("INSERT INTO task_messages(id,job_id,user_id,role,kind,body,attachments,status,created_at,updated_at) VALUES (?,?,'owner','user','revision','Change the title','[]','pending',1,1)").run(lateMessage,second);
assert.equal((await finish(0)).status,412);assert.equal(db.prepare('SELECT status FROM jobs WHERE id=?').get(second).status,'running');
assert.ok(objects.has(`results/${second}/${secondLease}.pptx`));
const lateSeq=db.prepare('SELECT seq FROM task_messages WHERE id=?').get(lateMessage).seq;
db.prepare("UPDATE task_messages SET status='applied' WHERE id=?").run(lateMessage);
assert.equal((await finish(lateSeq-1)).status,412);
objects.set(`bundles/${second}/${secondLease}.zip`,new Uint8Array([80,75,3,4]));
assert.equal((await finish(lateSeq)).status,200);assert.equal((await finish(lateSeq)).status,200);
assert.equal(db.prepare('SELECT COUNT(*) n FROM task_versions WHERE job_id=?').get(second).n,1);
assert.equal(db.prepare('SELECT bundle_key FROM task_versions WHERE job_id=?').get(second).bundle_key,`bundles/${second}/${secondLease}.zip`);
console.log('PASS: owner/CSRF isolation, bounded uploads, SHA metadata, conflicting idempotency, concurrent sends, lost acknowledgements, lease fencing, message delivery/application, safe checkpoints, quota-preserving resume, retained versions and atomic late-input delivery fence');
