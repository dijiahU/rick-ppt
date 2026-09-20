import {database,files,json} from '@/lib/server';
export type Draft={sha256:string;bytes:number;pages:number;revision:number;exported_at:number;saved_at:number};
export async function draftInfo(id:string):Promise<Draft|null>{
 return database().prepare('SELECT sha256,bytes,pages,revision,exported_at,saved_at FROM task_drafts WHERE job_id=?').bind(id).first<Draft>();
}
export async function draftDownload(id:string){
 const row=await database().prepare('SELECT object_key,sha256,bytes FROM task_drafts WHERE job_id=?').bind(id).first<{object_key:string;sha256:string;bytes:number}>();
 if(!row)return json({error:'No successfully exported progress copy yet.'},404);
 const object=await files().get(row.object_key);if(!object)return json({error:'Progress copy unavailable.'},404);
 return new Response(object.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Content-Disposition':'attachment; filename="presentation-progress-unreviewed.pptx"','Content-Length':String(row.bytes),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','ETag':'"'+row.sha256+'"','X-Presentation-Status':'unreviewed-progress'}});
}
