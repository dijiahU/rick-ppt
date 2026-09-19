import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const controls=JSON.parse(readFileSync(new URL('../../examples/controls.scene.json',import.meta.url),'utf8'));
const charts=JSON.parse(readFileSync(new URL('../../examples/charts-map.scene.json',import.meta.url),'utf8'));
import type {Scene} from '../../src/core/types';
const expr=(expr:string)=>({expr});
const node=(id:string,type:string,props:any={},rest:any={})=>({id,type,props,...rest});
const action=(type:string,rest:any={})=>({type,...rest});
const interaction=(target:string,event:string,actions:any[])=>({target,event,actions});
const fixture=(patch:any={}):Scene=>({schemaVersion:1,id:'test-scene',viewport:{width:1000,height:700},nodes:[],...patch});
const state=(page:Page,path?:string)=>page.evaluate(path=>(window as any).__interactive.runtime.store.get(path),path);
const byId=(page:Page,id:string)=>page.locator(`[data-node-id="${id}"]`);
async function load(page:Page,scene:any){await page.route(url=>url.pathname==='/fixture.scene.json',route=>route.fulfill({json:scene}));await page.goto('/preview.html?spec=/fixture.scene.json&debug=1');await expect.poll(()=>page.evaluate(()=>(window as any).__interactive?.ready)).toBe(true);await expect(page.locator('.scene')).toBeVisible();}
async function point(page:Page,id:string,x:number,y:number){return byId(page,id).evaluate((el:any,p)=>{const q=new DOMPoint(p.x,p.y).matrixTransform(el.getScreenCTM());return{x:q.x,y:q.y};},{x,y});}
async function dragParent(page:Page,id:string,dx:number,dy:number){const p=await byId(page,id).evaluate((el:any,d)=>{const m=el.getScreenCTM(),parent=el.parentElement.getScreenCTM(),from=new DOMPoint(el.getAttribute('data-node-type')==='Circle'?0:20,el.getAttribute('data-node-type')==='Circle'?0:20).matrixTransform(m),delta=new DOMPoint(d.dx,d.dy).matrixTransform(new DOMMatrix([parent.a,parent.b,parent.c,parent.d,0,0]));return{x:from.x,y:from.y,dx:delta.x,dy:delta.y};},{dx,dy});await page.mouse.move(p.x,p.y);await page.mouse.down();await page.mouse.move(p.x+p.dx,p.y+p.dy,{steps:6});await page.mouse.up();}
async function range(page:Page,id:string,value:number){await byId(page,id).locator('input').evaluate((el:any,value)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(el,String(value));el.dispatchEvent(new Event('input',{bubbles:true}));},value);}

test('transformed dragging stays in parent coordinates after responsive resize; unrelated DOM stays untouched',async({page},info)=>{
 await load(page,controls);await page.screenshot({path:info.outputPath('initial.png')});
 await byId(page,'sentinel').evaluate(el=>{(window as any).__sentinelMutations=0;new MutationObserver(records=>(window as any).__sentinelMutations+=records.length).observe(el,{subtree:true,attributes:true,characterData:true,childList:true});});
 await dragParent(page,'dragBox',40,-10);await expect.poll(()=>state(page,'box')).toEqual({x:65,y:10});
 await expect(byId(page,'dragBox')).toHaveAttribute('transform',/translate\(65 10\)/);expect(await page.evaluate(()=>(window as any).__sentinelMutations)).toBe(0);
 await page.setViewportSize({width:760,height:900});await dragParent(page,'dragBox',20,15);await expect.poll(()=>state(page,'box')).toEqual({x:85,y:25});
 await page.screenshot({path:info.outputPath('responsive-drag.png')});
});

test('native controls, SVG keyboard activation, file upload, component bubbling, snapshot and reset affect real state',async({page},info)=>{
 await load(page,controls);await page.getByRole('button',{name:'Increment',exact:true}).click();await expect(byId(page,'counter')).toContainText('Count 1 · double 2');
 await page.getByRole('textbox',{name:'Your name'}).fill('Morty');await page.getByRole('textbox',{name:'Notes'}).fill('Explain one step at a time');
 await page.getByRole('slider',{name:'Gain'}).focus();await page.keyboard.press('ArrowRight');await expect.poll(()=>state(page,'gain')).toBe(3);
 await page.getByRole('combobox',{name:'Mode'}).selectOption('high');await page.getByRole('checkbox',{name:'Enabled'}).check();
 await page.getByRole('button',{name:'Change',exact:true}).click();await expect.poll(()=>state(page,'tab')).toBe(1);expect(await state(page,'tabClicks')).toBe(1);
 await byId(page,'keyboardBox').focus();await page.keyboard.press('Enter');expect(await state(page,'keyClicks')).toBe(1);
 await page.getByLabel('Load JSON or CSV').setInputFiles({name:'measurements.json',mimeType:'application/json',buffer:Buffer.from('{"values":[2,4,6]}')});await expect.poll(()=>state(page,'uploaded')).toEqual({values:[2,4,6]});
 const saved=await page.evaluate(()=>(window as any).__interactive.snapshot());expect(saved.state).toMatchObject({name:'Morty',mode:'high',enabled:true,note:'Explain one step at a time'});
 await page.screenshot({path:info.outputPath('edited.png')});await page.getByRole('button',{name:'Reset',exact:true}).focus();await page.keyboard.press('Enter');await expect.poll(()=>state(page,'name')).toBe('Rick');expect(await state(page,'tabClicks')).toBe(0);
 await page.evaluate(saved=>(window as any).__interactive.restore(saved),saved);await expect(page.getByRole('textbox',{name:'Your name'})).toHaveValue('Morty');await expect(page.getByRole('checkbox',{name:'Enabled'})).toBeChecked();await page.screenshot({path:info.outputPath('restored.png')});
});

test('bound row and grid layout expands repeat/when and updates hit-tested z order',async({page})=>{
 await load(page,fixture({initialState:{width:80,showB:false,raised:false,clicked:''},dataSources:{items:{type:'inline',value:[{id:'a'},{id:'b'},{id:'c'}]}},nodes:[
  node('row','Group',{x:20,y:20,width:500,height:100,layout:'row',padding:10,gap:12,align:'center'},{children:[node('cell','Rect',{height:40,fill:'#0d9488'},{repeat:{source:expr('data.items'),item:'item',key:expr('item.id')},when:expr('item.id !== "b" || state.showB'),bind:{width:expr('state.width')}})]}),
  node('grid','Group',{x:20,y:160,width:300,height:200,layout:'grid',columns:2,rows:2,padding:10,gap:10},{children:[node('g1','Rect',{width:60,height:40}),node('g2','Rect',{width:60,height:40}),node('g3','Rect',{width:60,height:40})]}),
  node('size','Slider',{x:20,y:400,width:300,height:40,min:40,max:150,ariaLabel:'Cell width'},{bind:{value:expr('state.width')}}),node('show','Button',{x:20,y:460,width:160,height:40,text:'Show B'}),node('raise','Button',{x:200,y:460,width:160,height:40,text:'Raise first'}),
  node('first','Rect',{x:600,y:100,width:120,height:120,fill:'#2563eb'},{bind:{zIndex:expr('state.raised ? 5 : 0')}}),node('second','Rect',{x:600,y:100,width:120,height:120,fill:'#f97316',zIndex:1})
 ],interactions:[interaction('size','input',[action('set',{path:'width',value:expr('event.value')})]),interaction('show','click',[action('set',{path:'showB',value:true})]),interaction('raise','click',[action('set',{path:'raised',value:true})]),interaction('first','click',[action('set',{path:'clicked',value:'first'})]),interaction('second','click',[action('set',{path:'clicked',value:'second'})])]}));
 await expect(byId(page,'a-cell')).toHaveAttribute('transform',/translate\(10 30\)/);await expect(byId(page,'c-cell')).toHaveAttribute('transform',/translate\(102 30\)/);expect(await byId(page,'b-cell').count()).toBe(0);
 await page.getByRole('button',{name:'Show B'}).click();await expect(byId(page,'c-cell')).toHaveAttribute('transform',/translate\(194 30\)/);await range(page,'size',120);await expect(byId(page,'c-cell')).toHaveAttribute('transform',/translate\(274 30\)/);
 await expect(byId(page,'g2')).toHaveAttribute('transform',/translate\(155 10\)/);await expect(byId(page,'g3')).toHaveAttribute('transform',/translate\(10 105\)/);
 const p=await point(page,'second',30,30);await page.mouse.click(p.x,p.y);expect(await state(page,'clicked')).toBe('second');await page.getByRole('button',{name:'Raise first'}).click();await page.mouse.click(p.x,p.y);expect(await state(page,'clicked')).toBe('first');
});

test('timeline seek/play/pause/stop, markers, bound speed and reduced motion are observable',async({page},info)=>{
 const scene=fixture({initialState:{x:0,seek:0,marker:0,speed:1},nodes:[node('dot','Circle',{x:50,y:150,radius:22,fill:'#2563eb'},{bind:{x:expr('state.x+50')}}),node('play','Button',{x:30,y:250,width:150,height:45,text:'Play'}),node('pause','Button',{x:200,y:250,width:150,height:45,text:'Pause'}),node('stop','Button',{x:370,y:250,width:150,height:45,text:'Stop'}),node('seek','Slider',{x:30,y:330,width:500,height:45,min:0,max:1000,step:100,ariaLabel:'Timeline seek'},{bind:{value:expr('state.seek')}})],timelines:[{id:'move',duration:1000,bind:{playbackRate:expr('state.speed')},tracks:[{path:'x',keyframes:[{time:0,value:0},{time:1000,value:400}]}],markers:[{time:600,actions:[action('increment',{path:'marker'})]}]}],interactions:[interaction('play','click',[action('playTimeline',{timeline:'move'})]),interaction('pause','click',[action('pauseTimeline',{timeline:'move'})]),interaction('stop','click',[action('stopTimeline',{timeline:'move'})]),interaction('seek','input',[action('set',{path:'seek',value:expr('event.value')}),action('seekTimeline',{timeline:'move',time:expr('event.value')})])]});
 await load(page,scene);await range(page,'seek',400);await expect.poll(()=>state(page,'x')).toBe(160);await expect(byId(page,'dot')).toHaveAttribute('transform',/translate\(210 150\)/);
 await page.getByRole('button',{name:'Play',exact:true}).click();await expect.poll(()=>state(page,'x')).toBeGreaterThan(180);await page.getByRole('button',{name:'Pause',exact:true}).click();const paused=await state(page,'x');await page.waitForTimeout(150);expect(await state(page,'x')).toBe(paused);await page.screenshot({path:info.outputPath('paused.png')});
 await page.getByRole('button',{name:'Play',exact:true}).click();await expect.poll(()=>state(page,'x')).toBe(400);expect(await state(page,'marker')).toBe(1);await page.getByRole('button',{name:'Stop',exact:true}).click();expect(await state(page,'x')).toBe(0);
 await page.emulateMedia({reducedMotion:'reduce'});await page.reload();await expect.poll(()=>page.evaluate(()=>(window as any).__interactive?.ready)).toBe(true);await page.getByRole('button',{name:'Play',exact:true}).click();await expect.poll(()=>state(page,'x')).toBe(400);expect(await page.evaluate(()=>(window as any).__interactive.runtime.timeline.states.move.playing)).toBe(false);
});

test('charts and GeoJSON expose selection metadata; pan/zoom and reset preserve data',async({page},info)=>{
 await load(page,charts);await page.screenshot({path:info.outputPath('charts-initial.png')});
 await byId(page,'bars.bar-1-1').click();await expect.poll(()=>state(page,'selectedBar')).toBe(1);await expect(byId(page,'bars.bar-1-1').locator('rect')).toHaveAttribute('stroke-width','3');
 // West polygon contains a hole, and all four supported geometry types render.
 await expect(byId(page,'map.geo-0-0').locator('path')).toHaveAttribute('fill-rule','evenodd');await expect(byId(page,'map.geo-1').locator('polyline')).toHaveCount(1);await expect(byId(page,'map.geo-3-1').locator('path')).toHaveCount(1);
 await byId(page,'map.geo-2').hover();await expect(byId(page,'hoverLabel')).toContainText('East point');await byId(page,'map.geo-2').click();await expect(byId(page,'choice')).toContainText('Selected: east');
 await dragParent(page,'map.geo-2',25,15);await expect.poll(()=>state(page,'mapX')).toBe(25);await expect.poll(()=>state(page,'mapY')).toBe(15);
 await byId(page,'map.geo-2').hover();await page.mouse.wheel(0,-100);await expect.poll(()=>state(page,'zoom')).toBeGreaterThan(1);await page.screenshot({path:info.outputPath('charts-selected-and-panned.png')});
 await page.getByRole('button',{name:'Reset view'}).click();expect(await state(page,'mapX')).toBe(0);expect(await state(page,'zoom')).toBe(1);expect(await page.evaluate(()=>(window as any).__interactive.runtime.store.getData().sales.length)).toBe(3);
});

test('data refresh updates chart/derived state and failed refresh retains last data with readable status',async({page})=>{
 let value=2,offline=false;await page.route('**/sales.json',route=>offline?route.abort('failed'):route.fulfill({json:[{label:'Today',value}]}));
 await load(page,fixture({dataSources:{sales:{type:'json',path:'sales.json',fallback:[]}},derivedState:{total:expr('sum(pluck(data.sales,"value"))')},nodes:[node('total','Text',{x:30,y:30,width:400,height:60},{bind:{text:expr('"Total " + state.total')}}),node('chart','component',{x:30,y:120,width:400,height:250,max:10},{component:'barChart',bind:{data:expr('data.sales')}}),node('refresh','Button',{x:30,y:450,width:200,height:45,text:'Refresh data'}),node('status','Text',{x:30,y:520,width:800,height:60,fontSize:18},{bind:{text:expr('state._dataStatus.sales.error || "Ready"')}})],interactions:[interaction('refresh','click',[action('refreshData',{name:'sales'})])]}));
 await expect(byId(page,'total')).toContainText('Total 2');const initialHeight=Number(await byId(page,'chart.bar-0-0').locator('rect').getAttribute('height'));value=9;await page.getByRole('button',{name:'Refresh data'}).click();await expect(byId(page,'total')).toContainText('Total 9');expect(Number(await byId(page,'chart.bar-0-0').locator('rect').getAttribute('height'))).toBeGreaterThan(initialHeight*4);
 offline=true;await page.getByRole('button',{name:'Refresh data'}).click();await expect(byId(page,'status')).toContainText('Failed to fetch');await expect(byId(page,'total')).toContainText('Total 9');expect(await page.locator('[role=alert]').count()).toBe(0);
});

test('media playback, seek, rate, cues and Reset work in the browser',async({page},info)=>{
 const scene=fixture({initialState:{time:0,cue:false},nodes:[node('audio','Audio',{x:30,y:80,width:700,height:60,src:'examples/assets/pulse.wav',timePath:'time',cues:[{time:.8,actions:[action('set',{path:'cue',value:true})]}]}),node('play','Button',{x:30,y:180,width:140,height:44,text:'Play audio'}),node('pause','Button',{x:200,y:180,width:140,height:44,text:'Pause audio'}),node('seek','Button',{x:370,y:180,width:140,height:44,text:'Seek audio'}),node('rate','Button',{x:540,y:180,width:140,height:44,text:'Double speed'}),node('reset','Button',{x:30,y:250,width:140,height:44,text:'Reset media'}),node('caption','Text',{x:30,y:330,width:700,height:60},{bind:{text:expr('state.cue ? "Cue reached" : "Listen for the cue"')}})],interactions:[interaction('play','click',[action('media',{target:'audio',method:'play'})]),interaction('pause','click',[action('media',{target:'audio',method:'pause'})]),interaction('seek','click',[action('media',{target:'audio',method:'currentTime',value:1.2})]),interaction('rate','click',[action('media',{target:'audio',method:'playbackRate',value:2})]),interaction('reset','click',[action('reset')])]});
 await load(page,scene);const media=page.locator('audio');await expect.poll(()=>media.evaluate((el:HTMLMediaElement)=>el.readyState)).toBeGreaterThanOrEqual(1);await page.getByRole('button',{name:'Play audio',exact:true}).click();await expect.poll(()=>state(page,'time')).toBeGreaterThan(0);await page.getByRole('button',{name:'Pause audio',exact:true}).click();expect(await media.evaluate((el:HTMLMediaElement)=>el.paused)).toBe(true);
 await page.getByRole('button',{name:'Seek audio'}).click();await expect(byId(page,'caption')).toContainText('Cue reached');expect(await media.evaluate((el:HTMLMediaElement)=>el.currentTime)).toBeCloseTo(1.2,1);await page.getByRole('button',{name:'Double speed'}).click();expect(await media.evaluate((el:HTMLMediaElement)=>el.playbackRate)).toBe(2);await page.screenshot({path:info.outputPath('media-cue.png')});
 await page.getByRole('button',{name:'Reset media'}).click();await expect(byId(page,'caption')).toContainText('Listen for the cue');expect(await media.evaluate((el:HTMLMediaElement)=>el.currentTime)).toBe(0);expect(await media.evaluate((el:HTMLMediaElement)=>el.paused)).toBe(true);
});

test('brush, resize, scrub, hover, selection, clip and mask share runtime semantics',async({page})=>{
 await load(page,fixture({initialState:{width:100,height:60,selected:'',hover:false,progress:0,brush:null},nodes:[node('parent','Group',{x:50,y:50,scale:1.5},{children:[node('resize','Rect',{fill:'#2563eb'},{bind:{width:expr('state.width'),height:expr('state.height')}}),node('brush','Rect',{x:180,y:0,width:180,height:140,fill:'#dbeafe'}),node('scrub','Rect',{x:0,y:200,width:300,height:30,fill:'#94a3b8'})]}),node('clipped','Rect',{x:650,y:50,width:200,height:150,clip:{x:10,y:10,width:60,height:60},mask:{x:50,y:50,radius:10}})],behaviors:[{type:'resize',target:'resize',widthPath:'width',heightPath:'height',snap:10},{type:'hoverHighlight',target:'resize',path:'hover'},{type:'select',target:'resize',path:'selected',value:'resized'},{type:'brush',target:'brush',path:'brush'},{type:'scrub',target:'scrub',path:'progress',min:0,max:1}]}));
 await byId(page,'resize').hover();expect(await state(page,'hover')).toBe(true);await dragParent(page,'resize',20,20);expect(await state(page,'width')).toBe(120);expect(await state(page,'height')).toBe(80);expect(await state(page,'selected')).toBe('resized');
 const from=await point(page,'brush',20,30),to=await point(page,'brush',90,100);await page.mouse.move(from.x,from.y);await page.mouse.down();await page.mouse.move(to.x,to.y);await page.mouse.up();const brush=await state(page,'brush');for(const [key,value] of Object.entries({x:20,y:30,width:70,height:70}))expect(brush[key]).toBeCloseTo(value,3);
 const middle=await point(page,'scrub',150,15);await page.mouse.click(middle.x,middle.y);expect(await state(page,'progress')).toBeCloseTo(.5,4);await expect(byId(page,'clipped').locator('clipPath rect')).toHaveAttribute('width','60');await expect(byId(page,'clipped').locator('mask circle')).toHaveAttribute('r','10');
});

test('invalid expressions and duplicate repeat keys show a fallback instead of blank content',async({page})=>{
 await page.route(url=>url.pathname==='/fixture.scene.json',route=>route.fulfill({json:fixture({initialState:{items:[{id:'same'},{id:'same'}]},nodes:[node('repeated','Text',{text:'duplicate'},{repeat:{source:expr('state.items'),item:'item',key:expr('item.id')}})]})}));await page.goto('/preview.html?spec=/fixture.scene.json');await expect(page.getByRole('alert')).toContainText('Interactive content unavailable.');await expect(page.getByRole('alert')).toContainText('Static slide content remains available.');
});

test('the primitive/component gallery paints vectors, rich text, canvas, assets and real local video',async({page},info)=>{
 await page.goto('/preview.html?spec=examples/primitives.scene.json&debug=1');await expect.poll(()=>page.evaluate(()=>(window as any).__interactive?.ready)).toBe(true);await expect(page.locator('.scene')).toBeVisible();
 await expect(byId(page,'rounded').locator('rect')).toHaveAttribute('rx','15');await expect(byId(page,'ellipse').locator('ellipse')).toHaveAttribute('rx','42.5');await expect(byId(page,'arrow').locator('line')).toHaveAttribute('marker-end',/arrow-arrow/);await expect(byId(page,'line').locator('line')).toHaveAttribute('x2','70');await expect(byId(page,'polygon').locator('polygon')).toHaveAttribute('points','0,60 40,0 80,60');await expect(byId(page,'rich')).toContainText('Rich text without raw HTML');
 const pixel=await byId(page,'canvas').locator('canvas').evaluate((el:HTMLCanvasElement)=>Array.from(el.getContext('2d')!.getImageData(65,30,1,1).data));expect(pixel).toEqual([37,99,235,255]);
 await expect(byId(page,'comparison.after').locator('clipPath rect')).toHaveAttribute('width','110');await expect(byId(page,'table.text-2-1')).toContainText('18');await expect(byId(page,'kpi.value')).toContainText('42');await expect(byId(page,'tooltip.content')).toContainText('State-aware tooltip');
 const video=page.locator('video');await expect.poll(()=>video.evaluate((el:HTMLVideoElement)=>el.readyState)).toBeGreaterThanOrEqual(2);expect(await video.evaluate((el:HTMLVideoElement)=>el.videoWidth)).toBe(256);await page.getByRole('button',{name:'Play video',exact:true}).click();await expect.poll(()=>video.evaluate((el:HTMLVideoElement)=>el.currentTime)).toBeGreaterThan(.15);await video.evaluate((el:HTMLVideoElement)=>el.pause());
 await page.screenshot({path:info.outputPath('primitive-gallery-and-video.png')});expect(await page.locator('[role=alert]').count()).toBe(0);
});

test('custom component templates bind supplied props and nested repetition obeys the global node budget',async({page})=>{
 await load(page,fixture({initialState:{label:'Scoped template'},components:{labelCard:{nodes:[node('label','Text',{width:300,height:55},{bind:{text:expr('props.label')}})]}},nodes:[node('custom','component',{x:30,y:30,width:300,height:55},{component:'labelCard',bind:{label:expr('state.label')}})]}));await expect(byId(page,'custom.label')).toContainText('Scoped template');
 await page.unrouteAll();await page.route(url=>url.pathname==='/fixture.scene.json',route=>route.fulfill({json:fixture({initialState:{outer:Array.from({length:100},(_,i)=>i),inner:Array.from({length:101},(_,i)=>i)},nodes:[node('groups','Group',{},{repeat:{source:expr('state.outer'),item:'outer',key:expr('outer')},children:[node('cells','Rect',{width:2,height:2},{repeat:{source:expr('state.inner'),item:'inner',key:expr('inner')}})]})]})}));await page.goto('/preview.html?spec=/fixture.scene.json&debug=1');await expect(page.getByRole('alert')).toContainText('Interactive content unavailable.');expect(await page.locator('[data-node-id]').count()).toBe(0);
});
