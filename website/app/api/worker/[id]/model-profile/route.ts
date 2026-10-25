import {database,json,workerAuthorized} from '@/lib/server';
import {ensureModelAccounts,openKey,modelAccountsEnabled} from '@/lib/model-accounts';
import {modelProviders,isModelProvider,allowedModel} from '@/lib/model-providers';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);
 const {id}=await params,lease=request.headers.get('X-Job-Lease');
 if(!lease)return json({error:'Lease required'},400);
 await ensureModelAccounts();const db=database();
 const job=await db.prepare("SELECT id,user_id,execution_backend FROM jobs WHERE id=? AND lease=? AND status='running'").bind(id,lease).first();
 if(!job)return json({error:'Lease expired'},409);
 const binding=await db.prepare('SELECT user_id,credential_id,provider,model,version FROM task_funding WHERE job_id=?').bind(id).first();
 if(!binding)return json({funding:null});
 if(!modelAccountsEnabled())return json({error:'Customer credential storage unavailable'},503);
 if(job.execution_backend!=='api'||binding.user_id!==job.user_id||binding.version!==1||!isModelProvider(binding.provider)||!allowedModel(binding.provider,binding.model))return json({error:'Invalid task funding binding'},409);
 const account=await db.prepare('SELECT secret FROM model_accounts WHERE id=? AND user_id=? AND provider=? AND revoked_at IS NULL').bind(binding.credential_id,job.user_id,binding.provider).first<{secret:string}>();
 if(!account)return json({error:'Customer model account was disconnected',code:'model_account_disconnected'},409);
 try{
  const apiKey=await openKey(account.secret,String(binding.credential_id),String(job.user_id),String(binding.provider));
  return json({funding:{version:1,credentialId:binding.credential_id,provider:binding.provider,model:binding.model},apiKey});
 }catch{return json({error:'Customer credential could not be decrypted'},503);}
}
