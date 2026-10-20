import {database,files,json,workerAuthorized} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';
import {canvasKey,ensureCanvas} from '@/lib/canvas-storage';
import {validateSnapshot,digestPattern} from '@/lib/visual-edits';
import {ensureProgressiveCanvas,liveHead,pageReady} from '@/lib/progressive-canvas';
const hash=async(bytes:Uint8Array)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new Uint8Array(bytes)))).map(x=>x.toString(16).padStart(2,'0')).join('');
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);const {id}=await params,q=new URL(request.url).searchParams,lease=request.headers.get('X-Job-Lease'),sha=q.get('sha256')||'',action=q.get('action');
 if(!lease||!digestPattern.test(sha))return json({error:'Lease and checksum required'},400);
 const db=database(),job=await db.prepare("SELECT id,status,result_key FROM jobs WHERE id=? AND lease=? AND status IN ('running','complete')").bind(id,lease).first<{id:string;status:string;result_key:string|null}>();if(!job)return json({error:'Lease expired'},409);
 await ensureProgressiveCanvas();
 if(action==='locks'){const locks=await db.prepare('SELECT page,part,sha256,image_sha AS imageSha256 FROM canvas_page_locks WHERE job_id=? ORDER BY page').bind(id).all();return json({locks:locks.results,head:await liveHead(id,lease)});}
 if(action==='source'&&q.has('locked')||action==='lock-image'){
  const lock=await db.prepare('SELECT source_key FROM canvas_page_locks WHERE job_id=? AND sha256=?'+(action==='lock-image'?' AND page=?':'')+' LIMIT 1').bind(id,sha,...(action==='lock-image'?[Number(q.get('page'))]:[])).first<{source_key:string}>();if(!lock)return json({error:'Protected source unavailable'},404);
  const object=await files().get(action==='lock-image'?canvasKey(id,sha,`page-${Number(q.get('page'))}.png`):lock.source_key);return object?new Response(object.body):json({error:'Protected file unavailable'},404);
 }
 if(action==='source'){
  const message=q.get('message')||'';if(!/^[a-f0-9-]{36}$/.test(message))return json({error:'Invalid message'},400);
  const row=await db.prepare("SELECT body FROM task_messages WHERE job_id=? AND id=? AND role='user' AND kind='revision'").bind(id,message).first<{body:string}>();let base;try{base=JSON.parse(row?.body.split('\n')[1]||'null');}catch{}
  if(!row?.body.startsWith('[RICKPPT_VISUAL_EDITS_V1]\n')||base?.baseSha256!==sha)return json({error:'Source not bound to this request'},409);const object=await files().get(`canvas-inputs/${id}/${message}/baseline.pptx`);if(!object||object.customMetadata?.sha256!==sha)return json({error:'Source unavailable'},404);return new Response(object.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Cache-Control':'private, no-store','ETag':'"'+sha+'"'}});
 }
 if(job.status==='complete'){const object=job.result_key?await files().head(job.result_key):null;if(object?.customMetadata?.sha256!==sha)return json({error:'Artifact changed'},409);}
 if(action==='artifact'){
  if(job.status!=='running')return json({error:'Task is not running'},409);const bytes=await boundedBody(request,30*1024*1024);if(bytes[0]!==80||bytes[1]!==75||await hash(bytes)!==sha)return json({error:'PPTX identity mismatch'},400);const key=canvasKey(id,sha,'source.pptx');await files().put(key,bytes,{httpMetadata:{contentType:'application/vnd.openxmlformats-officedocument.presentationml.presentation'},customMetadata:{sha256:sha}});return json({ok:true});
 }
 if(action==='page'){
  const n=Number(q.get('page'));if(!Number.isSafeInteger(n)||n<1||n>200)return json({error:'Invalid page'},400);const bytes=await boundedBody(request,2*1024*1024);if(bytes.length<8||[137,80,78,71,13,10,26,10].some((x,i)=>bytes[i]!==x))return json({error:'PNG required'},400);const digest=await hash(bytes),options={httpMetadata:{contentType:'image/png'},customMetadata:{sha256:digest}};
  await files().put(canvasKey(id,sha,`page-${n}-${digest}.png`),bytes,options);await files().put(canvasKey(id,sha,`page-${n}.png`),bytes,options);return json({ok:true});
 }
 if(action!=='manifest')return json({error:'Unknown action'},400);let snapshot;try{snapshot=validateSnapshot(JSON.parse(new TextDecoder().decode(await boundedBody(request,3*1024*1024))));}catch{return json({error:'Invalid snapshot'},400);}if(snapshot.sha256!==sha)return json({error:'Snapshot identity mismatch'},409);
 for(const page of snapshot.pages){if(!pageReady(snapshot,page.number))continue;const image=await files().head(canvasKey(id,sha,`page-${page.number}.png`));if(image?.customMetadata?.sha256!==page.imageSha256)return json({error:'Page image missing or changed'},409);}
 const progressive=q.get('progressive')==='1',sourceKey=canvasKey(id,sha,'source.pptx');if(progressive&&(job.status!=='running'||(await files().head(sourceKey))?.customMetadata?.sha256!==sha))return json({error:'Progress source unavailable'},409);
 await files().put(canvasKey(id,sha,'manifest.json'),JSON.stringify(snapshot),{httpMetadata:{contentType:'application/json'}});await ensureCanvas();
 if(progressive){
  const parent=q.get('parent')||'';const updates=await db.batch([
   db.prepare("INSERT INTO canvas_sources(job_id,sha256,source_key,producer_lease) SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='running') ON CONFLICT(job_id,sha256) DO UPDATE SET producer_lease=excluded.producer_lease").bind(id,sha,sourceKey,lease,id,lease),
   db.prepare("INSERT INTO canvas_heads(job_id,sha256,source_key,producer_lease,updated_at) SELECT ?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='running') AND (?='' OR EXISTS(SELECT 1 FROM canvas_heads WHERE job_id=? AND sha256=? AND producer_lease=?)) ON CONFLICT(job_id) DO UPDATE SET sha256=excluded.sha256,source_key=excluded.source_key,producer_lease=excluded.producer_lease,updated_at=excluded.updated_at WHERE canvas_heads.producer_lease<>excluded.producer_lease OR canvas_heads.sha256=?").bind(id,sha,sourceKey,lease,Date.now(),id,lease,parent,id,parent,lease,parent),
  ]);if(!updates[1].meta.changes)return json({error:'Progress changed; merge current user pages and retry'},409);
 }
 await db.prepare('INSERT INTO canvas_snapshots(job_id,sha256,version_id,created_at,pages) VALUES (?,?,?,?,?) ON CONFLICT(job_id,sha256) DO NOTHING').bind(id,sha,snapshot.versionId,snapshot.createdAt,snapshot.pages.length).run();return json({ok:true,pages:snapshot.pages.length});
}
