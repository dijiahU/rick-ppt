import {database,json,userId,sameOrigin} from '@/lib/server';
import {ensureModelAccounts} from '@/lib/model-accounts';
export async function DELETE(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'Sign in first'},401);
 if(!sameOrigin(request))return json({error:'Invalid origin'},403);
 const {id}=await params;await ensureModelAccounts();const db=database();
 // Revocation affects future lease fetches. An in-flight provider request cannot
 // be recalled; pausing active jobs stops subsequent workflow turns.
 const owned=await db.prepare('SELECT id FROM model_accounts WHERE id=? AND user_id=? AND revoked_at IS NULL').bind(id,user).first();
 if(!owned)return json({error:'Account not found'},404);
 await db.batch([
  db.prepare('UPDATE model_accounts SET secret=\'\',revoked_at=? WHERE id=? AND user_id=? AND revoked_at IS NULL').bind(Date.now(),id,user),
  db.prepare("UPDATE jobs SET status='paused',summary='model_account_disconnected',updated_at=? WHERE user_id=? AND status IN ('queued','running') AND id IN (SELECT job_id FROM task_funding WHERE credential_id=? AND user_id=?)").bind(Date.now(),user,id,user),
 ]);
 return json({ok:true});
}
