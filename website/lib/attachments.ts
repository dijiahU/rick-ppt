export const MAX_FILES=10,MAX_FILE_BYTES=20*1024*1024,MAX_TOTAL_BYTES=200*1024*1024;
// Legacy multipart clients stay bounded; the website stages one file at a time.
export const MAX_INLINE_BYTES=20*1024*1024;
export const extensions=['pdf','pptx','docx','txt','md','csv','png','jpg','jpeg'] as const;
export type Attachment={id:string;name:string;size:number;ext:string;sha256:string};
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export function extension(name:string){return name.split('.').pop()?.toLowerCase()??'';}
export function validFiles(files:{name:string;size:number}[]){return files.length<=MAX_FILES&&files.every(f=>f.name.length<=180&&f.size>0&&f.size<=MAX_FILE_BYTES&&extensions.some(e=>e===extension(f.name)))&&files.reduce((sum,f)=>sum+f.size,0)<=MAX_TOTAL_BYTES;}
export function parseAttachments(value:unknown):Attachment[]{
 if(value==null)return [];
 let items:unknown;try{items=typeof value==='string'?JSON.parse(value):value;}catch{return [];}
 if(!Array.isArray(items)||!validFiles(items.filter(x=>x&&typeof x.name==='string'&&typeof x.size==='number'))||items.some(x=>!x||typeof x.name!=='string'||typeof x.size!=='number'||!Number.isSafeInteger(x.size)||!uuid.test(x.id)||!extensions.some(e=>e===x.ext)||extension(x.name)!==x.ext||typeof x.sha256!=='string'||!/^[0-9a-f]{64}$/.test(x.sha256)))return [];
 if(new Set(items.map(x=>x.id)).size!==items.length)return [];
 return items.map(({id,name,size,ext,sha256})=>({id,name,size,ext,sha256}));
}
export function validSignature(ext:string,data:Uint8Array){
 const start=(bytes:number[])=>bytes.every((v,i)=>data[i]===v);
 if(ext==='pdf')return start([37,80,68,70,45]);
 if(['docx','pptx'].includes(ext))return start([80,75,3,4]);
 if(ext==='png')return start([137,80,78,71,13,10,26,10]);
 if(['jpg','jpeg'].includes(ext))return start([255,216,255]);
 try{const text=new TextDecoder('utf-8',{fatal:true}).decode(data);return !text.includes('\0');}catch{return false;}
}
export async function boundedBody(request:Pick<Request,'headers'|'body'>,max:number){
 const length=Number(request.headers.get('Content-Length'));if(length>max)throw Error('size');
 const reader=request.body?.getReader();if(!reader)return new Uint8Array();
 const chunks:Uint8Array[]=[];let total=0;
 try{while(true){const {done,value}=await reader.read();if(done)break;total+=value.length;if(total>max){await reader.cancel();throw Error('size');}chunks.push(value);}}finally{reader.releaseLock();}
 const result=new Uint8Array(total);let offset=0;for(const chunk of chunks){result.set(chunk,offset);offset+=chunk.length;}return result;
}
export const attachmentKey=(job:string,file:string)=>`attachments/${job}/${file}`;
export const isImageAttachment=(file:{name:string;ext?:string})=>['png','jpg','jpeg'].includes(file.ext??extension(file.name));
export const canPreviewAttachment=(file:{name:string;ext?:string})=>isImageAttachment(file)||['pdf','docx','txt','md','csv'].includes(file.ext??extension(file.name));
export function attachmentResponse(file:{body:ReadableStream},meta:Attachment,preview=false){
 const image=preview&&isImageAttachment(meta);
 const pdf=preview&&meta.ext==='pdf';
 return new Response(file.body,{headers:{'Content-Type':image?(meta.ext==='png'?'image/png':'image/jpeg'):pdf?'application/pdf':'application/octet-stream','Content-Disposition':`${image||pdf?'inline':'attachment'}; filename="reference.${meta.ext}"; filename*=UTF-8''${encodeURIComponent(meta.name).replace(/['()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase())}`,'Content-Length':String(meta.size),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'; img-src 'self' data: blob:"}});
}
