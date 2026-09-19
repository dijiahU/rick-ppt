import {database,files,json} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';
export const traceKinds=['phase','command','tool','search','file','media','note','review','error'] as const;
export type TraceEvent={seq:number;at:number;stage:string;kind:typeof traceKinds[number];label:string;state:'started'|'completed'|'failed';command?:string;output?:string;detail?:string;itemId?:string;exitCode?:number;truncated?:boolean};
type Batch={version:1;chunk:number;events:TraceEvent[]};
type Index={chunks:number;events:number;updatedAt:number;finished?:boolean};
const LIMIT=1024*1024;
const prefix=(id:string,lease:string)=>`admin-traces/${id}/${lease}/`;
function scrub(value:string){return value.replace(/\b(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=:-]+/gi,'[authorization redacted]').replace(/\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{15,}|github_pat_[A-Za-z0-9_]{15,})/g,'[credential redacted]').replace(/(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret|authorization)\b["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;}]+)/gi,'$1[redacted]');}
export function parseTraceBatch(value:unknown):Batch|null{
 if(!value||typeof value!=='object')return null;
 const b=value as Batch;
 if(b.version!==1||!Number.isSafeInteger(b.chunk)||b.chunk<1||b.chunk>20001||!Array.isArray(b.events)||b.events.length<1||b.events.length>50)return null;
 const events:TraceEvent[]=[];let previous=0;
 for(const e of b.events){
  if(!e||!Number.isSafeInteger(e.seq)||e.seq<1||e.seq>20001||(previous&&e.seq!==previous+1)||!Number.isSafeInteger(e.at)||e.at<0||typeof e.stage!=='string'||!e.stage.length||e.stage.length>100||!traceKinds.includes(e.kind)||typeof e.label!=='string'||e.label.length>240||!['started','completed','failed'].includes(e.state))return null;
  const event:TraceEvent={seq:e.seq,at:e.at,stage:scrub(e.stage),kind:e.kind,label:scrub(e.label),state:e.state};
  for(const [key,max] of [['command',32000],['output',100000],['detail',16000],['itemId',100]] as const){if(e[key]!==undefined){if(typeof e[key]!=='string'||e[key]!.length>max)return null;event[key]=scrub(e[key]!);}}
  if(e.exitCode!==undefined){if(!Number.isSafeInteger(e.exitCode))return null;event.exitCode=e.exitCode;}
  if(e.truncated===true)event.truncated=true;
  previous=e.seq;events.push(event);
 }
 return {version:1,chunk:b.chunk,events};
}
export async function storeTrace(request:Request,id:string,lease:string){
 let batch:Batch|null;
 try{batch=parseTraceBatch(JSON.parse(new TextDecoder().decode(await boundedBody(request,LIMIT))));}catch{return json({error:'Invalid execution record'},400);}
 if(!batch)return json({error:'Invalid execution record'},400);
 const credential=request.headers.get('Authorization')?.replace(/^Bearer /,'');
 const base=prefix(id,lease),key=base+String(batch.chunk).padStart(5,'0')+'.json';
 const body=credential?JSON.stringify(batch).replaceAll(credential,'[redacted]'):JSON.stringify(batch);
 const [current,existing]=await Promise.all([files().get(base+'index.json'),files().get(key)]);
 const index:Index=current?await current.json():{chunks:0,events:0,updatedAt:0};
 if(existing&&await existing.text()!==body)return json({error:'Execution record conflict'},409);
 if(batch.chunk<=index.chunks)return existing?json({ok:true}):json({error:'Execution record unavailable'},409);
 if(batch.chunk!==index.chunks+1||batch.events[0].seq!==index.events+1)return json({error:'Execution record sequence mismatch'},409);
 // Job/lease authorization happens in the worker route before any storage read.
 if(!existing)await files().put(key,body,{httpMetadata:{contentType:'application/json'}});
 const next:Index={chunks:batch.chunk,events:batch.events.at(-1)!.seq,updatedAt:Date.now(),finished:index.finished||batch.events.some(e=>e.stage==='finished')};
 await files().put(base+'index.json',JSON.stringify(next),{httpMetadata:{contentType:'application/json'}});
 return json({ok:true});
}
export async function readTrace(request:Request,id:string){
 const raw=new URL(request.url).searchParams.get('after')??'0';
 if(!/^\d{1,5}$/.test(raw)||Number(raw)>20001)return json({error:'Invalid record cursor'},400);
 const after=Number(raw);
 const job=await database().prepare('SELECT lease,status FROM jobs WHERE id=?').bind(id).first<{lease:string|null;status:string}>();
 if(!job)return json({error:'Task not found'},404);
 if(!job.lease)return json({available:false,events:[],nextChunk:0,totalEvents:0,totalChunks:0,status:job.status,attempt:null});
 const base=prefix(id,job.lease),object=await files().get(base+'index.json');
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(job.lease));
 const attempt=Array.from(new Uint8Array(digest)).map(n=>n.toString(16).padStart(2,'0')).join('').slice(0,16);
 if(!object)return json({available:false,events:[],nextChunk:0,totalEvents:0,totalChunks:0,status:job.status,attempt});
 const index=await object.json<Index>(),start=after>index.chunks?0:after,end=Math.min(start+5,index.chunks);
 const events:TraceEvent[]=[];
 for(let chunk=start+1;chunk<=end;chunk++){
  const data=await files().get(base+String(chunk).padStart(5,'0')+'.json');
  if(!data)return json({error:'Execution record temporarily unavailable'},503);
  const batch=parseTraceBatch(await data.json());
  if(!batch)return json({error:'Invalid stored execution record'},503);
  events.push(...batch.events);
 }
 return json({available:true,events,nextChunk:end,totalEvents:index.events,totalChunks:index.chunks,updatedAt:index.updatedAt,finished:!!index.finished,status:job.status,attempt});
}
