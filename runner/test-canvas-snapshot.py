"""Native canvas geometry and revision checks; never contacts queues."""
import io,json,tempfile,unittest,zipfile,hashlib,uuid
from pathlib import Path
from types import SimpleNamespace
from canvas_snapshot import native_pages,scoped_requests
from conversation import Conversation
from durable import Journal
P='http://schemas.openxmlformats.org/presentationml/2006/main';A='http://schemas.openxmlformats.org/drawingml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def deck():
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldSz cx="1000" cy="1000"/><p:sldIdLst><p:sldId id="256" r:id="r1"/></p:sldIdLst></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels','<Relationships><Relationship Id="r1" Target="slides/slide9.xml"/></Relationships>')
        z.writestr('ppt/slides/slide9.xml',f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:grpSp><p:nvGrpSpPr><p:cNvPr id="2" name="Scaled group"/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="100" y="200"/><a:ext cx="400" cy="400"/><a:chOff x="10" y="20"/><a:chExt cx="200" cy="200"/></a:xfrm></p:grpSpPr><p:sp><p:nvSpPr><p:cNvPr id="3" name="Editable title"/></p:nvSpPr><p:spPr><a:xfrm><a:off x="10" y="20"/><a:ext cx="100" cy="50"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>Original</a:t></a:r></a:p></p:txBody></p:sp></p:grpSp><p:sp><p:nvSpPr><p:cNvPr id="4" name="Rotated"/></p:nvSpPr><p:spPr><a:xfrm rot="5400000"><a:off x="600" y="600"/><a:ext cx="200" cy="100"/></a:xfrm></p:spPr></p:sp></p:spTree></p:cSld></p:sld>')
    return b.getvalue()
class CanvasTests(unittest.TestCase):
    def test_group_coordinates_and_native_order(self):
        p=native_pages(deck())[0];self.assertEqual(p['part'],'ppt/slides/slide9.xml');self.assertEqual(len(p['objects']),2)
        o=p['objects'][0];self.assertEqual(o['id'],'3');self.assertTrue(o['textEditable']);self.assertEqual(o['text'],'Original')
        for key,value in {'x':.1,'y':.2,'width':.2,'height':.1}.items():self.assertAlmostEqual(o['bounds'][key],value)
        o=p['objects'][1];self.assertAlmostEqual(o['bounds']['width'],.1);self.assertAlmostEqual(o['bounds']['height'],.2);self.assertFalse(o['textEditable'])
    def test_baseline_transport_is_verified_and_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);job=root/'job';job.mkdir();task={'id':str(uuid.uuid4()),'lease':str(uuid.uuid4())};mid=str(uuid.uuid4());source=deck();sha=hashlib.sha256(source).hexdigest();calls=[]
            body='[RICKPPT_VISUAL_EDITS_V1]\n'+json.dumps({'schema':'rickppt-visual-edits/v1','baseSha256':sha,'scope':'selected_objects_and_pages','changes':[{'page':1,'objectId':'3'}]})+'\nUser instruction'
            row={'id':mid,'seq':1,'kind':'revision','body':body,'attachments':[]}
            def send(cfg,path,payload,lease,raw=False):calls.append((path,lease,raw));return source
            with Journal(root/'state',task['id'],plugin_version='native') as journal:
                c=Conversation({},task,job,journal,send);c.accept(row);c.accept(row);self.assertEqual(len(calls),1);self.assertTrue(calls[0][2]);self.assertEqual(calls[0][1],task['lease']);self.assertEqual(scoped_requests(journal,job)[0]['baseSha256'],sha)
                (job/f'visual-inputs/{mid}/baseline.pptx').write_bytes(b'changed');self.assertIsNone(scoped_requests(journal,job))
    def test_nonvisual_request_does_not_skip_planning(self):
        self.assertIsNone(scoped_requests(SimpleNamespace(state={'inbox':{'x':{'changes_input':True,'state':'accepted','text':'New topic'}}}),Path('/unused')))
    def test_wrong_digest_fails_before_journal_acceptance(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);job=root/'job';job.mkdir();task={'id':str(uuid.uuid4()),'lease':str(uuid.uuid4())};body='[RICKPPT_VISUAL_EDITS_V1]\n'+json.dumps({'schema':'rickppt-visual-edits/v1','baseSha256':'0'*64})
            with Journal(root/'state',task['id'],plugin_version='native') as journal:
                c=Conversation({},task,job,journal,lambda *a,**k:deck())
                with self.assertRaisesRegex(ValueError,'checksum'):c.accept({'id':str(uuid.uuid4()),'seq':1,'kind':'revision','body':body,'attachments':[]})
                self.assertEqual(journal.state['inbox'],{})
if __name__=='__main__':unittest.main()
