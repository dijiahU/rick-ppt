'use client';
import {useRef,useState} from 'react';
import {extensions,validFiles} from '@/lib/attachments';
import {uploadMessages} from '@/lib/upload-i18n';
import {useLanguage} from './language';
export default function FileUpload({files,onChange,title}:{files:File[];onChange:(files:File[])=>void;title?:string}){
 const {locale}=useLanguage(),t=uploadMessages[locale],input=useRef<HTMLInputElement>(null);
 const [invalid,setInvalid]=useState(false);
 return <section className="file-upload" aria-labelledby="upload-title"><label id="upload-title" htmlFor="references">{title??t.title}</label><div className="upload-zone"><span aria-hidden="true">↥</span><button type="button" onClick={()=>input.current?.click()}>{t.choose}</button><input ref={input} id="references" className="sr-only" type="file" multiple accept={extensions.map(x=>'.'+x).join(',')} aria-describedby="upload-help" onChange={e=>{const next=[...files,...Array.from(e.target.files??[])];if(validFiles(next)){onChange(next);setInvalid(false);}else setInvalid(true);e.target.value='';}}/><p id="upload-help" className="fineprint">{t.hint}</p></div>
 {!!files.length&&<ul className="attachment-list">{files.map((file,i)=><li key={i}><span>{file.name} <small>({(file.size/1024/1024).toFixed(2)} MB)</small></span><button type="button" aria-label={`${t.remove} ${file.name}`} onClick={()=>{onChange(files.filter((_,n)=>n!==i));setInvalid(false);}}>{t.remove}</button></li>)}</ul>}{invalid&&<p role="alert" className="error">{t.error}</p>}</section>;
}
