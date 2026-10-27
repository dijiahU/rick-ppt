"""One optional designer response inside the existing bounded repair loop.

Only a host review receipt authorizes this route. Suggestions remain optional;
neither their number nor the designer's taste becomes a new delivery gate.
"""
import hashlib
import base64
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from design_roles import enabled
from progress import read_scoped

POLICY={'version':1,'max_passes':1}


def mark_response(cfg,receipt,*,scoped):
    if (enabled(cfg) and not scoped and receipt.get('round')==1 and
            any(f.get('severity')=='suggestion' for f in receipt['visual']['findings'])):
        receipt['designer_response']=dict(POLICY)
    return receipt


def host_authorized_response(receipt):
    marker=receipt.get('designer_response')
    return (isinstance(marker,dict) and marker==POLICY and type(marker.get('version')) is int and
            receipt.get('round')==1 and receipt.get('review_mode')=='substantive' and
            type(receipt.get('input_revision')) is int and isinstance(receipt.get('plugin_version'),str) and
            any(f.get('severity')=='suggestion' for f in receipt.get('visual',{}).get('findings',[])))


def optional_response(receipt):
    return (host_authorized_response(receipt) and
            not any(f.get('severity')=='required' for kind in ('content','visual') for f in receipt[kind]['findings']))


def capture_metadata(job):
    result={}
    for name in ('outline.json','source-notes.md','decision-plan.json'):
        try:result[name]=read_scoped(job,name,2*1024*1024)
        except FileNotFoundError:result[name]=None
    return result


def _current_identity(run):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',run.task.get('id','')):raise ValueError('Invalid designer transaction task')
    state=run.journal.state if run.journal else {}
    return {'task_id':run.task['id'],'input_revision':state.get('input_revision',run.task.get('input_revision',0)),
            'author_completed_at':(state.get('completed_stages',{}).get('author') or {}).get('completed_at')}


def baseline_is_current(run,baseline):
    return baseline['identity']==_current_identity(run)


def save_baseline(run,artifact,receipt,rendered,review_states):
    """Host-private transaction baseline survives process loss and re-review."""
    records=Path(run.records).resolve(strict=True);job=Path(run.job).resolve(strict=True)
    if records.is_relative_to(job):raise ValueError('Designer baseline must be host private')
    digest=hashlib.sha256(artifact).hexdigest()
    if digest!=receipt['artifact_sha256'] or not optional_response(receipt):raise ValueError('Unverified designer baseline')
    identity=_current_identity(run)
    if identity['input_revision']!=receipt['input_revision']:raise ValueError('Stale designer baseline')
    home=records/(run.task['id']+'-designer-baseline-'+digest)
    if not home.exists():
        temporary=records/('.designer-baseline-'+uuid.uuid4().hex);temporary.mkdir(mode=0o700)
        def put(name,body):
            with (temporary/name).open('xb') as stream:stream.write(body)
            (temporary/name).chmod(0o600)
            return {'file':name,'sha256':hashlib.sha256(body).hexdigest()}
        try:
            artifact_info=put('presentation.pptx',artifact)
            pages=[put('page-'+str(n)+'.png',Path(path).read_bytes()) for n,path in enumerate(rendered['pages'],1)]
            metadata=capture_metadata(job)
            value={'version':1,'identity':identity,'receipt':receipt,'artifact':artifact_info,'pages':pages,
                   'review_states':review_states,'metadata':{name:base64.b64encode(body).decode() if body is not None else None for name,body in metadata.items()}}
            put('baseline.json',json.dumps(value,ensure_ascii=False).encode())
            os.rename(temporary,home)
        except BaseException:
            shutil.rmtree(temporary,ignore_errors=True);raise
    baseline=_load_home(home)
    if baseline['identity']!=identity or baseline['receipt']!=receipt:raise ValueError('Designer baseline identity conflict')
    return baseline


def _load_home(home):
    if home.is_symlink():raise ValueError('Unsafe designer baseline')
    value=json.loads(read_scoped(home,'baseline.json',16*1024*1024))
    if value.get('version')!=1 or not optional_response(value['receipt']):raise ValueError('Invalid designer baseline')
    def verified(info,limit):
        data=read_scoped(home,info['file'],limit)
        if hashlib.sha256(data).hexdigest()!=info['sha256']:raise ValueError('Designer baseline bytes changed')
        return data
    value['artifact_bytes']=verified(value['artifact'],30*1024*1024)
    if hashlib.sha256(value['artifact_bytes']).hexdigest()!=value['receipt']['artifact_sha256']:raise ValueError('Designer baseline review mismatch')
    for item in value['pages']:verified(item,30*1024*1024)
    value['rendered']={'pages':[str(home/item['file']) for item in value['pages']]}
    value['metadata_bytes']={name:base64.b64decode(body,validate=True) if body is not None else None for name,body in value['metadata'].items()}
    value['home']=str(home)
    status=Path(home)/'outcome.json'
    value['rolled_back']=status.is_file() and json.loads(read_scoped(home,'outcome.json',10000)).get('status')=='rolled_back'
    return value


def load_baseline(run):
    """Unambiguous host state only; task-local findings cannot create authority."""
    records=Path(run.records).resolve(strict=True);job=Path(run.job).resolve(strict=True)
    if records.is_relative_to(job):raise ValueError('Designer baseline must be host private')
    identity=_current_identity(run);matches=[]
    for home in records.glob(run.task['id']+'-designer-baseline-*'):
        value=_load_home(home)
        if value['identity']==identity:matches.append(value)
    if len(matches)>1:raise ValueError('Ambiguous designer transaction baseline')
    return matches[0] if matches else None


def mark_rollback(baseline):
    home=Path(baseline['home'])
    temporary=home/('.outcome-'+uuid.uuid4().hex)
    with temporary.open('x') as stream:json.dump({'status':'rolled_back','artifact_sha256':baseline['receipt']['artifact_sha256']},stream)
    os.replace(temporary,home/'outcome.json')
    baseline['rolled_back']=True


def restore_baseline(run,artifact,receipt,metadata,*,unpack=None,prepare=None):
    """Preserve failed work and rebuild editable state from reviewed exact bytes.

    This is not a successful design repair. A host receipt records that optional
    work was not applied. Lease/revision checks remain the caller's responsibility.
    """
    if hashlib.sha256(artifact).hexdigest()!=receipt['artifact_sha256']:
        raise ValueError('Optional refinement baseline hash changed')
    from repair_bootstrap import bootstrap_repair_workspace
    from tool_preparation import prepare_tool_manifest
    job=Path(run.job).resolve(strict=True)
    home=job/('designer-fallback-'+uuid.uuid4().hex);home.mkdir(mode=0o700)
    result=bootstrap_repair_workspace(home,run.cfg,artifact=artifact,
        artifact_sha256=receipt['artifact_sha256'],task_id=run.task['id'],
        input_revision=receipt['input_revision'],plugin_version=receipt['plugin_version'],
        repair_round=receipt['round'],unpack=unpack)
    def replace(name,body):
        destination=job/name
        if destination.is_symlink():raise ValueError('Unsafe optional-refinement metadata')
        temporary=job/('.designer-restore-'+uuid.uuid4().hex)
        with temporary.open('xb') as stream:stream.write(body)
        os.replace(temporary,destination)
    for name,body in metadata.items():
        current=job/name
        if current.is_file() and not current.is_symlink():
            # Preserve even an oversized/half-written optional attempt without
            # making its parseability a prerequisite for restoring accepted data.
            os.replace(current,home/('attempted-'+name))
        if body is None:
            if current.is_symlink():raise ValueError('Unsafe optional-refinement metadata')
            current.unlink(missing_ok=True)
        else:replace(name,body)
    replace('delivery.json',json.dumps({'path':result['candidate_path'],'workspace':result['workspace']}).encode())
    target={key:result[key] for key in ('binding','workspace','candidate_path','receipt_path','partial_edits_retained')}
    replace('repair-target.json',json.dumps(target).encode())
    (prepare or prepare_tool_manifest)(run.cfg,job,workspace=result['workspace'])
    response={'status':'not_applied','reason':'optional_refinement_failed',
              'artifact_sha256':receipt['artifact_sha256'],'round':receipt['round']}
    response_path=home/'designer-response.json';response_path.write_text(json.dumps(response))
    return [str(Path(result['candidate_path']).relative_to(job)),'delivery.json',
            str(response_path.relative_to(job)),'repair-target.json']
