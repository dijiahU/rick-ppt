import {env} from 'cloudflare:workers';
import {json} from './server';
// Separate read-only capability: never accepted by the job worker or admin UI.
export async function reviewGate(request:Request) {
  const expected=env.REVIEW_TOKEN;
  const provided=request.headers.get('Authorization')?.match(/^Bearer ([A-Za-z0-9_-]{32,128})$/)?.[1];
  if(!expected||expected.length<32||!provided)return json({error:'Unauthorized'},401);
  const digest=async(value:string)=>new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)));
  const [a,b]=await Promise.all([digest(expected),digest(provided)]);
  let difference=0;for(let i=0;i<a.length;i++)difference|=a[i]^b[i];
  return difference?json({error:'Unauthorized'},401):null;
}
