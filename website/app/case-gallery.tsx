'use client';
import {useState} from 'react';
import {useLanguage} from './language';
import {landingCopy} from '@/lib/landing-i18n';
import {galleryCopy} from '@/lib/gallery-i18n';
import {useWaterGallery} from './use-water-gallery';
import {switchDirection} from '@/lib/water-model';
import {ScientificCase,AnimationCase,ChartCase,ImageCase,FormulaCase,ObjectCase} from './gallery-cases';
const components=[ScientificCase,AnimationCase,ChartCase,ImageCase,FormulaCase,ObjectCase];
export default function CaseGallery(){
 const {locale}=useLanguage(),c=landingCopy[locale],g=galleryCopy[locale];const [active,setActive]=useState(0),[waterPaused,setWaterPaused]=useState(false),[developed,setDeveloped]=useState(false);
 const water=useWaterGallery(active,waterPaused);
 function go(index:number){const next=(index+components.length)%components.length;if(next===active)return;water.surge(next,switchDirection(active,next,components.length));setDeveloped(false);setActive(next);}
 const previous=(active+components.length-1)%components.length,next=(active+1)%components.length;
 return <section className="case-gallery water-gallery darkroom-gallery" id="cases" aria-label={g.sample} aria-roledescription="carousel" data-active-case={active}>
 <div className="case-stage" ref={water.stageRef} onPointerMove={water.onPointerMove} onPointerDown={water.onPointerDown}><div className="water-surface" aria-hidden="true"><div className="water-still"/><canvas className="water-canvas"/></div><canvas className="water-spray" aria-hidden="true"/><button type="button" className="water-motion-toggle" aria-pressed={waterPaused} onClick={()=>setWaterPaused(value=>!value)}><span aria-hidden="true">{waterPaused?'▷':'Ⅱ'}</span>{waterPaused?g.resumeWater:g.pauseWater}</button>{components.map((Component,index)=>{const position=index===active?'is-current':index===previous?'is-previous':index===next?'is-next':'is-away';return <article key={index} className={`case-card ${position}`} id={`gallery-panel-${index}`} role="tabpanel" aria-labelledby={`gallery-tab-${index}`} aria-hidden={index!==active}>
 <div className="case-paper" inert={index!==active} data-developed={index===active&&developed} onFocusCapture={()=>{if(index===active)setDeveloped(true);}} onAnimationEnd={event=>{if(index===active&&event.target===event.currentTarget&&event.animationName==='darkroom-develop')setDeveloped(true);}}><div className="case-paper-top"><span><i/>0{index+1} / {g.titles[index]}</span><span className="darkroom-print-status">{index===active?<><span className="darkroom-status-developing" aria-hidden="true">{g.developing}</span><span className="darkroom-status-ready">{g.output}</span></>:g.undeveloped}</span></div><div className="case-paper-content">{<Component g={g} c={c} active={active===index}/>}</div><span className="darkroom-emulsion" aria-hidden="true"/></div>
 {index!==active&&<button className="case-bring-forward" type="button" tabIndex={-1} aria-label={`${g.switch} ${g.titles[index]}`} onClick={()=>go(index)}><span><small>0{index+1}</small>{g.titles[index]}<i>↗</i></span></button>}
 </article>})}</div>
 <div className="case-gallery-nav"><button type="button" className="gallery-arrow" aria-label={g.previous} onClick={()=>go(active-1)}>←</button><div className="case-selector" role="tablist" aria-label={g.sample} onKeyDown={event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?components.length-1:(active+(event.key==='ArrowRight'?1:components.length-1))%components.length;go(next);(event.currentTarget.querySelectorAll('button')[next] as HTMLButtonElement)?.focus();}}>{g.titles.map((title,index)=><button type="button" id={`gallery-tab-${index}`} role="tab" aria-selected={active===index} tabIndex={active===index?0:-1} aria-controls={`gallery-panel-${index}`} key={index} onClick={()=>go(index)}><span>0{index+1}</span>{title}</button>)}</div><button type="button" className="gallery-arrow" aria-label={g.next} onClick={()=>go(active+1)}>→</button></div>
 <div className="case-caption" aria-live="polite"><p>{g.hints[active]}</p><span>{g.disclosure}</span></div>
 </section>;
}
