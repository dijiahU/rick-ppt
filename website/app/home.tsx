'use client';
import BriefForm from './brief-form';
import {queueWords} from '@/lib/queue-i18n';
import {landingCopy} from '@/lib/landing-i18n';
import {LanguagePicker,useLanguage} from './language';
import CaseGallery from './case-gallery';
import {galleryCopy} from '@/lib/gallery-i18n';
import './landing.css';
import './case-gallery.css';
import './water-gallery.css';
import './darkroom-gallery.css';
import './formula-case.css';
export default function Home({admin}:{admin:boolean}){
 const {t,locale}=useLanguage(),c=landingCopy[locale],g=galleryCopy[locale];
 return <main className="landing-root">
 <header className="landing-header"><a href="/" className="landing-brand" aria-label="rickppt"><span className="brand-mark" aria-hidden="true"><i/><i/><i/></span>rickppt<span className="brand-period">.</span></a><nav className="landing-navigation" aria-label={t.studio}><a href="#cases">{c.nav[0]}</a><a href="#workflow">{c.nav[1]}</a></nav><div className="header-actions">{admin&&<a className="admin-nav" href="/admin">{queueWords[locale].allTasks} ↗</a>}<LanguagePicker/><a className="workspace-link" href="#workspace">{c.nav[2]} <span>↗</span></a></div></header>
 <section className="gallery-hero"><div className="gallery-intro"><div><p className="hero-badge"><i/>{c.badge}</p><h1>{g.heading}</h1><p className="gallery-intro-copy">{g.intro}</p></div><a className="landing-primary" href="#workspace">{c.start}<span aria-hidden="true">↗</span></a></div><CaseGallery/></section>
 <section className="landing-workspace" id="workspace"><div className="workspace-form"><p className="landing-kicker">{c.workspaceKicker}</p><h2>{c.workspaceTitle}</h2><BriefForm/></div><aside className="landing-workflow" id="workflow"><p className="landing-kicker">THE PROCESS</p><h2>{c.workflow}</h2><p>{c.workflowNote}</p><ol>{t.steps.map((title,i)=><li key={i}><b>0{i+1}</b><div><h3>{title}</h3><p>{t.stepDetails[i]}</p></div></li>)}</ol><div className="workflow-file"><span className="file-outline" aria-hidden="true">P</span><div><strong>.pptx</strong><span>{c.proof[2]}</span></div><span aria-hidden="true">↙</span></div><div className="note"><span>{t.betaNote}</span><p>{t.warning}</p></div></aside></section>
 <footer className="landing-footer"><a className="landing-brand" href="/">rickppt<span className="brand-period">.</span></a><span>{c.footer}</span><span>BY RICK · {t.beta}</span></footer>
 </main>;
}
