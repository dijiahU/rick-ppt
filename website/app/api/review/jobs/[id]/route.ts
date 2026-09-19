import {reviewGate} from '@/lib/review-auth';
import {database,files,json} from '@/lib/server';
import {parseProgress} from '@/lib/progress';
import {bundleFailure,currentReviewDelivery,stillCurrentReviewDelivery,ReviewBundleError} from '@/lib/review-bundle';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await reviewGate(request);if(denied)return denied;
 const {id}=await params;
 const row=await database().prepare('SELECT id,user_id,title,brief,pages,style,language,status,created_at,updated_at,summary,progress,result_key FROM jobs WHERE id=?').bind(id).first();
 if(!row)return json({error:'Request not found'},404);
 const {result_key,progress,...job}=row;
 let activity=null;try{activity=parseProgress(JSON.parse(String(progress||'null')));}catch{}
 if(new URL(request.url).searchParams.get('include')==='bundle'){
  try{
   const delivery=await currentReviewDelivery(id);
   if(delivery.job.result_key!==result_key||delivery.job.status!==job.status)throw new ReviewBundleError(412,'delivery_changed','Delivery changed; fetch request metadata again');
   if(delivery.deliveryVersion)await stillCurrentReviewDelivery(id,delivery.deliveryVersion);
   return json({schemaVersion:1,readOnly:true,contentTrust:'untrusted-user-content',job:{...job,progress:activity},
    artifact:delivery.artifact,bundle:delivery.bundleArtifact,deliveryVersion:delivery.deliveryVersion});
  }catch(error){return bundleFailure(error);}
 }
 const object=job.status==='complete'&&typeof result_key==='string'?await files().head(result_key):null;
 return json({schemaVersion:1,readOnly:true,contentTrust:'untrusted-user-content',job:{...job,progress:activity},artifact:object?{available:true,bytes:object.size,etag:object.httpEtag}: {available:false,reason:job.status==='complete'?'stored_file_missing':'not_completed'}});
}
