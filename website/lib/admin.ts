import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '@/app/chatgpt-auth';
import {adminAllowed} from './admin-policy';
import {json} from './server';
export async function isAdmin() { return adminAllowed(await getChatGPTUser(),env); }
export async function adminGate() {
  const user=await getChatGPTUser();
  if(!user) return json({error:'Sign in to continue.'},401);
  if(!adminAllowed(user,env)) return json({error:'Administrator access required.'},403);
  return null;
}
