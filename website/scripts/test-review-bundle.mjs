// Real review auth/routes and SQLite, fake isolated R2. No local secrets or network.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as limits from '../lib/slide-limits.mjs';
const modules={'./slide-limits.mjs':limits,'@/lib/slide-limits.mjs':limits};
function load(path){
 const source=readFileSync(new URL('../'+path,import.meta.url),'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;
}
const db=new DatabaseSync(':memory:');
db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,title TEXT,brief TEXT,pages INTEGER,style TEXT,language TEXT,status TEXT,created_at INTEGER,updated_at INTEGER,summary TEXT,progress TEXT,result_key TEXT);CREATE TABLE task_versions(id TEXT PRIMARY KEY,job_id TEXT,result_key TEXT,bundle_key TEXT,revision INTEGER,created_at INTEGER);');
let selects=0,gets=0,cancels=0,afterGet=null;
const binding={prepare(sql){assert.match(sql,/^SELECT /,'review must never write or initialize schema');let args=[];const statement={bind(...values){args=values;return statement;},async first(){selects++;return db.prepare(sql).get(...args)??null;}};return statement;}};
const objects=new Map();
const storage={
 async head(key){const object=objects.get(key);return object?{size:object.size??object.bytes.length,httpEtag:object.etag}:null;},
 async get(key){gets++;const object=objects.get(key);if(!object)return null;
  const body=new ReadableStream({start(controller){controller.enqueue(object.bytes);controller.close();},cancel(){cancels++;}});
  if(afterGet)await afterGet(key);
  return {size:object.size??object.bytes.length,httpEtag:object.etag,body};},
 async put(){throw Error('Read-only review must not write R2');},async delete(){throw Error('Read-only review must not delete R2');},
};
const REVIEW_TOKEN='synthetic-review-token-at-least-32-characters',WORKER_TOKEN='synthetic-worker-token-at-least-32-characters';
modules['cloudflare:workers']={env:{DB:binding,FILES:storage,REVIEW_TOKEN,WORKER_TOKEN}};
modules['@/app/chatgpt-auth']={getChatGPTUser:async()=>({userId:'ordinary-account'})};
for(const name of ['server','review-auth','review-bundle','progress']){
 modules['@/lib/'+name]=load('lib/'+name+'.ts');modules['./'+name]=modules['@/lib/'+name];
}
const detail=load('app/api/review/jobs/[id]/route.ts').GET;
const pptx=load('app/api/review/jobs/[id]/pptx/route.ts').GET;
const bundleModule=load('app/api/review/jobs/[id]/bundle/route.ts'),bundle=bundleModule.GET;
assert.deepEqual(Object.keys(bundleModule).sort(),['GET','dynamic']);
const header='X-Review-Delivery';
function seed({status='complete',withVersion=true,withBundle=true}={}){
 const id=crypto.randomUUID(),version=crypto.randomUUID();
 const pptxKey=`results/${id}/${version}.pptx`,bundleKey=`bundles/${id}/${version}.zip`;
 db.prepare('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)').run(id,'owner','Title','Original untrusted brief',20,'technical','en',status,1,2,'complete','null',pptxKey);
 if(withVersion)db.prepare('INSERT INTO task_versions VALUES(?,?,?,?,?,?)').run(version,id,pptxKey,withBundle?bundleKey:null,3,5);
 objects.set(pptxKey,{bytes:new TextEncoder().encode('PK-original-pptx'),etag:'"pptx-a"'});
 if(withBundle)objects.set(bundleKey,{bytes:new Uint8Array([80,75,3,4,10,20,30,40]),etag:'"bundle-a"'});
 return {id,version,pptxKey,bundleKey};
}
function call(route,id,{token=REVIEW_TOKEN,include=false,method='GET',headers={}}={}){
 return route(new Request(`https://local.test/api/review/jobs/${id}${include?'?include=bundle':''}`,{method,headers:{...(token?{Authorization:'Bearer '+token}:{}),...headers}}),{params:Promise.resolve({id})});
}
const fixture=seed(),before=JSON.stringify(db.prepare('SELECT * FROM jobs').all());
for(const token of [null,'wrong-token',WORKER_TOKEN]){
 const count=selects;
 for(const route of [detail,pptx,bundle])assert.equal((await call(route,fixture.id,{token,headers:{Cookie:'__sites_local_auth=1'}})).status,401);
 assert.equal(selects,count,'unauthorized requests must not read task data');
}
for(const method of ['HEAD','POST','PUT','PATCH','DELETE'])assert.equal((await call(bundle,fixture.id,{method})).status,405);
assert.equal((await call(bundle,crypto.randomUUID())).status,404);
assert.equal((await call(bundle,'../escape')).status,400);
const ordinary=await (await call(detail,fixture.id)).json();
assert.equal('bundle' in ordinary,false,'default metadata remains backwards compatible');
assert.equal('deliveryVersion' in ordinary,false);
const metaResponse=await call(detail,fixture.id,{include:true});assert.equal(metaResponse.status,200);
const meta=await metaResponse.json();assert.equal(meta.bundle.available,true);assert.match(meta.deliveryVersion,/^[a-f0-9]{64}$/);
assert.equal(meta.artifact.deliveryVersion,meta.bundle.deliveryVersion);
for(const secret of ['result_key','bundle_key',fixture.version,fixture.pptxKey,fixture.bundleKey,REVIEW_TOKEN,WORKER_TOKEN])assert.ok(!JSON.stringify(meta).includes(secret),secret);
assert.equal((await call(bundle,fixture.id)).status,428);
const linked={'If-Match':meta.bundle.etag,[header]:meta.deliveryVersion};
assert.equal((await call(bundle,fixture.id,{headers:{...linked,'If-Match':'"other"'}})).status,412);
assert.equal((await call(bundle,fixture.id,{headers:{...linked,[header]:'0'.repeat(64)}})).status,412);
const zipped=await call(bundle,fixture.id,{headers:linked});assert.equal(zipped.status,200);
assert.deepEqual(new Uint8Array(await zipped.arrayBuffer()),objects.get(fixture.bundleKey).bytes);
assert.equal(zipped.headers.get('Content-Disposition'),'attachment; filename="interactive.zip"');
assert.equal(zipped.headers.get('Content-Length'),String(meta.bundle.bytes));
assert.equal(zipped.headers.get(header),meta.deliveryVersion);
assert.equal(zipped.headers.get('X-Review-PPTX-ETag'),meta.artifact.etag);
assert.equal(zipped.headers.get('Cache-Control'),'private, no-store');
const presentation=await call(pptx,fixture.id,{headers:{'If-Match':meta.artifact.etag,[header]:meta.deliveryVersion}});
assert.equal(presentation.status,200);assert.equal(presentation.headers.get(header),meta.deliveryVersion);
assert.equal((await call(pptx,fixture.id,{headers:{'If-Match':meta.artifact.etag,[header]:'0'.repeat(64)}})).status,412);
assert.equal(JSON.stringify(db.prepare('SELECT * FROM jobs').all()),before,'successful reads must preserve task rows');
console.log('PASS: dedicated review authorization, no ordinary/worker authorization, GET-only ZIP, exact bytes/ETag/version pairing, no task mutation or internal keys');

for(const options of [{status:'running'},{withVersion:false},{withBundle:false}]){
 const item=seed(options),metadata=await (await call(detail,item.id,{include:true})).json();
 assert.equal(metadata.bundle.available,false);
 assert.equal(metadata.bundle.reason,options.status==='running'?'not_completed':'not_delivered');
 assert.equal((await call(bundle,item.id)).status,404);
}
const absent=seed();objects.delete(absent.bundleKey);
assert.equal((await (await call(detail,absent.id,{include:true})).json()).bundle.reason,'stored_file_missing');
const broken=seed();objects.delete(broken.pptxKey);
assert.equal((await call(bundle,broken.id)).status,409);
const inconsistent=seed();db.prepare('UPDATE task_versions SET bundle_key=? WHERE id=?').run(fixture.bundleKey,inconsistent.version);
assert.equal((await call(bundle,inconsistent.id)).status,409,'a different task/version bundle must never be selected');
const old=seed(),newVersion=crypto.randomUUID();
db.prepare('UPDATE jobs SET result_key=? WHERE id=?').run(`results/${old.id}/${newVersion}.pptx`,old.id);
assert.equal((await call(bundle,old.id)).status,404,'a historical ZIP is not a current delivery');
const large=seed();objects.get(large.bundleKey).size=250*1024*1024+1;
const getsBefore=gets;assert.equal((await call(bundle,large.id)).status,413);assert.equal(gets,getsBefore,'oversized HEAD must be rejected before opening its body');
const boundary=seed();objects.get(boundary.bundleKey).size=250*1024*1024;
assert.equal((await call(detail,boundary.id,{include:true})).status,200,'250 MiB boundary is accepted');
const racing=seed(),racingMeta=await (await call(detail,racing.id,{include:true})).json();
afterGet=async key=>{if(key===racing.bundleKey)objects.get(racing.pptxKey).etag='"changed-pptx"';};
const cancelsBefore=cancels;
assert.equal((await call(bundle,racing.id,{headers:{'If-Match':racingMeta.bundle.etag,[header]:racingMeta.deliveryVersion}})).status,412);
assert.ok(cancels>cancelsBefore,'opened stale body must be cancelled');afterGet=null;
const moving=seed(),movingMeta=await (await call(detail,moving.id,{include:true})).json();
afterGet=async key=>{if(key===moving.bundleKey)db.prepare("UPDATE jobs SET status='running' WHERE id=?").run(moving.id);};
assert.equal((await call(bundle,moving.id,{headers:{'If-Match':movingMeta.bundle.etag,[header]:movingMeta.deliveryVersion}})).status,412);afterGet=null;
// Website downloads use signed-in owner/admin authorization, not review tokens.
let signedIn=null;
modules['@/app/chatgpt-auth'].getChatGPTUser=async()=>signedIn;
modules['cloudflare:workers'].env.ADMIN_USER_ID='admin';
modules['./admin-policy']=load('lib/admin-policy.ts');
modules['@/lib/admin']=load('lib/admin.ts');
modules['@/lib/bundle-download']=load('lib/bundle-download.ts');
const ownerDownload=load('app/api/jobs/[id]/bundle/route.ts').GET;
const adminDownload=load('app/api/admin/jobs/[id]/bundle/route.ts').GET;
const downloadable=seed();
const webCall=(route,id=downloadable.id,info=false)=>route(new Request(`https://local.test/api/jobs/${id}/bundle${info?'?info=1':''}`),{params:Promise.resolve({id})});
assert.equal((await webCall(ownerDownload)).status,401);
assert.equal((await webCall(adminDownload)).status,401);
signedIn={userId:'stranger',email:'stranger@test'};
const blockedGets=gets;
assert.equal((await webCall(ownerDownload)).status,404);
assert.equal((await webCall(adminDownload)).status,403);
assert.equal(gets,blockedGets);
signedIn={userId:'owner',email:'owner@test'};
assert.equal((await (await webCall(ownerDownload,downloadable.id,true)).json()).available,true);
const zipResponse=await webCall(ownerDownload);
assert.equal(zipResponse.status,200);
assert.equal(zipResponse.headers.get('Content-Type'),'application/zip');
assert.match(zipResponse.headers.get('Content-Disposition'),/presentation-interactive.zip/);
assert.deepEqual(new Uint8Array(await zipResponse.arrayBuffer()),objects.get(downloadable.bundleKey).bytes);
const noZip=seed({withBundle:false});
assert.equal((await (await webCall(ownerDownload,noZip.id,true)).json()).available,false);
assert.equal((await webCall(ownerDownload,noZip.id)).status,404);
const unfinished=seed({status:'running'});
assert.equal((await webCall(ownerDownload,unfinished.id)).status,404);
afterGet=async key=>{if(key===downloadable.bundleKey)objects.get(downloadable.pptxKey).etag='"web-race"';};
assert.equal((await webCall(ownerDownload)).status,412);afterGet=null;
signedIn={userId:'admin',email:'admin@test'};
assert.equal((await webCall(adminDownload)).status,200);
console.log('PASS: website owner/admin ZIP access, metadata, missing/unfinished bundles, attachment and version race');

// A legacy deployment is never migrated by a read-only review request.
db.exec('DROP TABLE task_versions');
assert.equal((await call(detail,fixture.id)).status,200);
const unavailable=await call(detail,fixture.id,{include:true});assert.equal(unavailable.status,503);
assert.equal((await unavailable.json()).reason,'bundle_metadata_unavailable');
assert.equal(db.prepare("SELECT COUNT(*) n FROM sqlite_master WHERE name='task_versions'").get().n,0);
db.close();
console.log('PASS: absent/unfinished/current-only selection, version inconsistency, missing pair, 250 MiB bound, stale-stream cancellation and no read-side migrations');
