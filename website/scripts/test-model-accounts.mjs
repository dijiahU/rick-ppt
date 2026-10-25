// Actual handlers, transactional SQLite and fake upstream. Never touches production.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as limits from '../lib/slide-limits.mjs';
const db=new DatabaseSync(':memory:');
for(const f of ['0000_absurd_mongoose.sql','0001_misty_tyger_tiger.sql'])db.exec(readFileSync(new URL('../drizzle/'+f,import.meta.url),'utf8'));
let user='alice',lostAcknowledgement=false;
const binding={prepare(sql){let values=[];return {sql,bind(...args){values=args;return this;},async first(){return db.prepare(sql).get(...values)??null;},async all(){return {results:db.prepare(sql).all(...values)};},async run(){const s=db.prepare(sql);if(s.columns().length){const results=s.all(...values);return {results,meta:{changes:results.length}};}return {results:[],meta:{changes:Number(s.run(...values).changes)}};}};},async batch(items){db.exec('BEGIN');let result;try{result=[];for(const item of items)result.push(await item.run());db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}if(lostAcknowledgement&&items.some(i=>i.sql.startsWith('INSERT INTO jobs'))){lostAcknowledgement=false;throw Error('Synthetic acknowledgement loss');}return result;}};
const token='synthetic-worker-token-with-over-32-characters';
const env={DB:binding,FILES:{async head(){return null;},async delete(){}},WORKER_TOKEN:token,BYOK_ENCRYPTION_KEY:'7b'.repeat(32)};
const modules={'cloudflare:workers':{env},'./slide-limits.mjs':limits,'@/lib/slide-limits.mjs':limits,'@/app/chatgpt-auth':{getChatGPTUser:async()=>user?{userId:user}:null},'@/lib/admin':{isAdmin:async()=>false}};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const out={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},out);return out;}
for(const name of ['execution-backend','server','model-providers','model-accounts','i18n','execution-backend-i18n','attachments','queries','task-mode','task-mode-i18n','page-count-i18n','upload-i18n','progress','conversation','admin-trace','staged-uploads']){const m=load('lib/'+name+'.ts');modules['@/lib/'+name]=modules['./'+name]=m;}
const accounts=load('app/api/model-accounts/route.ts'),disconnect=load('app/api/model-accounts/[id]/route.ts').DELETE;
const submit=load('app/api/jobs/route.ts').POST,claim=load('app/api/worker/route.ts').POST,profile=load('app/api/worker/[id]/model-profile/route.ts').POST;
const resume=load('app/api/jobs/[id]/resume/route.ts').POST;
const {openKey,sealKey}=modules['@/lib/model-accounts'];
const base='https://fixture.test',fakeKey='sk-synthetic-customer-a-key-1234';
let providerCalls=[];
const originalFetch=globalThis.fetch;
globalThis.fetch=async(url,options)=>{providerCalls.push({url,options});assert.equal(options.redirect,'error');return Response.json({data:[{id:'deepseek-flash'},{id:'gpt-6-astra'},{id:'arbitrary-unapproved-model'}]});};
function request(path,body={},extra={}){return new Request(base+path,{method:'POST',headers:{Origin:base,'Content-Type':'application/json',...extra},body:JSON.stringify(body)});}
function fields(funding,key=crypto.randomUUID()){return {title:'Fixture title',brief:'Explain the supplied diagram for testing.',pages:5,style:'Designer choice',language:'en',requestKey:key,modelAccount:funding};}
function worker(path,body={},lease){return request(path,body,{Authorization:'Bearer '+token,...(lease?{'X-Job-Lease':lease}:{})});}
function params(id){return {params:Promise.resolve({id})};}
try{
 user=null;assert.equal((await accounts.GET()).status,401);assert.equal((await accounts.POST(request('/api/model-accounts',{}))).status,401);
 user='alice';assert.equal((await accounts.POST(request('/api/model-accounts',{}, {Origin:'https://evil.test'}))).status,403);
 assert.equal((await accounts.POST(request('/api/model-accounts',{provider:'custom',label:'test',apiKey:fakeKey,base_url:'https://evil.test'}))).status,400);assert.equal(providerCalls.length,0);
 let r=await accounts.POST(request('/api/model-accounts',{provider:'deepseek',label:'My DeepSeek',apiKey:fakeKey}));assert.equal(r.status,201);const a=await r.json();
 assert.deepEqual(a.models,['deepseek-flash']);assert.equal(a.keyHint,'••••1234');assert.equal(providerCalls[0].url,'https://api.deepseek.com/models');
 const row=db.prepare('SELECT * FROM model_accounts WHERE id=?').get(a.id);
 assert.ok(!JSON.stringify(row).includes(fakeKey));assert.match(row.secret,/^v1\./);
 assert.equal(await openKey(row.secret,a.id,'alice','deepseek'),fakeKey);
 for(const args of [[row.secret,a.id,'bob','deepseek'],[row.secret,a.id,'alice','openai'],[row.secret,crypto.randomUUID(),'alice','deepseek']])await assert.rejects(()=>openKey(...args));
 const changed=row.secret.slice(0,-2)+(row.secret.at(-2)==='A'?'B':'A')+row.secret.at(-1);await assert.rejects(()=>openKey(changed,a.id,'alice','deepseek'));
 const other=await sealKey(fakeKey,a.id,'alice','deepseek');assert.notEqual(other,row.secret,'Nonces must differ');
 r=await accounts.GET();const listed=await r.json();assert.equal(listed.enabled,true);assert.equal(listed.accounts.length,1);assert.ok(!JSON.stringify(listed).includes(fakeKey));assert.ok(!JSON.stringify(listed).includes(row.secret));
 user='bob';assert.equal((await (await accounts.GET()).json()).accounts.length,0);
 const funding={credentialId:a.id,model:'deepseek-flash'};
 assert.equal((await submit(request('/api/jobs',fields(funding)))).status,400,'Cannot spend another user key');
 assert.equal((await disconnect(new Request(base+'/api/model-accounts/'+a.id,{method:'DELETE',headers:{Origin:base}}),params(a.id))).status,404);
 user='alice';assert.equal((await submit(request('/api/jobs',fields({...funding,base_url:'https://evil.test'})))).status,400);
 assert.equal((await submit(request('/api/jobs',fields({...funding,model:'unapproved'})))).status,400);
 const idempotency=crypto.randomUUID();r=await submit(request('/api/jobs',fields(funding,idempotency)));assert.equal(r.status,201);const job=await r.json();assert.equal(job.execution_backend,'api');
 assert.equal(db.prepare('SELECT COUNT(*) n FROM task_funding WHERE job_id=?').get(job.id).n,1);
 assert.equal((await submit(request('/api/jobs',fields(funding,idempotency)))).status,200);
 assert.equal((await submit(request('/api/jobs',fields(null,idempotency)))).status,409,'Retries cannot change who pays');
 assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs WHERE user_id=?').get(user).n,1);
 assert.equal((await (await claim(worker('/api/worker',{execution_backends:['api','codex']}))).json()).job,null,'Old worker cannot consume customer work');
 const claimed=(await (await claim(worker('/api/worker',{execution_backends:['codex'],funding_version:1}))).json()).job;
 assert.equal(claimed.id,job.id);assert.equal(claimed.funding_mode,'user_api');assert.ok(!JSON.stringify(claimed).includes(fakeKey));
 assert.equal((await profile(request('/api/worker/'+job.id+'/model-profile'),params(job.id))).status,401);
 assert.equal((await profile(worker('/api/worker/'+job.id+'/model-profile',{},'wrong-lease'),params(job.id))).status,409);
 r=await profile(worker('/api/worker/'+job.id+'/model-profile',{},claimed.lease),params(job.id));assert.equal(r.status,200);const secretResult=await r.json();assert.equal(secretResult.apiKey,fakeKey);assert.equal(secretResult.funding.credentialId,a.id);assert.equal(r.headers.get('cache-control'),'private, no-store');
 const rotatedKey='sk-synthetic-rotated-customer-key-5678';
 r=await accounts.POST(request('/api/model-accounts',{provider:'deepseek',label:'New Key',apiKey:rotatedKey,replaceId:a.id}));assert.equal(r.status,201);assert.equal((await r.json()).id,a.id);
 r=await profile(worker('/api/worker/'+job.id+'/model-profile',{},claimed.lease),params(job.id));assert.equal((await r.json()).apiKey,rotatedKey);assert.equal(db.prepare('SELECT credential_id FROM task_funding WHERE job_id=?').get(job.id).credential_id,a.id);
 user='bob';assert.equal((await accounts.POST(request('/api/model-accounts',{provider:'deepseek',label:'Invalid replacement',apiKey:rotatedKey,replaceId:a.id}))).status,404);user='alice';
 // Failure between job and funding rolls both back; no unbound API admission.
 db.exec("CREATE TRIGGER reject_funding BEFORE INSERT ON task_funding BEGIN SELECT RAISE(ABORT,'fixture failure');END;");
 const before=db.prepare('SELECT COUNT(*) n FROM jobs').get().n;
 assert.equal((await submit(request('/api/jobs',fields(funding)))).status,503);assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs').get().n,before);
 db.exec('DROP TRIGGER reject_funding');
 lostAcknowledgement=true;const lostKey=crypto.randomUUID();r=await submit(request('/api/jobs',fields(funding,lostKey)));assert.equal(r.status,201);const recovered=await r.json();assert.ok(db.prepare('SELECT * FROM task_funding WHERE job_id=?').get(recovered.id));assert.equal((await submit(request('/api/jobs',fields(funding,lostKey)))).status,200);
 r=await disconnect(new Request(base+'/api/model-accounts/'+a.id,{method:'DELETE',headers:{Origin:base}}),params(a.id));assert.equal(r.status,200);
 assert.equal(db.prepare('SELECT secret FROM model_accounts WHERE id=?').get(a.id).secret,'');
 for(const id of [job.id,recovered.id])assert.equal(db.prepare('SELECT status FROM jobs WHERE id=?').get(id).status,'paused');
 assert.equal((await profile(worker('/api/worker/'+job.id+'/model-profile',{},claimed.lease),params(job.id))).status,409);
 assert.equal((await resume(request('/api/jobs/'+job.id+'/resume',{expectedUpdatedAt:db.prepare('SELECT updated_at FROM jobs WHERE id=?').get(job.id).updated_at}),params(job.id))).status,409);
 assert.equal((await submit(request('/api/jobs',fields(funding)))).status,400);
 assert.equal((await (await accounts.GET()).json()).accounts.length,0);
 env.BYOK_ENCRYPTION_KEY=undefined;assert.equal((await accounts.POST(request('/api/model-accounts',{provider:'deepseek',label:'test',apiKey:fakeKey}))).status,503);
 console.log('PASS: real routes; per-user ownership; fixed origins/models; encrypted authenticated storage; private leased credential release; atomic admission; retry billing identity; rollback/lost acknowledgement; legacy worker isolation; disconnect pauses and clears secrets; no fallback.');
}finally{globalThis.fetch=originalFetch;db.close();}
