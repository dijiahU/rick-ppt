import * as slideLimits from '../lib/slide-limits.mjs';
// Render both real form branches without browser automation or account access.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import * as React from 'react';
import * as jsx from 'react/jsx-runtime';
import {renderToStaticMarkup} from 'react-dom/server';
let mode='create',locale='en',calls=0,brief='',pageInput='10';
const modules={react:{...React,useState(initial){calls++;return React.useState(calls===2?mode:calls===8?pageInput:calls===9?brief:initial);}},'react/jsx-runtime':jsx};
modules['./slide-limits.mjs']=slideLimits;modules['@/lib/slide-limits.mjs']=slideLimits;
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
for(const name of ['i18n','quota-i18n','queue-i18n','upload-i18n','task-mode-i18n','task-mode','page-count-i18n'])modules['@/lib/'+name]=load('lib/'+name+'.ts');
modules['./language']={useLanguage:()=>({locale,t:modules['@/lib/i18n'].messages[locale]})};
modules['./file-upload']={default:({title})=>React.createElement('p',null,title||'Optional references')};
const Form=load('app/brief-form.tsx').default;
for(locale of Object.keys(modules['@/lib/i18n'].languages)){
 for(mode of ['create','edit']){
  calls=0;const html=renderToStaticMarkup(React.createElement(Form));
  assert.equal(html.includes('name="pages"'),mode==='create');
  assert.ok(html.includes('id="task-mode"'));
  if(mode==='create'){
   const input=html.match(/<input[^>]*name="pages"[^>]*>/)[0];
   assert.ok(input.includes('type="number"'));assert.ok(input.includes('min="1"'));assert.ok(input.includes('max="50"'));
   assert.ok(input.includes('value="10"'));assert.ok(html.includes('id="pages-resolved"'));
   assert.ok(!html.includes('<select id="pages"'));
  }
  if(mode==='edit')assert.ok(html.includes(modules['@/lib/task-mode-i18n'].sourceFileLabels[locale]));
 }
}
console.log('PASS: numeric slide input from 1–50, default of 10 and create/edit form branches in all five languages; editing hides slide count and requires original PPTX copy');
mode='create';locale='zh-CN';brief='请做30页的历史课程介绍。';pageInput='15';calls=0;
const resolved=renderToStaticMarkup(React.createElement(Form));
const countInput=resolved.match(/<input[^>]*name="pages"[^>]*>/)[0];
assert.ok(countInput.includes('value="30"'));assert.ok(countInput.includes('disabled=""'));
assert.ok(resolved.includes('本次将制作 30 页，采用需求中明确指定的页数。'));
console.log('PASS: actual form visibly uses the 30-page brief over the 15-page fallback before submission');
