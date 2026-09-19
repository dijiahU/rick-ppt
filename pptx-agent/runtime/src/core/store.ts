import type {Dict,Environment,Expression} from './types';
import {equal,getPath,setPath,safeObject} from './state';
import {Expressions} from './expressions';
export class SceneStore {
 private initial:Dict;private state:Dict;private data:Dict={};private listeners=new Set<()=>void>();private nesting=0;private changed=false;private undoStack:Dict[]=[];private redoStack:Dict[]=[];private disposed=false;
 constructor(initial:Dict={},private derived:Record<string,Expression>={},public expressions=new Expressions(),data:Dict={}){safeObject(initial);this.data=structuredClone(data);this.initial=structuredClone(initial);this.state=structuredClone(initial);this.recompute();}
 environment(locals:Dict={},event:Dict={}):Environment{return {state:this.state,data:this.data,locals,event};}
 get(path?:string){return path?getPath(this.state,path):this.state;}
 getData(){return this.data;}
 snapshot(){return structuredClone({state:this.state,data:this.data});}
 restore(snap:{state:Dict;data:Dict}){safeObject(snap);this.state=structuredClone(snap.state);this.data=structuredClone(snap.data);this.changed=true;this.flush();}
 set(path:string,value:any){if(this.disposed)return;const next=setPath(this.state,path,value);if(equal(this.state,next))return;this.state=next;this.changed=true;if(!this.nesting)this.flush();}
 setData(name:string,value:any){safeObject({[name]:value});this.data={...this.data,[name]:structuredClone(value)};this.changed=true;if(!this.nesting)this.flush();}
 batch(fn:()=>void,history=false){if(history){this.undoStack.push(this.snapshot());if(this.undoStack.length>100)this.undoStack.shift();this.redoStack=[];}this.nesting++;try{fn();}finally{if(--this.nesting===0)this.flush();}}
 reset(){this.state=structuredClone(this.initial);this.changed=true;this.flush();}
 undo(){const v=this.undoStack.pop();if(v){this.redoStack.push(this.snapshot());this.restore(v as any);}}
 redo(){const v=this.redoStack.pop();if(v){this.undoStack.push(this.snapshot());this.restore(v as any);}}
 subscribe<T>(selector:(env:Environment)=>T,callback:()=>void){let before=selector(this.environment());const listener=()=>{const after=selector(this.environment());if(!equal(before,after)){before=after;callback();}};this.listeners.add(listener);return ()=>{this.listeners.delete(listener);};}
 private recompute(){const entries=Object.entries(this.derived);for(let iteration=0;iteration<=entries.length;iteration++){let changed=false;for(const [path,expression]of entries){const value=this.expressions.evaluate(expression.expr,this.environment());if(!equal(getPath(this.state,path),value)){this.state=setPath(this.state,path,value);changed=true;}}if(!changed)return;}throw new Error('Derived state cycle or non-convergent calculation');}
 private flush(){if(!this.changed)return;this.recompute();this.changed=false;for(const fn of this.listeners)fn();}
 dispose(){this.disposed=true;this.listeners.clear();}
}
