import {useEffect,useRef,useState} from 'react';
import * as monaco from 'monaco-editor/editor/editor.api.js';
import 'monaco-editor/languages/definitions/javascript/register.js';
import 'monaco-editor/languages/definitions/python/register.js';
import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker';
import {CodeExecution,type ExecutionResult} from './execution';
import type {FeaturePack,FeatureProps} from '../types';
import {emitFeature,featureError} from '../types';

(globalThis as any).MonacoEnvironment={getWorker:()=>new EditorWorker()};
type Controller={run:()=>Promise<ExecutionResult>;stop:()=>void;reset:()=>void;getCode:()=>string;setCode:(value:string)=>void};
const controllers=new WeakMap<object,Map<string,Controller>>();
function entries(runtime:object){let value=controllers.get(runtime);if(!value){value=new Map();controllers.set(runtime,value);}return value;}
const buttonStyle={border:'1px solid #cbd5e1',borderRadius:5,padding:'5px 11px',background:'#fff',color:'#172033',cursor:'pointer'};
export function CodeEditor({p,runtime,nodeId}:FeatureProps){
 const host=useRef<HTMLDivElement>(null),editor=useRef<monaco.editor.IStandaloneCodeEditor|undefined>(undefined),settings=useRef(p);settings.current=p;const [status,setStatus]=useState('ready'),[output,setOutput]=useState({stdout:'',stderr:''});const initial=useRef(String(p.value??p.code??'')),execution=useRef<CodeExecution|undefined>(undefined);
 useEffect(()=>{if(!host.current)return;let live=true;const code=new CodeExecution((next,text)=>{if(live){setStatus(next);if(text)setOutput(text);}});execution.current=code;
  const instance=monaco.editor.create(host.current,{value:initial.current,language:p.language??'javascript',theme:p.theme??'vs-dark',automaticLayout:true,minimap:{enabled:false},fontSize:p.fontSize??15,scrollBeyondLastLine:false,wordWrap:'on',readOnly:!!p.readOnly,ariaLabel:p.ariaLabel??'Editable teaching code',padding:{top:8,bottom:8}});editor.current=instance;
  const changed=instance.onDidChangeModelContent(()=>{const value=instance.getValue();if(settings.current.valuePath)runtime.store.set(settings.current.valuePath,value);emitFeature(runtime,nodeId,'codeChange',value);});
  const controller:Controller={getCode:()=>instance.getValue(),setCode:value=>instance.setValue(value),run:async()=>{setOutput({stdout:'',stderr:''});const props=settings.current;const result=await code.run({language:props.language??'javascript',code:instance.getValue(),stdin:props.stdin??[],timeoutMs:props.timeoutMs,outputLimit:props.outputLimit});if(live){if(props.resultPath)runtime.store.set(props.resultPath,result);emitFeature(runtime,nodeId,'codeResult',result);}return result;},stop:()=>code.stop(),reset:()=>{code.stop();instance.setValue(initial.current);setOutput({stdout:'',stderr:''});setStatus('ready');if(settings.current.resultPath)runtime.store.set(settings.current.resultPath,null);emitFeature(runtime,nodeId,'codeReset',null);}};
  entries(runtime).set(nodeId,controller);return()=>{live=false;entries(runtime).delete(nodeId);code.dispose();changed.dispose();instance.getModel()?.dispose();instance.dispose();};
 },[runtime,nodeId]);
 useEffect(()=>{if(p.value!==undefined&&editor.current&&String(p.value)!==editor.current.getValue())editor.current.setValue(String(p.value));},[p.value]);
 const action=(name:keyof Controller)=>()=>{try{const result=(entries(runtime).get(nodeId)?.[name] as any)?.();if(result?.catch)result.catch((error:any)=>setOutput(v=>({...v,stderr:featureError(error)})));}catch(error){setOutput(v=>({...v,stderr:featureError(error)}));}};
 return <div style={{height:'100%',display:'flex',flexDirection:'column',background:'#0f172a',borderRadius:8,border:'1px solid #334155',overflow:'hidden'}}><div style={{display:'flex',alignItems:'center',gap:7,padding:'7px 10px',background:'#e2e8f0',fontFamily:'system-ui',fontSize:12}}><button aria-label="Run code" style={buttonStyle} onClick={action('run')}>Run</button><button aria-label="Stop code" style={buttonStyle} onClick={action('stop')}>Stop</button><button aria-label="Reset code" style={buttonStyle} onClick={action('reset')}>Reset</button><span role="status" data-code-status={status}>{status} · {p.language??'javascript'}</span></div><div ref={host} style={{minHeight:80,flex:'1 1 auto'}}/><pre aria-label="Code output" style={{margin:0,padding:10,height:p.outputHeight??100,overflow:'auto',flexShrink:0,borderTop:'1px solid #334155',fontSize:p.outputFontSize??13,color:'#d1fae5',whiteSpace:'pre-wrap'}}>{output.stdout}<span style={{color:'#fda4af'}}>{output.stderr}</span></pre></div>;
}
const pack:FeaturePack={id:'code',install(context){context.component('CodeEditor',CodeEditor);for(const method of ['run','stop','reset','getCode','setCode'] as const)context.action(`code.${method}`,async args=>{const controller=entries(context.runtime).get(args.target);if(!controller)throw new Error(`Code editor not mounted: ${args.target}`);return method==='setCode'?controller.setCode(String(args.code??'')):(controller[method] as any)();});context.dispose(()=>{entries(context.runtime).forEach(value=>value.stop());controllers.delete(context.runtime);});}};
export default pack;
