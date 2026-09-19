import type {Dict} from './types';
export const forbidden = new Set(['__proto__','prototype','constructor','caller','callee','arguments']);
export function safeKey(key:string) {if(forbidden.has(key))throw new Error(`Forbidden key: ${key}`);return key;}
export function safeObject(value:any,depth=0):void {if(depth>48)throw new Error('Maximum nesting depth exceeded');if(value&&typeof value==='object')for(const k of Object.keys(value)){safeKey(k);safeObject(value[k],depth+1);}}
export function parts(path:string):string[]{if(!path||path.length>512)throw new Error('Invalid state path');return path.replace(/^state\./,'').split('.').map(k=>{if(!/^[\w-]+$/.test(k))throw new Error('Invalid state path');return safeKey(k);});}
export function getPath(value:any,path:string){return parts(path).reduce((v,k)=>v!=null&&Object.hasOwn(v,k)?v[k]:undefined,value);}
export function setPath(value:Dict,path:string,next:any):Dict {safeObject(next);const keys=parts(path);const copy=Array.isArray(value)?[...value]:{...value};let cursor:any=copy;let old:any=value;keys.forEach((k,i)=>{if(i===keys.length-1)cursor[k]=structuredClone(next);else {old=old!=null&&Object.hasOwn(old,k)?old[k]:undefined;cursor[k]=Array.isArray(old)?[...old]:{...old};cursor=cursor[k];}});return copy;}
export function equal(a:any,b:any):boolean{return Object.is(a,b)||JSON.stringify(a)===JSON.stringify(b);}
