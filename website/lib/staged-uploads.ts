import {files} from '@/lib/server';
import {MAX_FILES,parseAttachments,type Attachment} from '@/lib/attachments';

const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
export const STAGING_TTL=24*60*60*1000;
export function validUploadScope(scope:string){
 const parts=scope.split(':');
 return parts[0]==='job'&&parts.length===2&&uuid.test(parts[1])||parts[0]==='message'&&parts.length===3&&uuid.test(parts[1])&&uuid.test(parts[2]);
}
export async function stagedKey(user:string,scope:string,id:string){
 if(!validUploadScope(scope)||!uuid.test(id))throw Error('Invalid upload scope');
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(user));
 const owner=Array.from(new Uint8Array(digest)).map(v=>v.toString(16).padStart(2,'0')).join('');
 return `staged-attachments/${owner}/${scope}/${id}`;
}
export type StagedAttachment={meta:Attachment;key:string};
export async function resolveUploads(user:string,scope:string,ids:unknown):Promise<StagedAttachment[]>{
 if(ids===undefined)return [];
 if(!Array.isArray(ids)||ids.length>MAX_FILES||ids.some(id=>typeof id!=='string'||!uuid.test(id))||new Set(ids).size!==ids.length)throw Error('Invalid upload list');
 const result:StagedAttachment[]=[];
 for(const id of ids){
  const key=await stagedKey(user,scope,id),object=await files().head(key);
  const meta=parseAttachments(object?.customMetadata?.attachment)[0];
  const expires=Number(object?.customMetadata?.expires);
  if(!object||!meta||meta.id!==id||meta.size!==object.size||!Number.isFinite(expires)||expires<=Date.now())throw Error('Upload missing or expired');
  result.push({key,meta});
 }
 if(parseAttachments(result.map(x=>x.meta)).length!==result.length)throw Error('Upload limits exceeded');
 return result;
}
export async function copyUpload(upload:StagedAttachment,destination:string){
 const source=await files().get(upload.key);
 if(!source||source.size!==upload.meta.size)throw Error('Upload missing');
 // R2-to-R2 streaming keeps a 200 MB submission out of Worker memory.
 await files().put(destination,source.body,{httpMetadata:{contentType:'application/octet-stream'}});
}
