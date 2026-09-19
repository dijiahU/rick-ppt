import {validSlideKey} from '@/lib/slide-limits.mjs';
import { database,files,json,userId } from '@/lib/server';
export const dynamic='force-dynamic';
export async function GET(_request:Request,{params}:{params:Promise<{id:string;slide:string}>}) {
  const user=await userId();if(!user)return json({error:'请先登录。'},401);
  const {id,slide}=await params;
  if(!validSlideKey(slide))return json({error:'页面不存在。'},404);
  const job=await database().prepare('SELECT lease FROM jobs WHERE id=? AND user_id=?').bind(id,user).first<{lease:string|null}>();
  if(!job?.lease)return json({error:'预览不存在。'},404);
  const file=await files().get(`previews/${id}/${job.lease}/${slide}.png`);
  if(!file)return json({error:'页面尚未渲染。'},404);
  return new Response(file.body,{headers:{'Content-Type':'image/png','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"}});
}
