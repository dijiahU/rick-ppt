import {boundedNumber,packURL} from '../types';
export type RunLanguage='javascript'|'python';
export type ExecutionResult={status:'done'|'error'|'timed_out'|'stopped';stdout:string;stderr:string;result:unknown;elapsedMs:number};
export type ExecutionOptions={language:RunLanguage;code:string;stdin?:string[];timeoutMs?:number;outputLimit?:number};
export function validateExecution(options:ExecutionOptions){
 if(!['javascript','python'].includes(options.language)||typeof options.code!=='string'||options.code.length>65536)throw new Error('Code must be JavaScript or Python and at most 64 KiB');
 if(options.stdin&&(!Array.isArray(options.stdin)||options.stdin.length>1000||options.stdin.some(v=>typeof v!=='string'||v.length>8192)))throw new Error('Invalid stdin inputs');
 return {...options,timeoutMs:boundedNumber(options.timeoutMs,5000,100,30000),outputLimit:boundedNumber(options.outputLimit,262144,1024,262144)};
}
export class CodeExecution {
 private worker?:Worker;private timer:any;private settle?:((result:ExecutionResult)=>void);private started=0;private stdout='';private stderr='';private outputLimit=262144;
 constructor(private progress?:(status:string,output?:{stdout:string;stderr:string})=>void){}
 async run(input:ExecutionOptions):Promise<ExecutionResult>{
  const options=validateExecution(input);this.stop();this.stdout='';this.stderr='';this.outputLimit=options.outputLimit;this.started=performance.now();this.progress?.(options.language==='python'?'loading':'running');
  return new Promise(resolve=>{this.settle=resolve;try{const worker=new Worker(packURL('code/code-runner.worker.js'),{name:'isolated-slide-code'});this.worker=worker;
   const timeout=()=>{this.stderr+='\nExecution exceeded its time limit';this.finish('timed_out',null);};this.timer=setTimeout(timeout,options.language==='python'?60000:options.timeoutMs);
   worker.onmessage=event=>{if(this.worker!==worker)return;const data=event.data;if(data.type==='started'){clearTimeout(this.timer);this.timer=setTimeout(timeout,options.timeoutMs);this.progress?.('running');}else if(data.type==='stdout'||data.type==='stderr'){const key=data.type as 'stdout'|'stderr';this[key]=(this[key]+String(data.text)+'\n').slice(0,this.outputLimit);this.progress?.('running',{stdout:this.stdout,stderr:this.stderr});}else if(data.type==='done')this.finish('done',data.result);else if(data.type==='error')this.finish('error',null);};
   worker.onerror=event=>{event.preventDefault();this.stderr+='\n'+event.message;this.finish('error',null);};worker.postMessage({type:'run',...options,pythonURL:packURL('code/pyodide/')});
  }catch(error){this.stderr=String(error);this.finish('error',null);}});
 }
 private finish(status:ExecutionResult['status'],result:unknown){clearTimeout(this.timer);this.worker?.terminate();this.worker=undefined;const value={status,stdout:this.stdout,stderr:this.stderr,result,elapsedMs:performance.now()-this.started};const settle=this.settle;this.settle=undefined;this.progress?.(status,{stdout:this.stdout,stderr:this.stderr});settle?.(value);}
 stop(){if(this.worker||this.settle)this.finish('stopped',null);}
 dispose(){this.stop();}
}
