import {database,json,userId,sameOrigin} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';
import {ensureConversation} from '@/lib/conversation';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'请先登录。'},401);if(!sameOrigin(request))return json({error:'来源无效。'},403);
 const {id}=await params;let body;try{body=JSON.parse(new TextDecoder().decode(await boundedBody(request,1024)));}catch{return json({error:'请求无效。'},400);}
 if(!body||!Number.isSafeInteger(body.expectedUpdatedAt))return json({error:'请刷新任务后重试。'},400);
 await ensureConversation();const db=database();
 const job=await db.prepare('SELECT status,updated_at FROM jobs WHERE id=? AND user_id=?').bind(id,user).first<{status:string;updated_at:number}>();
 if(!job)return json({error:'任务不存在。'},404);
 if(job.status==='queued'||job.status==='running')return json({ok:true,status:job.status});
 const resumed=await db.prepare("UPDATE jobs SET status='queued',lease=NULL,summary='resume_requested',updated_at=? WHERE id=? AND user_id=? AND status IN ('failed','complete') AND updated_at=? AND EXISTS(SELECT 1 FROM task_recovery WHERE job_id=? AND resumable=1) AND (SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running'))<100 RETURNING id,status").bind(Math.max(Date.now(),body.expectedUpdatedAt+1),id,user,body.expectedUpdatedAt,id).first();
 return resumed?json({ok:true,...resumed}):json({error:'当前没有可用恢复点、任务已变化或队列已满。'},409);
}
