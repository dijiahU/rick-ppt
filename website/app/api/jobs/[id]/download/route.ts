import { database,files,json,userId } from '@/lib/server';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}) {
  const user=await userId(); if(!user) return json({error:'请先登录。'},401);
  const {id}=await params;
  const job=await database().prepare("SELECT result_key FROM jobs WHERE id=? AND user_id=? AND status='complete'").bind(id,user).first<{result_key:string}>();
  if(!job?.result_key) return json({error:'结果不存在或尚未完成。'},404);
  const file=await files().get(job.result_key); if(!file) return json({error:'结果文件不可用。'},404);
  return new Response(file.body,{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation','Content-Disposition':'attachment; filename="presentation.pptx"','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
}
