"""Copy each delivered presentation into a local folder for the operator (2026-11-21, Rick).

Enabled only by the worker setting `local_output_dir` (local Mac profile); servers leave it unset.
Never affects delivery: any error is reported and ignored.
  1121-1519_<title>_<task8>.pptx  plus one row in manifest.json (file, task, sha256)
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path


def name_for(task, now=None):
    stamp = time.strftime('%m%d-%H%M', time.localtime(now))
    title = re.sub(r'[\\/:*?"<>|\s]+', '', str(task.get('title') or 'presentation'))[:40] or 'presentation'
    return f"{stamp}_{title}_{str(task.get('id', ''))[:8]}.pptx"


def copy(cfg, task, artifact, now=None):
    folder = cfg.get('local_output_dir')
    if not folder:
        return None
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(artifact).hexdigest()
    manifest = folder / 'manifest.json'
    try:
        rows = json.loads(manifest.read_text())
    except (OSError, ValueError):
        rows = []
    if any(r.get('task') == task.get('id') and r.get('sha256') == digest for r in rows):
        return None  # same delivery already copied (a retried upload)
    target = folder / name_for(task, now)
    temporary = target.with_suffix('.pptx.part')
    temporary.write_bytes(artifact); os.replace(temporary, target)
    rows.append({'file': target.name, 'task': task.get('id'), 'sha256': digest})
    temporary = manifest.with_suffix('.json.part')
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=1)); os.replace(temporary, manifest)
    return target
