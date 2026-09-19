"""Real, bounded hosted search/image test under the website worker's permissions."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import runner

parser=argparse.ArgumentParser()
parser.add_argument('--live',action='store_true')
args=parser.parse_args()
cfg=runner.settings();job=runner.prepare(cfg)
shutil.copyfile('/Users/rick/.codex/skills/.system/imagegen/SKILL.md',job/'imagegen-skill.md')
command=runner.codex_command(cfg,job)
if args.live:command=command[:-1]+['-c','web_search="live"','-']
prompt='''This is an authorized capability smoke test for the PPTX website runner, not a full presentation.
Do exactly these bounded checks, then stop:
1. Invoke the built-in web search tool to find the official OpenAI documentation for Codex web search. Open the matching official page, then write a short source URL and one supported sentence into search-proof.txt. Never use shell networking or claim a search you did not run.
2. Read the complete imagegen-skill.md in this task. If a built-in image generation tool is available, call it ONCE to generate a small polished landscape illustration of a friendly digital office assistant at a workstation, midnight navy, cyan and violet, no text or logos. This is a raster asset for a PPTX, not SVG/code artwork. Use built-in generation only, no API key or API fallback. Copy the tool's generated image into this task as capability-image.png if permitted. If copying is denied, preserve the tool's original output and report the exact returned path; do not broaden filesystem permissions or seek another route.
If a tool is absent or fails, report the exact capability limitation without simulating it. Do not inspect credentials, other tasks or private files. Do not modify any plugin or configuration. Return a concise result, distinguishing actual tool success from untested or unavailable capability.'''
print('Capability test task:',job,flush=True)
with (job/'capabilities.jsonl').open('wb') as log:
    result=subprocess.run(command,input=prompt.encode(),stdout=log,stderr=log,env=runner.environment(job),cwd=job,timeout=600)
print('Exit:',result.returncode,'Log:',job/'capabilities.jsonl',flush=True)
for line in (job/'capabilities.jsonl').read_text().splitlines():
    try:event=json.loads(line)
    except ValueError:continue
    item=event.get('item',{})
    if event.get('type')=='item.completed':
        print(json.dumps({'type':item.get('type'),'status':item.get('status'),'text':item.get('text','')[:1800]},ensure_ascii=False))
