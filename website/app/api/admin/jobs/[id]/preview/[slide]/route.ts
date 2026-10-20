import {canvasKey} from '@/lib/canvas-storage';
import {digestPattern} from '@/lib/visual-edits';
import {validSlideKey} from '@/lib/slide-limits.mjs';
import {adminGate} from '@/lib/admin';
import {database,files,json} from '@/lib/server';
export const dynamic='force-dynamic';
export async function GET(_request:Request,{params}:{params:Promise<{id:string;slide:string}>}) {
  const denied=await adminGate();if(denied)return denied;
  const {id,slide}=await params;if(!validSlideKey(slide))return json({error:'Invalid slide.'},404);
  const job=await database().prepare('SELECT lease,status,result_key FROM jobs WHERE id=?').bind(id).first<{lease:string|null;status:string;result_key:string|null}>();
  if(job?.status==='complete'&&job.result_key){const saved=await files().head(job.result_key),sha=saved?.customMetadata?.sha256;if(sha&&digestPattern.test(sha)){const image=await files().get(canvasKey(id,sha,`page-${slide}.png`));if(image)return new Response(image.body,{headers:{'Content-Type':'image/png','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"}});}}
  if(!job?.lease)return json({error:'Preview unavailable.'},404);
  const file=await files().get(`previews/${id}/${job.lease}/${slide}.png`);
  if(!file)return json({error:'Preview unavailable.'},404);
  return new Response(file.body,{headers:{'Content-Type':'image/png','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"}});
}
