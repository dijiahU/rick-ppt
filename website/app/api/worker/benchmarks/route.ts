import {database,json,workerAuthorized} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';
import {INSERT_JOB} from '@/lib/queries';
import {resolvePages} from '@/lib/task-mode';

// Operational tests have their own identity and quota; never impersonate a visitor.
const OWNER='system:operator-benchmark';
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
async function find(requestKey:string){
 return database().prepare('SELECT id,title,brief,pages,style,language,status,execution_backend,created_at,updated_at,result_key FROM jobs WHERE user_id=? AND request_key=?').bind(OWNER,requestKey).first<Record<string,unknown>>();
}
function receipt(row:Record<string,unknown>){
 const {id,title,pages,status,execution_backend,created_at,updated_at}=row;
 return {id,title,pages,status,execution_backend,created_at,updated_at,result_available:!!row.result_key,benchmark:true};
}
export async function GET(request:Request){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);
 const key=new URL(request.url).searchParams.get('requestKey');
 if(!key||!UUID.test(key))return json({error:'Valid requestKey required'},400);
 const row=await find(key);return row?json(receipt(row)):json({error:'Benchmark not found'},404);
}
export async function POST(request:Request){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);
 let body;try{body=JSON.parse(new TextDecoder().decode(await boundedBody(request,4096)));}catch{return json({error:'Invalid benchmark request'},400);}
 if(!body||typeof body!=='object'||Array.isArray(body))return json({error:'Invalid benchmark request'},400);
 const {title,brief,requestKey}=body;
 if(typeof title!=='string'||!title.trim()||title.length>120||typeof brief!=='string'||brief.trim().length<10||brief.length>2000||typeof requestKey!=='string'||!UUID.test(requestKey))return json({error:'Invalid benchmark request'},400);
 const choice=resolvePages('create',body.pages,title+'\n'+brief);
 if(choice.pages===null||choice.pages===0)return json({error:'Invalid page count'},400);
 const pages=choice.pages,style='简洁专业',language='zh-CN';
 const matches=(row:Record<string,unknown>)=>row.title===title.trim()&&row.brief===brief.trim()&&row.pages===pages&&row.execution_backend==='codex';
 const prior=await find(requestKey);
 if(prior)return matches(prior)?json(receipt(prior)):json({error:'Request key belongs to a different benchmark'},409);
 const id=crypto.randomUUID(),now=Date.now();
 try{
  // Same atomic queue admission and ten-task quota as visitors, under OWNER.
  await database().prepare(INSERT_JOB).bind(id,OWNER,requestKey,title.trim(),brief.trim(),pages,style,language,'codex','[]',now,now,0,OWNER).first();
 }catch{
  const committed=await find(requestKey);
  return committed&&matches(committed)?json(receipt(committed),201):json({error:'Benchmark admission unavailable'},503);
 }
 const row=await find(requestKey);
 return row?matches(row)?json(receipt(row),row.id===id?201:200):json({error:'Request key belongs to a different benchmark'},409):json({error:'Benchmark quota or queue capacity reached'},429);
}
