import {adminGate} from '@/lib/admin';
import {adminQuery} from '@/lib/admin-query';
import {database,json} from '@/lib/server';
import {queueHealth} from '@/lib/queue';
import {QUEUE_POSITION_SQL} from '@/lib/queue-state';
import {parseProgress} from '@/lib/progress';
export const dynamic='force-dynamic';
export async function GET(request:Request) {
  const denied=await adminGate();if(denied)return denied;
  let query;try{query=adminQuery(new URL(request.url));}catch{return json({error:'Invalid filter.'},400);}
  const {where,args,page,limit,offset}=query,db=database();
  const [counts,total,rows,queue]=await Promise.all([
    db.prepare("SELECT COUNT(*) AS total,COUNT(DISTINCT user_id) AS users,COALESCE(SUM(status='queued'),0) AS queued,COALESCE(SUM(status='running'),0) AS running,COALESCE(SUM(status='complete'),0) AS complete,COALESCE(SUM(status='failed'),0) AS failed FROM jobs").first(),
    db.prepare(`SELECT COUNT(*) AS count FROM jobs ${where}`).bind(...args).first<{count:number}>(),
    db.prepare(`SELECT id,user_id,title,status,pages,language,created_at,updated_at,progress,${QUEUE_POSITION_SQL} AS queuePosition FROM jobs ${where} ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?`).bind(...args,limit,offset).all(),queueHealth()]);
  const jobs=rows.results.map(({progress,...row})=>{let p=null;try{p=parseProgress(JSON.parse(String(progress||'null')));}catch{}return {...row,activity:p?.notes?.at(-1)||p?.events.at(-1)||null,previewCount:p?.previews.length||0};});
  return json({counts,total:total?.count||0,page,limit,jobs,queue,online:queue.online,checkedAt:queue.checkedAt});
}
