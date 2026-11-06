"""Task-pinned author continuity; reviewers and recovery remain independent."""
import json
import os
from pathlib import Path

MODES = ('continuous', 'split')


def supported(cfg):
    # Retained API/DSH tools use model-backed helpers. Keep their verified route.
    return not cfg.get('_model_profile') and cfg.get('_harness_transport', 'app-server') == 'app-server'


def new_task_mode(cfg):
    mode = cfg.get('author_context_mode', 'continuous' if supported(cfg) else 'split')
    if mode not in MODES:
        raise ValueError('author_context_mode must be continuous or split')
    if mode == 'continuous' and not supported(cfg):
        raise ValueError('Continuous author currently requires local Codex native tools; retain split for API/DSH')
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
    return ('CONTINUOUS AUTHOR: you own research, source/asset inspection, design, native implementation '
            'and repairs in this conversation. Phase boundaries are host checkpoints, not a handoff to '
            'another designer. Preserve the actual inspected evidence and decisions; revise provisional '
            'choices against the page. Keep research/planning validation before sequential native authoring. '
            'Batch independent native search queries and run independent supported tool calls concurrently; '
            'known asset URLs may download through web-media-proxy.py --submit-only while you continue. '
            'Do not serialize independent I/O merely because there is one author. Inspect material needed '
            'for the current composition before committing it. Use native search, image viewing/generation '
            'and deterministic tools. Model-backed search/browser/prefetch helpers and subagents are disabled '
            'in this mode; do not infer logged-in browser access or relabel hosted search as Google. '
            'This host policy overrides older separate-designer/helper descriptions in supplied guides. '
            'The host alone runs independent reviews in fresh contexts; do not impersonate reviewers. ')
