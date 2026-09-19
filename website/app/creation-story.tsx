'use client';
import {useState} from 'react';
import {useLanguage} from './language';
import PreviewLink from './preview-link';
import type {Progress} from '@/lib/progress';
import {creationWords} from '@/lib/creation-i18n';
import {contentWords} from '@/lib/content-i18n';
import {pageProgress,previewVersion,progressNotes} from '@/lib/creation-progress';

export default function CreationStory({progress,pages,status,base}:{progress:Progress|null;pages:number;status:string;base:string}){
 const {locale,t}=useLanguage(),w=creationWords[locale],c=contentWords(locale);
 const [all,setAll]=useState(false);
 const notes=progressNotes(progress),latest=notes.at(-1),direction=notes.findLast(e=>(e.phase==='design'||e.phase==='planning')&&!e.slide);
 const cards=pageProgress(progress,pages),terminal=['complete','failed'].includes(status);
 const visible=all?notes:notes.slice(-8);
 return <section className="creation-story" aria-label={w.overview}>
  {progress?.outline?<div className="creation-direction creation-outline"><h3>{c.outline}</h3><strong>{progress.outline.title}</strong><p>{progress.outline.purpose}</p>{progress.outline.style&&<details><summary>{c.style}</summary><p>{progress.outline.style}</p></details>}</div>:direction&&<div className="creation-direction"><h3>{w.design}</h3><p>{direction.detail}</p></div>}
  {progress?.reviews&&<div className="creation-reviews" aria-label={c.review}>{(['content','visual'] as const).map(kind=><span key={kind} data-state={progress.reviews![kind]}><strong>{c[kind]}</strong> · {c.states[progress.reviews![kind]]}</span>)}</div>}
  {!terminal&&latest&&<div className="creation-current" aria-live="polite"><p className="eyebrow">{w.current}{latest.slide?` · ${t.slide} ${latest.slide}`:''}</p><p>{latest.detail}</p>{latest.next&&<p className="creation-next"><strong>{w.next}</strong> {latest.next}</p>}</div>}
  <div className="creation-pages-heading"><h3>{w.pages}</h3><span>{progress?.previews.length??0}{pages>0?` / ${pages}`:''} {w.ready}</span></div>
  <p className="fineprint">{w.hint}</p>
  <div className="creation-pages">{cards.map(card=>{
    const current=!terminal&&latest?.slide===card.slide;
    const stage=current&&card.note?.phase?w.phase[card.note.phase]:card.preview?w.ready:w.waiting;
    const content=<><div className="creation-thumbnail">{card.preview&&progress?<img src={`${base}/preview/${card.slide}?v=${previewVersion(progress,card.slide)}`} alt={card.outline?.title??`${t.slide} ${card.slide}`} loading="lazy"/>:<span>{String(card.slide).padStart(2,'0')}</span>}</div><div className="creation-page-caption"><strong>{t.slide} {card.slide}</strong><span>{stage}</span></div>{card.outline&&<div className="creation-page-content">{card.outline.section&&<span className="creation-section">{card.outline.section}</span>}<h4>{card.outline.title}</h4><p>{card.outline.summary}</p></div>}</>;
    return card.preview?<PreviewLink key={card.outline?.id??card.slide} className={`creation-page ${current?'is-current':''}`} href={`${base}/preview/${card.slide}?v=${previewVersion(progress!,card.slide)}`} label={`${t.slide} ${card.slide}`}>{content}</PreviewLink>:<div key={card.outline?.id??card.slide} className={`creation-page is-pending ${current?'is-current':''}`}>{content}</div>;
  })}</div>
  <h3>{w.history}</h3>{!notes.length?<p className="fineprint">{w.empty}</p>:<>
   {notes.length>8&&<button className="creation-expand" onClick={()=>setAll(v=>!v)} aria-expanded={all}>{all?w.less:w.more}</button>}
   <ol className="creation-notes">{visible.map(note=><li key={note.seq}><div className="creation-note-heading"><strong>{note.phase?w.phase[note.phase]:w.overview}{note.slide?` · ${t.slide} ${note.slide}`:''}</strong><time>{new Date(note.at).toLocaleTimeString(locale)}</time></div><p>{note.detail}</p>{note.next&&<p className="creation-next"><strong>{w.next}</strong> {note.next}</p>}</li>)}</ol>
  </>}
 </section>;
}
