"""Ensure one sequential native page without rebuilding or cloning page content.

An explicit existing layout supplies the master/theme chain. This is deliberately
not a slide clone: source-slide objects, notes, animations and backgrounds are not
copied. Existing requested pages are returned intact, never cleared.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import sys
import tempfile

from lxml import etree as E

from native_batch import _scoped, _parts_hash, _json_write
from pptx_core.common import P, A, R, PR, CT, STRICT_P, STRICT_R, parse
from pptx_core.package import select
from pptx_core.relationships import relationships, slide_parts, rels_part
from pptx_core.validator import validate


def _write(path, node):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(E.tostring(node, encoding='UTF-8', xml_declaration=True, standalone=True))


def _identities(parts):
    ordered = slide_parts(parts)
    pres = parse(parts / 'ppt/presentation.xml')
    namespace = E.QName(pres).namespace
    listing = pres.find('{' + namespace + '}sldIdLst')
    nodes = [] if listing is None else list(listing)
    return [{'part': part, 'slide_id': node.get('id'),
             'relationship_id': node.get('{' + R + '}id') or node.get('{' + STRICT_R + '}id')}
            for node, part in zip(nodes, ordered)]


def _page_layout(parts, part):
    matches = [r for r in relationships(parts, part) if r['type'].endswith('/slideLayout')]
    if len(matches) != 1 or matches[0]['external']:
        raise ValueError('Source/current page needs exactly one internal slideLayout relationship')
    return matches[0]['resolved']


def _layout(parts, value):
    if not isinstance(value, str) or not value or PurePosixPath(value).as_posix() != value:
        raise ValueError('layout must be an explicit normalized package part')
    if value.startswith('/') or '..' in PurePosixPath(value).parts or '\\' in value:
        raise ValueError('layout must stay inside the native package')
    path = _scoped(parts, value)
    tree = parse(path)
    namespace = E.QName(parse(parts / 'ppt/presentation.xml')).namespace
    if tree.tag != '{' + namespace + '}sldLayout':
        raise ValueError('Selected layout must be a native slideLayout in the presentation namespace')
    master = [r for r in relationships(parts, value) if r['type'].endswith('/slideMaster')]
    if len(master) != 1 or master[0]['external']:
        raise ValueError('Selected layout needs exactly one internal slideMaster')
    master_path = _scoped(parts, master[0]['resolved'])
    if parse(master_path).tag != '{' + namespace + '}sldMaster':
        raise ValueError('Selected layout has an invalid native master')
    theme = [r for r in relationships(parts, master[0]['resolved']) if r['type'].endswith('/theme')]
    if len(theme) != 1 or theme[0]['external']:
        raise ValueError('Selected layout master needs exactly one internal theme')
    theme_path = _scoped(parts, theme[0]['resolved'])
    if E.QName(parse(theme_path)).localname != 'theme':
        raise ValueError('Selected master has an invalid theme')
    return value


def _append(parts, layout):
    pres_path = parts / 'ppt/presentation.xml'
    pres = parse(pres_path)
    namespace = E.QName(pres).namespace
    rnamespace = STRICT_R if namespace == STRICT_P else R
    anamespace = 'http://purl.oclc.org/ooxml/drawingml/main' if namespace == STRICT_P else A
    listing = pres.find('{' + namespace + '}sldIdLst')
    if listing is None:
        raise ValueError('Existing presentation needs a slide list; do not reconstruct its schema')
    number = 1
    while (parts / f'ppt/slides/slide{number}.xml').exists() or (parts / f'ppt/slides/_rels/slide{number}.xml.rels').exists():
        number += 1
    part = f'ppt/slides/slide{number}.xml'
    rel_path = parts / 'ppt/_rels/presentation.xml.rels'
    rels = parse(rel_path)
    used = {r.get('Id') for r in rels}
    index = 1
    while f'rId{index}' in used:
        index += 1
    rid = f'rId{index}'
    used_slide_ids = [int(n.get('id')) for n in listing]
    ident = max([255, *used_slide_ids]) + 1
    if ident >= 2147483648:
        raise ValueError('No available valid presentation slide ID')
    relationship_base = rnamespace.rsplit('/', 1)[0] + '/relationships' if namespace == STRICT_P else 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    E.SubElement(rels, '{' + PR + '}Relationship', Id=rid,
                 Type=relationship_base + '/slide', Target=posixpath.relpath(part, 'ppt'))
    E.SubElement(listing, '{' + namespace + '}sldId', id=str(ident), **{'{' + rnamespace + '}id': rid})
    slide = E.Element('{' + namespace + '}sld', nsmap={'p': namespace, 'a': anamespace, 'r': rnamespace})
    common = E.SubElement(slide, '{' + namespace + '}cSld')
    shapes = E.SubElement(common, '{' + namespace + '}spTree')
    props = E.SubElement(shapes, '{' + namespace + '}nvGrpSpPr')
    E.SubElement(props, '{' + namespace + '}cNvPr', id='1', name='')
    E.SubElement(props, '{' + namespace + '}cNvGrpSpPr')
    E.SubElement(props, '{' + namespace + '}nvPr')
    E.SubElement(shapes, '{' + namespace + '}grpSpPr')
    mapping = E.SubElement(slide, '{' + namespace + '}clrMapOvr')
    E.SubElement(mapping, '{' + anamespace + '}masterClrMapping')
    page_rels = E.Element('{' + PR + '}Relationships', nsmap={None: PR})
    E.SubElement(page_rels, '{' + PR + '}Relationship', Id='rId1',
                 Type=relationship_base + '/slideLayout', Target=posixpath.relpath(layout, posixpath.dirname(part)))
    types_path = parts / '[Content_Types].xml'
    types = parse(types_path)
    E.SubElement(types, '{' + CT + '}Override', PartName='/' + part,
                 ContentType='application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
    _write(parts / part, slide)
    _write(parts / rels_part(part), page_rels)
    _write(pres_path, pres)
    _write(rel_path, rels)
    _write(types_path, types)
    # Preserve all other package parts, including template metadata, byte for byte.
    return {'part': part, 'slide_id': str(ident), 'relationship_id': rid}


def ensure_page(workspace, task_root, *, page, key, mode, source_slide=None, layout=None):
    if type(page) is not int or page < 1:
        raise ValueError('page must be a positive integer')
    if mode != 'blank_from_layout':
        raise ValueError('Choose the explicit blank_from_layout mode; cloning is not supported')
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', key):
        raise ValueError('key needs 1–80 filename-safe characters')
    if (source_slide is None) == (layout is None):
        raise ValueError('Choose exactly one existing source_slide or layout package part')
    if source_slide is not None and (type(source_slide) is not int or source_slide < 1):
        raise ValueError('source_slide must be a positive page number')
    root = Path(task_root).resolve(strict=True)
    selected = _scoped(root, workspace, directory=True)
    ws = select(selected)
    _scoped(root, ws.root, directory=True)
    _scoped(root, ws.state_path)
    if (ws.home / '.lock').is_symlink():
        raise ValueError('Unsafe workspace lock')
    request = {'page': page, 'key': key, 'mode': mode, 'source_slide': source_slide, 'layout': layout}
    input_sha = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    receipts = ws.home / 'native-pages'
    if receipts.is_symlink():
        raise ValueError('Unsafe native page receipt directory')
    receipt_path = receipts / (key + '.json')
    if receipt_path.is_symlink():
        raise ValueError('Unsafe native page receipt')
    with ws.lock():
        ws.check_original()
        before = _parts_hash(ws.root)
        identities = _identities(ws.root)
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt.get('input_sha256') != input_sha:
                raise ValueError('key already belongs to a different page request')
            if page > len(identities) or identities[page - 1] != receipt.get('identity'):
                raise ValueError('Previously ensured page identity changed or disappeared; do not append again')
            if _page_layout(ws.root, identities[page - 1]['part']) != receipt.get('layout'):
                raise ValueError('Previously ensured page layout changed; do not append again')
            return {**receipt, 'status': 'already_applied'}
        if page > len(identities) + 1:
            raise ValueError('Only the next sequential page may be appended')
        if source_slide is not None:
            if source_slide > len(identities):
                raise ValueError('source_slide must already exist')
            layout = _page_layout(ws.root, identities[source_slide - 1]['part'])
        layout = _layout(ws.root, layout)
        if page <= len(identities) and _page_layout(ws.root, identities[page - 1]['part']) != layout:
            raise ValueError('Existing page uses another layout; it will not be replaced or cleared')
        with tempfile.TemporaryDirectory(prefix='.native-page-', dir=ws.home) as temporary:
            stage = Path(temporary) / 'parts'
            backup = Path(temporary) / 'before'
            shutil.copytree(ws.root, stage)
            existing = page <= len(identities)
            identity = identities[page - 1] if existing else _append(stage, layout)
            validate(stage).require()
            receipt = {'version': 1, 'key': key, 'page': page, 'mode': mode,
                       'status': 'existing' if existing else 'appended', 'input_sha256': input_sha,
                       'identity': identity, 'layout': layout, 'workspace': str(ws.root),
                       'render_required': True, 'playback_verified': False}
            if _parts_hash(ws.root) != before:
                raise ValueError('Workspace changed during page preparation')
            state_bytes = ws.state_path.read_bytes()
            swapped = False
            try:
                if not existing:
                    ws.root.rename(backup)
                    try:
                        stage.rename(ws.root)
                        swapped = True
                    except BaseException:
                        backup.rename(ws.root)
                        raise
                    ws.refresh()
                receipts.mkdir(exist_ok=True)
                _json_write(receipt_path, receipt)
            except BaseException:
                if swapped:
                    ws.root.rename(stage)
                    backup.rename(ws.root)
                    pending = ws.state_path.with_name('state.native-page-rollback')
                    pending.write_bytes(state_bytes)
                    os.replace(pending, ws.state_path)
                receipt_path.unlink(missing_ok=True)
                raise
            return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-root', required=True)
    parser.add_argument('--workspace', required=True, help='Existing task-local session or native parts directory')
    parser.add_argument('--page', type=int, required=True, help='Existing page or the single next page in presentation order')
    parser.add_argument('--key', required=True, help='Stable idempotency key for this exact page request')
    parser.add_argument('--mode', choices=['blank_from_layout'], required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source-slide', type=int, help='Use only this existing page’s layout; never copy its contents')
    group.add_argument('--layout', help='Explicit existing slideLayout package part')
    args = parser.parse_args()
    try:
        result = ensure_page(args.workspace, args.task_root, page=args.page, key=args.key, mode=args.mode,
                             source_slide=args.source_slide, layout=args.layout)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'status': 'rejected', 'error': str(error)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
