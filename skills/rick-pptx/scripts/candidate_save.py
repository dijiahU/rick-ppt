"""Export a fresh complete candidate and atomically declare its exact file.

Reuses native export/render and the existing authored decision check. This is a
candidate checkpoint, not independent review, aesthetic approval or delivery.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import uuid
import zipfile

if __package__:
    from .page_design import scoped, read
    from .pptx_core.common import NS, PptxError, sha256
    from .pptx_core.package import select, export
    from .workflow_decisions import validate_plan, MAX_PLAN_BYTES
    from .layout_checks import background, is_cream, slide_size
else:
    from page_design import scoped, read
    from pptx_core.common import NS, PptxError, sha256
    from pptx_core.package import select, export
    from workflow_decisions import validate_plan, MAX_PLAN_BYTES
    from layout_checks import background, is_cream, slide_size

ALLOW_CREAM = ('米白', '奶油', '象牙', '米色', 'cream', 'ivory', 'beige')
# Fonts that ship with Windows and Office for Mac (fonts.md); anything else falls back on recipients' machines.
SHIPPED_FONTS = {'times new roman', 'simsun', '宋体', 'dengxian', 'dengxian light', '等线', '等线 light', 'arial', 'arial black',
                 'microsoft yahei', 'microsoft yahei light', '微软雅黑', '微软雅黑 light', 'simhei', '黑体', 'kaiti', '楷体',
                 'fangsong', '仿宋', 'calibri', 'calibri light', 'cambria', 'cambria math', 'georgia', 'century gothic',
                 'verdana', 'tahoma', 'wingdings', 'wingdings 2', 'wingdings 3', 'webdings', 'symbol'}


def unshipped_fonts(artifact):
    """Text fonts used in the deck that recipients do not have (2026-11-21: a template's 思源黑体 Heavy
    title rendered thin in the renderer and on Windows, and the review missed why)."""
    import re
    found = {}
    pattern = re.compile(r'<a:(?:latin|ea|cs)\b[^>]*?typeface="([^"]*)"')
    with zipfile.ZipFile(artifact) as archive:
        for name in archive.namelist():
            if re.match(r'ppt/(slides/slide|slideLayouts/slideLayout|slideMasters/slideMaster|theme/theme)\d+\.xml$', name):
                for family in pattern.findall(archive.read(name).decode('utf-8', 'ignore')):
                    if family and not family.startswith('+') and family.lower() not in SHIPPED_FONTS:
                        found[family] = found.get(family, 0) + 1
    return dict(sorted(found.items(), key=lambda kv: -kv[1]))


def template_grounds(root):
    """Background colours carried by template decks copied into this task (references/templates)."""
    found = set()
    folder = Path(root) / 'references' / 'templates'
    if not folder.is_dir():
        return found
    for path in folder.glob('*.pptx'):
        try:
            for _, colour in cream_slides(path, every=True):
                found.add(colour.upper())
        except Exception:
            continue
    return found


def cream_slides(artifact, every=False):
    """Slide numbers whose visible background (slide, else layout, else master) is cream."""
    import posixpath
    from lxml import etree
    rel_ns = '{http://schemas.openxmlformats.org/package/2006/relationships}'
    with zipfile.ZipFile(artifact) as archive:
        names = set(archive.namelist())
        load = lambda part: etree.fromstring(archive.read(part))
        def related(part, kind):
            rels = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
            if rels not in names:
                return None
            for rel in load(rels).iter(rel_ns + 'Relationship'):
                if rel.get('Type', '').endswith('/' + kind):
                    return posixpath.normpath(posixpath.join(posixpath.dirname(part), rel.get('Target')))
            return None
        size = slide_size(load('ppt/presentation.xml'))
        pres_rels = {r.get('Id'): r.get('Target') for r in load('ppt/_rels/presentation.xml.rels').iter(rel_ns + 'Relationship')}
        found = []
        ids = load('ppt/presentation.xml').findall('p:sldIdLst/p:sldId', NS)
        for number, sid in enumerate(ids, 1):
            part = posixpath.normpath(posixpath.join('ppt', pres_rels[sid.get('{%s}id' % NS['r'])]))
            colour, current = None, part
            for kind in (None, 'slideLayout', 'slideMaster'):
                current = current if kind is None else (related(current, kind) if current else None)
                if not current or current not in names:
                    break
                colour = background(load(current), size)
                if colour:
                    break
            if colour and (every or is_cream(colour)):
                found.append((number, colour))
        return found


def unit_collisions(artifact):
    """Pages where layout_checks finds a unit over its number (2026-11-21: seen in every deck
    version, never raised by reviewers, and missed when the page was not re-inspected)."""
    try:
        from .layout_checks import check
    except ImportError:
        from layout_checks import check
    import re
    import zipfile
    from lxml import etree
    found = []
    try:
        with zipfile.ZipFile(artifact) as z:
            size = slide_size(etree.fromstring(z.read('ppt/presentation.xml')))
            names = sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)),
                           key=lambda n: int(re.search(r'(\d+)', n.rsplit('/', 1)[1]).group(1)))
            for name in names:
                issues = check(etree.fromstring(z.read(name)), size)
                objects = [i['object'] for i in issues if i['kind'] == 'unit_over_number']
                if objects:
                    found.append({'slide': int(re.search(r'(\d+)', name.rsplit('/', 1)[1]).group(1)), 'objects': objects})
    except Exception:
        return []
    return found


def _declare(root, value, previous):
    target = scoped(root, 'delivery.json')
    current = read(root, 'delivery.json', 10000) if target.exists() else None
    if current != previous:
        raise ValueError('Delivery declaration changed while saving candidate')
    pending = root / ('.delivery-' + uuid.uuid4().hex + '.json')
    try:
        with pending.open('xb') as stream:
            stream.write((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def save_candidate(task_root, workspace, output, *, allow_legacy=False):
    root = Path(task_root).resolve(strict=True)
    ws = select(scoped(root, workspace))
    scoped(root, ws.home)
    scoped(root, ws.root)
    destination = scoped(root, output)
    declaration = scoped(root, 'delivery.json')
    lock = scoped(root, '.candidate-save.lock')
    with os.fdopen(os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        previous = read(root, 'delivery.json', 10000) if declaration.exists() else None
        request = json.loads(read(root, 'request.json')) if scoped(root, 'request.json').exists() else {}
        # A new path is created by native export; existing exports are immutable.
        artifact = export(ws, destination)
        from lxml import etree
        with zipfile.ZipFile(artifact) as archive:
            tree = etree.fromstring(archive.read('ppt/presentation.xml'))
            count = len(tree.findall('p:sldIdLst/p:sldId', NS))
        expected = request.get('pages')
        if type(expected) is int and expected > 0 and count != expected:
            raise ValueError('Complete candidate page count differs from request')
        wording = ' '.join(str(request.get(k) or '') for k in ('brief', 'style')).lower()
        if request.get('mode', 'create') == 'create' and not any(w in wording for w in ALLOW_CREAM):
            # 2026-11-21 (Rick): no self-declared exemption. An author once declared #FAF5EA as the
            # deck ground in deck-style.json and shipped a cream deck. Only the brief, or a template
            # base whose own masters carry the colour, may bring a cream ground.
            cream = cream_slides(artifact)
            inherited = template_grounds(root)
            cream = [(n, c) for n, c in cream if c.upper() not in inherited]
            if cream:
                raise ValueError('Warm-white/cream/beige backgrounds are excluded for new decks: ' + ', '.join(
                    f'slide {n} #{c}' for n, c in cream) + '. Use white, a cool or neutral light grey, a colour taken '
                    'from the subject at clearly visible strength, or a dark ground, and save again.')
        has_plan = scoped(root, 'decision-plan.json').exists()
        has_outline = scoped(root, 'outline.json').exists()
        if has_plan != has_outline:
            raise ValueError('Retain and reconcile both outline and decision plan before declaring a candidate')
        authored = None
        if has_plan:
            plan = json.loads(read(root, 'decision-plan.json', MAX_PLAN_BYTES))
            outline = json.loads(read(root, 'outline.json'))
            authored = validate_plan(plan, outline, stage='authored', root=root,
                                     artifact=artifact,
                                     mode=request.get('mode') or plan.get('task', {}).get('operation') or 'create',
                                     allow_legacy=allow_legacy,
                                     require_click_reveal=False if allow_legacy else None)
        fonts = unshipped_fonts(artifact) if request.get('mode', 'create') == 'create' else {}
        units = unit_collisions(artifact) if request.get('mode', 'create') == 'create' else []
        digest = sha256(artifact)
        value = {'path': str(artifact), 'workspace': str(ws.root)}
        _declare(root, value, previous)
        return {'ok': True, 'candidate': value, 'sha256': digest, 'pages': count,
                'authored': authored, 'native_render': ws.state.get('last_render'),
                **({'font_warning': {'fonts': fonts, 'meaning': (
                    'These fonts do not ship with Windows/Office for Mac: recipients and the renderer see a fallback face '
                    '(heavy titles turn regular). Unless the user asked for them, switch to an approved font of the same '
                    'weight (fonts.md: 微软雅黑/等线 bold for heavy CJK titles, SimSun/KaiTi, Arial/Georgia) and save again.')}}
                   if fonts else {}),
                **({'unit_warning': {'pages': units, 'meaning': (
                    'A unit is printed over its large number on these pages (e.g. 单 over the 3 of +23). Move the unit '
                    'right of the digits on their baseline, render the page, and save again.')}} if units else {}),
                'meaning': 'Complete exported candidate declared. Independent review and host delivery checks remain required.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-root', default='.')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--output', required=True, help='Fresh task-local PPTX; native export preserves existing versions')
    parser.add_argument('--allow-legacy', action='store_true', help='Only for an explicitly historically admitted contract')
    args = parser.parse_args()
    try:
        result = save_candidate(args.task_root, args.workspace, args.output, allow_legacy=args.allow_legacy)
    except (OSError, ValueError, KeyError, PptxError, zipfile.BadZipFile) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
