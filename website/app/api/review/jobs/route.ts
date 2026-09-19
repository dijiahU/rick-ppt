import {reviewGate} from '@/lib/review-auth';
import {adminQuery} from '@/lib/admin-query';
import {database,json} from '@/lib/server';
export const dynamic='force-dynamic';
export async function GET(request:Request){
 const denied=await reviewGate(request);if(denied)return denied;
 let query;try{query=adminQuery(new URL(request.url));}catch{return json({error:'Invalid filter'},400);}
 const {where,args,page,limit,offset}=query,db=database();
 const [total,rows]=await Promise.all([
  db.prepare(`SELECT COUNT(*) AS count FROM jobs ${where}`).bind(...args).first<{count:number}>(),
  db.prepare(`SELECT id,user_id,title,status,pages,language,created_at,updated_at,CASE WHEN status='complete' AND result_key IS NOT NULL THEN 1 ELSE 0 END AS has_pptx FROM jobs ${where} ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?`).bind(...args,limit,offset).all()
 ]);
 return json({schemaVersion:1,readOnly:true,total:total?.count||0,page,limit,jobs:rows.results});
}
