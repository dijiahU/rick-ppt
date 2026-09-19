import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from outline import validate_outline,page_version
from progress import Reporter
from workflow import Execution,validate_report,budget_summary,usage_summary
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


if __name__=='__main__':unittest.main()
