"""Edit existing native objects in place: move/resize, text size/colour/content, fill, delete.

Targets are object names (as given in native batches) or numeric shape IDs. Each edit
changes only the named properties, so a review instruction ("enlarge the photo to
62% width", "set the question to 30 pt") does not require rebuilding the page.

  native_edit.py --workspace PARTS_DIR --input edits.json
  edits.json: [{"slide": 2, "target": "壁画", "box": [0.6, 1.4, 6.2, 4.3]},
               {"slide": 2, "target": "提问", "size": 30, "ink": "F3F5F6"},
               {"slide": 3, "target": "旧沙丘", "delete": true}]
Box values are slide inches [x, y, width, height]; colours are RRGGBB.

Poster properties: rotate (degrees), vertical (true: East Asian vertical text, give the
box a tall shape), tracking (letter spacing in points, negative tightens), leading
(line spacing as a multiple, e.g. 0.9 for display type), opacity (0-1, shape fill or
picture), gradient ({"from": "@text", "to": "@text", "from_opacity": 0.8,
"to_opacity": 0, "angle": 0}: a scrim that fades over a picture; angle 0 runs left to
right, 90 top to bottom), shape (a picture's outline: ellipse, roundRect, parallelogram,
triangle, diamond, hexagon, round2SameRect, snip1Rect, rect), crop (a picture's [left, top,
right, bottom] fractions to trim, e.g. a pptx_study_reference crops candidate; give the
picture a box of the same aspect).
"""
import argparse
import json
import copy
import math
from pathlib import Path

import native_canvas as canvas
import deck_style

P, A = canvas.P, canvas.A
FIELDS = {'slide', 'target', 'box', 'size', 'ink', 'fill', 'text', 'delete',
          'rotate', 'vertical', 'tracking', 'leading', 'opacity', 'gradient', 'shape', 'crop', 'focus'}
PICTURE_SHAPES = ('rect', 'ellipse', 'roundRect', 'parallelogram', 'triangle', 'diamond', 'hexagon',
                  'round2SameRect', 'snip1Rect')
KINDS = ('sp', 'pic', 'grpSp', 'cxnSp', 'graphicFrame')


def _find(shapes, target):
    matches = []
    for el in shapes.iter():
        if el.tag.split('}')[-1] not in KINDS:
            continue
        nv = next((c for c in el.iter('{%s}cNvPr' % P)), None)
        if nv is None:
            continue
        if (isinstance(target, int) and nv.get('id') == str(target)) or (isinstance(target, str) and nv.get('name') == target):
            matches.append((el, nv))
    if not matches:
        raise ValueError(f'No object named or numbered {target!r} on this slide; list names with pptx.py inspect N')
    if len(matches) > 1:
        raise ValueError(f'{len(matches)} objects are named {target!r}; target one by its numeric shape ID')
    return matches[0]


def _xfrm(el):
    local = el.tag.split('}')[-1]
    holder = el.find('{%s}grpSpPr' % P) if local == 'grpSp' else el.find('{%s}spPr' % P)
    xf = holder.find('{%s}xfrm' % A) if holder is not None else el.find('{%s}xfrm' % P)
    if xf is None:
        raise ValueError('Object has no explicit position; rebuild it with a box')
    return xf


FILLS = ('noFill', 'solidFill', 'gradFill', 'blipFill', 'pattFill', 'grpFill')
# ECMA-376 child sequences (fills share one slot); PowerPoint rejects out-of-order children.
SHAPE_ORDER = ('xfrm', 'custGeom', 'prstGeom', FILLS, 'ln', 'effectLst', 'effectDag', 'scene3d', 'sp3d', 'extLst')
RUN_ORDER = ('ln', FILLS, 'effectLst', 'effectDag', 'highlight', 'uLnTx', 'uLn', 'uFillTx', 'uFill',
             'latin', 'ea', 'cs', 'sym', 'hlinkClick', 'hlinkMouseOver', 'rtl', 'extLst')
BLIP_ORDER = ('alphaModFix', 'extLst')


def _place(parent, child, order):
    """Insert child before the first sibling that the schema sequence puts after it."""
    rank = lambda el: next((i for i, slot in enumerate(order) if el.tag.split('}')[-1] in (slot if isinstance(slot, tuple) else (slot,))), -1)
    own = rank(child)
    later = next((c for c in parent if isinstance(c.tag, str) and rank(c) > own), None)
    (later.addprevious(child) if later is not None else parent.append(child))
    return child


def _set_fill(parent, value):
    """Replace parent's fill with a solid colour, or with a prepared fill element."""
    for old in list(parent):
        if old.tag.split('}')[-1] in FILLS:
            parent.remove(old)
    fill = value
    if isinstance(value, str):
        fill = canvas.E.Element('{%s}solidFill' % A)
        canvas.node(fill, A, 'srgbClr', val=canvas.color(value))
    return _place(parent, fill, SHAPE_ORDER if parent.tag == '{%s}spPr' % P else RUN_ORDER)


def _focus_aspect(pic, focus):
    if pic.tag != '{%s}pic' % P or not isinstance(focus, list) or len(focus) != 2 or any(
            type(v) not in (int, float) or not 0 <= v <= 1 for v in focus):
        raise ValueError('focus applies to pictures: [x, y] coordinates between 0 and 1')
    ext = _xfrm(pic).find('{%s}ext' % A)
    width, height = (int(ext.get(k, '0')) if ext is not None else 0 for k in ('cx', 'cy'))
    if min(width, height) <= 0:
        raise ValueError('focus needs a picture frame with positive width and height')
    return width / height


def _cover(root, slide_path, pic, aspect, focus=(0.5, 0.5)):
    """Fill the frame without stretching, centring on focus as far as the image allows."""
    from PIL import Image
    R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    fill = pic.find('{%s}blipFill' % P)
    blip = fill.find('{%s}blip' % A) if fill is not None else None
    rid = blip.get('{%s}embed' % R) if blip is not None else None
    rels = canvas.parse(slide_path.parent / '_rels' / (slide_path.name + '.rels'))
    rel = next((r for r in rels.getroot() if r.get('Id') == rid), None)
    if rel is None:
        return
    with Image.open((slide_path.parent / rel.get('Target')).resolve()) as image:
        width, height = image.size
    source = width / height
    for old in fill.findall('{%s}srcRect' % A):
        fill.remove(old)
    rect = canvas.E.Element('{%s}srcRect' % A)
    if source != aspect:
        keep, point, before, after = ((aspect / source, focus[0], 'l', 'r') if source > aspect
                                      else (source / aspect, focus[1], 't', 'b'))
        cut = 1 - keep
        start = min(max(point - keep / 2, 0), cut)
        rect.set(before, str(round(start * 100000))); rect.set(after, str(round((cut - start) * 100000)))
    blip.addnext(rect)


def _runs(el):
    return list(el.iter('{%s}rPr' % A)) + list(el.iter('{%s}endParaRPr' % A))


def apply(workspace, edit):
    if not isinstance(edit, dict) or not set(edit) <= FIELDS or 'slide' not in edit or 'target' not in edit:
        raise ValueError('Each edit needs slide and target, plus any of ' + ', '.join(sorted(FIELDS - {'slide', 'target'})))
    style = deck_style.load(workspace)
    edit = {k: deck_style.resolve(v, style) if k in ('ink', 'fill', 'gradient') else v for k, v in edit.items()}
    root, path, tree, shapes = canvas.page(workspace, edit['slide'])
    el, nv = _find(shapes, edit['target'])
    done = []
    if edit.get('delete'):
        spid = nv.get('id')
        if any(t.get('spid') == spid for t in tree.iter('{%s}spTgt' % P)):
            raise ValueError(f'{edit["target"]!r} is a click-reveal target; rebuild the reveal without it, then delete')
        el.getparent().remove(el)
        canvas.write(path, tree)
        return {'target': edit['target'], 'deleted': True}
    if 'box' in edit:
        box = edit['box']
        if (not isinstance(box, list) or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
                or min(box[2:]) <= 0):
            raise ValueError('box must be [x, y, width, height] in slide inches with positive size')
        xf = _xfrm(el)
        off, ext = xf.find('{%s}off' % A), xf.find('{%s}ext' % A)
        off.set('x', str(round(box[0] * canvas.EMU))); off.set('y', str(round(box[1] * canvas.EMU)))
        ext.set('cx', str(round(box[2] * canvas.EMU))); ext.set('cy', str(round(box[3] * canvas.EMU)))
        if el.tag == '{%s}pic' % P and 'focus' not in edit:
            _cover(root, path, el, box[2] / box[3])
        done.append('box')
    if 'focus' in edit:
        focus = edit['focus']
        _cover(root, path, el, _focus_aspect(el, focus), focus)
        done.append('focus')
    if 'text' in edit:
        body = el.find('{%s}txBody' % P)
        paragraphs = body.findall('{%s}p' % A) if body is not None else []
        if not paragraphs:
            raise ValueError('Object has no text to replace')
        text = edit['text']
        if isinstance(text, list):
            if not text or any(not isinstance(runs, list) or any(not isinstance(run, str) for run in runs) for runs in text):
                raise ValueError('text must be a string or a non-empty list of paragraphs with string runs')
        else:
            text = [[line] for line in str(text).split('\n')]
        styled = [list(p.iter('{%s}r' % A)) for p in paragraphs]
        for p in paragraphs:
            body.remove(p)
        for i, lines in enumerate(text):
            k = min(i, len(paragraphs) - 1)
            source = paragraphs[k]
            ppr = source.find('{%s}pPr' % A)
            # An empty spacer paragraph has no run to copy: borrow the nearest styled one
            # (earlier first) instead of falling back to the master's default size.
            runs = styled[k] or next((styled[j] for j in sorted(range(len(styled)), key=lambda j: (abs(j - k), j > k))
                                      if styled[j]), [])
            p = canvas.node(body, A, 'p')
            if ppr is not None:
                p.append(copy.deepcopy(ppr))
            for j, line in enumerate(lines):
                if runs:
                    r = copy.deepcopy(runs[min(j, len(runs) - 1)]); p.append(r)
                else:
                    r = canvas.node(p, A, 'r')
                t = r.find('{%s}t' % A)
                if t is None:
                    t = canvas.node(r, A, 't')
                t.text = line
        done.append('text')
    if 'size' in edit:
        size = edit['size']
        if type(size) not in (int, float) or not 4 <= size <= 400:
            raise ValueError('size is a font size in points between 4 and 400')
        for rpr in _runs(el):
            rpr.set('sz', str(round(size * 100)))
        done.append('size')
    if 'ink' in edit:
        for rpr in _runs(el):
            _set_fill(rpr, edit['ink'])
        done.append('ink')
    if 'fill' in edit:
        sppr = el.find('{%s}spPr' % P)
        if sppr is None:
            raise ValueError('Object has no shape properties to fill')
        _set_fill(sppr, edit['fill'])
        done.append('fill')
    done += _poster(root, path, el, edit)
    canvas.write(path, tree)
    return {'target': edit['target'], 'changed': done}


def _number(edit, key, low, high):
    value = edit[key]
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{key} must be a number between {low} and {high}')
    return value


def _poster(root, path, el, edit):
    done = []
    picture = el.tag == '{%s}pic' % P
    sppr = el.find('{%s}spPr' % P)
    body = el.find('{%s}txBody' % P)
    if 'rotate' in edit:
        _xfrm(el).set('rot', str(round(_number(edit, 'rotate', -360, 360) * 60000) % 21600000))
        done.append('rotate')
    if 'vertical' in edit or 'leading' in edit or 'tracking' in edit:
        if body is None:
            raise ValueError('vertical, leading and tracking apply to text objects')
    if 'vertical' in edit:
        body_pr = body.find('{%s}bodyPr' % A)
        if edit['vertical']:
            body_pr.set('vert', 'eaVert')
            # Text was wrapped for horizontal width; one vertical column reads as one line.
            paragraphs = body.findall('{%s}p' % A)
            first_run = next(iter(paragraphs[0].iter('{%s}r' % A)), None)
            if first_run is not None:
                first_run.find('{%s}t' % A).text = ''.join(t.text or '' for t in body.iter('{%s}t' % A))
                for run in list(paragraphs[0].iter('{%s}r' % A))[1:]:
                    run.getparent().remove(run)
                for p in paragraphs[1:]:
                    body.remove(p)
        else:
            body_pr.attrib.pop('vert', None)
        done.append('vertical')
    if 'tracking' in edit:
        for rpr in _runs(el):
            rpr.set('spc', str(round(_number(edit, 'tracking', -20, 100) * 100)))
        done.append('tracking')
    if 'leading' in edit:
        value = _number(edit, 'leading', 0.6, 3)
        for p in body.findall('{%s}p' % A):
            ppr = p.find('{%s}pPr' % A)
            if ppr is None:
                ppr = canvas.E.Element('{%s}pPr' % A); p.insert(0, ppr)
            for old in ppr.findall('{%s}lnSpc' % A):
                ppr.remove(old)
            spacing = canvas.E.Element('{%s}lnSpc' % A); ppr.insert(0, spacing)
            canvas.node(spacing, A, 'spcPct', val=round(value * 100000))
        done.append('leading')
    if 'opacity' in edit:
        amount = str(round(_number(edit, 'opacity', 0, 1) * 100000))
        if picture:
            blip = el.find('{%s}blipFill/{%s}blip' % (P, A))
            for old in blip.findall('{%s}alphaModFix' % A):
                blip.remove(old)
            _place(blip, canvas.E.Element('{%s}alphaModFix' % A, amt=amount), BLIP_ORDER)
        else:
            colour = sppr.find('{%s}solidFill/{%s}srgbClr' % (A, A)) if sppr is not None else None
            if colour is None:
                raise ValueError('opacity needs a picture or a shape with a solid fill')
            for old in colour.findall('{%s}alpha' % A):
                colour.remove(old)
            canvas.node(colour, A, 'alpha', val=amount)
        done.append('opacity')
    if 'gradient' in edit:
        g = edit['gradient']
        if picture or sppr is None or not isinstance(g, dict) or not {'from', 'to'} <= set(g):
            raise ValueError('gradient needs a shape and {"from", "to"} colours (optional from_opacity, to_opacity, angle)')
        fill = canvas.E.Element('{%s}gradFill' % A, rotWithShape='1')
        stops = canvas.node(fill, A, 'gsLst')
        for position, colour, alpha in ((0, g['from'], g.get('from_opacity', 1)), (100000, g['to'], g.get('to_opacity', 1))):
            if type(alpha) not in (int, float) or not 0 <= alpha <= 1:
                raise ValueError('gradient opacities are between 0 and 1')
            clr = canvas.node(canvas.node(stops, A, 'gs', pos=position), A, 'srgbClr', val=canvas.color(colour))
            canvas.node(clr, A, 'alpha', val=round(alpha * 100000))
        angle = g.get('angle', 0)
        if type(angle) not in (int, float) or not 0 <= angle < 360:
            raise ValueError('gradient angle is 0-359 degrees')
        canvas.node(fill, A, 'lin', ang=round(angle * 60000), scaled='0')
        _set_fill(sppr, fill)
        done.append('gradient')
    if 'crop' in edit:
        crop = edit['crop']
        if (not picture or not isinstance(crop, list) or len(crop) != 4
                or any(type(v) not in (int, float) or not 0 <= v < 1 for v in crop) or crop[0] + crop[2] >= 1 or crop[1] + crop[3] >= 1):
            raise ValueError('crop applies to pictures: [left, top, right, bottom] fractions to trim, each 0-1')
        fill = el.find('{%s}blipFill' % P)
        for old in fill.findall('{%s}srcRect' % A):
            fill.remove(old)
        rect = canvas.E.Element('{%s}srcRect' % A)
        for key, value in zip(('l', 't', 'r', 'b'), crop):
            if value:
                rect.set(key, str(round(value * 100000)))
        fill.find('{%s}blip' % A).addnext(rect)
        done.append('crop')
    if 'shape' in edit:
        if not picture or edit['shape'] not in PICTURE_SHAPES:
            raise ValueError('shape applies to pictures: ' + ', '.join(PICTURE_SHAPES))
        geometry = sppr.find('{%s}prstGeom' % A)
        geometry.set('prst', edit['shape'])
        done.append('shape')
    return done


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--input', required=True, help='JSON list of edits')
    args = parser.parse_args()
    edits = json.loads(Path(args.input).read_text())
    if not isinstance(edits, list):
        raise SystemExit('Input must be a JSON list of edits')
    results = []
    for index, edit in enumerate(edits, 1):
        try:
            results.append(apply(args.workspace, edit))
        except ValueError as error:
            results.append({'edit': index, 'error': str(error)})
    print(json.dumps(results, ensure_ascii=False))
    if any('error' in r for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
