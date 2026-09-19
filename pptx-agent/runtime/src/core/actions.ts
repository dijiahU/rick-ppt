import type {Action,Dict,EventContext} from './types';
import {SceneStore} from './store';
import {EventBus} from './events';
import {allowedUrl} from './assets';
export class ActionDispatcher {
 services:Dict={};private count=0;private depth=0;private disposed=false;private timers=new Map<any,()=>void>();private custom=new Map<string,(a:Action,e:Dict)=>void>();
 constructor(private store:SceneStore,private bus:EventBus,private maximum=2000){}
 register(name:string,fn:(a:Action,e:Dict)=>void){if(this.custom.has(name))throw new Error('Duplicate action');this.custom.set(name,fn);}
 async run(actions:Action[],event:Dict={},locals:Dict={},shared=false):Promise<void>{if(this.disposed)return;if(!this.depth&&!shared)this.count=0;this.depth++;try{for(const action of actions){if(++this.count>this.maximum)throw new Error('Action transaction limit exceeded');await this.execute(action,event,locals);}}finally{this.depth--;}}
 private execute(a:Action,event:Dict,locals:Dict):void|Promise<void>{const env=this.store.environment(locals,event);const value=this.store.expressions.value(a.value,env);const path=a.path??'';switch(a.type){
 case 'set':case 'select':this.store.set(path,value);break;
 case 'patch':this.store.batch(()=>{for(const [k,v]of Object.entries(value))this.store.set(path?path+'.'+k:k,v);});break;
 case 'toggle':this.store.set(path,!this.store.get(path));break;
 case 'increment':case 'decrement':this.store.set(path,Number(this.store.get(path)??0)+(a.type==='increment'?1:-1)*Number(value??1));break;
 case 'append':this.store.set(path,[...(this.store.get(path)??[]),value]);break;
 case 'remove':this.store.set(path,(this.store.get(path)??[]).filter((v:any,i:number)=>typeof value==='number'?i!==value:v!==value));break;
 case 'reset':this.services.reset?.();this.store.reset();break;
 case 'undo':this.store.undo();break;case 'redo':this.store.redo();break;
 case 'show':case 'hide':this.store.set(`_visibility.${a.target}`,a.type==='show');break;
 case 'emit':this.bus.emit({type:a.event??a.name??'custom',target:a.target??event.target??'scene',timestamp:performance.now(),value});break;
 case 'sequence':return this.run(a.actions??[],event,locals,true);
 case 'parallel':return Promise.all((a.actions??[]).map(x=>this.run([x],event,locals,true))).then(()=>{});
 case 'condition':return this.run(this.store.expressions.value(a.condition,env)?a.then??[]:a.else??[],event,locals,true);
 case 'delay':return new Promise<void>(resolve=>{const id=setTimeout(()=>{this.timers.delete(id);resolve();},Math.max(0,Math.min(60000,a.duration??0)));this.timers.set(id,resolve);}).then(()=>this.run(a.actions??[],event,locals,true));
 case 'playTimeline':this.services.timeline.play(a.timeline);break;case 'pauseTimeline':this.services.timeline.pause(a.timeline);break;case 'stopTimeline':this.services.timeline.stop(a.timeline);break;case 'seekTimeline':this.services.timeline.seek(a.timeline,this.store.expressions.value(a.time??a.value,env));break;
 case 'startLoop':this.services.compute.start(a.name);break;case 'stopLoop':this.services.compute.stop(a.name);break;
 case 'loadData':case 'refreshData':return this.services.data.load(a.dataSource??a.name);
 case 'call':{const result=this.store.expressions.functions.call(a.name!,this.store.expressions.value(a.args??[],env));if(a.result)this.store.set(a.result,result);break;}
 case 'navigateView':this.store.set(path||'view',value);break;
 case 'openUrl':{const url=allowedUrl(this.store.expressions.value(a.url,env),this.services.base,this.services.allowlist);window.open(url,'_blank','noopener,noreferrer');break;}
 case 'media':this.services.media(a.target,a.method,value);break;
 default:if(!this.custom.has(a.type))throw new Error(`Unknown action: ${a.type}`);this.custom.get(a.type)!(a,event);
 }}
 dispose(){this.disposed=true;for(const [id,resolve]of this.timers){clearTimeout(id);resolve();}this.timers.clear();}
}
