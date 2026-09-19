export type TaskMode='create'|'edit';
import {MAX_SLIDES} from './slide-limits.mjs';
export {MAX_SLIDES};
// Existing jobs.pages is NOT NULL. Zero is reserved for task-dependent editing,
// never a target of zero slides. Worker payloads expose null plus mode;
// record UIs render zero as task-dependent instead of a numeric slide count.
export function taskScope(pages:number){return {mode:pages===0?'edit' as const:'create' as const,pages:pages===0?null:pages};}
type PageResolution={pages:number|null;source:'brief'|'input'|'edit';error?:'pagesRange'|'pagesAmbiguous'};
function numericCount(value:string):number{
 if(/^\d+$/.test(value))return Number(value);
 const digits:Record<string,number>={'零':0,'〇':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9};
 let total=0,current=0;
 for(const ch of value){if(ch in digits)current=digits[ch];else {total+=(current||1)*(ch==='十'?10:100);current=0;}}
 return total+current;
}
// Extract explicit deck sizes, not individual slide references or source lengths.
// Conflicting exact counts and ranges require clarification before admission.
export function briefPageCounts(brief:string):number[]{
 const text=brief.normalize('NFKC');const counts:number[]=[];
 const number='[0-9]+|[零〇一二两三四五六七八九十百]+';
 const pattern=new RegExp(`(${number})\\s*[-–]?\\s*(页|張|张|枚|slides?\\b|pages?\\b|diapositiv[ae]s?\\b)`,'gi');
 for(const match of text.matchAll(pattern)){
  const start=match.index!;const before=text.slice(0,start).split(/[。！!？?；;\n，,]/).at(-1)??'';
  const after=text.slice(start+match[0].length,start+match[0].length+20);
  if(/[张張]/.test(match[2])&&!/^\s*(?:的)?\s*(?:ppt|幻灯片|投影片|slides?)/i.test(after))continue;
  if(match[2]==='枚'&&/^\s*(?:の)?\s*(?:写真|画像|イラスト)/.test(after))continue;
  if(/第\s*$/.test(before)||/第\s*[\d一二三四五六七八九十]+\s*页\s*(?:到|至|[-–~～])\s*$/.test(before))continue;
  if(/\d\.\s*$/.test(before)){counts.push(NaN);continue;}
  if(/(?:^|[^\d])[-−]\s*$/.test(before)){counts.push(-numericCount(match[1]));continue;}
  if(/^\s*(?:到|至|[-–~～])\s*[\d一二三四五六七八九十]/.test(after)){counts.push(NaN);continue;}
  if(/(?:不要|不用|并非|不是|not|instead of)\s*$/i.test(before))continue;
  if(/(?:至少|最多|不超过|不少于|不多于|以内|at least|at most|up to)\s*$/i.test(before)||/^\s*(?:以内|以上|以下)/.test(after)){counts.push(NaN);continue;}
  if(/(?:\d|[一二三四五六七八九十])\s*(?:页|slides?)?\s*(?:[-–~～]|到|至|or|to)\s*$/i.test(before)){counts.push(NaN);continue;}
  const target=/(?:做|制作|生成|创建|输出|准备|需要|总共|总计|共|合计|全篇|整份|整套|控制在|改为|改成|调整为|要|create|make|generate|produce|prepare|total|exactly)\s*(?:一份|一个|一套|份|个|套|为|是|:|：|a|an|of)?\s*$/i.test(before);
  if(!target&&(/(?:参考|资料|文献|原文|原稿|附件|pdf|教材|书籍|source|reference|document|report|book|chapter|section|per|each|每|章节|部分|封面|结尾|目录|附录|正文|引言)/i.test(before)||/^\s*(?:的)?\s*(?:资料|文献|原文|教材|书籍|文档|pdf|report|document|book)/i.test(after)))continue;
  counts.push(numericCount(match[1]));
 }
 for(const match of text.matchAll(new RegExp(`(?:总页数|页数|slide\\s*count|nombre de diapositives|número de diapositivas)\\s*[:：=为是]?\\s*(${number})(?![\\d页])`,'gi')))counts.push(numericCount(match[1]));
 return [...new Set(counts)];
}
export function resolvePages(mode:unknown,pages:unknown,brief:unknown=''):PageResolution{
 if(mode==='edit')return {pages:0,source:'edit'};
 if(mode!==undefined&&mode!=='create')return {pages:null,source:'input',error:'pagesRange'};
 const counts=typeof brief==='string'?briefPageCounts(brief):[];
 if(counts.length>1||counts.some(Number.isNaN))return {pages:null,source:'brief',error:'pagesAmbiguous'};
 const value=counts.length?counts[0]:pages;const source=counts.length?'brief':'input';
 if(typeof value!=='number'||!Number.isSafeInteger(value)||value<1||value>MAX_SLIDES)return {pages:null,source,error:'pagesRange'};
 return {pages:value,source};
}
export function requestedPages(mode:unknown,pages:unknown,brief:unknown=''):number|null{return resolvePages(mode,pages,brief).pages;}
export function hasEditableDeck(uploads:{name:string}[]){return uploads.filter(f=>f.name.toLowerCase().endsWith('.pptx')).length===1;}
export const editInstruction='TASK MODE: EDIT EXISTING PPTX. Inspect the uploaded source presentation first. Modify or add slides only as required by the brief; preserve unrelated slides and existing design language unless a redesign is requested. There is no target slide count: pages=null means task-dependent, not zero or a fixed target. Plan which original slides to modify and where to add slides. Do not rebuild the whole deck from a blank file. Save a new complete PPTX, preserving the uploaded original. Research and reference materials may support the requested changes.';
