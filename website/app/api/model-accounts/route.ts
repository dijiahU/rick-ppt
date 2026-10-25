import {database,json,userId,sameOrigin} from '@/lib/server';
import {boundedBody} from '@/lib/attachments';
import {modelProviders,isModelProvider,type ModelProvider} from '@/lib/model-providers';
import {ensureModelAccounts,modelAccountsEnabled,sealKey} from '@/lib/model-accounts';
export const dynamic='force-dynamic';
export async function GET(){
 const user=await userId();if(!user)return json({error:'Sign in first'},401);
 await ensureModelAccounts();
 const rows=await database().prepare('SELECT id,provider,label,key_hint,models,created_at FROM model_accounts WHERE user_id=? AND revoked_at IS NULL ORDER BY created_at DESC').bind(user).all();
 return json({enabled:modelAccountsEnabled(),providers:Object.entries(modelProviders).map(([id,p])=>({id,label:p.label,models:p.models,webSearch:p.webSearch})),accounts:rows.results.map(r=>({id:r.id,provider:r.provider,label:r.label,keyHint:r.key_hint,models:JSON.parse(r.models as string),createdAt:r.created_at}))});
}
export async function POST(request:Request){
 const user=await userId();if(!user)return json({error:'Sign in first'},401);
 if(!sameOrigin(request))return json({error:'Invalid origin'},403);
 if(!modelAccountsEnabled())return json({error:'Model account storage is unavailable'},503);
 let b;try{b=JSON.parse(new TextDecoder().decode(await boundedBody(request,8192)));}catch{return json({error:'Invalid account'},400);}
 if(!b||typeof b!=='object'||Array.isArray(b)||Object.keys(b).some(k=>!['provider','apiKey','label','replaceId'].includes(k))||!isModelProvider(b.provider)||typeof b.apiKey!=='string'||!/^[\x21-\x7e]{12,1024}$/.test(b.apiKey)||typeof b.label!=='string'||!b.label.trim()||b.label.length>60||b.replaceId!==undefined&&typeof b.replaceId!=='string')return json({error:'Invalid account'},400);
 await ensureModelAccounts();const db=database();
 const n=await db.prepare('SELECT COUNT(*) AS n FROM model_accounts WHERE user_id=? AND revoked_at IS NULL').bind(user).first<{n:number}>();
 const replacing=b.replaceId?await db.prepare('SELECT id,created_at FROM model_accounts WHERE id=? AND user_id=? AND provider=? AND revoked_at IS NULL').bind(b.replaceId,user,b.provider).first<{id:string;created_at:number}>():null;
 if(b.replaceId&&!replacing)return json({error:'Account not found'},404);
 if(!replacing&&(n?.n??0)>=5)return json({error:'At most 5 model accounts can be connected'},409);
 const providerId=b.provider as ModelProvider,provider=modelProviders[providerId];let models:string[];
 try{
  // Access check only: no inference charges, no claim about remaining balance.
  const response=await fetch(provider.baseUrl+'/models',{headers:{Authorization:'Bearer '+b.apiKey},redirect:'error',signal:AbortSignal.timeout(15000)});
  if(!response.ok){await response.body?.cancel();return json({error:response.status===401||response.status===403?'API key was rejected':'Provider access check failed',code:'provider_access'},422);}
  const result=JSON.parse(new TextDecoder().decode(await boundedBody(response,1024*1024)));
  if(!Array.isArray(result.data))throw Error();
  const ids=new Set(result.data.map((m:{id?:unknown})=>m?.id));models=provider.models.filter(m=>ids.has(m));
  if(!models.length)return json({error:'No supported model is available to this key',code:'model_access'},422);
 }catch{return json({error:'Provider access check timed out or was unavailable',code:'provider_access'},502);}
 const id=replacing?.id??crypto.randomUUID(),now=replacing?.created_at??Date.now(),secret=await sealKey(b.apiKey,id,user,b.provider);
 if(replacing)await db.prepare('UPDATE model_accounts SET label=?,key_hint=?,secret=?,models=? WHERE id=? AND user_id=? AND provider=? AND revoked_at IS NULL').bind(b.label.trim(),'••••'+b.apiKey.slice(-4),secret,JSON.stringify(models),id,user,b.provider).run();
 else await db.prepare(`INSERT INTO model_accounts(id,user_id,provider,label,key_hint,secret,models,created_at) SELECT ?,?,?,?,?,?,?,? WHERE (SELECT COUNT(*) FROM model_accounts WHERE user_id=? AND revoked_at IS NULL)<5`).bind(id,user,b.provider,b.label.trim(),'••••'+b.apiKey.slice(-4),secret,JSON.stringify(models),now,user).run();
 const saved=await db.prepare('SELECT id FROM model_accounts WHERE id=? AND user_id=? AND revoked_at IS NULL').bind(id,user).first();
 if(!saved)return json({error:'Account limit reached'},409);
 return json({id,provider:b.provider,label:b.label.trim(),keyHint:'••••'+b.apiKey.slice(-4),models,createdAt:now},201);
}
