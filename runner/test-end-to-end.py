"""One real five-slide Codex run; intercept upload locally, never charge a user."""
import runner
import uuid
from pathlib import Path

completed=[]
def local_receipt(cfg,path,body=b'{}',lease=None):
    if 'action=complete' in path:
        assert body[:2]==b'PK'
        target=Path(__file__).resolve().parent/'smoke-result.pptx'
        if target.exists():raise RuntimeError('Smoke output already exists; preserve it.')
        with target.open('xb') as stream:stream.write(body)
        completed.append(str(target))
    return {'ok':True}

runner.request=local_receipt
runner.run_job(runner.settings(),{'id':str(uuid.uuid4()),'lease':'local-smoke',
 'title':'让演示文稿更容易理解',
 'brief':'制作 5 页简短中文演示文稿：封面、明确听众、每页一个重点、用视觉层级组织内容、交付前检查。每页文字不超过 60 字。用低饱和米白、深绿、陶土色，保持原生可编辑对象。使用 Noto Sans CJK SC 中文字体，无需外部资料或图片。',
 'pages':5,'style':'克制编辑风格'})
assert completed,'No validated result was delivered'
print('PASS: real Codex task → OOXML authoring → container render → independent validation → local delivery',completed[0])
