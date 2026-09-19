import {database,files,json,userId,sameOrigin} from '@/lib/server';
import {boundedBody,MAX_TOTAL_BYTES,validFiles,validSignature,extension,type Attachment,parseAttachments,attachmentResponse} from '@/lib/attachments';
import {ensureConversation,conversation,message,MAX_MESSAGE,MAX_MESSAGES,uuid,messageFileKey,messageAttachment,type MessageRow} from '@/lib/conversation';
export const dynamic='force-dynamic';
async function owned(id:string,user:string){return database().prepare('SELECT id,status FROM jobs WHERE id=? AND user_id=?').bind(id,user).first<{id:string;status:string}>();}
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'请先登录。'},401);const {id}=await params;
 if(!await owned(id,user))return json({error:'任务不存在。'},404);await ensureConversation();
 const query=new URL(request.url).searchParams;
 if(query.has('file')){const attachment=await messageAttachment(id,query.get('message')??'',query.get('file')??'');return attachment?attachmentResponse(attachment.object,attachment.meta):json({error:'文件不存在。'},404);}
 return json(await conversation(id));
}
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'请先登录。'},401);
 if(!sameOrigin(request))return json({error:'来源无效。'},403);const {id}=await params;
 if(!await owned(id,user))return json({error:'任务不存在。'},404);
 const type=request.headers.get('Content-Type')??'';let body;let uploads:File[]=[];
 try{
  if(type.startsWith('multipart/form-data')){const bytes=await boundedBody(request,MAX_TOTAL_BYTES+128*1024);const form=await new Response(bytes,{headers:{'Content-Type':type}}).formData();body={id:form.get('id'),kind:form.get('kind'),body:form.get('body')};const entries=form.getAll('files');if(entries.some(x=>typeof x==='string'))throw Error();uploads=entries as File[];}
  else if(type.startsWith('application/json'))body=JSON.parse(new TextDecoder().decode(await boundedBody(request,40000)));
  else return json({error:'请求格式无效。'},415);
 }catch{return json({error:'内容或附件超过限制。'},400);}
 if(!body||typeof body.id!=='string'||!uuid.test(body.id)||!['chat','revision'].includes(body.kind)||typeof body.body!=='string'||body.body.length>MAX_MESSAGE||(!body.body.trim()&&!uploads.length)||!validFiles(uploads))return json({error:'请填写消息，最多 8000 字；最多 3 个附件，每个 10 MB、合计 20 MB。'},400);
 await ensureConversation();const db=database();
 const attachments:Attachment[]=[];const payloads:{meta:Attachment;data:Uint8Array}[]=[];
 for(const upload of uploads){const data=new Uint8Array(await upload.arrayBuffer()),ext=extension(upload.name);if(!validSignature(ext,data))return json({error:'附件格式与内容不符。'},400);const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data))).map(x=>x.toString(16).padStart(2,'0')).join('');const meta={id:crypto.randomUUID(),name:upload.name.replace(/[\\/\u0000-\u001f\u007f]/g,'_'),size:data.length,ext,sha256:hash};attachments.push(meta);payloads.push({meta,data});}
 const repeated=(row:MessageRow)=>{
  const identity=(items:Attachment[])=>JSON.stringify(items.map(({name,size,sha256})=>({name,size,sha256})));
  return row.role==='user'&&row.body===body.body.trim()&&row.kind===body.kind&&identity(parseAttachments(row.attachments))===identity(attachments)?json({message:message(row)}):json({error:'消息编号已用于不同的内容。'},409);
 };
 const prior=await db.prepare('SELECT * FROM task_messages WHERE job_id=? AND id=?').bind(id,body.id).first<MessageRow>();if(prior)return repeated(prior);
 // New objects use per-attempt file IDs. Failed/racing uploads are retained; existing files are never removed.
 try{
  for(const {meta,data} of payloads)await files().put(messageFileKey(id,body.id,meta.id),data,{httpMetadata:{contentType:'application/octet-stream'}});
  const now=Date.now();const row=await db.prepare("INSERT INTO task_messages(id,job_id,user_id,role,kind,body,attachments,status,created_at,updated_at) SELECT ?,?,?,'user',?,?,?,'pending',?,? WHERE (SELECT COUNT(*) FROM task_messages WHERE job_id=?)<? ON CONFLICT(job_id,id) DO NOTHING RETURNING *").bind(body.id,id,user,body.kind,body.body.trim(),JSON.stringify(attachments),now,now,id,MAX_MESSAGES).first<MessageRow>();
  if(row)return json({message:message(row)},201);
  const accepted=await db.prepare('SELECT * FROM task_messages WHERE job_id=? AND id=?').bind(id,body.id).first<MessageRow>();
  return accepted?repeated(accepted):json({error:'此任务已达到消息数量限制。'},429);
 }catch{
  try{const accepted=await db.prepare('SELECT * FROM task_messages WHERE job_id=? AND id=?').bind(id,body.id).first<MessageRow>();if(accepted)return repeated(accepted);}catch{}
  return json({error:'消息未确认保存，可安全重试。'},503);
 }
}
