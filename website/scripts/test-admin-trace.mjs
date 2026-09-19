// Real authorization and route handlers with isolated SQLite/R2; never production.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as limits from '../lib/slide-limits.mjs';
const modules={'./slide-limits.mjs':limits,'@/lib/slide-limits.mjs':limits};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
const db=new DatabaseSync(':memory:');
db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,attachments TEXT,status TEXT,result_key TEXT,lease TEXT);');
const binding={prepare(sql){let args=[];const s={bind(...v){args=v;return s;},async first(){return db.prepare(sql).get(...args)??null;}};return s;}};
const objects=new Map();let failIndex=false,reads=0;
const storage={async put(key,data){if(failIndex&&key.endsWith('/index.json')){failIndex=false;throw Error('index write unavailable');}objects.set(key,typeof data==='string'?data:new TextDecoder().decode(data));},async get(key){reads++;const text=objects.get(key);return text===undefined?null:{text:async()=>text,json:async()=>JSON.parse(text),body:new Response(text).body};}};
const token='synthetic-worker-credential-at-least-32-chars';let user=null;
modules['cloudflare:workers']={env:{DB:binding,FILES:storage,WORKER_TOKEN:token,ADMIN_USER_ID:'rick'}};
modules['@/app/chatgpt-auth']={getChatGPTUser:async()=>user};
modules['./admin-policy']=load('lib/admin-policy.ts');
for(const name of ['server','admin','attachments','progress','queries','admin-trace']){modules['@/lib/'+name]=load('lib/'+name+'.ts');modules['./'+name]=modules['@/lib/'+name];}
const post=load('app/api/worker/[id]/route.ts').POST,get=load('app/api/admin/jobs/[id]/trace/route.ts').GET;
const id=crypto.randomUUID();db.prepare('INSERT INTO jobs VALUES(?,?,?,?,?,?)').run(id,'owner','[]','running',null,'lease-one');
const params={params:Promise.resolve({id})};
const event=n=>({seq:n,at:n,stage:'research',kind:'command',label:'Shell command',state:'completed',command:'python inspect.py',output:'30 slides',exitCode:0});
const batch=(n,e=event(n))=>({version:1,chunk:n,events:[e]});
const request=(body,{lease='lease-one',secret=token}={})=>post(new Request(`https://local.test/api/worker/${id}?action=trace`,{method:'POST',headers:{Authorization:'Bearer '+secret,'X-Job-Lease':lease},body:JSON.stringify(body)}),params);
const read=(after=0)=>get(new Request(`https://local.test/api/admin/jobs/${id}/trace?after=${after}`),params);
assert.equal((await read()).status,401);assert.equal(reads,0);
user={userId:'owner',email:'owner@test'};assert.equal((await read()).status,403);assert.equal(reads,0);
user={userId:'rick',email:'rick@test'};assert.equal((await (await read()).json()).available,false);
assert.equal((await request(batch(1),{secret:'wrong'})).status,401);
assert.equal((await request(batch(1),{lease:'expired'})).status,409);
assert.equal((await request(batch(1,{...event(1),kind:'reasoning',detail:'PRIVATE_CHAIN'}))).status,400);
const first=batch(1,{...event(1),output:`token=${token}\nAuthorization: Bearer another-private-token\nnormal output`,reasoning:'PRIVATE_CHAIN'});
assert.equal((await request(first)).status,200);
assert.equal((await request(first)).status,200);
assert.equal((await request(batch(1))).status,409);
assert.equal((await request(batch(3))).status,409);
const firstRead=await (await read()).json();assert.equal(firstRead.totalEvents,1);assert.equal(firstRead.events.length,1);
const serialized=JSON.stringify(firstRead);for(const secret of [token,'another-private-token','PRIVATE_CHAIN','lease-one'])assert.ok(!serialized.includes(secret));
assert.ok(serialized.includes('normal output'));
// A persisted chunk whose index write failed is repaired by an identical retry.
failIndex=true;await assert.rejects(()=>request(batch(2)));
assert.equal((await request(batch(2))).status,200);
for(let n=3;n<=7;n++)assert.equal((await request(batch(n))).status,200);
const page1=await (await read()).json(),page2=await (await read(page1.nextChunk)).json();
assert.equal(page1.events.length,5);assert.equal(page2.events.length,2);assert.equal(page2.nextChunk,7);
assert.deepEqual([...page1.events,...page2.events].map(e=>e.seq),[1,2,3,4,5,6,7]);
assert.equal((await read('../other')).status,400);
assert.equal((await request({version:1,chunk:8,events:[{...event(8),output:'x'.repeat(100001)}]})).status,400);
db.prepare("UPDATE jobs SET status='complete'").run();assert.equal((await request(batch(8,{...event(8),stage:'finished'}))).status,200);
assert.equal((await (await read()).json()).totalEvents,8);
assert.equal((await (await read()).json()).finished,true);
// A retried task uses a different lease and cannot expose/overwrite the previous attempt.
db.prepare("UPDATE jobs SET status='running',lease='lease-two'").run();
assert.equal((await (await read()).json()).available,false);
assert.equal((await request(batch(8))).status,409);
assert.equal((await request(batch(1),{lease:'lease-two'})).status,200);
assert.notEqual((await (await read()).json()).attempt,firstRead.attempt);
user={userId:'owner',email:'owner@test'};assert.equal((await read()).status,403);
console.log('PASS: admin-only reads, worker/lease writes, reasoning exclusion, credential scrubbing, bounded records, retry recovery, pagination and attempt isolation');
