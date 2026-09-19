import test from 'node:test';
import assert from 'node:assert/strict';
import {parseProgress,parseOutline} from '../lib/progress.ts';
import {pageProgress} from '../lib/creation-progress.ts';
const outline={revision:'abcdef0123456789',title:'二分查找',purpose:'理解排序前提与终止条件',slides:[{id:'intro',title:'为什么每次可以排除一半',summary:'用七个有序数字走完查找 19 的过程。',section:'原理'},{id:'edge',title:'找不到时如何停下',summary:'左右边界交错意味着候选区间为空。'}]};
const progress={updatedAt:1,events:[],previews:[],outline,reviews:{content:'reviewing',visual:'pending'}};
test('outline remains useful before any preview and retains substantive page content',()=>{
 const parsed=parseProgress(progress);assert.ok(parsed);
 const pages=pageProgress(parsed,0);assert.equal(pages.length,2);
 assert.equal(pages[0].outline.summary,outline.slides[0].summary);
 assert.equal(pages[0].preview,false);
 assert.deepEqual(parsed.reviews,progress.reviews);
});
test('malformed outlines and reviewer states are rejected; internal properties are discarded',()=>{
 assert.equal(parseOutline({...outline,revision:1234567890123456}),null);
 assert.equal(parseOutline({...outline,slides:[outline.slides[0],outline.slides[0]]}),null);
 assert.equal(parseOutline({...outline,slides:[{...outline.slides[0],summary:''}]}),null);
 assert.equal(parseProgress({...progress,reviews:{content:'perfect',visual:'passed'}}),null);
 assert.equal(parseOutline({...outline,source_notes:'PRIVATE'}).source_notes,undefined);
 assert.ok(parseProgress({updatedAt:1,events:[],previews:[1]}));
});

test('interactive outline metadata is preserved as bounded public data',()=>{
 const interaction={scene:'cnn-patch',purpose:'Move the kernel',bounds:{x:0,y:914400,width:10058400,height:4114800}};
 const input={...outline,slides:[{...outline.slides[0],presentationMode:'hybrid',interaction:{...interaction,internal:'PRIVATE'}}]};
 const parsed=parseOutline(input);assert.ok(parsed);
 assert.equal(parsed.slides[0].presentationMode,'hybrid');assert.deepEqual(parsed.slides[0].interaction,interaction);
 assert.deepEqual(parseProgress({...progress,outline:input}).outline,parsed);
 assert.equal(pageProgress({...progress,outline:parsed},0)[0].outline.interaction.scene,'cnn-patch');
 assert.deepEqual(parseOutline({...outline,slides:[{...outline.slides[0],interaction:{scene:'scene',purpose:'  Explain  one patch  '}}]}).slides[0].interaction,{scene:'scene',purpose:'Explain one patch'});
});
test('interactive outline rejects invalid modes, paths, private text and bad rectangles',()=>{
 const valid={scene:'cnn-patch',purpose:'Move the kernel',bounds:{x:0,y:0,width:100,height:100}};
 for(const mode of ['script',null,1,[]])assert.equal(parseOutline({...outline,slides:[{...outline.slides[0],presentationMode:mode}]}),null);
 for(const interaction of [null,[],{}, {...valid,scene:'../scene.json'},{...valid,scene:'https://example.org/scene'}, {...valid,purpose:'/Users/rick/private.txt'},{...valid,purpose:'api_key=private-value'}, {...valid,bounds:{}},{...valid,bounds:{...valid.bounds,width:0}}, {...valid,bounds:{...valid.bounds,width:true}}, {...valid,bounds:{...valid.bounds,width:Infinity}}, {...valid,bounds:{...valid.bounds,width:1.5}}, {...valid,bounds:{...valid.bounds,x:2147483647}}]){
  assert.equal(parseOutline({...outline,slides:[{...outline.slides[0],interaction}]}),null);
 }
});
