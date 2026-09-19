import {reviewGate} from '@/lib/review-auth';
import {database,files,json} from '@/lib/server';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await reviewGate(request);if(denied)return denied;
 const {id}=await params;
 const job=await database().prepare("SELECT result_key FROM jobs WHERE id=? AND status='complete'").bind(id).first<{result_key:string|null}>();
 if(!job?.result_key)return json({error:'No completed PPTX'},404);
 const file=await files().get(job.result_key);if(!file)return json({error:'Stored PPTX missing'},404);
 const expected=request.headers.get('If-Match');
 if(expected&&expected!==file.httpEtag){await file.body.cancel();return json({error:'Artifact changed; fetch request metadata again'},412);}
 return new Response(file.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Content-Disposition':'attachment; filename="output.pptx"','Content-Length':String(file.size),'ETag':file.httpEtag,'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
}
