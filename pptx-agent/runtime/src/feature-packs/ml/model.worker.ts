/// <reference lib="webworker" />
import * as ort from 'onnxruntime-web/webgpu';
import {validateTensors,type TensorMap} from './contracts';
const scope=self as unknown as DedicatedWorkerGlobalScope;let session:ort.InferenceSession|undefined;let provider='wasm';
function makeTensor(value:any){const data=value.type==='float32'?new Float32Array(value.data):value.type==='float64'?new Float64Array(value.data):value.type==='int32'?new Int32Array(value.data):value.type==='int64'?BigInt64Array.from(value.data.map(BigInt)):new Uint8Array(value.data.map(Number));return new ort.Tensor(value.type,data,value.dims);}
scope.onmessage=async event=>{const message=event.data;try{
 if(message.type==='load'){
  if(!(message.bytes instanceof ArrayBuffer)||message.bytes.byteLength>256*1024*1024)throw new Error('Invalid model or model exceeds 256 MiB');const base=new URL(message.wasmURL);if(base.origin!==location.origin||!base.pathname.endsWith('/packs/ml/'))throw new Error('ONNX runtime must be local');
  ort.env.wasm.wasmPaths={mjs:new URL('ort-wasm-simd-threaded.jsep.mjs',base).href,wasm:new URL('ort-wasm-simd-threaded.jsep.wasm',base).href};ort.env.wasm.numThreads=1;ort.env.wasm.proxy=false;ort.env.logLevel='warning';
  if(message.preferWebGPU!==false&&(navigator as any).gpu){try{session=await ort.InferenceSession.create(message.bytes,{executionProviders:['webgpu','wasm'],graphOptimizationLevel:'all'});provider='webgpu+wasm';}catch{session=undefined;}}
  if(!session){session=await ort.InferenceSession.create(message.bytes,{executionProviders:['wasm'],graphOptimizationLevel:'all'});provider='wasm';}
  scope.postMessage({id:message.id,type:'loaded',provider,inputs:session.inputNames,outputs:session.outputNames});
 }else if(message.type==='run'){
  if(!session)throw new Error('Model is not loaded');validateTensors(message.inputs);const inputs:Record<string,ort.Tensor>=Object.create(null);for(const [key,value]of Object.entries(message.inputs))inputs[key]=makeTensor(value);let outputs:Record<string,ort.Tensor>={};
  try{outputs=await session.run(inputs);const result:TensorMap=Object.create(null);let count=0;for(const [key,tensor]of Object.entries(outputs)){count+=tensor.data.length;if(count>16*1024*1024)throw new Error('Model output exceeds 16 million elements');result[key]={type:tensor.type as any,dims:[...tensor.dims],data:Array.from(tensor.data as any,value=>typeof value==='bigint'?value.toString():value) as any};}scope.postMessage({id:message.id,type:'result',outputs:result,provider});}finally{Object.values(inputs).forEach(tensor=>tensor.dispose());Object.values(outputs).forEach(tensor=>tensor.dispose());}
 }else throw new Error('Unknown model request');
 }catch(error){scope.postMessage({id:message.id,type:'error',error:String(error)});}};
