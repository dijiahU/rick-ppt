// Exercise actual component handlers with an isolated hook store; no queue/API calls.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import * as React from 'react';
import * as jsx from 'react/jsx-runtime';
import {renderToStaticMarkup} from 'react-dom/server';
let locale='zh-CN',state=[],cursor=0;
const modules={react:{...React,useState(initial){const index=cursor++;if(!(index in state))state[index]=initial;return [state[index],value=>{state[index]=typeof value==='function'?value(state[index]):value;}];},useRef:()=>({current:null}),useEffect:()=>{}},'react/jsx-runtime':jsx};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(name in modules,name);return modules[name];},exports);return exports;}
modules['@/lib/landing-i18n']=load('lib/landing-i18n.ts');
const copies=modules['@/lib/landing-i18n'].landingCopy;
modules['./language']={useLanguage:()=>({locale,t:modules['@/lib/i18n']?.messages[locale]}),LanguagePicker:()=>React.createElement('span',null,locale)};
modules['./transformer-diagram']=load('app/transformer-diagram.tsx');
const Show=load('app/transformer-showcase.tsx').default;
const Resources=load('app/resource-showcase.tsx').default;
function render(Component){cursor=0;return Component();}
function nodes(tree,match){if(!React.isValidElement(tree))return [];const children=React.Children.toArray(tree.props.children);return [...(match(tree)?[tree]:[]),...children.flatMap(child=>nodes(child,match))];}
function button(tree,match){const matches=nodes(tree,node=>node.type==='button'&&match(node.props));assert.equal(matches.length,1);return matches[0].props;}
for(locale of Object.keys(copies)){
 state=[];const tree=render(Show);const html=renderToStaticMarkup(tree);
 assert.equal(nodes(tree,node=>node.props.role==='tab').length,3);assert.ok(html.includes(copies[locale].demoNote));
 assert.ok(html.includes('Vaswani et al.'));assert.ok(html.includes('https://arxiv.org/abs/1706.03762'));
 state=[];assert.ok(renderToStaticMarkup(render(Resources)).includes('/showcase/earthrise.jpg'));
}
locale='zh-CN';state=[];let tree=render(Show);
button(tree,p=>p['aria-pressed']===false).onClick();tree=render(Show);
const slider=nodes(tree,node=>node.type==='input'&&node.props.type==='range')[0];assert.ok(slider);slider.props.onChange({target:{value:'73'}});tree=render(Show);assert.ok(renderToStaticMarkup(tree).includes('inset(0 0 0 73%)'));
button(tree,p=>p.id==='specimen-tab-1').onClick();tree=render(Show);
let diagram=nodes(tree,node=>node.type===modules['./transformer-diagram'].default)[0];assert.equal(diagram.props.stage,0);
for(let n=1;n<=4;n++){button(tree,p=>p.className==='next-control').onClick();tree=render(Show);diagram=nodes(tree,node=>node.type===modules['./transformer-diagram'].default)[0];assert.equal(diagram.props.stage,n);}
button(tree,p=>p.className==='next-control').onClick();tree=render(Show);assert.equal(nodes(tree,node=>node.type===modules['./transformer-diagram'].default)[0].props.stage,0);
button(tree,p=>p.id==='specimen-tab-2').onClick();tree=render(Show);
diagram=nodes(tree,node=>node.type===modules['./transformer-diagram'].default)[0];diagram.props.onSelect('decoder-cross');tree=render(Show);
nodes(tree,node=>node.props.id==='specimen-object-text')[0].props.onChange({target:{value:'Edited cross attention'}});tree=render(Show);
button(tree,p=>p['aria-label']==='对象颜色 #d3e7d6').onClick();tree=render(Show);diagram=nodes(tree,node=>node.type===modules['./transformer-diagram'].default)[0];assert.deepEqual(diagram.props.overrides['decoder-cross'],{label:'Edited cross attention',fill:'#d3e7d6'});
assert.equal(diagram.props.overrides['encoder-attention'],undefined);assert.equal(modules['./transformer-diagram'].diagramObjects.find(x=>x.id==='decoder-cross').label,'Multi-Head\nAttention');
button(tree,p=>p.className==='quiet-control'&&p.children[0]===copies[locale].reset).onClick();tree=render(Show);assert.deepEqual(nodes(tree,node=>node.type===modules['./transformer-diagram'].default)[0].props.overrides,{});
state=[];tree=render(Resources);button(tree,p=>p.id==='resource-tab-1').onClick();tree=render(Resources);const before=nodes(tree,node=>node.props.role==='img')[0].props['aria-label'];button(tree,p=>p.onClick&&!p.role).onClick();tree=render(Resources);assert.notEqual(nodes(tree,node=>node.props.role==='img')[0].props['aria-label'],before);
button(tree,p=>p.id==='resource-tab-2').onClick();tree=render(Resources);assert.equal(nodes(tree,node=>node.props.role==='math').length,1);
const base=copies.en;for(const copy of Object.values(copies)){assert.deepEqual(Object.keys(copy),Object.keys(base));for(const key of Object.keys(base)){if(Array.isArray(base[key]))assert.equal(copy[key].length,base[key].length);}}
console.log('PASS: five-language samples; comparison slider; all five reveal states and replay; isolated object label/colour edits and reset; dataset switching; formula view. No production requests.');
