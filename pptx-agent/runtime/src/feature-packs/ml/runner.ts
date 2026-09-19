import ModelWorker from './model.worker?worker';
import {packURL,boundedNumber} from '../types';
import {validateTensors,type TensorMap,type ModelAdapter,tensorAdapter} from './contracts';
export class ModelSession {
 private worker?:Worker;private pending=new Map<number,{resolve:(value:any)=>void;reject:(reason:Error)=>void;timer:any}>();private serial=0;loaded=false;provider='unavailable';inputs:string[]=[];outputs:string[]=[];
 private request(message:any,timeoutMs:number,transfer:Transferable[]=[]){const worker=this.worker;if(!worker)return Promise.reject(new Error('Model is not loaded'));return new Promise<any>((resolve,reject)=>{const id=++this.serial,timer=setTimeout(()=>{this.stop(new Error('Model operation timed out'));},timeoutMs);this.pending.set(id,{resolve,reject,timer});worker.postMessage({...message,id},transfer);});}
 async load(bytes:ArrayBuffer,preferWebGPU=true){this.stop();this.worker=new ModelWorker();this.worker.onmessage=event=>{const value=event.data,request=this.pending.get(value.id);if(!request)return;clearTimeout(request.timer);this.pending.delete(value.id);if(value.type==='error')request.reject(new Error(value.error));else request.resolve(value);};this.worker.onerror=event=>{event.preventDefault();this.stop(new Error(event.message));};const result=await this.request({type:'load',bytes,preferWebGPU,wasmURL:packURL('ml/')},60000,[bytes]);this.loaded=true;this.provider=result.provider;this.inputs=result.inputs;this.outputs=result.outputs;return result;}
 async run(inputs:TensorMap,timeoutMs=15000){if(!this.loaded)throw new Error('Model is not loaded');validateTensors(inputs);return this.request({type:'run',inputs},boundedNumber(timeoutMs,15000,100,60000));}
 stop(error=new Error('Model execution stopped')){this.worker?.terminate();this.worker=undefined;this.loaded=false;for(const request of this.pending.values()){clearTimeout(request.timer);request.reject(error);}this.pending.clear();}
}
export class AdapterRegistry {
 private adapters=new Map<string,ModelAdapter>([['tensors',tensorAdapter]]);
 register(name:string,adapter:ModelAdapter){if(!/^[A-Za-z][\w.-]{0,95}$/.test(name)||this.adapters.has(name)||typeof adapter?.preprocess!=='function'||typeof adapter?.postprocess!=='function')throw new Error('Invalid or duplicate model adapter');this.adapters.set(name,adapter);}
 get(name='tensors'){const adapter=this.adapters.get(name);if(!adapter)throw new Error(`Model adapter unavailable: ${name}`);return adapter;}
}
