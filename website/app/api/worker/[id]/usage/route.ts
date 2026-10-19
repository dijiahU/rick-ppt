import {database,json,workerAuthorized} from '@/lib/server';
import {storeUsage} from '@/lib/usage';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 if(!await workerAuthorized(request))return json({error:'Unauthorized'},401);
 const {id}=await params,lease=request.headers.get('X-Job-Lease');
 if(!lease)return json({error:'Lease required'},400);
 const job=await database().prepare('SELECT id FROM jobs WHERE id=? AND lease=?').bind(id,lease).first();
 if(!job)return json({error:'Lease expired'},409);
 return storeUsage(request,id,lease);
}
