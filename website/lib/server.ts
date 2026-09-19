import { env } from 'cloudflare:workers';
import { getChatGPTUser } from '@/app/chatgpt-auth';
export function database() { return env.DB; }
export function files() { return env.FILES; }
export const json = (value: unknown, status = 200) => Response.json(value, {status, headers:{'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
export async function userId() { return (await getChatGPTUser())?.userId ?? null; }
export function sameOrigin(request: Request) { const origin=request.headers.get('Origin'); return !!origin && origin===new URL(request.url).origin; }
export async function workerAuthorized(request: Request) {
  const expected = env.WORKER_TOKEN;
  if (!expected || expected.length < 32) return false;
  const provided = request.headers.get('Authorization')?.replace(/^Bearer /,'') ?? '';
  const digest = async (s: string) => new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)));
  const [a,b] = await Promise.all([digest(provided),digest(expected)]);
  let difference=0; for(let i=0;i<a.length;i++) difference|=a[i]^b[i]; return difference===0;
}
export async function workerOnline() {
  const row=await database().prepare('SELECT heartbeat FROM worker WHERE id = ?').bind('primary').first<{heartbeat:number}>();
  return !!row && row.heartbeat > Date.now()-90000;
}
