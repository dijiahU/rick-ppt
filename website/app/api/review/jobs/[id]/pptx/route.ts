import {reviewGate} from '@/lib/review-auth';
import {database,files,json} from '@/lib/server';
import {bundleFailure,stillCurrentReviewDelivery,DELIVERY_HEADER,ReviewBundleError} from '@/lib/review-bundle';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await reviewGate(request);if(denied)return denied;
 const {id}=await params;
 const job=await database().prepare("SELECT result_key FROM jobs WHERE id=? AND status='complete'").bind(id).first<{result_key:string|null}>();
 if(!job?.result_key)return json({error:'No completed PPTX'},404);
 const file=await files().get(job.result_key);if(!file)return json({error:'Stored PPTX missing'},404);
 const expected=request.headers.get('If-Match');
 if(expected&&expected!==file.httpEtag){await file.body.cancel();return json({error:'Artifact changed; fetch request metadata again'},412);}
 const version=request.headers.get(DELIVERY_HEADER);
 if(version){
  try{
   const current=await stillCurrentReviewDelivery(id,version);
   if(current.job.result_key!==job.result_key||current.pptx?.httpEtag!==file.httpEtag||current.pptx?.size!==file.size)throw new ReviewBundleError(412,'delivery_changed','Delivery changed; fetch request metadata again');
  }catch(error){await file.body.cancel();return bundleFailure(error);}
 }
 return new Response(file.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Content-Disposition':'attachment; filename="output.pptx"','Content-Length':String(file.size),'ETag':file.httpEtag,...(version?{[DELIVERY_HEADER]:version}:{}),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
}
