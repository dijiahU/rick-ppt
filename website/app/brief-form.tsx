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
import ModelAccounts,{ModelAccountPicker,type ModelSelection} from './model-accounts';
import type {ModelAccount} from '@/lib/model-providers';
import AttachmentPreviews from './attachment-previews';
import {uploadFiles,discardUploads} from '@/lib/upload-client';
import {uploadMessages} from '@/lib/upload-i18n';
import type {Attachment} from '@/lib/attachments';
import {useLanguage} from './language';
import {resolvePresentationLanguage,languageResolutionMessages} from '@/lib/presentation-language';
import {displaySummary,isLocale,languages,styleValues,type Locale,type Messages} from '@/lib/i18n';
type Job={id:string;title:string;status:string;created_at:number;summary:string|null;download:boolean;language:Locale|null;execution_backend:ExecutionBackend|null;attachments:Attachment[];modelAccount?:{provider:string;model:string}};
type Account={signedIn:boolean;admin?:boolean;unlimited?:boolean;remaining?:number|null;online?:boolean;jobs?:Job[]};
export default function BriefForm(){
 const {locale,t}=useLanguage();const u=uploadMessages[locale];const q=quotaMessages[locale];
 const [attachments,setAttachments]=useState<File[]>([]);
 const [mode,setMode]=useState<TaskMode>('create');const m=taskModeMessages[locale];
 const ew=executionWords[locale];
 const [account,setAccount]=useState<Account|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState(false),[busy,setBusy]=useState(false);
 const [pptOverride,setPptOverride]=useState<Locale|null>(null);
 const [pageInput,setPageInput]=useState('10'),[briefText,setBriefText]=useState(''),[titleText,setTitleText]=useState('');
 const languageChoice=resolvePresentationLanguage(titleText+'\n'+briefText,locale,pptOverride,mode);const pptLanguage=languageChoice.language;
 const pw=pageCountMessages[locale],pageChoice=resolvePages(mode,Number(pageInput),titleText+'\n'+briefText);
 const [modelAccounts,setModelAccounts]=useState<ModelAccount[]>([]),[modelSelection,setModelSelection]=useState<ModelSelection>(null);
 const requestKey=useRef<string|null>(null),formRef=useRef<HTMLFormElement>(null);
 const refresh=useCallback(async()=>{try{const response=await fetch('/api/account',{cache:'no-store'});if(!response.ok)throw Error();setAccount(await response.json());}catch{setError('account');}},[]);
 useEffect(()=>{void refresh();const timer=setInterval(()=>void refresh(),12000);return()=>clearInterval(timer);},[refresh]);
 async function submit(event:React.FormEvent<HTMLFormElement>){event.preventDefault();if(busy)return;if(mode==='create'&&pageChoice.error){setError(pageChoice.error);return;}if(mode==='edit'&&!hasEditableDeck(attachments)){setError('source');return;}setBusy(true);setError('');setNotice(false);const data=new FormData(event.currentTarget);data.set('mode',mode);if(mode==='edit')data.delete('pages');requestKey.current??=crypto.randomUUID();
  data.set('language',pptLanguage);data.set('requestKey',requestKey.current);
  try{const uploadIds=await uploadFiles(attachments,`job:${requestKey.current}`,{locale});const payload={...Object.fromEntries(data),pages:mode==='create'?pageChoice.pages:undefined,uploadIds,modelAccount:modelSelection};const response=await fetch('/api/jobs',{method:'POST',headers:{'X-UI-Language':locale,'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json() as {code?:string};if(!response.ok){setError(result.code&&(['upload','source','pagesRange','pagesAmbiguous','execution_backend','execution_backend_locked','model_account'].includes(result.code)||Object.hasOwn(t.errors,result.code))?result.code:'submit');return;}void discardUploads(uploadIds,`job:${requestKey.current}`);requestKey.current=null;formRef.current?.reset();setPageInput('10');setBriefText('');setTitleText('');setMode('create');setAttachments([]);setNotice(true);await refresh();}catch{setError('submit');}finally{setBusy(false);}}
 const hasQuota=account?.unlimited===true||(account?.remaining??0)>0;
 const errorText=error==='model_account'?(locale==='zh-CN'?'模型账户不可用，请重新连接或选择其他账户。':'Model account unavailable. Reconnect or select another account.'):error==='execution_backend'?ew.missing:error==='execution_backend_locked'?ew.locked:error==='execution_backend_unavailable'?ew.unavailable:error==='pagesRange'||error==='pagesAmbiguous'?pw[error]:error==='source'?m.missing:error==='quota'&&account?.unlimited?q.full:error==='upload'?u.error:error==='account'?t.accountError:error==='submit'?t.submitError:Object.hasOwn(t.errors,error)?t.errors[error as keyof Messages['errors']]:'';
 return <><div className="account-bar">{account===null?t.loading:account.signedIn?<><span>{account.unlimited?q.label:<>{t.remaining}: <strong>{account.remaining}</strong> / 10</>}</span><a href="/signout-with-chatgpt?return_to=/">{t.signout}</a></>:<><span>{t.signinHint}</span><a href="/signin-with-chatgpt?return_to=/">{t.signin}</a></>}</div>
 {account?.admin&&<aside className="admin-shortcut"><a href="/admin">{queueWords[locale].allTasks} ↗</a><p>{queueWords[locale].adminHelp}</p></aside>}
 {account?.signedIn&&<p className="fineprint">{account.online?t.online:t.offline}</p>}
 {account?.signedIn&&<ModelAccounts onAccounts={setModelAccounts} onSelect={setModelSelection}/>}
 <form ref={formRef} onSubmit={submit}><fieldset disabled={busy}>
 <ModelAccountPicker accounts={modelAccounts} selection={modelSelection} onSelect={setModelSelection}/>
 <label htmlFor="task-mode">{m.label}</label><select id="task-mode" name="mode" value={mode} aria-describedby="mode-help" onChange={e=>{setMode(e.target.value as TaskMode);setError('');setNotice(false);}}><option value="create">{m.create}</option><option value="edit">{m.edit}</option></select><p id="mode-help" className="fineprint">{mode==='edit'?m.editHelp:m.createHelp}</p>
 <label htmlFor="title">{t.title}</label><input id="title" name="title" onChange={e=>setTitleText(e.target.value)} required maxLength={120} placeholder={t.titlePlaceholder}/><label htmlFor="brief">{t.brief}</label><textarea id="brief" name="brief" onChange={e=>setBriefText(e.target.value)} rows={6} required minLength={10} maxLength={12000} placeholder={mode==='edit'?m.placeholder:t.briefPlaceholder}/><div className="fields"><div>{mode==='create'?<><label htmlFor="pages">{m.pages}</label><input id="pages" name="pages" type="number" inputMode="numeric" min={1} max={MAX_SLIDES} step={1} required disabled={pageChoice.source==='brief'} value={pageChoice.source==='brief'&&pageChoice.pages!==null?String(pageChoice.pages):pageInput} onChange={e=>setPageInput(e.target.value)} aria-describedby="pages-help pages-resolved"/><p id="pages-help" className="fineprint">{pw.help}</p><p id="pages-resolved" className="fineprint" role="status" aria-live="polite">{pageChoice.error?pw[pageChoice.error]:pageChoice.source==='brief'?pw.fromBrief(pageChoice.pages!):pw.fromInput(pageChoice.pages!)}</p></>:<p className="fineprint" role="status">{m.automatic}</p>}</div><div><label htmlFor="style">{t.style}</label><select id="style" name="style">{styleValues.map((v,i)=><option key={v} value={v}>{t.styles[i]}</option>)}</select></div></div>
 <label htmlFor="ppt-language">{t.pptLanguage}</label><select id="ppt-language" name="language" value={pptLanguage} aria-describedby="language-help" onChange={e=>{if(isLocale(e.target.value))setPptOverride(e.target.value);}}>{Object.entries(languages).map(([code,name])=><option key={code} value={code} lang={code}>{name}</option>)}</select><p id="language-help" className="fineprint">{t.languageHelp}</p>
 <FileUpload files={attachments} onChange={setAttachments} title={mode==='edit'?sourceFileLabels[locale]:undefined}/>
 <p className="fineprint" role="status" aria-live="polite">{languageResolutionMessages[locale][languageChoice.source]}: <strong lang={pptLanguage}>{languages[pptLanguage]}</strong></p>
 <button disabled={busy||!account?.signedIn||!hasQuota}>{busy?(attachments.length?u.uploading:t.submitting):!account?.signedIn?t.loginFirst:!hasQuota?t.exhausted:account.unlimited?q.submit:t.submit}</button></fieldset><p className="fineprint">{account?.unlimited?q.note:t.quotaNote}</p><p role="alert" className="error">{errorText}</p><p role="status" className="success">{notice?(account?.unlimited?q.submitted:t.submitted):''}</p></form>
 {account?.signedIn&&<section className="history"><p className="eyebrow">{t.private}</p><h2>{t.history}</h2>{!account.jobs?.length?<p className="fineprint">{t.empty}</p>:account.jobs.map(job=><article key={job.id}><div className="job-heading"><h3>{job.title}</h3><span className={`status status-${job.status}`}>{Object.hasOwn(t.statuses,job.status)?t.statuses[job.status as keyof Messages['statuses']]:t.unknownStatus}</span></div><p>{new Date(job.created_at).toLocaleString(locale)}{account.admin&&<> · {executionLabel(job.execution_backend,locale)}</>}{isLocale(job.language)&&<> · {t.pptLanguage}: <span lang={job.language}>{languages[job.language]}</span></>}</p>{job.modelAccount&&<p className="fineprint">{locale==='zh-CN'?'使用你的 API 账户':'Your API account'} · {job.modelAccount.model}</p>}{job.summary&&<p>{displaySummary(job.summary,t)}</p>}{!!job.attachments?.length&&<div className="reference-files"><p className="fineprint">{u.references}</p><AttachmentPreviews files={job.attachments} hrefFor={file=>`/api/jobs/${job.id}/attachments/${file.id}`}/></div>}<p><a className="download" href={`/jobs/${job.id}`}>{t.details} →</a></p>{job.download&&<a className="download" href={`/api/jobs/${job.id}/download`}>{t.download}</a>}</article>)}</section>}
 </>;
}
