import {adminGate} from '@/lib/admin';
import {database,files,json} from '@/lib/server';
export const dynamic='force-dynamic';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}) {
  const denied=await adminGate();if(denied)return denied;
  const {id}=await params;
  const job=await database().prepare("SELECT result_key FROM jobs WHERE id=? AND status='complete'").bind(id).first<{result_key:string|null}>();
  if(!job?.result_key)return json({error:'Result unavailable.'},404);
  const file=await files().get(job.result_key);if(!file)return json({error:'Result unavailable.'},404);
  return new Response(file.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Content-Disposition':'attachment; filename="presentation.pptx"','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
}
