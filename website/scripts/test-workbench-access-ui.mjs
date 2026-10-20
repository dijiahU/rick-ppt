// Server-render the real React component; no browser or production access.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import * as React from 'react';
import * as jsx from 'react/jsx-runtime';
import {unzipSync,strFromU8} from 'fflate';
import {renderToStaticMarkup} from 'react-dom/server';
let locale='en';const modules={react:React,'react/jsx-runtime':jsx,'@/app/language':{useLanguage:()=>({locale})},'@/lib/upload-client':{},'./canvas-workbench.css':{},'./native-editor.css':{},fflate:{unzipSync,strFromU8}};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
modules['@/lib/visual-edits']=load('lib/visual-edits.ts');modules['./visual-edits']=modules['@/lib/visual-edits'];modules['@/lib/native-edits']=load('lib/native-edits.ts');modules['@/lib/native-canvas-client']=load('lib/native-canvas-client.ts');modules['./native-editor']=load('app/jobs/[id]/native-editor.tsx');const Workbench=load('app/jobs/[id]/canvas-workbench.tsx').default;
for(locale of ['en','zh-CN']){
 const html=renderToStaticMarkup(React.createElement(Workbench,{id:'test',status:'complete',progress:null,onSubmitted(){},conversation:React.createElement('p',null,'Full conversation history')}));
 assert.match(html,/role="tablist"/);assert.match(html,/aria-selected="true"[^>]*aria-controls="canvas-chat-panel-test"/);
 const panel=html.match(/<section[^>]*id="canvas-chat-panel-test"[^>]*>/)?.[0];assert.ok(panel);assert.ok(!/\bhidden/.test(panel));assert.ok(html.includes('Full conversation history'));
 const changes=html.match(/<section[^>]*id="canvas-changes-panel-test"[^>]*>/)?.[0];assert.match(changes,/hidden/);
 assert.ok(!html.includes('<details class="canvas-chat"'));
}
console.log('PASS: real workbench renders visible conversation by default in English/Chinese, with separate persistent chat/change tabs.');
