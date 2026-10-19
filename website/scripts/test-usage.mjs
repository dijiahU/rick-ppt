// Isolated SQLite + real worker/admin auth and handlers. No production requests.
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as limits from '../lib/slide-limits.mjs';
const modules={'./slide-limits.mjs':limits,'@/lib/slide-limits.mjs':limits};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
const db=new DatabaseSync(':memory:');
db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,lease TEXT,status TEXT);');
const binding={prepare(sql){let args=[];const s={bind(...v){args=v;return s;},async first(){return db.prepare(sql).get(...args)??null;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){const r=db.prepare(sql).run(...args);return {meta:{changes:Number(r.changes)}};}};return s;},async batch(rows){db.exec('BEGIN');try{const result=[];for(const r of rows)result.push(await r.run());db.exec('COMMIT');return result;}catch(e){db.exec('ROLLBACK');throw e;}}};
let user=null;const secret='fixture-worker-secret-at-least-32-chars';
modules['cloudflare:workers']={env:{DB:binding,WORKER_TOKEN:secret,ADMIN_USER_ID:'rick'}};
modules['@/app/chatgpt-auth']={getChatGPTUser:async()=>user};
modules['./admin-policy']=load('lib/admin-policy.ts');
for(const name of ['execution-backend','admin-accounts'])if(existsSync(new URL('../lib/'+name+'.ts',import.meta.url)))modules['./'+name]=load('lib/'+name+'.ts');
for(const name of ['server','admin','attachments','usage']){modules['@/lib/'+name]=load('lib/'+name+'.ts');modules['./'+name]=modules['@/lib/'+name];}
const post=load('app/api/worker/[id]/usage/route.ts').POST,get=load('app/api/admin/jobs/[id]/usage/route.ts').GET;
const id=crypto.randomUUID(),other=crypto.randomUUID();
db.prepare('INSERT INTO jobs VALUES(?,?,?,?)').run(id,'owner','lease-one','running');
db.prepare('INSERT INTO jobs VALUES(?,?,?,?)').run(other,'other-owner','other-lease','running');
const row=(overrides={})=>({id:'a'.repeat(64),attempt:'b'.repeat(16),stage:'author',source:'api',provider:'provider.invalid',model:'test-model',protocol:'responses',usageStatus:'reported',at:100,version:1,serviceTier:'default',outcome:'completed',inputTokens:1000,cachedInputTokens:400,cacheWriteTokens:100,outputTokens:200,reasoningTokens:50,totalTokens:1200,costMicrousd:3050,costSource:'configured_rate',priceVersion:'contract-v1',priceSnapshot:{inputUsdPerMillion:'2',cachedInputUsdPerMillion:'0.5',cacheWriteUsdPerMillion:'2.5',outputUsdPerMillion:'8'},...overrides});
const write=(records,{token=secret,lease='lease-one',job=id}={})=>post(new Request(`https://local.test/api/worker/${job}/usage`,{method:'POST',headers:{Authorization:'Bearer '+token,'X-Job-Lease':lease},body:JSON.stringify({version:1,records})}),{params:Promise.resolve({id:job})});
const read=(job=id,query='')=>get(new Request(`https://local.test/api/admin/jobs/${job}/usage${query}`),{params:Promise.resolve({id:job})});
assert.equal((await read()).status,401);
user={userId:'owner'};assert.equal((await read()).status,403);
assert.equal((await write([row()],{token:'wrong'})).status,401);
assert.equal((await write([row()],{lease:'expired'})).status,409);
assert.equal(db.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE name='task_usage'").get().n,0,'authorization before storage creation');
assert.equal((await write([row()])).status,200);
assert.equal((await write([row()])).status,200,'lost acknowledgement replay');
assert.equal((await write([row({totalTokens:999})])).status,400);
assert.equal((await write([row({inputTokens:2000,totalTokens:2200})])).status,409,'same-version conflict');
assert.equal((await write([row({version:2,inputTokens:900,totalTokens:1100})])).status,409,'cannot reduce usage');
assert.equal((await write([row({version:2,model:'other-model'})])).status,409,'cannot change model');
assert.equal((await write([row({version:2,attempt:'c'.repeat(16)})])).status,409,'cannot change attempt');
assert.equal((await write([row({requestId:secret})])).status,400,'never persist worker secret');
assert.equal((await write([row({requestId:'lease-one'})])).status,400,'never persist lease');
assert.equal((await write([row({source:'codex',protocol:'codex'})])).status,400,'local usage cannot claim API cost');
assert.equal((await write([row({inputTokens:1.1})])).status,400);
const local=row({id:'c'.repeat(64),source:'codex',protocol:'codex',costMicrousd:null,costSource:'not_api',priceVersion:null,priceSnapshot:null});
assert.equal((await write([local])).status,200);
assert.equal((await write([{...local,version:2,inputTokens:2000,totalTokens:2200}])).status,200);
assert.equal((await write([local])).status,200,'stale cumulative snapshot cannot replace newer');
const unknown=row({id:'d'.repeat(64),usageStatus:'unavailable',inputTokens:null,outputTokens:null,cachedInputTokens:null,cacheWriteTokens:null,reasoningTokens:null,totalTokens:null,costMicrousd:null,costSource:'unpriced',priceVersion:null,priceSnapshot:null,outcome:'unknown'});
assert.equal((await write([unknown])).status,200);
user={userId:'rick'};
let data=await (await read()).json();assert.equal(data.total,3);
assert.equal(data.groups.find(g=>g.source==='api').totalTokens,1200);
assert.equal(data.groups.find(g=>g.source==='api').costMicrousd,3050);
assert.equal(data.groups.find(g=>g.source==='api').unpricedCalls,1);
assert.equal(data.groups.find(g=>g.source==='codex').totalTokens,2200);
assert.equal(data.chargingEnabled,false);
assert.equal(JSON.stringify(data).includes('lease-one'),false);
assert.equal((await (await read(other)).json()).available,false);
assert.equal((await read(id,'?after=-1')).status,400);
// Resumption keeps all previous costs; old credentials cannot append to the task.
db.prepare("UPDATE jobs SET lease='lease-two',status='complete' WHERE id=?").run(id);
assert.equal((await write([row()])).status,409);
assert.equal((await write([row()],{lease:'lease-two'})).status,200,'recovery resends frozen old-attempt receipt');
assert.equal((await write([row({id:'e'.repeat(64),attempt:'f'.repeat(16)})],{lease:'lease-two'})).status,200,'late final usage accepted without changing job status');
data=await (await read()).json();assert.equal(data.total,4);assert.equal(data.groups.find(g=>g.source==='api').costMicrousd,6100);
assert.equal(db.prepare('SELECT status FROM jobs WHERE id=?').get(id).status,'complete');
user={userId:'owner'};assert.equal((await read()).status,403);
// Public endpoints never import the private ledger or SELECT its table.
for(const path of ['app/api/jobs/route.ts','app/api/jobs/[id]/progress/route.ts','app/api/jobs/[id]/conversation/route.ts']){
 const source=readFileSync(new URL('../'+path,import.meta.url),'utf8');assert.ok(!source.includes('@/lib/usage'));assert.ok(!source.includes('task_usage'));
}
console.log('PASS: private auth, per-job isolation, exact receipts, idempotent replay, cumulative snapshots, unknown usage, frozen costs, attempt recovery, late uploads and unchanged charging/public routes');
