import {adminGate} from '@/lib/admin';
import {bundleDownload} from '@/lib/bundle-download';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await adminGate();if(denied)return denied;const {id}=await params;
 return bundleDownload(request,id);
}
