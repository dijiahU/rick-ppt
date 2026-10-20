"""Exercise real native save + rendering, with fake transport and no model calls."""
import hashlib,importlib.util,json,sys,uuid
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from native_edit_worker import execute
from canvas_snapshot import native_pages

spec=importlib.util.spec_from_file_location('editor_fixture',Path(__file__).with_name('test-native-editor.py'));fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True);source=fixture.fixture();(root/'baseline.pptx').write_bytes(source)
pages=native_pages(source)
for page in pages:page['imageSha256']='0'*64
base={'schema':'rickppt-canvas/v1','sha256':hashlib.sha256(source).hexdigest(),'versionId':str(uuid.uuid4()),'createdAt':100,'pages':pages}
(root/'baseline-snapshot.json').write_text(json.dumps(base));actions=[]
def send(cfg,path,body=b'{}',lease=None,raw=False):
    q=parse_qs(urlsplit(path).query);action=q['action'][0];actions.append(action)
    if action=='source':return source
    if action=='picture':return fixture.picture('#ca815e')
    if action=='base-manifest':return {'snapshot':base}
    if action=='artifact':(root/'edited.pptx').write_bytes(body);return {'sha256':hashlib.sha256(body).hexdigest()}
    if action=='page':(root/('page-'+q['page'][0]+'.png')).write_bytes(body);return {'sha256':hashlib.sha256(body).hexdigest()}
    if action=='finish':(root/'edited-snapshot.json').write_bytes(body);return {'ok':True,'sha256':json.loads(body)['sha256']}
    raise AssertionError('Unexpected action '+action)
cfg={'plugin':str(Path(__file__).resolve().parents[1]/'pptx-agent')}
edit={'id':str(uuid.uuid4()),'lease':'synthetic-test-lease','baseSha256':base['sha256'],'patches':fixture.PATCHES}
result=execute(cfg,edit,send);assert result['ok'];assert hashlib.sha256((root/'edited.pptx').read_bytes()).hexdigest()==result['sha256'];assert (root/'page-1.png').stat().st_size>1000
(root/'render-receipt.json').write_text(json.dumps({'ok':True,'actions':actions,'modelCalls':0,'artifactSha256':result['sha256'],'powerpointOrWpsPlaybackVerified':False},indent=2))
print('PASS: real OOXML edits, image replacement, table text, native render, hashed upload and finish; zero model calls.')
