import {database,files,json,workerAuthorized} from '@/lib/server';
import {boundedBody,attachmentResponse} from '@/lib/attachments';
import {ensureConversation,message,checkpointValue,messageAttachment,MAX_MESSAGE,uuid,type MessageRow} from '@/lib/conversation';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);
 const {id}=await params,lease=request.headers.get('X-Job-Lease'),action=new URL(request.url).searchParams.get('action');
 if(!lease)return json({error:'Lease required'},400);
 const db=database();const job=await db.prepare('SELECT id,user_id,status,result_key FROM jobs WHERE id=? AND lease=?').bind(id,lease).first<{id:string;user_id:string;status:string;result_key:string|null}>();
 if(!job||!(job.status==='running'||(action==='version'&&job.status==='complete')))return json({error:'Lease expired'},409);
 await ensureConversation();const now=Date.now();
 if(action==='poll'){
  const rows=await db.prepare("SELECT * FROM task_messages WHERE job_id=? AND role='user' AND status IN ('pending','received') ORDER BY seq LIMIT 100").bind(id).all<MessageRow>();
  const latest=await db.prepare("SELECT COALESCE(MAX(seq),0) revision FROM task_messages WHERE job_id=? AND role='user' AND kind='revision'").bind(id).first<{revision:number}>();
  return json({messages:rows.results.map(message),revision:latest?.revision??0});
 }
 if(action==='attachment'){
  const q=new URL(request.url).searchParams,attachment=await messageAttachment(id,q.get('message')??'',q.get('file')??'');
  return attachment?attachmentResponse(attachment.object,attachment.meta):json({error:'Not found'},404);
 }
 let body;try{body=JSON.parse(new TextDecoder().decode(await boundedBody(request,40000)));}catch{return json({error:'Invalid body'},400);}
 if(!body||typeof body!=='object'||Array.isArray(body))return json({error:'Invalid body'},400);
 if(action==='ack'||action==='applied'){
  const ids=body.ids;if(!Array.isArray(ids)||!ids.length||ids.length>100||ids.some(x=>typeof x!=='string'||!uuid.test(x))||new Set(ids).size!==ids.length)return json({error:'Invalid message IDs'},400);
  if(action==='applied'&&(!Number.isSafeInteger(body.revision)||body.revision<0))return json({error:'Revision required'},400);
  const selected=await db.prepare(`SELECT id,seq,kind FROM task_messages WHERE job_id=? AND role='user' AND id IN (${ids.map(()=>'?').join(',')})`).bind(id,...ids).all<{id:string;seq:number;kind:string}>();
  if(selected.results.length!==ids.length)return json({error:'Message not found'},404);
  if(action==='applied'&&selected.results.some(row=>row.kind==='revision'&&row.seq>body.revision))return json({error:'Applied revision is older than the request'},409);
  const statements=ids.map(messageId=>action==='ack'?
   db.prepare("UPDATE task_messages SET status='received',updated_at=? WHERE job_id=? AND id=? AND role='user' AND status='pending' AND EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='running')").bind(now,id,messageId,id,lease):
   db.prepare("UPDATE task_messages SET status='applied',revision=?,updated_at=? WHERE job_id=? AND id=? AND role='user' AND status='received' AND EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='running')").bind(body.revision,now,id,messageId,id,lease));
  await db.batch(statements);const current=await db.prepare("SELECT id FROM jobs WHERE id=? AND lease=? AND status='running'").bind(id,lease).first();
  return current?json({ok:true}):json({error:'Lease expired'},409);
 }
 if(action==='assistant'){
  if(typeof body.id!=='string'||!uuid.test(body.id)||typeof body.body!=='string'||!body.body.trim()||body.body.length>MAX_MESSAGE)return json({error:'Invalid assistant message'},400);
  const row=await db.prepare("INSERT INTO task_messages(id,job_id,user_id,role,kind,body,attachments,status,created_at,updated_at) SELECT ?,?,?,'assistant','chat',?,'[]','applied',?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='running') ON CONFLICT(job_id,id) DO NOTHING RETURNING seq").bind(body.id,id,job.user_id,body.body,now,now,id,lease).first();
  const existing=row??await db.prepare("SELECT seq FROM task_messages WHERE job_id=? AND id=? AND role='assistant'").bind(id,body.id).first();return existing?json({ok:true,...existing}):json({error:'Lease expired'},409);
 }
 if(action==='checkpoint'){
  const value=checkpointValue(body);if(!value)return json({error:'Invalid checkpoint metadata'},400);
  const changed=await db.prepare("INSERT INTO task_recovery(job_id,checkpoint,revision,last_message_seq,resumable,updated_at) SELECT ?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='running') ON CONFLICT(job_id) DO UPDATE SET checkpoint=excluded.checkpoint,revision=excluded.revision,last_message_seq=excluded.last_message_seq,resumable=excluded.resumable,updated_at=excluded.updated_at WHERE excluded.revision>=task_recovery.revision AND excluded.last_message_seq>=task_recovery.last_message_seq").bind(id,JSON.stringify(value),value.revision,value.lastMessageSeq,value.resumable?1:0,now,id,lease).run();
  return changed.meta.changes?json({ok:true}):json({error:'Stale checkpoint or lease'},409);
 }
 if(action==='version'){
  if(!job.result_key||!Number.isSafeInteger(body.revision)||body.revision<0)return json({error:'Completed artifact required'},409);
  const key=`bundles/${id}/${lease}.zip`,bundle=await files().head(key);
  const result=await db.prepare("INSERT INTO task_versions(id,job_id,result_key,bundle_key,revision,created_at) SELECT ?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='complete') ON CONFLICT(id) DO NOTHING").bind(lease,id,job.result_key,bundle?key:null,body.revision,now,id,lease).run();
  return json({ok:true,created:!!result.meta.changes});
 }
 return json({error:'Unknown action'},400);
}
