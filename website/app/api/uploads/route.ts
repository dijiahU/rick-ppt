import {database,files,json,sameOrigin,userId} from '@/lib/server';
import {boundedBody,extension,MAX_FILE_BYTES,validFiles,validSignature} from '@/lib/attachments';
import {stagedKey,STAGING_TTL,validUploadScope} from '@/lib/staged-uploads';
import {isLocale} from '@/lib/i18n';
import {uploadMessages} from '@/lib/upload-i18n';

export async function POST(request:Request){
 const selected=request.headers.get('X-UI-Language'),locale=isLocale(selected)?selected:'en';
 const fail=(status=400)=>json({code:'upload',error:uploadMessages[locale].error},status);
 const user=await userId();if(!user)return json({error:'Sign in required'},401);
 if(!sameOrigin(request))return json({error:'Invalid origin'},403);
 const query=new URL(request.url).searchParams,scope=query.get('scope')??'',name=query.get('name')??'';
 if(!validUploadScope(scope)||!validFiles([{name,size:1}]))return fail();
 if(scope.startsWith('message:')){
  const job=scope.split(':')[1];
  if(!await database().prepare('SELECT id FROM jobs WHERE id=? AND user_id=?').bind(job,user).first())return json({error:'Task not found'},404);
 }
 let data:Uint8Array<ArrayBuffer>;
 try{data=await boundedBody(request,MAX_FILE_BYTES);}catch{return fail();}
 const ext=extension(name);
 if(!validFiles([{name,size:data.length}])||!validSignature(ext,data))return fail();
 const hash=await crypto.subtle.digest('SHA-256',data);
 const sha256=Array.from(new Uint8Array(hash)).map(v=>v.toString(16).padStart(2,'0')).join('');
 const meta={id:crypto.randomUUID(),name:name.replace(/[\\/\u0000-\u001f\u007f]/g,'_'),size:data.length,ext,sha256};
 try{
  await files().put(await stagedKey(user,scope,meta.id),data,{httpMetadata:{contentType:'application/octet-stream'},customMetadata:{attachment:JSON.stringify([meta]),expires:String(Date.now()+STAGING_TTL)}});
  return json({id:meta.id},201);
 }catch{return fail(503);}
}

export async function DELETE(request:Request){
 const user=await userId();if(!user)return json({error:'Sign in required'},401);
 if(!sameOrigin(request))return json({error:'Invalid origin'},403);
 const scope=new URL(request.url).searchParams.get('scope')??'';
 if(!validUploadScope(scope))return json({error:'Invalid scope'},400);
 try{
  const {ids}=JSON.parse(new TextDecoder().decode(await boundedBody(request,4096)));
  if(!Array.isArray(ids)||ids.length>10)return json({error:'Invalid uploads'},400);
  const keys=await Promise.all(ids.map(id=>stagedKey(user,scope,id)));
  if(keys.length)await files().delete(keys);
  return json({ok:true});
 }catch{return json({error:'Could not remove temporary uploads'},400);}
}
