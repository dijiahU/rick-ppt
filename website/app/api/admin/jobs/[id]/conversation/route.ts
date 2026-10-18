import {adminGate} from '@/lib/admin';
import {database,json} from '@/lib/server';
import {attachmentResponse} from '@/lib/attachments';
import {message,messageAttachment,uuid,type MessageRow} from '@/lib/conversation';
export const dynamic='force-dynamic';
const PAGE_SIZE=100;
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await adminGate();if(denied)return denied;
 const {id}=await params,db=database();
 if(!await db.prepare('SELECT id FROM jobs WHERE id=?').bind(id).first())return json({error:'Request not found.'},404);
 const query=new URL(request.url).searchParams;
 if(query.has('file')){
  const file=query.get('file')??'',messageId=query.get('message')??'';
  if(!uuid.test(file)||!uuid.test(messageId))return json({error:'Invalid attachment.'},400);
  const attachment=await messageAttachment(id,messageId,file);
  return attachment?attachmentResponse(attachment.object,attachment.meta,query.get('preview')==='1'):json({error:'Not found.'},404);
 }
 const before=query.get('before');
 if(before!==null&&(!/^[1-9]\d*$/.test(before)||!Number.isSafeInteger(Number(before))))return json({error:'Invalid message cursor.'},400);
 const statement=before===null?
  db.prepare('SELECT seq,id,role,kind,body,attachments,status,revision,created_at,updated_at FROM task_messages WHERE job_id=? ORDER BY seq DESC LIMIT ?').bind(id,PAGE_SIZE+1):
  db.prepare('SELECT seq,id,role,kind,body,attachments,status,revision,created_at,updated_at FROM task_messages WHERE job_id=? AND seq<? ORDER BY seq DESC LIMIT ?').bind(id,Number(before),PAGE_SIZE+1);
 let rows:MessageRow[];
 try{rows=(await statement.all<MessageRow>()).results;}
 catch(error){
  // Older tasks can predate conversations. Viewing history never creates tables.
  if(!String(error).includes('no such table: task_messages'))throw error;
  rows=[];
 }
 const hasMore=rows.length>PAGE_SIZE,messages=rows.slice(0,PAGE_SIZE).reverse().map(message);
 return json({messages,hasMore,nextBefore:hasMore?messages[0].seq:null});
}
