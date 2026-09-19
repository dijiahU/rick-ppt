import {database,files,json} from './server';

export const MAX_REVIEW_BUNDLE=250*1024*1024;
export const DELIVERY_HEADER='X-Review-Delivery';
const uuid=/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
type Job={id:string;status:string;result_key:string|null};
type Version={id:string;job_id:string;result_key:string|null;bundle_key:string|null;revision:number;created_at:number};

export class ReviewBundleError extends Error {
 constructor(readonly status:number,readonly reason:string,message:string){super(message);}
}
export function bundleFailure(error:unknown){
 return error instanceof ReviewBundleError?json({error:error.message,reason:error.reason},error.status):
  json({error:'Read-only bundle metadata is unavailable',reason:'bundle_metadata_unavailable'},503);
}
function fail(status:number,reason:string,message:string):never{throw new ReviewBundleError(status,reason,message);}
function validSize(size:number){return Number.isSafeInteger(size)&&size>=4&&size<=MAX_REVIEW_BUNDLE;}
const missing=(reason:string)=>({available:false as const,reason});

// SELECT and R2 HEAD only. Do not call ensureConversation: review access cannot
// initialize/migrate database tables or change a task even on a legacy service.
export async function currentReviewDelivery(id:string){
 if(!uuid.test(id))fail(400,'invalid_task','Expected a task UUID');
 const db=database();
 const job=await db.prepare('SELECT id,status,result_key FROM jobs WHERE id=?').bind(id).first<Job>();
 if(!job)fail(404,'task_not_found','Request not found');
 const pptx=job.status==='complete'&&job.result_key?await files().head(job.result_key):null;
 const artifact=pptx?{available:true as const,bytes:pptx.size,etag:pptx.httpEtag}:missing(job.status==='complete'?'stored_file_missing':'not_completed');
 const base={job,pptx,artifact,bundle:null,bundleKey:null,deliveryVersion:null};
 if(job.status!=='complete'||!job.result_key)return {...base,bundleArtifact:missing('not_completed')};
 const version=await db.prepare('SELECT id,job_id,result_key,bundle_key,revision,created_at FROM task_versions WHERE job_id=? AND result_key=? ORDER BY created_at DESC,id DESC LIMIT 1').bind(id,job.result_key).first<Version>();
 if(!version?.bundle_key)return {...base,bundleArtifact:missing('not_delivered')};
 if(!uuid.test(version.id)||version.job_id!==id||version.result_key!==`results/${id}/${version.id}.pptx`||
    job.result_key!==version.result_key||version.bundle_key!==`bundles/${id}/${version.id}.zip`||
    !Number.isSafeInteger(version.revision)||version.revision<0||!Number.isSafeInteger(version.created_at)){
  fail(409,'inconsistent_delivery','Current PPTX and bundle version records do not match');
 }
 if(!pptx)fail(409,'paired_pptx_missing','The current bundle has no matching stored PPTX');
 const bundle=await files().head(version.bundle_key);
 if(!bundle)return {...base,bundleArtifact:missing('stored_file_missing')};
 if(!validSize(bundle.size))fail(413,'bundle_too_large','Bundle must contain 4 bytes to 250 MiB');
 // An opaque linkage value: storage keys, lease identifiers and worker secrets
 // are never exposed by this read-only interface.
 const identity=JSON.stringify([id,job.result_key,version.id,version.revision,version.created_at,
  pptx.httpEtag,pptx.size,bundle.httpEtag,bundle.size]);
 const deliveryVersion=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(identity))),byte=>byte.toString(16).padStart(2,'0')).join('');
 return {job,pptx,bundle,bundleKey:version.bundle_key,deliveryVersion,
  artifact:{available:true as const,bytes:pptx.size,etag:pptx.httpEtag,deliveryVersion},
  bundleArtifact:{available:true as const,bytes:bundle.size,etag:bundle.httpEtag,deliveryVersion}};
}

export async function stillCurrentReviewDelivery(id:string,expected:string){
 let current;
 try{current=await currentReviewDelivery(id);}catch{
  fail(412,'delivery_changed','Delivery changed; fetch request metadata again');
 }
 if(current.deliveryVersion!==expected)fail(412,'delivery_changed','Delivery changed; fetch request metadata again');
 return current;
}

export function requireDeliveryHeaders(request:Request){
 const version=request.headers.get(DELIVERY_HEADER),etag=request.headers.get('If-Match');
 if(!version||!etag)fail(428,'metadata_required','Fetch metadata with include=bundle before downloading the ZIP');
 if(!/^[a-f0-9]{64}$/.test(version)||etag.length>256)fail(400,'invalid_precondition','Invalid artifact precondition');
 return {version,etag};
}
