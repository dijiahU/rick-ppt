import { database,json,userId,workerOnline } from '@/lib/server';
import {parseAttachments} from '@/lib/attachments';
import {isAdmin} from '@/lib/admin';
export const dynamic='force-dynamic';
export async function GET() {
  const id=await userId(); if(!id) return json({signedIn:false});
  const records=await database().prepare('SELECT id,title,status,created_at,summary,result_key,language,attachments FROM jobs WHERE user_id=? ORDER BY created_at DESC').bind(id).all();
  const admin=await isAdmin();
  return json({signedIn:true,admin,unlimited:admin,remaining:admin?null:Math.max(0,10-records.results.length),online:await workerOnline(),jobs:records.results.map(({result_key,attachments,...row})=>({...row,attachments:parseAttachments(attachments),download:!!result_key}))});
}
