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
 }else if(format==='xlsx')text=workbookText(data);
 else if(['txt','md','csv'].includes(format))text=new TextDecoder('utf-8',{fatal:true}).decode(data);
 else throw Error('Unsupported document preview');
 return {text:text.slice(0,MAX_CHARS),truncated:text.length>MAX_CHARS};
}

const SHEET_NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
function parseXml(xml:string){
 if(/<!DOCTYPE|<!ENTITY/i.test(xml))throw Error('Unsupported XML declarations');
 const doc=new DOMParser().parseFromString(xml,'application/xml');
 if(doc.getElementsByTagName('parsererror').length)throw Error('Invalid workbook XML');
 return doc;
}
function columnIndex(ref:string){let n=0;for(const ch of ref.replace(/[0-9]/g,''))n=n*26+ch.charCodeAt(0)-64;return n-1;}
// Text preview of each worksheet as tab-separated rows (values only, no formulas or styles).
export function workbookText(data:Uint8Array){
 let count=0,total=0;
 const parts=unzipSync(data,{filter(file){
  count++;total+=file.originalSize;
  if(count>2000||total>80*1024*1024)throw Error('Workbook archive too large');
  const wanted=file.name==='xl/workbook.xml'||file.name==='xl/sharedStrings.xml'||/^xl\/worksheets\/sheet\d+\.xml$/.test(file.name);
  if(wanted&&file.originalSize>8*1024*1024)throw Error('Worksheet too large');
  return wanted;
 }});
 if(!parts['xl/workbook.xml'])throw Error('Missing workbook');
 const shared=parts['xl/sharedStrings.xml']?Array.from(parseXml(strFromU8(parts['xl/sharedStrings.xml'])).getElementsByTagNameNS(SHEET_NS,'si')).map(si=>Array.from(si.getElementsByTagNameNS(SHEET_NS,'t')).map(t=>t.textContent??'').join('')):[];
 const names=Array.from(parseXml(strFromU8(parts['xl/workbook.xml'])).getElementsByTagNameNS(SHEET_NS,'sheet')).map(x=>x.getAttribute('name')??'');
 const sheets=Object.keys(parts).filter(n=>n.startsWith('xl/worksheets/')).sort((a,b)=>Number(a.match(/\d+/)![0])-Number(b.match(/\d+/)![0]));
 return sheets.map((name,i)=>{
  const rows=Array.from(parseXml(strFromU8(parts[name])).getElementsByTagNameNS(SHEET_NS,'row')).map(row=>{
   const cells:string[]=[];
   for(const c of Array.from(row.getElementsByTagNameNS(SHEET_NS,'c'))){
    const type=c.getAttribute('t'),v=c.getElementsByTagNameNS(SHEET_NS,'v')[0]?.textContent??'';
    const value=type==='s'?(shared[Number(v)]??''):type==='inlineStr'?Array.from(c.getElementsByTagNameNS(SHEET_NS,'t')).map(t=>t.textContent??'').join(''):v;
    cells[columnIndex(c.getAttribute('r')??'A')]=value;
   }
   return Array.from(cells,x=>x??'').join('\t');
  });
  return `# ${names[i]??'Sheet '+(i+1)}\n`+rows.join('\n');
 }).join('\n\n');
}
