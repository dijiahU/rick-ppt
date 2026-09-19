import * as slideLimits from '../lib/slide-limits.mjs';
// Execute the real route handlers against isolated SQLite and an in-memory R2 adapter.
// No real user records, website quota, secrets, or production requests.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
const modules={};
modules['./slide-limits.mjs']=slideLimits;modules['@/lib/slide-limits.mjs']=slideLimits;
function load(path){const source=readFileSync(new URL('../'+path,import.meta.url),'utf8');const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
modules['@/lib/attachments']=load('lib/attachments.ts');
modules['@/lib/page-count-i18n']=load('lib/page-count-i18n.ts');modules['@/lib/task-mode']=load('lib/task-mode.ts');modules['@/lib/task-mode-i18n']=load('lib/task-mode-i18n.ts');
modules['@/lib/admin']={isAdmin:async()=>false};
modules['@/lib/i18n']=load('lib/i18n.ts');modules['@/lib/upload-i18n']=load('lib/upload-i18n.ts');modules['@/lib/queries']=load('lib/queries.ts');modules['@/lib/progress']=load('lib/progress.ts');
const db=new DatabaseSync(':memory:');
db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,request_key TEXT,title TEXT,brief TEXT,pages INTEGER,style TEXT,language TEXT,attachments TEXT,status TEXT,created_at INTEGER,updated_at INTEGER,lease TEXT,summary TEXT,result_key TEXT,progress TEXT,UNIQUE(user_id,request_key));CREATE TABLE worker(id TEXT PRIMARY KEY,heartbeat INTEGER);');
let currentUser='owner',failPut=false;const objects=new Map();
const binding={prepare(sql){let args=[];const statement={bind(...values){args=values;return statement;},async first(){return db.prepare(sql).get(...args)??null;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){const result=db.prepare(sql).run(...args);return {meta:{changes:Number(result.changes)}};}};return statement;},async batch(statements){return Promise.all(statements.map(s=>s.run()));}};
modules['@/lib/server']={database:()=>binding,files:()=>({async put(key,data){objects.set(key,new Uint8Array(data));if(failPut)throw Error('simulated partial R2 failure');},async get(key){const data=objects.get(key);return data?{body:new Response(data).body}:null;},async delete(keys){for(const key of Array.isArray(keys)?keys:[keys])objects.delete(key);}}),json:(v,status=200)=>Response.json(v,{status}),userId:async()=>currentUser,sameOrigin:r=>r.headers.get('Origin')===new URL(r.url).origin,workerAuthorized:async r=>r.headers.get('Authorization')==='Bearer local-test-token'};
modules['@/lib/admin-trace']=load('lib/admin-trace.ts');
const submit=load('app/api/jobs/route.ts').POST,download=load('app/api/jobs/[id]/attachments/[file]/route.ts').GET,worker=load('app/api/worker/[id]/route.ts').POST;
function request({key=crypto.randomUUID(),files=[new File(['Café reference material'],'référence.txt')],origin='https://local.test'}={}){const form=new FormData();for(const [k,v] of Object.entries({title:'Test attachment',brief:'Use these references for a French deck.',pages:'5',style:'Designer choice',language:'fr',requestKey:key}))form.set(k,v);for(const file of files)form.append('files',file);return new Request('https://local.test/api/jobs',{method:'POST',headers:{Origin:origin,'X-UI-Language':'fr'},body:form});}
currentUser=null;assert.equal((await submit(request())).status,401);currentUser='owner';assert.equal((await submit(request({origin:'https://evil.test'}))).status,403);
assert.equal((await submit(request({files:[new File(['x'],'bad.exe')]}))).status,400);
assert.equal((await submit(request({files:[new File(['fake PDF'],'fake.pdf')]}))).status,400);
assert.equal((await submit(request({files:[new File([],'empty.txt')]}))).status,400);
assert.equal((await submit(request({files:Array.from({length:4},()=>new File(['x'],'x.txt'))}))).status,400);
assert.equal((await submit(request({files:[new File([new Uint8Array(10*1024*1024+1)],'large.png')]}))).status,400);
const key=crypto.randomUUID();const accepted=await submit(request({key}));assert.equal(accepted.status,201);const {id}=await accepted.json();
const row=db.prepare('SELECT * FROM jobs WHERE id=?').get(id),meta=JSON.parse(row.attachments)[0];assert.equal(row.language,'fr');assert.equal(meta.name,'référence.txt');assert.equal(meta.size,new TextEncoder().encode('Café reference material').length);assert.equal(objects.size,1);
const replay=await submit(request({key}));assert.equal((await replay.json()).id,id);assert.equal(objects.size,1);
const params={params:Promise.resolve({id,file:meta.id})};
currentUser='other';assert.equal((await download(new Request('https://local.test'),params)).status,404);
currentUser=null;assert.equal((await download(new Request('https://local.test'),params)).status,401);
currentUser='owner';const own=await download(new Request('https://local.test'),params);assert.equal(await own.text(),'Café reference material');assert.equal(own.headers.get('Content-Type'),'application/octet-stream');assert.ok(own.headers.get('Content-Disposition').startsWith('attachment;'));assert.ok(own.headers.get('Cache-Control').includes('no-store'));assert.equal(own.headers.get('X-Content-Type-Options'),'nosniff');
function workerRequest(lease='lease',authorized=true,file=meta.id){return new Request('https://local.test/api/worker/'+id+'?action=attachment&file='+file,{method:'POST',headers:{'X-Job-Lease':lease,...(authorized?{Authorization:'Bearer local-test-token'}:{})}});}
const workerParams={params:Promise.resolve({id})};
assert.equal((await worker(workerRequest(),workerParams)).status,409);
db.prepare("UPDATE jobs SET status='running',lease='lease' WHERE id=?").run(id);
assert.equal((await worker(workerRequest('lease',false),workerParams)).status,401);
assert.equal((await worker(workerRequest('wrong'),workerParams)).status,409);
assert.equal((await worker(workerRequest('lease',true,crypto.randomUUID()),workerParams)).status,404);
assert.equal(await (await worker(workerRequest(),workerParams)).text(),'Café reference material');
db.prepare("UPDATE jobs SET status='complete' WHERE id=?").run(id);
assert.equal((await worker(workerRequest(),workerParams)).status,409);
// Competing retries must leave just one job and its own one object.
const concurrentKey=crypto.randomUUID();const results=await Promise.all(Array.from({length:4},()=>submit(request({key:concurrentKey}))));const ids=await Promise.all(results.map(r=>r.json()));assert.equal(new Set(ids.map(x=>x.id)).size,1);assert.equal(objects.size,2);
// A partial object write must not charge quota or leave an unlinked object.
failPut=true;assert.equal((await submit(request())).status,503);failPut=false;assert.equal(objects.size,2);assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs').get().n,2);
// JSON-only legacy submissions still work.
const jsonRequest=new Request('https://local.test/api/jobs',{method:'POST',headers:{Origin:'https://local.test','Content-Type':'application/json'},body:JSON.stringify({title:'Legacy',brief:'No attachments here.',pages:5,style:'test',requestKey:crypto.randomUUID()})});assert.equal((await submit(jsonRequest)).status,201);
// Count quota exactly once for every accepted task, not per attachment.
for(let i=3;i<10;i++)assert.equal((await submit(request({files:[]}))).status,201);
assert.equal((await submit(request())).status,429);assert.equal(objects.size,2);
const {boundedBody,parseAttachments}=modules['@/lib/attachments'];assert.deepEqual(parseAttachments('[{}]'),[]);assert.deepEqual(parseAttachments(JSON.stringify([meta,meta])),[]);
await assert.rejects(()=>boundedBody(new Request('https://local.test',{method:'POST',body:'123456'}),5));
console.log('PASS: real multipart handlers, file validation/limits, private downloads, lease isolation, concurrent retry cleanup, storage-failure rollback, JSON compatibility and quota');
// Mode-specific requests use a separate synthetic account, never production.
currentUser='mode-test';
const pptx=()=>new File([new Uint8Array([80,75,3,4,0,0,0,0])],'original.pptx');
function modeRequest(mode,files=[],pages,key=crypto.randomUUID()){
 const form=new FormData();for(const [k,v] of Object.entries({title:'Mode test',brief:'Change slide two and add a conclusion.',style:'Designer choice',language:'en',requestKey:key,mode}))form.set(k,v);
 if(pages!==undefined)form.set('pages',String(pages));for(const f of files)form.append('files',f);
 return new Request('https://local.test/api/jobs',{method:'POST',headers:{Origin:'https://local.test'},body:form});
}
assert.equal((await submit(modeRequest('create',[]))).status,400);
assert.equal((await submit(modeRequest('create',[],0))).status,400);
assert.equal((await submit(modeRequest('unknown',[],5))).status,400);
assert.equal((await submit(modeRequest('edit'))).status,400);
assert.equal((await submit(modeRequest('edit',[new File(['reference'],'reference.txt')]))).status,400);
assert.equal((await submit(modeRequest('edit',[pptx(),pptx()]))).status,400);
assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs WHERE user_id=?').get(currentUser).n,0);
const editKey=crypto.randomUUID();
const edit=await submit(modeRequest('edit',[pptx()],15,editKey));assert.equal(edit.status,201);const editId=(await edit.json()).id;
assert.equal(db.prepare('SELECT pages FROM jobs WHERE id=?').get(editId).pages,0);
assert.equal((await (await submit(modeRequest('edit',[],undefined,editKey))).json()).id,editId);
const create=await submit(modeRequest('create',[],10));assert.equal(create.status,201);
const noCount=await submit(modeRequest('edit',[pptx()]));assert.equal(noCount.status,201);
db.prepare("UPDATE jobs SET status='complete' WHERE id<>?").run(editId);
const claim=load('app/api/worker/route.ts').POST;
const claimed=await (await claim(new Request('https://local.test/api/worker',{method:'POST',headers:{Authorization:'Bearer local-test-token'}}))).json();
assert.equal(claimed.job.id,editId);assert.equal(claimed.job.mode,'edit');assert.equal(claimed.job.pages,null);
assert.ok(claimed.job.brief.includes('There is no target slide count'));assert.ok(claimed.job.brief.includes('Change slide two'));
assert.ok(!db.prepare('SELECT brief FROM jobs WHERE id=?').get(editId).brief.includes('TASK MODE'));
console.log('PASS: create/edit validation, missing and multiple originals, ignored edit count, omitted count, retries, original brief preservation and actual worker claim payload');
// Every offered count survives both submission formats and the worker payload.
function countRequest(pages){return new Request('https://local.test/api/jobs',{method:'POST',headers:{Origin:'https://local.test','Content-Type':'application/json'},body:JSON.stringify({mode:'create',title:'Exact slide count',brief:'Create the exact requested number of slides.',pages,style:'test',requestKey:crypto.randomUUID()})});}
for(const format of ['multipart','json']){
 for(const pages of [1,10,15,16,30,50]){
  currentUser=`count-${format}-${pages}`;
  db.prepare("UPDATE jobs SET status='complete'").run();
  const response=await submit(format==='multipart'?modeRequest('create',[],pages):countRequest(pages));
  assert.equal(response.status,201,`${format}: ${pages} slides`);
  const {id}=await response.json();
  assert.equal(db.prepare('SELECT pages FROM jobs WHERE id=?').get(id).pages,pages);
  const payload=await (await claim(new Request('https://local.test/api/worker',{method:'POST',headers:{Authorization:'Bearer local-test-token'}}))).json();
  assert.equal(payload.job.id,id);assert.equal(payload.job.mode,'create');assert.equal(payload.job.pages,pages);
 }
}
currentUser='invalid-count-test';
for(const pages of [undefined,null,0,-1,51,1000,5.5,'6',true,{},[]])assert.equal((await submit(countRequest(pages))).status,400,`JSON rejects ${JSON.stringify(pages)}`);
for(const pages of [undefined,'',0,-1,51,1000,5.5,'six'])assert.equal((await submit(modeRequest('create',[],pages))).status,400,`multipart rejects ${pages}`);
assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs WHERE user_id=?').get(currentUser).n,0);
console.log('PASS: counts through 50 through multipart/JSON, database and worker payload; invalid counts rejected without charging quota');

// Conflicting form fallback is resolved BEFORE quota/storage admission.
for(const format of ['multipart','json']){
 currentUser=`brief-count-${format}`;
 const brief='请制作30页的中国历史介绍，面向初学者。';
 const fields={mode:'create',title:'历史课件',brief,pages:15,language:'zh-CN',style:'test',requestKey:crypto.randomUUID()};
 const form=new FormData();for(const [key,value] of Object.entries(fields))form.set(key,String(value));
 db.prepare("UPDATE jobs SET status='complete'").run();
 const req=new Request('https://local.test/api/jobs',{method:'POST',headers:{Origin:'https://local.test',...(format==='json'?{'Content-Type':'application/json'}:{})},body:format==='json'?JSON.stringify(fields):form});
 const response=await submit(req);assert.equal(response.status,201);const {id}=await response.json();
 const saved=db.prepare('SELECT pages,brief FROM jobs WHERE id=?').get(id);assert.equal(saved.pages,30);assert.equal(saved.brief,brief);
 const job=(await (await claim(new Request('https://local.test/api/worker',{method:'POST',headers:{Authorization:'Bearer local-test-token'}}))).json()).job;
 assert.equal(job.id,id);assert.equal(job.pages,30);
 const params={params:Promise.resolve({id})};
 const post=async(action,body)=>worker(new Request(`https://local.test/api/worker/${id}?${action}`,{method:'POST',headers:{Authorization:'Bearer local-test-token','X-Job-Lease':job.lease,'Content-Length':String(Buffer.byteLength(body))},body}),params);
 const png=new Uint8Array([137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,0,0,0,1,0,0,0,1]);
 assert.equal((await post('action=preview&slide=30',png)).status,200);
 assert.equal((await post('action=preview&slide=51',png)).status,400);
 const progress={updatedAt:1,events:[],previews:[30],previewVersions:{30:'0123456789abcdef'},outline:{revision:'0123456789abcdef',title:'历史课件',purpose:'学习历史',slides:Array.from({length:30},(_,i)=>({id:`s${i+1}`,title:`主题 ${i+1}`,summary:'历史事件及其原因'}))}};
 assert.equal((await post('action=progress',JSON.stringify(progress))).status,200);
 const preview=load('app/api/jobs/[id]/preview/[slide]/route.ts').GET;
 const previewParams={params:Promise.resolve({id,slide:'30'})};
 assert.equal((await preview(new Request('https://local.test'),previewParams)).status,200);
 const owner=currentUser;currentUser='other-viewer';assert.equal((await preview(new Request('https://local.test'),previewParams)).status,404);currentUser=owner;
 modules['@/lib/admin'].adminGate=async()=>currentUser==='admin'?null:Response.json({error:'Forbidden'},{status:403});
 const adminPreview=load('app/api/admin/jobs/[id]/preview/[slide]/route.ts').GET;
 assert.equal((await adminPreview(new Request('https://local.test'),previewParams)).status,403);
 currentUser='admin';assert.equal((await adminPreview(new Request('https://local.test'),previewParams)).status,200);
}
currentUser='ambiguous-count';
for(const brief of ['请制作20页，再做30页的完整课件。','请制作20到30页的完整课件。','请制作51页的完整课件。']){
 const response=await submit(new Request('https://local.test/api/jobs',{method:'POST',headers:{Origin:'https://local.test','Content-Type':'application/json'},body:JSON.stringify({mode:'create',title:'页数冲突',brief,pages:15,style:'test',requestKey:crypto.randomUUID()})}));
 assert.equal(response.status,400);assert.ok(['pagesAmbiguous','pagesRange'].includes((await response.json()).code));
}
assert.equal(db.prepare('SELECT COUNT(*) n FROM jobs WHERE user_id=?').get(currentUser).n,0);
console.log('PASS: brief 30 overrides input 15 in both formats; original brief preserved; worker, outline, page-30 upload and private/admin retrieval agree; invalid totals consume no quota');
