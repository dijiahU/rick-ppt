"""Repair known local artifact paths in a verified, newly restored task attempt.

No archived commands run here. Only active workspace state and runtime-render
receipt JSON are changed; original bytes and snapshot history remain untouched.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
import re
import stat
import uuid
import zipfile
from pathlib import Path

MAX_JSON=8*1024*1024


def resolve_delivery(delivery, current_root, recoveries=()):
    """Resolve known delivery fields using only host-owned recovery history.

    Keep the author receipt byte-identical so a verified completed author phase
    stays reusable. No old directory is opened and no archived commands execute.
    The caller still reads each resolved file through its scoped file reader.
    """
    if not isinstance(delivery,dict) or not isinstance(delivery.get('path'),str):
        raise ValueError('Missing exported delivery path')
    root=Path(current_root).resolve(strict=True)
    aliases={root}
    for recovery in recoveries:
        if not isinstance(recovery,dict):raise ValueError('Invalid recovery history')
        for key in ('previous_workspace','workspace'):
            value=recovery.get(key)
            if isinstance(value,str) and Path(value).is_absolute():aliases.add(Path(value))
    result=copy.deepcopy(delivery)
    for key in ('path','workspace'):
        value=result.get(key)
        if value is None and key=='workspace':continue
        if not isinstance(value,str) or not value or '\\' in value or '\x00' in value or '..' in Path(value).parts:
            raise ValueError('Invalid delivery '+key)
        path=Path(value)
        if path.is_absolute():
            matches=[alias for alias in aliases if path.is_relative_to(alias)]
            if not matches:raise ValueError('Delivery path is outside this task and its recovery history')
            origin=max(matches,key=lambda alias:len(alias.parts))
            path=root/path.relative_to(origin)
        else:path=root/path
        if not path.resolve().is_relative_to(root):raise ValueError('Delivery path escapes restored task')
        result[key]=str(path)
    return result


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def read(path):
    if path.is_symlink() or path.stat().st_size>MAX_JSON:raise ValueError('Unsafe or oversized recovery JSON')
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('Duplicate recovery JSON key')
            value[key]=item
        return value
    value=json.loads(path.read_text(),object_pairs_hook=pairs)
    if not isinstance(value,dict):raise ValueError('Recovery receipt must be an object')
    return value


def safe_tree(root):
    count=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        for name in [*dirs,*files]:
            count+=1
            if count>200000:raise ValueError('Recovery task file limit exceeded')
            if (Path(directory)/name).is_symlink():raise ValueError('Recovery task contains a symlink')
        dirs[:]=[name for name in dirs if name!='.recovery-relocation']


def relocate_task(old_root,new_root,cfg=None):
    """Return path mappings and invalidations; fail before writes on tamper.

    The caller verifies/restores its host-owned checkpoint first, and excludes
    model or old-worker writes to the new attempt during relocation.
    """
    old_root=Path(old_root).resolve();given=Path(new_root)
    if given.is_symlink():raise ValueError('Restored task root is a symlink')
    new_root=given.resolve(strict=True)
    if not new_root.is_dir() or new_root==old_root or new_root.is_relative_to(old_root) or old_root.is_relative_to(new_root):raise ValueError('Recovery requires distinct, nonoverlapping task roots')
    safe_tree(new_root);planned={};workspaces={};reports=[];invalidated=[]

    def local(value):
        if not isinstance(value,str) or not Path(value).is_absolute():return None
        path=Path(value).resolve()
        if path.is_relative_to(old_root):path=new_root/path.relative_to(old_root)
        if not path.is_relative_to(new_root):return None
        return path

    def receipt(value,home):
        if not isinstance(value,dict):return None,'receipt is not an object'
        result=copy.deepcopy(value);directory=local(value.get('directory'))
        if not directory or not directory.is_dir():return None,'runtime render directory is missing'
        result['directory']=str(directory)
        captures=value.get('captures',[])
        if not isinstance(captures,list) or not captures:return None,'runtime captures are missing'
        output=[]
        for capture in captures:
            if not isinstance(capture,str):return None,'runtime capture path is invalid'
            if Path(capture).is_absolute():path=local(capture);rewritten=str(path) if path else None
            else:
                path=directory/capture;rewritten=capture
                if '..' in Path(capture).parts or '\\' in capture:return None,'runtime capture path escapes its directory'
            if not path or not path.resolve().is_relative_to(directory) or not path.is_file():return None,'runtime capture file is missing'
            output.append(rewritten)
        result['captures']=output
        scene_id=result.get('sceneId');bundle_path=home/'interactive/deck/bundle.json'
        if not isinstance(scene_id,str) or not bundle_path.is_file():return None,'runtime receipt has no bundled scene'
        bundle=read(bundle_path);scene=bundle.get('scenes',{}).get(scene_id)
        if not isinstance(scene,dict):return None,'runtime scene identity is missing'
        relative=scene.get('path','');scene_path=home/'interactive/deck'/relative
        if not isinstance(relative,str) or Path(relative).is_absolute() or '..' in Path(relative).parts or not scene_path.is_file():return None,'runtime scene file is missing'
        actual=digest(scene_path)
        if result.get('specHash')!=actual or scene.get('sha256')!=actual:return None,'runtime receipt scene hash is stale'
        if not result.get('ok') or not result.get('runtime_verified') or result.get('testCount',0)<1:return None,'runtime receipt was not verified'
        return result,None

    def invalidate(path,value,reason):
        result=copy.deepcopy(value);result.update(ok=False,runtime_verified=False,recovery_invalidated=True,recovery_reason=reason)
        directory=local(result.get('directory'))
        result['directory']=str(directory) if directory else None
        invalidated.append({'path':str(path.relative_to(new_root)),'reason':reason})
        return result

    candidates=[]
    for directory,dirs,files in os.walk(new_root,followlinks=False):
        dirs[:]=[name for name in dirs if name not in ('.recovery-relocation','snapshots') and not name.startswith('.replaced-')]
        home=Path(directory)
        if 'state.json' in files and (home/'workspace').is_dir() and (home/'original.pptx').is_file():candidates.append(home)
    for home in sorted(candidates):
        path=home/'state.json';value=read(path);result=copy.deepcopy(value);old_home=old_root/home.relative_to(new_root)
        if value.get('version') not in (1,2) or Path(value.get('workspace','')).resolve() not in (old_home/'workspace',home/'workspace'):raise ValueError('Invalid restored workspace identity: '+str(path.relative_to(new_root)))
        protected=home/'original.pptx';expected=value.get('source_hash')
        if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or digest(protected)!=expected:raise ValueError('Restored protected original hash mismatch: '+str(path.relative_to(new_root)))
        if not zipfile.is_zipfile(protected):raise ValueError('Restored original is not a PowerPoint package')
        with zipfile.ZipFile(protected) as archive:
            if not {'[Content_Types].xml','ppt/presentation.xml'}.issubset(archive.namelist()):raise ValueError('Restored original lacks PowerPoint parts')
        source=local(value.get('source'));source_fallback=not(source and source.is_file() and digest(source)==expected)
        if source_fallback:source=protected
        result.update(workspace=str(home/'workspace'),source=str(source),last_validation=None)
        for key,is_directory in (('latest_output',False),('latest_bundle',True)):
            old=value.get(key);candidate=local(old)
            exists=bool(candidate and (candidate.is_dir() if is_directory else candidate.is_file()))
            result[key]=str(candidate) if exists else None
            if old and not exists:invalidated.append({'path':str(path.relative_to(new_root))+':'+key,'reason':'restored artifact is missing or outside this attempt'})
        render=value.get('last_render')
        if render:
            candidate=copy.deepcopy(render);pdf=local(render.get('pdf'));pages=[local(p) for p in render.get('pages',[])]
            valid=bool(pdf and pdf.is_file() and pages and all(p and p.is_file() for p in pages))
            if valid:
                candidate.update(pdf=str(pdf),pages=[str(p) for p in pages]);result['last_render']=candidate
            else:
                result['last_render']=None;invalidated.append({'path':str(path.relative_to(new_root))+':last_render','reason':'native render files are missing'})
        if value.get('latest_interactive_render'):
            candidate,reason=receipt(value['latest_interactive_render'],home)
            result['latest_interactive_render']=candidate
            if reason:invalidated.append({'path':str(path.relative_to(new_root))+':latest_interactive_render','reason':reason})
        for report_path in sorted([*(home/'interactive/tests').glob('*.json'),*(home/'interactive/renders').rglob('report.json')]):
            original=read(report_path);candidate,reason=receipt(original,home)
            if reason:candidate=invalidate(report_path,original,reason)
            if candidate!=original:planned[report_path]=candidate
        if result!=value:planned[path]=result
        workspaces[str(old_home)]=str(home);workspaces[str(old_home/'workspace')]=str(home/'workspace')
        reports.append({'home':str(home),'source':str(source),'sourceFallback':source_fallback,'sourceHash':expected})
    backup=None
    if planned:
        backup=new_root/'.recovery-relocation'/uuid.uuid4().hex;backup.mkdir(parents=True,exist_ok=False)
        inventory={}
        for path in sorted(planned):
            relative=path.relative_to(new_root);target=backup/relative;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(path.read_bytes())
            inventory[relative.as_posix()]=digest(target)
        with (backup/'inventory.json').open('x') as stream:json.dump(inventory,stream,indent=2)
        for path,value in planned.items():
            temporary=path.with_name(path.name+'.relocation-'+uuid.uuid4().hex)
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,stat.S_IMODE(path.stat().st_mode))
            with os.fdopen(fd,'w') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path)
    return {'ok':True,'old_root':str(old_root),'new_root':str(new_root),'workspace_count':len(reports),'workspaces':workspaces,'states':reports,'invalidated':invalidated,'backup':str(backup) if backup else None,'changed':len(planned),'snapshotsRetained':True}
