// Run actual route code against SQLite and in-memory object storage only.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as slideLimits from '../lib/slide-limits.mjs';
const db=new DatabaseSync(':memory:');
db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,status TEXT,lease TEXT,summary TEXT,updated_at INTEGER,result_key TEXT,attachments TEXT,progress TEXT);CREATE TABLE worker(id TEXT PRIMARY KEY,heartbeat INTEGER);CREATE TABLE task_drafts(job_id TEXT PRIMARY KEY,object_key TEXT,sha256 TEXT,bytes INTEGER);');
let user='owner',admin=false;
const binding={prepare(sql){let args=[];const s={bind(...a){args=a;return s;},async first(){return db.prepare(sql).get(...args)??null;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};}};return s;},async batch(ss){return Promise.all(ss.map(s=>s.run()));}};
const objects=new Map(),modules={'@/lib/server':{database:()=>binding,files:()=>({put:async(k,v)=>objects.set(k,v),head:async()=>null}),json:(body,status=200)=>Response.json(body,{status}),userId:async()=>user,sameOrigin:r=>r.headers.get('Origin')===new URL(r.url).origin,workerAuthorized:r=>r.headers.get('Authorization')==='Bearer synthetic-worker-secret'},'@/lib/admin':{isAdmin:async()=>admin},'./slide-limits.mjs':slideLimits,'@/lib/slide-limits.mjs':slideLimits};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
for(const name of ['attachments','conversation','progress','queries','admin-trace'])modules['@/lib/'+name]=load('lib/'+name+'.ts');
const pause=load('app/api/jobs/[id]/pause/route.ts').POST,resume=load('app/api/jobs/[id]/resume/route.ts').POST,worker=load('app/api/worker/[id]/route.ts').POST,conversation=load('app/api/worker/[id]/conversation/route.ts').POST;
function seed(status='running',lease='lease'){const id=crypto.randomUUID();db.prepare('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)').run(id,'owner',status,lease,null,100,null,'[]','saved-progress');return id;}
function call(route,id,action='',body='{}',headers={}){return route(new Request('https://local.test/api/jobs/'+id+'?action='+action,{method:'POST',headers:{Origin:'https://local.test','Content-Length':String(new TextEncoder().encode(body).length),Authorization:'Bearer synthetic-worker-secret','X-Job-Lease':'lease',...headers},body}),{params:Promise.resolve({id})});}
const payload=JSON.stringify({expectedUpdatedAt:100}),id=seed();
user=null;assert.equal((await call(pause,id,'',payload)).status,401);
user='other';assert.equal((await call(pause,id,'',payload)).status,404);
user='owner';assert.equal((await call(pause,id,'',payload,{Origin:'https://evil.test'})).status,403);
assert.equal((await call(pause,id,'','{}')).status,400);
assert.equal((await call(pause,id,'',payload)).status,200);
assert.equal(db.prepare('SELECT status FROM jobs WHERE id=?').get(id).status,'paused');
assert.equal((await call(pause,id,'',payload)).status,200,'lost response may retry');
assert.deepEqual(await (await call(worker,id,'heartbeat')).json(),{ok:true,stop:true});
assert.equal((await call(worker,id,'complete','PKfrozen')).status,409,'pause fences final upload');
assert.equal((await call(worker,id,'fail')).status,409,'late failure cannot overwrite pause');
assert.equal((await (await call(conversation,id,'poll')).json()).stop,true);
await modules['@/lib/conversation'].ensureConversation();
assert.equal((await call(resume,id,'',JSON.stringify({expectedUpdatedAt:db.prepare('SELECT updated_at FROM jobs WHERE id=?').get(id).updated_at}))).status,409,'cannot resume before shutdown acknowledgement');
const checkpoint={checkpointId:crypto.randomUUID(),runId:crypto.randomUUID(),phase:'paused',pluginVersion:'native-test',resumable:true,revision:0,lastMessageSeq:0};
assert.equal((await call(conversation,id,'checkpoint',JSON.stringify(checkpoint))).status,200);
const row=db.prepare('SELECT * FROM jobs WHERE id=?').get(id);assert.equal(row.summary,'paused');assert.equal(row.progress,'saved-progress');
assert.equal((await call(resume,id,'',JSON.stringify({expectedUpdatedAt:row.updated_at}))).status,200);
assert.equal(db.prepare('SELECT status FROM jobs WHERE id=?').get(id).status,'queued');
assert.equal((await call(conversation,id,'checkpoint',JSON.stringify(checkpoint))).status,409,'old lease cannot write to resumed attempt');
assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs').get().n,1,'pause/resume creates no quota admission');
const queued=seed('queued',null);assert.equal((await call(pause,queued,'',payload)).status,200);const qrow=db.prepare('SELECT * FROM jobs WHERE id=?').get(queued);assert.equal(qrow.summary,'paused');
assert.equal((await call(resume,queued,'',JSON.stringify({expectedUpdatedAt:qrow.updated_at}))).status,200,'unstarted task needs no checkpoint');assert.equal(db.prepare('SELECT summary FROM jobs WHERE id=?').get(queued).summary,null);
for(const status of ['complete','failed'])assert.equal((await call(pause,seed(status),'',payload)).status,409);
admin=true;user='admin';assert.equal((await call(pause,seed(),' ',payload)).status,200,'administrator may pause');
console.log('PASS: auth, ownership, CSRF, queued/running pause, idempotency, upload/failure fencing, stop signal, checkpoint acknowledgement, safe resume and unchanged quota');
