'use client';
import {useId} from 'react';
import type {Locale} from '@/lib/i18n';
import {briefCopy,composeBrief,missingFields,type BriefAnswers} from '@/lib/brief-fields';

function Choices({name,label,options,value,onChange,required,mark,other,help}:{name:string;label:string;options:string[];value:string;onChange:(v:string)=>void;required?:boolean;mark:string;other?:string;help?:string}){
 return <fieldset className="bf-question"><legend>{label}<span className="bf-mark">{mark}</span></legend>
  <div className="bf-choices">
   {options.map(o=><label key={o} className="bf-chip"><input type="radio" name={name} value={o} checked={value===o} onChange={()=>onChange(o)} required={required}/><span>{o}</span></label>)}
   {other&&<label className="bf-chip"><input type="radio" name={name} value="other" checked={value==='other'} onChange={()=>onChange('other')}/><span>{other}</span></label>}
  </div>
  {help&&<p className="bf-help">{help}</p>}
 </fieldset>;
}

export default function BriefFields({locale,value,onChange}:{locale:Locale;value:BriefAnswers;onChange:(v:BriefAnswers)=>void}){
 const c=briefCopy[locale]||briefCopy.en,id=useId();
 const set=<K extends keyof BriefAnswers>(k:K)=>(v:BriefAnswers[K])=>onChange({...value,[k]:v});
 const missing=missingFields(value,c);
 return <div className="brief-fields">
  <p className="bf-intro">{c.legend}</p>
  <Choices name={`${id}-purpose`} label={c.purpose} options={c.purposes} value={value.purpose} onChange={set('purpose')} required mark={c.required} other={c.other}/>
  {value.purpose==='other'&&<input className="bf-other" aria-label={c.other} value={value.purposeOther} onChange={e=>set('purposeOther')(e.target.value)} placeholder={c.otherPlaceholder} maxLength={120} required/>}
  <Choices name={`${id}-viewing`} label={c.viewing} options={c.viewings} value={value.viewing} onChange={set('viewing')} required mark={c.required} help={c.viewingHelp}/>
  <div className="bf-question">
   <label htmlFor={`${id}-audience`}>{c.audience}<span className="bf-mark">{c.required}</span></label>
   <input id={`${id}-audience`} value={value.audience} onChange={e=>set('audience')(e.target.value)} placeholder={c.audiencePlaceholder} maxLength={300} required/>
  </div>
  <Choices name={`${id}-familiarity`} label={c.familiarity} options={c.familiarities} value={value.familiarity} onChange={set('familiarity')} mark={c.optional}/>
  <div className="bf-question">
   <label htmlFor={`${id}-outcome`}>{c.outcome}<span className="bf-mark">{c.required}</span></label>
   <input id={`${id}-outcome`} value={value.outcome} onChange={e=>set('outcome')(e.target.value)} placeholder={c.outcomePlaceholder} maxLength={400} required/>
  </div>
  <div className="bf-more">
   <p className="bf-subhead">{c.more}</p>
   <div className="bf-question">
    <label htmlFor={`${id}-own`}>{c.own}</label>
    <textarea id={`${id}-own`} rows={3} value={value.own} onChange={e=>set('own')(e.target.value)} placeholder={c.ownPlaceholder} maxLength={4000} aria-describedby={`${id}-own-help`}/>
    <p id={`${id}-own-help`} className="bf-help">{c.ownHelp}</p>
   </div>
   <div className="bf-pair">
    <div className="bf-question"><label htmlFor={`${id}-include`}>{c.include}</label><input id={`${id}-include`} value={value.include} onChange={e=>set('include')(e.target.value)} placeholder={c.includePlaceholder} maxLength={1500}/></div>
    <div className="bf-question"><label htmlFor={`${id}-avoid`}>{c.avoid}</label><input id={`${id}-avoid`} value={value.avoid} onChange={e=>set('avoid')(e.target.value)} placeholder={c.avoidPlaceholder} maxLength={1500}/></div>
   </div>
   <div className="bf-question">
    <label htmlFor={`${id}-notes`}>{c.notes}</label>
    <textarea id={`${id}-notes`} rows={3} value={value.notes} onChange={e=>set('notes')(e.target.value)} placeholder={c.notesPlaceholder} maxLength={4000}/>
   </div>
  </div>
  <details className="bf-preview"><summary>{c.preview}</summary><pre>{composeBrief(value,locale)}</pre></details>
  {missing.length>0&&<p className="bf-missing" role="status" aria-live="polite">{c.missing}{missing.join(locale==='zh-CN'||locale==='ja'?'、':', ')}</p>}
 </div>;
}
