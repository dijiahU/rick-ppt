import {database,files,json,workerAuthorized} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);
 const {id}=await params,q=new URL(request.url).searchParams,lease=request.headers.get('X-Job-Lease');
 const sha=q.get('sha256')??'',pages=Number(q.get('pages')),revision=Number(q.get('revision')),exportedAt=Number(q.get('exportedAt'));
 const expected=Number(q.get('expectedUpdatedAt')),backfill=!lease&&Number.isSafeInteger(expected)&&expected>0;
 if(!/^[0-9a-f]{64}$/.test(sha)||!Number.isSafeInteger(pages)||pages<1||pages>200||!Number.isSafeInteger(revision)||revision<0||!Number.isSafeInteger(exportedAt)||exportedAt<=0||exportedAt>Date.now()+60000)return json({error:'Invalid draft metadata'},400);
 if(!lease&&!backfill)return json({error:'Lease or exact failed-attempt timestamp required'},400);
 const db=database();
 const guard=backfill?"id=? AND status='failed' AND updated_at=?":"id=? AND lease=? AND status='running'";
 const args=[id,backfill?expected:lease];
 if(!await db.prepare('SELECT id FROM jobs WHERE '+guard).bind(...args).first())return json({error:'Task attempt changed'},409);
 let bytes:Uint8Array;try{bytes=await boundedBody(request,30*1024*1024);}catch{return json({error:'Draft exceeds 30 MiB'},413);}
 if(bytes.length<22||bytes[0]!==80||bytes[1]!==75||bytes[2]!==3||bytes[3]!==4)return json({error:'PPTX required'},400);
 const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new Uint8Array(bytes).buffer))).map(v=>v.toString(16).padStart(2,'0')).join('');
 if(actual!==sha)return json({error:'Draft checksum mismatch'},400);
 const key=`drafts/${id}/${sha}.pptx`;
 await files().put(key,bytes,{httpMetadata:{contentType:'application/vnd.openxmlformats-officedocument.presentationml.presentation'}});
 const savedAt=Date.now();
 const result=await db.prepare(`INSERT INTO task_drafts(job_id,object_key,sha256,bytes,pages,revision,exported_at,saved_at)
 SELECT ?,?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE ${guard})
 ON CONFLICT(job_id) DO UPDATE SET object_key=excluded.object_key,sha256=excluded.sha256,bytes=excluded.bytes,pages=excluded.pages,revision=excluded.revision,exported_at=excluded.exported_at,saved_at=excluded.saved_at
 WHERE excluded.revision>task_drafts.revision OR (excluded.revision=task_drafts.revision AND excluded.exported_at>task_drafts.exported_at)`)
 .bind(id,key,sha,bytes.length,pages,revision,exportedAt,savedAt,...args).run();
 if(!result.meta.changes&&!await db.prepare('SELECT id FROM jobs WHERE '+guard).bind(...args).first())return json({error:'Task attempt changed'},409);
 return json({ok:true,stored:!!result.meta.changes});
}
