import * as slideLimits from '../lib/slide-limits.mjs';
// Real worker routes, real authorization and SQLite; no production records.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
const modules={};
modules['@/lib/conversation']={ensureConversation:async()=>{throw Error('Legacy route must not require conversation storage without a revision fence');}};
modules['./slide-limits.mjs']=slideLimits;modules['@/lib/slide-limits.mjs']=slideLimits;
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
const db=new DatabaseSync(':memory:');
db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,request_key TEXT,title TEXT,brief TEXT,pages INTEGER,style TEXT,language TEXT,attachments TEXT,status TEXT,created_at INTEGER,updated_at INTEGER,lease TEXT,summary TEXT,result_key TEXT,progress TEXT);CREATE TABLE worker(id TEXT PRIMARY KEY,heartbeat INTEGER);CREATE TABLE task_drafts(job_id TEXT PRIMARY KEY,object_key TEXT,sha256 TEXT,bytes INTEGER);');
const metadata=new Map();const objects=new Map();let puts=0,deletes=0,beforeBatch=null,putBarrier=null;
const binding={prepare(sql){let args=[];const statement={bind(...values){args=values;return statement;},async first(){return db.prepare(sql).get(...args)??null;},async run(){const result=db.prepare(sql).run(...args);return {meta:{changes:Number(result.changes)}};}};return statement;},async batch(statements){if(beforeBatch)beforeBatch();return Promise.all(statements.map(s=>s.run()));}};
const WORKER_TOKEN='synthetic-worker-secret-at-least-32-characters',REVIEW_TOKEN='synthetic-review-secret-at-least-32-characters';
modules['cloudflare:workers']={env:{DB:binding,WORKER_TOKEN,REVIEW_TOKEN,FILES:{async head(key){return objects.has(key)?{customMetadata:metadata.get(key)||{}}:null;},async put(key,data,options){puts++;metadata.set(key,options?.customMetadata||{});objects.set(key,new Uint8Array(data));if(putBarrier)await putBarrier();},async get(key){const data=objects.get(key);return data?{body:new Response(data).body}:null;},async delete(key){deletes++;objects.delete(key);}}}};
modules['@/app/chatgpt-auth']={getChatGPTUser:async()=>null};
for(const name of ['server','attachments','progress','queries'])modules['@/lib/'+name]=load('lib/'+name+'.ts');
modules['@/lib/admin-trace']=load('lib/admin-trace.ts');
const worker=load('app/api/worker/[id]/route.ts').POST;
function seed(status='failed',result=null){const id=crypto.randomUUID();db.prepare('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(id,'owner','request-'+id,'Original title','Original brief',1,'test','en','[{"original":"reference"}]',status,10,100,'old-lease','interrupted',result,'old-progress');return id;}
function call(id,action,{token=WORKER_TOKEN,lease='old-lease',body='{}'}={}){return worker(new Request('https://local.test/api/worker/'+id+'?action='+action,{method:'POST',headers:{Authorization:'Bearer '+token,'X-Job-Lease':lease,'Content-Length':String(new TextEncoder().encode(body).length)},body}),{params:Promise.resolve({id})});}
const retryBody=JSON.stringify({expectedUpdatedAt:100});
const id=seed(),original=db.prepare('SELECT * FROM jobs WHERE id=?').get(id);
for(const token of ['',REVIEW_TOKEN,'wrong-token'])assert.equal((await call(id,'retry',{token,body:retryBody})).status,401);
for(const body of ['{','{}','null','x'.repeat(1025),JSON.stringify({expectedUpdatedAt:'100'}),JSON.stringify({expectedUpdatedAt:0})])assert.equal((await call(id,'retry',{body})).status,400);
const parallel=await Promise.all([call(id,'retry',{body:retryBody}),call(id,'retry',{body:retryBody})]);
assert.deepEqual(parallel.map(r=>r.status).sort(),[200,409]);
const retried=db.prepare('SELECT * FROM jobs WHERE id=?').get(id);
assert.equal(retried.status,'queued');assert.equal(retried.lease,null);assert.equal(retried.progress,null);assert.equal(retried.summary,null);
for(const field of ['id','user_id','request_key','title','brief','pages','style','language','attachments','created_at'])assert.equal(retried[field],original[field],field);
assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs').get().n,1,'retry cannot charge another quota');
assert.equal((await call(id,'heartbeat')).status,409);assert.equal((await call(id,'complete',{body:'PKold'})).status,409);
db.prepare("UPDATE jobs SET status='running',lease='new-lease' WHERE id=?").run(id);
assert.equal((await call(id,'fail')).status,409);assert.equal((await call(id,'heartbeat',{lease:'new-lease'})).status,200);
const draftBytes=new Uint8Array([80,75,3,4,1,2,3]),draftKey='drafts/'+id+'/progress.pptx';objects.set(draftKey,draftBytes);db.prepare("UPDATE jobs SET summary='resume_from_draft' WHERE id=?").run(id);db.prepare('INSERT INTO task_drafts VALUES (?,?,?,?)').run(id,draftKey,'a'.repeat(64),draftBytes.length);
const draftSource=await call(id,'draft-source',{lease:'new-lease'});assert.equal(draftSource.status,200);assert.deepEqual(new Uint8Array(await draftSource.arrayBuffer()),draftBytes);
db.prepare("UPDATE jobs SET summary=NULL WHERE id=?").run(id);assert.equal((await call(id,'draft-source',{lease:'new-lease'})).status,409);
for(const state of ['queued','running','complete'])assert.equal((await call(seed(state),'retry',{body:retryBody})).status,409);
assert.equal((await call(seed('failed','already-delivered.pptx'),'retry',{body:retryBody})).status,409);
assert.equal((await call(seed(),'retry',{body:JSON.stringify({expectedUpdatedAt:99})})).status,409);
// Queue capacity remains atomic and retry creates no extra rows.
for(let n=Number(db.prepare("SELECT COUNT(*) n FROM jobs WHERE status IN ('queued','running')").get().n);n<100;n++)seed('queued');
assert.equal((await call(seed(),'retry',{body:retryBody})).status,409);
console.log('PASS: operator-only retry, request bounds, version guard, concurrent retry, preserved brief/attachments/quota, old-lease isolation and queue capacity');

const completeId=seed('running'),bytes='PKsynthetic-frozen-artifact';
assert.equal((await call(completeId,'complete',{body:bytes})).status,200);
const writes=puts;
assert.equal((await call(completeId,'complete',{body:bytes})).status,200);
assert.equal(puts,writes,'lost-ack retry should not upload again');
assert.equal((await call(completeId,'fail')).status,409,'late failure cannot overwrite delivery');
assert.equal((await call(completeId,'complete',{lease:'other-lease',body:bytes})).status,409);
assert.equal(db.prepare('SELECT status FROM jobs WHERE id=?').get(completeId).status,'complete');
// Force both requests past the running-state read before either updates SQL.
const raceId=seed('running');let entered=0,release;
const gate=new Promise(resolve=>{release=resolve;});
putBarrier=async()=>{entered++;if(entered===2)release();await gate;};
const completions=await Promise.all([call(raceId,'complete',{body:bytes}),call(raceId,'complete',{body:bytes})]);putBarrier=null;
assert.deepEqual(completions.map(r=>r.status),[200,200]);assert.equal(deletes,0);
const result=db.prepare('SELECT result_key FROM jobs WHERE id=?').get(raceId).result_key;
assert.equal(new TextDecoder().decode(objects.get(result)),bytes);
const failId=seed('running');assert.deepEqual((await Promise.all([call(failId,'fail'),call(failId,'fail')])).map(r=>r.status),[200,200]);
assert.equal((await call(failId,'fail')).status,200);
const expiredId=seed('running');beforeBatch=()=>db.prepare("UPDATE jobs SET status='failed' WHERE id=?").run(expiredId);
assert.equal((await call(expiredId,'heartbeat')).status,409);beforeBatch=null;
console.log('PASS: lost upload acknowledgement, concurrent completion, preserved delivered bytes, idempotent failure and expired heartbeat rejection');

// New delivery protocol: identify frozen bytes, preserve upload-only recovery,
// and fence actual revisions while ordinary chat cannot invalidate the file.
db.exec('CREATE TABLE task_messages(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT,job_id TEXT,role TEXT,kind TEXT,status TEXT);CREATE TABLE task_versions(id TEXT PRIMARY KEY,job_id TEXT,result_key TEXT,bundle_key TEXT,revision INTEGER,created_at INTEGER);');
modules['@/lib/conversation'].ensureConversation=async()=>{};
const hash=async value=>Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))).toString('hex');
const frozenHash=await hash(bytes),reviewed=seed('running');
const identity='&revision=0&sha256='+frozenHash;
assert.equal((await call(reviewed,'delivery-ready'+identity)).status,200);
assert.equal((await call(reviewed,'fail')).status,200);
assert.equal(db.prepare('SELECT summary FROM jobs WHERE id=?').get(reviewed).summary,'delivery_pending');
assert.equal((await call(reviewed,'delivery-status')).status,200);
db.prepare("UPDATE jobs SET status='running' WHERE id=?").run(reviewed);
// A chat question does not revise frozen presentation requirements.
db.prepare("INSERT INTO task_messages(id,job_id,role,kind,status) VALUES(? ,?,'user','chat','pending')").run(crypto.randomUUID(),reviewed);
assert.equal((await call(reviewed,'complete'+identity,{body:bytes})).status,200);
const confirmed=await (await call(reviewed,'delivery-status')).json();
assert.deepEqual(confirmed,{status:'complete',sha256:frozenHash,revision:0});
const frozenWrites=puts;
assert.equal((await call(reviewed,'complete'+identity,{body:bytes})).status,200);
assert.equal(puts,frozenWrites);
assert.equal((await call(reviewed,'complete&revision=0&sha256='+'0'.repeat(64),{body:bytes})).status,409);
assert.equal((await call(reviewed,'delivery-status',{lease:'other-lease'})).status,409);
const wrongBytes=seed('running');
assert.equal((await call(wrongBytes,'complete'+identity,{body:'PKdifferent'})).status,400);
const modified=seed('running');
db.prepare("INSERT INTO task_messages(id,job_id,role,kind,status) VALUES(? ,?,'user','revision','pending')").run(crypto.randomUUID(),modified);
assert.equal((await call(modified,'delivery-ready'+identity)).status,412);
assert.equal((await call(modified,'complete'+identity,{body:bytes})).status,412);
assert.equal(db.prepare('SELECT status FROM jobs WHERE id=?').get(modified).status,'running');
assert.equal((await call(modified,'delivery-reset')).status,200);
console.log('PASS: exact checksum/revision confirmation, delivery-pending preservation, chat distinction, revision fences, idempotency and lease isolation');
