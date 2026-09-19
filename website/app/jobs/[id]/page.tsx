import ProgressRoom from './progress-room';
import './progress-room.css';
import {database,userId} from '@/lib/server';
import {isAdmin} from '@/lib/admin';
export const dynamic='force-dynamic';
export async function generateMetadata({params}:{params:Promise<{id:string}>}){
 const {id}=await params,user=await userId();
 const row=user?await database().prepare('SELECT title FROM jobs WHERE id=? AND (user_id=? OR ?=1)').bind(id,user,await isAdmin()?1:0).first<{title:string}>():null;
 const title=row?`${row.title} · PPTX LAB`:'PPTX LAB · Task activity',description=row?'Task execution, sources and slide previews.':'Sign in to view this task.';
 return {title,description,robots:{index:false,follow:false},openGraph:{title,description,images:[]},twitter:{title,description,images:[]}};
}
export default async function TaskPage({params}:{params:Promise<{id:string}>}){
 const {id}=await params;
 return <ProgressRoom id={id}/>;
}
