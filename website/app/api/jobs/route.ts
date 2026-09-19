import {database,files,json,userId,sameOrigin} from '@/lib/server';
import {INSERT_JOB} from '@/lib/queries';
import {isAdmin} from '@/lib/admin';
import {isLocale,messages,type Messages} from '@/lib/i18n';
import {uploadMessages} from '@/lib/upload-i18n';
import {resolvePages,hasEditableDeck} from '@/lib/task-mode';
import {pageCountMessages} from '@/lib/page-count-i18n';
import {taskModeMessages} from '@/lib/task-mode-i18n';
import {boundedBody,MAX_TOTAL_BYTES,validFiles,validSignature,extension,attachmentKey,type Attachment} from '@/lib/attachments';
export async function POST(request:Request){
 const selected=request.headers.get('X-UI-Language'),locale=isLocale(selected)?selected:'en',t=messages[locale];
 const fail=(code:keyof Messages['errors']|'upload',status:number)=>json({error:code==='upload'?uploadMessages[locale].error:t.errors[code],code},status);
 const user=await userId();if(!user)return fail('auth',401);
 if(!sameOrigin(request))return fail('origin',403);
 const type=request.headers.get('content-type')??'';
 if(!type.startsWith('application/json')&&!type.startsWith('multipart/form-data'))return fail('format',415);
 let body;let uploads:File[]=[];
 try{
  if(type.startsWith('multipart/form-data')){
   const raw=await boundedBody(request,MAX_TOTAL_BYTES+128*1024);
   const form=await new Response(raw,{headers:{'Content-Type':type}}).formData();
   body={...Object.fromEntries(['title','brief','style','language','requestKey'].map(key=>[key,form.get(key)])),mode:form.get('mode')??undefined,pages:Number(form.get('pages'))};
   const entries=form.getAll('files');
   if(entries.some(x=>typeof x==='string'))return fail('upload',400);
   uploads=entries as File[];
  }else{
   const raw=await boundedBody(request,16000);body=JSON.parse(new TextDecoder().decode(raw));
  }
 }catch{return fail(type.startsWith('multipart/')?'upload':'invalid',400);}
 if(!body||typeof body!=='object'||Array.isArray(body))return fail('invalid',400);
 const {title,brief,style,requestKey}=body;
 const choice=resolvePages(body.mode,body.pages,typeof title==='string'&&typeof brief==='string'?title+'\n'+brief:'');
 const pages=choice.pages;
 const language=body.language===undefined?'en':body.language;
 if(typeof title!=='string'||!title.trim()||title.length>120||typeof brief!=='string'||brief.trim().length<10||brief.length>12000||typeof style!=='string'||style.length>80||!isLocale(language)||typeof requestKey!=='string'||!/^[a-f0-9-]{36}$/.test(requestKey))return fail('invalid',400);
 if(pages===null)return json({error:pageCountMessages[locale][choice.error??'pagesRange'],code:choice.error??'pagesRange'},400);
 if(!validFiles(uploads))return fail('upload',400);
 const db=database();const prior=await db.prepare('SELECT id FROM jobs WHERE user_id=? AND request_key=?').bind(user,requestKey).first();
 if(prior)return json(prior);
 if(pages===0&&!hasEditableDeck(uploads))return json({error:taskModeMessages[locale].missing,code:'source'},400);
 const count=await db.prepare('SELECT COUNT(*) AS n FROM jobs WHERE user_id=?').bind(user).first<{n:number}>();
 const unlimited=await isAdmin();
 if(!unlimited&&(count?.n??0)>=10)return fail('quota',429);
 const id=crypto.randomUUID(),now=Date.now(),metadata:Attachment[]=[],payloads:{meta:Attachment;data:Uint8Array}[]=[];
 for(const file of uploads){
  const data=new Uint8Array(await file.arrayBuffer()),ext=extension(file.name);
  if(!validSignature(ext,data))return fail('upload',400);
  const sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data))).map(b=>b.toString(16).padStart(2,'0')).join('');
  const name=file.name.replace(/[\\/\u0000-\u001f\u007f]/g,'_');
  const meta={id:crypto.randomUUID(),name,size:data.length,ext,sha256};metadata.push(meta);payloads.push({meta,data});
 }
 const stored:string[]=[];
 let admitted=false;
 try{
  for(const {meta,data} of payloads){const key=attachmentKey(id,meta.id);stored.push(key);await files().put(key,data,{httpMetadata:{contentType:'application/octet-stream'}});}
  const row=await db.prepare(INSERT_JOB).bind(id,user,requestKey,title.trim(),brief.trim(),pages,style,language,JSON.stringify(metadata),now,now,unlimited?1:0,user).first();
  if(row){admitted=true;return json(row,201);}
  const repeated=await db.prepare('SELECT id FROM jobs WHERE user_id=? AND request_key=?').bind(user,requestKey).first();
  if(repeated)return json(repeated);
  return fail('quota',429);
 }catch{
  // A lost DB response must not delete files from a successfully committed job.
  const committed=await db.prepare('SELECT id FROM jobs WHERE id=? AND user_id=?').bind(id,user).first();
  if(committed){admitted=true;return json(committed,201);}
  return json({error:t.submitError,code:'submit'},503);
 }finally{
  if(!admitted&&stored.length){
   // Verify non-admission before removing this attempt's own objects.
   // If DB is unreachable, retain them rather than break an accepted job.
   try{const exists=await db.prepare('SELECT id FROM jobs WHERE id=?').bind(id).first();if(!exists)await files().delete(stored);}catch{/* Retain for explicit scoped cleanup. */}
  }
 }
}
