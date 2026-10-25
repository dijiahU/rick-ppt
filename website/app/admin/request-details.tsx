'use client';
import {useEffect,useRef,useState} from 'react';
import CreationStory from '@/app/creation-story';
import ActivityTimeline from '@/app/activity-timeline';
import AttachmentPreviews from '@/app/attachment-previews';
import QueueStatus from '@/app/queue-status';
import {useLanguage} from '@/app/language';
import {displaySummary,languages,isLocale,type Locale} from '@/lib/i18n';
import {executionLabel,executionWords} from '@/lib/execution-backend-i18n';
import {taskModeMessages} from '@/lib/task-mode-i18n';
import type {ExecutionBackend} from '@/lib/execution-backend';
import type {Progress} from '@/lib/progress';
import type {Attachment} from '@/lib/attachments';
import type {QueueHealth} from '@/lib/queue-state';
import ConversationHistory from './conversation-history';
import UsagePanel from './usage-panel';

type Detail={id:string;user_id:string;title:string;status:string;pages:number;language:string;execution_backend:ExecutionBackend|null;created_at:number;updated_at:number;queue:QueueHealth|null;queuePosition:number|null;brief:string;style:string;summary:string|null;download:boolean;progress:Progress|null;attachments:Attachment[]};
const tabs=['process','conversation','brief','usage','activity'] as const;
type Tab=typeof tabs[number];
const words:Record<Locale,Record<Tab|'close'|'updated'|'user'|'submitted'|'files'|'original'|'trace'|'stale',string>>={
 'zh-CN':{process:'制作过程',conversation:'聊天记录',brief:'需求与附件',usage:'用量',activity:'活动记录',close:'关闭详情',updated:'最后更新',user:'用户编号',submitted:'提交时间',files:'附件',original:'原始需求',trace:'执行记录 · 命令、输出与审核',stale:'执行端近期未上报，进度可能已中断。'},
 en:{process:'Creation process',conversation:'Conversation',brief:'Brief & files',usage:'Usage',activity:'Activity',close:'Close details',updated:'Last updated',user:'User ID',submitted:'Submitted',files:'Attachments',original:'Original brief',trace:'Execution trace · Commands, output and reviews',stale:'The worker has not reported recently. Progress may be interrupted.'},
 fr:{process:'Création',conversation:'Discussion',brief:'Demande et fichiers',usage:'Utilisation',activity:'Activité',close:'Fermer',updated:'Dernière mise à jour',user:'Identifiant utilisateur',submitted:'Soumis le',files:'Pièces jointes',original:'Demande originale',trace:'Exécution · Commandes, résultats et vérifications',stale:'Aucun signal récent de l’exécuteur. La progression peut être interrompue.'},
 es:{process:'Creación',conversation:'Conversación',brief:'Solicitud y archivos',usage:'Uso',activity:'Actividad',close:'Cerrar',updated:'Última actualización',user:'ID de usuario',submitted:'Enviado',files:'Archivos adjuntos',original:'Solicitud original',trace:'Ejecución · Comandos, resultados y revisiones',stale:'El ejecutor no ha informado recientemente. El progreso puede estar interrumpido.'},
 ja:{process:'制作過程',conversation:'会話',brief:'依頼と添付',usage:'使用量',activity:'活動',close:'閉じる',updated:'最終更新',user:'ユーザーID',submitted:'送信日時',files:'添付ファイル',original:'依頼内容',trace:'実行記録 · コマンド・出力・レビュー',stale:'最近の応答がありません。処理が中断している可能性があります。'}
};

export default function RequestDetails({detail,onClose}:{detail:Detail;onClose:()=>void}){
 const {locale,t}=useLanguage(),w=words[locale],m=taskModeMessages[locale];
 const [tab,setTab]=useState<Tab>('process');
 const body=useRef<HTMLDivElement>(null);
 useEffect(()=>{if(body.current)body.current.scrollTop=0;},[tab]);
 const prefix=`admin-detail-${detail.id}`,date=(value:number)=>new Date(value).toLocaleString(locale);
 const label=Object.hasOwn(t.statuses,detail.status)?t.statuses[detail.status as keyof typeof t.statuses]:t.unknownStatus;
 return <>
  <div className="admin-detail-heading"><div className="admin-detail-heading-top"><span className={`status status-${detail.status}`}>{label}</span><button type="button" className="admin-close" onClick={onClose}>{w.close} ×</button></div><h2 title={detail.title}>{detail.title}</h2>
   <div className="admin-detail-actions"><a className="admin-link" href={`/jobs/${detail.id}`}>{t.details} ↗</a>{detail.download&&<a className="admin-link admin-detail-download" href={`/api/admin/jobs/${detail.id}/download`}>{t.download}</a>}</div>
  </div>
  <div className="admin-detail-tabs" role="tablist" aria-label={detail.title} onKeyDown={event=>{
   if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
   event.preventDefault();const current=tabs.indexOf(tab),next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(current+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length;
   setTab(tabs[next]);event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  }}>{tabs.map(key=><button key={key} type="button" role="tab" id={`${prefix}-tab-${key}`} aria-controls={`${prefix}-panel-${key}`} aria-selected={tab===key} tabIndex={tab===key?0:-1} onClick={()=>setTab(key)}>{w[key]}</button>)}</div>
  <div className="admin-detail-body" ref={body}>
   {tabs.map(key=><section key={key} className="admin-detail-panel" role="tabpanel" id={`${prefix}-panel-${key}`} aria-labelledby={`${prefix}-tab-${key}`} hidden={tab!==key} tabIndex={0}>
    {tab===key&&<>
     {key==='process'&&<>{detail.queue&&<QueueStatus queue={detail.queue} position={detail.queuePosition} createdAt={detail.created_at}/>} {detail.status==='running'&&Date.now()-detail.updated_at>120000&&<p className="error">{w.stale}</p>}<CreationStory progress={detail.progress} pages={detail.pages} status={detail.status} base={`/api/admin/jobs/${detail.id}`}/></>}
     {key==='conversation'&&<ConversationHistory id={detail.id}/>}
     {key==='brief'&&<><h3>{w.original}</h3><p className="original-brief">{detail.brief}</p>{!!detail.attachments.length&&<><h3>{w.files} · {detail.attachments.length}</h3><AttachmentPreviews files={detail.attachments} hrefFor={file=>`/api/admin/jobs/${detail.id}/attachments/${file.id}`}/></>}<dl><dt>{w.user}</dt><dd>{detail.user_id}</dd><dt>ID</dt><dd>{detail.id}</dd><dt>{w.submitted}</dt><dd>{date(detail.created_at)}</dd><dt>{w.updated}</dt><dd>{date(detail.updated_at)}</dd><dt>{m.label} / {t.pptLanguage}</dt><dd>{detail.pages===0?m.edit:`${m.create} · ${detail.pages}`} / {isLocale(detail.language)?languages[detail.language]:'—'}</dd><dt>{executionWords[locale].label}</dt><dd>{executionLabel(detail.execution_backend,locale)}</dd><dt>{t.style}</dt><dd>{detail.style}</dd></dl>{detail.pages===0&&<p className="fineprint">{m.automatic}</p>}</>}
     {key==='usage'&&<UsagePanel id={detail.id}/>}
     {key==='activity'&&<>{detail.summary&&<p>{displaySummary(detail.summary,t)}</p>}<p><a className="admin-link" href={`/admin/jobs/${detail.id}/trace`}>{w.trace} →</a></p>{detail.progress?.events.length?<ActivityTimeline events={detail.progress.events}/>:<p className="fineprint">{t.noProgress}</p>}</>}
    </>}
   </section>)}
  </div>
 </>;
}
