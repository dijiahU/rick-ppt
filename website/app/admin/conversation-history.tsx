'use client';
import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {visualEditDisplay} from '@/lib/visual-edits';
import {useLanguage} from '@/app/language';
import AttachmentPreviews from '@/app/attachment-previews';
import type {Message} from '@/lib/conversation';
import type {Locale} from '@/lib/i18n';
import './conversation-history.css';
type Page={messages:Message[];hasMore:boolean;nextBefore:number|null};
const words:Record<Locale,string[]>={
 'zh-CN':['用户聊天与修改','用户','Codex','修改要求','普通聊天','已保存','已收到','已应用','暂无聊天记录。','加载更早的消息','正在加载…','聊天记录刷新失败，请稍后重试。','管理员只读查看 · 每 5 秒更新','无权查看聊天记录，请用管理员账号登录。'],
 en:['Conversation and changes','User','Codex','Change request','Chat','Saved','Received','Applied','No messages yet.','Load earlier messages','Loading…','Unable to refresh the conversation. Please try again.','Read-only administrator view · Refreshes every 5 seconds','Administrator sign-in is required to view this conversation.'],
 fr:['Discussion et modifications','Utilisateur','Codex','Modification','Discussion','Enregistré','Reçu','Appliqué','Aucun message.','Charger les messages précédents','Chargement…','Impossible d’actualiser la discussion. Réessayez.','Vue administrateur en lecture seule · Actualisation toutes les 5 secondes','Connectez-vous avec un compte administrateur.'],
 es:['Conversación y cambios','Usuario','Codex','Solicitud de cambios','Conversación','Guardado','Recibido','Aplicado','Todavía no hay mensajes.','Cargar mensajes anteriores','Cargando…','No se pudo actualizar la conversación. Reintenta.','Vista de administrador de solo lectura · Se actualiza cada 5 segundos','Inicia sesión como administrador para ver esta conversación.'],
 ja:['会話と変更依頼','ユーザー','Codex','変更依頼','チャット','保存済み','受信済み','反映済み','メッセージはまだありません。','以前のメッセージを読み込む','読み込み中…','会話を更新できません。もう一度お試しください。','管理者の閲覧専用 · 5秒ごとに更新','管理者アカウントでログインしてください。']
};
export function ConversationMessages({id,messages}:{id:string;messages:Message[]}){
 const {locale}=useLanguage(),w=words[locale];
 return <>{!messages.length?<p className="admin-chat-empty">{w[8]}</p>:messages.map(m=><article className={`admin-chat-message ${m.role}`} key={m.id} data-message-id={m.id}>
  <header><strong>{m.role==='user'?w[1]:w[2]}</strong><time dateTime={new Date(m.createdAt).toISOString()}>{new Date(m.createdAt).toLocaleString(locale)}</time></header>
  {m.body&&<p className="admin-chat-body">{visualEditDisplay(m.body,locale==='zh-CN')??m.body}</p>}
  {!!m.attachments.length&&<AttachmentPreviews files={m.attachments} hrefFor={file=>`/api/admin/jobs/${id}/conversation?message=${m.id}&file=${file.id}`}/>}
  {m.role==='user'&&<small className={`admin-chat-status ${m.status}`}>{m.kind==='revision'?w[3]:w[4]} · {m.status==='applied'?w[7]:m.status==='received'?w[6]:w[5]}</small>}
 </article>)}</>;
}
export default function ConversationHistory({id}:{id:string}){
 const {locale}=useLanguage(),w=words[locale];
 const [data,setData]=useState<Page|null>(null),[error,setError]=useState(false),[denied,setDenied]=useState(false),[loadingEarlier,setLoadingEarlier]=useState(false);
 const transcript=useRef<HTMLDivElement>(null),followLatest=useRef(true),restoreScroll=useRef<{height:number;top:number}|null>(null),olderRequest=useRef<AbortController|null>(null),revoked=useRef(false);
 useEffect(()=>{
  let active=true;const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  async function poll(){try{
   const response=await fetch(`/api/admin/jobs/${id}/conversation`,{cache:'no-store',signal:controller.signal});
   if(response.status===401||response.status===403){if(active){revoked.current=true;olderRequest.current?.abort();setData(null);setDenied(true);}return;}
   if(!response.ok)throw Error();const next=await response.json() as Page;
   if(active&&!revoked.current){setData(prior=>{if(!prior)return next;const all=new Map(prior.messages.map(m=>[m.id,m]));for(const m of next.messages)if(!all.has(m.id)||all.get(m.id)!.updatedAt<=m.updatedAt)all.set(m.id,m);return {...prior,messages:[...all.values()].sort((a,b)=>a.seq-b.seq)};});setError(false);}
  }catch{if(active)setError(true);}finally{if(active&&!revoked.current)timer=setTimeout(poll,5000);}}
  void poll();return()=>{active=false;controller.abort();olderRequest.current?.abort();clearTimeout(timer);};
 },[id]);
 useLayoutEffect(()=>{const node=transcript.current;if(!node)return;if(restoreScroll.current){const prior=restoreScroll.current;node.scrollTop=prior.top+node.scrollHeight-prior.height;restoreScroll.current=null;}else if(followLatest.current)node.scrollTop=node.scrollHeight;},[data?.messages]);
 async function earlier(){
  if(!data?.hasMore||data.nextBefore===null||loadingEarlier||revoked.current)return;
  const controller=new AbortController();olderRequest.current=controller;setLoadingEarlier(true);
  try{
   const response=await fetch(`/api/admin/jobs/${id}/conversation?before=${data.nextBefore}`,{cache:'no-store',signal:controller.signal});
   if(response.status===401||response.status===403){revoked.current=true;setData(null);setDenied(true);return;}
   if(!response.ok)throw Error();const next=await response.json() as Page;
   if(controller.signal.aborted||revoked.current)return;
   const node=transcript.current;if(node)restoreScroll.current={height:node.scrollHeight,top:node.scrollTop};followLatest.current=false;
   setData(prior=>{const all=new Map(next.messages.map(m=>[m.id,m]));for(const m of prior?.messages??[])all.set(m.id,m);return {...next,messages:[...all.values()].sort((a,b)=>a.seq-b.seq)};});setError(false);
  }catch{if(!controller.signal.aborted)setError(true);}finally{if(!controller.signal.aborted)setLoadingEarlier(false);}
 }
 return <section className="admin-conversation" aria-label={w[0]}><h3>{w[0]}</h3><p className="fineprint">{w[12]}</p>
  {denied?<p role="alert" className="error">{w[13]}</p>:<>
   {error&&<p role="status" className="error">{w[11]}</p>}
   {!data?<p role="status">{w[10]}</p>:<><div ref={transcript} className="admin-chat-transcript" role="region" aria-label={w[0]} tabIndex={0} onScroll={event=>{const node=event.currentTarget;followLatest.current=node.scrollHeight-node.scrollTop-node.clientHeight<120;}}>
    {data.hasMore&&<button className="admin-chat-earlier" type="button" onClick={()=>void earlier()} disabled={loadingEarlier}>{loadingEarlier?w[10]:w[9]}</button>}
    <ConversationMessages id={id} messages={data.messages}/>
   </div></>}
  </>}
 </section>;
}
