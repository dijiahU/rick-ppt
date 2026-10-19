import {adminGate} from '@/lib/admin';
import {database,files,json} from '@/lib/server';
import {parseAttachments,attachmentKey,attachmentResponse} from '@/lib/attachments';
export async function GET(request:Request,{params}:{params:Promise<{id:string;file:string}>}){
 const denied=await adminGate();if(denied)return denied;
 const {id,file}=await params;
 const job=await database().prepare('SELECT attachments FROM jobs WHERE id=?').bind(id).first<{attachments:string|null}>();
 const meta=parseAttachments(job?.attachments).find(x=>x.id===file);
 if(!meta)return json({error:'Not found'},404);
 const object=await files().get(attachmentKey(id,meta.id));
 return object?attachmentResponse(object,meta,new URL(request.url).searchParams.get('preview')==='1'):json({error:'Not found'},404);
}
