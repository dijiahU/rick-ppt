"""Scene-sidecar authoring and CLI orchestration; native export stays independent."""
from __future__ import annotations
import copy
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from .common import PptxError,atomic_json,now,sha256,parse,NS
from .package import select
from .snapshots import snapshot
from .interactive_validate import PLUGIN_ROOT,config,read_json,safe_path,validate_spec,validate_interactive
from .interactive_ooxml import attach_content_addin,discover_content_addins,remove_content_addin,clone_content_addin,resize_content_addin,update_content_addin


def deck_manifest(ws):
    path=ws.home/'interactive/deck/bundle.json'
    if path.exists():return read_json(path)
    cfg=config()
    return {'bundleVersion':1,'deckId':'deck-'+uuid.uuid4().hex,'pptxHash':ws.state['source_hash'],'runtimeVersion':cfg['runtimeVersion'],'addinId':cfg['addinId'],'schemaVersion':1,'slides':[],'scenes':{},'assets':{},'featurePacks':[],'generatedAt':now()}


def sync_manifest(ws,bundle=None):
    bundle=bundle or deck_manifest(ws);bundle['slides']=[i for i in discover_content_addins(ws.root) if i.get('addinId')==config()['addinId']]
    atomic_json(ws.home/'interactive/deck/bundle.json',bundle)
    ws.state.update(interactive=bool(bundle['slides']),runtime_version=config()['runtimeVersion'],bundle_manifest='interactive/deck/bundle.json')
    ws.refresh();ws.save();return bundle


def import_scene(ws,source,replace=False):
    source=Path(source).resolve();spec=copy.deepcopy(validate_spec(source));deck=ws.home/'interactive/deck';bundle=deck_manifest(ws)
    imported={};imported_bytes=0
    def import_file(name,base=None,dependency=False):
        nonlocal imported_bytes
        parsed=urlsplit(name)
        if parsed.scheme or parsed.netloc:
            origin=parsed.scheme+'://'+parsed.netloc
            if dependency or parsed.scheme!='https' or origin not in spec.get('runtimeOptions',{}).get('networkAllowlist',[]):
                raise PptxError('Asset dependency must be a scoped local file or explicitly allowed HTTPS asset')
            return name
        path=safe_path(base or source.parent,name);ext=path.suffix.lower()
        if path in imported:return imported[path]
        if len(imported)>=4096:raise PptxError('Scene asset count limit exceeded')
        size=path.stat().st_size
        if size>512*1024*1024 or imported_bytes+size>512*1024*1024:raise PptxError('Scene asset byte limit exceeded')
        imported_bytes+=size
        if ext=='.gltf':
            if dependency:raise PptxError('Nested glTF dependency is not permitted')
            gltf=read_json(path)
            if not isinstance(gltf,dict):raise PptxError('glTF must be an object')
            entries=[*gltf.get('buffers',[]),*gltf.get('images',[])]
            if len(entries)>4096:raise PptxError('glTF dependency count limit exceeded')
            for entry in entries:
                uri=entry.get('uri') if isinstance(entry,dict) else None
                if uri is not None:
                    if not isinstance(uri,str):raise PptxError('Invalid glTF resource URI')
                    if uri.startswith('data:'):continue
                    entry['uri']=Path(import_file(uri,path.parent,True)).name
            body=json.dumps(gltf,ensure_ascii=False,separators=(',',':')).encode()
        else:body=path.read_bytes()
        digest=hashlib.sha256(body).hexdigest();dest='assets/'+digest+ext
        target=safe_path(deck,dest,False);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if sha256(target)!=digest:raise PptxError('Previously imported asset hash mismatch')
        else:
            with target.open('xb') as stream:stream.write(body)
        imported[path]=dest;bundle['assets'][dest]=digest;return dest
    for asset in spec.get('assets',{}).values():
        asset['path']=import_file(asset['path'])
        if not urlsplit(asset['path']).scheme:
            path=safe_path(deck,asset['path']);asset.update(sha256=sha256(path),bytes=path.stat().st_size)
    for ds in spec.get('dataSources',{}).values():
        if ds.get('path'):ds['path']=import_file(ds['path'])
    for plugin in spec.get('plugins',[]):
        plugin['path']=import_file(plugin['path']);plugin['sha256']=sha256(safe_path(deck,plugin['path']))
    # Native media/image nodes may reference declared asset IDs only in a bundled scene.
    def nodes(items):
        for node in items:
            props=node.get('props',{})
            keys=['src','poster']
            if node.get('component')=='ModelRunner':keys.append('model')
            if node.get('component')=='imageComparison':keys.extend(('before','after'))
            for key in keys:
                if isinstance(props.get(key),str) and props[key] not in spec.get('assets',{}):
                    props[key]=import_file(props[key])
            if node.get('component')=='carousel':
                for index,item in enumerate(props.get('items',[])):
                    value=item.get('src') if isinstance(item,dict) else item
                    if isinstance(value,str) and value not in spec.get('assets',{}):
                        if isinstance(item,dict):item['src']=import_file(value)
                        else:props['items'][index]=import_file(value)
            nodes(node.get('children',[]))
    nodes(spec['nodes'])
    relative=f'scenes/{spec["id"]}.json';path=safe_path(deck,relative,False)
    if path.exists() and read_json(path)!=spec and not replace:raise PptxError('A different scene already uses this ID; use a new scene ID or explicit update')
    atomic_json(path,spec);bundle['scenes'][spec['id']]={'path':relative,'sha256':sha256(path)};bundle['featurePacks']=sorted(set(bundle['featurePacks'])|set(spec.get('requires',[])))
    atomic_json(deck/'bundle.json',bundle)
    return spec,path,bundle


def update_scene(ws,source):
    with ws.lock():
        ws.check_original();checkpoint=snapshot(ws,'before-interactive-update')
        spec,path,bundle=import_scene(ws,source,replace=True)
        report=scene_render(ws,spec['id']);fallback=Path(report['directory'])/'initial.png'
        changed=[]
        for item in discover_content_addins(ws.root):
            if item.get('addinId')==config()['addinId'] and item.get('sceneId')==spec['id']:
                changed.append(update_content_addin(ws.root,item['instanceId'],{'specHash':sha256(path)},fallback))
        sync_manifest(ws,bundle)
        return {'updated':changed,'scene':spec['id'],'snapshot_id':checkpoint,'runtime_verified':report['runtime_verified']}


def scene_render(ws,scene_id):
    from interactive_render import render_scene
    bundle=deck_manifest(ws);record=bundle['scenes'][scene_id];deck=ws.home/'interactive/deck'
    destination=ws.home/'interactive/renders'/f'{scene_id}-{uuid.uuid4().hex[:10]}'
    result=render_scene(safe_path(deck,record['path']),destination,deck_root=deck,deck_id=bundle['deckId'])
    atomic_json(ws.home/'interactive/tests'/f'{scene_id}.json',result)
    ws.state['latest_interactive_render']=result;ws.save();return result


def attach(ws,slide,source,bounds=None,fallback=None):
    with ws.lock():
        ws.check_original();checkpoint=snapshot(ws,'before-interactive-attach');spec,path,bundle=import_scene(ws,source)
        if bounds is None:
            size=parse(ws.root/'ppt/presentation.xml').find('p:sldSz',NS);bounds={'x':0,'y':0,'width':int(size.get('cx')),'height':int(size.get('cy'))}
        if fallback is None:
            report=scene_render(ws,spec['id']);fallback=Path(report['directory'])/'initial.png'
        meta={'deckId':bundle['deckId'],'sceneId':spec['id'],'schemaVersion':spec['schemaVersion'],'specHash':sha256(path)}
        result=attach_content_addin(ws.root,slide,meta,bounds,fallback)
        sync_manifest(ws,bundle);report=validate_interactive(ws.root)
        if not report['ok']:raise PptxError('; '.join(report['errors']))
        return {**result,'snapshot_id':checkpoint,'runtime_verified':report['runtime_verified'],'powerpoint_playback_verified':False}


def doctor(ws=None):
    checks={};runtime=PLUGIN_ROOT/'runtime';checks['runtime_build']=(runtime/'dist/preview.html').is_file();checks['node']=shutil.which('node') is not None
    if checks['node']:checks['node_version']=subprocess.check_output(['node','--version'],text=True).strip()
    for module in ('aiohttp','jsonschema','playwright'):checks[module]=__import__('importlib.util',fromlist=['find_spec']).find_spec(module) is not None
    from .interactive_server import certificate_paths,tls_context
    cert,key=certificate_paths();checks['certificate']=cert.is_file() and key.is_file()
    if checks['certificate']:
        try:tls_context();checks['certificate_parse']=True
        except Exception:checks['certificate_parse']=False
    with socket.socket() as s:checks['port_available']=s.connect_ex(('127.0.0.1',config()['port']))!=0
    checks['xml_manifest']=(runtime/'manifests/manifest.addin.xml').is_file();checks['unified_manifest']=(runtime/'manifests/manifest.unified.json').is_file()
    checks['feature_packs']={name:any((runtime/'src/feature-packs'/name/f'index.{ext}').exists() for ext in ('ts','tsx')) or any((runtime/'src/feature-packs'/f'{name}.{ext}').exists() for ext in ('ts','tsx')) for name in ('three','code','ml','map','math')}
    if ws:checks['interactive']=validate_interactive(ws.root)
    return checks


def add_parser(commands):
    p=commands.add_parser('interactive');p.add_argument('--workspace','-w',dest='interactive_workspace');sub=p.add_subparsers(dest='interactive_command',required=True)
    for name in ('doctor','list'):sub.add_parser(name)
    inspect=sub.add_parser('inspect');inspect.add_argument('slide',type=int)
    for name in ('validate-spec','preview'):
        q=sub.add_parser(name);q.add_argument('file')
    q=sub.add_parser('update');q.add_argument('--scene',required=True)
    q=sub.add_parser('attach');q.add_argument('--slide',type=int,required=True);q.add_argument('--scene',required=True);q.add_argument('--bounds',choices=['full']);q.add_argument('--fallback');
    for name in ('x','y','width','height'):q.add_argument('--'+name,type=int)
    for name in ('detach','clone','resize'):
        q=sub.add_parser(name);q.add_argument('--instance',required=True);q.add_argument('--slide',type=int)
        if name=='resize':
            for key in ('x','y','width','height'):q.add_argument('--'+key,type=int,required=True)
    q=sub.add_parser('render');q.add_argument('--slide',type=int);q.add_argument('--scene')
    q=sub.add_parser('serve');q.add_argument('--root');q.add_argument('--port',type=int,default=config()['port']);q.add_argument('--http',action='store_true')
    q=sub.add_parser('bundle');q.add_argument('output');q.add_argument('--zip',action='store_true')
    q=sub.add_parser('cert');q.add_argument('action',choices=['install','status'])
    # Both global -w and `interactive COMMAND --workspace` are accepted.
    for parser in sub.choices.values():parser.add_argument('--workspace','-w',dest='sub_workspace')


def dispatch(args):
    command=args.interactive_command;ws_path=args.sub_workspace or args.interactive_workspace or args.workspace
    if command=='validate-spec':return {'ok':True,'scene':validate_spec(args.file)['id']}
    if command=='doctor':return doctor(select(ws_path) if ws_path else None)
    if command=='cert':
        if args.action=='status':return {k:v for k,v in doctor().items() if k.startswith('certificate')}
        subprocess.run(['node','scripts/certificates.mjs'],cwd=PLUGIN_ROOT/'runtime',check=True);return {'certificate':True}
    if command=='preview':
        validate_spec(args.file);source=Path(args.file).resolve()
        from .interactive_server import main
        print(json.dumps({'preview':f'http://127.0.0.1:{config()["port"]}/preview.html?spec=source/{source.name}'}),flush=True)
        main(['--root',str(source.parent),'--http']);return {'stopped':True}
    if command=='serve':
        from .interactive_server import main
        root=args.root or str(select(ws_path).home/'interactive');opts=['--root',root,'--port',str(args.port)]
        if args.http:opts.append('--http')
        main(opts);return {'stopped':True}
    ws=select(ws_path)
    if command=='update':return update_scene(ws,args.scene)
    if command in ('list','inspect'):
        records=discover_content_addins(ws.root)
        return records if command=='list' else [r for r in records if r['slide']==args.slide]
    if command=='attach':
        values=[getattr(args,k) for k in ('x','y','width','height')]
        if any(v is not None for v in values) and not all(v is not None for v in values):raise PptxError('Specify all four bounds in EMUs')
        return attach(ws,args.slide,args.scene,dict(zip(('x','y','width','height'),values)) if all(v is not None for v in values) else None,args.fallback)
    if command in ('detach','clone','resize'):
        with ws.lock():
            snapshot(ws,'before-interactive-'+command)
            if command=='detach':result=remove_content_addin(ws.root,args.instance)
            elif command=='clone':result=clone_content_addin(ws.root,args.instance,args.slide)
            else:result=resize_content_addin(ws.root,args.instance,{k:getattr(args,k) for k in ('x','y','width','height')})
            sync_manifest(ws);return result
    if command=='render':
        records=discover_content_addins(ws.root);ids={args.scene} if args.scene else {r['sceneId'] for r in records if not args.slide or r['slide']==args.slide}
        return [scene_render(ws,ident) for ident in sorted(ids)]
    if command=='bundle':
        from .interactive_bundle import assemble_bundle
        return assemble_bundle(ws,args.output,args.zip)
    raise PptxError('Unknown interactive command')
