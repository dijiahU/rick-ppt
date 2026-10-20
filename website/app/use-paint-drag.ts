'use client';
import {useEffect,useRef} from 'react';
import type {PointerEvent} from 'react';

// Painting changes only one CSS variable and the range value. The editable SVGs
// stay mounted and do not reconcile on every pointer event.
export function usePaintDrag(initial=48){
 const paintingRef=useRef<HTMLDivElement>(null),rangeRef=useRef<HTMLInputElement>(null),value=useRef(initial);
 const gesture=useRef<{pointer:number;x:number;width:number;gain:number;target:HTMLElement;stage:HTMLElement|null}|null>(null);
 function update(next:number){
  value.current=Math.max(0,Math.min(100,next));
  paintingRef.current?.style.setProperty('--paint-split',`${value.current}%`);
  if(rangeRef.current)rangeRef.current.value=String(value.current);
 }
 function end(){const current=gesture.current;gesture.current=null;if(current){current.stage?.removeAttribute('data-control-dragging');if(current.target.hasPointerCapture?.(current.pointer))current.target.releasePointerCapture(current.pointer);}}
 useEffect(()=>()=>end(),[]);
 function start(event:PointerEvent<HTMLElement>,fine:boolean){
  if(event.button!==0||!event.isPrimary)return;
  const target=event.currentTarget,width=(fine?target:paintingRef.current)?.getBoundingClientRect().width||0;
  if(!width)return;
  event.preventDefault();end();if(fine)target.focus({preventScroll:true});const stage=target.closest<HTMLElement>('.case-stage');
  gesture.current={pointer:event.pointerId,x:event.clientX,width,gain:fine?.45:1,target,stage};
  stage?.setAttribute('data-control-dragging','true');target.setPointerCapture(event.pointerId);
 }
 function move(event:PointerEvent<HTMLElement>){const current=gesture.current;if(!current||current.pointer!==event.pointerId)return;event.preventDefault();update(value.current+(event.clientX-current.x)/current.width*100*current.gain);current.x=event.clientX;}
 const events={onPointerMove:move,onPointerUp:(event:PointerEvent<HTMLElement>)=>{if(gesture.current?.pointer===event.pointerId){move(event);end();}},onPointerCancel:(event:PointerEvent<HTMLElement>)=>{if(gesture.current?.pointer===event.pointerId)end();},onLostPointerCapture:(event:PointerEvent<HTMLElement>)=>{if(gesture.current?.pointer===event.pointerId)end();}};
 return {paintingRef,rangeRef,reset:()=>{end();update(initial);},divider:{...events,onPointerDown:(event:PointerEvent<HTMLElement>)=>start(event,false)},range:{...events,onPointerDown:(event:PointerEvent<HTMLElement>)=>start(event,true),onChange:(event:React.ChangeEvent<HTMLInputElement>)=>{if(!gesture.current)update(Number(event.target.value));}},initial};
}
