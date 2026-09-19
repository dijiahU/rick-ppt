import {adminGate} from '@/lib/admin';
import {readTrace} from '@/lib/admin-trace';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await adminGate();if(denied)return denied;
 return readTrace(request,(await params).id);
}
