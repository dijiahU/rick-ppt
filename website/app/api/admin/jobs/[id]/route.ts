import {adminGate} from '@/lib/admin';
import {database,json} from '@/lib/server';
import {parseProgress} from '@/lib/progress';
import {parseAttachments} from '@/lib/attachments';
import {queueHealth} from '@/lib/queue';
import {QUEUE_POSITION_SQL} from '@/lib/queue-state';
export const dynamic='force-dynamic';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}) {
  const denied=await adminGate();if(denied)return denied;
  const {id}=await params;
  const row=await database().prepare(`SELECT id,user_id,title,brief,pages,style,language,status,created_at,updated_at,summary,result_key,progress,attachments,${QUEUE_POSITION_SQL} AS queuePosition FROM jobs WHERE id=?`).bind(id).first();
  if(!row)return json({error:'Request not found.'},404);
  const {result_key,progress,attachments,...job}=row;
  let parsed=null;try{parsed=parseProgress(JSON.parse(String(progress||'null')));}catch{}
  return json({...job,queue:job.status==='queued'?await queueHealth():null,download:job.status==='complete'&&!!result_key,progress:parsed,attachments:parseAttachments(attachments)});
}
