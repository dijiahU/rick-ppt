"""Real native-build regression; local receipts only, no website admissions."""
import argparse
import json
from pathlib import Path
import time
import uuid
import zipfile
from lxml import etree
import runner
from progress import Reporter

NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main'}

def verify(directory):
    receipts=json.loads((directory/'receipts.json').read_text())
    completed=next(i for i,r in enumerate(receipts) if r['kind']=='complete')
    pages=[]
    with zipfile.ZipFile(directory/'result.pptx') as archive:
        assert archive.testzip() is None
        files=[n for n in archive.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
        assert len(files)==2
        for name in sorted(files):
            root=etree.fromstring(archive.read(name))
            timing=root.find('p:timing',NS)
            assert timing is not None,f'{name}: missing native timing'
            shape_ids=set(root.xpath('.//p:spTree//p:cNvPr/@id',namespaces=NS))
            targets=set(timing.xpath('.//p:spTgt/@spid',namespaces=NS))
            assert targets and targets<=shape_ids,f'{name}: invalid animation targets'
            times=timing.xpath('.//p:cTn/@id',namespaces=NS)
            assert len(times)==len(set(times)),f'{name}: duplicate timing IDs'
            clicks=timing.xpath('.//p:cTn[@nodeType="clickEffect"]',namespaces=NS)
            assert len(clicks)>=2,f'{name}: missing separate click-controlled beats'
            beat_targets=[set(c.xpath('.//p:spTgt/@spid',namespaces=NS)) for c in clicks]
            assert len(set().union(*beat_targets))>=2,f'{name}: entire page is one reveal'
            assert timing.xpath('.//p:cTn[@presetClass="entr"]',namespaces=NS),f'{name}: no entrance builds'
            assert timing.xpath('.//p:cond[@evt="onNext"]',namespaces=NS),f'{name}: no presenter-next trigger'
            transition=root.find('p:transition',NS)
            assert transition is None or 'advTm' not in transition.attrib,f'{name}: automatic page advance'
            pages.append({'part':name,'clickBeats':len(clicks),'targets':len(targets)})
    for slide in (1,2):
        assert any(i<completed and r['kind']=='preview' and r['slide']==slide for i,r in enumerate(receipts))
    first_preview=next(i for i,r in enumerate(receipts) if r['kind']=='preview' and r['slide']==1)
    second_start=next(i for i,r in enumerate(receipts) if r['kind']=='progress' and any(n.get('slide')==2 and n.get('phase')=='building' for n in r['progress'].get('notes',[])))
    assert first_preview<second_start,'Page 1 was not previewed before page 2 authoring'
    # Replay the real run through the current publisher. Animation-state copies
    # must never create phantom slide 3 or replace a real page with a hidden state.
    saved=json.loads((directory/'run.json').read_text())
    calls=[]
    reporter=Reporter({}, {'id':'local-replay','lease':'local'},Path(saved['job']),lambda *a:calls.append(a),explicit_previews=True)
    for line in Path(saved['log']).read_text().splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        reporter.consume(event)
    assert not reporter.pending,'Private render outputs became public previews'
    reporter.poll_public_journal();reporter.flush(force=True)
    public=json.loads(calls[-1][2])['previews']
    assert public==[1,2],f'Incorrect logical page previews: {public}'
    return {'ok':True,'pages':pages,'publicPreviewsAfterReplay':public,'playback':'not tested; native XML and static rendering only'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',type=Path)
    args=parser.parse_args()
    if args.verify:
        print(json.dumps(verify(args.verify),ensure_ascii=False));return
    cfg=runner.settings()
    identifier=str(uuid.uuid4())
    directory=runner.ROOT.parent/'works'/('presentation-builds-'+identifier)
    directory.mkdir()
    receipts=[];start=time.monotonic();last_note=0
    def receive(_cfg,path,body=b'{}',lease=None,raw=False):
        nonlocal last_note
        kind=path.split('action=',1)[-1].split('&',1)[0]
        record={'kind':kind,'seconds':round(time.monotonic()-start,2)}
        if kind=='progress':
            record['progress']=json.loads(body)
            for note in record['progress'].get('notes',[]):
                if note['seq']>last_note:
                    print('NOTE',note.get('phase'),note.get('slide'),note['detail'],flush=True)
                    last_note=note['seq']
        elif kind=='preview':
            record['slide']=int(path.split('slide=')[1])
            (directory/f"preview-{len(receipts)}-slide-{record['slide']}.png").write_bytes(body)
            print('PREVIEW',record['slide'],record['seconds'],flush=True)
        elif kind=='complete':(directory/'result.pptx').write_bytes(body)
        receipts.append(record)
        return {'ok':True}
    runner.request=receive
    # An ordinary brief deliberately does not request animation: exercise the default.
    task={'id':identifier,'lease':'local-build-test','title':'高效团队会议','language':'zh-CN','pages':2,'style':'清晰简洁',
          'brief':'制作两页中文 PPT。第 1 页说明会前准备的三个步骤：明确目标、准备资料、发出议程；第 2 页说明会中的三个步骤：对齐目标、讨论选择、确定行动。每页用简洁可编辑图示和短句解释步骤。只使用这里的信息，不查资料、不用图片、视频或外部素材。采用直接 OOXML 制作。'}
    print('LOCAL TEST',directory,flush=True)
    try:
        result=runner.run_job(cfg,task)
        (directory/'run.json').write_text(json.dumps(result,ensure_ascii=False))
    finally:(directory/'receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
    report=verify(directory)
    (directory/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
