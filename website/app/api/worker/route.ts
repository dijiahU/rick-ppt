import { database,json,workerAuthorized } from '@/lib/server';
import { CLAIM_ACCOUNT_JOB } from '@/lib/queries';
import {ensureModelAccounts} from '@/lib/model-accounts';
import {taskScope,editInstruction} from '@/lib/task-mode';
import {boundedBody} from '@/lib/attachments';
import {workerCapabilities} from '@/lib/execution-backend';
export async function POST(request:Request) {
  if(!await workerAuthorized(request)) return json({error:'Unauthorized'},401);
  const action=new URL(request.url).searchParams.get('action')??'claim';
  if(action!=='claim'&&action!=='heartbeat')return json({error:'Invalid worker action'},400);
  let body;
  try {const bytes=await boundedBody(request,2048);body=bytes.length?JSON.parse(new TextDecoder().decode(bytes)):{};}
  catch {return json({error:'Invalid worker capabilities'},400);}
  if(!body||typeof body!=='object'||Array.isArray(body))return json({error:'Invalid worker capabilities'},400);
  const capabilities=workerCapabilities(body.execution_backends);
  if(!capabilities)return json({error:'Invalid worker capabilities'},400);
  if(body.funding_version!==undefined&&body.funding_version!==1)return json({error:'Invalid funding capability'},400);
  const db=database(),now=Date.now();
  await db.prepare('INSERT INTO worker(id,heartbeat,execution_backends) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat,execution_backends=excluded.execution_backends').bind('primary',now,capabilities.advertised?JSON.stringify(capabilities.backends):null).run();
  // An idle or dependency-blocked process is still reachable. This operation
  // never leases/reaps jobs, changes quota or requires a task lease.
  if(action==='heartbeat')return json({ok:true,ready:capabilities.backends.length>0});
  // Fail stale tasks, never silently replay potentially executed user work.
  await db.prepare("UPDATE jobs SET status='failed',summary=CASE WHEN summary='delivery_pending' THEN summary ELSE 'interrupted' END,updated_at=? WHERE status='running' AND updated_at<?").bind(now,now-180000).run();
  await ensureModelAccounts();
  const job=await db.prepare(CLAIM_ACCOUNT_JOB).bind(crypto.randomUUID(),now,capabilities.backends.includes('api')?1:0,capabilities.backends.includes('codex')?1:0,body.funding_version===1&&capabilities.backends.length>0?1:0).first();
  const funded=job?await db.prepare('SELECT job_id FROM task_funding WHERE job_id=?').bind(job.id).first():null;
  return json({job:job?{...job,...(funded?{funding_mode:'user_api'}:{}),...taskScope(Number(job.pages)),...(job.pages===0?{brief:editInstruction+'\n\nUSER BRIEF:\n'+job.brief}:{} )}:null});
}
