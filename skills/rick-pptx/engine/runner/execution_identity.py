"""Credential-free execution identity and observed phase summaries.

These are host receipts, not model claims or evidence of aesthetic quality.
Configured provider/model names are never described as provider-confirmed.
"""
import hashlib
import json
from pathlib import Path


def _hash(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def execution_identity(cfg):
    plugin = Path(cfg['plugin']) if cfg.get('plugin') else None
    version = cfg.get('plugin_version')
    manifest = plugin / '.codex-plugin/plugin.json' if plugin else None
    if manifest:
        try:
            version = version or json.loads(manifest.read_text()).get('version')
        except (OSError, ValueError, AttributeError):
            pass
    # Explicit whitelist: never copy a provider profile, endpoint, key, DSH home
    # or user-supplied configuration wholesale into an execution receipt.
    harness = cfg.get('_harness_identity') or {}
    profile = cfg.get('_model_profile') or {}
    selection = {
        'provider': harness.get('provider'),
        'model': harness.get('model') or profile.get('model') or cfg.get('_task_default_model'),
        'reasoning_effort': harness.get('reasoning_effort') or profile.get('reasoning_effort')
                            or cfg.get('_task_default_reasoning_effort'),
        'profile': harness.get('profile'),
        'wire_api': profile.get('wire_api'),
        'verification': 'host-selected; provider-resolved model not observed'}
    host = Path(__file__).resolve().parent
    distribution = None
    if cfg.get('_package_manifest'):
        path = Path(cfg['_package_manifest'])
        try:
            distribution = {'package_id': json.loads(path.read_text()).get('package_id'),
                            'manifest_sha256': _hash(path), 'verification': 'declared; run doctor --full for payload verification'}
        except (OSError, ValueError, AttributeError):
            distribution = {'package_id': None, 'manifest_sha256': None}
    return {
        'mode': 'managed', 'entrypoint': 'run_workflow',
        'harness_transport': cfg.get('_harness_transport', 'app-server'),
        'model_selection': selection,
        'plugin': {'version': version, 'manifest_sha256': _hash(manifest) if manifest else None,
                   'skill_sha256': _hash(plugin / 'skills/pptx/SKILL.md') if plugin else None},
        'engine_sha256': {name: _hash(host / name) for name in
                          ('workflow.py', 'phase_context.py', 'execution_continuity.py', 'execution_identity.py')},
        'distribution': distribution,
        'capability_evidence': 'Configured routes and observed tool events are separate; absent observations are unknown.'}


def phase_summary(phases):
    result = []
    for phase in phases:
        start, end = phase.get('started_at'), phase.get('ended_at')
        result.append({'id': phase['id'], 'name': phase['name'],
                       'status': phase.get('status', 'unknown' if phase.get('attempt_boundary') == 'unknown' else 'running'),
                       'elapsed_ms': max(0, end - start) if isinstance(start, int) and isinstance(end, int) else None,
                       'observed_tools': dict(phase.get('observed_tools') or {})})
    return result
