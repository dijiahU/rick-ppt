"""Start a fresh, memory-disabled Codex CLI task. No parent conversation or prior deck."""
import json
from pathlib import Path
import uuid
import runner

task={
 'id':str(uuid.uuid4()),'lease':'local-fresh-animation-test',
 'title':'心脏充盈与射血过程',
 'brief':'请制作一页简体中文 PPT，用心脏动画演示左右心房、心室的充盈与射血过程，以及相应瓣膜的开闭，帮助汇报者直观讲解心血管系统。画面应具有专业医学教学质量，结构清楚，文字简洁。',
 'pages':1,'style':'Designer choice','language':'zh-CN','attachments':[]
}
cfg=runner.settings()
output=runner.ROOT/('fresh-heart-animation-'+task['id']+'.pptx')
def receipt(cfg,path,body=b'{}',lease=None,raw=False):
    if 'action=complete' in path:
        with output.open('xb') as stream:stream.write(body)
    return {'ok':True}
runner.request=receipt
print('Independent test ID:',task['id'],flush=True)
try:
    result=runner.run_job(cfg,task)
    print(json.dumps({'status':'complete','output':str(output),**result},ensure_ascii=False),flush=True)
except Exception as error:
    print(json.dumps({'status':'not_completed','error':type(error).__name__,'detail':str(error),'task_id':task['id']},ensure_ascii=False),flush=True)
    raise SystemExit(1)
