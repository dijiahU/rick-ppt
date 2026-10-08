'use client';
import {FormEvent,useEffect,useState} from 'react';

type Admin={email:string;user_id:string|null;display_name:string|null;created_at:number;created_by:string};
type Payload={primary:{email:string;displayName:string}|null;admins:Admin[]};

export default function AdminManager(){
 const [data,setData]=useState<Payload|null>(null);const [email,setEmail]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 async function load(){const response=await fetch('/api/admin/admins',{cache:'no-store'});if(response.ok)setData(await response.json());}
 useEffect(()=>{void load();},[]);
 async function add(event:FormEvent){event.preventDefault();setBusy(true);setError('');const response=await fetch('/api/admin/admins',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});const result=await response.json().catch(()=>({error:'Request failed.'})) as {error?:string};if(!response.ok)setError(result.error||'Request failed.');else{setEmail('');await load();}setBusy(false);}
 async function remove(value:string){setBusy(true);setError('');const response=await fetch(`/api/admin/admins?email=${encodeURIComponent(value)}`,{method:'DELETE'});if(!response.ok){const result=await response.json().catch(()=>({error:'Request failed.'})) as {error?:string};setError(result.error||'Request failed.');}else await load();setBusy(false);}
 return <section className="admin-manager" aria-labelledby="admin-manager-title"><div><p className="eyebrow">ACCESS</p><h2 id="admin-manager-title">管理员账号</h2><p>主账号永久保留管理权限。新增账号首次用同一邮箱登录后，即可查看所有任务并继续配置管理员。这里管理站内权限；发布权限需同时把账号设为 Sites 编辑者。</p></div><form onSubmit={add}><label htmlFor="admin-email">管理员邮箱</label><div><input id="admin-email" type="email" autoComplete="email" maxLength={254} required value={email} onChange={event=>setEmail(event.target.value)} placeholder="name@example.com"/><button disabled={busy}>添加管理员</button></div>{error&&<p className="error" role="alert">{error}</p>}</form><ul>{data?.primary&&<li><span><strong>{data.primary.displayName||data.primary.email}</strong><small>{data.primary.email}</small></span><em>主账号 · 不可移除</em></li>}{data?.admins.map(admin=><li key={admin.email}><span><strong>{admin.display_name||admin.email}</strong>{admin.display_name&&<small>{admin.email}</small>}</span><button disabled={busy} onClick={()=>void remove(admin.email)}>移除</button></li>)}</ul></section>;
}
