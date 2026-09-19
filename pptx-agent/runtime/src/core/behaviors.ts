import type {Action,Dict,EventContext} from './types';
import {SceneStore} from './store';
export class Behaviors {
 private gestures=new Map<string,Dict>();
 constructor(private definitions:Dict[],private store:SceneStore,private dispatch:(actions:Action[],event:Dict)=>void){}
 handle(event:EventContext,node:Dict){for(const b of this.definitions.filter(b=>b.target===node.id)){const key=node.id+':'+b.type;const set=(path:string,value:any)=>this.dispatch([{type:'set',path,value}],event);const xPath=b.xPath??'x',yPath=b.yPath??'y';const bounded=(v:number,axis:string)=>{const snap=b.snap??1;const bounds=b.bounds??{};return Math.max(bounds[axis+'Min']??b.min??-Infinity,Math.min(bounds[axis+'Max']??b.max??Infinity,Math.round(v/snap)*snap));};
 if(b.type==='hoverHighlight'&&['hoverEnter','hoverLeave'].includes(event.type))set(b.path??'_hover.'+node.id,event.type==='hoverEnter');
 if(b.type==='select'&&(event.type==='click'||event.type==='keyboard'&&['Enter',' '].includes(event.key??'')))set(b.path??'selected',b.value??node.id);
 if(['zoom','panZoom'].includes(b.type)&&event.type==='wheel'){const path=b.scalePath??'zoom';set(path,Math.max(b.min??.1,Math.min(b.max??10,(this.store.get(path)??1)*Math.exp(-(event.deltaY??0)*.001))));}
 if(event.type==='pointerDown'){this.gestures.set(key,{x:event.x,y:event.y,sx:this.store.get(xPath)??node.x??0,sy:this.store.get(yPath)??node.y??0,width:this.store.get(b.widthPath??'width')??node.width??100,height:this.store.get(b.heightPath??'height')??node.height??100});if(b.type==='brush')set(b.path??'brush',{x:event.x,y:event.y,width:0,height:0});}
 const g=this.gestures.get(key);if(event.type==='pointerMove'&&g){const dx=(event.x??0)-g.x,dy=(event.y??0)-g.y;const proposed={x:bounded(g.sx+dx,'x'),y:bounded(g.sy+dy,'y')};if(b.constraints&&!this.store.expressions.value(b.constraints,this.store.environment({proposed},event)))continue;
 if(['drag','pan','panZoom'].includes(b.type)){if(b.axis!=='y')set(xPath,proposed.x);if(b.axis!=='x')set(yPath,proposed.y);}
 if(b.type==='resize'){set(b.widthPath??'width',Math.max(1,bounded(g.width+dx,'width')));set(b.heightPath??'height',Math.max(1,bounded(g.height+dy,'height')));}
 if(b.type==='brush')set(b.path??'brush',{x:Math.min(g.x,event.x??0),y:Math.min(g.y,event.y??0),width:Math.abs(dx),height:Math.abs(dy)});
 if(b.type==='scrub'){const t=Math.max(0,Math.min(1,((event.x??0)-(node.x??0))/(node.width??100)));if(b.timeline)this.dispatch([{type:'seekTimeline',timeline:b.timeline,time:(b.max??1000)*t}],event);else set(b.path??'progress',(b.min??0)+((b.max??1)-(b.min??0))*t);}}
 if(['pointerUp','pointerCancel','blur'].includes(event.type))this.gestures.delete(key);
 }}
}
