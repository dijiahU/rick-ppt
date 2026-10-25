import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {dirname,resolve,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {JSDOM} from 'jsdom';
import ts from 'typescript';

const dom=new JSDOM('<main id="root"></main>',{url:'https://test.local'});
for(const key of ['window','document','HTMLElement','Node','MouseEvent','Event','KeyboardEvent'])globalThis[key]=dom.window[key];
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const React=await import('react'),jsx=await import('react/jsx-runtime'),{createRoot}=await import('react-dom/client');
const base=resolve(dirname(fileURLToPath(import.meta.url)),'..');
let locale='en',messages,closed=false;
const mock=(name,render)=>({default:props=>React.createElement('div',{'data-testid':name},render?.(props))});
const modules={react:React,'react/jsx-runtime':jsx,
 '@/app/language':{useLanguage:()=>({locale,t:messages[locale]})},
 './conversation-history':mock('conversation',()=>Array.from({length:100},(_,i)=>React.createElement('p',{key:i},'Chat message '+i))),
 './usage-panel':mock('usage',()=>React.createElement('p',null,'Private usage ledger')),
 '@/app/queue-status':mock('queue',props=>String(props.position)),
 '@/app/activity-timeline':mock('activity',props=>props.events.map(e=>e.detail).join(' ')),
 '@/app/attachment-previews':mock('attachments',props=>props.files.map(file=>React.createElement('a',{key:file.id,href:props.hrefFor(file)},file.name))),
 './preview-link':{default:({children,...props})=>React.createElement('a',props,children)},
 './slide-limits.mjs':await import('../lib/slide-limits.mjs')};
const cache={};
function load(path){
 if(cache[path])return cache[path];
 const exports={};cache[path]=exports;
 const source=readFileSync(resolve(base,path),'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2023,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 new Function('require','exports',code)(name=>{
  if(modules[name])return modules[name];
  const target=name.startsWith('@/')?name.slice(2):relative(base,resolve(base,dirname(path),name));
  for(const suffix of ['', '.ts','.tsx'])if(existsSync(resolve(base,target+suffix)))return load(target+suffix);
  throw Error('Unexpected test dependency: '+name);
 },exports);
 return exports;
}
messages=load('lib/i18n.ts').messages;
assert.ok(messages);
const Details=load('app/admin/request-details.tsx').default;
const now=Date.now();
const fixture={id:'task-one',user_id:'user-one',title:'Long presentation task',status:'running',pages:2,language:'zh-CN',execution_backend:'codex',created_at:now,updated_at:now,queue:null,queuePosition:null,brief:'Original requirements that should not precede previews',style:'Designer choice',summary:null,download:true,attachments:[{id:'file-one',name:'reference.png'}],progress:{updatedAt:now,events:[{seq:1,at:now,code:'rendered',detail:'Actual render finished'}],notes:[{seq:1,at:now,code:'working',reported:true,phase:'building',slide:1,detail:'Making the first page'}],previews:[1],previewVersions:{1:'first-version'},outline:{title:'Outline title',purpose:'Explain the subject',slides:[{id:'one',title:'First page',summary:'The opening explanation'},{id:'two',title:'Second page',summary:'The next explanation'}]}}};
const root=createRoot(document.getElementById('root'));
const buttons=()=>[...document.querySelectorAll('[role=tab]')];
const selected=()=>document.querySelector('[role=tab][aria-selected=true]');
const visible=()=>[...document.querySelectorAll('[role=tabpanel]')].filter(p=>!p.hidden);
async function render(detail=fixture){await React.act(async()=>root.render(React.createElement(Details,{key:detail.id,detail,onClose:()=>{closed=true;}})));}
async function click(index){await React.act(async()=>buttons()[index].click());}
for(const [language,processTitle] of [['en','Creation process'],['zh-CN','制作过程'],['fr','Création'],['es','Creación'],['ja','制作過程']]){
 locale=language;await render({...fixture,id:'locale-'+language});
 assert.equal(selected().textContent,processTitle);
 assert.equal(visible().length,1);
 assert.ok(document.querySelector('.creation-story .creation-thumbnail img'));
 assert.equal(document.querySelector('[data-testid=conversation]'),null);
 assert.equal(document.querySelector('[data-testid=usage]'),null);
 assert.ok(!document.body.textContent.includes(fixture.brief));
 assert.ok(document.querySelector(`.admin-detail-actions a[href="/jobs/locale-${language}"]`));
 await click(1);assert.ok(document.querySelector('[data-testid=conversation]').textContent.includes('Chat message 99'));
 assert.equal(document.querySelector('.creation-story'),null);
 const body=document.querySelector('.admin-detail-body');body.scrollTop=980;
 await click(0);assert.equal(body.scrollTop,0);assert.ok(document.querySelector('.creation-story'));
 await React.act(async()=>buttons()[0].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true})));
 assert.equal(selected(),buttons()[1]);assert.equal(document.activeElement,buttons()[1]);
 await React.act(async()=>buttons()[1].dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true})));
 assert.equal(selected(),buttons()[4]);assert.ok(document.querySelector('[data-testid=activity]'));
 await click(2);assert.ok(document.body.textContent.includes(fixture.brief));
 assert.equal(document.querySelector('[data-testid=attachments] a').getAttribute('href'),`/api/admin/jobs/locale-${language}/attachments/file-one`);
 await click(3);assert.ok(document.querySelector('[data-testid=usage]'));
 await click(1);await render({...fixture,id:'locale-'+language,updated_at:now+5000});assert.equal(selected(),buttons()[1]);
 await render({...fixture,id:'next-'+language});assert.equal(selected(),buttons()[0]);
}
await React.act(async()=>document.querySelector('.admin-close').click());assert.equal(closed,true);
await React.act(async()=>root.unmount());dom.window.close();
console.log('PASS: actual React detail tabs in 5 languages; previews first, long chat isolated, usage on demand, attachments and trace access, tab scroll reset, keyboard focus, polling retains selection, new task resets and close works. DOM emulator; no browser screenshot QA.');
