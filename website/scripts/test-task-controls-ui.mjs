// Actual React controls and route requests with isolated fixtures, not production mutations.
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
const {default:Controls,taskControlWords}=load('app/jobs/[id]/pause-control.tsx');
let saved=true,failRead=false,failResume=false,refreshes=0;const requests=[];
globalThis.fetch=async(url,options={})=>{requests.push({url:String(url),...options});if(String(url).endsWith('/conversation'))return failRead?Response.json({}, {status:503}):Response.json({recovery:saved?{resumable:true}:null});if(String(url).endsWith('/resume')&&failResume)return Response.json({error:'Task changed; refresh and retry.'},{status:409});return Response.json({ok:true});};
const root=createRoot(document.getElementById('root'));let props={id:'test-job',status:'running',updatedAt:100,pending:false,hasDraft:false,allowResume:true,locale:'en',onChange:()=>refreshes++};
async function render(change={}){props={...props,...change};await React.act(async()=>root.render(React.createElement('div',{className:'room-status'},React.createElement(Controls,props))));}
const buttons=()=>[...document.querySelectorAll('[role=group] button')],hint=()=>document.querySelector('.task-resume-hint')?.textContent;
async function click(el){await React.act(async()=>el.click());}
await render();assert.equal(buttons().length,2);assert.equal(buttons()[0].textContent,'Pause task');assert.equal(buttons()[1].textContent,'Resume');assert.equal(buttons()[0].disabled,false);assert.equal(buttons()[1].disabled,true);assert.equal(requests.length,0,'Live tasks do not need recovery lookups');
await click(buttons()[0]);assert.equal(refreshes,1);assert.equal(requests.at(-1).url,'/api/jobs/test-job/pause');assert.deepEqual(JSON.parse(requests.at(-1).body),{expectedUpdatedAt:100});
await render({status:'paused',updatedAt:101,pending:true});assert.ok(buttons().every(b=>b.disabled));assert.match(document.querySelector('[role=status]').textContent,/Saving progress/);
await render({updatedAt:102,pending:false});assert.equal(buttons()[0].disabled,true);assert.equal(buttons()[1].disabled,false);await click(buttons()[1]);assert.equal(requests.at(-1).url,'/api/jobs/test-job/resume');assert.deepEqual(JSON.parse(requests.at(-1).body),{expectedUpdatedAt:102});assert.equal(refreshes,2);
await render({status:'failed',updatedAt:103});assert.match(hint(),/Not completed\? Use Resume/);assert.equal(buttons()[1].disabled,false);await React.act(async()=>{buttons()[1].click();buttons()[1].click();});assert.equal(requests.filter(r=>r.url.endsWith('/resume')).length,2,'Double click submits a single new resume');
saved=false;await render({updatedAt:104});assert.equal(buttons()[1].disabled,true);assert.match(hint(),/No saved checkpoint/);const before=requests.length;await click(buttons()[1]);assert.equal(requests.length,before);
await render({updatedAt:105,hasDraft:true});assert.equal(buttons()[1].disabled,false);assert.match(hint(),/saved progress/);
failRead=true;await render({updatedAt:106});assert.equal(buttons()[1].disabled,false,'A known draft is usable even when the transcript lookup fails');failResume=true;await click(buttons()[1]);assert.match(document.querySelector('[role=alert]').textContent,/Task changed/);assert.equal(refreshes,3,'Rejected saves do not pretend to resume');
failRead=false;failResume=false;await render({status:'delivery_pending',updatedAt:107});assert.equal(buttons()[1].textContent,'Retry delivery');assert.equal(buttons()[1].disabled,false);
const count=requests.length;await render({status:'failed',updatedAt:108,allowResume:false});assert.equal(buttons()[1].disabled,true);assert.equal(hint(),undefined);assert.equal(requests.length,count,'An administrator inspecting another owner cannot use the owner resume action');
for(const locale of ['en','zh-CN','fr','es','ja']){saved=true;await render({locale,updatedAt:109+refreshes,allowResume:true,hasDraft:true});assert.equal(buttons()[1].textContent,taskControlWords[locale].resume);assert.equal(hint(),taskControlWords[locale].hint);}
await React.act(async()=>root.unmount());
// Render the real task page too: controls stay at the top even in the canvas tab.
modules['@/app/language']={useLanguage:()=>({locale:'en',t:load('lib/i18n.ts').messages.en}),LanguagePicker:()=>null};
for(const name of ['@/app/queue-status','./canvas-workbench','@/app/admin/conversation-history','@/app/attachment-previews','./draft-download','./interactive-download','@/app/creation-story','@/app/preview-link'])modules[name]={default:()=>null};
modules['./conversation']={default:()=>React.createElement('p',null,'Conversation history')};modules['./pause-control']={default:Controls};
modules['@/lib/upload-i18n']=load('lib/upload-i18n.ts');modules['@/lib/creation-i18n']=load('lib/creation-i18n.ts');modules['@/lib/creation-progress']={progressNotes:()=>[],previewVersion:()=>''};modules['./execution-backend']=load('lib/execution-backend.ts');modules['@/lib/execution-backend-i18n']=load('lib/execution-backend-i18n.ts');modules['@/lib/task-mode-i18n']=load('lib/task-mode-i18n.ts');
modules['@/lib/review-i18n']=load('lib/review-i18n.ts');modules['./review-results']=load('app/jobs/[id]/review-results.tsx');
const Room=load('app/jobs/[id]/progress-room.tsx').default;
const priorFetch=globalThis.fetch;globalThis.fetch=async(url,options={})=>String(url).endsWith('/progress')?Response.json({title:'Interrupted task',brief:'fixture',pages:15,attachments:[],status:'failed',scope:'user',updatedAt:777,createdAt:1,download:false,progress:null,pausePending:false,queue:null,draft:null}):priorFetch(url,options);
const page=createRoot(document.getElementById('root'));await React.act(async()=>page.render(React.createElement(Room,{id:'page-fixture'})));
assert.match(document.querySelector('.room-status .status').textContent,/Not completed/);assert.equal(document.querySelectorAll('.room-status .task-controls button').length,2);assert.equal(document.querySelectorAll('.task-resume').length,1);assert.match(document.querySelector('.room-status .task-resume-hint').textContent,/Use Resume/);
await click(document.querySelector('.task-resume'));assert.equal(requests.at(-1).url,'/api/jobs/page-fixture/resume');assert.deepEqual(JSON.parse(requests.at(-1).body),{expectedUpdatedAt:777});
await React.act(async()=>page.unmount());dom.window.close();
console.log('PASS: adjacent Pause/Resume controls, state/permission gates, saving-pause lock, exact revision-bound resume request, double-click guard, Not completed guidance, missing-checkpoint explanation, draft fallback, rejected-request feedback, delivery retry and five locales. React DOM emulator, not browser QA.');
