// Real route handlers + SQLite/R2. No production jobs or model/API calls.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
const modules={};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
const db=new DatabaseSync(':memory:');db.exec("CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,status TEXT,lease TEXT,result_key TEXT,summary TEXT,updated_at INTEGER);CREATE TABLE task_drafts(job_id TEXT PRIMARY KEY);CREATE TABLE worker(id TEXT PRIMARY KEY,heartbeat INTEGER)");
const id=crypto.randomUUID(),lease=crypto.randomUUID(),versionId=crypto.randomUUID();let user='owner',admin=false;const objects=new Map();
const binding={prepare(sql){let args=[];const s={bind(...v){args=v;return s;},async first(){return db.prepare(sql).get(...args)??null;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};}};return s;},async batch(statements){db.exec('BEGIN');try{const values=[];for(const s of statements)values.push(await s.run());db.exec('COMMIT');return values;}catch(e){db.exec('ROLLBACK');throw e;}}};
const r2={async put(key,data,options={}){const bytes=new Uint8Array(await new Response(data).arrayBuffer());objects.set(key,{bytes,customMetadata:options.customMetadata||{}});},async get(key){const o=objects.get(key);return o?{body:new Response(o.bytes).body,size:o.bytes.length,customMetadata:o.customMetadata,json:async()=>JSON.parse(new TextDecoder().decode(o.bytes))}:null;},async head(key){const o=objects.get(key);return o?{size:o.bytes.length,customMetadata:o.customMetadata}:null;}};
modules['@/lib/server']={database:()=>binding,files:()=>r2,json:(v,status=200)=>Response.json(v,{status}),userId:async()=>user,sameOrigin:r=>r.headers.get('Origin')===new URL(r.url).origin,workerAuthorized:async r=>r.headers.get('Authorization')==='Bearer test-worker'};
modules['@/lib/admin']={isAdmin:async()=>admin};modules['@/lib/attachments']=load('lib/attachments.ts');modules['@/lib/conversation']=load('lib/conversation.ts');modules['@/lib/staged-uploads']=load('lib/staged-uploads.ts');modules['@/lib/visual-edits']=load('lib/visual-edits.ts');modules['./visual-edits']=modules['@/lib/visual-edits'];modules['./server']=modules['@/lib/server'];modules['@/lib/canvas-storage']=load('lib/canvas-storage.ts');modules['./canvas-storage']=modules['@/lib/canvas-storage'];modules['@/lib/progressive-canvas']=load('lib/progressive-canvas.ts');
const visual=modules['@/lib/visual-edits'];const publish=load('app/api/worker/[id]/canvas/route.ts').POST;const read=load('app/api/jobs/[id]/canvas/route.ts').GET;const submit=load('app/api/jobs/[id]/visual-edits/route.ts').POST;const params={params:Promise.resolve({id})};

modules['@/lib/native-edits']=load('lib/native-edits.ts');modules['@/lib/native-edit-storage']=load('lib/native-edit-storage.ts');modules['./native-edit-storage']=modules['@/lib/native-edit-storage'];modules['./conversation']=modules['@/lib/conversation'];modules['./progressive-canvas']=modules['@/lib/progressive-canvas'];modules['@/lib/progressive-native-finish']=load('lib/progressive-native-finish.ts');
const direct=load('app/api/jobs/[id]/native-edits/route.ts'),worker=load('app/api/worker/native-edits/route.ts').POST;

const root=process.argv[2];assert.ok(root,'Pass progressive fixture directory');
const source=readFileSync(root+'/source.pptx'),growing=readFileSync(root+'/growing.pptx'),merged=readFileSync(root+'/merged.pptx');
const base=JSON.parse(readFileSync(root+'/source.json')),later=JSON.parse(readFileSync(root+'/growing.json')),result=JSON.parse(readFileSync(root+'/merged.json'));
const hash=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b))).map(n=>n.toString(16).padStart(2,'0')).join('');const png=new Uint8Array([137,80,78,71,13,10,26,10]),imageSha=await hash(png);
for(const snap of [base,later,result])for(const p of snap.pages)if(snap.readyPages.includes(p.number))p.imageSha256=imageSha;
await modules['@/lib/canvas-storage'].ensureCanvas();await modules['@/lib/conversation'].ensureConversation();await modules['@/lib/native-edit-storage'].ensureNativeEdits();
db.prepare("INSERT INTO jobs VALUES (?,'owner','running',?,NULL,NULL,100)").run(id,lease);
const workerReq=(sha,action,body,token='test-worker',l=lease)=>new Request(`https://test.local/api/worker/${id}/canvas?sha256=${sha}&action=${action}`,{method:'POST',headers:{Authorization:'Bearer '+token,'X-Job-Lease':l},body:body instanceof Uint8Array?body:JSON.stringify(body||{})});
async function publishProgress(snapshot,bytes,parent=''){
 assert.equal((await publish(workerReq(snapshot.sha256,'artifact',bytes),params)).status,200);
 for(const n of snapshot.readyPages)assert.equal((await publish(workerReq(snapshot.sha256,'page&page='+n,png),params)).status,200);
 const response=await publish(workerReq(snapshot.sha256,'manifest&progressive=1&parent='+parent,snapshot),params);assert.equal(response.status,200,await response.text());
}
await publishProgress(base,source);
const pageState=await (await read(new Request(`https://test.local/api/jobs/${id}/canvas`),params)).json();assert.deepEqual(pageState.snapshot.readyPages,[1]);assert.equal(pageState.canEdit,true);assert.ok(!JSON.stringify(pageState).includes(lease),'Do not expose task leases');
const body={id:crypto.randomUUID(),baseSha256:base.sha256,patches:[{page:1,objectId:'2',text:'Edited native title'}]};
const post=(b=body)=>new Request(`https://test.local/api/jobs/${id}/native-edits`,{method:'POST',headers:{Origin:'https://test.local'},body:JSON.stringify(b)});
assert.equal((await direct.POST(post({...body,patches:[{page:2,objectId:'2',text:'Not ready'}]}),params)).status,409);
assert.equal((await direct.POST(post(),params)).status,201);assert.equal(db.prepare('SELECT status,result_key FROM jobs WHERE id=?').get(id).status,'running');
// Continue publishing other pages while the native save is queued.
await publishProgress(later,growing,base.sha256);
const req=(action,bytes={},l='')=>new Request(`https://test.local/api/worker/native-edits?action=${action}&id=${body.id}`,{method:'POST',headers:{Authorization:'Bearer test-worker','X-Job-Lease':l},body:bytes instanceof Uint8Array?bytes:JSON.stringify(bytes)});
const claimed=(await (await worker(req('claim'))).json()).edit;assert.equal(claimed.progressive,true);const nativeLease=claimed.lease;
const current=await (await worker(req('base-manifest',{},nativeLease))).json();assert.equal(current.snapshot.sha256,later.sha256);assert.equal((await worker(req('rebase-source&parent='+later.sha256,{},nativeLease))).status,200);
assert.equal((await worker(req('artifact',merged,nativeLease))).status,200);assert.equal((await worker(req('page&page=1',png,nativeLease))).status,200);
assert.equal((await worker(req('finish&parent='+base.sha256,result,nativeLease))).status,409,'Never replace a newer growing deck with an older one');
const done=await worker(req('finish&parent='+later.sha256,result,nativeLease));assert.equal(done.status,200,await done.text());
const head=db.prepare('SELECT * FROM canvas_heads WHERE job_id=?').get(id);assert.equal(head.sha256,result.sha256);assert.equal(db.prepare('SELECT status,result_key FROM jobs WHERE id=?').get(id).status,'running');assert.equal(db.prepare('SELECT result_key FROM jobs WHERE id=?').get(id).result_key,null);assert.equal(db.prepare('SELECT page FROM canvas_page_locks WHERE job_id=?').get(id).page,1);
const updated=await (await read(new Request(`https://test.local/api/jobs/${id}/canvas`),params)).json();assert.equal(updated.snapshot.pages.length,3);assert.deepEqual(updated.snapshot.readyPages,[1,2]);assert.match(db.prepare('SELECT body FROM task_messages').get().body,/Continue authoring all later pages/);
// A racing author snapshot cannot overwrite a just-saved protected page.
const stalePublish=await publish(workerReq(later.sha256,'manifest&progressive=1&parent='+later.sha256,later),params);assert.equal(stalePublish.status,409);assert.equal(db.prepare('SELECT sha256 FROM canvas_heads WHERE job_id=?').get(id).sha256,result.sha256);
// A queued save from an unchanged earlier page is permitted, but a changed page or unfinished page is not.
const stale=await direct.POST(post({...body,id:crypto.randomUUID()}),params);assert.equal(stale.status,409);assert.equal((await direct.POST(post({id:crypto.randomUUID(),baseSha256:result.sha256,patches:[{page:3,objectId:'2',text:'Still making'}]}),params)).status,409);
db.exec('ALTER TABLE jobs ADD COLUMN attachments TEXT');
modules['@/lib/slide-limits.mjs']=await import('../lib/slide-limits.mjs');modules['@/lib/progress']={parseProgress:v=>v};modules['@/lib/queries']={RETRY_JOB:''};modules['@/lib/admin-trace']={storeTrace(){}};modules['@/lib/execution-backend']={workerCapabilities(){return {advertised:false,backends:[]};}};
const deliver=load('app/api/worker/[id]/route.ts').POST;
const deliveryRequest=()=>new Request(`https://test.local/api/worker/${id}?action=delivery-ready&revision=1&sha256=${result.sha256}`,{method:'POST',headers:{Authorization:'Bearer test-worker','X-Job-Lease':lease}});
assert.equal((await deliver(deliveryRequest(),params)).status,412,'Pending native revision must invalidate the old reviewed candidate');
db.prepare("UPDATE task_messages SET status='applied' WHERE job_id=?").run(id);assert.equal((await deliver(deliveryRequest(),params)).status,200);
// Delivery commits briefly close admission; keep the user's draft rather than race the upload.
assert.equal((await direct.POST(post({id:crypto.randomUUID(),baseSha256:result.sha256,patches:[{page:1,objectId:'2',text:'After commit'}]}),params)).status,409);
console.log('PASS: ready-page admission during production, private source access, growing deck publication, native save rebasing, preservation of later pages, unfinished-page rejection, user page locks, stale publisher CAS and final-delivery fences.');
