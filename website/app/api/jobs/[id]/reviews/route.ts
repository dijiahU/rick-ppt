import {database,json,userId} from '@/lib/server';
import {isAdmin} from '@/lib/admin';
import {readTracePage} from '@/lib/admin-trace';
import {publicReview} from '@/lib/review-results';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'Sign in required'},401);
 const {id}=await params,admin=await isAdmin();
 const job=await database().prepare('SELECT lease,status FROM jobs WHERE id=? AND (user_id=? OR ?=1)').bind(id,user,admin?1:0).first<{lease:string|null;status:string}>();
 if(!job)return json({error:'Task unavailable'},404);
 // Authorization precedes every trace/storage read. Raw records stay internal.
 const trace=await readTracePage(request,id,job);
 if(trace instanceof Response)return json({error:'Review results unavailable'},trace.status);
 const reports=(trace.events||[]).map(publicReview).filter(Boolean);
 return json({available:trace.available,attempt:trace.attempt??null,reports,nextChunk:trace.nextChunk,totalChunks:trace.totalChunks,finished:trace.finished===true});
}
