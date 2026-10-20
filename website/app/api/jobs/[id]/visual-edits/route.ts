import {editableSource,ensureProgressiveCanvas,unchangedPages} from '@/lib/progressive-canvas';
import {database,files,json,userId,sameOrigin} from '@/lib/server';
import {isAdmin} from '@/lib/admin';
import {resolveUploads,copyUpload} from '@/lib/staged-uploads';
import {boundedBody} from '@/lib/attachments';
import {ensureConversation,MAX_MESSAGES,message,messageFileKey,type MessageRow} from '@/lib/conversation';
import {canvasSnapshot,canvasVersions} from '@/lib/canvas-storage';
import {digestPattern,uuidPattern,validateEdits,visualEditMessage} from '@/lib/visual-edits';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'Sign in to continue.'},401);if(!sameOrigin(request))return json({error:'Invalid origin.'},403);
 const {id}=await params;let body;try{body=JSON.parse(new TextDecoder().decode(await boundedBody(request,40000)));}catch{return json({error:'Invalid request.'},400);}
 if(!body||!uuidPattern.test(body.id)||!digestPattern.test(body.baseSha256))return json({error:'Version and request ID required.'},400);
 const administrator=await isAdmin();const db=database();const job=await db.prepare('SELECT id,user_id,status,lease,result_key,updated_at FROM jobs WHERE id=? AND (user_id=? OR ?=1)').bind(id,user,administrator?1:0).first<{id:string;lease:string|null;user_id:string;status:string;result_key:string|null;updated_at:number}>();if(!job)return json({error:'Task unavailable.'},404);const asAdmin=job.user_id!==user;if(asAdmin&&(!administrator||body.adminEdit!==true))return json({error:'Enable administrator editing before submitting changes.'},403);
 await ensureConversation();const prior=await db.prepare('SELECT * FROM task_messages WHERE job_id=? AND id=?').bind(id,body.id).first<MessageRow>();
 const snapshot=await canvasSnapshot(id,body.baseSha256);if(!snapshot)return json({error:'This version is unavailable. Refresh the canvas.'},409);
 let changes,compiled;try{changes=validateEdits(body.changes,snapshot);compiled=visualEditMessage(snapshot,changes,asAdmin);}catch(e){return json({error:e instanceof Error?e.message:'Invalid changes.'},400);}
 if(prior)return prior.body===compiled&&prior.role==='user'&&prior.kind==='revision'?json({message:message(prior),status:job.status}):json({error:'This request ID was used for different changes.'},409);
 let uploads;try{
  const pictures=changes.filter(c=>c.kind==='replace_image');if(pictures.length>10)throw Error();
  uploads=(await Promise.all(pictures.map(c=>resolveUploads(user,`message:${id}:${c.id}`,[c.uploadId])))).flat();
  if(uploads.some(u=>!['png','jpg','jpeg'].includes(u.meta.ext)))throw Error();
 }catch{return json({error:'A replacement image is missing, expired or unsupported. Choose it again.'},400);}
 const head=await editableSource(job),current=head?await canvasSnapshot(id,head.sha256):null;const progressive=job.status==='running';
 if(!head||!current||!unchangedPages(snapshot,current,Array.from(new Set(changes.map(c=>c.page)))))return json({error:'An affected page changed. Refresh that page before submitting.',code:'stale_canvas'},409);
 const sourceRow=progressive?await db.prepare('SELECT source_key FROM canvas_sources WHERE job_id=? AND sha256=? AND producer_lease=?').bind(id,body.baseSha256,job.lease).first<{source_key:string}>():null;const sourceKey=progressive?(sourceRow?.source_key||job.result_key):job.result_key;const source=sourceKey?await files().head(sourceKey):null;
 if(source?.customMetadata?.sha256!==body.baseSha256)return json({error:'The current source is unavailable.',code:'stale_canvas'},409);
 if(!['complete','running','queued'].includes(job.status))return json({error:'Resume this task before submitting changes.'},409);
 if(job.status==='complete'){
  const recovery=await db.prepare('SELECT job_id FROM task_recovery WHERE job_id=? AND resumable=1').bind(id).first();const draft=await db.prepare('SELECT job_id FROM task_drafts WHERE job_id=?').bind(id).first();
  if(!recovery&&!draft)return json({error:'No editable checkpoint is available for this historical task.'},409);
 }
 const original=await files().get(sourceKey!);if(!original||original.size>30*1024*1024)return json({error:'Source PPTX unavailable or exceeds 30 MiB.'},409);
 await files().put(`canvas-inputs/${id}/${body.id}/baseline.pptx`,original.body,{httpMetadata:{contentType:'application/vnd.openxmlformats-officedocument.presentationml.presentation'},customMetadata:{sha256:body.baseSha256}});
 for(const upload of uploads)await copyUpload(upload,messageFileKey(id,body.id,upload.meta.id));
 const attachments=JSON.stringify(uploads.map(u=>u.meta));
 const now=Date.now();
 // The insert and resume share one atomic D1 batch. Never queue work without its
 // revision, spend quota again, or overwrite a concurrently delivered artifact.
 const targetColumn=progressive?'lease':'result_key',targetValue=progressive?job.lease:job.result_key;await ensureProgressiveCanvas();
 const inserted=await db.batch([
  db.prepare("INSERT INTO task_messages(id,job_id,user_id,role,kind,body,attachments,status,created_at,updated_at) SELECT ?,?,?,'user','revision',?,?,'pending',?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND user_id=? AND "+targetColumn+"=? AND status IN ('complete','running','queued')) AND (SELECT COUNT(*) FROM task_messages WHERE job_id=?)<? AND (SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running'))<100 ON CONFLICT(job_id,id) DO NOTHING").bind(body.id,id,user,compiled,attachments,now,now,id,job.user_id,targetValue,id,MAX_MESSAGES),
  db.prepare("UPDATE jobs SET status=CASE WHEN status='complete' THEN 'queued' ELSE status END,lease=CASE WHEN status='complete' THEN NULL ELSE lease END,summary=CASE WHEN status='complete' THEN 'resume_requested' ELSE NULL END,updated_at=? WHERE id=? AND user_id=? AND "+targetColumn+"=? AND status IN ('complete','running','queued') AND EXISTS(SELECT 1 FROM task_messages WHERE job_id=? AND id=?)").bind(now,id,job.user_id,targetValue,id,body.id),
  ...Array.from(new Set(changes.map(c=>c.page))).map(page=>db.prepare('DELETE FROM canvas_page_locks WHERE job_id=? AND page=? AND EXISTS(SELECT 1 FROM task_messages WHERE job_id=? AND id=?)').bind(id,page,id,body.id))
 ]);
 const saved=await db.prepare('SELECT * FROM task_messages WHERE job_id=? AND id=?').bind(id,body.id).first<MessageRow>();if(!saved)return json({error:'Task changed or the queue is full. Your notes are retained; refresh and retry.'},409);
 return json({message:message(saved),status:job.status==='complete'?'queued':job.status,acceptedChanges:changes.length},inserted[0].meta.changes?201:200);
}
