import {getChatGPTUser,chatGPTSignInPath} from '@/app/chatgpt-auth';
import {isAdmin} from '@/lib/admin';
import Dashboard from './dashboard';
import './admin.css';
export const dynamic='force-dynamic';
export const metadata={title:'PPTX LAB · Administration',robots:{index:false,follow:false}};
export default async function AdminPage(){
  const user=await getChatGPTUser();
  if(!user)return <main className="admin"><header><a className="brand" href="/">PPTX LAB / ADMIN</a></header><h1>Private workspace.</h1><p>Sign in with the administrator account to view all requests.</p><a className="admin-link" href={chatGPTSignInPath('/admin')}>Sign in with ChatGPT →</a></main>;
  if(!await isAdmin())return <main className="admin"><h1>Administrator access required.</h1><p>This account does not have access to other users’ requests.</p><a href="/">← Return to your workspace</a></main>;
  return <Dashboard/>;
}
