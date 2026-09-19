"""Real search + built-in image + scoped import + PPTX render/export smoke."""
import json
from pathlib import Path
import uuid
import zipfile
import io
import runner

cfg=runner.settings()
cfg['plugin']=str(runner.ROOT/'runtime/0.1.0+codex.20260909072555/pptx-agent')
completed=[]
def receipt(cfg,path,body=b'{}',lease=None):
    if 'action=complete' in path:
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            assert any(n.startswith('ppt/media/') and n.endswith('.png') for n in z.namelist()),'No raster embedded'
            assert b'<a:t>' in z.read('ppt/slides/slide1.xml'),'Missing native editable text'
        target=runner.ROOT/'capabilities-result.pptx'
        with target.open('xb') as stream:stream.write(body)
        completed.append(str(target))
    return {'ok':True}
runner.request=receipt
task={'id':str(uuid.uuid4()),'lease':'local-capability-smoke','title':'从对话到行动','pages':2,'style':'科技编辑风格',
 'brief':'制作 2 页简短中文技术演示。第 1 页标题“从对话到行动”，必须调用一次内置图片生成，生成横向数字办公场景插画，深蓝、青色、紫色；画面内不含文字，标题由原生可编辑文字叠加。必须使用本会话新生成、由 assets/index.json 转交的图片，不用几何机器人代替。第 2 页标题“搜索与执行，各有边界”，实际调用一次网页搜索，打开 OpenAI 官方页面核实 Codex 的 hosted web search 与 shell 网络隔离分开控制；用不超过 50 个中文字解释并给出来源 URL。两页原生文字，图片嵌入，渲染复核后导出。只生成一张图，不进行额外变化。'}
print('Test task ID:',task['id'],flush=True)
runner.run_job(cfg,task)
assert completed
print('PASS: live search + new built-in image + scoped import + editable PPTX + independent render',completed[0])
