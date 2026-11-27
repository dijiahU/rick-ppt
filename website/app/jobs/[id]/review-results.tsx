'use client';
import {useEffect,useRef,useState} from 'react';
import {useLanguage} from '@/app/language';
import {reviewWords} from '@/lib/review-i18n';
import type {Progress} from '@/lib/progress';
import type {PublicReview,ReviewPage} from '@/lib/review-results';

export function ReviewStatus({progress,onOpen}:{progress:Progress|null;onOpen:()=>void}){
 const {locale}=useLanguage(),w=reviewWords[locale]||reviewWords.en;
 return <div className="review-status" aria-label={w.title}><div>{(['content','visual'] as const).map(kind=>{const state=progress?.reviews?.[kind]||'pending';return <span key={kind} data-state={state}><strong>{kind==='content'?w.contentEvidence:w.visual}</strong> · {w.states[state]}</span>;})}</div><button onClick={onOpen}>{w.open}</button></div>;
}

export default function ReviewResults({id,status,updatedAt,active=true}:{id:string;status:string;updatedAt?:number;active?:boolean}){
 const {locale}=useLanguage(),w=reviewWords[locale]||reviewWords.en;
 const [reports,setReports]=useState<PublicReview[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(false),[refresh,setRefresh]=useState(0),[all,setAll]=useState(false);
 const terminal=['complete','failed','paused','delivery_pending'].includes(status);
 const version=terminal?updatedAt??0:null;
 const history=useRef({cursor:0,attempt:null as string|null,collected:new Map<string,PublicReview>(),finished:false,status:'',version:null as number|null,refresh:0});
 useEffect(()=>{
  if(!active)return;
  const state=history.current;
  if(state.finished&&terminal&&state.status===status&&state.version===version&&state.refresh===refresh)return;
  state.status=status;state.version=version;state.refresh=refresh;
  const controller=new AbortController();let timer:ReturnType<typeof setTimeout>,terminalPolls=3;
  setError(false);
  async function poll(){try{
   const response=await fetch(`/api/jobs/${encodeURIComponent(id)}/reviews?after=${state.cursor}`,{cache:'no-store',signal:controller.signal});
   if(!response.ok)throw Error();const data=await response.json() as ReviewPage;if(controller.signal.aborted)return;
   if(state.attempt!==null&&data.attempt!==state.attempt){
    state.collected.clear();setReports([]);
    if(state.cursor){state.cursor=0;state.attempt=data.attempt;timer=setTimeout(poll,0);return;}
   }
   if(data.nextChunk<state.cursor){state.collected.clear();state.cursor=0;}
   state.attempt=data.attempt;
   for(const report of data.reports)state.collected.set(report.id,report);
   state.cursor=data.nextChunk;
   // Prefer a host-validated, file-bound receipt over its matching legacy copy.
   const values=[...state.collected.values()];
   setReports(values.filter(r=>r.verified||!values.some(v=>v.verified&&v.kind===r.kind&&v.round===r.round&&v.summary===r.summary)).sort((a,b)=>b.at-a.at||Number(b.id)-Number(a.id)));
   const more=state.cursor<data.totalChunks;
   state.finished=!more&&data.finished;setLoading(more&&!state.collected.size);setError(false);
   if(more||(!data.finished&&(!terminal||terminalPolls-->0)))timer=setTimeout(poll,more?0:3000);
  }catch{if(!controller.signal.aborted){state.finished=false;setLoading(false);setError(true);timer=setTimeout(poll,6000);}}}
  void poll();return()=>{controller.abort();clearTimeout(timer);};
 },[id,status,refresh,active,terminal,version]);
 const visible=all?reports:reports.slice(0,4);
 return <section className="review-results" aria-label={w.title}>
  <div className="review-heading"><h2>{w.title}</h2><button onClick={()=>setRefresh(n=>n+1)}>{w.retry}</button></div>
  <p className="fineprint">{w.scope}</p>
  {error&&<p role="alert">{w.error}</p>}
  {loading&&<p role="status">{w.loading}</p>}
  {!loading&&!reports.length&&!error&&<p className="room-empty">{w.waiting}</p>}
  {visible.map((report,index)=><details className="review-report" key={report.id} open={index<2}>
   <summary><span><strong>{report.kind==='visual'?w.visual:report.kind==='content-first'?w.contentFirst:w.contentEvidence}</strong><span className="review-round">{w.round} {report.round}</span></span><span className="review-counts"><span data-severity={report.requiredCount?'required':'clear'}>{w.required} {report.requiredCount}</span><span>{w.suggestions} {report.suggestionCount}</span></span></summary>
   <div className="review-report-body"><p className="review-summary">{report.summary}</p>
    <p className="review-meta"><time dateTime={new Date(report.at).toISOString()}>{w.recorded} · {new Date(report.at).toLocaleString(locale)}</time><span>{report.verified?`${w.candidate} ${report.artifactSha256!.slice(0,12)} · rev ${report.revision}`:w.legacy}</span></p>
    <p className="fineprint">{w.coverage} · {report.pagesReviewed.join(', ')}</p>
    {report.truncated&&<p className="fineprint">{w.truncated}</p>}
    {!report.requiredCount&&<p className="review-clear">{w.none}</p>}
    <ol className="review-findings">{report.findings.map((finding,n)=><li key={finding.id+'-'+n} data-severity={finding.severity}><div className="review-finding-heading"><strong>{finding.severity==='required'?w.required:w.suggestions}</strong><span>{w.pages} {finding.pages.join(', ')}</span></div><p>{finding.observation}</p>{finding.impact&&<p><strong>{w.impact}: </strong>{finding.impact}</p>}<p><strong>{w.recommendation}: </strong>{finding.recommendation}</p></li>)}</ol>
    {!!report.limitations.length&&<div className="review-limits"><h3>{w.limitations}</h3><ul>{report.limitations.map((limit,n)=><li key={n}>{limit}</li>)}</ul></div>}
   </div>
  </details>)}
  {reports.length>4&&<button className="review-history" onClick={()=>setAll(v=>!v)} aria-expanded={all}>{all?w.less:`${w.more} (${reports.length-4})`}</button>}
 </section>;
}
