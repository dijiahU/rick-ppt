import test from 'node:test';
import assert from 'node:assert/strict';
import {queueReason,QUEUE_CAPACITY} from '../lib/queue-state.ts';
test('queue explanations distinguish offline, full capacity, pickup and idle',()=>{
  const queue={online:true,running:0,queued:2,capacity:QUEUE_CAPACITY};
  assert.equal(queueReason(queue),'waiting');
  assert.equal(queueReason({...queue,running:3}),'busy');
  assert.equal(queueReason({...queue,online:false,running:3}),'offline');
  assert.equal(queueReason({...queue,queued:0}),'idle');
});
