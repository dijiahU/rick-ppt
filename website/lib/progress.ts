import {MAX_SLIDES,validSlideKey} from './slide-limits.mjs';
export const activityLabels = {
  started:'本地 Codex 已领取任务', working:'正在设计与制作页面',
  edited:'已完成一次文件编辑', rendering:'正在渲染页面',
  rendered:'页面渲染完成', inspected:'已打开渲染图进行检查',
  checking:'正在独立校验交付文件', uploading:'校验通过，正在上传成品',
} as const;
export type ActivityCode = keyof typeof activityLabels;
export const categories=['search','source','file','command','media','render','note','lifecycle'] as const;
export const phases=['research','planning','design','building','rendering','review'] as const;
export type ActivityEvent={seq:number;at:number;code:ActivityCode;detail?:string;url?:string;category?:typeof categories[number];reported?:boolean;state?:'started'|'completed'|'failed';phase?:typeof phases[number];slide?:number;next?:string};
export type OutlinePage={id:string;title:string;summary:string;section?:string};
export type Outline={revision:string;title:string;purpose:string;style?:string;slides:OutlinePage[]};
export type ReviewState='pending'|'reviewing'|'changes_requested'|'passed'|'unverified';
export type Progress = {updatedAt:number;events:ActivityEvent[];previews:number[];notes?:ActivityEvent[];previewVersions?:Record<string,string>;outline?:Outline;reviews?:{content:ReviewState;visual:ReviewState}};
function text(value:unknown,limit:number):value is string{return typeof value==='string'&&value.trim().length>0&&value.length<=limit;}
export function parseOutline(value:unknown):Outline|null{
 if(!value||typeof value!=='object')return null;
 const o=value as Outline;
 if(typeof o.revision!=='string'||!/^[a-f0-9]{16}$/.test(o.revision)||!text(o.title,200)||!text(o.purpose,1600)||(o.style!==undefined&&!text(o.style,1200))||!Array.isArray(o.slides)||!o.slides.length||o.slides.length>MAX_SLIDES)return null;
 const ids=new Set<string>();const slides:OutlinePage[]=[];
 for(const p of o.slides){
  if(!p||typeof p.id!=='string'||!/^[A-Za-z0-9_-]{1,64}$/.test(p.id)||ids.has(p.id)||!text(p.title,200)||!text(p.summary,2400)||(p.section!==undefined&&!text(p.section,200)))return null;
  ids.add(p.id);slides.push({id:p.id,title:p.title,summary:p.summary,...(p.section?{section:p.section}:{})});
 }
 return {revision:o.revision,title:o.title,purpose:o.purpose,...(o.style?{style:o.style}:{}),slides};
}
export function safeSource(value:unknown):string|undefined {
  if(typeof value!=='string'||value.length>1200)return;
  try{const u=new URL(value);if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.hash)return;
    for(const [key,v] of u.searchParams){if(!['id','v','page','lang','title','article','app','appid','app_id','p'].includes(key)||v.length>200)return;}
    if(u.hostname==='localhost'||!u.hostname.includes('.')||u.hostname.endsWith('.local')||u.hostname.endsWith('.internal')||/^[\d.]+$/.test(u.hostname)||u.hostname.includes(':'))return;
    return u.href;
  }catch{return;}
}
function parseEvents(value:unknown,limit:number):ActivityEvent[]|null {
  if(!Array.isArray(value)||value.length>limit)return null;
  let seq=0;
  for(const e of value){
    if(!e||!Number.isSafeInteger(e.seq)||e.seq<=seq||!Number.isSafeInteger(e.at)||e.at<0||!Object.hasOwn(activityLabels,e.code))return null;
    seq=e.seq;
    if(e.detail!==undefined&&(typeof e.detail!=='string'||e.detail.length>800))return null;
    if(e.category!==undefined&&!categories.includes(e.category))return null;
    if(e.state!==undefined&&!['started','completed','failed'].includes(e.state))return null;
    if(e.phase!==undefined&&!phases.includes(e.phase))return null;
    if(e.slide!==undefined&&(!Number.isInteger(e.slide)||e.slide<1||e.slide>MAX_SLIDES))return null;
    if(e.next!==undefined&&(typeof e.next!=='string'||e.next.length>400))return null;
  }
  return value.map(({seq,at,code,detail,url,reported,state,category,phase,slide,next})=>({seq,at,code,...(detail?{detail}:{}),...(safeSource(url)?{url:safeSource(url)}:{}),...(reported===true?{reported:true}:{}),...(state?{state}:{}),...(category?{category}:{}),...(phase?{phase}:{}),...(slide!==undefined?{slide}:{}),...(next&&reported===true?{next}:{})}));
}
// Only explicit public summaries and allowlisted activity cross the bridge.
export function parseProgress(value:unknown):Progress|null {
  if(!value || typeof value!=='object')return null;
  const p=value as Progress;
  if(!Number.isSafeInteger(p.updatedAt)||p.updatedAt<0||!Array.isArray(p.previews)||p.previews.length>MAX_SLIDES)return null;
  const events=parseEvents(p.events,500);
  const notes=p.notes===undefined?events?.filter(e=>e.reported).slice(-80):parseEvents(p.notes,80);
  if(!events||!notes||notes.some(e=>!e.reported))return null;
  if(p.previews.some(n=>!Number.isInteger(n)||n<1||n>MAX_SLIDES)||new Set(p.previews).size!==p.previews.length)return null;
  const previewVersions:Record<string,string>={};
  if(p.previewVersions!==undefined){
    if(!p.previewVersions||typeof p.previewVersions!=='object'||Array.isArray(p.previewVersions))return null;
    for(const [slide,version] of Object.entries(p.previewVersions)){
      if(!validSlideKey(slide)||!p.previews.includes(Number(slide))||typeof version!=='string'||!/^[a-f0-9]{16}$/.test(version))return null;
      previewVersions[slide]=version;
    }
  }
  const outline=p.outline===undefined?undefined:parseOutline(p.outline);
  if(outline===null)return null;
  let reviews:Progress['reviews'];
  if(p.reviews!==undefined){
    const states=['pending','reviewing','changes_requested','passed','unverified'];
    if(!p.reviews||!states.includes(p.reviews.content)||!states.includes(p.reviews.visual))return null;
    reviews={content:p.reviews.content,visual:p.reviews.visual};
  }
  return {updatedAt:p.updatedAt,events,notes,previews:p.previews,previewVersions,...(outline?{outline}:{}),...(reviews?{reviews}:{})};
}
