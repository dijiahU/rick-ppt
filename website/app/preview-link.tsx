'use client';
import {lazy,Suspense,useEffect,useRef,useState,type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {useLanguage} from './language';
const DocumentPreview=lazy(()=>import('./document-preview'));

const words={
 en:{open:'View full screen',close:'Close preview',actual:'Original size',fit:'Fit to screen'},
 'zh-CN':{open:'全屏查看',close:'关闭预览',actual:'原图大小',fit:'适应屏幕'},
 fr:{open:'Voir en plein écran',close:'Fermer l’aperçu',actual:'Taille originale',fit:'Ajuster à l’écran'},
 es:{open:'Ver en pantalla completa',close:'Cerrar vista previa',actual:'Tamaño original',fit:'Ajustar a la pantalla'},
 ja:{open:'全画面で表示',close:'プレビューを閉じる',actual:'元のサイズ',fit:'画面に合わせる'},
};

function PreviewDialog({src,label,format,closeLabel,onClose}:{src:string;label:string;format?:string;closeLabel:string;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const {locale}=useLanguage(),w=words[locale];const [actual,setActual]=useState(false);
 const image=!format||['png','jpg','jpeg'].includes(format);
 useEffect(()=>{
  const element=dialog.current!;
  const previous=document.body.style.overflow;
  document.body.style.overflow='hidden';
  if(!element.open)element.showModal();
  return()=>{document.body.style.overflow=previous;};
 },[]);
 return createPortal(<dialog ref={dialog} className="preview-dialog" aria-label={label} onClose={onClose}>
  <div className="preview-toolbar"><span>{label}</span><div>{image&&<button type="button" onClick={()=>setActual(value=>!value)} aria-pressed={actual}>{actual?w.fit:w.actual}</button>}<button type="button" onClick={()=>dialog.current?.close()} aria-label={closeLabel}>{closeLabel} <span aria-hidden="true">×</span></button></div></div>
  <div className={`preview-canvas${actual?' is-actual-size':''}`}>{image?<img src={src} alt={label}/>:<Suspense fallback={<p role="status">…</p>}><DocumentPreview src={src} format={format!} label={label}/></Suspense>}</div>
 </dialog>,document.body);
}

export default function PreviewLink({href,label,format,className,children}:{href:string;label:string;format?:string;className?:string;children:ReactNode}){
 const {locale}=useLanguage(),w=words[locale];
 const [open,setOpen]=useState(false),link=useRef<HTMLAnchorElement>(null);
 return <><a ref={link} href={href} className={className} aria-haspopup="dialog" aria-label={`${w.open} · ${label}`} onClick={event=>{
  if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  event.preventDefault();setOpen(true);
 }}>{children}</a>
 {open&&<PreviewDialog src={href} label={label} format={format} closeLabel={w.close} onClose={()=>{setOpen(false);link.current?.focus();}}/>}
 </>;
}
