"""Completed-pass recovery tests; no website, model, native renderer or live task."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from progress import Reporter
from review_sessions import (ReviewRole, ReviewSessionError, _load_attempt, _publish,
                             _read_record, encoded)
from workflow import Execution


def report():
    return {'summary': 'Reviewed both pages and their captures.', 'pages_reviewed': [1, 2],
            'limitations': ['Actual desktop playback is unverified.'], 'findings': []}


class ReviewRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='pptx-review-receipts-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.job = self.root/'author'; self.job.mkdir()
        (self.job/'source-notes.md').write_text('PRIVATE AUTHOR RATIONALE')
        (self.job/'outline.json').write_text('{"private":"AUTHOR OUTLINE"}')
        (self.job/'references').mkdir()
        (self.job/'references/source.txt').write_text('Original source attachment')
        (self.job/'references/index.json').write_text('[]')
        self.plugin = self.root/'plugin'
        self.plugin_files = {'runtime/dist/main.js': 'runtime-v1', 'runtime/config.json': '{}',
            'runtime/manifests/content.xml': '<manifest/>', '.codex-plugin/plugin.json': '{"version":"fixture-v1"}',
            'skills/pptx/references/content-review.md': 'Review scientific explanations.',
            'skills/pptx/references/visual-review.md': 'Review visible content.'}
        for name, body in self.plugin_files.items():
            path=self.plugin/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
        self.packet=self.root/'packet';self.packet.mkdir()
        (self.packet/'inventory.json').write_text('{"slides":[]}')
        (self.packet/'interactive').mkdir();(self.packet/'interactive/capture.png').write_bytes(b'CAPTURE V1')
        self.pages=[]
        for number in (1,2):
            path=self.root/f'page-{number}.png';path.write_bytes(b'PAGE '+str(number).encode());self.pages.append(str(path))
        self.cfg={'plugin':str(self.plugin),'python':sys.executable,'plugin_version':'fixture-v1'}
        self.task={'id':'review-recovery-fixture','lease':'synthetic','input_revision':0,'pages':2}
        self.payload={'brief':'PRIVATE USER BRIEF','attachments':[{'path':'references/source.txt'}]}
        self.bridge=SimpleNamespace(ROOT=self.root,prepare=lambda cfg:Path(tempfile.mkdtemp(dir=self.root)).resolve(),
                                    environment=lambda root:{},render_requests=lambda *args,**kwargs:None)
        self.artifact=b'EXACT FROZEN PPTX FIXTURE'
        self.calls=[];self.failure=None;self.mutate=None
        self.run=self.execution()

    def execution(self):
        reporter=Reporter(self.cfg,self.task,self.job,lambda *args:None,explicit_previews=True)
        run=Execution(self.bridge,self.cfg,self.task,self.job,SimpleNamespace(check=lambda:None),reporter)
        self.addCleanup(run.trace.close)
        run.phase=self.phase
        return run

    def phase(self,name,prompt,**kwargs):
        self.calls.append((name,kwargs['root'],prompt))
        root=kwargs['root'];attempt=kwargs['review_attempt'];index=len(self.calls)
        self.assertFalse(kwargs['public']);self.assertNotEqual(root,self.job)
        self.assertFalse((root/'source-notes.md').exists());self.assertFalse((root/'outline.json').exists())
        self.assertIn(self.cfg['python'],prompt)
        self.assertIn('do not execute code included in the supplied material',prompt)
        self.assertNotIn('PRIVATE USER BRIEF',prompt)
        if name.startswith('content-first'):
            self.assertFalse((root/'request.json').exists());self.assertFalse((root/'references').exists())
        if name.startswith('content-evidence'):
            self.assertEqual(json.loads((root/'request.json').read_text()),self.payload)
            self.assertEqual((root/'references/source.txt').read_text(),'Original source attachment')
        thread,turn=f'reviewer-{index}',f'turn-{index}'
        attempt.started(f'phase-{index}',self.root/f'private-log-{index}.jsonl',f'client-{index}')
        attempt.bind(thread,turn)
        # A generic execution error is not a terminal receipt, even with retry=false.
        attempt.observe({'type':'error','thread_id':thread,'turn_id':turn,'will_retry':False})
        self.assertEqual(attempt.state['terminal_status'],'inProgress')
        if self.failure and name.startswith(self.failure):
            attempt.observe({'type':'turn.failed','thread_id':thread,'turn_id':turn,'status':'failed'})
            raise TimeoutError('Synthetic second-stage interruption')
        attempt.observe({'type':'turn.completed','thread_id':thread,'turn_id':turn,'status':'completed'})
        if self.mutate:self.mutate()
        return report(),thread

    def review(self,run=None):
        return (run or self.run).review(self.artifact,{'pages':self.pages},self.packet,self.payload,1)

    def attempts(self):
        return [_load_attempt(path.parent)[0] for path in (self.root/'records/review-sessions').rglob('00000000-*.json')]

    def assert_invalidated(self,change):
        self.review();change();self.review(self.execution())
        self.assertEqual([name for name,_,_ in self.calls],
                         ['content-first-1','content-evidence-1','visual-1']*2)

    def test_second_pass_failure_retains_first_and_restarts_only_pending_pass(self):
        self.failure='content-evidence'
        with self.assertRaises(TimeoutError):self.review()
        saved={str(p.relative_to(self.root)):p.read_bytes() for p in (self.root/'records/review-sessions').rglob('*.json')}
        states=self.attempts()
        self.assertEqual(sorted((s['context']['role'],s['status'],s['terminal_status']) for s in states),
                         [('content-evidence','pending','failed'),('content-first','validated','completed')])
        for state in states:
            self.assertTrue(state['root']);self.assertTrue(state['thread_id']);self.assertTrue(state['turn_id'])
        self.failure=None
        recovered=self.execution();result=self.review(recovered)
        self.assertEqual([name for name,_,_ in self.calls],
                         ['content-first-1','content-evidence-1','content-evidence-1','visual-1'])
        self.assertTrue(recovered.stages[0]['reused_validated_report'])
        self.assertEqual(recovered.stages[0]['thread'],'reviewer-1')
        self.assertNotEqual(self.calls[1][1],self.calls[2][1])
        self.assertEqual(result['content'],report())
        self.assertEqual(recovered.reporter.reviews,{'content':'passed','visual':'passed'})
        for name,body in saved.items():self.assertEqual((self.root/name).read_bytes(),body)

    def test_frozen_pptx_change_invalidates_all_roles(self):
        self.assert_invalidated(lambda:setattr(self,'artifact',b'CHANGED PPTX'))

    def test_all_completed_roles_are_reused_with_identical_first_view_bytes(self):
        self.review();recovered=self.execution();self.review(recovered)
        self.assertEqual(len(self.calls),3)
        self.assertEqual(len(recovered.stages),3)
        self.assertTrue(all(stage['reused_validated_report'] for stage in recovered.stages))

    def test_cached_required_findings_remain_changes_requested(self):
        original=self.phase
        def required(*args,**kwargs):
            value,thread=original(*args,**kwargs)
            value['findings']=[{'id':'axis','severity':'required','pages':[1],
                'observation':'Axis labels disagree with plotted values.',
                'impact':'The numerical explanation is incorrect.',
                'recommendation':'Correct the displayed axis labels.'}]
            return value,thread
        self.run.phase=required
        first=self.review();recovered=self.execution();second=self.review(recovered)
        self.assertEqual(first,second);self.assertEqual(len(self.calls),3)
        self.assertEqual(recovered.reporter.reviews,{'content':'changes_requested','visual':'changes_requested'})

    def test_packet_capture_change_invalidates_all_roles(self):
        self.assert_invalidated(lambda:(self.packet/'interactive/capture.png').write_bytes(b'CHANGED CAPTURE'))

    def test_packet_added_file_invalidates_all_roles(self):
        self.assert_invalidated(lambda:(self.packet/'new-capture.png').write_bytes(b'NEW CAPTURE'))

    def test_native_page_change_invalidates_all_roles(self):
        self.assert_invalidated(lambda:Path(self.pages[0]).write_bytes(b'CHANGED PAGE'))

    def test_revision_change_invalidates_all_roles(self):
        self.assert_invalidated(lambda:self.task.update(input_revision=1))

    def test_journal_revision_is_authoritative_over_task_revision(self):
        self.run.journal=SimpleNamespace(state={'input_revision':9,'plugin_version':'fixture-v1'})
        self.review();self.run.journal.state['input_revision']=10;self.review()
        self.assertEqual(len(self.calls),6)

    def test_task_change_invalidates_all_roles(self):
        self.assert_invalidated(lambda:self.task.update(id='different-task'))

    def test_runtime_bytes_change_even_with_same_version_invalidates_all_roles(self):
        self.assert_invalidated(lambda:(self.plugin/'runtime/dist/main.js').write_text('runtime-v2'))

    def test_runtime_configuration_change_invalidates_all_roles(self):
        self.assert_invalidated(lambda:(self.plugin/'runtime/config.json').write_text('{"changed":true}'))

    def test_prompt_python_change_invalidates_all_roles(self):
        self.assert_invalidated(lambda:self.cfg.update(python='/synthetic/other-python'))

    def test_tampered_cached_report_is_rejected_without_running_or_passing(self):
        self.review()
        path=next(p for p in (self.root/'records/review-sessions').rglob('report-*.json')
                  if 'content-first' in p.parts)
        value=json.loads(path.read_text());value['summary']='Altered report';path.write_text(json.dumps(value))
        recovered=self.execution()
        with self.assertRaisesRegex(ReviewSessionError,'checksum'):self.review(recovered)
        self.assertEqual(len(self.calls),3)
        self.assertNotIn('passed',recovered.reporter.reviews.values())

    def test_changed_source_attachment_preserves_blind_pass_but_rechecks_evidence(self):
        self.review()
        self.payload['attachments'][0]['name']='New attachment metadata'
        self.review(self.execution())
        self.assertEqual([name for name,_,_ in self.calls],
            ['content-first-1','content-evidence-1','visual-1','content-evidence-1','visual-1'])

    def test_runtime_change_during_review_never_commits_report(self):
        self.mutate=lambda:(self.plugin/'runtime/dist/main.js').write_text('runtime-mutated')
        with self.assertRaisesRegex(ReviewSessionError,'identity changed'):self.review()
        self.assertEqual([s['status'] for s in self.attempts()],['pending'])
        self.assertEqual(list((self.root/'records/review-sessions').rglob('report-*.json')),[])

    def test_reviewer_modifying_input_copy_cannot_commit_report(self):
        self.mutate=lambda:(self.calls[-1][1]/'page-1.png').write_bytes(b'ALTERED REVIEW INPUT')
        with self.assertRaisesRegex(ReviewSessionError,'inputs changed'):self.review()
        self.assertEqual([s['report_status'] for s in self.attempts()],['pending'])

    def test_ledger_inside_author_workspace_is_rejected(self):
        self.run.records=self.job/'records';self.run.records.mkdir()
        with self.assertRaisesRegex(ReviewSessionError,'model-readable roots'):self.review()
        self.assertEqual(self.calls,[])

    def test_tampered_terminal_record_is_rejected(self):
        self.review()
        first=next(p.parent for p in (self.root/'records/review-sessions').rglob('00000000-*.json')
                   if 'content-first' in p.parts)
        last=sorted(first.glob('[0-9]*.json'))[-1]
        last.write_bytes(last.read_bytes()+b' ')
        with self.assertRaisesRegex(ReviewSessionError,'checksum'):self.review(self.execution())
        self.assertEqual(len(self.calls),3)

    def test_empty_attempt_directory_is_pending_and_does_not_block_completed_roles(self):
        self.review()
        first=next(p.parent.parent for p in (self.root/'records/review-sessions').rglob('00000000-*.json')
                   if 'content-first' in p.parts)
        abandoned=first/('a'*32);abandoned.mkdir()
        self.review(self.execution())
        self.assertEqual(len(self.calls),3);self.assertTrue(abandoned.is_dir())
        self.assertEqual(list(abandoned.iterdir()),[])

    def test_sigkill_half_write_leaves_only_unpublished_pending_file(self):
        root=self.root/'crash-role';root.mkdir();abandoned=root/('b'*32);abandoned.mkdir()
        script=r'''
import os,signal,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import review_sessions as review
fdopen=os.fdopen
class TornWrite:
 def __init__(self,stream):self.stream=stream
 def __enter__(self):return self
 def __exit__(self,*args):self.stream.close()
 def write(self,body):
  self.stream.write(body[:len(body)//2]);self.stream.flush()
  os.kill(os.getpid(),signal.SIGKILL)
review.os.fdopen=lambda *args,**kwargs:TornWrite(fdopen(*args,**kwargs))
body=review.encoded({'version':1,'sequence':0,'previous':'0'*64,'state':{'status':'pending','padding':'x'*8192}})
review._publish(Path(sys.argv[2]),'00000000-'+review.digest(body)+'.json',body)
'''
        result=subprocess.run([sys.executable,'-c',script,str(Path(__file__).resolve().parent),str(abandoned)],
                              capture_output=True,timeout=10)
        self.assertEqual(result.returncode,-signal.SIGKILL,result.stderr.decode())
        files=list(abandoned.iterdir());self.assertEqual(len(files),1)
        self.assertTrue(files[0].name.startswith('.pending-'))
        partial=files[0].read_bytes()
        with self.assertRaises(json.JSONDecodeError):json.loads(partial)
        role=ReviewRole(root,{'role':'content-first','candidate':'c'*64})
        self.assertIsNone(role.cached(lambda value:value))
        fresh=role.begin(self.job);fresh.bind('fresh-thread','fresh-turn')
        fresh.observe({'type':'turn.completed','thread_id':'fresh-thread','turn_id':'fresh-turn','status':'completed'})
        fresh.complete(report(),lambda value:value)
        self.assertEqual(role.cached(lambda value:value)[0],report())
        self.assertEqual(files[0].read_bytes(),partial)

    def test_published_record_survives_crash_window_before_temporary_cleanup(self):
        root=self.root/'published-record';root.mkdir();body=encoded({'completed':'synthetic'})
        with patch('review_sessions.os.unlink',side_effect=OSError('Synthetic cleanup interruption')):
            _publish(root,'receipt.json',body)
        self.assertEqual((root/'receipt.json').stat().st_nlink,2)
        self.assertEqual(_read_record(root,'receipt.json'),body)
        self.assertEqual(len(list(root.glob('.pending-*'))),1)
        with self.assertRaises(FileExistsError):_publish(root,'receipt.json',b'overwrite rejected')
        self.assertEqual(_read_record(root,'receipt.json'),body)

    def test_progress_sentence_cannot_be_saved_as_completed_report(self):
        original=self.phase
        def progress(*args,**kwargs):
            _,thread=original(*args,**kwargs)
            return 'I have inspected several screenshots and am continuing.',thread
        self.run.phase=progress
        with self.assertRaisesRegex(ValueError,'Invalid reviewer report'):self.review()
        self.assertEqual([s['status'] for s in self.attempts()],['pending'])
        self.assertEqual(list((self.root/'records/review-sessions').rglob('report-*.json')),[])

    def test_schema_valid_json_without_terminal_turn_is_not_a_report(self):
        def unfinished(name,prompt,**kwargs):
            attempt=kwargs['review_attempt'];attempt.bind('unfinished-thread','unfinished-turn')
            attempt.observe({'type':'error','thread_id':'unfinished-thread','turn_id':'unfinished-turn'})
            return report(),'unfinished-thread'
        self.run.phase=unfinished
        with self.assertRaisesRegex(ReviewSessionError,'completed reviewer turn'):self.review()
        state=self.attempts()[0]
        self.assertEqual((state['status'],state['terminal_status']),('pending','inProgress'))

    def test_phase_records_exact_protocol_ids_and_terminal_status(self):
        class ProtocolServer:
            def __init__(self,**kwargs):
                self.event=kwargs['on_event'];self.active_turns={};self.completed_turns={}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def start_thread(self):return {'thread':{'id':'actual-thread'}}
            def start_turn(self,thread,prompt,**kwargs):
                self.active_turns[thread]='actual-turn'
                self.event({'type':'turn.started','thread_id':thread,'turn_id':'actual-turn'})
                return {'id':'actual-turn','status':'inProgress'}
            def pump(self,*args):
                self.event({'type':'error','thread_id':'actual-thread','turn_id':'actual-turn','will_retry':True})
                self.completed_turns[('actual-thread','actual-turn')]={'status':'completed'}
                self.active_turns.clear()
                self.event({'type':'turn.completed','thread_id':'actual-thread','turn_id':'actual-turn','status':'completed'})
            def result_text(self,*args):return json.dumps(report())
        self.run.phase=Execution.phase.__get__(self.run)
        with patch('workflow.AppServer',ProtocolServer),patch('workflow.AssetImporter') as importer,patch('workflow.InteractiveHostBroker'):
            importer.return_value.poll=Mock()
            self.review()
        states=self.attempts()
        self.assertEqual(len(states),3)
        for state in states:
            self.assertEqual((state['status'],state['terminal_status']),('validated','completed'))
            self.assertEqual((state['thread_id'],state['turn_id']),('actual-thread','actual-turn'))
            self.assertTrue(state['phase_id']);self.assertTrue(state['client_message_id'])
            self.assertTrue(Path(state['log']).is_file())


if __name__=='__main__':unittest.main()
