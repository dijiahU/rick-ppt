"""Real journal restoration with a new Execution; no model, HTTP or live task."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

from durable import Journal
from progress import Reporter
from repair_recovery import recovery_route
from workflow import Execution, _run_workflow, write_json


def outline():
    return {'title':'Binary search', 'purpose':'Understand the shrinking interval', 'slides':[
        {'id':'intro','title':'Sorted input','summary':'Sorting permits discarding half the search interval.'},
        {'id':'worked','title':'Worked example','summary':'Trace midpoint comparisons and the termination condition.'}]}


def findings(digest, number, revision=0, *, legacy=False):
    content = {'summary':'Actual correction needed', 'pages_reviewed':[1,2], 'limitations':[], 'findings':[
        {'id':'content-1','severity':'required','pages':[2], 'observation':'The stopping condition is missing.',
         'impact':'The learner cannot terminate the algorithm.', 'recommendation':'Show the stopping condition.'}]}
    visual = {**content, 'findings':[]}
    value = {'artifact_sha256':digest, 'round':number, 'content_first_view':content,
             'content':content, 'visual':visual}
    if not legacy:
        value.update(input_revision=revision, plugin_version='test-plugin')
    return value


class ReviewReached(RuntimeError):
    pass


class RepairRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='pptx-repair-recovery-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.job = self.root/'original'; self.job.mkdir()
        self.records = self.root/'records'; self.records.mkdir()
        self.plugin = self.root/'plugin'; self.plugin.mkdir()
        self.task = {'id':str(uuid.uuid4()), 'lease':'synthetic', 'pages':2, 'language':'en',
                     'title':'Binary search', 'brief':'Explain the stopping condition', 'style':'Clear'}
        self.cfg = {'plugin':str(self.plugin), 'python':sys.executable, 'token':'synthetic'}
        self.journal = Journal(self.root/'state', self.task['id'], plugin_version='test-plugin')
        self.addCleanup(lambda:self.journal.close())
        self.original = b'SYNTHETIC ORIGINAL PPTX BYTES; NO NATIVE VALIDATION CLAIM'
        (self.job/'original.pptx').write_bytes(self.original)
        write_json(self.job/'delivery.json', {'path':'original.pptx'})
        write_json(self.job/'outline.json', outline())
        (self.job/'source-notes.md').write_text('Original source notes')
        self.calls = []

    def seed(self, *, number=1, phase='repair', completed=False, legacy=False, revision=0):
        for n in range(revision):
            identifier = str(uuid.uuid4())
            self.journal.accept_message(identifier, f'Ordered revision {n+1}')
            self.journal.begin_delivery(identifier, f'request-{n}', 'original-author')
            self.journal.acknowledge_message(identifier, turn_id=f'turn-{n}')
        producer = 'author' if number == 1 else 'repair-1'
        self.journal.begin_phase(producer, self.job, thread_id='original-author')
        self.journal.complete_phase(producer, self.job, artifacts=['delivery.json','original.pptx'],
                                    next_phase='review', require_applied=False)
        self.baseline = self.journal.state['completed_stages'][producer]
        self.receipt = findings(hashlib.sha256(self.original).hexdigest(), number, revision, legacy=legacy)
        self.findings_name = f'review-findings-{number}-original.json'
        write_json(self.job/self.findings_name, self.receipt)
        self.host_record = self.records/(self.task['id']+'-review-original.json')
        write_json(self.host_record, self.receipt)
        content_name = f'content-revision-{number}'
        self.journal.begin_phase(content_name, self.job, thread_id='content-thread')
        if phase == 'repair' or completed:
            self.journal.complete_phase(content_name, self.job,
                artifacts=['outline.json','source-notes.md'] + ([] if legacy else [self.findings_name]),
                next_phase=f'repair-{number}', require_applied=False)
        if phase == 'repair':
            self.journal.begin_phase(f'repair-{number}', self.job, thread_id='interrupted-repair-thread')
            if completed:
                (self.job/'repaired.pptx').write_bytes(b'COMPLETED SYNTHETIC REPAIR')
                (self.job/'delivery.json').write_text(json.dumps({'path':'repaired.pptx'}))
                self.journal.complete_phase(f'repair-{number}', self.job,
                    artifacts=['delivery.json','repaired.pptx',self.findings_name],
                    next_phase='review', require_applied=False)
        (self.job/'partial-work.txt').write_text('Retain this observed partial work.')
        self.journal.checkpoint(self.job, reason='test_interruption')
        self.journal.interrupt(reason='synthetic_disconnect')

    def restore(self):
        destination = self.root/('restored-'+uuid.uuid4().hex)
        plan = self.journal.recover(destination, plugin_version='test-plugin')
        self.journal.close()
        self.journal = Journal(self.root/'state', self.task['id'], plugin_version='test-plugin')
        # Both a new host object and a new workspace are required by this test.
        def request(*args, **kwargs):
            return {'messages':[], 'revision':self.journal.state['message_cursor'], 'ok':True}
        bridge = SimpleNamespace(ROOT=self.root, request=request, environment=lambda root:{})
        reporter = Reporter(self.cfg, self.task, destination, request, explicit_previews=True)
        trace = Mock(); trace.path=self.root/'trace.jsonl'; trace.roots={}
        run = Execution(bridge, self.cfg, self.task, destination, SimpleNamespace(check=lambda:None),
                        reporter, trace=trace, journal=self.journal, recovery_plan=plan)
        frozen = self.root/('frozen-'+uuid.uuid4().hex); frozen.mkdir()
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=')
        pages = []
        for n in (1,2):
            path=frozen/f'page-{n}.png';path.write_bytes(png);pages.append(str(path))
        def freeze():
            return ((destination/run.delivery()['path']).read_bytes(), frozen, {'pages':pages}, frozen/'packet')
        run.freeze = Mock(side_effect=freeze)
        run.review = Mock(side_effect=ReviewReached('independent review boundary'))
        return run, bridge, reporter

    def server(self, run, *, fail=None):
        owner = self
        class FakeServer:
            def __init__(self, **kwargs):
                self.event=kwargs['on_event'];self.completed_turns={};self.active_turns={}
            def __enter__(self):return self
            def __exit__(self, *args):return False
            def start_thread(self):
                self.thread='new-thread-'+uuid.uuid4().hex
                return {'thread':{'id':self.thread}}
            def resume_thread(self, thread):
                self.thread=thread
                return {'thread':{'id':thread}}
            def start_turn(self, thread, prompt, **kwargs):
                name=owner.journal.state['phase']['name']
                owner.calls.append((name, thread, prompt))
                if name == fail:
                    (run.job/'retained-failure.txt').write_text('Partial repair remains available')
                    raise RuntimeError('synthetic repair disconnect')
                if name.startswith('content-revision-') or name == 'research':
                    (run.job/'outline.json').write_text(json.dumps(outline()))
                    (run.job/'source-notes.md').write_text('Verified stopping condition')
                elif name.startswith('repair-') or name == 'author':
                    export=f'export-{name}-{uuid.uuid4().hex}.pptx'
                    (run.job/export).write_bytes(b'FRESH SYNTHETIC EXPORT')
                    (run.job/'delivery.json').write_text(json.dumps({'path':export}))
                turn='turn-'+uuid.uuid4().hex
                self.event({'type':'turn.started','thread_id':thread,'turn_id':turn})
                self.completed_turns[(thread,turn)]={'status':'completed'}
                self.event({'type':'turn.completed','thread_id':thread,'turn_id':turn,'status':'completed'})
                return {'id':turn}
            def pump(self, timeout):pass
            def result_text(self, thread, turn):return 'Synthetic completed phase'
        return FakeServer

    def execute(self, run, bridge, reporter, *, fail=None):
        with patch('workflow.task_configuration', return_value={}), patch('workflow.AppServer', self.server(run, fail=fail)):
            return _run_workflow(run, bridge, self.cfg, self.task, run.job, {'mode':'create'}, run.lease, reporter)

    def assert_review_round(self, run, number):
        self.assertEqual(run.review.call_args.args[-1], number)
        self.assertEqual((run.job/'original.pptx').read_bytes(), self.original)
        self.assertEqual((self.job/'original.pptx').read_bytes(), self.original)
        self.assertEqual((run.job/'partial-work.txt').read_text(), 'Retain this observed partial work.')

    def test_interrupted_repair_precedes_unchanged_author_and_resumes_its_thread(self):
        self.seed(legacy=True, revision=7)
        run,bridge,reporter=self.restore()
        self.assertTrue(self.journal.can_reuse('author',run.job))  # The original bug trigger.
        with self.assertRaises(ReviewReached):self.execute(run,bridge,reporter)
        self.assertEqual([(x[0],x[1]) for x in self.calls],[('repair-1','interrupted-repair-thread')])
        self.assert_review_round(run,2)
        self.assertEqual(run.recovery_plan,{})
        self.assertEqual(self.journal.state['input_revision'],7)
        context=json.loads(next((run.job/'conversation-inputs').glob('*.json')).read_text())
        self.assertEqual([r['text'] for r in context['requests']],[f'Ordered revision {n}' for n in range(1,8)])
        self.assertIn(self.findings_name,self.journal.state['completed_stages']['repair-1']['artifacts'])
        self.assertIn('fresh filename under exports/',self.calls[0][2])

    def test_unfinished_content_can_repair_its_partial_outline_before_host_validation(self):
        self.seed(phase='content')
        (self.job/'outline.json').write_text('{unfinished')
        self.journal.checkpoint(self.job,reason='partial_outline')
        run,bridge,reporter=self.restore()
        with self.assertRaises(ReviewReached):self.execute(run,bridge,reporter)
        self.assertEqual([(x[0],x[1]) for x in self.calls],
                         [('content-revision-1','content-thread'),('repair-1','original-author')])
        self.assert_review_round(run,2)
        self.assertIn(self.findings_name,self.journal.state['completed_stages']['content-revision-1']['artifacts'])

    def test_completed_content_goes_directly_to_repair(self):
        self.seed(phase='content',completed=True)
        run,bridge,reporter=self.restore()
        with self.assertRaises(ReviewReached):self.execute(run,bridge,reporter)
        self.assertEqual([(x[0],x[1]) for x in self.calls],[('repair-1','original-author')])
        self.assert_review_round(run,2)

    def test_completed_second_repair_continues_round_three_without_authoring(self):
        self.seed(number=2,completed=True)
        run,bridge,reporter=self.restore()
        with self.assertRaises(ReviewReached):self.execute(run,bridge,reporter)
        self.assertEqual(self.calls,[])
        self.assert_review_round(run,3)

    def test_disconnect_does_not_create_completion_or_replace_original(self):
        self.seed()
        run,bridge,reporter=self.restore()
        with self.assertRaisesRegex(RuntimeError,'synthetic repair disconnect'):
            self.execute(run,bridge,reporter,fail='repair-1')
        run.review.assert_not_called()
        self.assertNotIn('repair-1',self.journal.state['completed_stages'])
        self.assertEqual(self.journal.state['phase']['status'],'interrupted')
        self.assertEqual((run.job/'original.pptx').read_bytes(),self.original)
        self.assertTrue((run.job/'retained-failure.txt').exists())

    def test_changed_revision_does_not_apply_previous_findings(self):
        self.seed(revision=6)
        identifier=str(uuid.uuid4());self.journal.accept_message(identifier,'Ordered revision 7')
        self.journal.begin_delivery(identifier,'new-request','old-thread')
        self.journal.acknowledge_message(identifier,turn_id='new-turn')
        self.journal.checkpoint(self.job,reason='new_user_revision')
        run,bridge,reporter=self.restore()
        with self.assertRaises(ReviewReached):self.execute(run,bridge,reporter)
        self.assertEqual([x[0] for x in self.calls],['research','author'])
        self.assertNotIn(self.findings_name,self.calls[-1][2])
        self.assert_review_round(run,1)
        self.assertEqual(self.journal.state['input_revision'],7)
        contexts=[json.loads(p.read_text()) for p in (run.job/'conversation-inputs').glob('*.json')]
        self.assertTrue(all(len(c['requests'])==7 for c in contexts))

    def test_changed_baseline_cannot_resume_old_findings_or_reuse_older_author(self):
        self.seed()
        (self.job/'original.pptx').write_bytes(b'CHANGED BASELINE')
        self.journal.checkpoint(self.job,reason='changed_baseline')
        run,bridge,reporter=self.restore()
        self.assertFalse(run.reusable_author())
        self.assertIsNone(run.correction_recovery.repair_round)
        self.assertTrue(run.correction_recovery.block_author)

    def test_legacy_task_findings_alone_or_tampered_copy_are_not_authority(self):
        self.seed(legacy=True)
        (self.job/self.findings_name).write_text(json.dumps({**self.receipt,'arbitrary':'changed'}))
        route=recovery_route(self.journal,self.job,records=self.records,task_id=self.task['id'])
        self.assertIsNone(route.repair_round);self.assertTrue(route.block_author)
        # No host record: a perfectly formed task file still cannot authorize repair.
        isolated=self.root/'empty-records';isolated.mkdir()
        (self.job/self.findings_name).write_text(json.dumps(self.receipt))
        route=recovery_route(self.journal,self.job,records=isolated,task_id=self.task['id'])
        self.assertIsNone(route.repair_round)

    def test_explicit_host_identity_recreates_missing_findings_without_overwriting(self):
        self.seed()
        (self.job/self.findings_name).rename(self.job/'preserved-findings-copy.json')
        self.journal.checkpoint(self.job,reason='missing_findings')
        run,bridge,reporter=self.restore()
        with self.assertRaises(ReviewReached):self.execute(run,bridge,reporter)
        self.assert_review_round(run,2)
        self.assertTrue((run.job/'preserved-findings-copy.json').exists())
        new=list(run.job.glob('review-findings-1-*.json'))
        self.assertEqual(len(new),1);self.assertNotEqual(new[0].name,self.findings_name)
        self.assertEqual(json.loads(new[0].read_text()),self.receipt)

    def test_out_of_interval_or_stale_plugin_host_record_is_rejected(self):
        self.seed()
        state=self.journal.state
        os.utime(self.host_record,ns=(state['phase']['started_at']+1,state['phase']['started_at']+1))
        self.assertIsNone(recovery_route(self.journal,self.job,records=self.records,task_id=self.task['id']).repair_round)
        self.host_record.write_text(json.dumps({**self.receipt,'plugin_version':'stale-plugin'}))
        middle=(self.baseline['completed_at']+state['phase']['started_at'])//2
        os.utime(self.host_record,ns=(middle,middle))
        self.assertIsNone(recovery_route(self.journal,self.job,records=self.records,task_id=self.task['id']).repair_round)

    def test_ambiguous_host_findings_and_symlinks_are_rejected(self):
        self.seed()
        second={**self.receipt,'different_review':'ambiguous'}
        other=self.records/(self.task['id']+'-review-second.json');write_json(other,second)
        middle=(self.baseline['completed_at']+self.journal.state['phase']['started_at'])//2
        os.utime(other,ns=(middle,middle))
        self.assertIsNone(recovery_route(self.journal,self.job,records=self.records,task_id=self.task['id']).repair_round)
        symbolic=self.root/'records-link';symbolic.symlink_to(self.records,target_is_directory=True)
        self.assertIsNone(recovery_route(self.journal,self.job,records=symbolic,task_id=self.task['id']).repair_round)

    def test_completed_repair_with_changed_artifacts_blocks_old_author_fallback(self):
        self.seed(completed=True)
        (self.job/'repaired.pptx').write_bytes(b'CHANGED REPAIRED EXPORT')
        self.journal.checkpoint(self.job,reason='changed_repair')
        run,bridge,reporter=self.restore()
        self.assertFalse(run.reusable_author())
        self.assertTrue(run.correction_recovery.block_author)
        self.assertEqual(run.correction_recovery.review_round,1)


if __name__=='__main__':unittest.main()
