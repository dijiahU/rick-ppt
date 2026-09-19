import {getChatGPTUser,chatGPTSignInPath} from '@/app/chatgpt-auth';
import {isAdmin} from '@/lib/admin';
import TraceRoom from './trace-room';
import './trace.css';
export const dynamic='force-dynamic';
export const metadata={title:'PPTX LAB · 执行记录',robots:{index:false,follow:false},openGraph:{images:[]},twitter:{images:[]}};
export default async function TracePage({params}:{params:Promise<{id:string}>}){
 const {id}=await params;
 if(!await getChatGPTUser())return <main><h1>管理员执行记录</h1><a href={chatGPTSignInPath(`/admin/jobs/${encodeURIComponent(id)}/trace`)}>登录后查看 →</a></main>;
 if(!await isAdmin())return <main><h1>需要管理员权限</h1><a href="/">返回工作室</a></main>;
 return <TraceRoom id={id}/>;
}
