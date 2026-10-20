// Actual handlers and animation effect lifecycle; no browser or production requests.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import * as React from 'react';
import * as jsx from 'react/jsx-runtime';
import {renderToStaticMarkup} from 'react-dom/server';
let locale='zh-CN',slots=[],cursor=0,effects=new Map(),pending=[],timerCount=0;
const timers=new Map();globalThis.window={setInterval(fn){const id=++timerCount;timers.set(id,fn);return id;},clearInterval(id){timers.delete(id);}};
const modules={react:{...React,useState(initial){const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],value=>{slots[i]=typeof value==='function'?value(slots[i]):value;}];},useRef(value){const i=cursor++;return slots[i]??=( {current:value} );},useEffect(fn,deps){const i=cursor++,prior=effects.get(i);if(!prior||deps.some((v,n)=>v!==prior.deps[n]))pending.push(()=>{prior?.cleanup?.();effects.set(i,{deps,cleanup:fn()});});},useId:()=>`test-${cursor++}`},'react/jsx-runtime':jsx};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(name in modules,name);return modules[name];},exports);return exports;}
modules['@/lib/landing-i18n']=load('lib/landing-i18n.ts');modules['@/lib/gallery-i18n']=load('lib/gallery-i18n.ts');
modules['./language']={useLanguage:()=>({locale})};modules['./transformer-diagram']=load('app/transformer-diagram.tsx');modules['./use-paint-drag']=load('app/use-paint-drag.ts');modules['./gallery-cases']=load('app/gallery-cases.tsx');
const waterSignals=[];let waterPaused=false;modules['./use-water-gallery']={useWaterGallery:(_active,paused)=>{waterPaused=paused;return {stageRef:{current:null},surge(index,direction){waterSignals.push({index,direction});},onPointerMove(){},onPointerDown(){}};}};modules['@/lib/water-model']=load('lib/water-model.ts');
const Gallery=load('app/case-gallery.tsx').default;const cases=modules['./gallery-cases'];
const props=()=>({g:modules['@/lib/gallery-i18n'].galleryCopy[locale],c:modules['@/lib/landing-i18n'].landingCopy[locale]});
function reset(){for(const effect of effects.values())effect.cleanup?.();slots=[];effects=new Map();pending=[];cursor=0;timers.clear();}
function render(Component,additional={}){cursor=0;const tree=Component({...props(),...additional});const work=pending;pending=[];for(const fn of work)fn();return tree;}
function nodes(tree,match){if(!React.isValidElement(tree))return [];return [...(match(tree)?[tree]:[]),...React.Children.toArray(tree.props.children).flatMap(child=>nodes(child,match))];}
function one(tree,match){const found=nodes(tree,match);assert.equal(found.length,1);return found[0].props;}
function button(tree,match){return one(tree,n=>n.type==='button'&&match(n.props));}
reset();let tree=render(Gallery);assert.equal(tree.props['data-active-case'],0);assert.equal(nodes(tree,n=>n.props.role==='tab').length,6);assert.equal(nodes(tree,n=>n.props.role==='tab'&&n.props['aria-selected']).length,1);
assert.ok(tree.props.className.includes('darkroom-gallery'));
assert.equal(nodes(tree,n=>n.props.className==='darkroom-emulsion'&&n.props['aria-hidden']==='true').length,6);
assert.equal(nodes(tree,n=>n.props.className==='darkroom-status-developing').length,1);
assert.equal(nodes(tree,n=>n.props.className==='darkroom-status-ready').length,1);
assert.equal(nodes(tree,n=>n.props.className==='darkroom-print-status'&&n.props.children===props().g.undeveloped).length,5);
const currentPaper=tree=>one(nodes(tree,n=>n.type==='article'&&n.props.className.includes('is-current'))[0],n=>n.props.className==='case-paper');
assert.equal(currentPaper(tree)['data-developed'],false);
const paperElement={};currentPaper(tree).onAnimationEnd({target:{},currentTarget:paperElement,animationName:'darkroom-develop'});tree=render(Gallery);
assert.equal(currentPaper(tree)['data-developed'],false,'Child animations must not complete paper development');
currentPaper(tree).onAnimationEnd({target:paperElement,currentTarget:paperElement,animationName:'darkroom-develop'});tree=render(Gallery);
assert.equal(currentPaper(tree)['data-developed'],true);
one(tree,n=>n.props.className==='case-stage').onPointerDown();tree=render(Gallery);
assert.equal(currentPaper(tree)['data-developed'],true,'A background click must retain the developed colour');
button(tree,p=>p['aria-label']==='切换到 对象编辑').onClick();tree=render(Gallery);assert.equal(tree.props['data-active-case'],5);assert.deepEqual(waterSignals.at(-1),{index:5,direction:-1});
assert.equal(currentPaper(tree)['data-developed'],false,'A newly selected print starts development');
currentPaper(tree).onFocusCapture();tree=render(Gallery);
one(tree,n=>n.props.className==='case-stage').onPointerDown();tree=render(Gallery);
assert.equal(currentPaper(tree)['data-developed'],true,'Editing completes development persistently, including after clicking outside');
const selectedPrint=nodes(tree,n=>n.type==='article'&&n.props.className.includes('is-current'))[0];
assert.equal(selectedPrint.props.id,'gallery-panel-5');
assert.equal(nodes(selectedPrint,n=>n.props.className==='darkroom-status-developing').length,1);
assert.equal(nodes(tree,n=>n.props.className==='darkroom-print-status'&&n.props.children===props().g.undeveloped).length,5,'Visited side prints return to the undeveloped treatment.');
button(tree,p=>p['aria-label']==='下一个案例').onClick();tree=render(Gallery);assert.equal(tree.props['data-active-case'],0);assert.deepEqual(waterSignals.at(-1),{index:0,direction:1});button(tree,p=>p.className==='water-motion-toggle').onClick();tree=render(Gallery);assert.equal(waterPaused,true);assert.equal(button(tree,p=>p.className==='water-motion-toggle')['aria-pressed'],true);assert.ok(nodes(tree,n=>n.type===cases.ObjectCase).length,'Visited object case stays mounted to preserve edits');
const list=one(tree,n=>n.props.role==='tablist');let focused=-1,prevented=false;list.onKeyDown({key:'End',preventDefault(){prevented=true;},currentTarget:{querySelectorAll:()=>Array.from({length:6},(_,i)=>({focus(){focused=i;}}))}});tree=render(Gallery);assert.equal(tree.props['data-active-case'],5);assert.equal(focused,5);assert.ok(prevented);
reset();tree=render(cases.ScientificCase);assert.equal(one(tree,n=>n.type==='input'&&n.props.type==='range').defaultValue,48);assert.equal(nodes(tree,n=>n.props.className==='paint-divider').length,1);
// Pointer precision, immediate updates and cancellation use actual DOM events in test-paint-drag-ui.mjs.
// Editing shares the exact overrides across paint layers and the enlarged diagram.
reset();tree=render(cases.ScientificCase);const Diagram=modules['./transformer-diagram'].default;
one(tree,n=>n.type===Diagram&&typeof n.props.onSelect==='function').onSelect('decoder-cross');tree=render(cases.ScientificCase);
one(tree,n=>n.type==='textarea').onChange({target:{value:'Custom\nCross Attention'}});tree=render(cases.ScientificCase);
button(tree,p=>p['aria-label']==='对象颜色 #d3e7d6').onClick();tree=render(cases.ScientificCase);
let diagrams=nodes(tree,n=>n.type===Diagram);assert.equal(diagrams.length,2);assert.equal(diagrams[0].props.overrides,diagrams[1].props.overrides);assert.deepEqual(diagrams[0].props.overrides['decoder-cross'],{label:'Custom\nCross Attention',fill:'#d3e7d6'});assert.equal(diagrams[0].props.selected,'decoder-cross');assert.equal(diagrams[1].props.onSelect,undefined);assert.equal(one(tree,n=>n.props.className==='science-colour').inert,true);assert.equal(one(tree,n=>n.props.className==='science-colour')['aria-hidden'],'true');
assert.equal(one(tree,n=>n.type==='input'&&n.props.type==='range').defaultValue,48,'Editing must not move the paint divider');
button(tree,p=>p.className==='science-zoom-open').onClick();tree=render(cases.ScientificCase);diagrams=nodes(tree,n=>n.type===Diagram);assert.equal(diagrams.length,3);assert.equal(diagrams[2].props.overrides,diagrams[0].props.overrides);
const enlarged=nodes(tree,n=>n.type==='dialog')[0];one(enlarged,n=>n.type==='textarea').onChange({target:{value:'Edited in enlarged view'}});tree=render(cases.ScientificCase);assert.ok(nodes(tree,n=>n.type==='textarea').every(n=>n.props.value==='Edited in enlarged view'));assert.equal(new Set(nodes(tree,n=>n.type==='textarea').map(n=>n.props.id)).size,2);
button(tree,p=>p.autoFocus===true).onClick();tree=render(cases.ScientificCase);assert.equal(nodes(tree,n=>n.type==='dialog').length,0);assert.equal(one(tree,n=>n.type==='textarea').value,'Edited in enlarged view');
button(tree,p=>p.className==='science-editor-close').onClick();tree=render(cases.ScientificCase);assert.equal(nodes(tree,n=>n.type==='textarea').length,0);assert.equal(one(tree,n=>n.type===Diagram&&typeof n.props.onSelect==='function').overrides['decoder-cross'].label,'Edited in enlarged view');
button(tree,p=>p.className==='science-edit-open').onClick();tree=render(cases.ScientificCase);button(tree,p=>p.className==='science-reset').onClick();tree=render(cases.ScientificCase);assert.deepEqual(one(tree,n=>n.type===Diagram&&typeof n.props.onSelect==='function').overrides,{});assert.equal(modules['./transformer-diagram'].diagramObjects.find(obj=>obj.id==='decoder-cross').label,'Multi-Head\nAttention');
reset();tree=render(Diagram,{label:'Fit labels',onSelect(){},overrides:{'encoder-norm-1':{label:'One\nTwo\nThree\nFour'}}});const fitted=nodes(tree,n=>n.props.role==='button'&&n.props['aria-label']==='Select: One Two Three Four')[0];const text=one(fitted,n=>n.type==='text');const spans=nodes(fitted,n=>n.type==='tspan');let baseline=text.y;for(const span of spans){baseline+=span.props.dy;assert.ok(baseline>411&&baseline<434,'Edited multiline labels must fit inside their module');}
reset();tree=render(cases.AnimationCase);button(tree,p=>p['data-action']==='play').onClick();tree=render(cases.AnimationCase);assert.equal(timers.size,1);for(let step=1;step<=3;step++){[...timers.values()][0]();tree=render(cases.AnimationCase);assert.ok(one(tree,n=>n.props.className==='attention-flow')['aria-label'].includes(props().g.stages[step]));}tree=render(cases.AnimationCase);assert.equal(timers.size,0,'Completed playback must not leave a timer');button(tree,p=>p['data-action']==='play').onClick();tree=render(cases.AnimationCase);assert.equal(timers.size,1);tree=render(cases.AnimationCase,{active:false});tree=render(cases.AnimationCase,{active:false});assert.equal(timers.size,0,'Leaving the animation case stops playback');
reset();tree=render(cases.ChartCase);one(tree,n=>n.type==='input'&&n.props.type==='range').onChange({target:{value:'50'}});tree=render(cases.ChartCase);assert.ok(nodes(tree,n=>n.type==='button'&&n.props['aria-label']==='E: 50').length);button(tree,p=>p['aria-label']==='B: 56').onClick();tree=render(cases.ChartCase);one(tree,n=>n.type==='input'&&n.props.type==='range').onChange({target:{value:'65'}});tree=render(cases.ChartCase);assert.ok(nodes(tree,n=>n.type==='button'&&n.props['aria-label']==='B: 65').length);assert.ok(nodes(tree,n=>n.type==='button'&&n.props['aria-label']==='E: 50').length);
reset();tree=render(cases.ImageCase);button(tree,p=>p.children===props().g.compositions[1]).onClick();tree=render(cases.ImageCase);assert.equal(tree.props.className,'image-case image-layout-1');
reset();tree=render(cases.FormulaCase);button(tree,p=>p.children==='V').onClick();tree=render(cases.FormulaCase);assert.equal(one(tree,n=>n.type==='p'&&n.props['aria-live']==='polite').children,props().g.values);
one(tree,n=>n.type==='input'&&n.props['data-symbol']==='Q').onChange({target:{value:'X'}});tree=render(cases.FormulaCase);
one(tree,n=>n.type==='input'&&n.props['data-symbol']==='dimension').onChange({target:{value:'h'}});tree=render(cases.FormulaCase);
assert.ok(one(tree,n=>n.props.role==='math')['aria-label'].includes('Attention(X, K, V)'));
assert.ok(one(tree,n=>n.props.role==='math')['aria-label'].includes('d_h'));
const defaultResult=Number(one(tree,n=>n.type==='output').children);assert.ok(Math.abs(defaultResult-14.2479)<.01);
one(tree,n=>n.type==='input'&&n.props['aria-label']===props().g.equation.temperature).onChange({target:{value:'0.5'}});tree=render(cases.FormulaCase);
const sharperResult=Number(one(tree,n=>n.type==='output').children);assert.ok(Math.abs(sharperResult-11.4906)<.01);assert.ok(sharperResult<defaultResult);
const percentages=nodes(tree,n=>n.type==='b'&&React.Children.toArray(n.props.children).join('').endsWith('%')).map(n=>Number.parseFloat(React.Children.toArray(n.props.children).join('')));
assert.equal(percentages.length,3);assert.ok(Math.abs(percentages.reduce((a,b)=>a+b,0)-100)<.11);
button(tree,p=>p['data-term']==='K').onClick();tree=render(cases.FormulaCase);assert.equal(one(tree,n=>n.type==='input'&&n.props['data-symbol']==='Q').value,'X','Selecting a term preserves formula edits');
button(tree,p=>p.className==='formula-reset').onClick();tree=render(cases.FormulaCase);
assert.equal(one(tree,n=>n.type==='input'&&n.props['data-symbol']==='Q').value,'Q');assert.equal(one(tree,n=>n.type==='input'&&n.props['data-symbol']==='dimension').value,'k');assert.equal(one(tree,n=>n.type==='input'&&n.props.type==='range').value,1);
reset();tree=render(cases.ObjectCase);one(tree,n=>n.props.id==='gallery-title').onChange({target:{value:'A new title'}});tree=render(cases.ObjectCase);button(tree,p=>p['aria-label']==='颜色 #365a70').onClick();tree=render(cases.ObjectCase);assert.equal(one(tree,n=>n.props.className==='object-headline').fill,'#365a70');const title=one(tree,n=>n.props.className==='movable-title');title.onKeyDown({key:'ArrowRight',preventDefault(){}});tree=render(cases.ObjectCase);assert.equal(one(tree,n=>n.props.className==='movable-title').transform,'translate(81 157)');const pointerTarget={ownerSVGElement:{getBoundingClientRect:()=>({width:900})},setPointerCapture(){},hasPointerCapture:()=>true};const movable=one(tree,n=>n.props.className==='movable-title');movable.onPointerDown({pointerId:1,currentTarget:pointerTarget,clientX:10,clientY:10});movable.onPointerMove({pointerId:1,currentTarget:pointerTarget,clientX:35,clientY:30});tree=render(cases.ObjectCase);assert.equal(one(tree,n=>n.props.className==='movable-title').transform,'translate(106 177)');button(tree,p=>p.className==='object-reset').onClick();tree=render(cases.ObjectCase);assert.equal(one(tree,n=>n.props.id==='gallery-title').value,'Ideas worth sharing.');
for(locale of ['en','zh-CN','fr','es','ja']){reset();tree=render(Gallery);const html=renderToStaticMarkup(tree);assert.ok(html.includes(props().g.disclosure));assert.ok(html.includes(props().g.titles[0]));assert.equal(nodes(tree,n=>n.props.role==='tab').length,6);reset();const formula=render(cases.FormulaCase);const sample=renderToStaticMarkup(formula);assert.ok(sample.includes(props().g.equation.edit));assert.ok(sample.includes('14.25'));assert.equal(nodes(formula,n=>n.type==='input'&&n.props.type==='text').length,4);}
reset();console.log('PASS: six-case side switching/wraparound/keyboard navigation; preserved visited cases; initially visible divider and clamped painting drag; shared paint/label/colour editing in normal and enlarged views, isolated input layer, close/reset and multiline fit; timed animation completion and inactive cleanup; selected chart values; image composition; equation terms; editable title/colour/drag/reset; five-language rendering.');
