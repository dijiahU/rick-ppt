"""Load the immutable plugin's finite decision contract for host checks."""
import hashlib
import importlib.util
import json
from pathlib import Path

from progress import read_scoped


def choice_policy(cfg):
    plugin = Path(cfg['plugin'])
    catalog = plugin / 'skills/pptx/assets/workflow-choices.json'
    if not catalog.is_file():
        return None  # Historical runtimes keep their original recovery contract.
    script = plugin / 'skills/pptx/scripts/workflow_decisions.py'
    spec = importlib.util.spec_from_file_location('pptx_workflow_choices', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_decisions(cfg, job, outline, *, stage, artifact=None, required=True, mode='create', require_variation=None):
    policy = choice_policy(cfg)
    if policy is None:
        return None
    path = Path(job) / 'decision-plan.json'
    if not path.exists() and not required:
        return None
    raw = read_scoped(job, 'decision-plan.json', policy.MAX_PLAN_BYTES)
    profile = cfg.get('_model_profile')
    result = policy.validate_plan(json.loads(raw), outline, stage=stage, root=job,
                                  artifact=artifact, mode=mode,
                                  require_variation=require_variation,
                                  generation_enabled=not profile or profile.get('image_generation', False),
                                  search_enabled=not profile or profile.get('web_search', 'disabled') != 'disabled')
    return {**result, 'decision_plan_sha256': hashlib.sha256(raw).hexdigest()}


def needs_content_revision(receipt):
    """Implementation findings do not cause research merely due to reviewer role."""
    for kind in ('content', 'visual'):
        for finding in receipt[kind]['findings']:
            if finding['severity'] != 'required':
                continue
            route = finding.get('route')
            if route == 'content_revision' or route is None and kind == 'content':
                return True
    return False
