/* Deliberately a separate worker. Its response CSP alone permits unsafe-eval. */
'use strict';
const send=postMessage.bind(globalThis);
const rawConsole=console;
let total=0,maximum=262144,closed=false;
function output(kind,value){if(closed)return;let text;try{text=typeof value==='string'?value:JSON.stringify(value);}catch{text=String(value);}text=String(text??'undefined');const remaining=maximum-total;if(remaining<=0)return;text=text.slice(0,remaining);total+=text.length;send({type:kind,text});if(total===maximum)send({type:'stderr',text:'\n[Output limit reached]'});}
function deny(){throw new Error('Network and nested workers are disabled in code execution');}
function lockNetwork(){for(const key of ['fetch','XMLHttpRequest','WebSocket','EventSource','Worker','SharedWorker','importScripts','BroadcastChannel']){try{Object.defineProperty(globalThis,key,{value:deny,writable:false,configurable:false});}catch{globalThis[key]=deny;}}}
function serializable(value){if(value===undefined)return null;try{const text=JSON.stringify(value,(_,v)=>typeof v==='bigint'?v.toString():v);return text.length>262144?'[Result exceeds 256 KiB]':JSON.parse(text);}catch{return String(value).slice(0,262144);}}
onmessage=async(event)=>{
 if(closed)return;const request=event.data;
 try{
  if(request?.type!=='run'||!['javascript','python'].includes(request.language)||typeof request.code!=='string'||request.code.length>65536)throw new Error('Invalid code execution request');
  maximum=Math.min(262144,Math.max(1024,Number(request.outputLimit)||262144));const inputs=Array.isArray(request.stdin)?request.stdin.map(String):[];let result;
  if(request.language==='python'){
   const indexURL=new URL(request.pythonURL);if(indexURL.origin!==location.origin||!indexURL.pathname.endsWith('/packs/code/pyodide/'))throw new Error('Python runtime must use local installed assets');
   importScripts(new URL('pyodide.js',indexURL).href);
   const pyodide=await loadPyodide({indexURL:indexURL.href,stdout:text=>output('stdout',text),stderr:text=>output('stderr',text)});
   pyodide.setStdin({stdin:()=>inputs.length?inputs.shift():null});pyodide.setStdout({batched:text=>output('stdout',text)});pyodide.setStderr({batched:text=>output('stderr',text)});
   lockNetwork();send({type:'started'});result=await pyodide.runPythonAsync(request.code);if(result?.toJs){const proxy=result;try{result=proxy.toJs({dict_converter:entries=>Object.fromEntries(entries)});}finally{proxy.destroy();}}
  }else{
   lockNetwork();Object.defineProperty(globalThis,'console',{value:Object.freeze({log:(...values)=>output('stdout',values.map(v=>typeof v==='string'?v:JSON.stringify(v)).join(' ')),info:(...v)=>output('stdout',v.join(' ')),warn:(...v)=>output('stderr',v.join(' ')),error:(...v)=>output('stderr',v.join(' '))}),writable:false});
   send({type:'started'});const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
   result=await new AsyncFunction('input','print','"use strict";\nreturn await (async () => {\n'+request.code+'\n})();')(()=>inputs.length?inputs.shift():null,(...values)=>output('stdout',values.join(' ')));
  }
  send({type:'done',result:serializable(result)});
 }catch(error){output('stderr',String(error?.stack??error));send({type:'error',error:String(error?.message??error)});}
 finally{closed=true;close();}
};
