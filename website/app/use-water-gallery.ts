'use client';
import {useEffect,useRef} from 'react';
import {createWaterRuntime,type WaterRuntime} from '@/lib/water-runtime';
export function useWaterGallery(active:number,paused:boolean){
 const stageRef=useRef<HTMLDivElement>(null),runtime=useRef<WaterRuntime|null>(null),latest=useRef(active);const lastPointer=useRef({x:0,y:0,time:0});
 useEffect(()=>{latest.current=active;runtime.current?.setActive(active);},[active]);
 useEffect(()=>{if(!stageRef.current)return;const engine=createWaterRuntime(stageRef.current,latest.current,paused);runtime.current=engine;return()=>{engine.dispose();runtime.current=null;};},[]);
 useEffect(()=>{runtime.current?.setPaused(paused);},[paused]);
 function pointer(event:React.PointerEvent<HTMLDivElement>,press=false){const target=event.target as Element;if(target.closest('button,input,textarea,select,a,dialog,[role="button"],.paint-divider,.movable-title,.science-inspector'))return;const now=performance.now();if(!press&&(event.pointerType==='touch'||now-lastPointer.current.time<65||Math.hypot(event.clientX-lastPointer.current.x,event.clientY-lastPointer.current.y)<12))return;const rect=event.currentTarget.getBoundingClientRect();if(!rect.width||!rect.height)return;lastPointer.current={x:event.clientX,y:event.clientY,time:now};runtime.current?.disturb((event.clientX-rect.left)/rect.width,(event.clientY-rect.top)/rect.height,press?.85:.17);}
 return {stageRef,surge:(index:number,direction:number)=>{runtime.current?.setActive(index);runtime.current?.surge(direction);},onPointerMove:(event:React.PointerEvent<HTMLDivElement>)=>pointer(event),onPointerDown:(event:React.PointerEvent<HTMLDivElement>)=>pointer(event,true)};
}
