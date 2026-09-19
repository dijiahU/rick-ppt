import test from 'node:test';
import assert from 'node:assert/strict';
import {resolvePages} from '../lib/task-mode.ts';
import {parseProgress} from '../lib/progress.ts';
import {pageProgress} from '../lib/creation-progress.ts';

test('explicit brief total overrides fallback, including Chinese and full-width numbers',()=>{
 for(const brief of ['请做30页，介绍中国历史。','制作三十页PPT。','请做３０页的课件。','Create a 30-slide presentation.','30 slides about history.','Faire 30 diapositives.','Crear 30 diapositivas.','30枚のプレゼンテーションを作成してください。','页数：30']){
  assert.deepEqual(resolvePages('create',15,brief),{pages:30,source:'brief'},brief);
 }
 assert.equal(resolvePages('create',undefined,'做30页的介绍').pages,30);
 assert.deepEqual(resolvePages('create',30,'介绍产品的功能与使用场景'),{pages:30,source:'input'});
 assert.deepEqual(resolvePages('edit',15,'把30页改成40页'),{pages:0,source:'edit'});
});
test('slide references, source lengths and content numbers do not override the total',()=>{
 for(const brief of ['第30页介绍总结。','阅读参考资料30页，介绍历史。','Read a 30-page report and summarize it.','介绍30个人物，每章5页。','参考第30页到第40页。','插入5张图片介绍主题。','30枚の写真を使ってください。']){
  assert.deepEqual(resolvePages('create',15,brief),{pages:15,source:'input'},brief);
 }
 assert.equal(resolvePages('create',15,'参考30页资料，做20页的PPT，第1页介绍背景。').pages,20);
 assert.equal(resolvePages('create',15,'不要15页，要30页。').pages,30);
 assert.equal(resolvePages('create',15,'封面1页，正文28页，结尾1页，总共30页。').pages,30);
});
test('ambiguous totals, ranges and invalid counts stop before admission',()=>{
 for(const brief of ['做20页，做30页。','做20-30页。','做20页至30页。','最多30页。'])assert.equal(resolvePages('create',15,brief).error,'pagesAmbiguous',brief);
 for(const brief of ['做51页。','做0页。','做-5页。','做30.5页。'])assert.ok(resolvePages('create',15,brief).error,brief);
 for(const pages of [0,51,2.5,null,undefined,'30'])assert.equal(resolvePages('create',pages,'介绍产品').error,'pagesRange');
});
test('30-page outline, public progress, final preview and page cards stay intact',()=>{
 const slides=Array.from({length:30},(_,i)=>({id:`s${i+1}`,title:`第 ${i+1} 页`,summary:'具体内容摘要'}));
 const data={updatedAt:1,events:[{seq:1,at:1,code:'rendered',slide:30}],previews:Array.from({length:30},(_,i)=>i+1),previewVersions:{30:'0123456789abcdef'},outline:{revision:'0123456789abcdef',title:'三十页',purpose:'说明完整主题',slides}};
 const parsed=parseProgress(data);assert.ok(parsed);assert.equal(parsed.previews.at(-1),30);
 const cards=pageProgress(parsed,30);assert.equal(cards.length,30);assert.equal(cards.at(-1).preview,true);assert.equal(cards.at(-1).outline.id,'s30');
 assert.equal(parseProgress({...data,previews:[51]}),null);
});
