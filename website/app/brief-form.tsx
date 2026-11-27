'use client';
import {useCallback,useEffect,useState,useRef} from 'react';
import {executionWords,executionLabel} from '@/lib/execution-backend-i18n';
import type {ExecutionBackend} from '@/lib/execution-backend';
import {quotaMessages} from '@/lib/quota-i18n';
import {queueWords} from '@/lib/queue-i18n';
import {taskModeMessages,sourceFileLabels} from '@/lib/task-mode-i18n';
import {hasEditableDeck,resolvePages,MAX_SLIDES,type TaskMode} from '@/lib/task-mode';
import {pageCountMessages} from '@/lib/page-count-i18n';
import FileUpload from './file-upload';
import BriefFields from './brief-fields';
import {briefCopy,composeBrief,deriveTitle,emptyAnswers,type BriefAnswers} from '@/lib/brief-fields';
import ModelAccounts,{ModelAccountPicker,type ModelSelection} from './model-accounts';
import type {ModelAccount} from '@/lib/model-providers';
import {uploadFiles,discardUploads} from '@/lib/upload-client';
import {uploadMessages} from '@/lib/upload-i18n';
import type {Attachment} from '@/lib/attachments';
import {useLanguage} from './language';
import {resolvePresentationLanguage,languageResolutionMessages} from '@/lib/presentation-language';
import {displaySummary,isLocale,languages,styleValues,type Locale,type Messages} from '@/lib/i18n';
type Job={id:string;title:string;status:string;created_at:number;summary:string|null;download:boolean;language:Locale|null;execution_backend:ExecutionBackend|null;attachments:Attachment[];modelAccount?:{provider:string;model:string}};
/** How many earlier jobs hang on the wall before the visitor asks for all of them: two rows of three. */
const RECENT=6;
const words:Record<Locale,{settings:string;all:(count:number)=>string;fewer:string}>={
 'zh-CN':{settings:'制作设置（页数、视觉方向、语言、Fast 模式）',all:count=>`查看全部 ${count} 条`,fewer:`只看最近 ${RECENT} 条`},
 en:{settings:'Settings (slide count, visual direction, language, Fast mode)',all:count=>`Show all ${count}`,fewer:`Show the latest ${RECENT}`},
 fr:{settings:'Réglages (nombre de diapositives, direction visuelle, langue, mode Fast)',all:count=>`Tout afficher (${count})`,fewer:`Afficher les ${RECENT} derniers`},
 es:{settings:'Ajustes (número de diapositivas, dirección visual, idioma, modo Fast)',all:count=>`Ver los ${count}`,fewer:`Ver los ${RECENT} últimos`},
 ja:{settings:'制作設定（枚数・ビジュアルの方向・言語・Fast モード）',all:count=>`${count} 件すべて表示`,fewer:`最新 ${RECENT} 件のみ表示`},
};
type Account={signedIn:boolean;admin?:boolean;unlimited?:boolean;remaining?:number|null;online?:boolean;jobs?:Job[]};
/** `after` is placed between the form and the visitor's earlier jobs. */
export default function BriefForm({after}:{after?:React.ReactNode}={}){
 const {locale,t}=useLanguage();const u=uploadMessages[locale];const q=quotaMessages[locale];
 const [attachments,setAttachments]=useState<File[]>([]);
 const [mode,setMode]=useState<TaskMode>('create');const m=taskModeMessages[locale];
 const ew=executionWords[locale];
 const [account,setAccount]=useState<Account|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState(false),[busy,setBusy]=useState(false);
 const [pptOverride,setPptOverride]=useState<Locale|null>(null);
 const [pageInput,setPageInput]=useState('10'),[briefText,setBriefText]=useState(''),[titleText,setTitleText]=useState('');
 const [answers,setAnswers]=useState<BriefAnswers>(emptyAnswers);
 const briefValue=mode==='create'?composeBrief(answers,locale):briefText;
 const [modelAccounts,setModelAccounts]=useState<ModelAccount[]>([]),[modelSelection,setModelSelection]=useState<ModelSelection>(null);
 const requestKey=useRef<string|null>(null),formRef=useRef<HTMLFormElement>(null);
 // The title follows the first sentence of the request until the visitor writes their own.
 const [titleEdited,setTitleEdited]=useState(false),[allJobs,setAllJobs]=useState(false),[round,setRound]=useState(0);const w=words[locale];
 const titleValue=titleEdited?titleText:deriveTitle(mode==='create'?answers.request:briefText),bc=briefCopy[locale]||briefCopy.en;
 const languageChoice=resolvePresentationLanguage(titleValue+'\n'+briefValue,locale,pptOverride,mode);const pptLanguage=languageChoice.language;
 const pw=pageCountMessages[locale],pageChoice=resolvePages(mode,Number(pageInput),titleValue+'\n'+briefValue);
 const refresh=useCallback(async()=>{try{const response=await fetch('/api/account',{cache:'no-store'});if(!response.ok)throw Error();setAccount(await response.json());}catch{setError('account');}},[]);
 useEffect(()=>{void refresh();const timer=setInterval(()=>void refresh(),12000);return()=>clearInterval(timer);},[refresh]);
 async function submit(event:React.FormEvent<HTMLFormElement>){event.preventDefault();if(busy)return;if(mode==='create'&&pageChoice.error){setError(pageChoice.error);return;}if(mode==='edit'&&!hasEditableDeck(attachments)){setError('source');return;}setBusy(true);setError('');setNotice(false);const data=new FormData(event.currentTarget);data.set('mode',mode);if(mode==='edit')data.delete('pages');requestKey.current??=crypto.randomUUID();
  data.set('language',pptLanguage);data.set('brief',briefValue);data.set('requestKey',requestKey.current);const fast=data.get('fast')==='true';data.delete('fast');
  try{const uploadIds=await uploadFiles(attachments,`job:${requestKey.current}`,{locale});const payload={...Object.fromEntries(data),pages:mode==='create'?pageChoice.pages:undefined,...(fast?{fast:true}:{}),uploadIds,modelAccount:modelSelection};const response=await fetch('/api/jobs',{method:'POST',headers:{'X-UI-Language':locale,'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json() as {code?:string};if(!response.ok){setError(result.code&&(['upload','source','pagesRange','pagesAmbiguous','execution_backend','execution_backend_locked','model_account'].includes(result.code)||Object.hasOwn(t.errors,result.code))?result.code:'submit');return;}void discardUploads(uploadIds,`job:${requestKey.current}`);requestKey.current=null;formRef.current?.reset();setPageInput('10');setBriefText('');setAnswers(emptyAnswers);setTitleText('');setTitleEdited(false);setRound(value=>value+1);setMode('create');setAttachments([]);setNotice(true);await refresh();}catch{setError('submit');}finally{setBusy(false);}}
 const hasQuota=account?.unlimited===true||(account?.remaining??0)>0;
 const errorText=error==='model_account'?(locale==='zh-CN'?'模型账户不可用，请重新连接或选择其他账户。':'Model account unavailable. Reconnect or select another account.'):error==='execution_backend'?ew.missing:error==='execution_backend_locked'?ew.locked:error==='execution_backend_unavailable'?ew.unavailable:error==='pagesRange'||error==='pagesAmbiguous'?pw[error]:error==='source'?m.missing:error==='quota'&&account?.unlimited?q.full:error==='upload'?u.error:error==='account'?t.accountError:error==='submit'?t.submitError:Object.hasOwn(t.errors,error)?t.errors[error as keyof Messages['errors']]:'';
 const jobs=account?.jobs??[];
 return <><div className="account-bar">{account===null?t.loading:account.signedIn?<><span>{account.unlimited?q.label:<>{t.remaining}: <strong>{account.remaining}</strong> / 10</>}<small>{account.online?t.online:t.offline}</small></span><span className="account-links">{account.admin&&<a href="/admin" title={queueWords[locale].adminHelp}>{queueWords[locale].allTasks}</a>}<a href="/signout-with-chatgpt?return_to=/">{t.signout}</a></span></>:<><span>{t.signinHint}</span><a href="/signin-with-chatgpt?return_to=/">{t.signin}</a></>}</div>
 {account?.signedIn&&<ModelAccounts onAccounts={setModelAccounts} onSelect={setModelSelection}/>}
 <form ref={formRef} onSubmit={submit}><fieldset disabled={busy} className="pad">
 <div className="notes-wall">
  {/* The large sheet: what to make, and what to call it. */}
  <div className="sheet">
   <ModelAccountPicker accounts={modelAccounts} selection={modelSelection} onSelect={setModelSelection}/>
   <div className="pad-row"><label htmlFor="task-mode">{m.label}</label><select id="task-mode" name="mode" value={mode} aria-describedby="mode-help" onChange={e=>{setMode(e.target.value as TaskMode);setError('');setNotice(false);}}><option value="create">{m.create}</option><option value="edit">{m.edit}</option></select></div><p id="mode-help" className="fineprint">{mode==='edit'?m.editHelp:m.createHelp}</p>
   {mode==='edit'?<div className="bf-main"><label htmlFor="brief">{t.brief}</label><textarea id="brief" className="bf-request" name="brief" onChange={e=>setBriefText(e.target.value)} rows={6} required minLength={10} maxLength={12000} placeholder={m.placeholder}/></div>:<BriefFields locale={locale} value={answers} onChange={setAnswers} part="request"/>}
   <div className="pad-row pad-title"><label htmlFor="title">{t.title}</label><textarea id="title" name="title" rows={1} value={titleValue} onChange={e=>{const value=e.target.value.replace(/\n/g,' ');setTitleText(value);setTitleEdited(value!=='');}} required maxLength={120} placeholder={t.titlePlaceholder} aria-describedby="title-help"/></div><p id="title-help" className="fineprint">{bc.titleAuto}</p>
  </div>
  {/* One sticky note per question; `round` clears the added ones after a brief is sent. */}
  {mode==='create'&&<BriefFields key={round} locale={locale} value={answers} onChange={setAnswers} part="notes"/>}
  <FileUpload files={attachments} onChange={setAttachments} title={mode==='edit'?sourceFileLabels[locale]:undefined}/>
 </div>
 <details className="pad-settings"><summary>{w.settings}</summary>
 <div className="fields">
  <div>{mode==='create'?<><label htmlFor="pages">{m.pages}</label><input id="pages" name="pages" type="number" inputMode="numeric" min={1} max={MAX_SLIDES} step={1} required disabled={pageChoice.source==='brief'} value={pageChoice.source==='brief'&&pageChoice.pages!==null?String(pageChoice.pages):pageInput} onChange={e=>setPageInput(e.target.value)} aria-describedby="pages-help pages-resolved"/><div className="pad-help"><p id="pages-help" className="fineprint">{pw.help}</p><p id="pages-resolved" className="fineprint" role="status" aria-live="polite">{pageChoice.error?pw[pageChoice.error]:pageChoice.source==='brief'?pw.fromBrief(pageChoice.pages!):pw.fromInput(pageChoice.pages!)}</p></div></>:<p className="fineprint" role="status">{m.automatic}</p>}</div>
  <div><label htmlFor="style">{t.style}</label><select id="style" name="style">{styleValues.map((v,i)=><option key={v} value={v}>{t.styles[i]}</option>)}</select></div>
  <div><label htmlFor="ppt-language">{t.pptLanguage}</label><select id="ppt-language" name="language" value={pptLanguage} aria-describedby="language-help" onChange={e=>{if(isLocale(e.target.value))setPptOverride(e.target.value);}}>{Object.entries(languages).map(([code,name])=><option key={code} value={code} lang={code}>{name}</option>)}</select><div className="pad-help"><p id="language-help" className="fineprint">{t.languageHelp}</p><p className="fineprint" role="status" aria-live="polite">{languageResolutionMessages[locale][languageChoice.source]}: <strong lang={pptLanguage}>{languages[pptLanguage]}</strong></p></div></div>
 </div>
 <label className="fast-toggle" htmlFor="fast-mode"><input id="fast-mode" name="fast" type="checkbox" value="true" aria-describedby="fast-help"/><span>{ew.fast}</span></label><p id="fast-help" className="fineprint">{ew.fastHelp}</p>
 </details>
 {mode==='create'&&<BriefFields locale={locale} value={answers} onChange={setAnswers} part="summary"/>}
 <button className="nb-submit" disabled={busy||!account?.signedIn||!hasQuota}>{busy?(attachments.length?u.uploading:t.submitting):!account?.signedIn?t.loginFirst:!hasQuota?t.exhausted:account.unlimited?q.submit:t.submit}</button>
 <p className="fineprint">{account?.unlimited?q.note:t.quotaNote}</p><p role="alert" className="error">{errorText}</p><p role="status" className="success">{notice?(account?.unlimited?q.submitted:t.submitted):''}</p>
 </fieldset></form>
 {after}
 {/* Earlier jobs hang on the wall the way the finished decks do: the first slide where there is one, a blank sheet with the status where there is not. */}
 {account?.signedIn&&<section className="history"><h2>{t.history}</h2>{!jobs.length?<p className="fineprint">{t.empty}</p>:<div className="job-wall">{(allJobs?jobs:jobs.slice(0,RECENT)).map(job=>{
  const status=Object.hasOwn(t.statuses,job.status)?t.statuses[job.status as keyof Messages['statuses']]:t.unknownStatus;
  return <article key={job.id} className="job-print" data-status={job.status}>
   <a className="job-cover" href={`/jobs/${job.id}`} aria-label={`${t.details} · ${job.title}`}><span className="job-blank">{status}</span>{(job.download||job.status==='running')&&<img src={`/api/jobs/${job.id}/preview/1`} alt="" loading="lazy" onError={event=>{event.currentTarget.hidden=true;}}/>}</a>
   <div className="job-heading"><h3>{job.title}</h3><span className={`status status-${job.status}`}>{status}</span></div>
   <p>{new Date(job.created_at).toLocaleString(locale)}{account.admin&&<> · {executionLabel(job.execution_backend,locale)}</>}{isLocale(job.language)&&<> · {t.pptLanguage}: <span lang={job.language}>{languages[job.language]}</span></>}</p>
   {job.modelAccount&&<p className="fineprint">{locale==='zh-CN'?'使用你的 API 账户':'Your API account'} · {job.modelAccount.model}</p>}
   {job.summary&&<p>{displaySummary(job.summary,t)}</p>}
   {!!job.attachments?.length&&<p className="fineprint">{u.references} · {job.attachments.length}</p>}
   <p className="job-links"><a className="download" href={`/jobs/${job.id}`}>{t.details}</a>{job.download&&<a className="download" href={`/api/jobs/${job.id}/download`}>{t.download}</a>}</p>
  </article>;})}</div>}{jobs.length>RECENT&&<button type="button" className="history-more" aria-expanded={allJobs} onClick={()=>setAllJobs(value=>!value)}>{allJobs?w.fewer:w.all(jobs.length)}</button>}</section>}
 </>;
}
