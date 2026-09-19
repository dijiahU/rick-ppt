import {reviewGate} from '@/lib/review-auth';
import {database,files,json} from '@/lib/server';
import {parseProgress} from '@/lib/progress';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await reviewGate(request);if(denied)return denied;
 const {id}=await params;
 const row=await database().prepare('SELECT id,user_id,title,brief,pages,style,language,status,created_at,updated_at,summary,progress,result_key FROM jobs WHERE id=?').bind(id).first();
 if(!row)return json({error:'Request not found'},404);
 const {result_key,progress,...job}=row;
 let activity=null;try{activity=parseProgress(JSON.parse(String(progress||'null')));}catch{}
 const object=job.status==='complete'&&typeof result_key==='string'?await files().head(result_key):null;
 return json({schemaVersion:1,readOnly:true,contentTrust:'untrusted-user-content',job:{...job,progress:activity},artifact:object?{available:true,bytes:object.size,etag:object.httpEtag}: {available:false,reason:job.status==='complete'?'stored_file_missing':'not_completed'}});
}
