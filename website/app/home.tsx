'use client';
import {useRef} from 'react';
import {ReactLenis} from 'lenis/react';
import 'lenis/dist/lenis.css';
import BriefForm from './brief-form';
import {queueWords} from '@/lib/queue-i18n';
import {landingCopy} from '@/lib/landing-i18n';
import {LanguagePicker,useLanguage} from './language';
import CaseGallery from './case-gallery';
import ExampleDecks from './example-decks';
import {galleryCopy} from '@/lib/gallery-i18n';
import VariableProximity from './reactbits/VariableProximity';
import Sunlight from './sunlight';
import StepCards from './step-cards';
import './landing.css';
import './case-gallery.css';
import './formula-case.css';
import './darkroom.css';
/** Form fields, dialogs and anything that scrolls on its own keep native scrolling. */
const nativeScroll=(node:HTMLElement)=>!!node.closest('dialog,textarea,select,pre,[data-native-scroll]');
/** One room: the developing tray, then one wall — finished decks, the brief as notes, the visitor's own jobs. */
export default function Home({admin}:{admin:boolean}){
 const {t,locale}=useLanguage(),c=landingCopy[locale],g=galleryCopy[locale];
 const headline=useRef<HTMLHeadingElement>(null);
 return <main className="landing-root darkroom">
 <ReactLenis root options={{lerp:.11,anchors:{offset:-8},prevent:nativeScroll}}/>
 <header className="landing-header"><a href="/" className="landing-brand" aria-label="rickppt"><span className="brand-mark" aria-hidden="true"><i/><i/><i/></span>rickppt</a><nav className="landing-navigation" aria-label={t.studio}><a href="#cases">{c.nav[0]}</a><a href="#workflow">{c.nav[1]}</a></nav><div className="header-actions">{admin&&<a className="admin-nav" href="/admin">{queueWords[locale].allTasks}</a>}<LanguagePicker/><a className="workspace-link" href="#workspace">{c.nav[2]}</a></div></header>
 <CaseGallery>
  <h1 ref={headline}><VariableProximity label={g.heading} containerRef={headline} radius={190} falloff="gaussian" fromFontVariationSettings="'wght' 760" toFontVariationSettings="'wght' 900" fromColor="var(--paper-dim)" toColor="var(--paper-lit)"/></h1>
  <p className="pool-intro">{g.intro}</p>
  <a className="landing-primary" href="#workspace">{c.start}<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 5v14M6 13l6 6 6-6"/></svg></a>
 </CaseGallery>
 {/* Below the tray every section is on the same wall. */}
 <div className="room">
 <ExampleDecks/>
 {/* The examples and the brief are parted by a stretch of wall in soft shade, with no line between them. */}
 <div className="storey" aria-hidden="true"/>
 <section className="landing-workspace bench" id="workspace">
  <Sunlight side="left"/>
  <h2>{c.workspaceTitle}</h2>
  {/* After the notes and the send button: what the visitor has just set in motion, then their own earlier jobs. */}
  <div className="workspace-form notebook"><BriefForm after={<aside className="bench-next" id="workflow">
   <h3>{c.workflow}</h3><p>{c.workflowNote}</p>
   <StepCards steps={t.steps} details={t.stepDetails}/>
   <p className="bench-note"><strong>{t.betaNote}</strong> {t.warning}</p>
  </aside>}/></div>
 </section>
 <footer className="landing-footer"><a className="landing-brand" href="/">rickppt</a><span>{c.footer}</span><span>By Rick · {t.beta}</span></footer>
 </div>
 </main>;
}
