'use client';
import BriefForm from './brief-form';
import {queueWords} from '@/lib/queue-i18n';
import {LanguagePicker,useLanguage} from './language';
export default function Home({admin}:{admin:boolean}){
 const {t,locale}=useLanguage();
 return <main>
 <header><a href="/" className="brand">PPTX LAB <span>/ {t.studio}</span></a><div className="header-actions">{admin&&<a className="admin-nav" href="/admin">{queueWords[locale].allTasks} ↗</a>}<small>{t.beta}</small><LanguagePicker/></div></header>
 <section className="intro"><div><p className="eyebrow">{t.tagline}</p><h1>{t.headline}<br/><em>{t.headline2}</em></h1><p className="lede">{t.intro}</p></div><div className="specimen" aria-label={t.specimenLabel}><small>{t.process}</small><div className="arch"/><strong>{t.specimen}</strong><small className="bottom">{t.contentDesign}</small></div></section>
 <section className="workspace"><div><p className="eyebrow">{t.briefHeading}</p><h2>{t.briefTitle}</h2><BriefForm/></div><aside><p className="eyebrow">{t.next}</p><h2 className="multiline">{t.nextTitle}</h2><ol>{t.steps.map((title,i)=><li key={i}><b>0{i+1}</b><div><h3>{title}</h3><p>{t.stepDetails[i]}</p></div></li>)}</ol><div className="note"><span>{t.betaNote}</span><p>{t.warning}</p></div></aside></section><footer><span>PPTX LAB / BY RICK</span><span>{t.footer}</span></footer></main>;
}
