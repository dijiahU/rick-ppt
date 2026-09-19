import {database,files,json,userId} from '@/lib/server';
import {parseAttachments,attachmentKey,attachmentResponse} from '@/lib/attachments';
export async function GET(_request:Request,{params}:{params:Promise<{id:string;file:string}>}){
 const user=await userId();if(!user)return json({error:'Unauthorized'},401);
 const {id,file}=await params;
 const job=await database().prepare('SELECT attachments FROM jobs WHERE id=? AND user_id=?').bind(id,user).first<{attachments:string|null}>();
 const meta=parseAttachments(job?.attachments).find(x=>x.id===file);
 if(!meta)return json({error:'Not found'},404);
 const object=await files().get(attachmentKey(id,meta.id));
 if(!object)return json({error:'Not found'},404);
 return attachmentResponse(object,meta);
}
