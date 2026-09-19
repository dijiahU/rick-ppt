import io
import json
from pathlib import Path
import tempfile
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch
from admin_trace import AdminTrace


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.calls=[]
        self.trace=AdminTrace({'token':'synthetic-bridge-credential'}, {'id':'test','lease':'test'},lambda *a:self.calls.append(a) or {'ok':True},self.root)
        self.trace.begin('research',self.root/'job')

    def tearDown(self):self.trace.close();self.temp.cleanup()

    def test_commands_outputs_and_notes_are_retained_but_reasoning_is_not(self):
        items=[
            {'type':'reasoning','text':'PRIVATE_CHAIN'},
            {'type':'command_execution','id':'c1','command':'python script.py --token=synthetic-bridge-credential','aggregated_output':'Authorization: Bearer hidden-credential\noutput: 30 slides','exit_code':0},
            {'type':'agent_message','id':'n1','text':'已读完资料，将用实例解释这个概念。'},
            {'type':'web_search','id':'s1','action':{'query':'binary search','url':'https://example.com?token=hidden-query'}},
        ]
        for item in items:self.trace.consume({'type':'item.completed','item':item})
        self.trace.flush(force=True)
        raw='\n'.join(c[2].decode() for c in self.calls)
        self.assertNotIn('PRIVATE_CHAIN',raw)
        for secret in ('synthetic-bridge-credential','hidden-credential','hidden-query'):self.assertNotIn(secret,raw)
        self.assertIn('output: 30 slides',raw);self.assertIn('python script.py',raw)
        self.assertIn('已读完资料',raw)
        self.assertEqual(self.trace.path.stat().st_mode&0o777,0o600)

    def test_partial_log_and_completed_command_failure(self):
        item={'type':'item.completed','item':{'id':'c','type':'command_execution','command':'exit 2','aggregated_output':'failure details','exit_code':2}}
        raw=json.dumps(item).encode();stream=io.BytesIO(raw)
        self.trace.poll(stream);self.assertEqual(self.trace.offset,0)
        stream=io.BytesIO(raw+b'\n');self.trace.poll(stream);self.trace.flush(force=True)
        events=[e for c in self.calls for e in json.loads(c[2])['events']]
        self.assertEqual(events[-1]['state'],'failed');self.assertEqual(events[-1]['exitCode'],2)

    def test_lost_ack_retry_keeps_identical_chunk_and_no_event_loss(self):
        bodies=[]
        def send(*args):
            bodies.append(args[2])
            if len(bodies)==1:raise RuntimeError('lost acknowledgement')
            return {'ok':True}
        self.trace.send=send
        self.trace.flush(force=True)
        self.trace.emit('note','New record',detail='after timeout')
        self.trace.flush(force=True)
        self.assertEqual(bodies[0],bodies[1])
        self.assertEqual(json.loads(bodies[2])['events'][0]['seq'],2)
        self.assertEqual(self.trace.chunk,3)

    def test_long_output_is_marked_and_review_stage_is_recorded(self):
        self.trace.begin('visual-1',self.root/'review')
        self.trace.emit('command','Render',output='x'*100001)
        self.trace.flush(force=True)
        events=[e for c in self.calls for e in json.loads(c[2])['events']]
        self.assertEqual(events[-1]['stage'],'visual-1');self.assertTrue(events[-1]['truncated'])

    def test_legacy_subprocess_captures_command_and_stage_result(self):
        from workflow import Execution
        script='''import json,sys,subprocess
sys.stdin.read()
command=[sys.executable,'-c','print(6 * 7)']
print(json.dumps({'type':'thread.started','thread_id':'fixture-thread'}),flush=True)
print(json.dumps({'type':'item.started','item':{'id':'c','type':'command_execution','command':'python -c "print(6 * 7)"'}}),flush=True)
result=subprocess.run(command,capture_output=True,text=True)
print(json.dumps({'type':'item.completed','item':{'id':'c','type':'command_execution','command':'python -c "print(6 * 7)"','aggregated_output':result.stdout,'exit_code':result.returncode}}),flush=True)
print(json.dumps({'type':'item.completed','item':{'id':'private','type':'reasoning','text':'PRIVATE_CHAIN'}}),flush=True)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}),flush=True)
open(sys.argv[sys.argv.index('--output-last-message')+1],'w').write('Command returned 42.')
'''
        bridge=SimpleNamespace(ROOT=self.root,codex_command=lambda cfg,job:[sys.executable,'-c',script,'-'],environment=lambda job:{},render_requests=lambda root:None)
        reporter=SimpleNamespace(offset=0,poll=lambda *a:None,flush=lambda **k:None,last_sent=0)
        self.trace.roots[str(self.root)]='$WORKSPACE'
        with patch('workflow.AssetImporter') as assets,patch('workflow.WebMediaBroker'):
            assets.return_value.poll=lambda *a:None
            execution=Execution(bridge,{},self.trace.task,self.root,SimpleNamespace(check=lambda:None),reporter,trace=self.trace)
            result,thread=execution._legacy_phase('research','Perform one observable command.',timeout=10)
        self.assertEqual(thread,'fixture-thread');self.assertEqual(result,'Command returned 42.')
        self.trace.flush(force=True)
        events=[e for c in self.calls for e in json.loads(c[2])['events']]
        self.assertTrue(any(e.get('output')=='42\n' for e in events))
        self.assertTrue(any(e.get('detail')=='Command returned 42.' for e in events))
        self.assertNotIn('PRIVATE_CHAIN',json.dumps(events))

    def test_unicode_output_respects_receiving_javascript_limit(self):
        self.trace.emit('command','Unicode output',output='a'+'😀'*50000)
        self.trace.flush(force=True)
        event=json.loads(self.calls[-1][2])['events'][-1]
        self.assertTrue(event['truncated'])
        self.assertLessEqual(len(event['output'].encode('utf-16-le'))//2,100000)
        self.assertTrue(event['output'].endswith('😀'))


if __name__=='__main__':unittest.main()
