'use client';
import {useEffect,useRef,useState} from 'react';
import {useLanguage} from './language';
import {landingCopy} from '@/lib/landing-i18n';
import {galleryCopy} from '@/lib/gallery-i18n';
import {useWaterGallery} from './use-water-gallery';
import {ScientificCase,AnimationCase,FormulaCase,ObjectCase} from './gallery-cases';
/** The samples in the tray. `id` is the sample's place in the gallery copy (titles, hints); charts (2) and image layout (3) are not shown, so the four that are can be large. */
const cases=[{id:0,Component:ScientificCase},{id:1,Component:AnimationCase},{id:4,Component:FormulaCase},{id:5,Component:ObjectCase}];
/** A print waits in the bath as a latent image. Lifted the first time, it is built the way a slide is: shapes, then text, then colour. */
export type Phase='latent'|'building'|'ready';
/**
 * The build is one CSS timeline that starts while the print is still rising (see "the build" in darkroom.css).
 * Script only names the stage for the status line and unlocks the controls at the end.
 * Milliseconds from the lift: text begins, colour begins, the print is handed over.
 */
export const BUILD={text:1150,colour:1950,ready:3250};
const Icon=({d}:{d:string})=><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d={d}/></svg>;
export default function CaseGallery({children}:{children?:React.ReactNode}){
 const {locale}=useLanguage(),c=landingCopy[locale],g=galleryCopy[locale];
 const [lifted,setLifted]=useState<number|null>(null),[waterPaused,setWaterPaused]=useState(false),[phases,setPhases]=useState<Phase[]>(()=>cases.map(()=>'latent')),[step,setStep]=useState(0);
 const water=useWaterGallery(lifted,waterPaused);
 const timers=useRef<number[]>([]),cards=useRef<(HTMLElement|null)[]>([]),openers=useRef<(HTMLButtonElement|null)[]>([]),returnTo=useRef<number|null>(null);
 const total=cases.length,title=(index:number)=>g.titles[cases[(index+total)%total].id];
 function setPhase(index:number,phase:Phase){setPhases(old=>old.map((value,i)=>i===index?phase:value));}
 function stopBuild(){for(const id of timers.current)window.clearTimeout(id);timers.current=[];}
 function startBuild(index:number){
  stopBuild();setStep(0);
  if(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){setPhase(index,'ready');return;}
  setPhase(index,'building');
  timers.current=[window.setTimeout(()=>setStep(1),BUILD.text),window.setTimeout(()=>setStep(2),BUILD.colour),window.setTimeout(()=>setPhase(index,'ready'),BUILD.ready)];
 }
 /** Whatever is on the easel is finished before anything else happens to it. */
 function settle(){stopBuild();if(lifted!==null)setPhase(lifted,'ready');}
 function lift(index:number){
  const next=(index+total)%total;if(next===lifted)return;settle();setLifted(next);
  if(phases[next]==='ready')stopBuild();else startBuild(next);
 }
 function putBack(){if(lifted===null)return;settle();returnTo.current=lifted;setLifted(null);}
 function replay(){if(lifted!==null)startBuild(lifted);}
 useEffect(()=>()=>stopBuild(),[]);
 // Focus follows the print: onto it when lifted, back to its place in the tray when returned.
 useEffect(()=>{if(lifted!==null)cards.current[lifted]?.focus({preventScroll:true});else if(returnTo.current!==null){openers.current[returnTo.current]?.focus({preventScroll:true});returnTo.current=null;}},[lifted]);
 const busy=lifted!==null&&phases[lifted]==='building';
 const status=(index:number)=>{const phase=phases[index];return phase==='ready'?g.output:phase==='latent'?g.undeveloped:g.buildSteps[step];};
 return <section className="case-gallery pool" id="cases" aria-label={g.sample} data-lifted={lifted??undefined} onKeyDown={event=>{if(event.key==='Escape'&&lifted!==null&&!(event.target as Element).closest?.('dialog')){event.preventDefault();putBack();}}}>
 <div className="case-stage" ref={water.stageRef} onPointerMove={water.onPointerMove} onPointerDown={water.onPointerDown} onPointerLeave={water.onPointerLeave}>
 <div className="water-surface" aria-hidden="true"><div className="water-still"/><canvas className="water-canvas"/></div><canvas className="water-spray" aria-hidden="true"/>
 <div className="safelight" aria-hidden="true"><i/></div>
 <div className="pool-copy" inert={lifted!==null}>{children}</div>
 {cases.map(({id,Component},index)=>{const up=index===lifted,phase=phases[index];return <article key={index} ref={element=>{cards.current[index]=element;}} className={`case-card ${up?'is-lifted':lifted===null?'is-afloat':'is-waiting'}`} id={`gallery-panel-${index}`} aria-label={title(index)} tabIndex={-1} data-phase={phase} data-case={id} onClick={up&&busy?settle:undefined}>
 <div className="case-paper" inert={!up||busy} data-phase={phase} data-step={up&&phase==='building'?step:undefined}><div className="case-paper-top"><span><i/><span className="case-position"><b>{String(index+1).padStart(2,'0')}</b><span> / {String(total).padStart(2,'0')}</span></span><span>{title(index)}</span></span><span className="print-status" role={up?'status':undefined} aria-live={up?'polite':undefined}>{status(index)}</span></div><div className="case-paper-content">{<Component g={g} c={c} active={up} phase={phase} step={step}/>}</div></div>
 {!up&&<button ref={element=>{openers.current[index]=element;}} className="case-bring-forward" type="button" aria-label={`${g.open} ${title(index)}`} onClick={()=>lift(index)}><span className="print-tag">{title(index)}</span></button>}
 </article>})}
 {lifted!==null&&<div className="lift-bar">
 {busy?<button type="button" className="lift-skip" onClick={settle}>{g.skip}</button>:<button type="button" className="lift-replay" onClick={replay}><Icon d="M5 12a7 7 0 1 0 2.2-5.1M5 4.5V8h3.5"/>{g.replayBuild}</button>}
 <button type="button" className="lift-step" aria-label={`${g.previous} · ${title(lifted-1)}`} title={title(lifted-1)} onClick={()=>lift(lifted-1)}><Icon d="M14.5 5 7.5 12l7 7"/></button>
 <button type="button" className="lift-step" aria-label={`${g.next} · ${title(lifted+1)}`} title={title(lifted+1)} onClick={()=>lift(lifted+1)}><Icon d="M9.5 5l7 7-7 7"/></button>
 <button type="button" className="lift-close" onClick={putBack}><Icon d="M6 6l12 12M18 6 6 18"/>{g.close}</button>
 </div>}
 <p className="lift-hint" aria-live="polite">{lifted!==null?g.hints[cases[lifted].id]:''}</p>
 </div>
 {/* A strip under the tray, so nothing printed here ever lies across a print. */}
 <div className="pool-foot"><span>{g.disclosure}</span><button type="button" className="water-motion-toggle" aria-pressed={waterPaused} onClick={()=>setWaterPaused(value=>!value)}><Icon d={waterPaused?'M8 5.5v13l10-6.5z':'M8.5 5.5v13M15.5 5.5v13'}/>{waterPaused?g.resumeWater:g.pauseWater}</button></div>
 </section>;
}
