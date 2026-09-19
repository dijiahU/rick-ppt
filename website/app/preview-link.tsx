'use client';
import {useEffect,useRef,useState,type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {useLanguage} from './language';

const words={
 en:{open:'View full screen',close:'Close preview'},
 'zh-CN':{open:'全屏查看',close:'关闭预览'},
 fr:{open:'Voir en plein écran',close:'Fermer l’aperçu'},
 es:{open:'Ver en pantalla completa',close:'Cerrar vista previa'},
 ja:{open:'全画面で表示',close:'プレビューを閉じる'},
};

function PreviewDialog({src,label,closeLabel,onClose}:{src:string;label:string;closeLabel:string;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{
  const element=dialog.current!;
  const previous=document.body.style.overflow;
  document.body.style.overflow='hidden';
  if(!element.open)element.showModal();
  return()=>{document.body.style.overflow=previous;};
 },[]);
 return createPortal(<dialog ref={dialog} className="preview-dialog" aria-label={label} onClose={onClose}>
  <div className="preview-toolbar"><span>{label}</span><button type="button" onClick={()=>dialog.current?.close()} aria-label={closeLabel}>{closeLabel} <span aria-hidden="true">×</span></button></div>
  <div className="preview-canvas"><img src={src} alt={label}/></div>
 </dialog>,document.body);
}

export default function PreviewLink({href,label,className,children}:{href:string;label:string;className?:string;children:ReactNode}){
 const {locale}=useLanguage(),w=words[locale];
 const [open,setOpen]=useState(false),link=useRef<HTMLAnchorElement>(null);
 return <><a ref={link} href={href} className={className} aria-haspopup="dialog" aria-label={`${w.open} · ${label}`} onClick={event=>{
  if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  event.preventDefault();setOpen(true);
 }}>{children}</a>
 {open&&<PreviewDialog src={href} label={label} closeLabel={w.close} onClose={()=>{setOpen(false);link.current?.focus();}}/>}
 </>;
}
