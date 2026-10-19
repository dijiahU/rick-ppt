import {database,json} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';

const tokenFields=['inputTokens','outputTokens','cachedInputTokens','cacheWriteTokens','reasoningTokens','totalTokens'] as const;
type TokenField=typeof tokenFields[number];
export type UsageRecord=Record<TokenField,number|null>&{
 id:string;attempt:string;stage:string;source:'api'|'codex';provider:string;model:string;
 protocol:'responses'|'chat_completions'|'codex';usageStatus:'reported'|'unavailable';
 at:number;version:number;serviceTier:string;outcome:string;responseId?:string|null;requestId?:string|null;
 costMicrousd:number|null;costSource:'configured_rate'|'unpriced'|'not_api';priceVersion:string|null;
 priceSnapshot:Record<string,string>|null;
 rawUsage?:Record<string,unknown>|null;
};
const marker=(v:unknown,max=200):v is string=>typeof v==='string'&&new RegExp(`^[A-Za-z0-9_.:/-]{1,${max}}$`).test(v);
const integer=(v:unknown,max=10**12):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0&&v<=max;
const rateFields=['inputUsdPerMillion','cachedInputUsdPerMillion','cacheWriteUsdPerMillion','outputUsdPerMillion'];
function rawUsage(value:unknown):Record<string,unknown>|null{
 if(!value||typeof value!=='object'||Array.isArray(value))return null;
 const input=value as Record<string,unknown>,result:Record<string,unknown>={};
 for(const k of ['input_tokens','output_tokens','prompt_tokens','completion_tokens','total_tokens','cache_read_input_tokens','cache_creation_input_tokens'])if(integer(input[k]))result[k]=input[k];
 for(const k of ['input_tokens_details','output_tokens_details','prompt_tokens_details','completion_tokens_details']){
  const nested=input[k];if(nested&&typeof nested==='object'&&!Array.isArray(nested)){
   result[k]=Object.fromEntries(['cached_tokens','cache_write_tokens','reasoning_tokens','audio_tokens','accepted_prediction_tokens','rejected_prediction_tokens'].filter(n=>integer((nested as Record<string,unknown>)[n])).map(n=>[n,(nested as Record<string,unknown>)[n]]));
  }
 }
 return Object.keys(result).length?result:null;
}

export function parseUsageBatch(value:unknown):UsageRecord[]|null{
 if(!value||typeof value!=='object')return null;
 const batch=value as {version:unknown;records:unknown};
 if(batch.version!==1||!Array.isArray(batch.records)||batch.records.length<1||batch.records.length>25)return null;
 const records:UsageRecord[]=[],seen=new Set<string>();
 for(const raw of batch.records){
  if(!raw||typeof raw!=='object'||Array.isArray(raw))return null;
  const r=raw as UsageRecord;
  if(!/^[a-f0-9]{64}$/.test(r.id)||seen.has(r.id)||!/^[a-f0-9]{16}$/.test(r.attempt)||!marker(r.stage,100)||!marker(r.provider,253)||!marker(r.model)||!integer(r.at,10**15)||!integer(r.version)||r.version<1)return null;
  if(!['api','codex'].includes(r.source)||!['responses','chat_completions','codex'].includes(r.protocol)||(r.source==='codex')!==(r.protocol==='codex')||!['reported','unavailable'].includes(r.usageStatus)||!['default','priority','auto','fast'].includes(r.serviceTier)||!['completed','failed','incomplete','interrupted','unknown'].includes(r.outcome))return null;
  const row:UsageRecord={id:r.id,attempt:r.attempt,stage:r.stage,source:r.source,provider:r.provider,model:r.model,protocol:r.protocol,usageStatus:r.usageStatus,at:r.at,version:r.version,serviceTier:r.serviceTier,outcome:r.outcome,costMicrousd:r.costMicrousd,costSource:r.costSource,priceVersion:r.priceVersion,priceSnapshot:null,...Object.fromEntries(tokenFields.map(k=>[k,r[k]]))} as UsageRecord;
  for(const k of tokenFields)if(r.usageStatus==='reported'?!integer(r[k]):r[k]!==null)return null;
  if(r.usageStatus==='reported'&&(r.totalTokens!==r.inputTokens!+r.outputTokens!||r.cachedInputTokens!+r.cacheWriteTokens!>r.inputTokens!||r.reasoningTokens!>r.outputTokens!))return null;
  for(const k of ['responseId','requestId'] as const){if(r[k]!=null&&!marker(r[k]))return null;row[k]=r[k]??null;}
  if(r.source==='codex'){
   if(r.costSource!=='not_api'||r.costMicrousd!==null||r.priceVersion!==null||r.priceSnapshot!==null)return null;
  }else if(r.costSource==='configured_rate'){
   if(r.usageStatus!=='reported'||!integer(r.costMicrousd,10**15)||!marker(r.priceVersion)||!r.priceSnapshot||typeof r.priceSnapshot!=='object')return null;
   if(rateFields.some(k=>typeof r.priceSnapshot![k]!=='string'||!/^\d{1,7}(?:\.\d{1,12})?$/.test(r.priceSnapshot![k])))return null;
   row.priceSnapshot=Object.fromEntries(rateFields.map(k=>[k,r.priceSnapshot![k]]));
  }else if(r.costSource!=='unpriced'||r.costMicrousd!==null||r.priceVersion!==null||r.priceSnapshot!==null)return null;
  row.rawUsage=rawUsage(r.rawUsage);
  seen.add(r.id);records.push(row);
 }
 return records;
}

export async function ensureUsage(){
 const db=database();await db.batch([
  db.prepare('CREATE TABLE IF NOT EXISTS task_usage (job_id TEXT NOT NULL,event_id TEXT NOT NULL,version INTEGER NOT NULL,source TEXT NOT NULL,model TEXT NOT NULL,provider TEXT NOT NULL,stage TEXT NOT NULL,usage_status TEXT NOT NULL,input_tokens INTEGER,output_tokens INTEGER,cached_input_tokens INTEGER,cache_write_tokens INTEGER,reasoning_tokens INTEGER,total_tokens INTEGER,cost_microusd INTEGER,payload TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,PRIMARY KEY(job_id,event_id))'),
  db.prepare('CREATE INDEX IF NOT EXISTS task_usage_job_created ON task_usage(job_id,created_at,event_id)'),
 ]);
}

export async function storeUsage(request:Request,id:string,lease:string){
 let records:UsageRecord[]|null;
 try{records=parseUsageBatch(JSON.parse(new TextDecoder().decode(await boundedBody(request,128*1024))));}catch{return json({error:'Invalid usage receipts'},400);}
 if(!records)return json({error:'Invalid usage receipts'},400);
 const secret=request.headers.get('Authorization')?.replace(/^Bearer /,'');
 if(records.some(r=>[secret,lease].some(s=>s&&JSON.stringify(r).includes(s))))return json({error:'Protected value in usage receipt'},400);
 await ensureUsage();const db=database(),now=Date.now();
 // Preflight catches mismatched replays. Receipt identifiers survive task resume;
 // a new lease does not discard costs of earlier attempts.
 for(const r of records){
  const old=await db.prepare('SELECT version,payload FROM task_usage WHERE job_id=? AND event_id=?').bind(id,r.id).first<{version:number;payload:string}>();
  if(old&&old.version===r.version&&old.payload!==JSON.stringify(r))return json({error:'Usage receipt conflict'},409);
  if(old&&old.version<r.version){
   const p=JSON.parse(old.payload) as UsageRecord;
   if(p.source==='api'||p.source!==r.source||p.model!==r.model||p.provider!==r.provider||p.stage!==r.stage||p.at!==r.at||p.attempt!==r.attempt||tokenFields.some(k=>p[k]!==null&&(r[k]===null||r[k]!<p[k]!)))return json({error:'Usage receipt cannot decrease or change identity'},409);
  }
 }
 await db.batch(records.map(r=>db.prepare(`INSERT INTO task_usage(job_id,event_id,version,source,model,provider,stage,usage_status,input_tokens,output_tokens,cached_input_tokens,cache_write_tokens,reasoning_tokens,total_tokens,cost_microusd,payload,created_at,updated_at)
 SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE id=? AND lease=?)
 ON CONFLICT(job_id,event_id) DO UPDATE SET version=excluded.version,usage_status=excluded.usage_status,input_tokens=excluded.input_tokens,output_tokens=excluded.output_tokens,cached_input_tokens=excluded.cached_input_tokens,cache_write_tokens=excluded.cache_write_tokens,reasoning_tokens=excluded.reasoning_tokens,total_tokens=excluded.total_tokens,cost_microusd=excluded.cost_microusd,payload=excluded.payload,updated_at=excluded.updated_at
 WHERE task_usage.version<excluded.version AND task_usage.source='codex' AND excluded.source='codex' AND task_usage.model=excluded.model AND task_usage.provider=excluded.provider AND task_usage.stage=excluded.stage AND task_usage.created_at=excluded.created_at
 AND json_extract(task_usage.payload,'$.attempt')=json_extract(excluded.payload,'$.attempt')
 AND (task_usage.input_tokens IS NULL OR excluded.input_tokens>=task_usage.input_tokens)
 AND (task_usage.output_tokens IS NULL OR excluded.output_tokens>=task_usage.output_tokens)
 AND (task_usage.cached_input_tokens IS NULL OR excluded.cached_input_tokens>=task_usage.cached_input_tokens)
 AND (task_usage.cache_write_tokens IS NULL OR excluded.cache_write_tokens>=task_usage.cache_write_tokens)
 AND (task_usage.reasoning_tokens IS NULL OR excluded.reasoning_tokens>=task_usage.reasoning_tokens)`)
 .bind(id,r.id,r.version,r.source,r.model,r.provider,r.stage,r.usageStatus,r.inputTokens,r.outputTokens,r.cachedInputTokens,r.cacheWriteTokens,r.reasoningTokens,r.totalTokens,r.costMicrousd,JSON.stringify(r),r.at,now,id,lease)));
 const current=await db.prepare('SELECT id FROM jobs WHERE id=? AND lease=?').bind(id,lease).first();
 if(!current)return json({error:'Lease expired'},409);
 for(const r of records){
  const saved=await db.prepare('SELECT version,payload FROM task_usage WHERE job_id=? AND event_id=?').bind(id,r.id).first<{version:number;payload:string}>();
  if(!saved||saved.version<r.version||(saved.version===r.version&&saved.payload!==JSON.stringify(r)))return json({error:'Usage receipt conflict'},409);
 }
 return json({ok:true,records:records.length});
}

export async function readUsage(id:string,after=0){
 await ensureUsage();const db=database();
 const [groups,rows,total]=await Promise.all([
  db.prepare(`SELECT source,provider,model,stage,COUNT(*) AS calls,SUM(CASE WHEN usage_status='reported' THEN 1 ELSE 0 END) AS reportedCalls,SUM(CASE WHEN source='api' AND cost_microusd IS NULL THEN 1 ELSE 0 END) AS unpricedCalls,SUM(input_tokens) AS inputTokens,SUM(cached_input_tokens) AS cachedInputTokens,SUM(cache_write_tokens) AS cacheWriteTokens,SUM(output_tokens) AS outputTokens,SUM(reasoning_tokens) AS reasoningTokens,SUM(total_tokens) AS totalTokens,SUM(cost_microusd) AS costMicrousd FROM task_usage WHERE job_id=? GROUP BY source,provider,model,stage ORDER BY source,model,stage`).bind(id).all(),
  db.prepare('SELECT payload FROM task_usage WHERE job_id=? ORDER BY created_at,event_id LIMIT 100 OFFSET ?').bind(id,after).all<{payload:string}>(),
  db.prepare('SELECT COUNT(*) AS n FROM task_usage WHERE job_id=?').bind(id).first<{n:number}>(),
 ]);
 return {available:!!total?.n,groups:groups.results,records:rows.results.map(r=>JSON.parse(r.payload) as UsageRecord),total:total?.n??0,nextOffset:after+rows.results.length,costScope:'model_tokens',chargingEnabled:false};
}
