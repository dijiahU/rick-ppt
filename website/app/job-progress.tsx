'use client';
import {useEffect,useState} from 'react';
import {type Progress} from '@/lib/progress';
import {useLanguage} from './language';
import ActivityTimeline from './activity-timeline';
type State={status:string;updatedAt:number;progress:Progress|null};
export default function JobProgress({id,status}:{id:string;status:string}) {
 const {locale,t}=useLanguage();
 const [data,setData]=useState<State|null>(null),[error,setError]=useState(false);
 useEffect(()=>{let active=true;let timer:ReturnType<typeof setTimeout>;
  async function poll(){try{const r=await fetch(`/api/jobs/${id}/progress`,{cache:'no-store'});if(!r.ok)throw Error();const value=await r.json() as State;if(!active)return;setData(value);setError(false);if(!['complete','failed'].includes(value.status))timer=setTimeout(poll,5000);}catch{if(active){setError(true);timer=setTimeout(poll,10000);}}}
  void poll();return()=>{active=false;clearTimeout(timer);};
 },[id,status]);
 const progress=data?.progress;
 return <div className="job-progress"><p className="progress-caption">{t.progressCaption}</p>
 {error&&<p role="status">{t.progressError}</p>}
 {!progress?.events.length?<p>{status==='queued'?t.waiting:t.noProgress}</p>:<>
 <p aria-live="polite">{data?.status==='complete'?t.delivered:data?.status==='failed'?t.stopped:t.activities[progress.events[progress.events.length-1].code]}</p>
 {progress.events[progress.events.length-1].detail&&<p>{progress.events[progress.events.length-1].detail}</p>}
 <p>{t.synced}: {new Date(progress.updatedAt).toLocaleTimeString(locale)} · {t.syncNote}</p>
 <ActivityTimeline events={progress.events}/>
 </>}
 {!!progress?.previews.length&&<><p>{t.previews}</p><div className="preview-grid">{progress.previews.map(slide=><a key={slide} href={`/api/jobs/${id}/preview/${slide}?v=${progress.updatedAt}`} target="_blank" rel="noreferrer"><img src={`/api/jobs/${id}/preview/${slide}?v=${progress.updatedAt}`} alt={`${t.slide} ${slide} · ${t.preview}`} loading="lazy"/><span>{t.slide} {slide} ↗</span></a>)}</div></>}
 <p className="fineprint">{t.privacy}</p></div>;
}
