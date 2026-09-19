import {init,parse} from 'es-module-lexer';
import {digest,safeRelative} from '../core/assets';
import type {FeatureContext} from '../feature-packs/types';
import type {Dict} from '../core/types';
import {readBounded} from '../feature-packs/fetch';

export const pluginCapabilities=new Set(['components','actions','functions','dataSources']);
export function validatePluginManifest(manifest:Dict,allowed:string[],base:string){
 if(!/^[A-Za-z][A-Za-z0-9_-]{0,95}$/.test(manifest.id)||!/^\d+\.\d+\.\d+(?:[-+.][\w.-]+)?$/.test(manifest.version))throw new Error('Plugin identity/version invalid');
 if(!allowed.includes(manifest.id))throw new Error(`Plugin is not explicitly approved: ${manifest.id}`);
 if(!/^[a-f0-9]{64}$/.test(manifest.sha256)||!Array.isArray(manifest.capabilities)||new Set(manifest.capabilities).size!==manifest.capabilities.length||manifest.capabilities.some((v:string)=>!pluginCapabilities.has(v)))throw new Error('Plugin hash/capabilities invalid');
 const url=new URL(safeRelative(manifest.path),base);if(url.origin!==new URL(base).origin)throw new Error('Plugin must be same-origin');return url;
}
export async function validatePluginSource(source:string){
 if(source.length>2*1024*1024)throw new Error('Plugin exceeds 2 MiB');await init;const [imports]=parse(source);if(imports.length)throw new Error('Plugin must be a self-contained bundle without static/dynamic imports or import.meta');
}
export async function loadDeckPlugins(context:FeatureContext){
 const runtime=context.runtime;for(const manifest of runtime.scene.plugins??[]){
  const url=validatePluginManifest(manifest,runtime.scene.runtimeOptions?.allowedPlugins??[],runtime.base);const response=await fetch(url,{credentials:'omit',redirect:'error'});if(!response.ok)throw new Error(`Plugin unavailable: ${manifest.id}`);
  const bytes=await readBounded(response,2*1024*1024);if(await digest(bytes)!==manifest.sha256)throw new Error(`Plugin integrity failed: ${manifest.id}`);
  const source=new TextDecoder('utf-8',{fatal:true}).decode(bytes);await validatePluginSource(source);const blob=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));let plugin:any;
  try{plugin=(await import(/* @vite-ignore */ blob)).default;}finally{URL.revokeObjectURL(blob);}
  if(!plugin||plugin.id!==manifest.id||plugin.version!==manifest.version)throw new Error('Plugin export identity mismatch');const caps=new Set(manifest.capabilities);const requireCapability=(name:string)=>{if(!caps.has(name))throw new Error(`Plugin capability not declared: ${name}`);};
  for(const key of ['components','actions','functions','dataSources'])if(plugin[key]&&Object.keys(plugin[key]).length)requireCapability(key);
  for(const [name,fn]of Object.entries(plugin.components??{})){if(typeof fn!=='function')throw new Error('Plugin component must be callable');runtime.components.register(`${manifest.id}.${name}`,fn as any);}
  for(const [name,fn]of Object.entries(plugin.actions??{})){if(typeof fn!=='function')throw new Error('Plugin action must be callable');context.action(`${manifest.id}.${name}`,(args,event)=>(fn as any)(args,event,api));}
  for(const [name,fn]of Object.entries(plugin.functions??{})){if(typeof fn!=='function')throw new Error('Plugin function must be callable');runtime.expressions.functions.register(`${manifest.id.replace(/-/g,'_')}_${name}`,fn as any);}
  for(const [name,fn]of Object.entries(plugin.dataSources??{})){if(typeof fn!=='function')throw new Error('Plugin data source must be callable');context.dataSource(`${manifest.id}.${name}`,source=>(fn as any)(source,api));}
  const api=Object.freeze({id:manifest.id,version:manifest.version,readState:()=>structuredClone(runtime.store.get()),readData:()=>structuredClone(runtime.store.getData()),setState:(path:string,value:any)=>{requireCapability('actions');runtime.store.set(path,value);},emit:(type:string,value:any)=>{requireCapability('actions');runtime.emit({type,target:manifest.id,value,timestamp:performance.now()});},asset:(key:string)=>runtime.assets.resolve(key)});
  if(plugin.init)await plugin.init(api);if(plugin.dispose)context.dispose(()=>plugin.dispose());
 }
}
