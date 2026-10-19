'use client';
import {useEffect,useRef,useState} from 'react';
import {useLanguage} from './language';
import {landingCopy} from '@/lib/landing-i18n';
import TransformerDiagram,{diagramObjects} from './transformer-diagram';
export default function TransformerShowcase(){
 const {locale}=useLanguage(),c=landingCopy[locale];
 const [mode,setMode]=useState(0),[stage,setStage]=useState(0),[compare,setCompare]=useState(false),[split,setSplit]=useState(50),[zoom,setZoom]=useState(false),[selected,setSelected]=useState('encoder-attention');
 const [overrides,setOverrides]=useState<Record<string,{label?:string;fill?:string}>>({});
 const dialog=useRef<HTMLDialogElement>(null);const zoomButton=useRef<HTMLButtonElement>(null);
 useEffect(()=>{if(!zoom)return;const element=dialog.current;if(!element)return;element.showModal();const old=document.body.style.overflow;document.body.style.overflow='hidden';return()=>{element.close();document.body.style.overflow=old;zoomButton.current?.focus();};},[zoom]);
 function dragComparison(event:React.PointerEvent<HTMLDivElement>){const bounds=event.currentTarget.parentElement?.getBoundingClientRect();if(bounds&&bounds.width>0)setSplit(Math.max(0,Math.min(100,Math.round((event.clientX-bounds.left)/bounds.width*100))));}
 const object=diagramObjects.find(obj=>obj.id===selected)!;
 const change=(value:{label?:string;fill?:string})=>setOverrides(old=>({...old,[selected]:{...old[selected],...value}}));
 function chooseMode(value:number){setMode(value);if(value===1)setStage(0);}
 const graphic=(expanded=false)=><TransformerDiagram label={c.figureCaption} interactiveLabel={c.object} stage={mode===1?stage:4} selected={mode===2?selected:undefined} overrides={mode===2?overrides:{}} onSelect={mode===2&&!expanded?setSelected:undefined}/>;
 return <section className="transformer-showcase" aria-label={c.demo} id="specimen">
 <div className="specimen-topline"><span><i/>{c.demo}</span><span className="specimen-file">transformer.pptx <span>↗</span></span></div>
 <div className="specimen-tabs" role="tablist" aria-label={c.demo} onKeyDown={event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const value=event.key==='Home'?0:event.key==='End'?2:(mode+(event.key==='ArrowRight'?1:2))%3;chooseMode(value);(event.currentTarget.querySelectorAll('button')[value] as HTMLButtonElement)?.focus();}}>
 {c.modes.map((text,index)=><button key={index} id={`specimen-tab-${index}`} type="button" role="tab" aria-selected={mode===index} tabIndex={mode===index?0:-1} aria-controls="specimen-panel" onClick={()=>chooseMode(index)}><span>0{index+1}</span>{text}</button>)}
 </div>
 <div id="specimen-panel" role="tabpanel" aria-labelledby={`specimen-tab-${mode}`}>
 <div className="diagram-canvas">
 <div className="diagram-heading"><span>ATTENTION IS ALL YOU NEED</span><strong>The Transformer</strong><span className="diagram-page">01 / 01</span></div>
 <div className="diagram-artwork">{compare&&mode===0?<>
 <TransformerDiagram label={c.wire} monochrome/>
 <div className="diagram-comparison" style={{clipPath:`inset(0 0 0 ${split}%)`}}>{graphic()}</div>
 <div className="comparison-divider" aria-hidden="true" style={{left:`${split}%`}} onPointerDown={event=>{event.currentTarget.setPointerCapture(event.pointerId);dragComparison(event);}} onPointerMove={event=>{if(event.currentTarget.hasPointerCapture(event.pointerId))dragComparison(event);}} onPointerUp={event=>{event.currentTarget.releasePointerCapture(event.pointerId);}}><span>↔</span></div>
 <div className="comparison-labels"><span>{c.wire}</span><span>{c.color}</span></div>
 </>:graphic()}</div>
 <div className="canvas-bottom"><span>{c.figureCaption}</span><button ref={zoomButton} type="button" className="detail-button" onClick={()=>setZoom(true)}>{c.zoom}<span aria-hidden="true">↗</span></button></div>
 </div>
 <div className="specimen-controls">
 {mode===0&&<><div className="precision-controls"><p>{c.lineHint}</p><button type="button" className="outline-control" aria-pressed={compare} onClick={()=>setCompare(value=>!value)}>{c.compare}<span aria-hidden="true">{compare?'−':'+'}</span></button></div>{compare&&<input className="comparison-range" type="range" min="0" max="100" value={split} aria-label={c.slider} onChange={event=>setSplit(Number(event.target.value))}/>}</>}
 {mode===1&&<><div className="stage-progress" aria-hidden="true">{c.stageTitles.map((_,i)=><i key={i} className={i<=stage?'is-active':''}/>)}</div><div className="stage-copy" role="status" aria-live="polite"><span>0{stage+1} / 05</span><div><strong>{c.stageTitles[stage]}</strong><p>{c.stageDescriptions[stage]}</p></div></div><div className="stage-buttons"><button type="button" className="quiet-control" onClick={()=>setStage(s=>Math.max(0,s-1))} disabled={stage===0}>← {c.back}</button><button type="button" className="next-control" onClick={()=>setStage(s=>s===4?0:s+1)}>{stage===4?c.replay:c.next}<span aria-hidden="true">{stage===4?'↺':'→'}</span></button></div></>}
 {mode===2&&<><p className="object-pick-hint">{c.pick}</p><div className="edit-heading"><span>{c.object}</span><button type="button" className="quiet-control" onClick={()=>setOverrides({})}>{c.reset} ↺</button></div><label className="object-input-label" htmlFor="specimen-object-text">{c.editLabel}<input id="specimen-object-text" maxLength={40} value={(overrides[selected]?.label??object.label).replaceAll('\n',' ')} onChange={event=>change({label:event.target.value})}/></label><div className="object-colors"><span>{c.editColor}</span>{['#f1dfbd','#d2e4e9','#d3e7d6','#efdbd5'].map(color=><button key={color} type="button" aria-label={`${c.editColor} ${color}`} aria-pressed={(overrides[selected]?.fill??object.fill)===color} style={{background:color}} onClick={()=>change({fill:color})}/>)}</div><p className="object-edit-hint">{c.editHint}</p></>}
 </div></div>
 <div className="specimen-source"><a href="https://arxiv.org/abs/1706.03762" target="_blank" rel="noreferrer">{c.paper}: Vaswani et al., 2017 · Fig. 1 ↗</a><span>{c.webSample}</span></div>
 <p className="specimen-disclosure">{c.demoNote}</p>
 {zoom&&<dialog className="diagram-dialog" ref={dialog} aria-label={c.detail} onCancel={()=>setZoom(false)} onClick={event=>{if(event.target===event.currentTarget)setZoom(false);}}><div className="diagram-dialog-head"><span>{c.detail} / Transformer</span><button type="button" autoFocus onClick={()=>setZoom(false)}>{c.close} ×</button></div><div className="diagram-dialog-art">{graphic(true)}</div><p>{c.illustration}</p></dialog>}
 </section>;
}
