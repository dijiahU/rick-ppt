"""One real Codex presentation using a task-scoped attachment; no live website job."""
import hashlib
import io
import uuid
import xml.etree.ElementTree as ET
import zipfile
import runner

data=b'# Fictional internal pilot: Project Juniper\nCompletion rate: 73%\nReview cycles: 21\nThis is synthetic test data, not real research.\n'
attachment={'id':str(uuid.uuid4()),'name':'pilot-reference.md','ext':'md','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
received=[];delivered=[]
def receipt(cfg,path,body=b'{}',lease=None,raw=False):
    if 'action=attachment' in path:
        assert raw and path.endswith('file='+attachment['id']);received.append(path);return data
    if 'action=complete' in path:
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            texts=[]
            for name in z.namelist():
                if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                    texts.extend(e.text or '' for e in ET.fromstring(z.read(name)).iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'))
            text=' '.join(texts)
            assert 'Juniper' in text and '73' in text and '21' in text,text
        target=runner.ROOT/'attachment-result.pptx'
        with target.open('xb') as f:f.write(body)
        delivered.append(str(target));print('Native slide text:',text,flush=True)
    return {'ok':True}
runner.request=receipt
task={'id':str(uuid.uuid4()),'lease':'local-attachment-smoke','title':'Pilot overview','brief':'Create one slide summarizing the uploaded pilot reference. Read the file, use its actual project name and both metrics, and clearly label the data as fictional. Do not search or generate images. Use native editable text and shapes with a calm editorial layout. Cite the reference filename in a small footer.','pages':1,'style':'Restrained editorial','language':'en','attachments':[attachment]}
print(runner.run_job(runner.settings(),task),flush=True)
assert received and delivered
print('PASS: scoped attachment download → content read → editable PPTX → independent render/export',delivered[0])
