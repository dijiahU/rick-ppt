import {database,files} from '@/lib/server';
import {parseAttachments,type Attachment} from '@/lib/attachments';
export const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
export const MAX_MESSAGE=8000,MAX_MESSAGES=1000;
export type Message={seq:number;id:string;role:'user'|'assistant';kind:'chat'|'revision';body:string;attachments:Attachment[];status:string;revision:number|null;createdAt:number;updatedAt:number};
export type MessageRow={seq:number;id:string;role:'user'|'assistant';kind:'chat'|'revision';body:string;attachments:string;status:string;revision:number|null;created_at:number;updated_at:number};
export const message=(row:MessageRow):Message=>({seq:row.seq,id:row.id,role:row.role,kind:row.kind,body:row.body,attachments:parseAttachments(row.attachments),status:row.status,revision:row.revision,createdAt:row.created_at,updatedAt:row.updated_at});
export const messageFileKey=(job:string,messageId:string,file:string)=>`conversation/${job}/${messageId}/${file}`;
// Additive initialization supports an existing deployment while migrations are applied.
export async function ensureConversation(){
 const db=database();await db.batch([
  db.prepare("CREATE TABLE IF NOT EXISTS task_messages (seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL,job_id TEXT NOT NULL,user_id TEXT NOT NULL,role TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,attachments TEXT NOT NULL DEFAULT '[]',status TEXT NOT NULL DEFAULT 'pending',revision INTEGER,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)"),
  db.prepare('CREATE UNIQUE INDEX IF NOT EXISTS task_messages_job_id ON task_messages(job_id,id)'),
  db.prepare('CREATE INDEX IF NOT EXISTS task_messages_job_seq ON task_messages(job_id,seq)'),
  db.prepare("CREATE TABLE IF NOT EXISTS task_recovery (job_id TEXT PRIMARY KEY,checkpoint TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0,last_message_seq INTEGER NOT NULL DEFAULT 0,resumable INTEGER NOT NULL DEFAULT 0,updated_at INTEGER NOT NULL)"),
  db.prepare('CREATE TABLE IF NOT EXISTS task_versions (id TEXT PRIMARY KEY,job_id TEXT NOT NULL,result_key TEXT,bundle_key TEXT,revision INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL)'),
  db.prepare('CREATE INDEX IF NOT EXISTS task_versions_job_created ON task_versions(job_id,created_at)'),
 ]);
}
export async function conversation(job:string){
 const db=database();const [rows,recovery,versions]=await Promise.all([
  db.prepare('SELECT * FROM task_messages WHERE job_id=? ORDER BY seq DESC LIMIT 200').bind(job).all<MessageRow>(),
  db.prepare('SELECT checkpoint,revision,last_message_seq,resumable,updated_at FROM task_recovery WHERE job_id=?').bind(job).first<{checkpoint:string;revision:number;last_message_seq:number;resumable:number;updated_at:number}>(),
  db.prepare('SELECT id,revision,created_at,result_key IS NOT NULL AS pptx,bundle_key IS NOT NULL AS bundle FROM task_versions WHERE job_id=? ORDER BY created_at DESC LIMIT 100').bind(job).all(),
 ]);
 let checkpoint:{phase?:string;pluginVersion?:string}|null=null;try{checkpoint=JSON.parse(recovery?.checkpoint??'null');}catch{}
 return {messages:rows.results.reverse().map(message),recovery:recovery?{resumable:!!recovery.resumable,revision:recovery.revision,lastMessageSeq:recovery.last_message_seq,updatedAt:recovery.updated_at,phase:checkpoint?.phase??'',pluginVersion:checkpoint?.pluginVersion??''}:null,versions:versions.results};
}
export function checkpointValue(value:unknown){
 if(!value||typeof value!=='object'||Array.isArray(value))return null;
 const v=value as Record<string,unknown>;
 if(typeof v.checkpointId!=='string'||!uuid.test(v.checkpointId)||typeof v.runId!=='string'||!uuid.test(v.runId)||typeof v.phase!=='string'||!/^[\w .-]{1,80}$/.test(v.phase)||typeof v.pluginVersion!=='string'||!/^[\w.+-]{1,120}$/.test(v.pluginVersion)||typeof v.resumable!=='boolean'||!Number.isSafeInteger(v.revision)||(v.revision as number)<0||!Number.isSafeInteger(v.lastMessageSeq)||(v.lastMessageSeq as number)<0)return null;
 return {checkpointId:v.checkpointId,runId:v.runId,phase:v.phase,pluginVersion:v.pluginVersion,resumable:v.resumable,revision:v.revision as number,lastMessageSeq:v.lastMessageSeq as number};
}
export async function messageAttachment(job:string,id:string,file:string){
 const row=await database().prepare('SELECT attachments FROM task_messages WHERE job_id=? AND id=?').bind(job,id).first<{attachments:string}>();
 const meta=parseAttachments(row?.attachments).find(x=>x.id===file);
 if(!meta)return null;const object=await files().get(messageFileKey(job,id,file));return object?{object,meta}:null;
}
