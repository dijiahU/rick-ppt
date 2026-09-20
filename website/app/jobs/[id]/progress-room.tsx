'use client';
import {useEffect,useMemo,useState} from 'react';
import QueueStatus from '@/app/queue-status';
import Conversation from './conversation';
import DraftDownload from './draft-download';
import InteractiveDownload from './interactive-download';
import type {Draft} from '@/lib/drafts';
import CreationStory from '@/app/creation-story';
import PreviewLink from '@/app/preview-link';
import {creationWords} from '@/lib/creation-i18n';
import {progressNotes,previewVersion} from '@/lib/creation-progress';
import type {QueueHealth} from '@/lib/queue-state';
import {LanguagePicker,useLanguage} from '@/app/language';
import {taskModeMessages} from '@/lib/task-mode-i18n';
import type {ActivityEvent,Progress} from '@/lib/progress';
type Data={draft:Draft|null;queue:QueueHealth|null;queuePosition:number|null;title:string;brief:string;pages:number;status:string;createdAt:number;updatedAt:number;download:boolean;scope:'user'|'admin';canInspectExecution?:boolean;progress:Progress|null};
const words={
 en:['Back to studio','Task activity','Events','Sources','Slide previews','All','Search','Opened links','Files','Execution','Media','Render & review','Progress notes','Lifecycle','Filter activity or URL','Newest first','Oldest first','Live · refreshes every 3 seconds','Finished · saved activity','Reconnect failed. Retrying…','No recorded activity yet.','No matching activity.','Original request','Sign in to view this task','Task unavailable or access denied','Started','Completed','Failed','Updated','Recent activity (up to 500 events). Older tasks may have fewer details. Tool events and public progress notes—not a screen broadcast.','No source links recorded yet.','View full screen','Last worker update is over two minutes old.','Refresh now','Waiting in queue','Download PPTX','Recorded action','Agent progress note'],
 'zh-CN':['返回工作室','任务执行详情','活动记录','来源链接','页面预览','全部','搜索','打开的链接','文件','执行操作','素材','渲染与检查','进度说明','任务状态','搜索活动内容或网址','最新在前','最早在前','实时更新 · 每 3 秒同步','任务结束 · 已保存记录','连接失败，正在重试…','尚未收到活动记录。','没有符合条件的活动。','原始需求','登录后查看此任务','任务不存在或无权访问','已开始','已完成','失败','更新时间','最多保留最近 500 条活动。旧任务可能缺少详细记录；这里展示真实工具事件和进度说明，不是屏幕直播。','尚未记录来源链接。','全屏查看','执行端超过两分钟未更新，请留意任务是否中断。','立即刷新','正在排队','下载 PPTX','实际操作记录','Agent 进度说明'],
 fr:['Retour au studio','Activité de la demande','Événements','Sources','Aperçus','Tout','Recherche','Liens ouverts','Fichiers','Exécution','Médias','Rendu et contrôle','Notes','État','Filtrer les activités ou URL','Plus récents','Plus anciens','Direct · actualisation toutes les 3 s','Terminé · activité enregistrée','Connexion interrompue. Nouvel essai…','Aucune activité enregistrée.','Aucun résultat.','Demande originale','Connectez-vous pour voir cette demande','Demande indisponible ou accès refusé','Démarré','Terminé','Échec','Mise à jour','Jusqu’à 500 événements récents. Les anciennes demandes peuvent être moins détaillées. Activités et notes, pas une diffusion d’écran.','Aucune source enregistrée.','Voir en plein écran','Aucun signal depuis plus de deux minutes.','Actualiser','En attente','Télécharger PPTX','Action enregistrée','Note de progression'],
 es:['Volver al estudio','Actividad de la solicitud','Eventos','Fuentes','Vistas previas','Todo','Búsqueda','Enlaces abiertos','Archivos','Ejecución','Medios','Renderizado y revisión','Notas','Estado','Filtrar actividad o URL','Más recientes','Más antiguos','En vivo · cada 3 segundos','Finalizado · actividad guardada','Conexión interrumpida. Reintentando…','Sin actividad registrada.','Sin coincidencias.','Solicitud original','Inicia sesión para ver la solicitud','Solicitud no disponible o acceso denegado','Iniciado','Completado','Fallido','Actualizado','Hasta 500 eventos recientes. Las solicitudes antiguas pueden tener menos detalles. Actividad y notas, no transmisión de pantalla.','Sin fuentes registradas.','Ver en pantalla completa','Sin actualización durante más de dos minutos.','Actualizar','En cola','Descargar PPTX','Acción registrada','Nota de progreso'],
 ja:['スタジオへ','タスクの実行状況','活動','出典','プレビュー','すべて','検索','開いたリンク','ファイル','実行','素材','レンダリングと確認','進捗説明','状態','活動やURLを検索','新しい順','古い順','ライブ · 3秒ごとに更新','完了 · 保存済みの記録','接続できません。再試行中…','活動はまだありません。','一致する活動がありません。','依頼内容','ログインして表示','タスクがないかアクセスできません','開始','完了','失敗','更新日時','最新500件まで。過去のタスクは詳細が少ない場合があります。実際の活動と説明であり、画面配信ではありません。','出典はまだありません。','全画面で表示','2分以上更新されていません。','更新','待機中','PPTXをダウンロード','実際の操作','進捗説明']
};
function category(e:ActivityEvent){return e.category||(e.reported?'note':e.url?'source':e.code==='edited'?'file':['rendered','rendering','inspected','checking'].includes(e.code)?'render':e.code==='working'?'command':'lifecycle');}
const kinds=['all','search','source','file','command','media','render','note','lifecycle'];
export default function ProgressRoom({id}:{id:string}){
 const {locale,t}=useLanguage(),w=words[locale],cw=creationWords[locale];
 const [data,setData]=useState<Data|null>(null),[error,setError]=useState(false),[denied,setDenied]=useState(0),[refresh,setRefresh]=useState(0);
 const [tab,setTab]=useState('story'),[filter,setFilter]=useState('all'),[query,setQuery]=useState(''),[newest,setNewest]=useState(false);
 useEffect(()=>{let active=true;const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  async function poll(){try{const r=await fetch(`/api/jobs/${encodeURIComponent(id)}/progress`,{cache:'no-store',signal:controller.signal});if([401,403,404].includes(r.status)){if(active){setDenied(r.status);setData(null);}return;}if(!r.ok)throw Error();const value=await r.json() as Data;if(!active)return;setData(value);setError(false);setDenied(0);if(!['complete','failed'].includes(value.status))timer=setTimeout(poll,3000);}catch{if(active){setError(true);timer=setTimeout(poll,6000);}}}
  void poll();return()=>{active=false;controller.abort();clearTimeout(timer);};
 },[id,refresh]);
 const events=data?.progress?.events;
 const notes=progressNotes(data?.progress),latestNote=notes.at(-1);
 const visible=useMemo(()=>{const result=(events||[]).filter(e=>(filter==='all'||category(e)===filter)&&`${e.detail||''} ${e.url||''}`.toLowerCase().includes(query.toLowerCase()));return newest?result.slice().reverse():result;},[events,filter,query,newest]);
 const sources=useMemo(()=>{const map=new Map<string,{at:number;count:number}>();for(const e of events||[]){if(e.url){const prior=map.get(e.url);map.set(e.url,{at:e.at,count:(prior?.count||0)+1});}}return [...map];},[events]);
 const base=data?.scope==='admin'?`/api/admin/jobs/${id}`:`/api/jobs/${id}`;
 const terminal=!!data&&['complete','failed'].includes(data.status);
 const label=(status:string)=>Object.hasOwn(t.statuses,status)?t.statuses[status as keyof typeof t.statuses]:t.unknownStatus;
 return <main className="progress-room"><header><a className="brand" href="/">PPTX LAB</a><div><a href="/">← {w[0]}</a><LanguagePicker/></div></header>
 <p className="eyebrow">LIVE WORKSPACE / {w[1]}</p><h1>{data?.title||w[1]}</h1>
 {denied?<section className="room-empty"><p>{denied===401?w[23]:w[24]}</p>{denied===401&&<a href={`/signin-with-chatgpt?return_to=${encodeURIComponent('/jobs/'+id)}`}>{t.signin} →</a>}</section>:<>
 <div className="room-status"><span className={`status status-${data?.status||'queued'}`}>{data?label(data.status):t.loading}</span><span>{terminal?w[18]:w[17]}</span><button onClick={()=>setRefresh(n=>n+1)}>{w[33]}</button>{data?.download&&<a className="download" href={`${base}/download`}>{w[35]} ↓</a>}</div>
 {data?.download&&<InteractiveDownload base={base} locale={locale}/>}
 {data&&<DraftDownload draft={data.draft??null} base={base} locale={locale}/>}
 {error&&<p className="error" role="alert">{w[19]}</p>}{data?.status==='running'&&Date.now()-data.updatedAt>120000&&<p className="error">{w[32]}</p>}
 {data?.queue&&<QueueStatus queue={data.queue} position={data.queuePosition} createdAt={data.createdAt}/>}
 {data&&<details className="room-brief"><summary>{w[22]}</summary><p className="fineprint">{data.pages===0?taskModeMessages[locale].edit:taskModeMessages[locale].create} · {data.pages===0?taskModeMessages[locale].automatic:`${t.pages}: ${data.pages}`}</p><p>{data.brief}</p></details>}
 {data?.canInspectExecution&&<p><a className="download" href={`/admin/jobs/${id}/trace`}>管理员执行记录 · 命令、输出与审核 →</a></p>}
 <div className="room-layout"><section className="room-main"><nav className="room-tabs" aria-label={w[1]}>{[['story',cw.overview,notes.length],['events',w[2],events?.length||0],['sources',w[3],sources.length],['previews',w[4],data?.progress?.previews.length||0]].map(([key,title,count])=><button key={key} onClick={()=>setTab(String(key))} aria-pressed={tab===key}>{title} <span>{count}</span></button>)}</nav>
 {tab==='story'&&data&&<CreationStory key={id} progress={data.progress} pages={data.pages} status={data.status} base={base}/>}
 {tab==='events'&&<><div className="room-controls"><label className="sr-only" htmlFor="activity-query">{w[14]}</label><input id="activity-query" type="search" placeholder={w[14]} value={query} onChange={e=>setQuery(e.target.value)}/><button onClick={()=>setNewest(v=>!v)}>{newest?w[15]:w[16]} ↕</button></div><div className="room-filters">{kinds.map((k,i)=><button key={k} aria-pressed={filter===k} onClick={()=>setFilter(k)}>{w[5+i]}</button>)}</div>
 {!visible.length?<p className="room-empty">{events?.length?w[21]:data?.status==='queued'?w[34]:w[20]}</p>:<ol className="room-events">{visible.map(e=><li key={e.seq}><div className="event-stamp"><span>#{e.seq}</span><time>{new Date(e.at).toLocaleTimeString(locale)}</time></div><article><div className="event-heading"><strong>{e.category?w[5+kinds.indexOf(e.category)]:t.activities[e.code]}</strong>{e.state&&<span className={`event-state ${e.state}`}>{w[25+['started','completed','failed'].indexOf(e.state)]}</span>}</div>{e.detail&&<p>{e.detail}</p>}{e.url&&<a className="event-url" href={e.url} target="_blank" rel="noopener noreferrer">{e.url} ↗</a>}<small>{e.reported?w[37]:w[36]}</small></article></li>)}</ol>}</>}
 {tab==='sources'&&<div className="room-sources">{!sources.length?<p>{w[30]}</p>:sources.map(([url,info])=><article key={url}><strong>{new URL(url).hostname}</strong><a href={url} target="_blank" rel="noopener noreferrer">{url} ↗</a><small>{new Date(info.at).toLocaleTimeString(locale)} · {info.count} {w[2]}</small></article>)}</div>}
 {tab==='previews'&&<div className="room-previews">{!data?.progress?.previews.length?<p>{t.noProgress}</p>:data.progress.previews.map(n=><PreviewLink key={n} href={`${base}/preview/${n}?v=${previewVersion(data.progress!,n)}`} label={`${t.slide} ${n}`}><img src={`${base}/preview/${n}?v=${previewVersion(data.progress!,n)}`} alt={`${t.slide} ${n}`} loading="lazy"/><span>{t.slide} {n} · {w[31]}</span></PreviewLink>)}</div>}
 </section><aside className="room-aside">{data?.scope==='user'&&<Conversation id={id} status={data.status} updatedAt={data.updatedAt} onResume={()=>setRefresh(n=>n+1)}/>}<h2>{w[28]}</h2><p>{data?.progress?new Date(data.progress.updatedAt).toLocaleString(locale):'—'}</p><div aria-live="polite"><strong>{terminal?label(data!.status):latestNote?.phase?cw.phase[latestNote.phase]:events?.length?t.activities[events[events.length-1].code]:t.waiting}</strong><p>{latestNote?.detail||''}</p>{!terminal&&latestNote?.next&&<p><strong>{cw.next}</strong><br/>{latestNote.next}</p>}</div><p className="fineprint">{w[29]}</p></aside></div></>}
 </main>;
}
