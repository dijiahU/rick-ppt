'use client';
import {useEffect,useState} from 'react';
import {isImageAttachment,canPreviewAttachment,extension,type Attachment} from '@/lib/attachments';
import PreviewLink from './preview-link';
import {useLanguage} from './language';

const words={en:'Download',fr:'Télécharger',es:'Descargar','zh-CN':'下载原文件',ja:'ダウンロード'};
export function SelectedAttachment({file}:{file:File}){
 const [src,setSrc]=useState<string|null>(null);
 useEffect(()=>{
  if(!canPreviewAttachment(file)){setSrc(null);return;}
  const url=URL.createObjectURL(file);setSrc(url);return()=>URL.revokeObjectURL(url);
 },[file]);
 const label=<span>{file.name}<small>{(file.size/1024/1024).toFixed(2)} MB</small></span>;
 return src?<PreviewLink href={src} label={file.name} format={extension(file.name)} className="selected-attachment">{isImageAttachment(file)&&<img src={src} alt={file.name} loading="lazy" decoding="async"/>}{label}</PreviewLink>:<span className="selected-attachment">{label}</span>;
}
export default function AttachmentPreviews({files,hrefFor}:{files:Attachment[];hrefFor:(file:Attachment)=>string}){
 const {locale}=useLanguage();
 return <ul className="attachment-previews">{files.map(file=>{
  const href=hrefFor(file),preview=href+(href.includes('?')?'&':'?')+'preview=1';
  return <li key={file.id}>{canPreviewAttachment(file)?<PreviewLink href={preview} label={file.name} format={file.ext} className={isImageAttachment(file)?'attachment-image':'attachment-document'}>{isImageAttachment(file)&&<img src={preview} alt={file.name} loading="lazy" decoding="async"/>}<span>{file.name}</span></PreviewLink>:<span className="attachment-filename">{file.name}</span>}<div className="attachment-meta"><small>{(file.size/1024/1024).toFixed(2)} MB</small><a href={href}>{words[locale]} ↓</a></div></li>;
 })}</ul>;
}
