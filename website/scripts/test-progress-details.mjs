import test from 'node:test';
import assert from 'node:assert/strict';
import {parseProgress} from '../lib/progress.ts';
const payload=(event)=>({updatedAt:1,events:[{seq:1,at:1,code:'working',...event}],previews:[]});
test('details survive; unknown raw fields are discarded; old events remain valid',()=>{
 const r=parseProgress(payload({detail:'Checking the example',reported:true,state:'started',reasoning:'PRIVATE',command:'PRIVATE'}));
 assert.equal(r.events[0].detail,'Checking the example');assert.equal(r.events[0].reported,true);
 assert.equal(JSON.stringify(r).includes('PRIVATE'),false);assert.ok(parseProgress(payload({})));
});
test('unsafe links are omitted and details bounded',()=>{
 for(const url of ['javascript:alert(1)','http://localhost/x','http://127.0.0.1/x','https://user:pass@example.com','https://example.com/?token=private'])assert.equal(parseProgress(payload({url})).events[0].url,undefined);
 assert.equal(parseProgress(payload({url:'https://example.com/paper'})).events[0].url,'https://example.com/paper');
 assert.equal(parseProgress(payload({detail:'x'.repeat(801)})),null);
 assert.equal(parseProgress(payload({state:'invented'})),null);
});
test('fine-grained categories, 500 events, and resource URLs survive',()=>{
 const r=parseProgress({updatedAt:1,events:Array.from({length:500},(_,i)=>({seq:i+1,at:1,code:'working',category:'source',url:'https://www.youtube.com/watch?v=abc123',detail:'x'.repeat(800)})),previews:[]});
 assert.equal(r.events.length,500);assert.equal(r.events[0].category,'source');assert.match(r.events[0].url,/v=abc123/);
 assert.equal(parseProgress({...r,events:[...r.events,{seq:501,at:1,code:'working'}]}),null);
 assert.equal(parseProgress(payload({category:'reasoning'})),null);
});
test('public design notes, page numbers and next actions survive independently of commands',()=>{
 const note={seq:1,at:1,code:'working',reported:true,category:'note',phase:'design',slide:2,detail:'Use a comparison.',next:'Render this page.',reasoning:'PRIVATE'};
 const result=parseProgress({updatedAt:2,events:[{seq:501,at:2,code:'working'}],notes:[note],previews:[2],previewVersions:{2:'0123456789abcdef'}});
 assert.equal(result.notes[0].phase,'design');assert.equal(result.notes[0].slide,2);
 assert.equal(result.notes[0].next,'Render this page.');assert.equal(JSON.stringify(result).includes('PRIVATE'),false);
 assert.equal(result.previewVersions[2],'0123456789abcdef');
 for(const patch of [{phase:'reasoning'},{slide:0},{slide:51},{slide:true},{next:'x'.repeat(401)}])assert.equal(parseProgress(payload({...note,...patch})),null);
 assert.equal(parseProgress({...result,notes:[{...note,reported:false}]}),null);
 assert.equal(parseProgress({...result,previewVersions:{2:'https://example.com/token'}}),null);
 assert.equal(parseProgress({...result,previewVersions:{3:'0123456789abcdef'}}),null);
 assert.equal(parseProgress(payload(note)).notes[0].detail,'Use a comparison.');
});
