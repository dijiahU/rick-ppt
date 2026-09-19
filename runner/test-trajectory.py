import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
import sys

from trajectory import Trajectory,digest
from trajectory_history import sync


class TrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.job=self.root/'job';self.job.mkdir();self.directory=self.root/'trajectory'
        self.task={'id':str(uuid.uuid4()),'lease':'synthetic-private-lease','brief':'Explain photosynthesis','pages':3}
        self.run=Trajectory({'token':'synthetic-private-token'},self.task,self.directory)

    def tearDown(self):
        if not self.run.events.closed:self.run.events.close()
        if not self.run.steps.closed:self.run.steps.close()
        if not self.run.catalog.closed:self.run.catalog.close()
        self.temp.cleanup()

    def events(self):return [json.loads(line) for line in (self.run.root/'events.jsonl').read_text().splitlines()]

    def test_unshortened_actions_feedback_inputs_and_versions(self):
        (self.job/'notes.txt').write_text('before')
        (self.job/'image.png').write_bytes(b'\x89PNG\r\n\x1a\n\xfffixture')
        self.run.begin('author',self.job,'Read notes.txt; explain with an example.',['codex','exec','--json','-'])
        self.run.consume({'type':'thread.started','thread_id':'thread-a'})
        self.run.consume({'type':'turn.started'})
        self.run.consume({'type':'item.started','item':{'type':'command_execution','id':'item-1','command':'python edit.py'}})
        (self.job/'notes.txt').write_text('after')
        output='x'*150001+'😀'+' token=synthetic-private-token'
        self.run.consume({'type':'item.completed','item':{'type':'command_execution','id':'item-1','command':'python edit.py','aggregated_output':output,'exit_code':0}})
        self.run.consume({'type':'item.completed','item':{'type':'reasoning','id':'secret','text':'PRIVATE_CHAIN'}})
        self.run.end(result='Done.');self.run.finish('complete',self.job)
        events=self.events();raw=json.dumps(events)
        self.assertNotIn('PRIVATE_CHAIN',raw);self.assertNotIn('synthetic-private-token',raw);self.assertNotIn('synthetic-private-lease',raw)
        command=next(e for e in events if e['kind']=='item.completed')
        self.assertGreater(len(command['data']['item']['aggregated_output']),150001)
        step=json.loads((self.run.root/'steps.jsonl').read_text())
        self.assertIsNotNone(step['start_event_seq']);self.assertTrue(step['observation_present'])
        after=json.loads((self.run.root/'snapshots'/(step['after_snapshot']+'.json')).read_text())
        ref=after['files']['notes.txt']['sha256'];self.assertEqual((self.run.root/'blobs'/ref).read_text(),'after')
        self.assertTrue((self.run.root/'blobs'/digest(b'before')).exists())
        self.assertTrue((self.run.root/'blobs'/digest(b'\x89PNG\r\n\x1a\n\xfffixture')).exists())
        manifest=json.loads((self.run.root/'manifest.json').read_text())
        prompt=manifest['phases'][0]['supplied_prompt']['sha256']
        self.assertEqual((self.run.root/'blobs'/prompt).read_text(),'Read notes.txt; explain with an example.')
        self.assertFalse(manifest['coverage']['exact_model_requests'])
        self.assertEqual(self.run.root.stat().st_mode&0o777,0o700)

    def test_scope_no_symlink_escape_and_explicit_missing_feedback(self):
        outside=self.root/'outside-secret';outside.write_text('OUTSIDE_SECRET')
        (self.job/'escape').symlink_to(outside)
        self.run.begin('research',self.job,'Read scoped files.',['codex'])
        self.run.consume({'type':'item.completed','item':{'id':'web1','type':'web_search','action':{'query':'plants'}}})
        self.run.end();self.run.finish('failed',self.job)
        blobs=b''.join(p.read_bytes() for p in (self.run.root/'blobs').iterdir())
        self.assertNotIn(b'OUTSIDE_SECRET',blobs)
        codes={g['code'] for g in self.run.gaps}
        self.assertIn('snapshot_incomplete',codes);self.assertIn('hosted_search_observation_unavailable',codes)
        self.assertFalse(json.loads((self.run.root/'steps.jsonl').read_text())['observation_present'])

    def test_independent_sessions_partial_lines_and_same_item_ids(self):
        for stage in ('author','visual-1'):
            self.run.begin(stage,self.job,'Stage '+stage,['codex'])
            raw=json.dumps({'type':'item.completed','item':{'id':'item-1','type':'agent_message','text':stage}}).encode()
            self.run.poll(io.BytesIO(raw));self.assertEqual(self.run.offset,0)
            self.run.poll(io.BytesIO(raw+b'\n'));self.run.end()
        self.run.finish('complete')
        steps=[json.loads(line) for line in (self.run.root/'steps.jsonl').read_text().splitlines()]
        self.assertEqual(len(steps),2);self.assertNotEqual(steps[0]['phase_id'],steps[1]['phase_id'])

    def test_legacy_phase_captures_observation_and_working_file(self):
        from workflow import Execution
        script='''import json,sys,subprocess
sys.stdin.read()
print(json.dumps({'type':'thread.started','thread_id':'thread-real'}),flush=True)
print(json.dumps({'type':'item.started','item':{'id':'cmd','type':'command_execution','command':'python -c "print(42)"'}}),flush=True)
r=subprocess.run([sys.executable,'-c','print(42)'],capture_output=True,text=True)
open('actual-output.txt','w').write(r.stdout)
print(json.dumps({'type':'item.completed','item':{'id':'cmd','type':'command_execution','command':'python -c "print(42)"','aggregated_output':r.stdout,'exit_code':r.returncode}}),flush=True)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':3,'output_tokens':2}}),flush=True)
open(sys.argv[sys.argv.index('--output-last-message')+1],'w').write('Actual output 42.')
'''
        bridge=SimpleNamespace(ROOT=self.root,codex_command=lambda cfg,job:[sys.executable,'-c',script,'-'],environment=lambda job:{},render_requests=lambda root,**kwargs:None)
        reporter=SimpleNamespace(offset=0,poll=lambda *a:None,flush=lambda **k:None,last_sent=0)
        with patch('workflow.AssetImporter') as importer,patch('workflow.WebMediaBroker'):
            importer.return_value.poll=lambda *a:None
            run=Execution(bridge,{},self.task,self.job,SimpleNamespace(check=lambda:None),reporter,trajectory=self.run)
            result,thread=run._legacy_phase('research','Run the observable fixture.',timeout=10)
            run.trace.close()
        self.run.finish('complete',self.job)
        self.assertEqual(result,'Actual output 42.');self.assertEqual(thread,'thread-real')
        self.assertTrue(any(e['data'].get('item',{}).get('aggregated_output')=='42\n' for e in self.events()))
        self.assertTrue((self.run.root/'blobs'/digest(b'42\n')).exists())

    def test_history_recovery_is_read_only_idempotent_and_labeled(self):
        old=str(uuid.uuid4());queued=str(uuid.uuid4());records=self.root/'records';records.mkdir()
        (records/(old+'-old.jsonl')).write_text(json.dumps({'type':'item.completed','item':{'id':'a','type':'command_execution','command':'echo old','aggregated_output':'old\n','exit_code':0}})+'\n')
        jobs=[{'id':old,'status':'complete','updated_at':1},{'id':queued,'status':'queued','updated_at':1}]
        calls=[]
        def read(*args):
            calls.append(args)
            if args[0]=='list':return {'jobs':jobs,'total':2,'limit':25}
            self.assertEqual(args[:2],('fetch',old));source=Path(args[-1])/'fetched';source.mkdir(parents=True)
            (source/'request.json').write_text(json.dumps({'job':jobs[0]}));(source/'output.pptx').write_bytes(b'PKfixture')
            return {'directory':str(source)}
        result=sync(self.directory,read,records)
        self.assertEqual(result['recovered'],1);self.assertEqual(result['pending'],1)
        manifest=json.loads(next((self.directory/old).glob('*/manifest.json')).read_text())
        self.assertEqual(manifest['source_mode'],'historical-recovery');self.assertIsNone(manifest['attempt_id'])
        self.assertFalse(manifest['coverage']['supplied_phase_prompts'])
        self.assertEqual(sync(self.directory,read,records)['recovered'],0)
        self.assertEqual(sum(c[0]=='fetch' for c in calls),1)
        self.assertTrue((self.directory/queued/'task.json').exists())

    def test_runner_delivery_finalizes_a_local_trajectory(self):
        import runner
        import workflow
        runner_root=self.root/'runner';runner_root.mkdir()
        reporter=SimpleNamespace(event=lambda *a:None,flush=lambda **k:None)
        lease=SimpleNamespace(check=lambda:None,finish=lambda:None)
        with patch.object(runner,'ROOT',runner_root),patch.object(runner,'prepare',return_value=self.job),\
             patch.object(runner,'request',return_value={'ok':True}),patch.object(runner,'Reporter',return_value=reporter),\
             patch('language.presentation_request',return_value={'brief':'fixture'}),patch('attachments.receive',return_value=[]),\
             patch.object(workflow,'run_workflow',return_value={'artifact':b'PKfixture','revision':0}),patch.object(Trajectory,'runtime'):
            runner._run_job({'token':'synthetic-private-token','plugin':str(self.root/'fixture-plugin'),'plugin_version':'synthetic'},self.task,lease)
        manifests=[json.loads(p.read_text()) for p in self.directory.glob('*/*/manifest.json')]
        self.assertTrue(any(m['status']=='complete' for m in manifests))
        event_files=list(self.directory.glob('*/*/events.jsonl'))
        self.assertTrue(any('delivery.completed' in p.read_text() for p in event_files))

if __name__=='__main__':unittest.main()
