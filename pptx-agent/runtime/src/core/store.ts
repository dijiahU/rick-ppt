import type {Dict,Environment,Expression} from './types';
import {equal,getPath,setPath,safeObject} from './state';
import {Expressions} from './expressions';
type Snapshot={state:Dict;data:Dict};
export class SceneStore {
 private initial:Dict;private initialData:Dict;private state:Dict;private data:Dict={};private listeners=new Set<()=>void>();private nesting=0;private changed=false;private undoStack:Snapshot[]=[];private redoStack:Snapshot[]=[];private disposed=false;
 constructor(initial:Dict={},private derived:Record<string,Expression>={},public expressions=new Expressions(),data:Dict={}){safeObject(initial);safeObject(data);this.initialData=structuredClone(data);this.data=structuredClone(data);this.initial=structuredClone(initial);this.state=structuredClone(initial);this.recompute();}
 environment(locals:Dict={},event:Dict={}):Environment{return {state:this.state,data:this.data,locals,event};}
 get(path?:string){return path?getPath(this.state,path):this.state;}
 getData(){return this.data;}
 snapshot():Snapshot{return structuredClone({state:this.state,data:this.data});}
 /** Plugin functions are registered before a Runtime activates its derived state. */
 activateDerived(derived:Record<string,Expression>){const before=this.derived;try{this.derived=derived;this.batch(()=>{this.changed=true;});}catch(error){this.derived=before;throw error;}}
 restore(snap:Snapshot){safeObject(snap);if(!snap.state||!snap.data)throw new Error('Invalid state snapshot');this.batch(()=>{this.state=structuredClone(snap.state);this.data=structuredClone(snap.data);this.changed=true;});}
 set(path:string,value:any){if(this.disposed)return;const next=setPath(this.state,path,value);if(equal(this.state,next))return;this.batch(()=>{this.state=next;this.changed=true;});}
 setData(name:string,value:any){if(this.disposed)return;safeObject({[name]:value});if(equal(this.data[name],value))return;this.batch(()=>{this.data={...this.data,[name]:structuredClone(value)};this.changed=true;});}
 batch(fn:()=>void,history=false){if(this.disposed)return;const outer=this.nesting===0,before=outer?{state:this.state,data:this.data,changed:this.changed}:null;const undo=history&&outer?this.snapshot():null;this.nesting++;try{fn();this.nesting--;if(outer){this.flush();if(undo){this.undoStack.push(undo);if(this.undoStack.length>100)this.undoStack.shift();this.redoStack=[];}}}catch(error){this.nesting=Math.max(0,this.nesting-(this.nesting>0?1:0));if(before){this.state=before.state;this.data=before.data;this.changed=before.changed;}throw error;}}
 reset(){this.batch(()=>{const status=this.state._dataStatus;this.state=structuredClone(this.initial);if(status)this.state._dataStatus=status;this.changed=true;});}
 undo(){const v=this.undoStack.at(-1);if(v){const current=this.snapshot();this.restore(v);this.undoStack.pop();this.redoStack.push(current);}}
 redo(){const v=this.redoStack.at(-1);if(v){const current=this.snapshot();this.restore(v);this.redoStack.pop();this.undoStack.push(current);}}
 subscribe<T>(selector:(env:Environment)=>T,callback:()=>void){let before=selector(this.environment());const listener=()=>{const after=selector(this.environment());if(!equal(before,after)){before=after;callback();}};this.listeners.add(listener);return ()=>{this.listeners.delete(listener);};}
 private recompute(){const entries=Object.entries(this.derived);for(let iteration=0;iteration<=entries.length;iteration++){let changed=false;for(const [path,expression]of entries){const value=this.expressions.evaluate(expression.expr,this.environment());if(!equal(getPath(this.state,path),value)){this.state=setPath(this.state,path,value);changed=true;}}if(!changed)return;}throw new Error('Derived state cycle or non-convergent calculation');}
 private flush(){if(!this.changed)return;this.recompute();this.changed=false;for(const fn of this.listeners)fn();}
 dispose(){this.disposed=true;this.listeners.clear();}
}
