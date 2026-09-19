import { database,json,workerAuthorized } from '@/lib/server';
import { CLAIM_JOB } from '@/lib/queries';
import {taskScope,editInstruction} from '@/lib/task-mode';
export async function POST(request:Request) {
  if(!await workerAuthorized(request)) return json({error:'Unauthorized'},401);
  const db=database(),now=Date.now();
  await db.prepare('INSERT INTO worker(id,heartbeat) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat').bind('primary',now).run();
  // Fail stale tasks, never silently replay potentially executed user work.
  await db.prepare("UPDATE jobs SET status='failed',summary='interrupted',updated_at=? WHERE status='running' AND updated_at<?").bind(now,now-180000).run();
  const job=await db.prepare(CLAIM_JOB).bind(crypto.randomUUID(),now).first();
  return json({job:job?{...job,...taskScope(Number(job.pages)),...(job.pages===0?{brief:editInstruction+'\n\nUSER BRIEF:\n'+job.brief}:{} )}:null});
}
