import {database} from './server';
export async function ensureNativeEdits(){const db=database();await db.batch([
 db.prepare("CREATE TABLE IF NOT EXISTS native_edits(id TEXT PRIMARY KEY,job_id TEXT NOT NULL,user_id TEXT NOT NULL,base_sha TEXT NOT NULL,source_key TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',lease TEXT,result_sha TEXT,error TEXT,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)"),
 db.prepare('CREATE INDEX IF NOT EXISTS native_edits_job ON native_edits(job_id,created_at)'),
]);}
export type NativeEditRow={id:string;job_id:string;user_id:string;base_sha:string;source_key:string;payload:string;status:string;lease:string|null;result_sha:string|null;error:string|null;created_at:number;updated_at:number};
export const nativeKey=(job:string,id:string,name:string)=>`native-edits/${job}/${id}/${name}`;
export const nativeStatus=(r:NativeEditRow)=>({id:r.id,status:r.status,resultSha256:r.result_sha,error:r.error,updatedAt:r.updated_at});
