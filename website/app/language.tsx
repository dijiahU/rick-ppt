'use client';
import {createContext,useContext,useEffect,useState} from 'react';
import {isLocale,languages,messages,type Locale} from '@/lib/i18n';
const Context=createContext<{locale:Locale;setLocale:(locale:Locale)=>void}>({locale:'en',setLocale:()=>{}});
export function LanguageProvider({children}:{children:React.ReactNode}){
 const [locale,setValue]=useState<Locale>('en');
 useEffect(()=>{try{const saved=localStorage.getItem('pptx-lab-language');if(isLocale(saved))setValue(saved);}catch{/* Preferences are optional. */}},[]);
 useEffect(()=>{document.documentElement.lang=locale;},[locale]);
 function setLocale(value:Locale){setValue(value);try{localStorage.setItem('pptx-lab-language',value);}catch{/* Switching still works without storage. */}}
 return <Context.Provider value={{locale,setLocale}}>{children}</Context.Provider>;
}
export function useLanguage(){const context=useContext(Context);return {...context,t:messages[context.locale]};}
export function LanguagePicker(){const {locale,setLocale,t}=useLanguage();return <label className="language-picker"><span aria-hidden="true">🌐</span><span className="sr-only">{t.language}</span><select aria-label={t.language} value={locale} onChange={e=>{if(isLocale(e.target.value))setLocale(e.target.value);}}>{Object.entries(languages).map(([code,name])=><option key={code} value={code} lang={code}>{name}</option>)}</select></label>;}
