// Real React handlers and DOM updates; no browser or model requests.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';
import ts from 'typescript';
const dom=new JSDOM('<main id="root"></main>',{url:'https://test.local'});
for(const key of ['window','document','HTMLElement','Node','MouseEvent','Event'])globalThis[key]=dom.window[key];
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const React=await import('react'),jsx=await import('react/jsx-runtime'),{createRoot}=await import('react-dom/client');
const modules={react:React,'react/jsx-runtime':jsx};
function load(path){const exports={};new Function('require','exports',ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
modules['./use-paint-drag']=load('app/use-paint-drag.ts');modules['./transformer-diagram']=load('app/transformer-diagram.tsx');
let diagramRenders=0;const Diagram=modules['./transformer-diagram'].default;
modules['./transformer-diagram']={...modules['./transformer-diagram'],default:props=>{diagramRenders++;return React.createElement(Diagram,props);}};
const {ScientificCase}=load('app/gallery-cases.tsx'),g=load('lib/gallery-i18n.ts').galleryCopy.en,c=load('lib/landing-i18n.ts').landingCopy.en;
const capture=new WeakMap();HTMLElement.prototype.setPointerCapture=function(id){capture.set(this,id);};HTMLElement.prototype.hasPointerCapture=function(id){return capture.get(this)===id;};HTMLElement.prototype.releasePointerCapture=function(id){if(this.hasPointerCapture(id))capture.delete(this);};
const root=createRoot(document.getElementById('root'));
await React.act(async()=>root.render(React.createElement('section',{className:'case-stage'},React.createElement(ScientificCase,{g,c}))));
const stage=document.querySelector('.case-stage'),painting=document.querySelector('.science-painting'),range=document.querySelector('input[type=range]'),divider=document.querySelector('.paint-divider');
painting.getBoundingClientRect=()=>({width:800,left:0});range.getBoundingClientRect=()=>({width:300,left:0});
async function pointer(el,type,x,extra={}){const event=new MouseEvent(type,{bubbles:true,cancelable:true,button:0,clientX:x});Object.defineProperties(event,{pointerId:{value:1},isPrimary:{value:true},...Object.fromEntries(Object.entries(extra).map(([k,v])=>[k,{value:v}]))});await React.act(async()=>el.dispatchEvent(event));}
const number=()=>Number.parseFloat(painting.style.getPropertyValue('--paint-split'));
const initialRenders=diagramRenders;
await pointer(range,'pointerdown',144);assert.equal(range.value,'48','Grabbing the track must not jump to a new absolute value');assert.equal(stage.dataset.controlDragging,'true');
await pointer(range,'pointermove',174);assert.equal(number(),52.5,'30px over a 300px fine track moves only 4.5 percentage points');assert.equal(range.value,'52.5');
for(let x=175;x<=204;x++)await pointer(range,'pointermove',x);
assert.ok(Math.abs(number()-57)<.001);assert.equal(diagramRenders,initialRenders,'The complex SVG must not rerender for pointer moves');
await pointer(range,'pointerup',204);assert.equal(stage.dataset.controlDragging,undefined);
await pointer(divider,'pointerdown',456);assert.ok(Math.abs(number()-57)<.001,'Grabbing the divider has no jump');await pointer(divider,'pointermove',536);assert.ok(Math.abs(number()-67)<.001,'The divider follows physical pointer distance 1:1');
await pointer(divider,'pointermove',5000);assert.equal(number(),100);await pointer(divider,'pointermove',4992);assert.equal(number(),99,'Clamping does not create reverse-drag lag after an overshoot');
await pointer(divider,'pointercancel',4992);assert.equal(stage.dataset.controlDragging,undefined);const cancelled=number();await pointer(divider,'pointermove',4300);assert.equal(number(),cancelled);
// Keyboard/assistive input retains the native range path.
await React.act(async()=>{Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype,'value').set.call(range,'36.7');range.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(number(),36.7);
await React.act(async()=>document.querySelector('.science-edit-open').click());assert.equal(number(),36.7,'Opening the inspector preserves the paint position');assert.equal(range.value,'36.7');
await React.act(async()=>document.querySelector('.science-reset').click());assert.equal(number(),48);assert.equal(range.value,'48');
await pointer(range,'pointerdown',100);await React.act(async()=>root.unmount());assert.equal(stage.dataset.controlDragging,undefined,'Unmount releases the water freeze');
dom.window.close();console.log('PASS: real React DOM drag events, reduced fine-slider gain, no grab jump, 1:1 divider motion, immediate paint updates without SVG rerenders, boundary reversal, cancellation, keyboard input, inspector/reset preservation and cleanup. DOM emulator, not browser QA.');
