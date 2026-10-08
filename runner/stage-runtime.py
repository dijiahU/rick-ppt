"""Stage an immutable plugin runtime; validate before changing worker settings.

Does not restart the worker or claim queued jobs. Never prints credentials.
"""
import json
import argparse
import os
from pathlib import Path
import shutil
import tempfile
import runner

parser=argparse.ArgumentParser();parser.add_argument('--runner-root',type=Path,default=Path(__file__).resolve().parent)
parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1]/'pptx-agent')
parser.add_argument('--python',type=Path)
args=parser.parse_args();root=args.runner_root.resolve();source=args.source.resolve(strict=True)
version=json.loads((source/'.codex-plugin/plugin.json').read_text())['version']
if not version or Path(version).name!=version:raise ValueError('Invalid version')
target=root/'runtime'/version/'pptx-agent'
cfg=json.loads((root/'settings.local.json').read_text())
if not target.exists():
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('.venv','node_modules','__pycache__','.pytest_cache','test-results'))
required=('skills/pptx/SKILL.md','skills/pptx/references/content.md','skills/pptx/references/research-and-assets.md','skills/pptx/references/content-review.md','skills/pptx/references/visual-review.md','skills/pptx/scripts/native_builds.py','skills/pptx/scripts/review_packet.py','skills/pptx/assets/blank.pptx')
if (source/'skills/pptx/assets/workflow-choices.json').is_file():
    required+=('skills/pptx/assets/workflow-choices.json','skills/pptx/references/workflow-branches.md','skills/pptx/scripts/workflow_decisions.py')
    if json.loads((source/'skills/pptx/assets/workflow-choices.json').read_text())['version']>=3:
        required+=('skills/pptx/references/native-canvas.md','skills/pptx/references/animations.md','skills/pptx/scripts/native_canvas.py','skills/pptx/scripts/design_references.py')
if not (source/'skills/pptx/assets/single-file-policy.json').is_file():
    required+=('skills/pptx/references/interactive-authoring.md','runtime/dist/preview.html','runtime/dist/content.html','runtime/config.json','runtime/manifests/manifest.addin.xml')
for relative in required:
    if (source/relative).read_bytes()!=(target/relative).read_bytes():raise RuntimeError('Runtime mismatch: '+relative)
cfg['plugin']=str(target)
cfg['blank']=str(target/'skills/pptx/assets/blank.pptx')
if args.python:cfg['python']=str(args.python.absolute())
cfg.setdefault('job_timeout_seconds',5400)
runner.self_test(cfg)
settings=root/'settings.local.json'
backup=root/('settings-before-'+version+'.local.json')
if not backup.exists():
    with os.fdopen(os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as out:out.write(settings.read_bytes())
fd,tmp=tempfile.mkstemp(prefix='.settings-',dir=root)
with os.fdopen(fd,'w') as out:
    json.dump(cfg,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
os.replace(tmp,settings)
print('Staged and validated runtime:',target)
print('Settings switched; running workers keep their current configuration until restarted.')
