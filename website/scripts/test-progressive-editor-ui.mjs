// Actual React event/state tests in a DOM emulator. Not browser/playback QA.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';
import ts from 'typescript';
import {unzipSync,strFromU8} from 'fflate';
const dom=new JSDOM('<!doctype html><html><body><main id="root"></main></body></html>',{url:'https://test.local'});
for(const key of ['window','document','HTMLElement','Node','DOMParser','MouseEvent','Event','KeyboardEvent','localStorage'])globalThis[key]=dom.window[key];
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
dom.window.HTMLElement.prototype.setPointerCapture=function(){};
const React=await import('react'),jsx=await import('react/jsx-runtime'),{createRoot}=await import('react-dom/client');const {act}=React;
const directory=process.argv[2];assert.ok(directory,'Pass local test artifact directory');const base=JSON.parse(readFileSync(directory+'/source.json')),after=JSON.parse(readFileSync(directory+'/merged.json'));const later=JSON.parse(readFileSync(directory+'/growing.json'));let current=base,savedBody=null;const requests=[];
globalThis.fetch=async(url,options={})=>{requests.push(String(url));if(String(url).includes('/native-edits?sha256=')){const bytes=readFileSync(directory+(String(url).includes(base.sha256)?'/source.pptx':'/merged.pptx'));return new Response(bytes);}if(String(url).endsWith('/native-edits')&&options.method==='POST'){savedBody=JSON.parse(options.body);return Response.json({id:savedBody.id,status:'queued'});}if(String(url).includes('/native-edits?request=')){current=after;return Response.json({id:savedBody.id,status:'complete',resultSha256:after.sha256});}if(String(url).includes('/canvas'))return Response.json({snapshot:current,versions:[{sha256:current.sha256,createdAt:current.createdAt,pages:1}],canEdit:true});throw Error('Unexpected fetch '+url);};
const modules={react:React,'react/jsx-runtime':jsx,'@/app/language':{useLanguage:()=>({locale:'en'})},'@/lib/upload-client':{uploadFiles:async()=>['upload']},'./canvas-workbench.css':{},'./native-editor.css':{},fflate:{unzipSync,strFromU8}};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
modules['@/lib/visual-edits']=load('lib/visual-edits.ts');modules['./visual-edits']=modules['@/lib/visual-edits'];modules['@/lib/native-edits']=load('lib/native-edits.ts');modules['@/lib/native-canvas-client']=load('lib/native-canvas-client.ts');modules['./native-editor']=load('app/jobs/[id]/native-editor.tsx');const Workbench=load('app/jobs/[id]/canvas-workbench.tsx').default;
const parsed=modules['@/lib/native-canvas-client'].readNativeCanvas(readFileSync(directory+'/source.pptx'),base);assert.ok(parsed['1:2'].canText);assert.ok(parsed['1:11'].canTransform);assert.equal(parsed['1:3'].canDelete,false);assert.equal(parsed['1:5'].cells.length,4);

const originalTimeout=globalThis.setTimeout,canvasPolls=[];globalThis.setTimeout=(fn,ms,...args)=>ms===10000?(canvasPolls.push(fn),987654):originalTimeout(fn,ms,...args);
let submitted=0;const root=createRoot(document.getElementById('root'));const settle=async()=>act(async()=>{await new Promise(r=>originalTimeout(r,20));});
await act(async()=>{root.render(React.createElement(Workbench,{id:'11111111-1111-4111-8111-111111111111',status:'running',progress:null,onSubmitted(){submitted++;},conversation:React.createElement('p',null,'Full conversation history')}));});await settle();
async function click(el){assert.ok(el);await act(async()=>el.dispatchEvent(new MouseEvent('click',{bubbles:true})));await settle();}
async function input(el,text){assert.ok(el);await act(async()=>{Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype,'value').set.call(el,text);el.dispatchEvent(new Event('input',{bubbles:true}));});}
assert.match(document.querySelector('.canvas-live-edit-status').textContent,/1 pages ready to edit/);
await click(document.getElementById('canvas-edit-tab-11111111-1111-4111-8111-111111111111'));
await click([...document.querySelectorAll('.native-object-list button')].find(b=>b.textContent.includes('Original title')));
const text=document.querySelector('textarea[aria-label="Object text"]');assert.equal(text.disabled,false);await input(text,'Edited native title');assert.equal(document.querySelector('.native-save .canvas-primary').disabled,false);
// The author publishes another page while the user is typing on the unchanged first page.
current=later;assert.ok(canvasPolls.length);await act(async()=>{await canvasPolls.shift()();});await settle();assert.equal(document.querySelector('textarea[aria-label="Object text"]').value,'Edited native title');assert.equal(document.querySelector('.native-save .canvas-primary').disabled,false);
await click(document.querySelector('.native-save .canvas-primary'));await settle();assert.ok(savedBody);assert.equal(savedBody.baseSha256,base.sha256);assert.equal(savedBody.patches[0].text,'Edited native title');assert.ok(submitted>0);assert.match(document.querySelector('.canvas-notice').textContent,/saved and protected/);assert.match(document.querySelector('.canvas-live-edit-status').textContent,/2 pages ready to edit/);
// The unfinished third page stays visible as a placeholder, with direct controls disabled.
await click(document.querySelector('button[aria-label="Slide 3"]'));assert.match(document.querySelector('.canvas-wait h2').textContent,/being made/);assert.ok(!document.querySelector('.native-properties textarea')||document.querySelector('.native-properties textarea').disabled);
await act(async()=>root.unmount());globalThis.setTimeout=originalTimeout;dom.window.close();
console.log('PASS: actual React ready-page editing during production, preservation of drafts as later pages arrive, native save from unchanged earlier revision, protected-page receipt and unfinished-page placeholder/lock. DOM emulator, not browser QA.');
