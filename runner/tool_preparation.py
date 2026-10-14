"""Host entry to current-plugin task tool preparation; old plugins remain usable."""
import json
import os
from pathlib import Path
import subprocess


def prepare_tool_manifest(cfg, task_root, *, workspace=None):
    script = (Path(cfg['plugin']) / 'skills/pptx/scripts/tool_prepare.py').absolute()
    if not script.is_file():
        return None
    root = Path(task_root).absolute()
    interpreter = os.path.abspath(cfg['python'])
    command = [interpreter, str(script), '--task-root', str(root), '--python', interpreter]
    if workspace is not None:
        command += ['--workspace', str(workspace)]
    # A fresh interpreter avoids already-imported host modules from older plugins.
    # Do not forward provider credentials or an inherited PYTHONPATH.
    environment = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR')
                   if key in os.environ}
    environment['PYTHONPATH'] = str(script.parent)
    completed = subprocess.run(command, cwd=root, env=environment, timeout=30,
                               check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)
