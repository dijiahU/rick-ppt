"""Fresh isolated generation with local receipts; no website admissions or uploads."""
import argparse
import io
import json
from pathlib import Path
import time
import sys
import uuid
import zipfile
from lxml import etree
import runner

def verify(receipts,directory):
    previews=[(i,r) for i,r in enumerate(receipts) if r['kind']=='preview']
    completion=next(i for i,r in enumerate(receipts) if r['kind']=='complete')
    notes={n['seq']:n for r in receipts if r['kind']=='progress' for n in r['progress'].get('notes',[])}
    assert any(n.get('phase') in ('design','planning') and not n.get('slide') for n in notes.values()),'Missing public design or content direction'
    assert any(n.get('next') for n in notes.values()),'Missing next-action update'
    for slide in (1,2,3):
        assert any(n.get('slide')==slide and n.get('phase')=='building' for n in notes.values()),f'Missing page {slide} note'
        assert any(r['slide']==slide and i<completion for i,r in previews),f'Missing early page {slide} preview'
    first_preview=previews[0][0]
    second_start=next(i for i,r in enumerate(receipts) if r['kind']=='progress' and any(n.get('slide')==2 and n.get('phase')=='building' for n in r['progress'].get('notes',[])))
    assert first_preview<second_start,'First preview was delayed until page 2 started'
    with zipfile.ZipFile(directory/'result.pptx') as archive:
        assert archive.testzip() is None
        root=etree.fromstring(archive.read('ppt/presentation.xml'))
        assert len(root.findall('{*}sldIdLst/{*}sldId'))==3
    return {'ok':True,'directory':str(directory),'firstPreviewSeconds':previews[0][1]['seconds'],'notes':len(notes),'previewUploads':len(previews)}

parser=argparse.ArgumentParser()
parser.add_argument('--verify',type=Path,help='Verify a saved local receipt run without generating again')
args=parser.parse_args()
if args.verify:
    print(json.dumps(verify(json.loads((args.verify/'receipts.json').read_text()),args.verify),ensure_ascii=False))
    raise SystemExit
cfg=runner.settings()
identifier=str(uuid.uuid4())
directory=runner.ROOT.parent/'works'/('progressive-smoke-'+identifier)
directory.mkdir()
receipts=[];started=time.monotonic();last_note=0

def receive(_cfg,path,body=b'{}',lease=None,raw=False):
    global last_note
    kind=path.split('action=',1)[-1].split('&',1)[0]
    record={'kind':kind,'seconds':round(time.monotonic()-started,2)}
    if kind=='progress':
        record['progress']=json.loads(body)
        for note in record['progress'].get('notes',[]):
            if note['seq']>last_note:
                print('NOTE',note.get('phase'),note.get('slide'),note['detail'],flush=True)
                last_note=note['seq']
    elif kind=='preview':
        record['slide']=int(path.split('slide=')[1])
        target=directory/f"preview-{len(receipts)}-slide-{record['slide']}.png"
        target.write_bytes(body);record['file']=str(target)
        print('PREVIEW',record['slide'],record['seconds'],flush=True)
    elif kind=='complete':
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            assert archive.testzip() is None
            root=etree.fromstring(archive.read('ppt/presentation.xml'))
            assert len(root.findall('{*}sldIdLst/{*}sldId'))==3
        (directory/'result.pptx').write_bytes(body)
    receipts.append(record)
    return {'ok':True}

runner.request=receive
task={'id':identifier,'lease':'local-test','title':'逐页进度验证','language':'zh-CN','pages':3,'style':'清晰简洁',
 'brief':'制作三页中文演示，解释一个日常项目的三步：1 定义目标，2 执行并检查，3 根据结果调整。每页一个短句和一个简单可编辑图示；不要查资料，不要外部素材，不要生成图片，不要动画。按网站逐页流程发布设计说明、每页制作说明、实际渲染和简短检查结果。'}
try:
    result=runner.run_job(cfg,task)
    print(json.dumps(verify(receipts,directory),ensure_ascii=False),flush=True)
finally:
    (directory/'receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
