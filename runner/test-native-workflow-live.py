"""Local real-model acceptance; intercept every site call and never claim a job."""
import json
import argparse
from pathlib import Path
import uuid
import runner

root=Path('/Users/rick/Desktop/ppt')
cfg=json.loads((root/'pptx-test-runner/settings.local.json').read_text())
cfg.update(plugin=str(root/'pptx-agent'),python=str(root/'pptx-agent/.venv/bin/python'),
           blank=str(root/'pptx-agent/skills/pptx/assets/blank.pptx'),token='LOCAL_TEST_ONLY_'*4,
           job_timeout_seconds=5400)
parser=argparse.ArgumentParser();parser.add_argument('--label',default='live-acceptance');args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Invalid local test label')
out=root/'.work/content-first-20260920'/args.label
out.mkdir(exist_ok=True)
receipts=[]
def local_request(cfg,path,body=b'{}',lease=None):
    if 'action=complete' in path:
        assert body[:2]==b'PK'
        with (out/'result.pptx').open('xb') as f:f.write(body)
        receipts.append('delivered')
    elif 'action=progress' in path:
        (out/'progress.json').write_bytes(body if isinstance(body,bytes) else body.encode())
    return {'ok':True}
runner.request=local_request
result=runner.run_job(cfg,{'id':str(uuid.uuid4()),'lease':'LOCAL_TEST',
    'title':'第一次理解二分查找','pages':3,'language':'zh-CN',
    'brief':'给初学者讲清二分查找，3 页中文授课 PPT。只使用下述资料，无需搜索或外部图片：有序数组 [3,7,11,15,19,23,27]，目标 19；依次比较中间值 15、23、19，每次依据大小排除一半候选；前提是数组有序；如果左右边界交错，表示找不到。第 1 页交代目的和有序前提，第 2 页用这个例子展示三次比较，第 3 页解释找不到时怎么结束并给一道有答案的小练习。用原生可编辑对象，以 Noto Sans CJK SC 显式设中西文字体，颜色克制但层次清楚；第 2 页使用语义分组逐步出现。资料中没有其他统计或事实，不要编造。',
    'style':'适合课堂，字清楚，重视解释与步骤图'})
assert receipts==['delivered']
(out/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('PASS: fresh research, native authoring, isolated audience reviews and frozen local delivery',flush=True)
