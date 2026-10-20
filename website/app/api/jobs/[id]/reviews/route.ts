import {database,json,userId} from '@/lib/server';
import {isAdmin} from '@/lib/admin';
import {readTrace} from '@/lib/admin-trace';
import type {TraceEvent} from '@/lib/admin-trace';
import {publicReview} from '@/lib/review-results';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'Sign in required'},401);
 const {id}=await params,admin=await isAdmin();
 const job=await database().prepare('SELECT id FROM jobs WHERE id=? AND (user_id=? OR ?=1)').bind(id,user,admin?1:0).first();
 if(!job)return json({error:'Task unavailable'},404);
 // Authorization precedes every trace/storage read. Raw records stay internal.
 const response=await readTrace(request,id);
 if(!response.ok)return json({error:'Review results unavailable'},response.status);
 const trace=await response.json() as {available:boolean;attempt?:string|null;events:TraceEvent[];nextChunk:number;totalChunks:number;finished?:boolean};
 const reports=(trace.events||[]).map(publicReview).filter(Boolean);
 return json({available:trace.available,attempt:trace.attempt??null,reports,nextChunk:trace.nextChunk,totalChunks:trace.totalChunks,finished:trace.finished===true});
}
