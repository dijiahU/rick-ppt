import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';
import ts from 'typescript';
import * as React from 'react';
import * as jsx from 'react/jsx-runtime';
import {createRoot} from 'react-dom/client';
const dom=new JSDOM('<div id="root"></div>',{url:'https://fixture.test'});
for(const k of ['window','document','HTMLElement','HTMLInputElement','FormData','Event'])Object.defineProperty(globalThis,k,{value:dom.window[k],configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let locale='en',failConnect=false;
const connected={id:crypto.randomUUID(),provider:'openai',label:'Personal',keyHint:'••••1234',models:['gpt-6-astra','gpt-6.1-sol'],createdAt:1};
const calls=[];
globalThis.fetch=async(url,init={})=>{calls.push({url,init});if(init.method==='DELETE')return Response.json({ok:true});if(init.method==='POST')return failConnect?Response.json({error:'API key was rejected'},{status:422}):Response.json(connected,{status:201});return Response.json({enabled:true,accounts:[],providers:[{id:'openai',label:'OpenAI',models:connected.models}]});};
const modules={react:React,'react/jsx-runtime':jsx,'./language':{useLanguage:()=>({locale})},'./model-accounts.css':{}};
const code=ts.transpileModule(readFileSync(new URL('../app/model-accounts.tsx',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const output={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},output);
let currentSelection;
function Harness(){const [accounts,onAccounts]=React.useState([]),[selection,setSelection]=React.useState(null);currentSelection=selection;return React.createElement(React.Fragment,null,React.createElement(output.default,{onAccounts,onSelect:setSelection}),React.createElement(output.ModelAccountPicker,{accounts,selection,onSelect:setSelection}));}
const root=createRoot(document.getElementById('root'));
await React.act(async()=>{root.render(React.createElement(Harness));});
function value(id,v){const input=document.getElementById(id);Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype,'value').set.call(input,v);}
async function connect(key='sk-dom-synthetic-only-1234'){value('model-account-label','Personal');value('model-api-key',key);await React.act(async()=>{document.querySelector('.model-accounts form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));});}
await connect();assert.equal(currentSelection.credentialId,connected.id);assert.equal(currentSelection.model,'gpt-6-astra');
assert.equal(document.getElementById('model-api-key').value,'');assert.ok(!document.body.textContent.includes('sk-dom-synthetic'));assert.ok(document.body.textContent.includes('••••1234'));
assert.equal(document.querySelector('input[name="base_url"]'),null);assert.equal(dom.window.localStorage.length,0);
await React.act(async()=>{const select=document.getElementById('task-customer-model');select.value='gpt-6.1-sol';select.dispatchEvent(new dom.window.Event('change',{bubbles:true}));});assert.equal(currentSelection.model,'gpt-6.1-sol');
await React.act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Replace key').click();});assert.equal(document.getElementById('model-provider').disabled,true);
await connect('sk-dom-replacement-secret-5678');const posted=JSON.parse(calls.filter(c=>c.init.method==='POST').at(-1).init.body);assert.equal(posted.replaceId,connected.id);assert.equal(posted.provider,'openai');assert.equal(document.querySelectorAll('.model-account-row').length,1);
failConnect=true;await connect('sk-dom-rejected-secret-9000');assert.ok(document.querySelector('[role="alert"]').textContent.includes('API key was rejected'));assert.equal(document.getElementById('model-api-key').value,'');assert.equal(currentSelection.credentialId,connected.id);
await React.act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Disconnect').click();});assert.equal(currentSelection,null);assert.equal(document.querySelectorAll('.model-account-row').length,0);assert.equal(document.getElementById('task-model-account'),null);
locale='zh-CN';await React.act(async()=>root.render(React.createElement(Harness)));assert.ok(document.body.textContent.includes('使用自己的 API 余额'));
await React.act(async()=>root.unmount());dom.window.close();
console.log('PASS: actual React DOM connect/model selection/key replacement/error/disconnect flows; password cleared; no persistent browser key; fixed provider inputs; English and Chinese UI.');
