"""Task-pinned author continuity; reviewers and recovery remain independent."""
import json
import os
from pathlib import Path

MODES = ('continuous', 'split')


def supported(cfg):
    # Retained API/DSH tools use model-backed helpers. Keep their verified route.
    return not cfg.get('_model_profile') and cfg.get('_harness_transport', 'app-server') == 'app-server'


def new_task_mode(cfg):
    """New admissions always use one continuous author; split is resume-only."""
    mode = cfg.get('author_context_mode', 'continuous')
    if mode == 'split':
        raise ValueError('author_context_mode=split is retired for new tasks; it remains only for resuming tasks already pinned to it')
    if mode not in MODES:
        raise ValueError('author_context_mode must be continuous')
    return mode


def pin_mode(cfg, state_root, task_id, existing):
    path = Path(state_root)/task_id/'author-context.json'
    if path.is_file():
        value = json.loads(path.read_text())
        if value.get('version') != 1 or value.get('mode') not in MODES:
            raise ValueError('Invalid pinned author context')
        mode = value['mode']
    elif existing:
        return 'split'  # Do not change an older task's admitted execution path.
    else:
        mode = new_task_mode(cfg)
        if not supported(cfg):
            # Checked before pinning so a rejected admission leaves no record.
            raise ValueError('New tasks require the local Codex continuous author; the split API/DSH route '
                             'is retired for new tasks (existing tasks still resume)')
        path.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump({'version': 1, 'mode': mode}, stream)
    if mode == 'continuous' and not supported(cfg):
        raise ValueError('Pinned continuous author cannot switch to a helper-backed runtime')
    return mode


def enabled(cfg):
    # Only host admission activates this. Standalone/legacy callers retain behavior.
    return cfg.get('_author_context_mode') == 'continuous'


def author_phase(name):
    return name in ('research', 'author') or name.startswith(('repair-', 'live-revision-'))


def saved_thread(journal):
    if not journal:
        return None
    stages = journal.state.get('completed_stages', {})
    candidates = [receipt for name, receipt in stages.items()
                  if author_phase(name) and receipt.get('thread_id')]
    return max(candidates, key=lambda r: r.get('completed_at', 0))['thread_id'] if candidates else None


def instruction():
    return ('CONTINUOUS AUTHOR: one conversation owns research, design, native pages and repairs; phase boundaries are host '
            'checkpoints. Run independent searches, downloads (web-media-proxy.py --submit-only) and tool calls concurrently; '
            'keep page authoring in order. Use the tools actually exposed to you. The host runs the independent reviews; '
            'do not impersonate reviewers. ')
