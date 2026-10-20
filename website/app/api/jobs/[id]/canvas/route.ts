import {database,files,json,userId} from '@/lib/server';
import {isAdmin} from '@/lib/admin';
import {canvasKey,canvasSnapshot,canvasVersions} from '@/lib/canvas-storage';
import {liveHead} from '@/lib/progressive-canvas';
import {digestPattern} from '@/lib/visual-edits';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'Sign in to continue.'},401);const {id}=await params,admin=await isAdmin();
 const job=await database().prepare('SELECT id,user_id,status,lease,result_key FROM jobs WHERE id=? AND (user_id=? OR ?=1)').bind(id,user,admin?1:0).first<{id:string;user_id:string;status:string;lease:string|null;result_key:string|null}>();if(!job)return json({error:'Task unavailable.'},404);
 const delivered=job.status==='complete'&&job.result_key?(await files().head(job.result_key))?.customMetadata?.sha256:null;
 const q=new URL(request.url).searchParams,versions=await canvasVersions(id),head=job.status==='running'?await liveHead(id,job.lease):null,sha=q.get('sha256')||head?.sha256||delivered||String(versions[0]?.sha256||'');if(!sha)return json({snapshot:null,versions:[],canEdit:job.user_id===user,canAdminEdit:admin&&job.user_id!==user});if(!digestPattern.test(sha)||!versions.some(v=>v.sha256===sha)&&sha!==head?.sha256)return json({error:'Version unavailable.'},404);
 const snapshot=await canvasSnapshot(id,sha);if(!snapshot)return json({error:'Canvas unavailable.'},404);
 if(q.has('page')){const n=Number(q.get('page'));if(!Number.isSafeInteger(n)||n<1||n>snapshot.pages.length)return json({error:'Page unavailable.'},404);const requested=q.get('image');if(requested&&!digestPattern.test(requested))return json({error:'Invalid image'},400);let image=requested?await files().get(canvasKey(id,sha,`page-${n}-${requested}.png`)):await files().get(canvasKey(id,sha,`page-${n}.png`));if(!image&&requested===snapshot.pages[n-1].imageSha256)image=await files().get(canvasKey(id,sha,`page-${n}.png`));return image?new Response(image.body,{headers:{'Content-Type':'image/png','Cache-Control':'private, max-age=31536000, immutable','ETag':'"'+snapshot.pages[n-1].imageSha256+'"','X-Content-Type-Options':'nosniff'}}):json({error:'Image unavailable.'},404);}
 return json({snapshot,versions,canEdit:job.user_id===user,canAdminEdit:admin&&job.user_id!==user});
}
