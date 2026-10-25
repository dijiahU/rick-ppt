import { database,json,userId,workerStatus } from '@/lib/server';
import {parseAttachments} from '@/lib/attachments';
import {isAdmin} from '@/lib/admin';
import {publicJobStatus} from '@/lib/job-status';
import {ensureModelAccounts} from '@/lib/model-accounts';
export const dynamic='force-dynamic';
export async function GET() {
  const id=await userId(); if(!id) return json({signedIn:false});
  const records=await database().prepare('SELECT id,title,status,created_at,summary,result_key,language,execution_backend,attachments FROM jobs WHERE user_id=? ORDER BY created_at DESC').bind(id).all();
  await ensureModelAccounts();
  const bindings=await database().prepare('SELECT job_id,provider,model FROM task_funding WHERE user_id=?').bind(id).all();
  const funding=new Map(bindings.results.map(r=>[r.job_id,{provider:r.provider,model:r.model}]));
  const admin=await isAdmin();
  return json({signedIn:true,admin,unlimited:admin,remaining:admin?null:Math.max(0,10-records.results.length),...await workerStatus(),jobs:records.results.map(({result_key,attachments,...row})=>({...row,...(funding.has(row.id)?{modelAccount:funding.get(row.id)}:{}),status:publicJobStatus(row.status,row.summary),attachments:parseAttachments(attachments),download:row.status==='complete'&&!!result_key}))});
}
