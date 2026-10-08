import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '@/app/chatgpt-auth';
import {normalizeAdminEmail} from '@/lib/admin-accounts';
import {adminGate} from '@/lib/admin';
import {adminAllowed} from '@/lib/admin-policy';
import {database,json,sameOrigin} from '@/lib/server';

export const dynamic='force-dynamic';

export async function GET(){
  const denied=await adminGate();if(denied)return denied;
  const current=await getChatGPTUser();
  const rows=await database().prepare('SELECT email,user_id,display_name,created_at,created_by FROM site_admins ORDER BY created_at ASC').all();
  return json({primary:current&&adminAllowed(current,env)?{email:current.email,displayName:current.displayName}:null,admins:rows.results});
}

export async function POST(request:Request){
  const denied=await adminGate();if(denied)return denied;
  if(!sameOrigin(request))return json({error:'Invalid origin.'},403);
  const current=await getChatGPTUser();if(!current)return json({error:'Sign in to continue.'},401);
  let body:unknown;try{body=await request.json();}catch{return json({error:'Invalid request.'},400);}
  const email=normalizeAdminEmail((body as {email?:unknown})?.email);
  if(!email)return json({error:'Enter a valid email address.'},400);
  if(adminAllowed({userId:'',email},env))return json({error:'This is already the primary administrator.'},409);
  await database().prepare('INSERT OR IGNORE INTO site_admins(email,user_id,display_name,created_at,created_by) VALUES(?,NULL,NULL,?,?)').bind(email,Date.now(),current.userId).run();
  return json({ok:true,email},201);
}

export async function DELETE(request:Request){
  const denied=await adminGate();if(denied)return denied;
  if(!sameOrigin(request))return json({error:'Invalid origin.'},403);
  const email=normalizeAdminEmail(new URL(request.url).searchParams.get('email'));
  if(!email)return json({error:'Enter a valid email address.'},400);
  await database().prepare('DELETE FROM site_admins WHERE email=?').bind(email).run();
  return json({ok:true});
}
