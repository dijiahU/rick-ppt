import type {ComponentType} from 'react';
import type {Runtime} from '../core/runtime';
import type {Dict} from '../core/types';
import type {FeatureContext,FeatureProps,FeatureAction,FeaturePack} from './types';
import {loadDeckPlugins} from '../plugins/loader';
import {withDiagnostic} from '../core/diagnostics';

type Registry={components:Map<string,ComponentType<FeatureProps>>;actions:Map<string,FeatureAction>;sources:Map<string,(source:Dict)=>Promise<unknown>>;loaded:Set<string>};
const registries=new WeakMap<Runtime,Registry>();
const loaders:Record<string,()=>Promise<{default:FeaturePack}>>={three:()=>import('./three'),code:()=>import('./code'),ml:()=>import('./ml'),map:()=>import('./map'),math:()=>import('./math')};
function registry(runtime:Runtime){let r=registries.get(runtime);if(!r){r={components:new Map(),actions:new Map(),sources:new Map(),loaded:new Set()};registries.set(runtime,r);}return r;}
function unique<T>(map:Map<string,T>,name:string,value:T){if(!/^[A-Za-z][A-Za-z0-9_.:-]{0,128}$/.test(name)||map.has(name))throw new Error(`Invalid or duplicate extension: ${name}`);map.set(name,value);}
export async function loadFeaturePacks(runtime:Runtime){
 const r=registry(runtime);if(r.loaded.has('_initialized'))return;r.loaded.add('_initialized');
 const context:FeatureContext={runtime,component:(name,component)=>unique(r.components,name,component),action:(name,action)=>unique(r.actions,name,action),dataSource:(name,adapter)=>unique(r.sources,name,adapter),dispose:callback=>runtime.plugins.push(callback)};
 runtime.actions.register('plugin',async(action,event)=>{const fn=r.actions.get(action.name);if(!fn)throw new Error(`Extension action unavailable: ${action.name}`);const args=runtime.expressions.value(action.args??action.value??{},runtime.store.environment(event.locals??{},event));const result=await fn({...args,target:action.target??args.target},event);if(action.result)runtime.store.set(action.result,result??null);});
 runtime.data.register('plugin',async source=>{const adapter=r.sources.get(source.adapter);if(!adapter)throw new Error(`Extension data adapter unavailable: ${source.adapter}`);return adapter(source);});
 for(const name of new Set(runtime.scene.requires??[])){if(name==='core')continue;try{const load=loaders[name];if(!load)throw new Error(`Unsupported feature pack: ${name}`);const pack=(await load()).default;if(pack.id!==name)throw new Error('Feature pack identity mismatch');await pack.install(context);r.loaded.add(name);}catch(error){throw withDiagnostic(error,{sceneId:runtime.scene.id,plugin:name,phase:'feature-pack-load'});}}
 await loadDeckPlugins(context);
 runtime.plugins.push(()=>{r.components.clear();r.actions.clear();r.sources.clear();registries.delete(runtime);});
}
export function hasFeatureComponent(runtime:Runtime,name:string){return registry(runtime).components.has(name);}
export function FeatureNode({name,p,runtime,nodeId}:{name:string}&FeatureProps){const Component=registry(runtime).components.get(name);if(!Component)throw new Error(`Feature component unavailable: ${name}`);return <foreignObject width={p.width??400} height={p.height??300}><div data-feature={name} data-feature-id={nodeId} style={{width:'100%',height:'100%',overflow:'hidden',color:p.color??'#172033'}}><Component p={p} runtime={runtime} nodeId={nodeId}/></div></foreignObject>;}
export function loadedFeaturePacks(runtime:Runtime){return [...registry(runtime).loaded].filter(v=>!v.startsWith('_'));}
