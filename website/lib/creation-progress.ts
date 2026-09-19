import {MAX_SLIDES} from './slide-limits.mjs';
import type {Progress} from './progress';
export function progressNotes(progress:Progress|null|undefined){
  return progress?.notes??progress?.events.filter(e=>e.reported)??[];
}
export function pageProgress(progress:Progress|null|undefined,pages:number){
  const notes=progressNotes(progress),previews=progress?.previews??[];
  const total=progress?.outline?.slides.length??pages;
  const numbers=total>0?Array.from({length:Math.min(total,MAX_SLIDES)},(_,i)=>i+1):
    [...new Set([...previews,...notes.flatMap(e=>e.slide?[e.slide]:[])])].sort((a,b)=>a-b);
  return numbers.map(slide=>({slide,preview:previews.includes(slide),note:notes.findLast(e=>e.slide===slide),outline:progress?.outline?.slides[slide-1]}));
}
export function previewVersion(progress:Progress,slide:number){
  return progress.previewVersions?.[String(slide)]??String(progress.updatedAt);
}
