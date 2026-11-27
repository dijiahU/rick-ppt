'use client';
import {useId,useState} from 'react';
import type {Locale} from '@/lib/i18n';
import {briefCopy,composeBrief,missingFields,purposeText,type BriefAnswers} from '@/lib/brief-fields';

/** Questions a visitor may add: each is a note peeled from the pad and stuck beside the others. */
const EXTRA=['audience','familiarity','outcome','include','avoid'] as const;
type Extra=typeof EXTRA[number];
const LIMIT:Record<Extra,number>={audience:300,familiarity:0,outcome:400,include:1500,avoid:1500};
const Icon=({d}:{d:string})=><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d={d}/></svg>;

function Choices({name,label,options,value,onChange,required,mark,other,help}:{name:string;label:string;options:string[];value:string;onChange:(v:string)=>void;required?:boolean;mark:string;other?:string;help?:string}){
 return <fieldset className="bf-question"><legend>{label}<span className="bf-mark">{mark}</span></legend>
  <div className="bf-choices">
   {options.map(o=><label key={o} className="bf-chip"><input type="radio" name={name} value={o} checked={value===o} onChange={()=>onChange(o)} required={required}/><span>{o}</span></label>)}
   {other&&<label className="bf-chip"><input type="radio" name={name} value="other" checked={value==='other'} onChange={()=>onChange('other')}/><span>{other}</span></label>}
  </div>
  {help&&<p className="bf-help">{help}</p>}
 </fieldset>;
}

/**
 * The brief is pinned to the wall in pieces. `part` renders one of them:
 *   request — the main entry, written on the large sheet;
 *   notes   — one sticky note per question: the two that must be answered, any the visitor adds, and the pad to add more;
 *   summary — what will be sent, and what is still missing.
 */
export default function BriefFields({locale,value,onChange,part}:{locale:Locale;value:BriefAnswers;onChange:(v:BriefAnswers)=>void;part:'request'|'notes'|'summary'}){
 const c=briefCopy[locale]||briefCopy.en,id=useId();
 const [added,setAdded]=useState<Extra[]>([]);
 const set=<K extends keyof BriefAnswers>(k:K)=>(v:BriefAnswers[K])=>onChange({...value,[k]:v});
 if(part==='request')return <div className="bf-main">
  <label htmlFor={`${id}-request`}>{c.request}<span className="bf-mark">{c.required}</span></label>
  <textarea id={`${id}-request`} className="bf-request" rows={6} value={value.request} onChange={e=>set('request')(e.target.value)} placeholder={c.requestPlaceholder} maxLength={6000} required minLength={6} aria-describedby={`${id}-request-help`}/>
  <p id={`${id}-request-help`} className="bf-help">{c.requestHelp}</p>
 </div>;
 if(part==='summary'){const missing=missingFields(value,c);return <>
  <details className="bf-preview"><summary>{c.preview}</summary><pre>{composeBrief(value,locale)}</pre></details>
  {missing.length>0&&<p className="bf-missing" role="status" aria-live="polite">{c.missing}{missing.join(locale==='zh-CN'||locale==='ja'?'、':', ')}</p>}
 </>;}
 const label:Record<Extra,string>={audience:c.audience,familiarity:c.familiarity,outcome:c.outcome,include:c.include,avoid:c.avoid};
 const hint:Record<Extra,string>={audience:c.audiencePlaceholder,familiarity:'',outcome:c.outcomePlaceholder,include:c.includePlaceholder,avoid:c.avoidPlaceholder};
 // A note is on the wall once the visitor has taken it from the pad or written on it.
 const shown=EXTRA.filter(key=>added.includes(key)||value[key].trim()!==''),spare=EXTRA.filter(key=>!shown.includes(key));
 function peel(key:Extra){setAdded(old=>old.filter(item=>item!==key));onChange({...value,[key]:''});}
 return <div className="brief-fields">
  <div className="sticky" data-filled={purposeText(value)?true:undefined}>
   <Choices name={`${id}-purpose`} label={c.purpose} options={c.purposes} value={value.purpose} onChange={set('purpose')} required mark={c.required} other={c.other}/>
   {value.purpose==='other'&&<input className="bf-other" aria-label={c.other} value={value.purposeOther} onChange={e=>set('purposeOther')(e.target.value)} placeholder={c.otherPlaceholder} maxLength={120} required/>}
  </div>
  <div className="sticky" data-filled={value.viewing?true:undefined}>
   <Choices name={`${id}-viewing`} label={c.viewing} options={c.viewings} value={value.viewing} onChange={set('viewing')} required mark={c.required} help={c.viewingHelp}/>
  </div>
  {shown.map(key=><div key={key} className="sticky is-extra" data-filled={value[key].trim()?true:undefined}>
   <button type="button" className="sticky-off" aria-label={`${c.remove} · ${label[key]}`} title={c.remove} onClick={()=>peel(key)}><Icon d="M6 6l12 12M18 6 6 18"/></button>
   {key==='familiarity'?<Choices name={`${id}-familiarity`} label={c.familiarity} options={c.familiarities} value={value.familiarity} onChange={set('familiarity')} mark=""/>
    :<div className="bf-question"><label htmlFor={`${id}-${key}`}>{label[key]}</label><textarea id={`${id}-${key}`} rows={2} value={value[key]} onChange={e=>set(key)(e.target.value.replace(/\n/g,' '))} placeholder={hint[key]} maxLength={LIMIT[key]} autoFocus={added.includes(key)&&!value[key]}/></div>}
  </div>)}
  {spare.length>0&&<div className="note-pad"><p>{c.more}</p>{spare.map(key=><button type="button" key={key} onClick={()=>setAdded(old=>[...old,key])}><Icon d="M12 5v14M5 12h14"/>{label[key]}</button>)}</div>}
 </div>;
}
