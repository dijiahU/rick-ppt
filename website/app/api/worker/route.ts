import { database,json,workerIdentity } from '@/lib/server';
import {deferToLocal,workerRow} from '@/lib/worker-routing';
import { CLAIM_ACCOUNT_JOB } from '@/lib/queries';
import {ensureModelAccounts} from '@/lib/model-accounts';
import {taskScope,editInstruction} from '@/lib/task-mode';
import {boundedBody} from '@/lib/attachments';
import {workerCapabilities} from '@/lib/execution-backend';
export async function POST(request:Request) {
  const identity=await workerIdentity(request);
  if(!identity) return json({error:'Unauthorized'},401);
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
  await db.prepare('INSERT INTO worker(id,heartbeat,execution_backends) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat,execution_backends=excluded.execution_backends').bind(workerRow(identity),now,capabilities.advertised?JSON.stringify(capabilities.backends):null).run();
  // An idle or dependency-blocked process is still reachable. This operation
  // never leases/reaps jobs, changes quota or requires a task lease.
  if(action==='heartbeat')return json({ok:true,ready:capabilities.backends.length>0});
  // Local-first: the server takes new work only while the local worker is offline.
  if(identity==='server'){
    const local=await db.prepare('SELECT heartbeat FROM worker WHERE id=?').bind(workerRow('local')).first<{heartbeat:number}>();
    if(deferToLocal(identity,local?.heartbeat,now))return json({job:null,deferred:'local_worker_online'});
  }
  // Fail stale tasks, never silently replay potentially executed user work.
  if(process.env.NODE_ENV!=='production'){
    // Local diagnostics: record what the stale-task sweep is about to fail and why.
    const stale=await db.prepare("SELECT id,updated_at FROM jobs WHERE status='running' AND updated_at<?").bind(now-180000).all<{id:string;updated_at:number}>();
    for(const row of stale.results??[])console.warn('[stale-sweep]',row.id,'updated_at',row.updated_at,typeof row.updated_at,'now',now,'age_ms',now-Number(row.updated_at),'worker',identity);
  }
  await db.prepare("UPDATE jobs SET status='failed',summary=CASE WHEN summary='delivery_pending' THEN summary ELSE 'interrupted' END,updated_at=? WHERE status='running' AND updated_at<?").bind(now,now-180000).run();
  await ensureModelAccounts();
  const job=await db.prepare(CLAIM_ACCOUNT_JOB).bind(crypto.randomUUID(),now,capabilities.backends.includes('api')?1:0,capabilities.backends.includes('codex')?1:0,body.funding_version===1&&capabilities.backends.length>0?1:0).first();
  const funded=job?await db.prepare('SELECT job_id FROM task_funding WHERE job_id=?').bind(job.id).first():null;
  const options=job?await db.prepare('SELECT service_tier FROM task_options WHERE job_id=?').bind(job.id).first<{service_tier:string}>():null;
  // Absent unless the submitter chose Fast; older workers ignore the extra field.
  return json({job:job?{...job,...(funded?{funding_mode:'user_api'}:{}),...(options?.service_tier==='fast'?{service_tier:'fast'}:{}),...taskScope(Number(job.pages)),...(job.pages===0?{brief:editInstruction+'\n\nUSER BRIEF:\n'+job.brief}:{} )}:null});
}
