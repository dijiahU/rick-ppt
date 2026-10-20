import {database,files} from './server';
import {validateSnapshot,type CanvasSnapshot,digestPattern} from './visual-edits';
export async function ensureCanvas(){await database().prepare('CREATE TABLE IF NOT EXISTS canvas_snapshots(job_id TEXT NOT NULL,sha256 TEXT NOT NULL,version_id TEXT NOT NULL,created_at INTEGER NOT NULL,pages INTEGER NOT NULL,PRIMARY KEY(job_id,sha256))').run();}
export const canvasKey=(job:string,sha:string,name:string)=>`canvas/${job}/${sha}/${name}`;
export async function canvasSnapshot(job:string,sha:string):Promise<CanvasSnapshot|null>{if(!digestPattern.test(sha))return null;const object=await files().get(canvasKey(job,sha,'manifest.json'));if(!object)return null;return validateSnapshot(await object.json());}
export async function canvasVersions(job:string){await ensureCanvas();const rows=await database().prepare('SELECT sha256,version_id AS versionId,created_at AS createdAt,pages FROM canvas_snapshots WHERE job_id=? ORDER BY created_at DESC LIMIT 30').bind(job).all();return rows.results;}
export async function latestCanvas(job:string){const versions=await canvasVersions(job);return versions.length?canvasSnapshot(job,String(versions[0].sha256)):null;}
