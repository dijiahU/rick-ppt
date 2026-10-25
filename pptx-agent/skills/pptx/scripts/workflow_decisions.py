"""Validate delivery decisions, page coverage, provenance and selected embedded bytes.

This validates routing records, not aesthetics or whether a source is trustworthy.
It never executes instructions from a presentation or modifies a deck.
"""
import argparse
import copy
import hashlib
import io
import importlib.util
import json
import re
from pathlib import Path
import posixpath
from xml.etree import ElementTree as ET
import zipfile
from urllib.parse import urlsplit

CATALOG = Path(__file__).resolve().parents[1] / 'assets/workflow-choices.json'
MAX_PLAN_BYTES = 512 * 1024


def _load_timing_reader():
    # Resolve beside this immutable plugin, never through host sys.path or an
    # installed legacy native_builds/native_timing module of the same name.
    path=Path(__file__).with_name('native_timing.py')
    spec=importlib.util.spec_from_file_location('_pptx_decision_native_timing',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.appear_steps


_appear_steps=_load_timing_reader()


def load_catalog(version=None):
    path = CATALOG.with_name('workflow-choices-v3.json') if version == 3 else CATALOG
    catalog = json.loads(path.read_text())
    if catalog['version'] >= 4:
        return catalog
    if set(catalog['eligible_forms']) != set(catalog['page']['intent']):
        raise ValueError('Catalog intent branches are incomplete')
    for options in catalog['eligible_forms'].values():
        if not options or len(options) != len(set(options)) or set(options) - set(catalog['page']['form']):
            raise ValueError('Catalog has invalid eligible forms')
    return catalog


def plan_template(outline):
    catalog = load_catalog()
    return {'version': catalog['version'], 'task': {field: None for field in catalog['task']},
            'template_preservation': [], 'design_direction': None, 'references': [],
            'pages': [{'id': page['id'], 'behavior': None,
                       'assets': [{'route': None}]} for page in outline['slides']]}


def page_reference_ids(plan, page):
    """v4 records applications once; page IDs and note contents are derived."""
    if plan.get('version') == 4:
        return [entry['id'] for entry in plan['references']
                if any(page['id'] in app['pages'] for app in entry['applications'])]
    return page.get('reference_ids', [])


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


def _historical_plan(plan, mode):
    """Retain historical meaning and bytes; no invented artistic provenance."""
    plan = copy.deepcopy(plan)
    if plan['version'] == 1:
        legacy = {'new_deck':'create','faithful_conversion':'create','redesign':'edit','scoped_edit':'edit'}
        scope = plan['task'].pop('scope')
        if scope not in legacy:raise ValueError('Unknown historical task route')
        plan['task']['operation'] = mode if scope == 'faithful_conversion' else legacy[scope]
        plan['task'].pop('inputs', None)
    for page in plan['pages']:
        form = page['form'];layout = page.pop('layout')
        page.pop('density')
        page['strategy'] = ('observe' if form in ('documentary_image','embedded_media') else
                            'envision' if form == 'original_illustration' else
                            'compare' if form in ('table','data_chart') else
                            'relate' if form == 'diagram' else 'read')
        page['composition'] = ('image_with_type' if form in ('documentary_image','original_illustration','embedded_media') else
                               'data_display' if form in ('table','data_chart') else
                               'relational_map' if form == 'diagram' else
                               'sequence' if layout == 'sequence' else 'editorial' if layout != 'focus' else 'type_statement')
        page['visual_action'] = 'Historical record: inspect the actual existing composition; no new design claim.'
        page['reference_ids'] = []
    plan.update(version=3, design_direction='Historical execution; preserve its verified artifact and editing scope.',references=[])
    return plan


def _references(plan, expected, root, catalog):
    _text(plan['design_direction'], 'design_direction', 2400)
    entries = plan['references']
    if not isinstance(entries,list) or len(entries)>64:raise ValueError('Invalid design reference register')
    lookup={}
    for entry in entries:
        _keys(entry, ('id','kind','title','creator','source','inspection','evidence','observed','borrowed','applications'))
        ident=entry['id']
        if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',ident) or ident in lookup:
            raise ValueError('Missing, duplicate or unsafe reference ID')
        _enum(entry['kind'],catalog['reference']['kind'],'reference.kind')
        _enum(entry['inspection'],catalog['reference']['inspection'],'reference.inspection')
        for field in ('title','creator','source','observed'):_text(entry[field],'reference.'+field,4000)
        source=entry['source']
        if '://' in source:
            u=urlsplit(source)
            if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or any(ord(c)<33 for c in source):
                raise ValueError('Reference source must be a credential-free HTTPS page or task-local file')
        elif root is None:raise ValueError('Local reference source requires the task directory')
        else:_local_file(root,source)
        inspection=entry['inspection']
        if inspection=='local_image':
            if root is None:raise ValueError('Visual inspection evidence requires the task directory')
            image=_local_file(root,entry['evidence'])
            from PIL import Image
            with Image.open(image) as opened:opened.verify()
        elif inspection!='unavailable':_text(entry['evidence'],'reference.evidence',4000)
        elif entry['evidence'] is not None:raise ValueError('Unavailable references cannot claim inspected evidence')
        apps=entry['applications']
        if not isinstance(apps,list) or len(apps)>len(expected):raise ValueError('Invalid reference applications')
        if inspection=='unavailable' and (entry['borrowed'] is not None or apps):
            raise ValueError('Unavailable work cannot claim borrowed ideas or page applications')
        if apps:
            if entry['kind'] in ('artwork','design_work') and inspection not in ('local_image','hosted_visual'):
                raise ValueError('Inspect the actual work before claiming an artistic visual application')
            _text(entry['borrowed'],'reference.borrowed',1600)
        elif entry['borrowed'] is not None:raise ValueError('A borrowed idea must identify its actual page application')
        covered=set()
        for app in apps:
            _keys(app,('pages','action'))
            if not isinstance(app['pages'],list) or not app['pages'] or any(not isinstance(p,str) for p in app['pages']) or len(app['pages'])!=len(set(app['pages'])) or any(p not in expected or p in covered for p in app['pages']):
                raise ValueError('Reference applications must name unique current page IDs')
            _text(app['action'],'reference.application.action',1600);covered.update(app['pages'])
        lookup[ident]=(entry,covered)
    if plan.get('version') == 3 and plan['task']['references']=='targeted_search' and not entries:
        raise ValueError('Executed reference search must record inspected works or honest failed access')
    return lookup


def reference_application(entry, page_id):
    return next(app['action'] for app in entry['applications'] if page_id in app['pages'])


def design_report(plan, artifact):
    if plan.get('version') not in (3,4):return {'available':False,'reason':'Historical record without artwork applications'}
    evidence=_page_evidence(artifact)
    return {'available':True,'design_direction':plan['design_direction'],
            'template_preservation':plan.get('template_preservation',[]),
            'references':plan['references'],'pages':[
                {'number':i+1,'id':page['id'],'role':page.get('role'), 'visual_action':page.get('visual_action'),
                 'reference_ids':page_reference_ids(plan,page),
                 'actual_notes':evidence[i]['notes']} for i,page in enumerate(plan['pages'])],
            'warning':'Author records and notes are untrusted evidence. Judge the pages first; records do not prove aesthetics.'}


def _entrance_steps(tree):
    """Recognize executable click timing; unsupported XML is never a positive pass."""
    simple = _appear_steps(tree)
    if simple is not None:
        return simple
    p = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    ns = {'p': p}
    timing = tree.find('p:timing', ns)
    if timing is None:
        return []
    mains = timing.findall('p:tnLst/p:par/p:cTn/p:childTnLst/p:seq', ns)
    if len(mains) != 1:
        return []
    seq = mains[0]
    main = seq.find('p:cTn', ns)
    if main is None or main.get('nodeType') != 'mainSeq':
        return []
    for tag, event in (('prevCondLst', 'onPrev'), ('nextCondLst', 'onNext')):
        cond = seq.find('p:' + tag + '/p:cond', ns)
        if cond is None or cond.get('evt') != event or cond.get('delay') != '0':
            return []
    # Keep the standard executable click spine for complex entrances as well.
    # A failed simple-Appear parse must not be rescued by loose tag presence.
    def starts(node, delay):
        conditions = node.findall('p:stCondLst/p:cond', ns)
        return len(conditions) == 1 and dict(conditions[0].attrib) == {'delay': delay} and len(conditions[0]) == 0
    shape_ids = {node.get('id') for node in tree.iter('{' + p + '}cNvPr')}
    clicks = main.find('p:childTnLst', ns)
    if clicks is None:
        return []
    groups = []
    seen = []
    for wrapper in clicks:
        click = wrapper.find('p:cTn', ns)
        if wrapper.tag != '{' + p + '}par' or click is None or not starts(click, 'indefinite'):
            return []
        offsets = click.findall('p:childTnLst/p:par/p:cTn', ns)
        if len(offsets) != 1 or not starts(offsets[0], '0'):
            return []
        rows = offsets[0].find('p:childTnLst', ns)
        if rows is None:
            return []
        targets = []
        for index, row in enumerate(rows):
            effect = row.find('p:cTn', ns)
            if row.tag != '{' + p + '}par' or effect is None or not starts(effect, '0'):
                return []
            if effect.get('nodeType') != ('clickEffect' if index == 0 else 'withEffect') or effect.get('presetClass') != 'entr':
                return []
            seen.append(effect)
            ids = {node.get('spid') for node in effect.iter('{' + p + '}spTgt')}
            actions = [n for n in effect.iter() if n.tag in {
                '{' + p + '}' + k for k in ('set', 'anim', 'animEffect', 'animMotion', 'animScale', 'animRot')}]
            if len(ids) != 1 or not ids <= shape_ids or not actions:
                return []
            # Preset 1 with only set behavior is simple Appear. If its strict
            # reader rejected it, it is not a valid generic entrance alternative.
            if effect.get('presetID') == '1' and all(action.tag == '{' + p + '}set' for action in actions):
                return []
            for action in actions:
                behavior = action.find('p:cBhvr', ns)
                if behavior is None or behavior.find('p:cTn', ns) is None or behavior.find('p:tgtEl/p:spTgt', ns) is None:
                    return []
                if action.tag == '{' + p + '}set':
                    names = behavior.findall('p:attrNameLst/p:attrName', ns)
                    value = action.find('p:to/p:strVal', ns)
                    if not names or action.find('p:to', ns) is None:
                        return []
                    if any(name.text == 'style.visibility' for name in names) and (value is None or value.get('val') != 'visible'):
                        return []
            targets.extend(sorted(ids))
        if targets:
            groups.append(targets)
    all_effects = [n for n in timing.iter('{' + p + '}cTn') if n.get('nodeType') in ('clickEffect','withEffect','afterEffect')]
    ids = [ident for group in groups for ident in group]
    if all_effects != seen or len(ids) != len(set(ids)):
        return []
    return groups



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
            notes = ''
            for item in rels:
                if item.get('Type','').endswith('/notesSlide') and item.get('TargetMode')!='External':
                    note_part=resolve(posixpath.dirname(name),item.get('Target',''))
                    note_tree=ET.fromstring(archive.read(note_part))
                    notes=' '.join(node.text or '' for node in note_tree.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'))
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
            # Inherited visible pictures/backgrounds are real page assets too.
            # Follow only the layout/master chain, never unrelated package media.
            inherited_seen = set()
            master_visible = tree.get('showMasterSp', '1') not in ('0', 'false')
            has_background = tree.find(f'{{{p}}}cSld/{{{p}}}bg') is not None
            def inherit(part, relation_type, include_master):
                nonlocal has_background
                if part in inherited_seen:
                    return
                inherited_seen.add(part)
                node = ET.fromstring(archive.read(part))
                rp = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
                relations = ET.fromstring(archive.read(rp)) if rp in archive.namelist() else []
                roots = []
                if relation_type == 'slideLayout' or include_master:
                    shapes = node.find(f'{{{p}}}cSld/{{{p}}}spTree')
                    if shapes is not None:
                        roots.append(shapes)
                background = node.find(f'{{{p}}}cSld/{{{p}}}bg')
                if not has_background and background is not None:
                    roots.append(background)
                    has_background = True
                used_ids = {value for root in roots for item in root.iter() for key, value in item.attrib.items()
                            if key in (f'{{{r}}}embed', f'{{{r}}}id')}
                for relation in relations:
                    if relation.get('TargetMode') == 'External':
                        continue
                    target = resolve(posixpath.dirname(part), relation.get('Target', ''))
                    if relation.get('Id') in used_ids and target.startswith('ppt/media/'):
                        if target not in hash_cache:
                            hash_cache[target] = hashlib.sha256(archive.read(target)).hexdigest()
                        hashes.add(hash_cache[target])
                    if relation.get('Type', '').endswith('/slideMaster'):
                        inherit(target, 'slideMaster', include_master and node.get('showMasterSp', '1') not in ('0', 'false'))
            for relation in rels:
                if relation.get('TargetMode') != 'External' and relation.get('Type', '').endswith('/slideLayout'):
                    inherit(resolve(posixpath.dirname(name), relation.get('Target', '')), 'slideLayout', master_visible)
            reveal_steps = _entrance_steps(tree)
            evidence.append({'assets': hashes, 'playable': playable, 'click_reveal': bool(reveal_steps), 'reveal_steps':reveal_steps,'internal_navigation': navigation,'notes':notes})
    return evidence


def validate_plan(plan, outline, *, stage='planning', root=None, artifact=None,
                  generation_enabled=True, search_enabled=True, mode='create', require_variation=None, allow_legacy=True, require_click_reveal=None):
    current = load_catalog()
    if stage not in ('planning', 'authored'):
        raise ValueError('Unknown decision validation stage')
    version = plan.get('version') if isinstance(plan, dict) else None
    if type(version) is not int or version not in (1, 2, 3, current['version']):
        raise ValueError('Unsupported decision-plan version')
    legacy = version < current['version']
    if legacy and not allow_legacy:
        raise ValueError('New tasks require the current delivery contract; preserve historical contracts only on recovery')
    if version in (1, 2):
        plan = _historical_plan(plan, mode)
    free_design = plan['version'] >= 4
    catalog = current if free_design else load_catalog(3)
    _keys(plan, ('version', 'task', 'pages', 'design_direction', 'references'),
          ('template_preservation',) if free_design else ())
    if free_design:
        preservation = plan.get('template_preservation')
        if not isinstance(preservation, list) or len(preservation) > 64:
            raise ValueError('Record template_preservation as the actual protected elements, or [] without a template')
        for item in preservation:
            _text(item, 'template_preservation', 1600)
    task = plan['task']
    _keys(task, tuple(catalog['task']))
    for field, options in catalog['task'].items():
        _enum(task[field], options, 'task.' + field)
    if task['operation'] != mode:
        raise ValueError('Operation must match the existing create/edit task entry')
    if require_click_reveal is None:
        require_click_reveal = bool(current.get('requirements', {}).get('new_deck_click_reveal')) and not legacy
    require_click_reveal = bool(require_click_reveal) and mode == 'create' and require_variation is not False
    if not search_enabled and (task['research'] != 'supplied_only' or task.get('references') == 'targeted_search'):
        raise ValueError('Search is unavailable; select permitted supplied/available branches')
    if not free_design and task['style'] == 'supplied_system' and task['references'] != 'preserve_supplied':
        raise ValueError('Historical supplied_system must use preserve_supplied references')
    expected = [page['id'] for page in outline['slides']]
    pages = plan['pages']
    if not isinstance(pages, list) or len(pages) != len(expected):
        raise ValueError('Decision pages must cover the exact outline')
    if any(not isinstance(page, dict) for page in pages) or [page.get('id') for page in pages] != expected:
        raise ValueError('Decision page IDs/order must match the current outline')
    references=_references(plan,expected,root,catalog)
    evidence = None
    if artifact is not None:
        data = artifact if isinstance(artifact, bytes) else Path(artifact).read_bytes()
        evidence = _page_evidence(data)
        if len(evidence) != len(pages):
            raise ValueError('Artifact page order/count differs from the decision plan')
    signatures = set()
    asset_hashes = {}
    for index, page in enumerate(pages):
        if free_design:
            _keys(page, ('id', 'behavior', 'assets'),
                  ('role', 'visual_action', 'intent', 'strategy', 'form', 'support', 'composition', 'reference_ids'))
            _enum(page['behavior'], catalog['page']['behavior'], 'page.behavior')
            for field in ('role', 'visual_action', 'intent', 'strategy', 'form', 'composition'):
                if field in page:
                    _text(page[field], 'page.' + field, 1600)
            if 'support' in page:
                if not isinstance(page['support'], list) or len(page['support']) > 32:
                    raise ValueError('Optional support must be a list of descriptions')
                for item in page['support']:
                    _text(item, 'page.support', 1600)
        else:
            _keys(page, ('id', 'intent', 'strategy','form', 'support', 'composition', 'behavior', 'assets', 'role','visual_action','reference_ids'))
            for field, options in catalog['page'].items():
                _enum(page[field], options, 'page.' + field)
            _text(page['role'], 'page.role')
            _text(page['visual_action'], 'page.visual_action', 1600)
        ids = page_reference_ids(plan, page)
        if 'reference_ids' in page and page['reference_ids'] != ids:
            raise ValueError('Optional page reference IDs must agree with the reference applications')
        if not isinstance(ids, list) or any(not isinstance(ident, str) for ident in ids) or len(ids) != len(set(ids)):
            raise ValueError('Page reference IDs must be a unique list')
        for ident in ids:
            if ident not in references or page['id'] not in references[ident][1]:
                raise ValueError('Page reference lacks an inspected work and matching application: ' + page['id'])
            if evidence is not None:
                entry = references[ident][0]; notes = ' '.join(evidence[index]['notes'].split())
                for value in (ident, entry['title'], entry['creator'], entry['source'], entry['observed'], entry['borrowed'], reference_application(entry, page['id'])):
                    if ' '.join(value.split()) not in notes:
                        raise ValueError('Final slide notes must record artwork, creator, source, observation, borrowed principle and application: ' + page['id'])
        support = page.get('support', [])
        if not free_design:
            if page['form'] not in catalog['eligible_forms'][page['intent']]:
                raise ValueError('Primary form is outside the selected intent branch: ' + page['id'])
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
        forms = {page.get('form'), *support}
        file_routes=routes & {'supplied','web_import','generate'}
        if not free_design and page['composition'] in ('image_field','image_with_type','annotated_visual') and not file_routes:
            raise ValueError('Chosen image composition needs an actual file asset')
        if not free_design and page['strategy']=='observe' and not ({'documentary_image','embedded_media'} & forms) and task['references']!='preserve_supplied':
            raise ValueError('Object/state observation requires real visual evidence, not an invented illustration or prose map')
        for form, kind in [('documentary_image', 'documentary'), ('original_illustration', 'illustrative'), ('embedded_media', 'media')]:
            if not free_design and form in forms and kind not in kinds:
                raise ValueError('Chosen form lacks its matching asset route: ' + form)
        if page['behavior'] == 'embedded_playback' and 'media' not in kinds:
            raise ValueError('embedded_playback requires an actual media asset')
        if evidence is not None and page['behavior'] in ('click_reveal', 'internal_navigation'):
            if not evidence[index][page['behavior']]:
                raise ValueError('Selected native behavior is missing on page: ' + page['id'])
        if not free_design:
            signatures.add((page['form'], page['composition']))
    if require_click_reveal and not any(page.get('behavior')=='click_reveal' for page in pages):
        raise ValueError('New presentations require content-led native click reveals; an entirely static deck cannot be delivered')
    for ident,(_,covered) in references.items():
        if {page['id'] for page in pages if ident in page_reference_ids(plan,page)}!=covered:
            raise ValueError('Reference applications and actual page reference IDs disagree: '+ident)
    variation = task['operation'] == 'create' and task.get('references') != 'preserve_supplied' if require_variation is None else require_variation
    if not free_design and variation and len(pages) > 1 and len(signatures) < 2:
        raise ValueError('New multi-page decks cannot select one form/composition throughout')
    return {'version': plan['version'], 'pages': len(pages), 'distinct_form_layouts': None if free_design else len(signatures),
            'stage': stage, 'embedded_assets_checked': evidence is not None,'legacy_record':legacy,
            'references_recorded':len(references),'artistic_transfer_requires_visual_review':True,'click_reveal_required':require_click_reveal}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path('decision-plan.json'))
    parser.add_argument('--outline', type=Path, default=Path('outline.json'))
    parser.add_argument('--stage', choices=('planning', 'authored'), default='planning')
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--mode', choices=('create', 'edit'), help='Normally read from the existing task request')
    parser.add_argument('--template', action='store_true', help='Print an unselected scaffold using exact current page IDs')
    parser.add_argument('--allow-legacy',action='store_true',help='Read historical records without inventing artistic provenance')
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
                               stage=args.stage, root=Path.cwd(), artifact=args.artifact, mode=mode,allow_legacy=args.allow_legacy,
                               require_click_reveal=False if args.allow_legacy else None)
        print(json.dumps({'ok': True, **result}))
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
