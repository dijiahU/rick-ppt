import {database,files,json,userId,sameOrigin} from '@/lib/server';
import {isAdmin} from '@/lib/admin';
import {boundedBody} from '@/lib/attachments';
import {resolveUploads,copyUpload} from '@/lib/staged-uploads';
import {editableSource,ensureProgressiveCanvas,unchangedPages} from '@/lib/progressive-canvas';
import {canvasSnapshot,canvasVersions} from '@/lib/canvas-storage';
import {digestPattern,uuidPattern} from '@/lib/visual-edits';
import {validateNativePatches} from '@/lib/native-edits';
import {ensureNativeEdits,nativeKey,nativeStatus,type NativeEditRow} from '@/lib/native-edit-storage';
async function access(id:string){const user=await userId();if(!user)return null;const admin=await isAdmin();const job=await database().prepare('SELECT id,user_id,status,lease,summary,result_key FROM jobs WHERE id=? AND (user_id=? OR ?=1)').bind(id,user,admin?1:0).first<{id:string;user_id:string;status:string;lease:string|null;summary:string|null;result_key:string|null}>();return job?{user,admin,job}:null;}
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const {id}=await params,a=await access(id);if(!a)return json({error:'Task unavailable.'},404);await ensureNativeEdits();const q=new URL(request.url).searchParams;
 if(q.get('request')){const r=await database().prepare('SELECT * FROM native_edits WHERE id=? AND job_id=?').bind(q.get('request'),id).first<NativeEditRow>();return r?json(nativeStatus(r)):json({error:'Save unavailable.'},404);}
 const sha=q.get('sha256')||'';await ensureProgressiveCanvas();const saved=a.job.status==='running'?await database().prepare('SELECT source_key FROM canvas_sources WHERE job_id=? AND sha256=? AND producer_lease=?').bind(id,sha,a.job.lease).first<{source_key:string}>():null;const object=await files().get(saved?.source_key||a.job.result_key||'missing');
 if(!digestPattern.test(sha)||object?.customMetadata?.sha256!==sha)return json({error:'The saved PPTX has changed. Refresh the version.'},409);
 if(object.size>30*1024*1024)return json({error:'PPTX exceeds the 30 MiB editor limit.'},400);
 return new Response(object.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
}
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 if(!sameOrigin(request))return json({error:'Invalid origin.'},403);const {id}=await params,a=await access(id);if(!a)return json({error:'Task unavailable.'},404);
 let b;try{b=JSON.parse(new TextDecoder().decode(await boundedBody(request,200000)));}catch{return json({error:'Invalid save.'},400);}
 if(!b||!uuidPattern.test(b.id)||!digestPattern.test(b.baseSha256))return json({error:'Version and request ID required.'},400);
 if(a.job.user_id!==a.user&&(!a.admin||b.adminEdit!==true))return json({error:'Enable administrator editing first.'},403);
 const db=database();await ensureNativeEdits();const snapshot=await canvasSnapshot(id,b.baseSha256);if(!snapshot)return json({error:'Saved preview unavailable.'},409);
 let patches;try{patches=validateNativePatches(b.patches,snapshot);}catch(e){return json({error:e instanceof Error?e.message:'Invalid changes.'},400);}
 const progressive=a.job.status==='running';const payload=JSON.stringify({patches,administrator:a.job.user_id!==a.user,...(progressive?{progressive:true,producerLease:a.job.lease}:{})});const prior=await db.prepare('SELECT * FROM native_edits WHERE id=?').bind(b.id).first<NativeEditRow>();
 if(prior)return prior.job_id===id&&prior.user_id===a.user&&prior.base_sha===b.baseSha256&&JSON.stringify(JSON.parse(prior.payload).patches)===JSON.stringify(patches)&&JSON.parse(prior.payload).administrator===(a.job.user_id!==a.user)?json(nativeStatus(prior)):json({error:'Save ID already used for different changes.'},409);
 const head=await editableSource(a.job),current=head?await canvasSnapshot(id,head.sha256):null;const affected=Array.from(new Set(patches.map(p=>p.page)));
 if(!head||!current||!unchangedPages(snapshot,current,affected))return json({error:'One of these pages changed. Refresh that page before saving; your draft is kept.',code:'stale_canvas'},409);
 const saved=progressive?await db.prepare('SELECT source_key FROM canvas_sources WHERE job_id=? AND sha256=? AND producer_lease=?').bind(id,b.baseSha256,a.job.lease).first<{source_key:string}>():null;
 const sourceKey=progressive?(saved?.source_key||a.job.result_key):a.job.result_key,source=sourceKey?await files().head(sourceKey):null;if(source?.customMetadata?.sha256!==b.baseSha256)return json({error:'The editable source has changed.',code:'stale_canvas'},409);
 if(!['complete','running'].includes(a.job.status)||a.job.summary==='delivery_pending')return json({error:'This task is committing a delivery or is paused. Keep your draft and retry after the status updates.'},409);
 // Adopt a verified legacy delivered baseline without replacing a newer live head.
 if(progressive&&!saved&&a.job.result_key){await db.batch([
  db.prepare("INSERT INTO canvas_heads(job_id,sha256,source_key,producer_lease,updated_at) SELECT ?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease=? AND result_key=?) ON CONFLICT(job_id) DO UPDATE SET sha256=excluded.sha256,source_key=excluded.source_key,producer_lease=excluded.producer_lease,updated_at=excluded.updated_at WHERE canvas_heads.producer_lease<>excluded.producer_lease").bind(id,head.sha256,head.source_key,a.job.lease,Date.now(),id,a.job.lease,a.job.result_key),
  db.prepare("INSERT INTO canvas_sources(job_id,sha256,source_key,producer_lease) SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM canvas_heads WHERE job_id=? AND sha256=? AND producer_lease=?) ON CONFLICT(job_id,sha256) DO UPDATE SET producer_lease=excluded.producer_lease").bind(id,head.sha256,head.source_key,a.job.lease,id,head.sha256,a.job.lease)
 ]);}
 const uploads=patches.flatMap(p=>p.image?[p.image]:[]);if(uploads.length>10)return json({error:'Save up to 10 replacement pictures at once.'},400);
 try{for(const image of uploads){const [u]=await resolveUploads(a.user,`message:${id}:${image.id}`,[image.uploadId]);if(!u||!['png','jpg','jpeg'].includes(u.meta.ext))throw Error();await copyUpload(u,nativeKey(id,b.id,image.id));}}catch{return json({error:'Replacement picture expired. Choose it again.'},400);}
 const now=Date.now();const guard=progressive?"EXISTS(SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease=? AND COALESCE(summary,'')<>'delivery_pending') AND EXISTS(SELECT 1 FROM canvas_heads WHERE job_id=? AND producer_lease=? AND sha256=?)":"EXISTS(SELECT 1 FROM jobs WHERE id=? AND status='complete' AND result_key=?)";
 const args=progressive?[id,a.job.lease,id,a.job.lease,head.sha256]:[id,a.job.result_key];
 const r=await db.prepare("INSERT INTO native_edits(id,job_id,user_id,base_sha,source_key,payload,status,created_at,updated_at) SELECT ?,?,?,?,?,?,'queued',?,? WHERE "+guard+" AND NOT EXISTS(SELECT 1 FROM native_edits WHERE job_id=? AND status IN ('queued','running')) AND (SELECT COUNT(*) FROM native_edits WHERE status IN ('queued','running'))<100 ON CONFLICT(id) DO NOTHING RETURNING *").bind(b.id,id,a.user,b.baseSha256,sourceKey,payload,now,now,...args,id).first<NativeEditRow>();
 return r?json(nativeStatus(r),201):json({error:'Another save is in progress, or the task changed. Your draft has been kept.'},409);
}
