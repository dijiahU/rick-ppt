import {adminGate} from '@/lib/admin';
import {database,json} from '@/lib/server';
import {readUsage} from '@/lib/usage';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await adminGate();if(denied)return denied;
 const {id}=await params,after=new URL(request.url).searchParams.get('after')??'0';
 if(!/^\d{1,7}$/.test(after))return json({error:'Invalid cursor'},400);
 if(!await database().prepare('SELECT id FROM jobs WHERE id=?').bind(id).first())return json({error:'Task not found'},404);
 return json(await readUsage(id,Number(after)));
}
