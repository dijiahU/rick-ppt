import {database,json,userId,sameOrigin} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';
import {isAdmin} from '@/lib/admin';

export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'请先登录。'},401);
 if(!sameOrigin(request))return json({error:'来源无效。'},403);
 let body;try{body=JSON.parse(new TextDecoder().decode(await boundedBody(request,1024)));}catch{return json({error:'请求无效。'},400);}
 if(!body||!Number.isSafeInteger(body.expectedUpdatedAt))return json({error:'请刷新后重试。'},400);
 const {id}=await params,admin=await isAdmin(),db=database();
 const job=await db.prepare('SELECT status FROM jobs WHERE id=? AND (user_id=? OR ?=1)').bind(id,user,admin?1:0).first<{status:string}>();
 if(!job)return json({error:'任务不存在。'},404);
 if(job.status==='paused')return json({ok:true,status:'paused'});
 // Heartbeats continually change updated_at. Pausing always targets the currently
 // running/queued row; the atomic status predicate fences a concurrent delivery.
 const row=await db.prepare("UPDATE jobs SET summary=CASE WHEN status='running' THEN 'pause_requested' ELSE 'paused' END,status='paused',updated_at=? WHERE id=? AND (user_id=? OR ?=1) AND status IN ('queued','running') RETURNING status,summary,updated_at")
  .bind(Date.now(),id,user,admin?1:0).first();
 return row?json({ok:true,...row}):json({error:'任务已经结束，请刷新查看。'},409);
}
