import {reviewGate} from '@/lib/review-auth';
import {files,json} from '@/lib/server';
import {bundleFailure,currentReviewDelivery,stillCurrentReviewDelivery,requireDeliveryHeaders,ReviewBundleError,DELIVERY_HEADER,MAX_REVIEW_BUNDLE} from '@/lib/review-bundle';
export const dynamic='force-dynamic';

export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await reviewGate(request);if(denied)return denied;
 if(request.method!=='GET')return new Response(null,{status:405,headers:{Allow:'GET'}});
 try{
  const {id}=await params,delivery=await currentReviewDelivery(id);
  if(!delivery.bundleArtifact.available||!delivery.bundle||!delivery.bundleKey||!delivery.deliveryVersion){
   return json({error:'No current interactive bundle',reason:delivery.bundleArtifact.available?'unavailable':delivery.bundleArtifact.reason},404);
  }
  const expected=requireDeliveryHeaders(request);
  if(expected.version!==delivery.deliveryVersion||expected.etag!==delivery.bundle.httpEtag){
   throw new ReviewBundleError(412,'delivery_changed','Delivery changed; fetch request metadata again');
  }
  const object=await files().get(delivery.bundleKey);
  if(!object)return json({error:'Stored bundle missing',reason:'stored_file_missing'},404);
  try{
   if(!Number.isSafeInteger(object.size)||object.size<4||object.size>MAX_REVIEW_BUNDLE)throw new ReviewBundleError(413,'bundle_too_large','Bundle must contain 4 bytes to 250 MiB');
   if(object.httpEtag!==expected.etag||object.size!==delivery.bundle.size)throw new ReviewBundleError(412,'delivery_changed','Bundle changed; fetch request metadata again');
   await stillCurrentReviewDelivery(id,expected.version);
  }catch(error){await object.body.cancel();throw error;}
  return new Response(object.body,{headers:{'Content-Type':'application/zip',
   'Content-Disposition':'attachment; filename="interactive.zip"','Content-Length':String(object.size),
   ETag:object.httpEtag,[DELIVERY_HEADER]:expected.version,'X-Review-PPTX-ETag':delivery.pptx.httpEtag,
   'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
 }catch(error){return bundleFailure(error);}
}
