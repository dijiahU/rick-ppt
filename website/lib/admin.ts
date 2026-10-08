import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '@/app/chatgpt-auth';
import {adminAllowed} from './admin-policy';
import {database,json} from './server';
import {normalizeAdminEmail} from './admin-accounts';

export async function isAdmin() {
  const user=await getChatGPTUser();
  if(adminAllowed(user,env)) return true;
  if(!user) return false;
  const email=normalizeAdminEmail(user.email);
  if(!email)return false;
  try {
    const row=await database().prepare('SELECT email,user_id FROM site_admins WHERE email=? OR user_id=? LIMIT 1').bind(email,user.userId).first<{email:string;user_id:string|null}>();
    if(!row)return false;
    if(row.user_id!==user.userId)await database().prepare('UPDATE site_admins SET user_id=?,display_name=? WHERE email=?').bind(user.userId,user.displayName,row.email).run();
    return true;
  } catch {
    return false;
  }
}
export async function adminGate() {
  const user=await getChatGPTUser();
  if(!user) return json({error:'Sign in to continue.'},401);
  if(!await isAdmin()) return json({error:'Administrator access required.'},403);
  return null;
}
