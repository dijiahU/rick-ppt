import type {TraceEvent} from './admin-trace';
import {MAX_SLIDES} from './slide-limits.mjs';

export type ReviewFinding={id:string;pages:number[];severity:'required'|'suggestion';observation:string;impact:string;recommendation:string};
export type PublicReview={id:string;at:number;kind:'content-first'|'content-evidence'|'visual';round:number;artifactSha256?:string;revision?:number;verified:boolean;summary:string;pagesReviewed:number[];findings:ReviewFinding[];limitations:string[];requiredCount:number;suggestionCount:number;truncated:boolean};
export type ReviewPage={available:boolean;attempt:string|null;reports:PublicReview[];nextChunk:number;totalChunks:number;finished:boolean};
function clean(value:unknown,max:number):string|null{
 if(typeof value!=='string'||value.length>max)return null;
 return value.replace(/\b(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=:-]+/gi,'[redacted]').replace(/\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{15,}|github_pat_[A-Za-z0-9_]{15,})/g,'[redacted]').replace(/(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|authorization)\b["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;}]+)/gi,'$1[redacted]').replace(/(?:\/Users\/|\/private\/|\/tmp\/|[A-Z]:\\)[^\s"'<>]*/g,'[local file]');
}
function pages(value:unknown):number[]|null{
 return Array.isArray(value)&&value.length<=MAX_SLIDES&&value.every(n=>Number.isInteger(n)&&n>=1&&n<=MAX_SLIDES)&&new Set(value).size===value.length?value:null;
}
// Only final structured reports cross the user boundary. No commands, raw
// assistant messages, private reasoning, transport receipts or local paths.
export function publicReview(event:TraceEvent):PublicReview|null{
 if(event.truncated||!event.detail)return null;
 const stage=/^(content-first|content-evidence|visual)-(\d+)$/.exec(event.stage);
 const envelope=event.kind==='review'&&event.label==='Validated review result';
 if(!envelope&&(!stage||!((event.kind==='note'&&event.label==='Assistant update')||(event.kind==='review'&&event.label==='Stage result'))))return null;
 let value;try{value=JSON.parse(event.detail.trim().replace(/^```(?:json)?\s*([\s\S]*?)\s*```$/,'$1'));}catch{return null;}
 if(!value||typeof value!=='object'||Array.isArray(value))return null;
 const verified=envelope&&value.schema==='rickppt-review/v1';
 if(envelope&&!verified)return null;
 const report=verified?value.report:value;
 const kind=verified?value.kind:stage![1],round=verified?value.round:Number(stage![2]);
 if(!['content-first','content-evidence','visual'].includes(kind)||!Number.isSafeInteger(round)||round<1||round>100)return null;
 if(verified&&(!/^[a-f0-9]{64}$/.test(value.artifactSha256)||!Number.isSafeInteger(value.revision)||value.revision<0))return null;
 if(!report||typeof report!=='object')return null;
 const summary=clean(report.summary,5000),reviewed=pages(report.pages_reviewed);
 if(!summary?.trim()||!reviewed?.length||!Array.isArray(report.findings)||report.findings.length>100||!Array.isArray(report.limitations)||report.limitations.length>30)return null;
 const findings:ReviewFinding[]=[];const limitations:string[]=[];
 for(const finding of report.findings){
  if(!finding||!['required','suggestion'].includes(finding.severity))return null;
  const p=pages(finding.pages),observation=clean(finding.observation,6000),impact=clean(finding.impact,4000),recommendation=clean(finding.recommendation,6000),id=clean(finding.id,100);
  if(!p?.length||!observation?.trim()||impact===null||!recommendation?.trim()||!id)return null;
  findings.push({id,pages:p,severity:finding.severity,observation,impact,recommendation});
 }
 for(const item of report.limitations){const text=clean(item,4000);if(text===null)return null;limitations.push(text);}
 const required=findings.filter(f=>f.severity==='required').length,suggestions=findings.length-required;
 if(verified&&(!Number.isSafeInteger(value.requiredCount)||value.requiredCount<required||value.requiredCount>1000||!Number.isSafeInteger(value.suggestionCount)||value.suggestionCount<suggestions||value.suggestionCount>1000))return null;
 return {id:String(event.seq),at:event.at,kind,round,verified,...(verified?{artifactSha256:value.artifactSha256,revision:value.revision}:{}),summary,pagesReviewed:reviewed,findings,limitations,requiredCount:verified?value.requiredCount:required,suggestionCount:verified?value.suggestionCount:suggestions,truncated:verified&&value.truncated===true};
}
