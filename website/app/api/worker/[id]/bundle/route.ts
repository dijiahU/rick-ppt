import {database,files,json,workerAuthorized} from '@/lib/server';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);
 const {id}=await params,lease=request.headers.get('X-Job-Lease'),length=Number(request.headers.get('Content-Length'));
 if(!lease)return json({error:'Lease required'},400);
 if(!Number.isSafeInteger(length)||length<4||length>250*1024*1024||!request.body)return json({error:'Bundle must be at most 250 MB'},413);
 const job=await database().prepare("SELECT id FROM jobs WHERE id=? AND lease=? AND status='running'").bind(id,lease).first();if(!job)return json({error:'Lease expired'},409);
 // Preserve the known-length request stream; R2 does not buffer the whole distribution in Worker memory.
 await files().put(`bundles/${id}/${lease}.zip`,request.body,{httpMetadata:{contentType:'application/zip'},customMetadata:{bytes:String(length)}});
 const current=await database().prepare("SELECT id FROM jobs WHERE id=? AND lease=? AND status='running'").bind(id,lease).first();return current?json({ok:true}):json({error:'Lease expired'},409);
}
