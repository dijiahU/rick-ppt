"""Small live two-page production-workflow check; delivery stays local."""
import json,sys,uuid,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runner'))
import runner
output=ROOT/'deploy/private/smoke-result.pptx'
if output.exists():raise SystemExit('Preserving previous smoke result; use a new output file.')
delivered=[]
def local_request(cfg,path,body=b'{}',lease=None,**kwargs):
    if 'action=complete' in path:
        assert body[:2]==b'PK'
        output.write_bytes(body)
        delivered.append(str(output))
    if 'action=poll' in path:return {'ok':True,'messages':[],'revision':0}
    return {'ok':True,'revision':0}
runner.request=local_request
cfg=runner.settings()
prior=ROOT/'deploy/private/smoke-receipt.local.json'
identifier=json.loads(prior.read_text())['task_id'] if '--resume' in sys.argv and prior.exists() else str(uuid.uuid4())
task={'id':identifier,'lease':'local-deployment-smoke-'+uuid.uuid4().hex,'mode':'create','language':'zh-CN','execution_backend':'codex',
      'title':'服务器自动接单部署验证','brief':'制作 2 页中文 PPT，用于部署测试。第一张是标题“服务器自动接单部署验证”，副标题“网站提交 → 服务器制作 → 下载文件”；第二张标题“本次验证范围”，列出“独立工作目录、生成可编辑PPT、渲染预览、保存文件”。这只是功能测试，不要声称尚未验证的公网提交或回传已经完成。只使用上述给定文字，无需搜索、引用或生图；不需要额外设计素材，使用 Noto Sans CJK SC。采用干净的白底、深蓝标题和青绿强调色，所有文字保持原生可编辑；第二张的四项检查依次点击揭示。严格只做两张，完成现有必要检查后交付。',
      'pages':2,'style':'简洁、清楚、原生可编辑'}
receipt=ROOT/'deploy/private/smoke-receipt.local.json'
receipt.write_text(json.dumps({'task_id':task['id'],'state':'running'},indent=2))
print('Live smoke task:',task['id'],flush=True)
runner.run_job(cfg,task)
if not delivered:raise RuntimeError('Production workflow did not deliver a PPTX')
receipt.write_text(json.dumps({'task_id':task['id'],'state':'complete','file':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()},indent=2))
print('PASS: real Codex → native PPTX → Linux render → independent reviews → validated local delivery:',output,flush=True)
