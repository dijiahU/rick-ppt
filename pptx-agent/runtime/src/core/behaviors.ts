import type {Action,Dict,EventContext} from './types';
import {SceneStore} from './store';
export class Behaviors {
 private gestures=new Map<string,Dict>();
 constructor(private definitions:Dict[],private store:SceneStore,private dispatch:(actions:Action[],event:Dict)=>void){}
 handle(event:EventContext,node:Dict){for(const b of this.definitions.filter(b=>b.target===node.id)){
  const key=(event.instanceId??node.id)+':'+b.type+':'+(event.pointerId??0);
  const set=(path:string,value:any)=>this.dispatch([{type:'set',path,value}],event);
  const xPath=b.xPath??'x',yPath=b.yPath??'y';
  const bounded=(v:number,axis:string)=>{const snap=Number(typeof b.snap==='object'?b.snap[axis]??1:b.snap??1);const bounds=b.bounds??{},scalarBounds=['drag','resize'].includes(b.type);const rounded=snap>0?Math.round(v/snap)*snap:v;return Math.max(bounds[axis+'Min']??(scalarBounds?b.min:undefined)??-Infinity,Math.min(bounds[axis+'Max']??(scalarBounds?b.max:undefined)??Infinity,rounded));};
  // Position is measured in the target's parent coordinate system. Size and
  // brush geometry use its own coordinate system. Logical scene coordinates
  // remain in event.x/y for authored interactions.
  const parent={x:event.parentX??event.x??0,y:event.parentY??event.y??0},local={x:event.localX??event.x??0,y:event.localY??event.y??0};
  if(b.type==='hoverHighlight'&&['hoverEnter','hoverLeave'].includes(event.type))set(b.path??'_hover.'+node.id,event.type==='hoverEnter');
  if(b.type==='select'&&event.type==='click')set(b.path??'selected',this.store.expressions.value(b.value??node.id,this.store.environment(event.locals,event)));
  if(['zoom','panZoom'].includes(b.type)&&event.type==='wheel'){const path=b.scalePath??'zoom';set(path,Math.max(b.min??.1,Math.min(b.max??10,(this.store.get(path)??1)*Math.exp(-(event.deltaY??0)*.001))));}
  const scrub=()=>{const t=Math.max(0,Math.min(1,(b.axis==='y'?local.y/(node.height??100):local.x/(node.width??100))));if(b.timeline)this.dispatch([{type:'seekTimeline',timeline:b.timeline,time:(b.min??0)+((b.max??1000)-(b.min??0))*t}],event);else set(b.path??'progress',(b.min??0)+((b.max??1)-(b.min??0))*t);};
  if(event.type==='pointerDown'){
   this.gestures.set(key,{...parent,localX:local.x,localY:local.y,sx:this.store.get(xPath)??node.x??0,sy:this.store.get(yPath)??node.y??0,width:this.store.get(b.widthPath??'width')??node.width??100,height:this.store.get(b.heightPath??'height')??node.height??100});
   if(b.type==='brush')set(b.path??'brush',{x:local.x,y:local.y,width:0,height:0});if(b.type==='scrub')scrub();
  }
  const g=this.gestures.get(key);if(event.type==='pointerMove'&&g){const dx=parent.x-g.x,dy=parent.y-g.y;const proposed={x:bounded(g.sx+dx,'x'),y:bounded(g.sy+dy,'y')};if(b.constraints&&!this.store.expressions.value(b.constraints,this.store.environment({...event.locals,proposed},event)))continue;
   if(['drag','pan','panZoom'].includes(b.type)){const actions:Action[]=[];if(b.axis!=='y')actions.push({type:'set',path:xPath,value:proposed.x});if(b.axis!=='x')actions.push({type:'set',path:yPath,value:proposed.y});this.dispatch(actions,event);}
   if(b.type==='resize'){if(b.axis!=='y')set(b.widthPath??'width',Math.max(1,bounded(g.width+local.x-g.localX,'width')));if(b.axis!=='x')set(b.heightPath??'height',Math.max(1,bounded(g.height+local.y-g.localY,'height')));}
   if(b.type==='brush')set(b.path??'brush',{x:Math.min(g.localX,local.x),y:Math.min(g.localY,local.y),width:Math.abs(local.x-g.localX),height:Math.abs(local.y-g.localY)});
   if(b.type==='scrub')scrub();
  }
  if(['pointerUp','pointerCancel','blur'].includes(event.type))this.gestures.delete(key);
 }}
 reset(){this.gestures.clear();}
}
