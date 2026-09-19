import {database,files,json,userId} from '@/lib/server';
import {ensureConversation} from '@/lib/conversation';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string;version:string}>}){
 const user=await userId();if(!user)return json({error:'请先登录。'},401);const {id,version}=await params;
 if(!await database().prepare('SELECT id FROM jobs WHERE id=? AND user_id=?').bind(id,user).first())return json({error:'任务不存在。'},404);
 await ensureConversation();const row=await database().prepare('SELECT result_key,bundle_key FROM task_versions WHERE job_id=? AND id=?').bind(id,version).first<{result_key:string|null;bundle_key:string|null}>();
 const bundle=new URL(request.url).searchParams.get('kind')==='bundle',key=bundle?row?.bundle_key:row?.result_key;if(!key)return json({error:'此版本文件不存在。'},404);
 const object=await files().get(key);if(!object)return json({error:'文件不存在。'},404);
 return new Response(object.body,{headers:{'Content-Type':bundle?'application/zip':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Content-Disposition':`attachment; filename="presentation-${version}.${bundle?'zip':'pptx'}"`,'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
}
