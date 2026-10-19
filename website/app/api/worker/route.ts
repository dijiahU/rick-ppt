import { database,json,workerAuthorized } from '@/lib/server';
import { CLAIM_JOB } from '@/lib/queries';
import {taskScope,editInstruction} from '@/lib/task-mode';
import {boundedBody} from '@/lib/attachments';
import {workerCapabilities} from '@/lib/execution-backend';
export async function POST(request:Request) {
  if(!await workerAuthorized(request)) return json({error:'Unauthorized'},401);
  let body;
  try {const bytes=await boundedBody(request,2048);body=bytes.length?JSON.parse(new TextDecoder().decode(bytes)):{};}
  catch {return json({error:'Invalid worker capabilities'},400);}
  if(!body||typeof body!=='object'||Array.isArray(body))return json({error:'Invalid worker capabilities'},400);
  const capabilities=workerCapabilities(body.execution_backends);
  if(!capabilities)return json({error:'Invalid worker capabilities'},400);
  const db=database(),now=Date.now();
  await db.prepare('INSERT INTO worker(id,heartbeat,execution_backends) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat,execution_backends=excluded.execution_backends').bind('primary',now,capabilities.advertised?JSON.stringify(capabilities.backends):null).run();
  // Fail stale tasks, never silently replay potentially executed user work.
  await db.prepare("UPDATE jobs SET status='failed',summary=CASE WHEN summary='delivery_pending' THEN summary ELSE 'interrupted' END,updated_at=? WHERE status='running' AND updated_at<?").bind(now,now-180000).run();
  const job=await db.prepare(CLAIM_JOB).bind(crypto.randomUUID(),now,capabilities.backends.includes('api')?1:0,capabilities.backends.includes('codex')?1:0).first();
  return json({job:job?{...job,...taskScope(Number(job.pages)),...(job.pages===0?{brief:editInstruction+'\n\nUSER BRIEF:\n'+job.brief}:{} )}:null});
}
