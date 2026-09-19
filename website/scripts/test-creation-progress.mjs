import test from 'node:test';
import assert from 'node:assert/strict';
import {progressNotes,pageProgress,previewVersion} from '../lib/creation-progress.ts';
test('old jobs show their recorded notes without invented progress; edits show only encountered pages',()=>{
 const p={updatedAt:123,events:[{seq:1,reported:true,detail:'Plan',slide:4},{seq:2,code:'working'}],previews:[4]};
 assert.equal(progressNotes(p).length,1);
 assert.deepEqual(pageProgress(p,0).map(p=>p.slide),[4]);
 assert.equal(pageProgress(p,5).length,5);
 assert.equal(pageProgress(p,5)[0].preview,false);
 assert.equal(pageProgress(p,5)[3].preview,true);
 assert.equal(previewVersion(p,4),'123');
 assert.equal(previewVersion({...p,previewVersions:{4:'0123456789abcdef'},updatedAt:999},4),'0123456789abcdef');
 assert.equal(progressNotes(null).length,0);
});
