import {draftInfo} from '@/lib/drafts';
import { database,json,userId } from '@/lib/server';
import { parseProgress } from '@/lib/progress';
import {isAdmin} from '@/lib/admin';
import {queueHealth} from '@/lib/queue';
import {QUEUE_POSITION_SQL} from '@/lib/queue-state';
export const dynamic='force-dynamic';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}) {
  const user=await userId();if(!user)return json({error:'请先登录。'},401);
  const {id}=await params;
  const admin=await isAdmin();
  const job=await database().prepare(`SELECT title,brief,pages,status,created_at,updated_at,progress,result_key,user_id,${QUEUE_POSITION_SQL} AS queuePosition FROM jobs WHERE id=? AND (user_id=? OR ?=1)`).bind(id,user,admin?1:0).first<{title:string;brief:string;pages:number;status:string;created_at:number;updated_at:number;progress:string|null;result_key:string|null;user_id:string;queuePosition:number|null}>();
  if(!job)return json({error:'任务不存在。'},404);
  let progress=null;try{progress=parseProgress(JSON.parse(job.progress||'null'));}catch{}
  return json({draft:await draftInfo(id),title:job.title,brief:job.brief,pages:job.pages,status:job.status,createdAt:job.created_at,updatedAt:job.updated_at,download:job.status==='complete'&&!!job.result_key,scope:job.user_id===user?'user':'admin',canInspectExecution:admin,progress,queuePosition:job.queuePosition,queue:job.status==='queued'?await queueHealth():null});
}
