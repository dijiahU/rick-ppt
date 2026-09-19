"""Bounded, offline validation for untrusted scene specifications and sidecars."""
from __future__ import annotations
import json
import hashlib
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, unquote
from .common import PptxError, sha256

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
SCHEMAS = PLUGIN_ROOT / 'skills/pptx/schemas'
FORBIDDEN = {'__proto__', 'prototype', 'constructor', 'caller', 'callee', 'arguments'}
MAX_JSON = 8 * 1024 * 1024


def config():
    return json.loads((PLUGIN_ROOT / 'runtime/config.json').read_text())


def runtime_fingerprint(runtime=None):
    root=Path(runtime or PLUGIN_ROOT/'runtime/dist').resolve()
    if not (root/'preview.html').is_file():raise PptxError('Interactive runtime build is missing')
    inventory={}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():raise PptxError('Runtime build contains a symlink')
        if path.is_file():inventory[path.relative_to(root).as_posix()]=sha256(path)
    encoded=json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()
    return {'sha256':hashlib.sha256(encoded).hexdigest(),'files':len(inventory),
            'configuration':sha256(PLUGIN_ROOT/'runtime/config.json')}


def verified_receipt(report,scene,spec_hash,home,runtime):
    """Validate local evidence integrity; the website host still reruns tests."""
    if (report.get('receiptVersion')!=1 or report.get('ok') is not True or
        report.get('runtime_verified') is not True or report.get('errors')!=[] or
        report.get('specHash')!=spec_hash or report.get('sceneId')!=scene['id'] or
        report.get('runtime')!=runtime):return False
    plan=scene.get('testPlan',[]);tests=report.get('tests',[])
    if not plan or len(tests)!=len(plan) or report.get('testCount')!=len(plan):return False
    for expected,actual in zip(plan,tests):
        if not isinstance(actual,dict) or not expected.get('assertions') or actual.get('ok') is not True or actual.get('name')!=expected['name'] or actual.get('assertions')!=len(expected['assertions']):return False
    captures=report.get('captures',[]);hashes=report.get('captureHashes',{})
    if not isinstance(captures,list) or not {'initial.png','reset.png'}.issubset(captures) or set(captures)!=set(hashes):return False
    directory=Path(report.get('directory',''))
    if not directory.is_absolute() or not directory.is_relative_to(home/'interactive/renders'):return False
    for name in captures:
        path=safe_path(home,directory.relative_to(home).as_posix()+'/'+name)
        if path.stat().st_size>30*1024*1024 or sha256(path)!=hashes[name]:return False
        from PIL import Image
        with Image.open(path) as image:
            if image.format!='PNG' or image.width*image.height>20000000:return False
            image.verify()
    return True


def safe_path(root, name, must_exist=True):
    root = Path(root).absolute()
    if not isinstance(name, str) or not name or unquote(name) != name:
        raise PptxError('Invalid asset path')
    p = PurePosixPath(name)
    if p.is_absolute() or any(x in {'..', '.', ''} for x in name.split('/')) or any(x in name for x in ('\\', ':', '\x00')):
        raise PptxError(f'Unsafe sidecar path: {name}')
    path = root / name
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise PptxError(f'Symlink not permitted: {name}')
        if part == root:
            break
    if not path.resolve().is_relative_to(root.resolve()):
        raise PptxError('Path escapes sidecar')
    if must_exist and not path.is_file():
        raise PptxError(f'Missing sidecar file: {name}')
    return path


def read_json(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > MAX_JSON:
        raise PptxError('Unsafe or oversized JSON file')
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result or k in FORBIDDEN:
                raise PptxError('Duplicate or forbidden JSON key')
            result[k] = v
        return result
    try:
        return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(PptxError('Nonfinite JSON number')))
    except (ValueError, RecursionError) as error:
        raise PptxError(f'Invalid JSON: {error}') from error


def structural(value, depth=0):
    if depth > 48:
        raise PptxError('JSON maximum nesting depth exceeded')
    if isinstance(value, dict):
        for k, v in value.items():
            if k in FORBIDDEN:
                raise PptxError('Forbidden object key')
            structural(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > 10000:
            raise PptxError('Array item limit exceeded')
        for v in value:
            structural(v, depth + 1)


def schema_validate(value, name):
    from jsonschema import Draft7Validator
    structural(value)
    validator = Draft7Validator(read_json(SCHEMAS / name))
    errors = list(validator.iter_errors(value))
    if errors:
        raise PptxError('Schema validation: ' + '; '.join(f'{"/".join(map(str,e.path))}: {e.message}' for e in errors[:10]))


def migrate_scene(value):
    # Explicit migration dispatch: new versions add functions here, never silently coerce.
    if value.get('schemaVersion') != 1:
        raise PptxError(f'Unsupported scene schemaVersion: {value.get("schemaVersion")}')
    return value


def validate_spec(value, asset_root=None, require_hashes=False):
    if isinstance(value, (str, Path)):
        path = Path(value)
        asset_root = asset_root or path.parent
        value = read_json(path)
    value = migrate_scene(value)
    schema_validate(value, 'interactive-slide.schema.json')
    ids = set()
    count = 0
    def walk(nodes, depth=0):
        nonlocal count
        if depth > 32:
            raise PptxError('Node nesting limit exceeded')
        for node in nodes:
            count += 1
            if count > 10000 or node['id'] in ids:
                raise PptxError('Too many or duplicate scene nodes')
            ids.add(node['id'])
            walk(node.get('children', []), depth + 1)
    walk(value['nodes'])
    allow = value.get('runtimeOptions', {}).get('networkAllowlist', [])
    def check_url(url):
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc:
            origin = f'{parsed.scheme}://{parsed.netloc}'
            if parsed.scheme not in ('https','wss') or origin not in allow or parsed.username or parsed.password:
                raise PptxError(f'Undeclared network URL: {origin}')
        elif asset_root:
            safe_path(asset_root, url)
        else:
            safe_path(Path('/nonexistent-sidecar'), url, False)
    for name, a in value.get('assets', {}).items():
        check_url(a['path'])
        if not urlsplit(a['path']).scheme and asset_root:
            path = safe_path(asset_root, a['path'])
            if path.stat().st_size > 512*1024*1024:
                raise PptxError('Asset size limit exceeded')
            if a.get('bytes') is not None and path.stat().st_size != a['bytes']:
                raise PptxError(f'Asset size mismatch: {name}')
            if require_hashes and not a.get('sha256') or a.get('sha256') and sha256(path) != a['sha256']:
                raise PptxError(f'Asset hash mismatch: {name}')
    for source in value.get('dataSources', {}).values():
        if source.get('path') or source.get('url'):
            check_url(source.get('path') or source['url'])
    for plugin in value.get('plugins', []):
        if plugin['id'] not in value.get('runtimeOptions', {}).get('allowedPlugins', []):
            raise PptxError('Custom plugin requires explicit allowlisting')
        if urlsplit(plugin['path']).scheme:
            raise PptxError('Remote plugin code prohibited')
        if asset_root and sha256(safe_path(asset_root, plugin['path'])) != plugin['sha256']:
            raise PptxError('Plugin hash mismatch')
    timeline_ids = {t['id'] for t in value.get('timelines', [])}
    if len(timeline_ids) != len(value.get('timelines', [])):
        raise PptxError('Duplicate timeline ID')
    for timeline in value.get('timelines', []):
        for track in timeline['tracks']:
            times = [k['time'] for k in track['keyframes']]
            if not times or times != sorted(set(times)) or times[0] < 0 or times[-1] > timeline['duration']:
                raise PptxError('Invalid timeline keyframe order or time')
    return value


def validate_bundle_manifest(value, root=None):
    schema_validate(value, 'interactive-bundle.schema.json')
    if root:
        for scene in value['scenes'].values():
            path = safe_path(root, scene['path'])
            if sha256(path) != scene['sha256']:
                raise PptxError('Scene hash mismatch')
            validate_spec(read_json(path), root, True)
        for name, expected in value['assets'].items():
            if sha256(safe_path(root, name)) != expected:
                raise PptxError(f'Bundle asset hash mismatch: {name}')
    return value


def validate_interactive(root, sidecar=None, require_runtime=False):
    from .interactive_ooxml import discover_content_addins, validate_ooxml
    errors = validate_ooxml(root)
    instances = [i for i in discover_content_addins(root) if i.get('addinId') == config()['addinId']]
    if not instances:
        return {'ok': not errors, 'errors': errors, 'instances': [], 'runtime_verified': False, 'powerpoint_playback_verified': False}
    sidecar = Path(sidecar) if sidecar else Path(root).parent/'interactive/deck'
    try:
        bundle = validate_bundle_manifest(read_json(safe_path(sidecar, 'bundle.json')), sidecar)
        for i in instances:
            if i['deckId'] != bundle['deckId'] or i['sceneId'] not in bundle['scenes']:
                raise PptxError('Scene identity missing from bundle')
            if i['specHash'] != bundle['scenes'][i['sceneId']]['sha256']:
                raise PptxError('OOXML/scene hash mismatch')
        verified = True
        fingerprint = runtime_fingerprint()
        for scene in {i['sceneId'] for i in instances}:
            report_path = sidecar.parent/'tests'/f'{scene}.json'
            report = read_json(report_path) if report_path.exists() else {}
            specification=read_json(safe_path(sidecar,bundle['scenes'][scene]['path']))
            valid = verified_receipt(report,specification,bundle['scenes'][scene]['sha256'],Path(root).parent,fingerprint)
            verified = bool(verified and valid)
            if require_runtime and not valid:
                raise PptxError(f'Missing/stale runtime test: {scene}')
    except (PptxError, OSError, KeyError, ValueError, TypeError) as error:
        errors.append(str(error)); verified = False
    return {'ok':not errors,'errors':errors,'instances':instances,'runtime_verified':verified,'powerpoint_playback_verified':False}
