'use client';
import {useEffect,useState} from 'react';
import {documentText} from '@/lib/document-preview';
import {MAX_FILE_BYTES} from '@/lib/attachments';
import {useLanguage} from './language';

const words={
 en:{loading:'Loading document…',error:'This document cannot be previewed. Download the original to open it.',note:'Content preview · Download the original for its complete formatting.',truncated:'This preview shows the beginning of a long document. Download the original for the full content.'},
 'zh-CN':{loading:'正在读取文档…',error:'暂时无法预览此文档，请下载原文件打开。',note:'内容预览 · 完整排版、图片和表格请查看原文件。',truncated:'文档较长，当前仅展示开头部分；完整内容请下载原文件。'},
 fr:{loading:'Chargement du document…',error:'Aperçu indisponible. Téléchargez le fichier original.',note:'Aperçu du contenu · Téléchargez l’original pour la mise en page complète.',truncated:'Début du document uniquement. Téléchargez l’original pour le contenu complet.'},
 es:{loading:'Cargando documento…',error:'Vista previa no disponible. Descarga el archivo original.',note:'Vista del contenido · Descarga el original para ver todo el formato.',truncated:'Solo se muestra el inicio. Descarga el original para ver todo el contenido.'},
 ja:{loading:'文書を読み込み中…',error:'プレビューできません。元のファイルをダウンロードしてください。',note:'内容のプレビュー · 完全な書式は元のファイルで確認してください。',truncated:'文書の冒頭のみ表示しています。全内容は元のファイルを確認してください。'},
};
function TextDocument({src,format}:{src:string;format:string}){
 const {locale}=useLanguage(),w=words[locale];
 const [result,setResult]=useState<{text:string;truncated:boolean}|null>(null),[error,setError]=useState(false);
 useEffect(()=>{const controller=new AbortController();let active=true;
  setResult(null);setError(false);
  (async()=>{
   const response=await fetch(src,{signal:controller.signal,credentials:'same-origin',cache:'no-store'});
   if(!response.ok||Number(response.headers.get('Content-Length'))>MAX_FILE_BYTES)throw Error('Document unavailable');
   const data=new Uint8Array(await response.arrayBuffer());
   const value=documentText(data,format);if(active)setResult(value);
  })().catch(()=>{if(active)setError(true);});
  return()=>{active=false;controller.abort();};
 },[src,format]);
 return <div className="document-preview"><article><p className="document-preview-note">{w.note}</p>{error?<p role="alert">{w.error}</p>:!result?<p role="status">{w.loading}</p>:<><pre>{result.text}</pre>{result.truncated&&<p>{w.truncated}</p>}</>}</article></div>;
}
export default function DocumentPreview({src,format,label}:{src:string;format:string;label:string}){
 return format==='pdf'?<iframe className="pdf-preview" src={src} title={label}/>:<TextDocument src={src} format={format}/>;
}
