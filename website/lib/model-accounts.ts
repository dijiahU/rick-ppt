import {env} from 'cloudflare:workers';
import {database} from './server';
import {modelProviders,type ModelProvider} from './model-providers';

export function modelAccountsEnabled(){return /^[a-fA-F0-9]{64}$/.test(env.BYOK_ENCRYPTION_KEY??'');}
export async function ensureModelAccounts(){
 const db=database();await db.batch([
  db.prepare('CREATE TABLE IF NOT EXISTS model_accounts (id TEXT PRIMARY KEY,user_id TEXT NOT NULL,provider TEXT NOT NULL,label TEXT NOT NULL,key_hint TEXT NOT NULL,secret TEXT NOT NULL,models TEXT NOT NULL,created_at INTEGER NOT NULL,revoked_at INTEGER)'),
  db.prepare('CREATE INDEX IF NOT EXISTS model_accounts_user ON model_accounts(user_id,revoked_at)'),
  db.prepare('CREATE TABLE IF NOT EXISTS task_funding (job_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,credential_id TEXT NOT NULL,provider TEXT NOT NULL,model TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,created_at INTEGER NOT NULL)'),
 ]);
}
async function encryptionKey(){
 if(!modelAccountsEnabled())throw Error('Model account storage is unavailable');
 const hex=env.BYOK_ENCRYPTION_KEY!;
 return crypto.subtle.importKey('raw',new Uint8Array(hex.match(/../g)!.map(s=>parseInt(s,16))),'AES-GCM',false,['encrypt','decrypt']);
}
function decode(s:string){return Uint8Array.from(atob(s),c=>c.charCodeAt(0));}
function encode(b:Uint8Array){return btoa(String.fromCharCode(...b));}
const context=(id:string,user:string,provider:string)=>new TextEncoder().encode(JSON.stringify(['rickppt-model-key-v1',id,user,provider]));
export async function sealKey(key:string,id:string,user:string,provider:string){
 const iv=crypto.getRandomValues(new Uint8Array(12));
 const data=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:context(id,user,provider)},await encryptionKey(),new TextEncoder().encode(key));
 return 'v1.'+encode(iv)+'.'+encode(new Uint8Array(data));
}
export async function openKey(value:string,id:string,user:string,provider:string){
 const parts=value.split('.');if(parts.length!==3||parts[0]!=='v1')throw Error('Invalid credential envelope');
 const data=await crypto.subtle.decrypt({name:'AES-GCM',iv:decode(parts[1]),additionalData:context(id,user,provider)},await encryptionKey(),decode(parts[2]));
 return new TextDecoder().decode(data);
}
export type Funding={credentialId:string;provider:ModelProvider;model:string};
export async function resolveFunding(user:string,value:unknown):Promise<Funding|null>{
 if(value===undefined||value===null||value==='')return null;
 if(!modelAccountsEnabled()||typeof value!=='object'||Array.isArray(value))throw Error('Invalid model account');
 const input=value as Record<string,unknown>;
 if(Object.keys(input).some(k=>!['credentialId','model'].includes(k))||typeof input.credentialId!=='string'||typeof input.model!=='string')throw Error('Invalid model account');
 const row=await database().prepare('SELECT id,provider,models FROM model_accounts WHERE id=? AND user_id=? AND revoked_at IS NULL').bind(input.credentialId,user).first<{id:string;provider:ModelProvider;models:string}>();
 if(!row||!Object.hasOwn(modelProviders,row.provider)||!(modelProviders[row.provider].models as readonly string[]).includes(input.model)||!JSON.parse(row.models).includes(input.model))throw Error('Model unavailable for this account');
 return {credentialId:row.id,provider:row.provider,model:input.model};
}
export async function sameFunding(job:string,funding:Funding|null){
 const row=await database().prepare('SELECT credential_id,provider,model FROM task_funding WHERE job_id=?').bind(job).first();
 return funding?!!row&&row.credential_id===funding.credentialId&&row.provider===funding.provider&&row.model===funding.model:!row;
}
