// Actual routes and SQLite/R2 fixtures only: no website jobs, quota, or credentials.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as limits from '../lib/slide-limits.mjs';

const db=new DatabaseSync(':memory:');
db.exec(readFileSync(new URL('../drizzle/0000_absurd_mongoose.sql',import.meta.url),'utf8'));
db.prepare('INSERT INTO jobs(id,user_id,request_key,title,brief,pages,style,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?, ?,?,?)').run('legacy','old','legacy','Old','Old brief',5,'test','complete',1,1);
db.exec(readFileSync(new URL('../drizzle/0001_misty_tyger_tiger.sql',import.meta.url),'utf8'));
assert.equal(db.prepare("SELECT execution_backend FROM jobs WHERE id='legacy'").get().execution_backend,null);
let user='owner',admin=false;
const objects=new Map();
const binding={prepare(sql){let args=[];const s={bind(...values){args=values;return s;},async first(){return db.prepare(sql).get(...args)??null;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};}};return s;},async batch(items){return Promise.all(items.map(s=>s.run()));}};
const token='local-synthetic-worker-token-over-32-characters';
const modules={'./slide-limits.mjs':limits,'@/lib/slide-limits.mjs':limits,'cloudflare:workers':{env:{DB:binding,WORKER_TOKEN:token,FILES:{async put(k,v){objects.set(k,new Uint8Array(v));},async delete(keys){for(const k of Array.isArray(keys)?keys:[keys])objects.delete(k);},async head(){return null;}}}},'@/app/chatgpt-auth':{getChatGPTUser:async()=>user?{userId:user}:null},'@/lib/admin':{isAdmin:async()=>admin}};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
for(const name of ['execution-backend','server','i18n','execution-backend-i18n','attachments','queries','task-mode','task-mode-i18n','page-count-i18n','upload-i18n','progress','conversation','drafts','job-status','admin-trace','staged-uploads']){modules['@/lib/'+name]=load('lib/'+name+'.ts');modules['./'+name]=modules['@/lib/'+name];}
const submit=load('app/api/jobs/route.ts').POST,claim=load('app/api/worker/route.ts').POST,account=load('app/api/account/route.ts').GET,resume=load('app/api/jobs/[id]/resume/route.ts').POST,message=load('app/api/jobs/[id]/conversation/route.ts').POST,worker=load('app/api/worker/[id]/route.ts').POST;
const base='https://local.test';
function fields(backend='api',key=crypto.randomUUID()){return {title:'LOCAL backend fixture',brief:'Explain this local-only test example.',pages:5,style:'test',language:'en',requestKey:key,execution_backend:backend};}
function request(body,origin=base){return new Request(base+'/api/jobs',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify(body)});}
function claimRequest(body={},secret=token){return new Request(base+'/api/worker',{method:'POST',headers:{Authorization:'Bearer '+secret,'Content-Type':'application/json'},body:JSON.stringify(body)});}
function taskRequest(id,body,path='resume'){return new Request(base+`/api/jobs/${id}/${path}`,{method:'POST',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)});}
const count=()=>db.prepare('SELECT COUNT(*) n FROM jobs WHERE user_id=?').get(user).n;

user=null;assert.equal((await submit(request(fields()))).status,401);assert.deepEqual(await (await account()).json(),{signedIn:false});
user='owner';assert.equal((await submit(request(fields(),'https://evil.test'))).status,403);assert.equal((await claim(claimRequest({},'wrong'))).status,401);
const automaticKey=crypto.randomUUID();let automaticId;
for(const backend of [undefined,null,'','unknown',true,{},[]]){const data=fields(backend,automaticKey);if(backend===undefined)delete data.execution_backend;const r=await submit(request(data));assert.ok([200,201].includes(r.status));const result=await r.json();automaticId??=result.id;assert.equal(result.id,automaticId);assert.equal(result.execution_backend,'codex');}
assert.equal(count(),1,'ignored client hints and retries cannot consume extra quota');
db.prepare('DELETE FROM jobs WHERE id=?').run(automaticId);
admin=true;for(const backend of ['', 'unknown', true, {}, []])assert.equal((await submit(request(fields(backend)))).status,400);admin=false;
// A live API-only worker can receive a new automatic admission. Public clients
// cannot force Codex; an availability change cannot reroute an admitted retry.
db.prepare('INSERT INTO worker(id,heartbeat,execution_backends) VALUES(?,?,?)').run('primary',Date.now(),JSON.stringify(['api']));
const routedKey=crypto.randomUUID(),routed=await (await submit(request(fields('codex',routedKey)))).json();assert.equal(routed.execution_backend,'api');
db.prepare('UPDATE worker SET execution_backends=? WHERE id=?').run(JSON.stringify(['api','codex']),'primary');
assert.equal((await (await submit(request(fields('api',routedKey)))).json()).id,routed.id);
assert.equal((await (await submit(request(fields('codex',routedKey)))).json()).execution_backend,'api');
db.prepare('DELETE FROM jobs WHERE id=?').run(routed.id);
db.prepare("UPDATE worker SET heartbeat=0 WHERE id='primary'").run();
for(const value of [null,'api',['bad'],['api','api'],['api','codex','api'],{}])assert.equal((await claim(claimRequest({execution_backends:value}))).status,400);
admin=true;const key=crypto.randomUUID();const responses=await Promise.all(Array.from({length:4},()=>submit(request(fields('api',key)))));const ids=await Promise.all(responses.map(r=>r.json()));assert.equal(new Set(ids.map(x=>x.id)).size,1);const apiId=ids[0].id;
assert.equal(count(),1);assert.equal(db.prepare('SELECT execution_backend FROM jobs WHERE id=?').get(apiId).execution_backend,'api');
assert.equal((await submit(request(fields('codex',key)))).status,409);assert.equal(count(),1,'same administrator request key cannot change route or charge again');admin=false;assert.equal((await submit(request(fields('codex',key)))).status,200,'public retries preserve the admitted route');
const codexResponse=await submit(request(fields('api')));assert.equal(codexResponse.status,201);const codexId=(await codexResponse.json()).id;
assert.equal((await (await account()).json()).jobs.find(x=>x.id===apiId).execution_backend,'api');

// An old worker cannot pick up any explicit new route; it can still claim legacy.
assert.equal((await (await claim(claimRequest())).json()).job,null);
db.prepare("UPDATE jobs SET status='queued' WHERE id='legacy'").run();
assert.equal((await (await claim(claimRequest())).json()).job.id,'legacy');
db.prepare("UPDATE jobs SET status='complete' WHERE id='legacy'").run();
const codexJob=(await (await claim(claimRequest({execution_backends:['codex']}))).json()).job;
assert.equal(codexJob.id,codexId);assert.equal(codexJob.execution_backend,'codex');assert.equal(codexJob.mode,'create');
assert.equal((await (await claim(claimRequest({execution_backends:['codex']}))).json()).job,null);
let state=await (await account()).json();assert.deepEqual(state.executionAvailability,{api:false,codex:true});assert.equal(state.online,true);
const apiJob=(await (await claim(claimRequest({execution_backends:['api','codex']}))).json()).job;
assert.equal(apiJob.id,apiId);assert.equal(apiJob.execution_backend,'api');
// Advertised heartbeat capabilities update public availability without provider data.
const heartbeatBody=JSON.stringify({execution_backends:['codex']});const params={params:Promise.resolve({id:apiId})};
assert.equal((await worker(new Request(base+`/api/worker/${apiId}?action=heartbeat`,{method:'POST',headers:{Authorization:'Bearer '+token,'X-Job-Lease':apiJob.lease},body:heartbeatBody}),params)).status,200);
state=await (await account()).json();assert.deepEqual(state.executionAvailability,{api:false,codex:true});assert.ok(!JSON.stringify(state).includes(token));
db.prepare("UPDATE worker SET heartbeat=0 WHERE id='primary'").run();state=await (await account()).json();assert.equal(state.online,false);assert.deepEqual(state.executionAvailability,{api:false,codex:false});

// Scope and route survive pause/resume/revision; restoration does not create a new admission.
user='edit-owner';const form=new FormData();for(const [k,v] of Object.entries({...fields('api'),mode:'edit'}))form.set(k,String(v));form.append('files',new File([new Uint8Array([80,75,3,4,0,0,0,0])],'original.pptx'));
admin=true;const editResponse=await submit(new Request(base+'/api/jobs',{method:'POST',headers:{Origin:base},body:form}));assert.equal(editResponse.status,201);const editId=(await editResponse.json()).id;admin=false;
db.prepare("UPDATE jobs SET status='paused',lease=NULL,summary='paused',updated_at=100 WHERE id=?").run(editId);
assert.equal((await resume(taskRequest(editId,{expectedUpdatedAt:100,execution_backend:'codex'}),{params:Promise.resolve({id:editId})})).status,409);
const restored=await resume(taskRequest(editId,{expectedUpdatedAt:100}),{params:Promise.resolve({id:editId})});assert.equal(restored.status,200);assert.equal((await restored.json()).execution_backend,'api');
const row=db.prepare('SELECT pages,execution_backend FROM jobs WHERE id=?').get(editId);assert.equal(row.pages,0);assert.equal(row.execution_backend,'api');assert.equal(count(),1);
const revision={id:crypto.randomUUID(),kind:'revision',body:'Change the title.',execution_backend:'codex'};
assert.equal((await message(taskRequest(editId,revision,'conversation'),{params:Promise.resolve({id:editId})})).status,409);
delete revision.execution_backend;assert.equal((await message(taskRequest(editId,revision,'conversation'),{params:Promise.resolve({id:editId})})).status,201);assert.equal(db.prepare('SELECT execution_backend FROM jobs WHERE id=?').get(editId).execution_backend,'api');

// FIFO uses the global tie-break among eligible rows; slots remain global, not per route.
db.exec("UPDATE jobs SET status='complete'");user='fifo-owner';
for(const [id,route,created] of [['z-api','api',1],['b-codex','codex',2],['a-codex','codex',2],['c-api','api',3]])db.prepare('INSERT INTO jobs(id,user_id,request_key,title,brief,pages,style,status,created_at,updated_at,execution_backend) VALUES(?,?,?,?,?,?,?, ?,?,?,?)').run(id,user,id,'Test','Local test',5,'test','queued',created,created,route);
const take=async routes=>(await (await claim(claimRequest({execution_backends:routes}))).json()).job;
assert.equal((await take(['codex'])).id,'a-codex');assert.equal((await take(['api'])).id,'z-api');assert.equal((await take(['codex'])).id,'b-codex');assert.equal(await take(['api','codex']),null);
db.prepare("UPDATE jobs SET status='complete' WHERE id='a-codex'").run();assert.equal((await take(['api','codex'])).id,'c-api');
db.exec("UPDATE jobs SET status='complete'");user='quota-owner';for(let i=0;i<10;i++)assert.equal((await submit(request(fields(i%2?'api':'codex')))).status,201);assert.equal((await submit(request(fields('api')))).status,429);assert.equal(count(),10);
const {backendChoiceUnavailable,executionAvailability,workerCapabilities,automaticExecutionBackend}=modules['@/lib/execution-backend'];
assert.equal(backendChoiceUnavailable('api',false,{api:false,codex:false}),false,'offline allows explicit queue choice');assert.equal(backendChoiceUnavailable('api',true,{api:false,codex:true}),true);assert.deepEqual(executionAvailability(null,true),{api:false,codex:false});assert.deepEqual(workerCapabilities(undefined),{backends:[],advertised:false});
assert.equal(automaticExecutionBackend({online:true,executionAvailability:{api:true,codex:true}}),'codex');assert.equal(automaticExecutionBackend({online:false,executionAvailability:{api:true,codex:false}}),'codex');assert.equal(automaticExecutionBackend({online:true,executionAvailability:{api:false,codex:false}}),'codex');
db.close();console.log('PASS: real routes, additive nullable migration, auth/CSRF, server-owned routing, public override suppression, administrator pinning, quota/idempotency, immutable admitted route, legacy worker fence, capabilities/availability, scoped resume/revision, global FIFO and three slots');
