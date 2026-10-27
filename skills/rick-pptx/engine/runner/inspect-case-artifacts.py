#!/usr/bin/env python3
"""Read-only structural/evidence inspection; never execute delivered bundle code.

Exit 0 means the declared structural requirements and evidence links were checked,
not that lesson content, appearance, browser execution or Office playback passed.
Exit 2 means invalid inputs/structure; exit 3 means incomplete case evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import stat
import sys
import unicodedata
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

PLUGIN = Path(__file__).resolve().parents[1] / 'pptx-agent'
sys.path.insert(0, str(PLUGIN / 'skills/pptx/scripts'))
from pptx_core.common import NS, PptxError, parse
from pptx_core.interactive_ooxml import discover_content_addins
from pptx_core.interactive_validate import config, validate_bundle_manifest
from pptx_core.relationships import slide_parts
from pptx_core.validator import validate

MAX_FILES = 50000
MAX_ARCHIVE_BYTES = 2 * 1024**3
MAX_FILE_BYTES = 512 * 1024**2
MAX_JSON_BYTES = 8 * 1024**2
MAX_PNG_BYTES = 30 * 1024**2
MAX_PIXELS = 20000000
MAX_EVIDENCE_BYTES = 2 * 1024**3
MAX_SAMPLED_BYTES = 512 * 1024**2
CHUNK = 1024**2
HEX = re.compile(r'^[a-f0-9]{64}$')
ID = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,95}$')
TEST_ACTIONS = {'click', 'hover', 'input', 'slider', 'select', 'toggle', 'keyboard',
                'key', 'drag', 'pan', 'wheel', 'seekTimeline', 'dispatch', 'resize',
                'wait', 'snapshot', 'restore', 'media'}
TARGET_ACTIONS = {'click', 'hover', 'input', 'slider', 'select', 'toggle', 'drag', 'pan', 'wheel', 'media'}
ASSERTION_FIELDS = {'state': ('path',), 'dataCount': ('source',),
                    'timeline': ('timeline', 'property'), 'visible': ('target',),
                    'text': ('target',), 'attribute': ('target', 'name'),
                    'property': ('target', 'name')}
CONTROL_TYPES = {'Button', 'Input', 'Textarea', 'Slider', 'Select', 'Toggle', 'FileInput'}
CONTROL_COMPONENTS = {'tabs', 'stepper', 'accordion', 'carousel', 'beforeAfter', 'timelineControls'}


class InspectionError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise InspectionError(message)


def safe_relative(name):
    need(isinstance(name, str) and bool(name), 'Empty/non-string relative path')
    need(not PurePosixPath(name).is_absolute() and unquote(name) == name,
         'Absolute/encoded archive path')
    need(not any(c in name for c in ('\\', ':')) and
         not any(ord(c) < 32 or ord(c) == 127 for c in name), 'Unsafe archive path character')
    for part in name.split('/'):
        need(part not in ('', '.', '..') and part.rstrip(' .') == part, 'Unsafe archive path component')
        need(not re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part),
             'Non-portable reserved archive path')
    return name


def local_path(value, *, directory=False):
    path = Path(os.path.abspath(value))
    for part in (path, *path.parents):
        need(not part.is_symlink(), f'Symlink input/ancestor is not permitted: {part}')
    need(path.is_dir() if directory else path.is_file(), f'Missing input: {path}')
    if not directory:
        need(stat.S_ISREG(path.stat().st_mode), f'Input must be a regular file: {path}')
    return path


def fresh_proof(value):
    path = Path(os.path.abspath(value))
    need(not path.exists() and not path.is_symlink(), 'Proof path already exists; choose a new directory')
    for ancestor in path.parents:
        need(not ancestor.is_symlink(), 'Proof ancestor may not be a symlink')
    need(path.parent.is_dir(), 'Proof parent must already exist')
    path.mkdir(mode=0o700)  # Never replace or clean an earlier proof.
    return path


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def hash_file(path, limit=MAX_ARCHIVE_BYTES):
    path = local_path(path)
    need(path.stat().st_size <= limit, f'Oversized input: {path.name}')
    digest = hashlib.sha256()
    total = 0
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(CHUNK), b''):
            total += len(chunk)
            need(total <= limit, 'Input grew beyond size limit')
            digest.update(chunk)
    return digest.hexdigest()


def json_data(data):
    need(len(data) <= MAX_JSON_BYTES, 'JSON file exceeds 8 MiB')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result and key not in {'__proto__', 'prototype', 'constructor'},
                 'Duplicate/forbidden JSON key')
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(InspectionError('Nonfinite JSON')))
        def depth(item, level=0):
            need(level <= 48, 'JSON nesting limit exceeded')
            if isinstance(item, dict):
                for child in item.values(): depth(child, level + 1)
            elif isinstance(item, list):
                need(len(item) <= MAX_FILES, 'JSON array limit exceeded')
                for child in item: depth(child, level + 1)
        depth(value)
        return value
    except (ValueError, RecursionError, UnicodeError) as error:
        raise InspectionError(f'Invalid JSON: {error}') from error


def read_json(path):
    path = local_path(path)
    need(path.stat().st_size <= MAX_JSON_BYTES, 'JSON file exceeds 8 MiB')
    with path.open('rb') as source:
        return json_data(source.read(MAX_JSON_BYTES + 1))


def write_json(path, value):
    with path.open('x', encoding='utf-8') as target:
        json.dump(value, target, indent=2, ensure_ascii=False, allow_nan=False)
        target.write('\n')


class SafeArchive:
    """Validate the whole ZIP namespace before reading or extracting any member."""
    def __init__(self, path):
        self.path = local_path(path)
        need(self.path.stat().st_size <= MAX_ARCHIVE_BYTES, 'ZIP exceeds input size limit')
        self.archive = zipfile.ZipFile(self.path)
        self.files = {}
        try:
            infos = self.archive.infolist()
            need(0 < len(infos) <= MAX_FILES, 'ZIP entry count outside bounds')
            seen = set()
            total = 0
            for info in infos:
                raw = info.filename
                need(info.orig_filename == raw, 'Ambiguous/truncated ZIP member name')
                name = safe_relative(raw[:-1] if info.is_dir() else raw)
                key = unicodedata.normalize('NFC', name).casefold()
                need(key not in seen, 'Duplicate/case/Unicode-colliding ZIP member')
                seen.add(key)
                mode = stat.S_IFMT(info.external_attr >> 16)
                need(mode in (0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG),
                     'ZIP symlink/device/nonregular member is forbidden')
                need(not info.flag_bits & 1, 'Encrypted ZIP member is forbidden')
                need(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                     'Unsupported ZIP compression')
                need(0 <= info.file_size <= MAX_FILE_BYTES, 'ZIP member exceeds size limit')
                total += info.file_size
                need(total <= MAX_ARCHIVE_BYTES, 'ZIP expansion exceeds 2 GiB')
                if not info.is_dir(): self.files[name] = info
            files_folded = {unicodedata.normalize('NFC', name).casefold() for name in self.files}
            for name in seen:
                for parent in PurePosixPath(name).parents:
                    need(str(parent) not in files_folded, 'ZIP file/directory path conflict')
        except Exception:
            self.archive.close()
            raise

    def close(self):
        self.archive.close()

    def read(self, name, limit=MAX_JSON_BYTES):
        need(name in self.files, f'Missing ZIP member: {name}')
        need(self.files[name].file_size <= limit, f'Oversized member: {name}')
        with self.archive.open(self.files[name]) as source:
            data = source.read(limit + 1)
        need(len(data) <= limit, 'ZIP member exceeded declared limit')
        return data

    def digest(self, name):
        digest = hashlib.sha256()
        total = 0
        with self.archive.open(self.files[name]) as source:
            for chunk in iter(lambda: source.read(CHUNK), b''):
                total += len(chunk)
                need(total <= self.files[name].file_size, 'ZIP member exceeded declared size')
                digest.update(chunk)
        need(total == self.files[name].file_size, 'Truncated ZIP member')
        return digest.hexdigest()

    def copy(self, name, destination):
        need(not destination.exists(), 'Refusing to overwrite a proof file')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.archive.open(self.files[name]) as source, destination.open('xb') as target:
            total = 0
            for chunk in iter(lambda: source.read(CHUNK), b''):
                total += len(chunk)
                need(total <= self.files[name].file_size, 'ZIP extraction exceeded declared size')
                target.write(chunk)
        need(total == self.files[name].file_size, 'Truncated ZIP member')


def identical_member(archive, member, path):
    if archive.files[member].file_size != path.stat().st_size:
        return False
    with archive.archive.open(archive.files[member]) as zipped, path.open('rb') as delivered:
        while True:
            left, right = zipped.read(CHUNK), delivered.read(CHUNK)
            if left != right: return False
            if not left: return True


def verified_bundle(path, pptx, proof):
    archive = SafeArchive(path)
    try:
        candidates = [name for name in archive.files if name == 'checksums.json' or
                      (name.count('/') == 1 and name.endswith('/checksums.json'))]
        need(len(candidates) == 1, 'Expected one bundle checksum manifest at root or one enclosing directory')
        checksum_path = candidates[0]
        prefix = checksum_path[:-len('checksums.json')]
        need(all(name.startswith(prefix) for name in archive.files), 'ZIP contains files outside the bundle root')
        names = {name[len(prefix):]: name for name in archive.files}
        checksums = json_data(archive.read(checksum_path))
        need(isinstance(checksums, dict) and checksums, 'Checksum manifest must be a nonempty object')
        for name, value in checksums.items():
            safe_relative(name)
            need(isinstance(value, str) and HEX.fullmatch(value), 'Invalid checksum digest')
        need(set(checksums) == set(names) - {'checksums.json'}, 'Checksum manifest does not cover the exact ZIP file inventory')
        for name, expected in checksums.items():
            need(archive.digest(names[name]) == expected, f'Checksum mismatch: {name}')
        need('presentation.pptx' in names, 'Bundle is missing presentation.pptx')
        need(identical_member(archive, names['presentation.pptx'], pptx),
             'Delivered PPTX bytes differ from ZIP presentation.pptx')
        need('runtime/dist/preview.html' in names and 'runtime/config.json' in names,
             'Bundle is missing its runtime preview/configuration')
        deck = proof / 'bundle-deck'
        for name in names:
            if name.startswith('deck/'):
                archive.copy(names[name], deck / name[5:])
        bundle = read_json(deck / 'bundle.json')
        validate_bundle_manifest(bundle, deck)
        need(bundle['pptxHash'] == checksums['presentation.pptx'], 'Deck manifest PPTX hash differs from bytes')
        need(bundle['addinId'] == config()['addinId'], 'Bundle uses an unexpected add-in identity')
        runtime_files = {name[len('runtime/dist/'):]: value for name, value in checksums.items()
                         if name.startswith('runtime/dist/')}
        fingerprint = {'sha256': hash_bytes(json.dumps(runtime_files, sort_keys=True, separators=(',', ':')).encode()),
                       'files': len(runtime_files), 'configuration': checksums['runtime/config.json']}
        cfg = json_data(archive.read(names['runtime/config.json']))
        need(isinstance(cfg, dict), 'Runtime configuration must be an object')
        need(cfg.get('addinId') == bundle['addinId'] and cfg.get('runtimeVersion') == bundle['runtimeVersion'],
             'Runtime configuration differs from bundle identity/version')
        write_json(proof / 'verified-checksums.json', checksums)
        return bundle, deck, {'files': len(checksums), 'pptxBytesExactlyEqual': True,
                             'presentationSha256': checksums['presentation.pptx'],
                             'runtimeFingerprint': fingerprint, 'zipRoot': prefix}, set(names)
    finally:
        archive.close()


def png_info(data):
    from PIL import Image
    need(len(data) <= MAX_PNG_BYTES, 'PNG exceeds 30 MiB')
    try:
        with Image.open(io.BytesIO(data)) as image:
            need(image.format == 'PNG' and 0 < image.width * image.height <= MAX_PIXELS,
                 'Capture must be PNG with at most 20 million pixels')
            size = {'width': image.width, 'height': image.height}
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()  # Validate bounded pixel decoding, not only PNG chunk CRCs.
    except Image.DecompressionBombError as error:
        raise InspectionError('PNG exceeds pixel limit') from error
    return size


def read_png(path):
    path = local_path(path)
    need(path.stat().st_size <= MAX_PNG_BYTES, 'PNG exceeds 30 MiB')
    with path.open('rb') as source: data = source.read(MAX_PNG_BYTES + 1)
    return data, png_info(data)


def native_inventory(pptx, bundle, proof, expected_pages):
    archive = SafeArchive(pptx)
    package = proof / 'native-package'
    try:
        for name in archive.files:
            archive.copy(name, package / name)
    finally:
        archive.close()
    native_validation = validate(package)
    need(native_validation.ok, 'Native package structural errors: ' + '; '.join(native_validation.errors))
    parts = slide_parts(package)
    need(len(parts) == expected_pages, f'Expected {expected_pages} slides; found {len(parts)}')
    instances = discover_content_addins(package)
    need(bool(instances), 'PPTX contains no Content Add-in instances')
    expected = {item.get('instanceId'): item for item in bundle['slides']}
    need(None not in expected and len(expected) == len(bundle['slides']), 'Invalid/duplicate manifest instance identity')
    need(set(expected) == {item.get('instanceId') for item in instances}, 'Manifest and PPTX instance inventories differ')
    fallback_bytes = 0
    for item in instances:
        for key in ('slide', 'part', 'shapeId', 'bounds', 'instanceId', 'addinId', 'deckId', 'sceneId', 'schemaVersion', 'specHash', 'snapshot'):
            need(json.dumps(item.get(key), sort_keys=True) == json.dumps(expected[item['instanceId']].get(key), sort_keys=True),
                 f'OOXML/manifest mismatch: {key}')
        scene = bundle['scenes'].get(item.get('sceneId'), {})
        need(item['addinId'] == bundle['addinId'] and item['deckId'] == bundle['deckId'] and
             item['specHash'] == scene.get('sha256'), 'OOXML/scene identity or hash mismatch')
        data, dimensions = read_png(package / safe_relative(item['snapshot']))
        digest = hash_bytes(data)
        target = proof / 'fallbacks' / f'{digest}.png'
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            fallback_bytes += len(data)
            need(fallback_bytes <= MAX_SAMPLED_BYTES, 'Copied native fallback proof exceeds 512 MiB limit')
            target.write_bytes(data)
        item['inspectedFallback'] = {'sha256': digest, **dimensions, 'proofFile': target.relative_to(proof).as_posix()}
    need({item['sceneId'] for item in instances} == set(bundle['scenes']), 'An advertised scene has no PPTX Content Add-in')
    slides = []
    for number, part in enumerate(parts, 1):
        tree = parse(package / part)
        texts = []
        for shape in tree.findall('.//p:sp', NS):
            if shape.find('p:txBody', NS) is None: continue
            paragraphs = [''.join(par.xpath('.//a:t/text()', namespaces=NS)) for par in shape.findall('p:txBody/a:p', NS)]
            text = '\n'.join(paragraphs).strip()
            if not text: continue
            props = shape.find('p:nvSpPr/p:cNvPr', NS)
            placeholder = shape.find('p:nvSpPr/p:nvPr/p:ph', NS)
            off, ext = shape.find('p:spPr/a:xfrm/a:off', NS), shape.find('p:spPr/a:xfrm/a:ext', NS)
            bounds = None
            if off is not None and ext is not None and not shape.xpath('ancestor::p:grpSp', namespaces=NS):
                bounds = {'x': int(off.get('x', 0)), 'y': int(off.get('y', 0)),
                          'width': int(ext.get('cx', 0)), 'height': int(ext.get('cy', 0))}
            def overlaps(rect):
                return (bounds['x'] < rect['x'] + rect['width'] and bounds['x'] + bounds['width'] > rect['x'] and
                        bounds['y'] < rect['y'] + rect['height'] and bounds['y'] + bounds['height'] > rect['y'])
            outside = bounds is not None and not any(overlaps(item['bounds']) for item in instances if item['slide'] == number)
            texts.append({'shapeId': props.get('id') if props is not None else None,
                          'name': props.get('name') if props is not None else None,
                          'placeholder': placeholder.get('type', 'body') if placeholder is not None else None,
                          'text': text, 'bounds': bounds, 'outsideInteractiveRegions': outside})
        positioned = sorted([row for row in texts if row['outsideInteractiveRegions']], key=lambda row: row['bounds']['y'])
        titles = [row for row in positioned if row['placeholder'] in ('title', 'ctrTitle')]
        title = (titles or positioned or [None])[0]
        context = [row for row in positioned if row is not title]
        slides.append({'slide': number, 'part': part, 'editableTextShapes': texts,
                       'titleCandidateShapeId': title['shapeId'] if title else None,
                       'contextCandidateShapeIds': [row['shapeId'] for row in context],
                       'hasEditableTitleAndContextCandidates': bool(title and context),
                       'semanticBodyConfirmed': False})
    return {'pages': len(parts), 'slides': slides, 'instances': instances,
            'nativePackageStructuralValidation': native_validation.to_dict(),
            'nativeTextPresentOnEverySlide': all(row['editableTextShapes'] for row in slides),
            'editableTitleAndContextCandidatesOnEverySlide': all(row['hasEditableTitleAndContextCandidates'] for row in slides)}


def walk_nodes(nodes):
    for node in nodes:
        yield node
        yield from walk_nodes(node.get('children', []))


def typed_objects(value):
    if isinstance(value, dict):
        if isinstance(value.get('type'), str): yield value
        for child in value.values(): yield from typed_objects(child)
    elif isinstance(value, list):
        for child in value: yield from typed_objects(child)


def numeric(value):
    if isinstance(value, bool): return False
    if isinstance(value, (int, float)): return math.isfinite(value)
    if isinstance(value, list): return any(numeric(child) for child in value)
    if isinstance(value, dict): return any(numeric(child) for child in value.values())
    return False


def inspect_plan(scene):
    plan = scene.get('testPlan', [])
    need(isinstance(plan, list) and bool(plan), 'Scene has no nonempty testPlan')
    names = set()
    tests = []
    for case in plan:
        need(bool(case['name']), 'Test name is empty')
        need(case['name'] not in names, 'Duplicate test name')
        names.add(case['name'])
        need(bool(case['assertions']), f"Test {case['name']} has no assertions")
        for action in case['actions']:
            need(action.get('type') in TEST_ACTIONS, 'Unsupported/nonexecutable test action')
            kind = action['type']
            if kind in TARGET_ACTIONS:
                need(isinstance(action.get('target'), str) and bool(action['target']), 'Test action has no observed target')
            if kind in ('input', 'slider', 'select', 'toggle'):
                need('value' in action, 'Test control action has no value')
            if kind in ('keyboard', 'key'):
                need(isinstance(action.get('key'), str) and bool(action['key']), 'Keyboard action has no key')
            if kind == 'seekTimeline':
                need(isinstance(action.get('timeline'), str) and bool(action['timeline']) and
                     type(action.get('time')) in (int, float) and math.isfinite(action['time']), 'Invalid seek action')
            if kind == 'dispatch':
                need(isinstance(action.get('actions'), list) and bool(action['actions']), 'Empty/nonexecutable dispatch action')
        for item in case['assertions']:
            kind = item.get('type')
            need(kind in ASSERTION_FIELDS, 'Unsupported/nonexecutable assertion')
            need(all(isinstance(item.get(field), str) and item[field] for field in ASSERTION_FIELDS[kind]),
                 'Assertion omits its actual observed subject')
            if 'tolerance' in item:
                need(isinstance(item['tolerance'], (int, float)) and not isinstance(item['tolerance'], bool) and
                     math.isfinite(item['tolerance']) and item['tolerance'] >= 0, 'Invalid numeric tolerance')
        tests.append({'name': case['name'], 'actions': case['actions'], 'assertions': case['assertions'],
                      'numericAssertions': [item for item in case['assertions'] if numeric(item.get('equals'))],
                      'hasExerciseAction': any(action['type'] not in ('wait', 'snapshot') for action in case['actions']),
                      'captureRequested': case.get('capture', True), 'resetFirst': case.get('reset', False)})
    return tests


def scene_inventory(scene, proof):
    nodes = list(walk_nodes(scene['nodes']))
    actions = list(typed_objects({'interactions': scene.get('interactions', []),
                                'timelines': scene.get('timelines', []), 'runtimeOptions': scene.get('runtimeOptions', {})}))
    editors = []
    for node in nodes:
        if node.get('component') != 'CodeEditor': continue
        props = node.get('props', {})
        source = props.get('value', props.get('code'))
        item = {'node': node['id'], 'language': props.get('language', 'javascript'),
                'readOnlyDeclared': bool(props.get('readOnly', False)), 'bindings': node.get('bind', {}),
                'highlightLines': props.get('highlightLines'), 'resultPath': props.get('resultPath'),
                'componentBuiltInControls': ['Run', 'Stop', 'Reset'], 'keyboardEditingVerified': False}
        if isinstance(source, str):
            destination = proof / 'code' / scene['id'] / f"{node['id']}.txt"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source, encoding='utf-8')
            item.update(sourceChars=len(source), sourceLines=len(source.splitlines()),
                        sourceSha256=hash_bytes(source.encode()), sourceFile=destination.relative_to(proof).as_posix())
        editors.append(item)
    controls = []
    for node in nodes:
        interactions = [item for item in scene.get('interactions', []) if item.get('target') == node['id']]
        if node['type'] in CONTROL_TYPES or node.get('component') in CONTROL_COMPONENTS or interactions:
            controls.append({'node': node['id'], 'type': node.get('component', node['type']),
                             'label': node.get('props', {}).get('ariaLabel', node.get('props', {}).get('text')),
                             'bindings': node.get('bind', {}), 'interactions': interactions})
    return {'id': scene['id'], 'requires': scene.get('requires', []), 'nodeCounts': dict(Counter(node['type'] for node in nodes)),
            'testPlan': inspect_plan(scene), 'editors': editors, 'learnerControls': controls,
            'timelines': scene.get('timelines', []), 'behaviors': scene.get('behaviors', []),
            'pluginActions': [item for item in actions if item['type'] == 'plugin'],
            'timelineActions': [item for item in actions if 'Timeline' in item['type']],
            'dataSources': scene.get('dataSources', {}), 'customPlugins': scene.get('plugins', []),
            'externalNetworkAllowlist': scene.get('runtimeOptions', {}).get('networkAllowlist', []),
            'mathematicalCorrectnessVerified': False, 'browserExecutionVerified': False}


def capture_names(scene):
    names = ['initial.png']
    for index, case in enumerate(scene['testPlan']):
        if case.get('capture', True):
            label = re.sub(r'[^A-Za-z0-9_-]+', '-', case['name'])[:80] or 'test'
            names.append(f'{index + 1:02d}-{label}.png')
    return names + ['reset.png']


def evidence_index(root):
    root = local_path(root, directory=True)
    local_path(root / 'tests', directory=True)
    renders = local_path(root / 'renders', directory=True)
    children = list(renders.iterdir())
    need(len(children) <= 4000, 'Evidence render directory count exceeds limit')
    index = {}
    for child in children:
        need(not child.is_symlink(), 'Evidence render directory may not be a symlink')
        if child.is_dir() and (child / 'report.json').exists():
            report = read_json(child / 'report.json')
            signature = hash_bytes(json.dumps(report, sort_keys=True, separators=(',', ':')).encode())
            index.setdefault(signature, []).append(child)
    return root, index


def receipt_evidence(scene, spec_hash, fingerprint, root, index, proof, budget):
    receipt = read_json(root / 'tests' / f"{scene['id']}.json")
    need(isinstance(receipt, dict), 'Receipt must be an object')
    need(receipt.get('receiptVersion') == 1 and receipt.get('sceneId') == scene['id'] and
         receipt.get('specHash') == spec_hash, 'Receipt identity/spec hash mismatch')
    need(receipt.get('runtime') == fingerprint, 'Receipt runtime fingerprint differs from distributed runtime')
    need(receipt.get('errors') == [], 'Receipt reports errors or omits its errors inventory')
    tests = receipt.get('tests')
    need(isinstance(tests, list) and type(receipt.get('testCount')) is int and len(tests) == len(scene['testPlan']) and
         receipt.get('testCount') == len(tests), 'Receipt test count mismatch')
    for expected, actual in zip(scene['testPlan'], tests):
        need(isinstance(actual, dict) and type(actual.get('assertions')) is int and actual.get('name') == expected['name'] and
             actual.get('assertions') == len(expected['assertions']), 'Receipt test identity/assertion count mismatch')
        need(actual.get('ok') is True, 'Receipt explicitly reports an unsuccessful test')
    # These author-written booleans cannot establish execution or approval.
    claims = {key: receipt.get(key) for key in ('ok', 'runtime_verified', 'powerpoint_playback_verified')}
    expected_captures = capture_names(scene)
    need(receipt.get('captures') == expected_captures, 'Receipt does not contain the expected initial/test/reset captures')
    hashes = receipt.get('captureHashes')
    need(isinstance(hashes, dict) and set(hashes) == set(expected_captures), 'Capture hash inventory mismatch')
    signature = hash_bytes(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode())
    candidates = index.get(signature, [])
    need(bool(candidates), 'No matching report.json beneath the explicitly supplied renders directory')
    # The receipt directory string is deliberately never opened. Relocated evidence
    # is selected by its complete matching report, then every PNG is re-hashed.
    directory = candidates[0]
    samples = {0, len(expected_captures) - 1}
    if len(expected_captures) > 2: samples.update({1, (len(expected_captures) - 1) // 2, len(expected_captures) - 2})
    captures = []
    for position, name in enumerate(expected_captures):
        need(isinstance(hashes[name], str) and HEX.fullmatch(hashes[name]), 'Invalid capture digest')
        source = local_path(directory / safe_relative(name))
        budget['bytes'] += source.stat().st_size
        budget['captures'] += 1
        need(budget['bytes'] <= MAX_EVIDENCE_BYTES and budget['captures'] <= 10000, 'Total capture evidence exceeds inspection limit')
        data, dimensions = read_png(source)
        need(hash_bytes(data) == hashes[name], f'Capture hash mismatch: {name}')
        need(dimensions == {'width': scene['viewport']['width'], 'height': scene['viewport']['height']},
             f'Capture dimensions differ from declared viewport: {name}')
        item = {'name': name, 'sha256': hashes[name], **dimensions,
                'sourceFile': (directory / name).relative_to(root).as_posix(), 'sampled': position in samples}
        if position in samples:
            budget['sampledBytes'] += len(data)
            need(budget['sampledBytes'] <= MAX_SAMPLED_BYTES, 'Sampled capture proof exceeds 512 MiB limit')
            destination = proof / 'captures' / scene['id'] / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            item['proofFile'] = destination.relative_to(proof).as_posix()
        captures.append(item)
    write_json(proof / f"receipt-{scene['id']}.json", receipt)
    return {'linksConsistent': True, 'authorClaimsNotTrusted': claims, 'reportDirectoryFieldIgnored': True,
            'captureCount': len(captures), 'distinctCaptureHashes': len(set(hashes.values())), 'captures': captures,
            'executionIndependentlyReplayed': False, 'provenanceAuthenticated': False}


def inspect(pptx, bundle_zip, expected_pages, proof_path, evidence_root=None):
    need(isinstance(expected_pages, int) and not isinstance(expected_pages, bool) and 1 <= expected_pages <= 1000,
         'Expected pages must be an integer from 1 to 1000')
    pptx, bundle_zip = local_path(pptx), local_path(bundle_zip)
    if evidence_root is not None: evidence_root = local_path(evidence_root, directory=True)
    candidate = Path(os.path.abspath(proof_path))
    need(evidence_root is None or not candidate.is_relative_to(evidence_root), 'Proof must be outside source evidence')
    proof = fresh_proof(candidate)
    report = {'inspectorVersion': 1, 'createdAt': datetime.now(timezone.utc).isoformat(),
              'inputs': {'pptx': str(pptx), 'zip': str(bundle_zip), 'expectedPages': expected_pages,
                         'evidenceRoot': str(evidence_root) if evidence_root else None},
              'structureChecksPassed': False, 'caseDeclarationsComplete': False, 'evidenceConsistencyPassed': False,
              'browserExecutionVerified': False, 'powerpointPlaybackVerified': False,
              'contentReviewPassed': False, 'visualReviewPassed': False, 'errors': [], 'evidenceErrors': [],
              'independentReviews': {'browserExecution': 'not-run', 'powerpointPlayback': 'not-run',
                                     'content': 'not-run', 'visual': 'not-run'},
              'limitations': ['Only structure and consistency of declared evidence are inspected.',
                              'No delivered scripts, plugins, scene expressions or teaching code are executed.',
                              'Receipts/checksums are integrity links, not authenticated proof of successful execution.',
                              'Editable title/context are native text-shape candidates; their semantic roles require review.',
                              'Numeric expected values are inventoried, not independently proven mathematically.']}
    before = {}
    try:
        before = {'pptx': hash_file(pptx), 'zip': hash_file(bundle_zip)}
        bundle, deck, integrity, names = verified_bundle(bundle_zip, pptx, proof)
        report['integrity'] = integrity
        report['native'] = native_inventory(pptx, bundle, proof, expected_pages)
        report['scenes'] = []
        for ident, entry in bundle['scenes'].items():
            need(ID.fullmatch(ident), 'Unsafe scene identifier')
            scene = read_json(deck / safe_relative(entry['path']))
            need(scene['id'] == ident, 'Scene key and scene ID differ')
            info = scene_inventory(scene, proof)
            info['specSha256'] = entry['sha256']
            info['slideNumbers'] = [item['slide'] for item in report['native']['instances'] if item['sceneId'] == ident]
            report['scenes'].append(info)
        report['structureChecksPassed'] = True
        editors = [editor for scene in report['scenes'] for editor in scene['editors']]
        requirements = {'nativeTextOnEverySlide': report['native']['nativeTextPresentOnEverySlide'],
                        'editableTitleAndContextCandidatesOnEverySlide': report['native']['editableTitleAndContextCandidatesOnEverySlide'],
                        'codePackDeclared': 'code' in bundle['featurePacks'],
                        'editableCodeEditorDeclared': bool(editors) and any(not item['readOnlyDeclared'] for item in editors),
                        'editorScenesDeclareCodePack': all('code' in scene['requires'] for scene in report['scenes'] if scene['editors']),
                        'codeWorkerDistributed': 'runtime/dist/packs/code/code-runner.worker.js' in names,
                        'timelineDeclared': any(scene['timelines'] for scene in report['scenes']),
                        'learnerControlsDeclared': any(scene['learnerControls'] for scene in report['scenes']),
                        'numericAssertionsDeclared': any(test['numericAssertions'] for scene in report['scenes'] for test in scene['testPlan'])}
        report['caseDeclarations'] = requirements
        report['caseDeclarationsComplete'] = all(requirements.values())
        if evidence_root is None:
            report['evidenceErrors'].append('No external frozen interactive evidence directory supplied; ZIP integrity remains independent.')
        else:
            try:
                root, index = evidence_index(evidence_root)
                budget = {'bytes': 0, 'sampledBytes': 0, 'captures': 0}
                for info in report['scenes']:
                    scene = read_json(deck / bundle['scenes'][info['id']]['path'])
                    try:
                        info['receipt'] = receipt_evidence(scene, info['specSha256'], integrity['runtimeFingerprint'], root, index, proof, budget)
                    except (InspectionError, PptxError, OSError, ValueError, KeyError, TypeError) as error:
                        info['receipt'] = {'linksConsistent': False, 'error': str(error)}
                        report['evidenceErrors'].append(f"{info['id']}: {error}")
            except (InspectionError, PptxError, OSError, ValueError, KeyError, TypeError) as error:
                report['evidenceErrors'].append(str(error))
            report['evidenceConsistencyPassed'] = not report['evidenceErrors']
    except (InspectionError, PptxError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        report['errors'].append(str(error))
    finally:
        if before:
            report['inputSha256'] = before
            try:
                report['sourceArtifactsUnchanged'] = before == {'pptx': hash_file(pptx), 'zip': hash_file(bundle_zip)}
                if not report['sourceArtifactsUnchanged']: report['errors'].append('Source artifact changed during inspection')
            except (InspectionError, OSError) as error:
                report['sourceArtifactsUnchanged'] = False
                report['errors'].append(str(error))
        if report['errors']: report['structureChecksPassed'] = False
        report['status'] = ('invalid-structure' if not report['structureChecksPassed'] else
                            'ready-for-manual-review' if report['caseDeclarationsComplete'] and report['evidenceConsistencyPassed'] else
                            'incomplete-case-evidence')
        write_json(proof / 'inspection.json', report)
        write_review_index(proof, report)
    return report


def write_review_index(proof, report):
    lines = ['# Read-only case artifact inspection', '', f"Status: `{report['status']}`.", '',
             '**This is not a content, visual, browser execution or PowerPoint playback pass.**', '',
             'Full native editable text, actions, exact expected numeric values, code languages and capture hashes are in [inspection.json](inspection.json).', '']
    for error in report['errors'] + report['evidenceErrors']:
        lines.append('- ' + error.replace('\n', ' ').replace('<', '&lt;'))
    for scene in report.get('scenes', []):
        tests = scene['testPlan']
        lines += ['', '## ' + scene['id'], '',
                  f"Slides {scene['slideNumbers']}; {len(tests)} tests; {sum(len(t['assertions']) for t in tests)} assertions; "
                  f"{sum(len(t['numericAssertions']) for t in tests)} numeric assertions.", '',
                  f"Declared packs: {', '.join(scene['requires']) or 'core'}; timelines: {len(scene['timelines'])}; controls: {len(scene['learnerControls'])}.", '']
        for editor in scene['editors']:
            if editor.get('sourceFile'):
                lines.append(f"- Code source ({editor['language']}): [{editor['node']}]({editor['sourceFile']}); keyboard editing has not been independently checked.")
        for capture in scene.get('receipt', {}).get('captures', []):
            if capture.get('sampled'):
                lines.append(f"- [{capture['name']}]({capture['proofFile']}) — {capture['width']} × {capture['height']}; integrity checked, appearance not reviewed.")
    lines += ['', '## Remaining independent acceptance', '',
              '- Review every native slide and mathematical claim against the brief and sources.',
              '- Review native fallback and initial/intermediate/reset screenshots for legibility and faithful state.',
              '- Replay scene tests in a trusted host; type into Monaco with real keyboard input, run changed code, then reset.',
              '- Exercise learner controls and animation timing, including intermediate states.',
              '- Verify desktop PowerPoint Content Add-in playback separately when available.', '']
    (proof / 'REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pptx', required=True)
    parser.add_argument('--zip', dest='bundle_zip', required=True)
    parser.add_argument('--expected-pages', type=int, required=True)
    parser.add_argument('--proof', required=True, help='New directory; its parent must already exist')
    parser.add_argument('--evidence-root', help='Frozen workspace interactive directory containing tests/ and renders/')
    args = parser.parse_args()
    try:
        report = inspect(args.pptx, args.bundle_zip, args.expected_pages, args.proof, args.evidence_root)
        print(json.dumps({'status': report['status'], 'structureChecksPassed': report['structureChecksPassed'],
                          'caseDeclarationsComplete': report['caseDeclarationsComplete'],
                          'evidenceConsistencyPassed': report['evidenceConsistencyPassed'],
                          'browserExecutionVerified': False, 'powerpointPlaybackVerified': False,
                          'report': str(Path(args.proof).absolute() / 'inspection.json')}, indent=2))
        return 0 if report['status'] == 'ready-for-manual-review' else 2 if report['status'] == 'invalid-structure' else 3
    except (InspectionError, OSError, ValueError) as error:
        print(json.dumps({'status': 'invalid-input', 'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
