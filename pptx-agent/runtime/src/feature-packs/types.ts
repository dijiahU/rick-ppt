import type {ComponentType} from 'react';
import type {Runtime} from '../core/runtime';
import type {Dict} from '../core/types';

export type FeatureProps={p:Dict;runtime:Runtime;nodeId:string};
export type FeatureAction=(args:Dict,event:Dict)=>unknown|Promise<unknown>;
export interface FeatureContext {
 runtime:Runtime;
 component(name:string,component:ComponentType<FeatureProps>):void;
 action(name:string,action:FeatureAction):void;
 dataSource(name:string,adapter:(source:Dict)=>Promise<unknown>):void;
 dispose(callback:()=>void):void;
}
export type FeaturePack={id:string;install(context:FeatureContext):void|Promise<void>};

/** Pack assets always belong to the installed runtime, never an untrusted deck. */
export function packURL(relative:string){
 if(!/^[A-Za-z0-9_/.-]+$/.test(relative)||relative.replace(/\/$/,'').split('/').some(v=>!v||v==='.'||v==='..'))throw new Error('Invalid feature asset path');
 return new URL(`packs/${relative}`,new URL('./',location.href)).href;
}
export function emitFeature(runtime:Runtime,nodeId:string,type:string,value:unknown){runtime.emit({type,target:nodeId,value,timestamp:performance.now()});}
export function safeNodeId(value:string){if(!/^[A-Za-z0-9_.:-]{1,192}$/.test(value))throw new Error('Invalid feature instance ID');return value;}
export function boundedNumber(value:unknown,fallback:number,min:number,max:number){const number=Number(value??fallback);if(!Number.isFinite(number))return fallback;return Math.min(max,Math.max(min,number));}
export function featureError(error:unknown){return error instanceof Error?error.message:String(error);}
