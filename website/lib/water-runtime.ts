import {advanceSpring,clamp,lampFalloff,poolHomes,poolTarget,safelight,WaterField,type Box,type PoolHome,type Spring} from './water-model';
import {WaterRenderer} from './water-renderer';
type Body={x:Spring;y:Spring;scale:Spring;roll:Spring;pitch:Spring;alpha:Spring};
type Particle={x:number;y:number;vx:number;vy:number;life:number;ttl:number;radius:number};
export type WaterRuntime={setLifted:(index:number|null)=>void;disturb:(x:number,y:number,power?:number)=>void;setPointer:(x:number,y:number,inside:boolean)=>void;setPaused:(paused:boolean)=>void;dispose:()=>void};
const KEYS=['x','y','scale','roll','pitch','alpha'] as const;
/** A print travels to the easel and back as one CSS transition, which the browser runs off the main thread at the final sharpness. */
const LIFT_MS=780,RETURN_MS=640,PARK_AFTER=1.3;
/** Room kept between a floating print (and the name tag on its top edge) and the headline text. */
const CLEARANCE=22;
const pose=(x:number,y:number,roll:number,scale:number)=>`translate3d(calc(-50% + ${x.toFixed(2)}px),calc(-50% + ${y.toFixed(2)}px),0) rotateZ(${roll.toFixed(2)}deg) scale(${scale.toFixed(5)})`;
/** Prints drift in a bath under a fixed safelight. One may be lifted out; the rest wait in the water. */
export function createWaterRuntime(stage:HTMLElement,initial:number|null,initialPaused=false):WaterRuntime{
 const canvas=stage.querySelector<HTMLCanvasElement>('.water-canvas')!,spray=stage.querySelector<HTMLCanvasElement>('.water-spray')!;
 const cards=Array.from(stage.querySelectorAll<HTMLElement>('.case-card'));
 const copy=stage.querySelector<HTMLElement>('.pool-copy');
 const ctx=spray.getContext('2d');const field=new WaterField();let renderer:WaterRenderer|null=null;
 let lifted=initial,paused=initialPaused,visible=true,dead=false,lost=false,frame=0,initialization=0,last=0,time=0,accumulator=0,width=1,height=1,cardWidth=1,cardHeight=1,quality=1,slowFrames=0;
 let homes:PoolHome[]=poolHomes(1.6),lamp=safelight(1.6),lift=1,parkAt=Infinity,clear:Box|null=null;
 // Prints whose transform belongs to a transition: the one on the easel (Infinity) and any on their way back (until that time).
 const held=new Map<number,number>();
 const cardUniforms=new Float32Array(cards.length*4),pointer={x:.5,y:.5,inside:false},torch:Spring={value:0,velocity:0};
 const bodies:Body[]=cards.map(()=>Object.fromEntries(KEYS.map(key=>[key,{value:key==='scale'||key==='alpha'?1:0,velocity:0}])) as Body);
 const lit=cards.map(()=>-1);const particles:Particle[]=[];
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
 const canAnimate=()=>!dead&&!paused&&!reduced.matches&&visible&&!document.hidden&&!lost;
 function initRenderer(){try{renderer=new WaterRenderer(canvas,field);}catch{renderer=null;}}
 /** The headline, its paragraph and its button, as they are actually laid out: prints float around them, never over them. */
 function measureCopy(){
  clear=null;if(!copy||typeof copy.getBoundingClientRect!=='function'||typeof stage.getBoundingClientRect!=='function')return;
  const origin=stage.getBoundingClientRect();let left=Infinity,top=Infinity,right=-Infinity,bottom=-Infinity;
  for(const element of [copy.querySelector('h1>*')??copy.querySelector('h1'),...Array.from(copy.querySelectorAll('p,a'))]){
   const box=element?.getBoundingClientRect();if(!box||!box.width)continue;
   left=Math.min(left,box.left);top=Math.min(top,box.top);right=Math.max(right,box.right);bottom=Math.max(bottom,box.bottom);
  }
  if(right>left)clear={left:left-origin.left-width/2-CLEARANCE,top:top-origin.top-height/2-CLEARANCE,right:right-origin.left-width/2+CLEARANCE,bottom:bottom-origin.top-height/2+CLEARANCE};
 }
 function resize(){
  width=Math.max(1,stage.clientWidth);height=Math.max(1,stage.clientHeight);cardWidth=cards[0]?.offsetWidth||width*.8;cardHeight=cards[0]?.offsetHeight||height*.7;
  lift=typeof getComputedStyle==='function'?Number.parseFloat(getComputedStyle(stage).getPropertyValue('--lift'))||1:1;
  measureCopy();
  const aspect=width/height;homes=poolHomes(aspect);lamp=safelight(aspect);stage.dataset.poolLayout=aspect>=1.25?'wide':aspect>=.8?'medium':'tall';
  stage.style.setProperty('--lamp-x',`${(lamp.x*100).toFixed(2)}%`);stage.style.setProperty('--lamp-y',`${(lamp.y*100).toFixed(2)}%`);
  // Type hung on a floating print is sized against the print's own scale, so it reads the same on every screen.
  cards.forEach((card,i)=>card.style.setProperty('--float',Math.max(.1,Math.min(.7,homes[i%homes.length].size*width/Math.max(1,cardWidth))).toFixed(4)));
  quality=Math.min(window.devicePixelRatio||1,2);renderer?.resize(width,height,quality);
  const ratio=Math.min(quality,1.4);spray.width=Math.round(width*ratio);spray.height=Math.round(height*ratio);ctx?.setTransform(ratio,0,0,ratio,0,0);
 }
 function drawCards(dt:number,snap=false){
  const moving=canAnimate(),aspect=width/height;
  for(let i=0;i<cards.length;i++){
   const target=poolTarget(i,lifted,homes,width,height,cardWidth,moving?time:0,lift,clear,cardHeight),body=bodies[i],up=i===lifted;
   if(snap&&!up)held.delete(i);
   for(const key of KEYS){if(snap){body[key].value=target[key];body[key].velocity=0;}else advanceSpring(body[key],target[key],dt,key==='alpha'?70:up?62:38,key==='alpha'?17:up?15:11);}
   const u=clamp(.5+body.x.value/width,0,1),v=clamp(.5+body.y.value/height,0,1);
   // A lifted print is out of the bath: it neither bobs nor tilts with the surface.
   const afloat=moving&&!up&&!held.has(i);
   const wave=afloat?field.sample(u,v):0,tilt=afloat?field.sample(u+.03,v)-field.sample(u-.03,v):0;
   const bob=afloat?clamp(wave*3.2,-4,4)+Math.sin(time*.72+i*1.7)*.9:0,roll=body.roll.value+(afloat?clamp(tilt*2.4,-1.1,1.1):0);
   if(held.has(i)){if(!up&&time>=held.get(i)!){held.delete(i);cards[i].style.transition='';}}
   else{if(snap)cards[i].style.transition='';cards[i].style.transform=pose(body.x.value,body.y.value+bob,roll,body.scale.value);}
   cards[i].style.opacity=clamp(body.alpha.value,0,1).toFixed(3);
   // Light reaching this print: the fixed safelight, plus the pointer when it is over the bath.
   const light=clamp(.5+lampFalloff(u,v,lamp.x,lamp.y,aspect,1.2)*.45+lampFalloff(u,v,pointer.x,pointer.y,aspect,16)*torch.value*.4,0,1);
   if(Math.abs(light-lit[i])>.012){lit[i]=light;cards[i].style.setProperty('--lit',light.toFixed(3));}
   const s=body.scale.value;cardUniforms.set(up?[u,v,0,0]:[u,v,cardWidth*s/width*.5,cardHeight*s/height*.5],i*4);
  }
 }
 function burst(x:number,y:number,strength=1){for(let i=0;i<Math.round(26*strength);i++){const angle=Math.random()*Math.PI*2,speed=(40+Math.random()*110)*strength;particles.push({x:x*width,y:y*height,vx:Math.cos(angle)*speed,vy:-Math.abs(Math.sin(angle)*speed)-35,life:0,ttl:.45+Math.random()*.55,radius:.65+Math.random()*1.6});}if(particles.length>180)particles.splice(0,particles.length-180);}
 function drawSpray(dt:number){
  if(!ctx)return;ctx.clearRect(0,0,width,height);if(!particles.length)return;ctx.save();ctx.beginPath();ctx.rect(0,0,width,height);
  if(lifted!==null){const b=bodies[lifted],w=cardWidth*b.scale.value,h=cardHeight*b.scale.value;ctx.rect(width*.5+b.x.value-w*.5,height*.5+b.y.value-h*.5,w,h);}
  ctx.clip('evenodd');
  for(let i=particles.length-1;i>=0;i--){const p=particles[i];p.life+=dt;if(p.life>=p.ttl){particles.splice(i,1);continue;}p.vy+=235*dt;p.x+=p.vx*dt;p.y+=p.vy*dt;p.vx*=Math.exp(-1.4*dt);ctx.fillStyle=`rgba(255,196,176,${.7*(1-p.life/p.ttl)})`;ctx.beginPath();ctx.ellipse(p.x,p.y,p.radius,Math.max(.6,p.radius*1.6),Math.atan2(p.vy,p.vx),0,Math.PI*2);ctx.fill();}
  ctx.restore();
 }
 function draw(){
  if(renderer?.draw(time,cardUniforms,lamp.x,lamp.y,pointer.x,pointer.y,torch.value)&&stage.dataset.waterRenderer!=='webgl')stage.dataset.waterRenderer='webgl';
 }
 function render(now:number){
  frame=0;if(!canAnimate())return;
  // A precise drag inside a lifted print gets every frame to itself.
  if(stage.dataset.controlDragging==='true'){last=now;frame=requestAnimationFrame(render);return;}
  const raw=last?(now-last)/1000:1/60;const dt=clamp(raw,0,1/30);last=now;time+=dt;accumulator+=dt;
  let steps=0;while(accumulator>=1/60&&steps<3){field.step();accumulator-=1/60;steps++;}
  advanceSpring(torch,pointer.inside&&lifted===null?1:0,dt,26,9);
  drawCards(dt);draw();drawSpray(dt);
  if(raw>.028)slowFrames++;else slowFrames=Math.max(0,slowFrames-1);
  if(slowFrames>70&&quality>.7){quality*=.82;renderer?.resize(width,height,quality);slowFrames=0;}
  // Once a print is on the easel and the splash has settled, the bath rests: nothing behind the print needs redrawing.
  if(lifted!==null&&time>=parkAt){stage.dataset.waterMotion='still';return;}
  frame=requestAnimationFrame(render);
 }
 function sync(){
  if(frame){cancelAnimationFrame(frame);frame=0;}last=0;stage.dataset.waterMotion=canAnimate()?'running':'still';
  if(canAnimate()&&!initialization)frame=requestAnimationFrame(render);else{torch.value=0;drawCards(0,true);draw();ctx?.clearRect(0,0,width,height);}
 }
 const onLost=(event:Event)=>{event.preventDefault();lost=true;renderer?.dispose();renderer=null;stage.dataset.waterRenderer='fallback';sync();};
 const onRestored=()=>{if(dead)return;lost=false;initRenderer();resize();draw();sync();};
 canvas.addEventListener('webglcontextlost',onLost);canvas.addEventListener('webglcontextrestored',onRestored);
 stage.dataset.waterRenderer='fallback';
 resize();drawCards(0,true);stage.dataset.waterReady='true';
 // Let the fallback and the positioned prints paint before compiling the shader.
 initialization=requestAnimationFrame(()=>{
  initialization=requestAnimationFrame(()=>{
   initialization=0;if(dead||lost)return;
   initRenderer();renderer?.resize(width,height,quality);draw();sync();
  });
 });
 // The headline reflows when its font arrives or the language changes, without the tray changing size.
 const sizeObserver=new ResizeObserver(()=>{if(dead)return;resize();if(!canAnimate())sync();});sizeObserver.observe(stage);if(copy)sizeObserver.observe(copy);
 const intersection=typeof IntersectionObserver!=='undefined'?new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting??true;sync();},{threshold:0}):null;intersection?.observe(stage);
 const onVisibility=()=>sync(),onPreference=()=>sync();document.addEventListener('visibilitychange',onVisibility);reduced.addEventListener('change',onPreference);sync();
 /**
  * Where a lifted print rests: centred in the part of the tray that is on screen. On a phone the tray is
  * taller than the screen, and its own centre can be out of sight.
  */
 function easel(){
  if(typeof stage.getBoundingClientRect!=='function')return 0;
  const half=cardHeight*lift/2,room=half+64;
  return clamp((window.innerHeight||height)/2-stage.getBoundingClientRect().top,room,Math.max(room,height-room))-height/2;
 }
 /** Water breaks where a print leaves or re-enters the bath. */
 function splash(index:number){const home=homes[index%homes.length],x=clamp(.5+home.x,0,1),y=clamp(.5+home.y,0,1);field.splash(x,y,home.size*.5,home.size*.5*cardHeight/Math.max(1,cardWidth)*width/height,.8);burst(x,y,.5);}
 return {
  setLifted(index){
   const previous=lifted;if(index===previous)return;lifted=index;const live=canAnimate();
   if(previous!==null){
    // Back to its place in the bath; the springs pick it up from there once the transition has ended.
    const home=poolTarget(previous,index,homes,width,height,cardWidth,live?time:0,lift,clear,cardHeight),body=bodies[previous];
    for(const key of KEYS){body[key].value=home[key];body[key].velocity=0;}
    cards[previous].style.transition=live?`transform ${RETURN_MS}ms cubic-bezier(.3,.7,.2,1)`:'';cards[previous].style.transform=pose(home.x,home.y,home.roll,home.scale);
    if(live)held.set(previous,time+RETURN_MS/1000);else held.delete(previous);
   }
   if(index!==null){
    const body=bodies[index],rest=easel();for(const key of KEYS){body[key].value=key==='scale'?lift:key==='alpha'?1:key==='y'?rest:0;body[key].velocity=0;}
    // The controls around the print follow it through this offset.
    stage.style.setProperty('--lift-y',`${rest.toFixed(1)}px`);
    cards[index].style.transition=live?`transform ${LIFT_MS}ms cubic-bezier(.2,.86,.24,1)`:'';cards[index].style.transform=pose(0,rest,0,lift);cards[index].style.opacity='1';held.set(index,Infinity);
   }
   parkAt=time+PARK_AFTER;
   if(live){if(previous!==null)splash(previous);if(index!==null)splash(index);if(!frame)sync();}else sync();
  },
  disturb(x,y,power=.3){if(!canAnimate())return;field.disturb(x,y,power,.022);if(power>.65)burst(x,y,.25);},
  setPointer(x,y,inside){pointer.x=clamp(x,0,1);pointer.y=clamp(y,0,1);pointer.inside=inside;},
  setPaused(value){paused=value;sync();},
  dispose(){
   if(dead)return;dead=true;if(frame)cancelAnimationFrame(frame);if(initialization)cancelAnimationFrame(initialization);sizeObserver.disconnect();intersection?.disconnect();
   document.removeEventListener('visibilitychange',onVisibility);reduced.removeEventListener('change',onPreference);canvas.removeEventListener('webglcontextlost',onLost);canvas.removeEventListener('webglcontextrestored',onRestored);
   renderer?.dispose();ctx?.clearRect(0,0,width,height);
   for(const card of cards){card.style.transition='';card.style.removeProperty('transform');card.style.removeProperty('opacity');card.style.removeProperty('--lit');card.style.removeProperty('--float');}
   stage.style.removeProperty('--lamp-x');stage.style.removeProperty('--lamp-y');stage.style.removeProperty('--lift-y');delete stage.dataset.waterReady;delete stage.dataset.waterRenderer;delete stage.dataset.waterMotion;delete stage.dataset.poolLayout;
  }
 };
}
