'use client';
import {useEffect,useRef} from 'react';
import {createWaterRuntime,type WaterRuntime} from '@/lib/water-runtime';
/** Controls that keep their own pointer gestures; touching them must not ripple the bath. */
const CONTROLS='button,input,textarea,select,a,dialog,[role="button"],.paint-divider,.movable-title,.science-inspector,.case-card.is-lifted';
export function useWaterGallery(lifted:number|null,paused:boolean){
 const stageRef=useRef<HTMLDivElement>(null),runtime=useRef<WaterRuntime|null>(null),latest=useRef(lifted);const lastPointer=useRef({x:0,y:0,time:0});
 useEffect(()=>{latest.current=lifted;runtime.current?.setLifted(lifted);},[lifted]);
 useEffect(()=>{if(!stageRef.current)return;const engine=createWaterRuntime(stageRef.current,latest.current,paused);runtime.current=engine;return()=>{engine.dispose();runtime.current=null;};},[]);
 useEffect(()=>{runtime.current?.setPaused(paused);},[paused]);
 function pointer(event:React.PointerEvent<HTMLDivElement>,press=false){
  const rect=event.currentTarget.getBoundingClientRect();if(!rect.width||!rect.height)return;
  const x=(event.clientX-rect.left)/rect.width,y=(event.clientY-rect.top)/rect.height;
  // The pointer is a second, faint light over the bath. Touch has no hover, so it only ripples.
  if(event.pointerType!=='touch')runtime.current?.setPointer(x,y,true);
  if((event.target as Element).closest(CONTROLS))return;
  const now=performance.now();
  if(!press&&(event.pointerType==='touch'||now-lastPointer.current.time<65||Math.hypot(event.clientX-lastPointer.current.x,event.clientY-lastPointer.current.y)<12))return;
  lastPointer.current={x:event.clientX,y:event.clientY,time:now};runtime.current?.disturb(x,y,press?.85:.17);
 }
 return {stageRef,onPointerMove:(event:React.PointerEvent<HTMLDivElement>)=>pointer(event),onPointerDown:(event:React.PointerEvent<HTMLDivElement>)=>pointer(event,true),onPointerLeave:()=>runtime.current?.setPointer(.5,.5,false)};
}
