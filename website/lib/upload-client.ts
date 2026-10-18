import {validFiles} from '@/lib/attachments';

type Options={locale?:string;onProgress?:(percent:number)=>void;onRequest?:(xhr:XMLHttpRequest|null)=>void};
const cache=new WeakMap<File,Map<string,{id:string;at:number}>>();
export async function discardUploads(ids:string[],scope:string){
 if(!ids.length)return;
 try{await fetch(`/api/uploads?scope=${encodeURIComponent(scope)}`,{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids})});}catch{/* A confirmed task must stay successful if temporary-file cleanup is unavailable. */}
}
export async function uploadFiles(files:File[],scope:string,options:Options={}){
 if(!validFiles(files))throw Error('Invalid attachments');
 const ids:string[]=[],total=files.reduce((sum,file)=>sum+file.size,0);let done=0;
 for(const file of files){
  const saved=cache.get(file)?.get(scope);
  if(saved&&saved.at>Date.now()-60*60*1000){ids.push(saved.id);done+=file.size;options.onProgress?.(Math.round(done/total*100));continue;}
  // One raw file per request avoids proxy body limits and multipart buffering.
  const id=await new Promise<string>((resolve,reject)=>{
   const xhr=new XMLHttpRequest();options.onRequest?.(xhr);
   xhr.open('POST',`/api/uploads?scope=${encodeURIComponent(scope)}&name=${encodeURIComponent(file.name)}`);
   xhr.timeout=120000;xhr.setRequestHeader('Content-Type','application/octet-stream');
   if(options.locale)xhr.setRequestHeader('X-UI-Language',options.locale);
   xhr.upload.onprogress=event=>{if(event.lengthComputable)options.onProgress?.(Math.round((done+Math.min(event.loaded,file.size))/total*100));};
   xhr.onload=()=>{try{const value=JSON.parse(xhr.responseText);if(xhr.status>=200&&xhr.status<300&&typeof value.id==='string')resolve(value.id);else reject(Error(value.error||'Upload failed'));}catch{reject(Error('Upload failed'));}};
   xhr.onerror=xhr.ontimeout=xhr.onabort=()=>reject(Error('Upload failed'));
   xhr.send(file);
  }).finally(()=>options.onRequest?.(null));
  if(!cache.has(file))cache.set(file,new Map());cache.get(file)!.set(scope,{id,at:Date.now()});
  ids.push(id);done+=file.size;options.onProgress?.(Math.round(done/total*100));
 }
 return ids;
}
