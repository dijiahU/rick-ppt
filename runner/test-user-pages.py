import copy,hashlib,importlib.util,io,json,tempfile,unittest,zipfile,sys,uuid
from pathlib import Path
from lxml import etree as E
from user_pages import graft,fingerprint
from canvas_snapshot import native_pages
from draft_progress import validate_native
from native_editor import apply,NS,xml
from progressive_canvas import ProgressiveCanvas

spec=importlib.util.spec_from_file_location('native_fixture',Path(__file__).with_name('test-native-editor.py'));fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
P=NS['p'];R=NS['r'];CT='http://schemas.openxmlformats.org/package/2006/content-types';REL='http://schemas.openxmlformats.org/package/2006/relationships'
def second_page(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:parts={n:z.read(n) for n in z.namelist()}
    number=len(native_pages(data))+1;name='slide'+str(number)+'.xml';rid='rIdAdded'+str(number)
    tree=xml(parts['ppt/presentation.xml']);E.SubElement(tree.find('p:sldIdLst',NS),'{'+P+'}sldId',id=str(255+number),attrib={'{'+R+'}id':rid})
    parts['ppt/presentation.xml']=E.tostring(tree);rels=xml(parts['ppt/_rels/presentation.xml.rels']);E.SubElement(rels,'{'+REL+'}Relationship',Id=rid,Type=R+'/slide',Target='slides/'+name);parts['ppt/_rels/presentation.xml.rels']=E.tostring(rels)
    parts['ppt/slides/'+name]=parts['ppt/slides/slide1.xml'].replace(b'Original title',b'Later page by Agent');parts['ppt/slides/_rels/'+name+'.rels']=parts['ppt/slides/_rels/slide1.xml.rels']
    types=xml(parts['[Content_Types].xml']);E.SubElement(types,'{'+CT+'}Override',PartName='/ppt/slides/'+name,ContentType='application/vnd.openxmlformats-officedocument.presentationml.slide+xml');parts['[Content_Types].xml']=E.tostring(types);out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
    return out.getvalue()
class UserPageTests(unittest.TestCase):
    def test_user_page_and_new_agent_page_both_survive(self):
        old=fixture.fixture();user,_=apply(old,fixture.PATCHES,{'testpic':fixture.picture('#ca815e')});agent=second_page(old);merged=graft(agent,[{'artifact':user,'pages':[1]}]);self.assertEqual(validate_native(merged),2)
        pages=native_pages(merged);self.assertEqual(next(o for o in pages[0]['objects'] if o['id']=='2')['text'],'Edited native title');self.assertEqual(next(o for o in pages[1]['objects'] if o['id']=='2')['text'],'Later page by Agent')
        with zipfile.ZipFile(io.BytesIO(agent)) as a,zipfile.ZipFile(io.BytesIO(user)) as u,zipfile.ZipFile(io.BytesIO(merged)) as m:
            self.assertEqual(a.read('ppt/slides/slide2.xml'),m.read('ppt/slides/slide2.xml'));self.assertEqual(u.read('ppt/slides/slide1.xml'),m.read('ppt/slides/slide1.xml'))
        self.assertEqual(merged,graft(merged,[{'artifact':user,'pages':[1]}]));self.assertEqual(fingerprint(user,1),fingerprint(merged,1))
    def test_later_page_does_not_change_first_page_identity(self):
        one=fixture.fixture();two=second_page(one);self.assertEqual(fingerprint(one,1),fingerprint(two,1));updated,_=apply(two,[{'page':2,'objectId':'2','text':'New later content'}]);self.assertEqual(fingerprint(two,1),fingerprint(updated,1));self.assertNotEqual(fingerprint(two,2),fingerprint(updated,2))
    def test_missing_page_is_not_silently_substituted(self):
        with self.assertRaisesRegex(ValueError,'presentation identity'):graft(fixture.fixture(),[{'artifact':second_page(fixture.fixture()),'pages':[2]}])
    def test_progressive_preview_only_unlocks_actual_rendered_pages(self):
        artifact=second_page(fixture.fixture());sha=hashlib.sha256(artifact).hexdigest();calls=[];snapshots=[]
        def send(cfg,path,body=b'{}',lease=None,raw=False):
            from urllib.parse import parse_qs,urlsplit
            action=parse_qs(urlsplit(path).query)['action'][0];calls.append(action)
            if action=='locks':return {'locks':[],'head':{'sha256':sha} if snapshots else None}
            if action=='manifest':snapshots.append(json.loads(body))
            return {'ok':True}
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'raw-blobs').mkdir();(root/'raw-blobs'/sha).write_bytes(artifact);publisher=ProgressiveCanvas({}, {'id':'task','lease':'private-test-lease'},root,send)
            publisher.pending[1]=(sha,b'\x89PNG\r\n\x1a\nfirst');publisher.synchronize();self.assertIsNone(publisher.last_error);self.assertEqual(snapshots[-1]['readyPages'],[1]);self.assertEqual(len(snapshots[-1]['pages']),2)
            publisher.pending[2]=(sha,b'\x89PNG\r\n\x1a\nsecond');publisher.synchronize();self.assertEqual(snapshots[-1]['readyPages'],[1,2]);self.assertEqual(calls.count('manifest'),2);self.assertNotIn('render',calls)
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--fixtures':
        root=Path(sys.argv[2]);root.mkdir(parents=True,exist_ok=True);base=fixture.fixture();source=second_page(base);growing=second_page(source);user,_=apply(base,fixture.PATCHES,{'testpic':fixture.picture('#ca815e')});merged=graft(growing,[{'artifact':user,'pages':[1]}])
        for name,data in [('source',source),('growing',growing),('merged',merged)]:
            (root/(name+'.pptx')).write_bytes(data);pages=native_pages(data)
            for page in pages:page['contentSha256']=fingerprint(data,page['number']);page['imageSha256']='0'*64
            snapshot={'schema':'rickppt-canvas/v1','sha256':hashlib.sha256(data).hexdigest(),'versionId':str(uuid.uuid4()),'createdAt':100 if name=='source' else 200 if name=='growing' else 300,'pages':pages,'readyPages':[1] if name=='source' else [1,2]}
            (root/(name+'.json')).write_text(json.dumps(snapshot))
        print('Progressive fixtures written')
    else:unittest.main()
