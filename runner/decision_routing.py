"""Load the immutable plugin's finite decision contract for host checks."""
import hashlib
import importlib.util
import json
import os
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
    plan=json.loads(raw)
    profile = cfg.get('_model_profile')
    extra={}
    version=policy.load_catalog()['version']
    if version>=3:
        minimum=cfg.get('_choice_min_version',version)
        if minimum is not None and (type(plan.get('version')) is not int or plan['version']<minimum):raise ValueError('New work cannot bypass its pinned design contract')
        extra['allow_legacy']=minimum is None or minimum<version
        if 'requirements' in policy.load_catalog():
            extra['require_click_reveal']=click_reveal_required(cfg,mode=mode,require_variation=require_variation)
    result = policy.validate_plan(plan, outline, stage=stage, root=job,
                                  artifact=artifact, mode=mode,
                                  require_variation=require_variation,
                                  generation_enabled=not profile or profile.get('image_generation', False),
                                  search_enabled=not profile or profile.get('web_search', 'disabled') != 'disabled',**extra)
    return {**result, 'decision_plan_sha256': hashlib.sha256(raw).hexdigest()}


def pin_decision_contract(cfg,state_root,task_id,existing):
    path=Path(state_root)/task_id/'decision-contract.json'
    if path.is_file():return json.loads(path.read_text())['version']
    if existing:return None  # Previously admitted tasks keep their original records.
    policy=choice_policy(cfg)
    if policy is None:return None
    version=policy.load_catalog()['version'];path.parent.mkdir(parents=True,exist_ok=True)
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:
        json.dump({'version':version,'click_reveal_required':bool(policy.load_catalog().get('requirements',{}).get('new_deck_click_reveal'))},stream)
    return version


def admitted_click_requirement(state_root,task_id):
    path=Path(state_root)/task_id/'decision-contract.json'
    return bool(json.loads(path.read_text()).get('click_reveal_required',False)) if path.is_file() else False


def click_reveal_required(cfg,*,mode='create',require_variation=None):
    catalog=Path(cfg['plugin'])/'skills/pptx/assets/workflow-choices.json'
    current=bool(catalog.is_file() and json.loads(catalog.read_text()).get('requirements',{}).get('new_deck_click_reveal'))
    pinned=cfg.get('_native_reveal_required',current and cfg.get('_choice_min_version',3) is not None)
    return bool(pinned) and mode=='create' and require_variation is not False


def write_design_packet(cfg,job,packet,artifact):
    policy=choice_policy(cfg)
    if policy is None or not hasattr(policy,'design_report'):return
    notes={'pages':[{'number':i+1,'text':entry['notes']} for i,entry in enumerate(policy._page_evidence(artifact))]}
    (Path(packet)/'audience-notes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2))
    if not (Path(job)/'decision-plan.json').is_file():return
    raw=read_scoped(job,'decision-plan.json',policy.MAX_PLAN_BYTES)
    plan=json.loads(raw);report=policy.design_report(plan,artifact)
    for entry in report.get('references',[]):
        if entry['inspection']=='local_image':
            source=policy._local_file(job,entry['evidence'])
            relative=Path('design-reference-images')/(entry['id']+source.suffix.lower())
            destination=Path(packet)/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(read_scoped(job,source.relative_to(Path(job).resolve()),30*1024*1024))
            entry['review_image']=relative.as_posix()
    (Path(packet)/'design-references.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))


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
