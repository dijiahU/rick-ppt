import {files,json} from './server';
import {bundleFailure,currentReviewDelivery,stillCurrentReviewDelivery,ReviewBundleError,MAX_REVIEW_BUNDLE} from './review-bundle';

// Call only after owner/admin authorization. Never select an older task version.
export async function bundleDownload(request:Request,id:string){
 try{
  const d=await currentReviewDelivery(id);
  if(new URL(request.url).searchParams.get('info')==='1')return json({available:d.bundleArtifact.available,bytes:d.bundleArtifact.available?d.bundleArtifact.bytes:null});
  if(!d.bundleArtifact.available||!d.bundle||!d.bundleKey||!d.deliveryVersion)return json({error:'No interactive ZIP is available for this delivery.'},404);
  const object=await files().get(d.bundleKey);
  if(!object)return json({error:'Interactive ZIP is unavailable.'},404);
  try{
   if(!Number.isSafeInteger(object.size)||object.size<4||object.size>MAX_REVIEW_BUNDLE)throw new ReviewBundleError(413,'bundle_too_large','Bundle is too large');
   if(object.httpEtag!==d.bundle.httpEtag||object.size!==d.bundle.size)throw new ReviewBundleError(412,'delivery_changed','Delivery changed; refresh and download again');
   await stillCurrentReviewDelivery(id,d.deliveryVersion);
  }catch(error){await object.body.cancel();throw error;}
  return new Response(object.body,{headers:{'Content-Type':'application/zip','Content-Disposition':'attachment; filename="presentation-interactive.zip"','Content-Length':String(object.size),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
 }catch(error){return bundleFailure(error);}
}
