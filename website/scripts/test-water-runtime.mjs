// Lifecycle of the actual runtime, with deterministic frames and a renderer fixture.
import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import ts from 'typescript';
const modules={};function load(path){const exports={};new Function('require','exports',ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(name=>modules[name],exports);return exports;}
modules['./water-model']=load('lib/water-model.ts');const instances=[];let failInit=false;
class Renderer{constructor(canvas,field){if(failInit)throw Error('WebGL unavailable');this.field=field;this.draws=0;this.disposals=0;instances.push(this);}resize(){}draw(){this.draws++;return true;}dispose(){this.disposals++;}}
modules['./water-renderer']={WaterRenderer:Renderer};const {createWaterRuntime}=load('lib/water-runtime.ts');
const frames=new Map();let seq=0;globalThis.requestAnimationFrame=fn=>{frames.set(++seq,fn);return seq;};globalThis.cancelAnimationFrame=id=>frames.delete(id);
const doc=new EventTarget();doc.hidden=false;globalThis.document=doc;const preference=new EventTarget();preference.matches=false;globalThis.window={devicePixelRatio:2,matchMedia:()=>preference};
const observers=[];globalThis.ResizeObserver=class{constructor(cb){this.cb=cb;observers.push(this);}observe(){}disconnect(){this.disconnected=true;}};globalThis.IntersectionObserver=class{constructor(cb){this.cb=cb;observers.push(this);}observe(){}disconnect(){this.disconnected=true;}};
const canvas=new EventTarget();const ctx=new Proxy({},{get:(target,key)=>target[key]??(()=>{})});const spray={getContext:()=>ctx};
const cards=Array.from({length:4},()=>({offsetWidth:800,offsetHeight:450,style:{setProperty(key,value){this[key]=value;},removeProperty(key){delete this[key];}}}));
const stage={clientWidth:1200,clientHeight:560,dataset:{},style:{setProperty(key,value){this[key]=value;},removeProperty(key){delete this[key];}},querySelector:name=>name==='.water-canvas'?canvas:spray,querySelectorAll:()=>cards};
function tick(now){const item=frames.entries().next().value;assert.ok(item);frames.delete(item[0]);item[1](now);}
const place=card=>{const [,x,y]=card.style.transform.match(/calc\(-50% \+ (-?[\d.]+)px\),calc\(-50% \+ (-?[\d.]+)px\)/);return {x:Number(x),y:Number(y),scale:Number(card.style.transform.match(/scale\(([\d.]+)\)/)[1])};};
const runtime=createWaterRuntime(stage,null);assert.equal(stage.dataset.waterReady,'true');assert.equal(stage.dataset.poolLayout,'wide');assert.ok(stage.style['--lamp-x'].endsWith('%'));assert.equal(frames.size,1);
// At rest every print floats at its own place, small, lit by the safelight.
const rest=cards.map(place);assert.equal(new Set(rest.map(p=>`${Math.round(p.x)}/${Math.round(p.y)}`)).size,4);assert.ok(rest.every(p=>p.scale<=.6));assert.ok(cards.every(card=>Number(card.style['--lit'])>0&&Number(card.style['--float'])>0));
const drain=(from,limit=400)=>{let n=0;while(frames.size&&n<limit)tick(from+(++n)*16.7);return n;};
assert.equal(stage.dataset.waterRenderer,'fallback');
assert.equal(instances.length,0,'Do not compile shaders before the first paint');
tick(983);
assert.equal(instances.length,0,'Let the browser paint the fallback and the positioned prints first');
tick(1000);
assert.equal(instances[0].draws,1,'Draw the first frame before revealing WebGL');
assert.equal(stage.dataset.waterRenderer,'webgl');
runtime.setLifted(1);assert.ok(instances[0].field.velocity.some(v=>v!==0),'Lifting a print breaks the water');
// The lift is handed to a CSS transition: the target pose is written once and the print is not touched again.
const lifted=place(cards[1]);assert.ok(Math.abs(lifted.x)<.01&&Math.abs(lifted.y)<.01&&lifted.scale===1,'The lifted print is sent centred at full size');assert.equal(stage.style['--lift-y'],'0.0px');assert.ok(cards[1].style.transition.startsWith('transform'));
const sent=cards[1].style.transform;tick(1017);assert.equal(cards[1].style.transform,sent,'A print in transit is left to the compositor');assert.ok(instances[0].draws>0);
const dragDraws=instances[0].draws;stage.dataset.controlDragging='true';tick(1034);assert.equal(instances[0].draws,dragDraws,'Water drawing yields during a control gesture');delete stage.dataset.controlDragging;tick(1051);assert.ok(instances[0].draws>dragDraws,'Water resumes when the gesture ends');
// Once the splash has settled the bath rests: no frames are scheduled behind an open print.
const ran=drain(1051);assert.ok(ran>40&&ran<200,`The bath keeps moving for about a second after the lift (${ran} frames)`);assert.equal(frames.size,0);assert.equal(stage.dataset.waterMotion,'still');assert.equal(cards[1].style.transform,sent);assert.ok(Number(cards[0].style.opacity)<.5,'The other prints recede');
// Returning it restarts the bath, sends the print home by transition, then the springs take it back.
runtime.setLifted(null);assert.equal(frames.size,1);assert.ok(cards[1].style.transition.startsWith('transform'));const home=place(cards[1]);assert.ok(home.scale<.5&&Math.hypot(home.x,home.y)>50,'The print is sent back to its place in the tray');
const back=cards[1].style.transform;tick(9000);tick(9017);assert.equal(cards[1].style.transform,back,'Untouched while it travels');
for(let n=1;n<=120;n++)tick(9017+n*16.7);assert.equal(cards[1].style.transition,'','The transition is released when the print is home');assert.notEqual(cards[1].style.transform,back,'The print floats again');assert.ok(Math.hypot(place(cards[1]).x-home.x,place(cards[1]).y-home.y)<40,'It resumes from where it landed');
// The pointer is a second light: a print near it is lit more than without it.
for(let n=1;n<=120;n++)tick(11100+n*16.7);const dim=Number(cards[2].style['--lit']);const spot=place(cards[2]);runtime.setPointer(.5+spot.x/1200,.5+spot.y/560,true);for(let n=1;n<=120;n++)tick(13200+n*16.7);assert.ok(Number(cards[2].style['--lit'])>dim+.05,'Pointing at a print brightens it');runtime.setPointer(.5,.5,false);
runtime.setPaused(true);assert.equal(frames.size,0);assert.equal(stage.dataset.waterMotion,'still');const energy=instances[0].field.energy();runtime.disturb(.5,.5,1);assert.equal(instances[0].field.energy(),energy);runtime.setLifted(2);assert.ok(Math.abs(place(cards[2]).x)<.01&&Math.abs(place(cards[2]).scale-1)<.001);assert.equal(cards[2].style.transition,'','Without motion a print is lifted at once, with no transition');runtime.setPaused(false);assert.equal(frames.size,1);
doc.hidden=true;doc.dispatchEvent(new Event('visibilitychange'));assert.equal(frames.size,0);doc.hidden=false;doc.dispatchEvent(new Event('visibilitychange'));assert.equal(frames.size,1);
const visibility=observers.find(o=>o instanceof IntersectionObserver);visibility.cb([{isIntersecting:false}]);assert.equal(frames.size,0);visibility.cb([{isIntersecting:true}]);assert.equal(frames.size,1);
preference.matches=true;preference.dispatchEvent(new Event('change'));assert.equal(frames.size,0);preference.matches=false;preference.dispatchEvent(new Event('change'));assert.equal(frames.size,1);
canvas.dispatchEvent(new Event('webglcontextlost',{cancelable:true}));assert.equal(frames.size,0);assert.equal(instances[0].disposals,1);assert.equal(stage.dataset.waterRenderer,'fallback');canvas.dispatchEvent(new Event('webglcontextrestored'));assert.equal(instances.length,2);assert.equal(frames.size,1);assert.equal(stage.dataset.waterRenderer,'webgl');
runtime.dispose();assert.equal(frames.size,0);assert.equal(instances[1].disposals,1);assert.ok(observers.every(o=>o.disconnected));assert.ok(cards.every(c=>!c.style.transform&&!c.style['--lit']&&!c.style['--float']));assert.equal(stage.dataset.waterReady,undefined);assert.equal(stage.style['--lamp-x'],undefined);doc.dispatchEvent(new Event('visibilitychange'));preference.dispatchEvent(new Event('change'));assert.equal(frames.size,0);runtime.dispose();assert.equal(instances[1].disposals,1);
{const tall={clientWidth:390,clientHeight:1320,dataset:{},style:{setProperty(key,value){this[key]=value;},removeProperty(key){delete this[key];}},getBoundingClientRect:()=>({top:-100}),querySelector:name=>name==='.water-canvas'?canvas:spray,querySelectorAll:()=>cards.map(()=>({offsetWidth:367,offsetHeight:620,style:{setProperty(key,value){this[key]=value;},removeProperty(key){delete this[key];}}}))};
 globalThis.window.innerHeight=844;const phone=createWaterRuntime(tall,null);phone.setLifted(0);
 // Screen centre is 522px down the tray (422 + 100 scrolled); the tray's own centre is at 660.
 assert.equal(tall.style['--lift-y'],'-138.0px','On a tray taller than the screen the print is lifted to where the visitor is looking');phone.dispose();assert.equal(frames.size,0,'Unmount cancels deferred rendering initialization');delete globalThis.window.innerHeight;}
{failInit=true;
 const fallback=createWaterRuntime(stage,null);tick(2000);tick(2017);
 assert.equal(stage.dataset.waterRenderer,'fallback','Failed WebGL keeps the visible fallback');
 assert.equal(stage.dataset.waterReady,'true');
 fallback.dispose();
}
console.log('PASS: real runtime frame scheduling, four floating prints at distinct places, lift and return by transition with a splash, receding neighbours, the bath resting behind an open print, handover back to the springs, pointer light, pause/resume, input suppression while paused, hidden/offscreen/reduced-motion suspension, WebGL loss/restoration, observer/listener/renderer teardown and idempotent disposal.');
