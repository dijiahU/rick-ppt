import {database,json,userId} from '@/lib/server';
import {draftDownload} from '@/lib/drafts';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await userId();if(!user)return json({error:'Sign in required.'},401);
 const {id}=await params;const job=await database().prepare('SELECT id FROM jobs WHERE id=? AND user_id=?').bind(id,user).first();
 if(!job)return json({error:'Task unavailable.'},404);
 return draftDownload(id);
}
