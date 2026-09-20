import base64
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import zipfile

from outline import validate_outline,page_version
from progress import Reporter
from workflow import Execution,validate_report,budget_summary,usage_summary,phase_time_limit,_run_workflow
from conversation import RevisionPending
from durable import Journal
from office_policy import validate_delivery,validate_workbook


def outline():
    return {'title':'二分查找','purpose':'理解区间为何缩小','slides':[{'id':'intro','title':'有序的前提','summary':'说明有序数组怎样让我们排除一半候选。'},{'id':'example','title':'实际查找','summary':'用具体数组展示中间值、区间变化和停止条件。'}]}


def report(pages=2,findings=None):
    return {'summary':'Reviewed actual pages','pages_reviewed':list(range(1,pages+1)),'limitations':['PowerPoint playback not tested'],'findings':findings or []}


def zip_bytes(files):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name,value in files.items():z.writestr(name,value)
    return out.getvalue()


class ContentWorkflowTests(unittest.TestCase):
    def test_complex_authoring_override_keeps_the_global_deadline(self):
        self.assertEqual(phase_time_limit({},'author',2700,9000),2700)
        cfg={'phase_timeout_seconds':{'author':7200}}
        self.assertEqual(phase_time_limit(cfg,'author',2700,9000),7200)
        self.assertEqual(phase_time_limit(cfg,'author',2700,1200),1200)
        self.assertEqual(phase_time_limit(cfg,'research',2700,9000),2700)
        for value in (True,'7200',0,10801,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                phase_time_limit({'phase_timeout_seconds':{'author':value}},'author',2700,9000)

    def test_outline_is_substantive_scoped_and_stable(self):
        a=validate_outline(outline(),2);b=validate_outline({**a,'internal':'not published'},2)
        self.assertEqual(a,b);self.assertNotIn('internal',b)
        reordered={**outline(),'slides':list(reversed(outline()['slides']))}
        self.assertNotEqual(page_version(a,1),page_version(validate_outline(reordered),1))
        for value in ({**outline(),'purpose':'/Users/rick/private.txt'}, {**outline(),'slides':[outline()['slides'][0]]*2}):
            with self.assertRaises(ValueError):validate_outline(value)
        with self.assertRaises(ValueError):validate_outline(outline(),3)

    def test_old_previews_are_removed_when_outline_reorders(self):
        with tempfile.TemporaryDirectory() as temp:
            sent=[];r=Reporter({}, {'id':'test','lease':'test','pages':2},Path(temp),lambda *args:sent.append(args),explicit_previews=True)
            r.set_outline(outline());r.previews={1:'a'*64,2:'b'*64}
            r.preview_content={n:page_version(r.outline,n) for n in (1,2)}
            changed=outline();changed['slides'][1]['summary']='增加未找到时的停止例子。'
            r.set_outline(changed)
            self.assertEqual(list(r.previews),[1])
            changed['slides'].reverse();r.set_outline(changed)
            self.assertEqual(r.previews,{})
            r.flush(force=True);body=json.loads(sent[-1][2]);self.assertEqual(body['outline']['slides'][0]['id'],'example')

    def test_review_coverage_and_findings_must_be_valid(self):
        validate_report(report(),2)
        with self.assertRaises(ValueError):validate_report(report(1),2)
        bad=report(findings=[{'id':'x','severity':'required','pages':[3],'observation':'a','impact':'b','recommendation':'c'}])
        with self.assertRaises(ValueError):validate_report(bad,2)

    def test_usage_does_not_turn_cached_input_into_research(self):
        usage=usage_summary([{'type':'turn.completed','usage':{'input_tokens':10000,'cached_input_tokens':9000,'output_tokens':100,'reasoning_output_tokens':30}}])
        self.assertEqual(usage['output_tokens'],100)
        stages=[{'name':'research','content_work':True,'seconds':30,'usage':usage},{'name':'author','content_work':False,'seconds':90,'usage':{**usage,'output_tokens':900}}]
        budget=budget_summary(stages)
        self.assertEqual(budget['stage_elapsed_content_share'],.25);self.assertEqual(budget['output_token_content_share'],.1)
        self.assertNotIn('actual_target_met',budget);self.assertFalse(budget['fixed_share_required'])
        self.assertEqual(budget['priority'],'content-first')

    def test_reviewers_receive_only_intended_material(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);job=root/'author';job.mkdir();(job/'source-notes.md').write_text('PRIVATE AUTHOR RATIONALE')
            (job/'outline.json').write_text(json.dumps(outline()));(job/'references').mkdir();(job/'references/source.txt').write_text('Actual source')
            (job/'references/index.json').write_text('[]')
            packet=root/'packet';packet.mkdir();(packet/'inventory.json').write_text('{}')
            images=[]
            for n in (1,2):p=root/f'page-{n}.png';p.write_bytes(b'PNG');images.append(str(p))
            def prepare(cfg):
                p=Path(tempfile.mkdtemp(dir=root));return p
            bridge=SimpleNamespace(ROOT=root,prepare=prepare)
            reporter=Reporter({}, {'id':'test','lease':'test','pages':2},job,lambda *a:None,explicit_previews=True)
            execute=Execution(bridge,{'plugin':str(root),'python':sys.executable},{'id':'test'},job,SimpleNamespace(check=lambda:None),reporter)
            self.addCleanup(execute.trace.close)
            calls=[]
            def phase(name,prompt,**kwargs):
                p=kwargs['root'];calls.append(p)
                self.assertNotEqual(p,job);self.assertFalse((p/'source-notes.md').exists());self.assertFalse((p/'outline.json').exists())
                self.assertTrue((p/'page-1.png').exists())
                if 'first' in name:self.assertFalse((p/'request.json').exists())
                if 'evidence' in name:self.assertEqual((p/'references/source.txt').read_text(),'Actual source')
                return report(),'independent-'+name
            execute.phase=phase
            result=execute.review(b'FROZEN',{'pages':images},packet,{'attachments':[{'path':'references/source.txt'}]},1)
            self.assertEqual(len(set(calls)),3);self.assertEqual(reporter.reviews,{'content':'passed','visual':'passed'})
            self.assertEqual(len(result['artifact_sha256']),64)

    def test_only_passive_chart_workbooks_are_allowed(self):
        workbook=zip_bytes({'[Content_Types].xml':'<Types/>','xl/workbook.xml':'<workbook/>'})
        validate_workbook(workbook)
        rel='<Relationships><Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package" Target="../embeddings/data.xlsx"/></Relationships>'
        deck=zip_bytes({'ppt/charts/_rels/chart1.xml.rels':rel,'ppt/embeddings/data.xlsx':workbook})
        validate_delivery(deck)
        for malicious in (zip_bytes({'xl/workbook.xml':'<workbook/>','[Content_Types].xml':'<Types/>','xl/vbaProject.bin':b'x'}),zip_bytes({'xl/workbook.xml':'<workbook/>','[Content_Types].xml':'<Types/>','xl/_rels/workbook.xml.rels':'<Relationships><Relationship TargetMode="External" Target="https://example.com"/></Relationships>'})):
            with self.assertRaises(ValueError):validate_workbook(malicious)
        with self.assertRaises(ValueError):validate_delivery(zip_bytes({'ppt/embeddings/data.xlsx':workbook}))


class RecoveryPreviewTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='pptx-recovered-preview-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve();self.job=self.root/'author';self.job.mkdir()
        self.frozen=self.root/'frozen';self.frozen.mkdir()
        self.task={'id':'preview-recovery','lease':'synthetic','title':'Search','brief':'Explain binary search',
                   'pages':2,'style':'Clear','language':'en'}
        self.cfg={'plugin':str(self.root/'plugin'),'python':sys.executable}
        (self.job/'outline.json').write_text(json.dumps(outline()))
        self.artifact=b'FROZEN NATIVE TEST FIXTURE'
        (self.job/'authored.pptx').write_bytes(self.artifact)
        (self.job/'delivery.json').write_text(json.dumps({'path':'authored.pptx'}))
        # Real durable author receipt: reuse does not depend on a mocked verdict.
        self.journal=Journal(self.root/'state',self.task['id'],plugin_version='0.2.0')
        self.addCleanup(self.journal.close)
        self.journal.begin_phase('author',self.job,thread_id='saved-author-thread')
        self.journal.complete_phase('author',self.job,artifacts=['delivery.json','authored.pptx'],next_phase='review')
        self.journal_before=self.journal.state
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=')
        self.pages=[]
        for number in (1,2):
            page=self.frozen/f'page-{number}.png';page.write_bytes(png);self.pages.append(str(page))
        self.sent=[]
        self.reporter=Reporter(self.cfg,self.task,self.job,lambda *args:self.sent.append(args),explicit_previews=True)
        self.run=SimpleNamespace(conversation=None,journal=self.journal,job=self.job,author_thread=None,
            phase=Mock(side_effect=AssertionError('Completed author must not run again')),
            reusable=Mock(side_effect=AssertionError('Completed author bypasses stale research')),
            review_tick=Mock(),freeze=Mock(return_value=(self.artifact,self.frozen,{'pages':self.pages},self.frozen/'packet')),
            review=Mock(side_effect=TimeoutError('Synthetic independent review timeout')))
        self.run.reusable_author=lambda:Execution.reusable_author(self.run)

    def execute(self):
        return _run_workflow(self.run,SimpleNamespace(),self.cfg,self.task,self.job,{'mode':'create'},
                             SimpleNamespace(check=lambda:None),self.reporter)

    def previews(self):
        return [call for call in self.sent if 'action=preview' in call[1]]

    def test_recovered_candidates_are_visible_before_review_without_restoring_passed(self):
        self.reporter.set_outline(outline())
        self.reporter.reviews={'content':'passed','visual':'passed'}
        def review(*args):
            self.assertEqual(len(self.previews()),2)
            self.assertEqual([call[2] for call in self.previews()],[Path(p).read_bytes() for p in self.pages])
            self.assertEqual(self.reporter.preview_content,{n:page_version(self.reporter.outline,n) for n in (1,2)})
            body=json.loads(self.sent[-1][2]);self.assertEqual(body['previews'],[1,2])
            self.assertEqual(body['reviews'],{'content':'pending','visual':'pending'})
            self.reporter.review_state('content','reviewing');self.reporter.flush(force=True)
            raise TimeoutError('Synthetic independent review timeout')
        self.run.review.side_effect=review
        with self.assertRaisesRegex(TimeoutError,'Synthetic independent review timeout'):self.execute()
        self.run.phase.assert_not_called();self.run.reusable.assert_not_called()
        self.assertEqual(self.run.author_thread,'saved-author-thread')
        self.assertEqual(self.journal.state,self.journal_before)
        self.assertEqual((self.job/'authored.pptx').read_bytes(),self.artifact)
        self.assertEqual(sorted(self.reporter.previews),[1,2])
        self.assertEqual(self.reporter.reviews,{'content':'reviewing','visual':'pending'})
        self.assertFalse((self.job/'delivery-versions').exists())

    def test_failed_freeze_does_not_publish_candidates_or_enter_review(self):
        self.run.freeze.side_effect=ValueError('Synthetic native validation failure')
        with self.assertRaisesRegex(ValueError,'Synthetic native validation failure'):self.execute()
        self.assertEqual(self.previews(),[]);self.assertEqual(self.reporter.pending,{})
        self.run.review.assert_not_called();self.run.phase.assert_not_called()
        self.assertEqual(self.journal.state,self.journal_before)

    def test_input_during_candidate_publication_returns_to_revision_before_review(self):
        self.run.review_tick.side_effect=[None,RevisionPending('New input')]
        self.run.phase.side_effect=RuntimeError('Synthetic revision entry')
        with self.assertRaisesRegex(RuntimeError,'Synthetic revision entry'):self.execute()
        self.assertEqual(self.previews(),[]);self.run.review.assert_not_called()
        self.run.phase.assert_called_once()
        self.assertTrue(self.run.phase.call_args.args[0].startswith('live-revision-'))
        self.assertEqual(self.run.phase.call_args.kwargs['thread'],'saved-author-thread')
        self.assertEqual(self.journal.state,self.journal_before)

    def test_deferred_candidates_keep_content_version_and_drop_changed_pages(self):
        def send(*args):
            if 'action=preview' in args[1]:raise RuntimeError('Synthetic temporary upload failure')
            self.sent.append(args)
        self.reporter.send=send
        with self.assertRaisesRegex(TimeoutError,'Synthetic independent review timeout'):self.execute()
        self.run.review.assert_called_once()
        self.assertEqual(sorted(self.reporter.pending),[1,2])
        self.assertEqual(self.reporter.pending_content,{n:page_version(self.reporter.outline,n) for n in (1,2)})
        changed=outline();changed['slides'][1]['summary']='增加未找到时的停止例子。'
        self.reporter.set_outline(changed)
        self.assertEqual(sorted(self.reporter.pending),[1])
        self.reporter.send=lambda *args:self.sent.append(args)
        self.reporter.flush(force=True)
        self.assertEqual(len(self.previews()),1)
        self.assertTrue(self.previews()[0][1].endswith('slide=1'))
        self.assertEqual(self.journal.state,self.journal_before)


if __name__=='__main__':unittest.main()
