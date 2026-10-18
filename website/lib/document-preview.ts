import {unzipSync,strFromU8} from 'fflate';
import {MAX_FILE_BYTES} from './attachments';

const MAX_CHARS=300000,WORD_NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main';
export function documentText(data:Uint8Array,format:string){
 if(data.byteLength>MAX_FILE_BYTES)throw Error('File too large');
 let text:string;
 if(format==='docx'){
  let count=0,total=0;
  const parts=unzipSync(data,{filter(file){
   count++;total+=file.originalSize;
   if(count>2000||total>80*1024*1024)throw Error('Document archive too large');
   if(file.name!=='word/document.xml')return false;
   if(file.originalSize>4*1024*1024)throw Error('Document text too large');
   return true;
  }});
  if(!parts['word/document.xml'])throw Error('Missing Word document');
  const xml=strFromU8(parts['word/document.xml']);
  if(/<!DOCTYPE|<!ENTITY/i.test(xml))throw Error('Unsupported XML declarations');
  const doc=new DOMParser().parseFromString(xml,'application/xml');
  if(doc.getElementsByTagName('parsererror').length)throw Error('Invalid Word XML');
  text=Array.from(doc.getElementsByTagNameNS(WORD_NS,'p')).map(paragraph=>{
   const nodes=paragraph.getElementsByTagNameNS(WORD_NS,'t');
   return Array.from(nodes).map(node=>node.textContent??'').join('');
  }).join('\n\n');
 }else if(['txt','md','csv'].includes(format))text=new TextDecoder('utf-8',{fatal:true}).decode(data);
 else throw Error('Unsupported document preview');
 return {text:text.slice(0,MAX_CHARS),truncated:text.length>MAX_CHARS};
}
