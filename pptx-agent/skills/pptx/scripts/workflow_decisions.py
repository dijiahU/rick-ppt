"""Validate finite workflow choices, page coverage and selected embedded bytes.

This validates routing records, not aesthetics or whether a source is trustworthy.
It never executes instructions from a presentation or modifies a deck.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import posixpath
from xml.etree import ElementTree as ET
import zipfile

CATALOG = Path(__file__).resolve().parents[1] / 'assets/workflow-choices.json'
MAX_PLAN_BYTES = 512 * 1024


def load_catalog():
    catalog = json.loads(CATALOG.read_text())
    if set(catalog['eligible_forms']) != set(catalog['page']['intent']):
        raise ValueError('Catalog intent branches are incomplete')
    for options in catalog['eligible_forms'].values():
        if not options or len(options) != len(set(options)) or set(options) - set(catalog['page']['form']):
            raise ValueError('Catalog has invalid eligible forms')
    return catalog


def plan_template(outline):
    catalog = load_catalog()
    return {'version': catalog['version'], 'task': {field: None for field in catalog['task']},
            'pages': [{'id': page['id'], 'intent': None, 'form': None, 'support': [],
                       'layout': None, 'density': None, 'behavior': None,
                       'assets': [{'route': None}], 'role': None} for page in outline['slides']]}


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError('Missing or unknown decision fields: ' + ', '.join(required))


def _text(value, field, limit=800):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Missing or oversized decision text: ' + field)


def _enum(value, choices, field):
    if not isinstance(value, str) or value not in choices:
        raise ValueError('Invalid choice for ' + field + '; select: ' + ', '.join(choices))


def _local_file(root, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('Asset file must be a task-relative path')
    path = Path(name)
    if path.is_absolute() or any(part in ('.', '..') for part in path.parts):
        raise ValueError('Asset file must stay inside the task')
    root = Path(root).resolve()
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Asset symlinks are not allowed')
    if not current.is_file() or not 0 < current.stat().st_size <= 30 * 1024 * 1024:
        raise ValueError('Selected asset is missing or exceeds the file limit')
    return current


def _page_evidence(data):
    """Follow actual presentation order and only relationships used on that page."""
    p = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    r = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    evidence = []
    hash_cache = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        presentation = ET.fromstring(archive.read('ppt/presentation.xml'))
        relationships = ET.fromstring(archive.read('ppt/_rels/presentation.xml.rels'))
        resolve = lambda parent, target: posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(parent, target))
        targets = {item.get('Id'): resolve('ppt', item.get('Target', ''))
                   for item in relationships if item.get('TargetMode') != 'External'}
        for slide in presentation.findall(f'{{{p}}}sldIdLst/{{{p}}}sldId'):
            name = targets[slide.get(f'{{{r}}}id')]
            tree = ET.fromstring(archive.read(name))
            used = {value for node in tree.iter() for key, value in node.attrib.items()
                    if key in (f'{{{r}}}embed', f'{{{r}}}id')}
            rel_name = posixpath.join(posixpath.dirname(name), '_rels', posixpath.basename(name) + '.rels')
            rels = ET.fromstring(archive.read(rel_name)) if rel_name in archive.namelist() else []
            hashes = set()
            playable = set()
            navigation = False
            for item in rels:
                if item.get('Id') not in used or item.get('TargetMode') == 'External':
                    continue
                target = resolve(posixpath.dirname(name), item.get('Target', ''))
                if target.startswith('ppt/media/'):
                    if target not in hash_cache:
                        body = archive.read(target)
                        hash_cache[target] = hashlib.sha256(body).hexdigest()
                    hashes.add(hash_cache[target])
                    if item.get('Type', '').endswith(('/audio', '/video', '/media')):
                        playable.add(hash_cache[target])
                    elif item.get('Type', '').endswith('/image'):
                        body = archive.read(target)
                        if body.startswith((b'GIF87a', b'GIF89a')):
                            from PIL import Image
                            try:
                                with Image.open(io.BytesIO(body)) as image:
                                    image.seek(1)  # Native animated GIF uses an image relationship.
                                playable.add(hash_cache[target])
                            except (OSError, EOFError, ValueError):
                                pass
                if item.get('Type', '').endswith('/slide'):
                    navigation = True
            timing = tree.find(f'{{{p}}}timing')
            reveal = timing is not None and any(node.get('evt') == 'onNext' for node in timing.iter(f'{{{p}}}cond')) and next(timing.iter(f'{{{p}}}spTgt'), None) is not None
            evidence.append({'assets': hashes, 'playable': playable, 'click_reveal': reveal, 'internal_navigation': navigation})
    return evidence


def validate_plan(plan, outline, *, stage='planning', root=None, artifact=None,
                  generation_enabled=True, search_enabled=True, mode='create', require_variation=None):
    catalog = load_catalog()
    if stage not in ('planning', 'authored'):
        raise ValueError('Unknown decision validation stage')
    # Historical execution records remain readable without mutating checkpoint bytes.
    if isinstance(plan, dict) and type(plan.get('version')) is int and plan['version'] == 1 and isinstance(plan.get('task'), dict):
        legacy = {'new_deck':'create','faithful_conversion':'create','redesign':'edit','scoped_edit':'edit'}
        if plan['task'].get('scope') not in legacy:
            raise ValueError('Unknown historical task route')
        plan = copy.deepcopy(plan)
        scope = plan['task'].pop('scope')
        plan['task']['operation'] = mode if scope == 'faithful_conversion' else legacy[scope]
        plan['task'].pop('inputs', None)
        plan['version'] = catalog['version']
    _keys(plan, ('version', 'task', 'pages'))
    if type(plan['version']) is not int or plan['version'] != catalog['version']:
        raise ValueError('Unsupported decision-plan version')
    task = plan['task']
    _keys(task, tuple(catalog['task']))
    for field, options in catalog['task'].items():
        _enum(task[field], options, 'task.' + field)
    if task['operation'] != mode:
        raise ValueError('Operation must match the existing create/edit task entry')
    if not search_enabled and (task['research'] != 'supplied_only' or task['references'] == 'targeted_search'):
        raise ValueError('Search is unavailable; select permitted supplied/available branches')
    if task['style'] == 'supplied_system' and task['references'] != 'preserve_supplied':
        raise ValueError('supplied_system must use preserve_supplied references')
    expected = [page['id'] for page in outline['slides']]
    pages = plan['pages']
    if not isinstance(pages, list) or len(pages) != len(expected):
        raise ValueError('Decision pages must cover the exact outline')
    if any(not isinstance(page, dict) for page in pages) or [page.get('id') for page in pages] != expected:
        raise ValueError('Decision page IDs/order must match the current outline')
    evidence = None
    if artifact is not None:
        data = artifact if isinstance(artifact, bytes) else Path(artifact).read_bytes()
        evidence = _page_evidence(data)
        if len(evidence) != len(pages):
            raise ValueError('Artifact page order/count differs from the decision plan')
    signatures = set()
    asset_hashes = {}
    for index, page in enumerate(pages):
        _keys(page, ('id', 'intent', 'form', 'support', 'layout', 'density', 'behavior', 'assets', 'role'))
        for field, options in catalog['page'].items():
            _enum(page[field], options, 'page.' + field)
        _text(page['role'], 'page.role')
        if page['form'] not in catalog['eligible_forms'][page['intent']]:
            raise ValueError('Primary form is outside the selected intent branch: ' + page['id'])
        support = page['support']
        if not isinstance(support, list) or len(support) > len(catalog['page']['form']):
            raise ValueError('support must be a list of form choices')
        for form in support:
            _enum(form, catalog['page']['form'], 'page.support')
        if len(set(support)) != len(support) or page['form'] in support:
            raise ValueError('Duplicate primary/support choices')
        assets = page['assets']
        if not isinstance(assets, list) or not assets or len(assets) > 32:
            raise ValueError('Select at least one asset route, including explicit none')
        routes = set()
        kinds = set()
        for asset in assets:
            _keys(asset, ('route',), ('kind', 'status', 'file', 'origin'))
            route = asset['route']
            _enum(route, catalog['asset']['route'], 'asset.route')
            routes.add(route)
            if route in ('none', 'source_grounded_native'):
                if set(asset) != {'route'}:
                    raise ValueError('Native/no-asset routes do not claim a downloaded file')
                continue
            _keys(asset, ('route', 'kind', 'status', 'file', 'origin'))
            _enum(asset['kind'], catalog['asset']['kind'], 'asset.kind')
            _enum(asset['status'], catalog['asset']['status'], 'asset.status')
            _text(asset['origin'], 'asset.origin', 4000)
            kinds.add(asset['kind'])
            if route == 'generate' and (not generation_enabled or asset['kind'] != 'illustrative'):
                raise ValueError('Generation requires an available tool and an illustrative role')
            if stage == 'authored' and asset['status'] != 'ready':
                raise ValueError('Selected asset is unresolved; execute or revise its branch')
            if asset['status'] == 'ready':
                if root is None:
                    raise ValueError('Asset validation requires the task directory')
                file = _local_file(root, asset['file'])
                if evidence is not None:
                    if file not in asset_hashes:
                        asset_hashes[file] = hashlib.sha256(file.read_bytes()).hexdigest()
                    digest = asset_hashes[file]
                    if digest not in evidence[index]['assets']:
                        raise ValueError('Selected asset bytes are not used on the planned page: ' + page['id'])
                    if asset['kind'] == 'media' and digest not in evidence[index]['playable']:
                        raise ValueError('Selected playback asset is only an image/unplayable relationship')
            elif asset['file'] is not None:
                raise ValueError('Unresolved assets must not claim a ready file')
        if 'none' in routes and len(assets) != 1:
            raise ValueError('none cannot be combined with other asset routes')
        forms = {page['form'], *support}
        for form, kind in [('documentary_image', 'documentary'), ('original_illustration', 'illustrative'), ('embedded_media', 'media')]:
            if form in forms and kind not in kinds:
                raise ValueError('Chosen form lacks its matching asset route: ' + form)
        if page['behavior'] == 'embedded_playback' and 'embedded_media' not in forms:
            raise ValueError('embedded_playback requires embedded_media')
        if evidence is not None and page['behavior'] in ('click_reveal', 'internal_navigation'):
            if not evidence[index][page['behavior']]:
                raise ValueError('Selected native behavior is missing on page: ' + page['id'])
        signatures.add((page['form'], page['layout']))
    variation = task['operation'] == 'create' and task['references'] != 'preserve_supplied' if require_variation is None else require_variation
    if variation and len(pages) > 1 and len(signatures) < 2:
        raise ValueError('New multi-page decks cannot select one form/layout throughout')
    return {'version': plan['version'], 'pages': len(pages), 'distinct_form_layouts': len(signatures),
            'stage': stage, 'embedded_assets_checked': evidence is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path('decision-plan.json'))
    parser.add_argument('--outline', type=Path, default=Path('outline.json'))
    parser.add_argument('--stage', choices=('planning', 'authored'), default='planning')
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--mode', choices=('create', 'edit'), help='Normally read from the existing task request')
    parser.add_argument('--template', action='store_true', help='Print an unselected scaffold using exact current page IDs')
    args = parser.parse_args()
    try:
        if args.template:
            print(json.dumps(plan_template(json.loads(args.outline.read_text())), ensure_ascii=False, indent=2))
            return
        if args.plan.stat().st_size > MAX_PLAN_BYTES:
            raise ValueError('Decision plan exceeds its size limit')
        plan = json.loads(args.plan.read_text())
        request = Path('request.json')
        task_mode = json.loads(request.read_text()).get('mode') if request.is_file() and request.stat().st_size <= MAX_PLAN_BYTES else None
        mode = args.mode or task_mode or plan.get('task', {}).get('operation') or 'create'
        result = validate_plan(plan, json.loads(args.outline.read_text()),
                               stage=args.stage, root=Path.cwd(), artifact=args.artifact, mode=mode)
        print(json.dumps({'ok': True, **result}))
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
