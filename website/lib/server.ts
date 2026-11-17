import { env } from 'cloudflare:workers';
import { getChatGPTUser } from '@/app/chatgpt-auth';
import {combinedWorkerStatus, type WorkerIdentity} from './worker-routing';
export function database() { return env.DB; }
export function files() { return env.FILES; }
export const json = (value: unknown, status = 200) => Response.json(value, {status, headers:{'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
export async function userId() { return (await getChatGPTUser())?.userId ?? null; }
export function sameOrigin(request: Request) { const origin=request.headers.get('Origin'); return !!origin && origin===new URL(request.url).origin; }
async function tokenMatches(provided: string, expected: string | undefined) {
  if (!expected || expected.length < 32) return false;
  const digest = async (s: string) => new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)));
  const [a,b] = await Promise.all([digest(provided),digest(expected)]);
  let difference=0; for(let i=0;i<a.length;i++) difference|=a[i]^b[i]; return difference===0;
}
// The presented secret decides the worker identity: the server keeps
// WORKER_TOKEN; an optional LOCAL_WORKER_TOKEN identifies the local machine.
export async function workerIdentity(request: Request): Promise<WorkerIdentity | null> {
  const provided = request.headers.get('Authorization')?.replace(/^Bearer /,'') ?? '';
  const [server, local] = await Promise.all([tokenMatches(provided, env.WORKER_TOKEN), tokenMatches(provided, env.LOCAL_WORKER_TOKEN)]);
  return server ? 'server' : local ? 'local' : null;
}
export async function workerAuthorized(request: Request) {
  return (await workerIdentity(request)) !== null;
}
async function workerRows() {
  return (await database().prepare('SELECT heartbeat,execution_backends FROM worker').all<{heartbeat:number;execution_backends:string|null}>()).results ?? [];
}
export async function workerOnline() {
  return combinedWorkerStatus(await workerRows(), Date.now()).online;
}
export async function workerStatus() {
  return combinedWorkerStatus(await workerRows(), Date.now());
}
