"""Select the staged runtime without exposing bridge credentials to tasks."""
import json
import os
from pathlib import Path
import sys


def launch_environment(worker,credentials,environ=None):
    worker=Path(worker).resolve();credentials=Path(credentials).resolve(strict=True)
    cfg=json.loads((worker/'settings.local.json').read_text())
    plugin=Path(cfg['plugin']).resolve(strict=True)
    manifest=json.loads((plugin/'.codex-plugin/plugin.json').read_text())
    if not manifest.get('version'):raise ValueError('Staged plugin has no version')
    if (plugin/'skills/pptx/assets/workflow-choices.json').is_file():
        required=['skills/pptx/references/workflow-branches.md','skills/pptx/scripts/workflow_decisions.py']
        if json.loads((plugin/'skills/pptx/assets/workflow-choices.json').read_text()).get('version',0)>=3:
            required+=['skills/pptx/references/native-canvas.md','skills/pptx/scripts/native_canvas.py','skills/pptx/scripts/design_references.py']
        for relative in required:
            if not (plugin/relative).is_file():raise ValueError('Incomplete staged workflow: '+relative)
    blank=Path(cfg['blank']).resolve(strict=True)
    env=dict(os.environ if environ is None else environ)
    env.update(PPTX_RUNNER_SETTINGS=str(credentials),PPTX_RUNNER_PLUGIN=str(plugin),
               PPTX_RUNNER_BLANK=str(blank),
               PPTX_RUNNER_STATE_DIRECTORY=str(Path(cfg.get('state_directory',worker/'state')).resolve()))
    return env


def launch_interpreter(worker):
    cfg=json.loads((Path(worker)/'settings.local.json').read_text())
    # Keep the venv executable path: resolving its symlink loses venv identity.
    python=str(Path(cfg['python']).absolute())
    if not Path(python).is_file():raise ValueError('Configured worker interpreter is missing')
    return python


def run(worker,credentials,argv=None):
    worker=Path(worker).resolve()
    env=launch_environment(worker,credentials)
    python=launch_interpreter(worker)
    os.execve(python,[python,str(worker/'runner.py'),*(sys.argv[1:] if argv is None else argv)],env)


def write_runtime_receipt(root,cfg,status):
    """Proof of the configuration loaded by this process, rather than the file."""
    from model_backend import DEFAULT_TASK_MODEL,DEFAULT_TASK_REASONING_EFFORT
    plugin=Path(cfg['plugin']).resolve()
    body={'pid':os.getpid(),'status':status,'plugin':str(plugin),
          'version':json.loads((plugin/'.codex-plugin/plugin.json').read_text())['version'],
          'workflow_choices':(plugin/'skills/pptx/assets/workflow-choices.json').is_file(),
          'default_model':cfg.get('default_model',DEFAULT_TASK_MODEL),
          'default_reasoning_effort':cfg.get('default_reasoning_effort',DEFAULT_TASK_REASONING_EFFORT)}
    catalog=plugin/'skills/pptx/assets/workflow-choices.json'
    body['decision_contract_version']=json.loads(catalog.read_text()).get('version') if catalog.is_file() else None
    body['new_deck_click_reveal_required']=bool(catalog.is_file() and json.loads(catalog.read_text()).get('requirements',{}).get('new_deck_click_reveal'))
    body['native_canvas_available']=(plugin/'skills/pptx/scripts/native_canvas.py').is_file()
    body['reference_notes_available']=(plugin/'skills/pptx/scripts/design_references.py').is_file()
    target=Path(root)/('runtime-'+str(os.getpid())+'.local.json')
    pending=target.with_suffix('.pending')
    with os.fdopen(os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as stream:
        json.dump(body,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(pending,target)
    return target
