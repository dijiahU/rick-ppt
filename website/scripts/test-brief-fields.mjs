import test from 'node:test';
import assert from 'node:assert/strict';
import {briefCopy,composeBrief,emptyAnswers,missingFields} from '../lib/brief-fields.ts';
import {resolvePages} from '../lib/task-mode.ts';

const filled={...emptyAnswers,purpose:'课堂讲课',viewing:'我在现场投影讲',audience:'初二学生',familiarity:'第一次接触',outcome:'理解浮力和排开水的体积有关'};

test('all five locales have the same field set',()=>{
 const keys=Object.keys(briefCopy.en).sort();
 for(const [locale,copy] of Object.entries(briefCopy)){
  assert.deepEqual(Object.keys(copy).sort(),keys,locale);
  assert.equal(copy.purposes.length,briefCopy.en.purposes.length,locale);
  assert.equal(copy.viewings.length,4,locale);
 }
});

test('required answers are reported until filled',()=>{
 assert.equal(missingFields(emptyAnswers,briefCopy['zh-CN']).length,4);
 assert.deepEqual(missingFields(filled,briefCopy['zh-CN']),[]);
 assert.equal(missingFields({...filled,purpose:'other',purposeOther:' '},briefCopy['zh-CN']).length,1);
});

test('composed brief is labelled, skips empty optional lines and asks for labelled examples',()=>{
 const text=composeBrief(filled,'zh-CN');
 assert.match(text,/^场合：课堂讲课$/m);
 assert.match(text,/^观看方式：我在现场投影讲$/m);
 assert.match(text,/示例数字，非真实数据/);
 assert.doesNotMatch(text,/必须包含|不要出现|其他补充/);
 assert.ok(text.trim().length>=10&&text.length<=12000);
 const own=composeBrief({...filled,own:'门店 3 家',include:'实验步骤'},'zh-CN');
 assert.match(own,/^我提供的信息：门店 3 家$/m);
 assert.match(own,/^必须包含：实验步骤$/m);
 assert.match(composeBrief({...filled,purpose:'other',purposeOther:'婚礼致辞'},'en'),/^Occasion: 婚礼致辞$/m);
});

test('composed brief adds no page count of its own',()=>{
 for(const locale of Object.keys(briefCopy)){
  const choice=resolvePages('create',8,'Topic\n'+composeBrief(filled,locale));
  assert.equal(choice.error,undefined,locale);assert.equal(choice.pages,8,locale);
 }
});
