import {ensureProgressiveCanvas,liveHead} from '@/lib/progressive-canvas';
import {finishProgressive} from '@/lib/progressive-native-finish';
import {database,files,json,workerAuthorized} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';
import {ensureNativeEdits,nativeKey,type NativeEditRow} from '@/lib/native-edit-storage';
import {canvasKey,canvasSnapshot,ensureCanvas} from '@/lib/canvas-storage';
import {digestPattern,validateSnapshot,visualEditMessage} from '@/lib/visual-edits';
import {ensureConversation} from '@/lib/conversation';
import type {NativePatch} from '@/lib/native-edits';
const hash=async(b:Uint8Array)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new Uint8Array(b)))).map(n=>n.toString(16).padStart(2,'0')).join('');
export async function POST(request:Request){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);await ensureNativeEdits();await ensureProgressiveCanvas();const db=database(),q=new URL(request.url).searchParams,action=q.get('action'),now=Date.now();
 if(action==='claim'){
  // Expired leases may be retried: deterministic mutations always start from frozen bytes.
  const lease=crypto.randomUUID();const edit=await db.prepare("UPDATE native_edits SET status='running',lease=?,updated_at=? WHERE id=(SELECT n.id FROM native_edits n JOIN jobs j ON j.id=n.job_id WHERE (n.status='queued' OR (n.status='running' AND n.updated_at<?)) AND ((j.status='complete' AND j.result_key=n.source_key AND COALESCE(json_extract(n.payload,'$.progressive'),0)=0) OR (j.status='running' AND j.lease=json_extract(n.payload,'$.producerLease'))) ORDER BY n.created_at LIMIT 1) RETURNING *").bind(lease,now,now-300000).first<NativeEditRow>();
  // Do not leave a save indefinitely queued after another editor/agent changed its source.
  await db.prepare("UPDATE native_edits SET status='failed',error='The task or source changed before this save. Refresh and try again.',updated_at=? WHERE status='queued' AND NOT EXISTS(SELECT 1 FROM jobs WHERE id=native_edits.job_id AND ((status='complete' AND result_key=native_edits.source_key AND COALESCE(json_extract(native_edits.payload,'$.progressive'),0)=0) OR (status='running' AND lease=json_extract(native_edits.payload,'$.producerLease'))))").bind(now).run();
  return json({edit:edit?{id:edit.id,jobId:edit.job_id,baseSha256:edit.base_sha,lease:edit.lease,...JSON.parse(edit.payload)}:null});
 }
 const id=q.get('id')||'',lease=request.headers.get('X-Job-Lease');const edit=await db.prepare('SELECT * FROM native_edits WHERE id=? AND lease=?').bind(id,lease).first<NativeEditRow>();if(!edit)return json({error:'Save lease expired'},409);
 if(action==='finish'&&edit.status==='complete')return json({ok:true,sha256:edit.result_sha});
 if(edit.status!=='running')return json({error:'Save is not running'},409);
 const meta=JSON.parse(edit.payload),progressive=meta.progressive===true;const job=await db.prepare(progressive?"SELECT id,user_id FROM jobs WHERE id=? AND status='running' AND lease=?":"SELECT id,user_id FROM jobs WHERE id=? AND status='complete' AND result_key=?").bind(edit.job_id,progressive?meta.producerLease:edit.source_key).first<{id:string;user_id:string}>();if(!job){await db.prepare("UPDATE native_edits SET status='failed',error='The task changed during this save. Refresh and try again.',updated_at=? WHERE id=? AND lease=? AND status='running'").bind(now,id,lease).run();return json({error:'Task changed'},409);}
 await db.prepare('UPDATE native_edits SET updated_at=? WHERE id=? AND lease=?').bind(now,id,lease).run();
 if(action==='source'){const source=await files().get(edit.source_key);return source?.customMetadata?.sha256===edit.base_sha?new Response(source.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation'}}):json({error:'Source changed'},409);}
 if(action==='base-manifest'){const head=progressive?await liveHead(edit.job_id,meta.producerLease):null;return json({snapshot:await canvasSnapshot(edit.job_id,head?.sha256||edit.base_sha),progressive});}
 if(action==='rebase-source'&&progressive){const head=await liveHead(edit.job_id,meta.producerLease);if(!head||head.sha256!==q.get('parent'))return json({error:'Progress changed'},409);const object=await files().get(head.source_key);return object?new Response(object.body):json({error:'Source unavailable'},404);}
 if(action==='picture'){const key=q.get('picture'),payload=JSON.parse(edit.payload);if(!payload.patches.some((p:NativePatch)=>p.image?.id===key))return json({error:'Picture unavailable'},404);const picture=await files().get(nativeKey(edit.job_id,id,key!));return picture?new Response(picture.body):json({error:'Picture unavailable'},404);}
 if(action==='artifact'){
  const bytes=await boundedBody(request,30*1024*1024);if(bytes[0]!==80||bytes[1]!==75)return json({error:'PPTX required'},400);const sha=await hash(bytes);await files().put(nativeKey(edit.job_id,id,'result.pptx'),bytes,{httpMetadata:{contentType:'application/vnd.openxmlformats-officedocument.presentationml.presentation'},customMetadata:{sha256:sha}});return json({sha256:sha});
 }
 if(action==='page'){
  const n=Number(q.get('page'));const base=await canvasSnapshot(edit.job_id,edit.base_sha);if(!Number.isSafeInteger(n)||!base?.pages[n-1])return json({error:'Page unavailable'},400);
  const bytes=await boundedBody(request,2*1024*1024);if([137,80,78,71,13,10,26,10].some((v,i)=>bytes[i]!==v))return json({error:'PNG required'},400);const sha=await hash(bytes);await files().put(nativeKey(edit.job_id,id,`page-${n}.png`),bytes,{httpMetadata:{contentType:'image/png'},customMetadata:{sha256:sha}});return json({sha256:sha});
 }
 if(action==='fail'){await db.prepare("UPDATE native_edits SET status='failed',error='The native save could not finish. Your previous PPTX is unchanged; keep your draft and retry.',updated_at=? WHERE id=? AND lease=? AND status='running'").bind(now,id,lease).run();return json({ok:true});}
 if(action!=='finish')return json({error:'Unknown action'},400);
 let snapshot;try{snapshot=validateSnapshot(JSON.parse(new TextDecoder().decode(await boundedBody(request,3*1024*1024))));}catch{return json({error:'Invalid native snapshot'},400);}
 if(progressive)return finishProgressive(edit,snapshot,q.get('parent')||'',lease!);
 const artifact=await files().get(nativeKey(edit.job_id,id,'result.pptx')),base=await canvasSnapshot(edit.job_id,edit.base_sha);if(!artifact||artifact.customMetadata?.sha256!==snapshot.sha256||!digestPattern.test(snapshot.sha256)||!base||snapshot.pages.length!==base.pages.length)return json({error:'Artifact/snapshot mismatch'},409);
 const patches:NativePatch[]=JSON.parse(edit.payload).patches,affected=new Set(patches.map(p=>p.page));
 for(const page of snapshot.pages){if(page.part!==base.pages[page.number-1].part)return json({error:'Slide order changed'},409);const key=affected.has(page.number)?nativeKey(edit.job_id,id,`page-${page.number}.png`):canvasKey(edit.job_id,edit.base_sha,`page-${page.number}.png`);const image=await files().get(key);if(!image||(affected.has(page.number)?image.customMetadata?.sha256!==page.imageSha256:base.pages[page.number-1].imageSha256!==page.imageSha256))return json({error:'Rendered page missing or changed'},409);const bytes=await new Response(image.body).arrayBuffer(),options={httpMetadata:{contentType:'image/png'},customMetadata:{sha256:page.imageSha256}};await files().put(canvasKey(edit.job_id,snapshot.sha256,`page-${page.number}.png`),bytes,options);await files().put(canvasKey(edit.job_id,snapshot.sha256,`page-${page.number}-${page.imageSha256}.png`),bytes,options);}
 const resultKey=nativeKey(edit.job_id,id,'result.pptx');await files().put(canvasKey(edit.job_id,snapshot.sha256,'manifest.json'),JSON.stringify(snapshot),{httpMetadata:{contentType:'application/json'}});await ensureCanvas();await ensureConversation();
 // Record the exact new baseline for the next Agent request without starting a model.
 const affectedPages=Array.from(affected);const messageBody=visualEditMessage(snapshot,[affectedPages[0]].map(page=>({id:crypto.randomUUID(),page,kind:'comment',region:{x:0,y:0,width:1,height:1},instruction:'These native edits are ALREADY saved in this exact baseline. For subsequent user changes, continue from this PPTX. Do not replay edits or restore an older checkpoint.'})),JSON.parse(edit.payload).administrator).replace('"scope":"selected_objects_and_pages"','"scope":"selected_objects_and_pages","directSave":true,"directCount":'+patches.length+',"directPages":'+JSON.stringify(affectedPages));
 await files().put(`canvas-inputs/${edit.job_id}/${id}/baseline.pptx`,artifact.body,{httpMetadata:{contentType:'application/vnd.openxmlformats-officedocument.presentationml.presentation'},customMetadata:{sha256:snapshot.sha256}});
 await db.batch([
  db.prepare("INSERT INTO task_versions(id,job_id,result_key,revision,created_at) SELECT ?,?,?,COALESCE((SELECT MAX(revision) FROM task_versions WHERE job_id=?),0),? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND status='complete' AND result_key=?) AND EXISTS(SELECT 1 FROM native_edits WHERE id=? AND lease=? AND status='running') ON CONFLICT(id) DO NOTHING").bind(crypto.randomUUID(),edit.job_id,edit.source_key,edit.job_id,now-1,edit.job_id,edit.source_key,id,lease),
  db.prepare("UPDATE jobs SET result_key=?,updated_at=? WHERE id=? AND status='complete' AND result_key=? AND EXISTS(SELECT 1 FROM native_edits WHERE id=? AND lease=? AND status='running')").bind(resultKey,now,edit.job_id,edit.source_key,id,lease),
  db.prepare("INSERT INTO canvas_snapshots(job_id,sha256,version_id,created_at,pages) SELECT ?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND result_key=?) ON CONFLICT(job_id,sha256) DO NOTHING").bind(edit.job_id,snapshot.sha256,snapshot.versionId,now,snapshot.pages.length,edit.job_id,resultKey),
  db.prepare("INSERT INTO task_versions(id,job_id,result_key,revision,created_at) SELECT ?,?,?,COALESCE((SELECT MAX(revision) FROM task_versions WHERE job_id=?),0),? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND result_key=?) ON CONFLICT(id) DO NOTHING").bind(id,edit.job_id,resultKey,edit.job_id,now,edit.job_id,resultKey),
  db.prepare("INSERT INTO task_messages(id,job_id,user_id,role,kind,body,attachments,status,created_at,updated_at) SELECT ?,?,?,'user','revision',?,'[]','pending',?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND result_key=?) ON CONFLICT(job_id,id) DO NOTHING").bind(id,edit.job_id,edit.user_id,messageBody,now,now,edit.job_id,resultKey),
  db.prepare("UPDATE native_edits SET status='complete',result_sha=?,updated_at=? WHERE id=? AND lease=? AND status='running' AND EXISTS(SELECT 1 FROM jobs WHERE id=? AND result_key=?)").bind(snapshot.sha256,now,id,lease,edit.job_id,resultKey),
 ]);
 const saved=await db.prepare('SELECT status FROM native_edits WHERE id=?').bind(id).first<{status:string}>();return saved?.status==='complete'?json({ok:true,sha256:snapshot.sha256}):json({error:'Task changed during publication'},409);
}
