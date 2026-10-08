import {MAX_SLIDES,MAX_PROGRESS_BYTES} from '@/lib/slide-limits.mjs';
import { database,files,json,workerAuthorized } from '@/lib/server';
import { parseProgress } from '@/lib/progress';
import {parseAttachments,attachmentKey,attachmentResponse} from '@/lib/attachments';
import {boundedBody} from '@/lib/attachments';
import {RETRY_JOB} from '@/lib/queries';
import {storeTrace} from '@/lib/admin-trace';
import {ensureConversation} from '@/lib/conversation';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}) {
  if(!await workerAuthorized(request)) return json({error:'Unauthorized'},401);
  const {id}=await params, lease=request.headers.get('X-Job-Lease');
  const db=database(),query=new URL(request.url).searchParams,action=query.get('action');
  const completionRevision=query.has('revision')?Number(query.get('revision')):null;
  const expectedDigest=query.get('sha256');
  if(['complete','delivery-ready'].includes(action||'')&&completionRevision!==null&&(!Number.isSafeInteger(completionRevision)||completionRevision<0))return json({error:'Invalid completion revision'},400);
  if(expectedDigest!==null&&!/^[a-f0-9]{64}$/.test(expectedDigest))return json({error:'Invalid artifact checksum'},400);
  if(action==='retry'){
    let body;try{body=JSON.parse(new TextDecoder().decode(await boundedBody(request,1024)));}catch{return json({error:'Invalid retry request'},400);}
    if(!body||!Number.isSafeInteger(body.expectedUpdatedAt)||body.expectedUpdatedAt<=0)return json({error:'Expected failed attempt timestamp required'},400);
    const row=await db.prepare(RETRY_JOB).bind(Math.max(Date.now(),body.expectedUpdatedAt+1),id,body.expectedUpdatedAt).first();
    return row?json(row):json({error:'Task changed, not failed, already delivered, or queue full'},409);
  }
  if(!lease) return json({error:'Lease required'},400);
  const job=await db.prepare('SELECT id,attachments,status,result_key,summary FROM jobs WHERE id=? AND lease=?').bind(id,lease).first<{id:string;attachments:string|null;status:string;result_key:string|null;summary:string|null}>();
  if(!job) return json({error:'Lease expired'},409);
  if(job.status==='paused'&&action==='heartbeat')return json({ok:true,stop:true});
  const resultKey=`results/${id}/${lease}${expectedDigest?'-'+expectedDigest:''}.pptx`;
  async function storedReceipt(){
    const object=await files().head(job!.result_key||resultKey);
    return {status:job!.status,sha256:object?.customMetadata?.sha256||null,revision:object?.customMetadata?.revision!==undefined?Number(object.customMetadata.revision):null};
  }
  if(action==='delivery-status')return json(await storedReceipt());
  async function recordVersion(){
    if(completionRevision===null)return;
    await ensureConversation();
    const bundleKey=`bundles/${id}/${lease}.zip`,bundle=await files().head(bundleKey);
    await db.prepare("INSERT INTO task_versions(id,job_id,result_key,bundle_key,revision,created_at) SELECT ?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='complete' AND result_key=?) ON CONFLICT(id) DO NOTHING").bind(lease,id,resultKey,bundle?bundleKey:null,completionRevision,Date.now(),id,lease,resultKey).run();
  }
  // A lost acknowledgement may be safely retried under the same lease.
  if(action==='complete'&&job.status==='complete'&&job.result_key===resultKey){
    if(expectedDigest!==null){const receipt=await storedReceipt();if(receipt.sha256!==expectedDigest||receipt.revision!==completionRevision)return json({error:'Delivery receipt mismatch'},409);}
    await recordVersion();return json({ok:true});
  }
  if(action==='fail'&&job.status==='failed')return json({ok:true});
  // Final upload/error records may arrive just after completion, under the same lease.
  if(action==='trace'&&['running','complete','failed','paused'].includes(job.status))return storeTrace(request,id,lease);
  if(job.status!=='running')return json({error:'Lease expired'},409);
  if(action==='delivery-reset'){
    await db.prepare("UPDATE jobs SET summary=NULL WHERE id=? AND lease=? AND status='running' AND summary='delivery_pending'").bind(id,lease).run();return json({ok:true});
  }
  if(action==='delivery-ready'){
    if(completionRevision===null||expectedDigest===null)return json({error:'Delivery identity required'},400);
    await ensureConversation();
    const ready=await db.prepare("UPDATE jobs SET summary='delivery_pending',updated_at=? WHERE id=? AND lease=? AND status='running' AND NOT EXISTS(SELECT 1 FROM task_messages WHERE job_id=? AND role='user' AND kind='revision' AND (status<>'applied' OR seq>?))").bind(Date.now(),id,lease,id,completionRevision).run();
    if(ready.meta.changes)return json({ok:true});
    const current=await db.prepare("SELECT id FROM jobs WHERE id=? AND lease=? AND status='running'").bind(id,lease).first();
    return current?json({error:'New revision awaits processing'},412):json({error:'Lease expired'},409);
  }
  if(action==='draft-source'){
    if(job.summary!=='resume_from_draft')return json({error:'Draft continuation was not requested'},409);
    const draft=await db.prepare('SELECT object_key,sha256,bytes FROM task_drafts WHERE job_id=?').bind(id).first<{object_key:string;sha256:string;bytes:number}>();
    if(!draft)return json({error:'Progress copy unavailable'},404);
    const object=await files().get(draft.object_key);if(!object)return json({error:'Progress copy unavailable'},404);
    return new Response(object.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Content-Length':String(draft.bytes),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','ETag':'"'+draft.sha256+'"'}});
  }
  if(action==='attachment'){
    const file=new URL(request.url).searchParams.get('file');
    const meta=parseAttachments(job.attachments).find(x=>x.id===file);
    if(!meta)return json({error:'Not found'},404);
    const object=await files().get(attachmentKey(id,meta.id));
    if(!object)return json({error:'Not found'},404);
    return attachmentResponse(object,meta);
  }
  if(action==='progress') {
    const length=Number(request.headers.get('Content-Length'));
    if(!length||length>MAX_PROGRESS_BYTES)return json({error:'Invalid progress size'},413);
    let progress;try{progress=parseProgress(JSON.parse(new TextDecoder().decode(await boundedBody(request,MAX_PROGRESS_BYTES))));}catch{return json({error:'Invalid progress'},400);}
    if(!progress)return json({error:'Invalid progress'},400);
    progress.updatedAt=Date.now();
    const result=await db.prepare("UPDATE jobs SET progress=?,updated_at=? WHERE id=? AND lease=? AND status='running'").bind(JSON.stringify(progress),Date.now(),id,lease).run();
    return result.meta.changes?json({ok:true}):json({error:'Lease expired'},409);
  }
  if(action==='preview') {
    const slide=Number(new URL(request.url).searchParams.get('slide'));
    const length=Number(request.headers.get('Content-Length'));
    if(!Number.isInteger(slide)||slide<1||slide>MAX_SLIDES)return json({error:'Invalid slide'},400);
    if(!length||length>2*1024*1024)return json({error:'Preview too large'},413);
    const bytes=await request.arrayBuffer(),data=new Uint8Array(bytes);
    const signature=[137,80,78,71,13,10,26,10];
    if(bytes.byteLength!==length||signature.some((v,i)=>data[i]!==v))return json({error:'PNG required'},400);
    await files().put(`previews/${id}/${lease}/${slide}.png`,bytes,{httpMetadata:{contentType:'image/png'}});
    return json({ok:true});
  }
  if(action==='heartbeat') {
    const [renewed]=await db.batch([db.prepare("UPDATE jobs SET updated_at=? WHERE id=? AND lease=? AND status='running'").bind(Date.now(),id,lease),db.prepare('UPDATE worker SET heartbeat=? WHERE id=?').bind(Date.now(),'primary')]);
    return renewed.meta.changes?json({ok:true}):json({error:'Lease expired'},409);
  }
  if(action==='complete') {
    if(completionRevision!==null)await ensureConversation();
    const length=Number(request.headers.get('Content-Length'));
    if(!length||length>30*1024*1024) return json({error:'PPTX must be at most 30 MB'},413);
    const bytes=await request.arrayBuffer(); if(bytes.byteLength!==length||new Uint8Array(bytes)[0]!==80||new Uint8Array(bytes)[1]!==75) return json({error:'Invalid PPTX upload'},400);
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
    if(expectedDigest!==null&&digest!==expectedDigest)return json({error:'Artifact checksum mismatch'},400);
    const key=resultKey;
    await files().put(key,bytes,{httpMetadata:{contentType:'application/vnd.openxmlformats-officedocument.presentationml.presentation'},customMetadata:{sha256:digest,...(completionRevision!==null?{revision:String(completionRevision)}:{})}});
    const result=completionRevision===null?
      await db.prepare("UPDATE jobs SET status='complete',result_key=?,summary='complete',updated_at=? WHERE id=? AND lease=? AND status='running'").bind(key,Date.now(),id,lease).run():
      await db.prepare("UPDATE jobs SET status='complete',result_key=?,summary='complete',updated_at=? WHERE id=? AND lease=? AND status='running' AND NOT EXISTS(SELECT 1 FROM task_messages WHERE job_id=? AND role='user' AND kind='revision' AND (status<>'applied' OR seq>?))").bind(key,Date.now(),id,lease,id,completionRevision).run();
    if(!result.meta.changes){
      const completed=await db.prepare("SELECT id FROM jobs WHERE id=? AND lease=? AND status='complete' AND result_key=?").bind(id,lease,key).first();
      if(completed){await recordVersion();return json({ok:true});}
      if(completionRevision!==null){
        const current=await db.prepare("SELECT id FROM jobs WHERE id=? AND lease=? AND status='running'").bind(id,lease).first();
        if(current)return json({error:'New user input must be handled before delivery'},412);
      }
      // Keep uncertain objects: another in-flight completion must not lose its file.
      return json({error:'Lease expired'},409);
    }
    await recordVersion();return json({ok:true});
  }
  if(action==='fail') {
    const result=await db.prepare("UPDATE jobs SET status='failed',summary=CASE WHEN summary='delivery_pending' THEN summary ELSE 'failed' END,updated_at=? WHERE id=? AND lease=? AND status='running'").bind(Date.now(),id,lease).run();
    if(result.meta.changes)return json({ok:true});
    const failed=await db.prepare("SELECT id FROM jobs WHERE id=? AND lease=? AND status='failed'").bind(id,lease).first();
    return failed?json({ok:true}):json({error:'Lease expired'},409);
  }
  return json({error:'Unknown action'},400);
}
