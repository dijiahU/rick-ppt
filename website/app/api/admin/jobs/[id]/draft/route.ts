import {adminGate} from '@/lib/admin';
import {draftDownload} from '@/lib/drafts';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}){
 const denied=await adminGate();if(denied)return denied;
 return draftDownload((await params).id);
}
