"""Build on a template deck: see its fillable slots, keep chosen slides, swap pictures.

Works on an unpacked workspace (PARTS_DIR from `pptx.py unpack` of the template file).
Text goes through native_edit.py (keeps paragraph and run formatting); moves, sizes
and deletions too. This tool adds what template work needs besides that:

  template_fill.py map    --workspace PARTS_DIR [--slides 1,6,11]
      every slide's objects with id, name, kind, box (inches), font size and current text,
      pictures with their pixel size: the slots to fill, at a glance, instead of reading XML.
  template_fill.py select --workspace PARTS_DIR --keep 1,6,11,16,18
      keep exactly these slides in this order (a number may repeat to reuse a layout page);
      other slides, their notes and orphaned media leave the package.
  template_fill.py image  --workspace PARTS_DIR --slide 2 --target 7 --source path.jpg [--focus X Y]
      put another picture into an existing picture frame, keeping its box and effects.
      Cover crop centres on the focus (0–1 coordinates from top left), or the image centre by default.

Never keep a template's sample text or stock pictures in delivered pages: replace them
with the deck's content or delete the object.
"""
import argparse
import copy
import json
import posixpath
import shutil
import uuid
from pathlib import Path

import native_canvas as canvas
import native_edit

P, A = canvas.P, canvas.A
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
SLIDE_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide'
IMAGE_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'
IMAGE_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}


def _slides(root):
    pres = canvas.parse(canvas.scoped(root, 'ppt/presentation.xml'))
    rels = canvas.parse(canvas.scoped(root, 'ppt/_rels/presentation.xml.rels'))
    targets = {r.get('Id'): r.get('Target') for r in rels.getroot()}
    ids = pres.findall('{%s}sldIdLst/{%s}sldId' % (P, P))
    return pres, rels, ids, [posixpath.normpath(posixpath.join('ppt', targets[i.get('{%s}id' % R)])) for i in ids]


def _box(el):
    try:
        xf = native_edit._xfrm(el)
    except ValueError:
        return None  # placeholder position inherited from its layout
    off, ext = xf.find('{%s}off' % A), xf.find('{%s}ext' % A)
    if off is None or ext is None:
        return None
    return [round(int(v) / canvas.EMU, 2) for v in (off.get('x'), off.get('y'), ext.get('cx'), ext.get('cy'))]


def _describe(el, rels_dir, depth=0):
    kind = el.tag.split('}')[1]
    nv = next(el.iter('{%s}cNvPr' % P), None)
    item = {'id': int(nv.get('id')) if nv is not None else None, 'name': nv.get('name') if nv is not None else None,
            'kind': kind, 'box': _box(el)}
    text = ''.join(t.text or '' for t in el.iter('{%s}t' % A)) if kind != 'grpSp' else ''
    if text.strip():
        item['text'] = text.strip()[:80]
        size = next((r.get('sz') for r in el.iter('{%s}rPr' % A) if r.get('sz')), None)
        if size:
            item['size'] = int(size) / 100
    blip = next(el.iter('{%s}blip' % A), None) if kind == 'pic' else None
    if blip is not None and rels_dir is not None:
        item['picture'] = True
        try:
            from PIL import Image
            rels = canvas.parse(rels_dir)
            rel = next(r for r in rels.getroot() if r.get('Id') == blip.get('{%s}embed' % R))
            with Image.open((rels_dir.parent.parent / rel.get('Target')).resolve()) as image:
                item['pixels'] = list(image.size)
        except Exception:
            pass
    if depth:
        item['in_group'] = True
    return item


def map_slides(workspace, wanted=None):
    root = Path(workspace).resolve(strict=True)
    _, _, _, parts = _slides(root)
    out = []
    for number, part in enumerate(parts, 1):
        if wanted and number not in wanted:
            continue
        path = canvas.scoped(root, part)
        tree = canvas.parse(path)
        rels_dir = path.parent / '_rels' / (path.name + '.rels')
        objects = []

        def walk(container, depth):
            for el in container:
                if el.tag in ('{%s}%s' % (P, k) for k in native_edit.KINDS):
                    objects.append(_describe(el, rels_dir if rels_dir.is_file() else None, depth))
                    if el.tag == '{%s}grpSp' % P:
                        walk(el, depth + 1)
        walk(tree.find('{%s}cSld/{%s}spTree' % (P, P)), 0)
        out.append({'slide': number, 'hidden': tree.getroot().get('show') == '0', 'objects': objects})
    return out


def _referenced(root):
    """Package part names still reachable from the presentation through relationships."""
    seen, todo = set(), ['ppt/presentation.xml']
    while todo:
        part = todo.pop()
        if part in seen:
            continue
        seen.add(part)
        rels = root / posixpath.dirname(part) / '_rels' / (posixpath.basename(part) + '.rels')
        if not rels.is_file():
            continue
        for rel in canvas.parse(rels).getroot():
            if rel.get('TargetMode') == 'External':
                continue
            target = rel.get('Target')
            todo.append(posixpath.normpath(target.lstrip('/') if target.startswith('/')
                                           else posixpath.join(posixpath.dirname(part), target)))
    return seen


def select(workspace, keep):
    root = Path(workspace).resolve(strict=True)
    pres, rels, ids, parts = _slides(root)
    if not keep or any(type(n) is not int or not 1 <= n <= len(ids) for n in keep):
        raise ValueError(f'--keep needs slide numbers between 1 and {len(ids)}')
    lst = pres.find('{%s}sldIdLst' % P)
    originals = list(ids)
    used, next_sid = set(), max(int(i.get('id')) for i in ids) + 1
    rel_root = rels.getroot()
    order = []
    for number in keep:
        source = originals[number - 1]
        if number not in used:
            used.add(number); order.append(source); continue
        # A repeated page: copy the slide part (and its relationships) as a new slide.
        src_part = parts[number - 1]
        stem = f'ppt/slides/slide{uuid.uuid4().hex[:8]}.xml'
        shutil.copyfile(root / src_part, root / stem)
        src_rels = root / posixpath.dirname(src_part) / '_rels' / (posixpath.basename(src_part) + '.rels')
        if src_rels.is_file():
            tree = canvas.parse(src_rels)
            for rel in list(tree.getroot()):
                if rel.get('Type', '').endswith('/notesSlide'):
                    tree.getroot().remove(rel)
            (root / 'ppt/slides/_rels').mkdir(exist_ok=True)
            canvas.write(root / 'ppt/slides/_rels' / (posixpath.basename(stem) + '.rels'), tree)
        rid = 'rId' + uuid.uuid4().hex[:8]
        canvas.E.SubElement(rel_root, '{%s}Relationship' % PKG, Id=rid, Type=SLIDE_REL, Target='slides/' + posixpath.basename(stem))
        el = copy.deepcopy(source); el.set('id', str(next_sid)); el.set('{%s}id' % R, rid); next_sid += 1
        order.append(el)
        _content_type(root, '/' + stem, 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
    for el in list(lst):
        lst.remove(el)
    for el in order:
        lst.append(el)
    kept_rids = {el.get('{%s}id' % R) for el in order}
    for rel in list(rel_root):
        if rel.get('Type') == SLIDE_REL and rel.get('Id') not in kept_rids:
            rel_root.remove(rel)
    canvas.write(canvas.scoped(root, 'ppt/presentation.xml'), pres)
    canvas.write(canvas.scoped(root, 'ppt/_rels/presentation.xml.rels'), rels)
    removed = _prune(root)
    return {'slides': len(order), 'kept_from': keep, 'removed_parts': removed}


def _prune(root):
    """Delete slide/notes/media parts no longer reachable, with their content-type overrides."""
    live = _referenced(root)
    removed = []
    for folder in ('ppt/slides', 'ppt/notesSlides', 'ppt/media'):
        for path in sorted((root / folder).glob('*')) if (root / folder).is_dir() else []:
            part = f'{folder}/{path.name}'
            if path.is_file() and part not in live:
                path.unlink(); removed.append(part)
                rel = path.parent / '_rels' / (path.name + '.rels')
                if rel.is_file():
                    rel.unlink()
    types = canvas.parse(root / '[Content_Types].xml')
    for override in list(types.getroot()):
        name = (override.get('PartName') or '').lstrip('/')
        if override.tag == '{%s}Override' % CT and name in removed:
            types.getroot().remove(override)
    canvas.write(root / '[Content_Types].xml', types)
    return len(removed)


def _content_type(root, part, value=None, extension=None):
    types = canvas.parse(root / '[Content_Types].xml')
    top = types.getroot()
    if extension:
        if not any(d.get('Extension', '').lower() == extension for d in top.findall('{%s}Default' % CT)):
            canvas.E.SubElement(top, '{%s}Default' % CT, Extension=extension, ContentType=IMAGE_TYPES[extension])
    else:
        canvas.E.SubElement(top, '{%s}Override' % CT, PartName=part, ContentType=value)
    canvas.write(root / '[Content_Types].xml', types)


def image(workspace, slide, target, source, focus=None):
    source = Path(source).resolve(strict=True)
    ext = source.suffix.lower().lstrip('.')
    if ext not in IMAGE_TYPES:
        raise ValueError('source must be ' + ', '.join(IMAGE_TYPES))
    root, path, tree, shapes = canvas.page(workspace, slide)
    el, _ = native_edit._find(shapes, target)
    if el.tag != '{%s}pic' % P:
        raise ValueError(f'{target!r} is not a picture; use native_canvas add_image for a new picture')
    aspect = native_edit._focus_aspect(el, focus) if focus is not None else None
    blip = el.find('{%s}blipFill/{%s}blip' % (P, A))
    media = root / 'ppt/media'; media.mkdir(exist_ok=True)
    name = f'fill-{uuid.uuid4().hex[:10]}.{ext}'
    shutil.copyfile(source, media / name)
    _content_type(root, None, extension=ext)
    rels_path = path.parent / '_rels' / (path.name + '.rels')
    rels = canvas.parse(rels_path)
    rid = 'rId' + uuid.uuid4().hex[:8]
    canvas.E.SubElement(rels.getroot(), '{%s}Relationship' % PKG, Id=rid, Type=IMAGE_REL, Target='../media/' + name)
    canvas.write(rels_path, rels)
    blip.set('{%s}embed' % R, rid)
    box = _box(el)
    if aspect is not None:
        native_edit._cover(root, path, el, aspect, focus)
    elif box:
        native_edit._cover(root, path, el, box[2] / box[3])
    canvas.write(path, tree)
    _prune(root)
    return {'slide': slide, 'target': target, 'image': f'ppt/media/{name}', 'box': box}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('map'); m.add_argument('--workspace', required=True); m.add_argument('--slides')
    s = sub.add_parser('select'); s.add_argument('--workspace', required=True); s.add_argument('--keep', required=True)
    i = sub.add_parser('image'); i.add_argument('--workspace', required=True); i.add_argument('--slide', type=int, required=True)
    i.add_argument('--target', required=True); i.add_argument('--source', required=True)
    i.add_argument('--focus', type=float, nargs=2, metavar=('X', 'Y'), help='cover crop focus, each coordinate between 0 and 1')
    args = ap.parse_args()
    numbers = lambda text: [int(x) for x in text.split(',') if x.strip()]
    if args.cmd == 'map':
        result = map_slides(args.workspace, set(numbers(args.slides)) if args.slides else None)
    elif args.cmd == 'select':
        result = select(args.workspace, numbers(args.keep))
    else:
        target = int(args.target) if args.target.isdigit() else args.target
        result = image(args.workspace, args.slide, target, args.source, focus=args.focus)
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
