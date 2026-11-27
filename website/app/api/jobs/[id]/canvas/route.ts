import {database,files,json,userId} from '@/lib/server';
import {isAdmin} from '@/lib/admin';
import {canvasKey,canvasSnapshot,canvasVersions,canvasVersionPageCount} from '@/lib/canvas-storage';
import {liveHead} from '@/lib/progressive-canvas';
import {digestPattern} from '@/lib/visual-edits';

function pageImage(image:R2ObjectBody,digest:string,immutable:boolean){
 return new Response(image.body,{headers:{
  'Content-Type':'image/png',
  'Cache-Control':immutable?'private, max-age=31536000, immutable':'private, no-store',
  'ETag':'"'+digest+'"',
  'X-Content-Type-Options':'nosniff',
 }});
}

export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'Sign in to continue.'},401);
 const {id}=await params,admin=await isAdmin();
 const job=await database().prepare('SELECT user_id,status,lease,result_key FROM jobs WHERE id=? AND (user_id=? OR ?=1)').bind(id,user,admin?1:0).first<{user_id:string;status:string;lease:string|null;result_key:string|null}>();
 if(!job)return json({error:'Task unavailable.'},404);
 const q=new URL(request.url).searchParams,explicit=q.get('sha256'),requested=q.get('image');
 const page=q.has('page')?Number(q.get('page')):null;
 if(page!==null&&(!Number.isSafeInteger(page)||page<1))return json({error:'Page unavailable.'},404);
 if(page!==null&&requested&&!digestPattern.test(requested))return json({error:'Invalid image'},400);
 if(explicit&&!digestPattern.test(explicit))return json({error:'Version unavailable.'},404);
 const bucket=files();
 if(page!==null&&explicit&&requested){
  // A registered version binds the slide count. A hash-addressed preview
  // can be served without reading the delivered PPTX or the object manifest.
  const count=await canvasVersionPageCount(id,explicit);
  if(count!==null){
   if(page>count)return json({error:'Page unavailable.'},404);
   const image=await bucket.get(canvasKey(id,explicit,`page-${page}-${requested}.png`));
   if(image?.customMetadata?.sha256===requested)return pageImage(image,requested,true);
  }
 }

 const [versions,head,delivered]=await Promise.all([
  canvasVersions(id),
  job.status==='running'?liveHead(id,job.lease):null,
  !explicit&&job.status==='complete'&&job.result_key?bucket.head(job.result_key):null,
 ]);
 const access={canEdit:job.user_id===user,canAdminEdit:admin&&job.user_id!==user};
 const sha=explicit||head?.sha256||delivered?.customMetadata?.sha256||String(versions[0]?.sha256||'');
 if(!sha)return json({snapshot:null,versions:[],...access});
 if(!digestPattern.test(sha)||!versions.some(v=>v.sha256===sha)&&sha!==head?.sha256)return json({error:'Version unavailable.'},404);
 const snapshot=await canvasSnapshot(id,sha);
 if(!snapshot)return json({error:'Canvas unavailable.'},404);
 if(page===null)return json({snapshot,versions,...access});
 if(page>snapshot.pages.length)return json({error:'Page unavailable.'},404);
 const digest=snapshot.pages[page-1].imageSha256;
 if(requested){
  const image=await bucket.get(canvasKey(id,sha,`page-${page}-${requested}.png`));
  if(image)return pageImage(image,requested,true);
  if(requested!==digest)return json({error:'Image unavailable.'},404);
 }
 const image=await bucket.get(canvasKey(id,sha,`page-${page}.png`));
 return image?pageImage(image,digest,!!requested):json({error:'Image unavailable.'},404);
}
