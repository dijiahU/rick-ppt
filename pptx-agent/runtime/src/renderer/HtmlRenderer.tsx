import {useEffect,useRef} from 'react';
import type {Dict} from '../core/types';
import type {Runtime} from '../core/runtime';
import {parseCSV} from '../core/data';
export function HtmlRenderer({type,p,runtime,onEvent}:{type:string;p:Dict;runtime:Runtime;onEvent:(type:string,event:any,value?:any)=>void}){
 const media=useRef<HTMLMediaElement>(null),fired=useRef(new Set<number>());
 useEffect(()=>{const el=media.current;if(!el)return;runtime.mediaElements.set(p.id,el);return()=>{runtime.mediaElements.delete(p.id);};},[p.id,runtime]);
 useEffect(()=>{const el=media.current;if(!el)return;try{for(const k of ['currentTime','playbackRate','volume','muted'])if(p[k]!==undefined&&(el as any)[k]!==p[k])(el as any)[k]=p[k];}catch(error){runtime.fail(error);}},[p.currentTime,p.playbackRate,p.volume,p.muted,runtime]);
 const style:any={width:'100%',height:'100%',boxSizing:'border-box',fontFamily:p.fontFamily??runtime.scene.theme?.fontFamily??'Arial,sans-serif',fontSize:p.fontSize??24,color:p.color??p.fill??runtime.scene.theme?.text??'#172033',textAlign:p.textAlign??'left',fontWeight:p.bold?700:400,lineHeight:p.lineHeight??1.3,whiteSpace:'pre-wrap',overflowWrap:'anywhere',display:'flex',alignItems:p.verticalAlign??'center',justifyContent:p.textAlign==='center'?'center':undefined};
 const common:any={'aria-label':p.ariaLabel??p.text??p.id,disabled:!!p.disabled,style:{...style,display:undefined},onInput:(e:any)=>onEvent('input',e),onChange:(e:any)=>onEvent('change',e)};let content;
 switch(type){
 case 'Text':content=<div style={style}>{p.text??''}</div>;break;
 case 'RichText':content=<div style={{...style,display:'block'}}>{(p.runs??[]).map((run:any,i:number)=><span key={i} style={{fontWeight:run.bold?700:undefined,fontStyle:run.italic?'italic':undefined,color:run.color,textDecoration:run.underline?'underline':undefined}}>{run.text}</span>)}</div>;break;
 case 'Button':content=<button type="button" {...common} style={{...common.style,background:p.fill??runtime.scene.theme?.accent??'#2563eb',color:p.color??'white',border:p.selected?'3px solid currentColor':'none',borderRadius:p.radius??8,cursor:'pointer',padding:8}} aria-pressed={typeof p.selected==='boolean'?p.selected:undefined}>{p.text??'Button'}</button>;break;
 case 'Input':content=<input {...common} type={p.inputType??'text'} value={p.value??''} placeholder={p.placeholder} min={p.min} max={p.max} step={p.step} readOnly={p.readOnly}/>;break;
 case 'Textarea':content=<textarea {...common} value={p.value??''} placeholder={p.placeholder} readOnly={p.readOnly}/>;break;
 case 'Slider':content=<input {...common} type="range" min={p.min??0} max={p.max??100} step={p.step??1} value={p.value??0}/>;break;
 case 'Toggle':content=<label style={{...style,gap:12}}><input {...common} style={{width:28,height:28}} type="checkbox" checked={!!p.value}/>{p.text}</label>;break;
 case 'Select':content=<select {...common} value={p.value??''}>{(p.options??[]).map((option:any)=><option key={option.value??option} value={option.value??option}>{option.label??option}</option>)}</select>;break;
 case 'FileInput':content=<input {...common} type="file" accept={p.accept??'.json,.csv,image/*'} onInput={undefined} onChange={async e=>{e.stopPropagation();const file=e.target.files?.[0];if(!file)return;try{if(file.size>32*1024*1024)throw new Error('Upload exceeds 32 MiB');const value=file.type.startsWith('image/')?runtime.assets.session(file):file.name.toLowerCase().endsWith('.csv')?parseCSV(await file.text()):JSON.parse(await file.text());onEvent('change',e,value);}catch(error){runtime.fail(error);}}}/>;break;
 case 'Video':case 'Audio':{
  const update=(e:any)=>{const el=media.current!;onEvent('mediaTime',e,el.currentTime);if(p.timePath)runtime.store.set(p.timePath,el.currentTime);for(let i=0;i<(p.cues??[]).length;i++){const cue=p.cues[i];if(el.currentTime<cue.time)fired.current.delete(i);else if(!fired.current.has(i)){fired.current.add(i);runtime.background(cue.actions,{value:el.currentTime,target:p.id});}}if(p.timeline)runtime.timeline.seek(p.timeline,el.currentTime*1000);};
  const mp={ref:media as any,src:runtime.assets.resolve(p.src),controls:p.controls!==false,muted:p.muted??false,loop:p.loop??false,preload:'metadata' as const,'aria-label':p.ariaLabel??p.id,style:{width:'100%',height:'100%'},onTimeUpdate:update,onSeeking:update,onPlay:(e:any)=>onEvent('mediaPlay',e),onPause:(e:any)=>onEvent('mediaPause',e),onEnded:(e:any)=>onEvent('mediaEnded',e)};
  content=type==='Video'?<video {...mp} poster={p.poster?runtime.assets.resolve(p.poster):undefined}/>:<audio {...mp}/>;break;
 }
 default:throw new Error(`Unsupported node ${type}`);
 }
 return <foreignObject width={p.width??100} height={p.height??40}>{content}</foreignObject>;
}
