import type {Scene} from './types';
import {withDiagnostic} from './diagnostics';
export function safeRelative(path:string){if(!path||path.startsWith('/')||path.includes('\\')||path.includes('\0')||/^[a-z]+:/i.test(path)||path.split('/').some(p=>p==='..'||p==='.'||!p)||decodeURIComponent(path)!==path)throw new Error(`Unsafe asset path: ${path}`);return path;}
export function allowedUrl(path:string,base:string,allowlist:string[]=[]):string {if(/^[a-z]+:/i.test(path)){const url=new URL(path);if(!['https:','wss:'].includes(url.protocol)||url.username||url.password||!allowlist.includes(url.origin))throw new Error(`Network URL is not allowlisted: ${url.origin}`);return url.href;}return new URL(safeRelative(path),base).href;}
export async function digest(bytes:ArrayBuffer){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');}
export class Assets {
 private urls=new Map<string,string>();
 constructor(public scene:Scene,public base:string){}
 url(key:string){try{const a=this.scene.assets?.[key];return allowedUrl(a?.path??key,this.base,this.scene.runtimeOptions?.networkAllowlist??[]);}catch(error){throw withDiagnostic(error,{sceneId:this.scene.id,asset:key,phase:'asset'});}}
 async verify(){for(const [key,asset]of Object.entries(this.scene.assets??{})){try{const r=await fetch(this.url(key),{redirect:'error',credentials:'omit'});if(!r.ok)throw new Error(`Asset unavailable: ${key}`);const declared=Number(r.headers.get('content-length')??0);if(declared>536870912)throw new Error('Asset too large');const reader=r.body?.getReader(),chunks:Uint8Array[]=[];let length=0;if(reader){try{while(true){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>Math.min(asset.bytes??536870912,536870912)){await reader.cancel();throw new Error(`Asset too large or size mismatch: ${key}`);}chunks.push(value);}}finally{reader.releaseLock();}}const buffer=new Uint8Array(length);let offset=0;for(const chunk of chunks){buffer.set(chunk,offset);offset+=chunk.length;}const b=buffer.buffer;if(b.byteLength>536870912||asset.bytes!==undefined&&b.byteLength!==asset.bytes)throw new Error(`Asset size mismatch: ${key}`);if(asset.sha256&&await digest(b)!==asset.sha256)throw new Error(`Asset hash mismatch: ${key}`);}catch(error){throw withDiagnostic(error,{sceneId:this.scene.id,asset:key,phase:'asset'});}}}
 session(file:File){if(file.size>32*1024*1024)throw new Error('Upload exceeds 32 MiB');const url=URL.createObjectURL(file);this.urls.set(url,url);return url;}
 resolve(key:string){return this.urls.has(key)?key:this.url(key);}
 dispose(){for(const url of this.urls.values())URL.revokeObjectURL(url);this.urls.clear();}
}
