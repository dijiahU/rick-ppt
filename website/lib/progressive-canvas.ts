import {database,files} from './server';

import type {CanvasSnapshot} from './visual-edits';
export async function ensureProgressiveCanvas(){const db=database();await db.batch([
 db.prepare('CREATE TABLE IF NOT EXISTS canvas_sources(job_id TEXT NOT NULL,sha256 TEXT NOT NULL,source_key TEXT NOT NULL,producer_lease TEXT NOT NULL,PRIMARY KEY(job_id,sha256))'),
 db.prepare('CREATE TABLE IF NOT EXISTS canvas_heads(job_id TEXT PRIMARY KEY,sha256 TEXT NOT NULL,source_key TEXT NOT NULL,producer_lease TEXT NOT NULL,updated_at INTEGER NOT NULL)'),
 db.prepare('CREATE TABLE IF NOT EXISTS canvas_page_locks(job_id TEXT NOT NULL,page INTEGER NOT NULL,part TEXT NOT NULL,sha256 TEXT NOT NULL,source_key TEXT NOT NULL,image_sha TEXT NOT NULL,edit_id TEXT NOT NULL,PRIMARY KEY(job_id,page))'),
]);}
export type CanvasHead={sha256:string;source_key:string;producer_lease:string};
export async function liveHead(job:string,lease:string|null){await ensureProgressiveCanvas();return database().prepare('SELECT sha256,source_key,producer_lease FROM canvas_heads WHERE job_id=? AND producer_lease=?').bind(job,lease).first<CanvasHead>();}
export async function editableSource(job:{id:string;status:string;lease:string|null;result_key:string|null}):Promise<CanvasHead|null>{
 if(job.status==='running'){const head=await liveHead(job.id,job.lease);if(head)return head;}
 if(!job.result_key)return null;const file=await files().head(job.result_key),sha=file?.customMetadata?.sha256;return sha?{sha256:sha,source_key:job.result_key,producer_lease:job.lease||''}:null;
}
export const pageReady=(s:CanvasSnapshot,n:number)=>s.readyPages===undefined||s.readyPages.includes(n);
export function unchangedPages(base:CanvasSnapshot,current:CanvasSnapshot,pages:number[]){return pages.every(n=>pageReady(base,n)&&pageReady(current,n)&&!!base.pages[n-1]&&base.pages[n-1].part===current.pages[n-1]?.part&&(base.sha256===current.sha256||!!base.pages[n-1].contentSha256&&base.pages[n-1].contentSha256===current.pages[n-1].contentSha256));}
