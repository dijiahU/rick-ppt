import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as jsx from 'react/jsx-runtime';
import {renderToStaticMarkup} from 'react-dom/server';
const db=new DatabaseSync(':memory:');db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,status TEXT,lease TEXT,updated_at INTEGER,result_key TEXT);');db.exec(readFileSync(new URL('../drizzle/0015_progress_drafts.sql',import.meta.url),'utf8'));
let user='owner',afterPut=null;const objects=new Map();
const binding={prepare(sql){let args=[];return {bind(...v){args=v;return this;},async first(){return db.prepare(sql).get(...args)??null;},async run(){return {meta:db.prepare(sql).run(...args)};}};}};
const modules={'@/lib/server':{database:()=>binding,files:()=>({async put(k,b){objects.set(k,b.slice());if(afterPut){const f=afterPut;afterPut=null;f();}},async get(k){return objects.has(k)?{body:objects.get(k)}:null;}}),json:(v,s=200)=>Response.json(v,{status:s}),userId:async()=>user,workerAuthorized:async r=>r.headers.get('Authorization')==='Bearer synthetic-worker'},'@/lib/admin':{adminGate:async()=>user==='admin'?null:Response.json({}, {status:403})}};
function load(n){const code=ts.transpileModule(readFileSync(new URL('../'+n,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(n=>{assert.ok(modules[n],n);return modules[n];},exports);return exports;}
modules['@/lib/attachments']=load('lib/attachments.ts');modules['@/lib/drafts']=load('lib/drafts.ts');
const upload=load('app/api/worker/[id]/draft/route.ts').POST,download=load('app/api/jobs/[id]/draft/route.ts').GET,admin=load('app/api/admin/jobs/[id]/draft/route.ts').GET;
const id='task-a',params={params:Promise.resolve({id})};db.prepare('INSERT INTO jobs VALUES (?,?,?,?,?,?)').run(id,'owner','running','lease-a',100,null);
const bytes=new Uint8Array(30);bytes.set([80,75,3,4]);
const sha=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b))).map(v=>v.toString(16).padStart(2,'0')).join('');
async function send({body=bytes,lease='lease-a',token='synthetic-worker',revision=1,time=1000,expected=null,hash=null}={}){const query=new URLSearchParams({sha256:hash??await sha(body),pages:'2',revision:String(revision),exportedAt:String(time)});if(expected!==null)query.set('expectedUpdatedAt',expected);return upload(new Request('https://test.local/api/worker/'+id+'/draft?'+query,{method:'POST',headers:{Authorization:'Bearer '+token,...(lease?{'X-Job-Lease':lease}:{})},body}),params);}
const get=()=>download(new Request('https://test.local'),params);
assert.equal((await get()).status,404);assert.equal((await send({token:'wrong'})).status,401);assert.equal((await send({lease:'old'})).status,409);assert.equal(objects.size,0);
assert.equal((await send({hash:'0'.repeat(64)})).status,400);assert.equal((await send({body:new Uint8Array(30)})).status,400);assert.equal((await send({revision:-1})).status,400);
assert.equal((await send()).status,200);const original=db.prepare('SELECT * FROM task_drafts').get();assert.equal((await send()).status,200);assert.deepEqual(db.prepare('SELECT * FROM task_drafts').get(),original);
const copy=await get();assert.equal(copy.status,200);assert.deepEqual(new Uint8Array(await copy.arrayBuffer()),bytes);assert.equal(copy.headers.get('X-Presentation-Status'),'unreviewed-progress');assert.match(copy.headers.get('Content-Disposition'),/unreviewed/);
user='other';assert.equal((await get()).status,404);user=null;assert.equal((await get()).status,401);user='owner';assert.equal((await admin(new Request('https://test.local'),params)).status,403);
const newer=bytes.slice();newer[20]=3;assert.equal((await send({body:newer,time:2000})).status,200);assert.equal((await send()).status,200);assert.equal(db.prepare('SELECT sha256 FROM task_drafts').get().sha256,await sha(newer));
for(const status of ['failed','queued','complete']){db.prepare('UPDATE jobs SET status=?').run(status);assert.equal((await get()).status,200);assert.equal((await send({time:3000})).status,409);}
db.prepare("UPDATE jobs SET status='failed'").run();assert.equal((await send({lease:null,expected:99,time:3000})).status,409);assert.equal((await send({lease:null,expected:100,time:3000})).status,200);assert.equal(db.prepare('SELECT status FROM jobs').get().status,'failed');
db.prepare("UPDATE jobs SET status='running'").run();afterPut=()=>db.prepare("UPDATE jobs SET lease='lease-b'").run();assert.equal((await send({time:4000})).status,409);assert.equal(db.prepare('SELECT exported_at FROM task_drafts').get().exported_at,3000);
assert.equal(db.prepare('SELECT result_key FROM jobs').get().result_key,null);assert.ok(objects.size>=2);user='admin';assert.equal((await admin(new Request('https://test.local'),params)).status,200);
console.log('PASS: draft ownership/admin, no-export state, auth, lease races, SHA/size metadata, immutable versions, stale ordering, idempotency, failed/queued/complete downloads, exact failed-attempt backfill and unchanged final delivery.');

modules['react/jsx-runtime']=jsx;const View=load('app/jobs/[id]/draft-download.tsx').default;
for(const locale of ['zh-CN','en','fr','es','ja']){
 const html=renderToStaticMarkup(jsx.jsx(View,{draft:{pages:12,saved_at:1000},base:'/api/jobs/task-a',locale}));assert.ok(html.includes('/api/jobs/task-a/draft'));assert.ok(html.includes('12'));
 const empty=renderToStaticMarkup(jsx.jsx(View,{draft:null,base:'/api/jobs/task-a',locale}));assert.ok(!empty.includes('href='));
}
console.log('PASS: five-language progress-download and no-export states render with the task-scoped link.');
