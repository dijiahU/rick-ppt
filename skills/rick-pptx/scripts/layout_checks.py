"""Mechanical layout clues for one native slide: off-slide objects, overlapping text
boxes, very small text and text crammed into its box. Clues, not design verdicts."""
import posixpath
import re
from urllib.parse import unquote
from xml.etree.ElementTree import fromstring

P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
EMU_PT = 12700
HEX = re.compile(r'[0-9A-Fa-f]{6}')
TOP = (P+'sp', P+'pic', P+'grpSp', P+'graphicFrame', P+'cxnSp')


def is_cream(hex_color):
    """Light warm white / cream / ivory / beige (the #F5F3ED family), not pure white."""
    if not hex_color or not re.fullmatch(r'[0-9A-Fa-f]{6}', hex_color):
        return False
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return min(r, g, b) >= 190 and r >= g >= b and 5 <= r - b <= 60


def _fill(node):
    fill = node.find('.//'+A+'solidFill/'+A+'srgbClr')
    return fill.get('val').upper() if fill is not None else None


def background(slide_tree, size):
    """The slide's own visible background colour: p:bg, else a near full-page filled shape."""
    bg = slide_tree.find('.//'+P+'bg')
    if bg is not None and _fill(bg):
        return _fill(bg)
    tree = slide_tree.find('.//'+P+'spTree')
    for node in (tree if tree is not None else []):
        if node.tag != P+'sp':
            continue
        box = _box(node)
        if box and box[2] * box[3] >= 0.9 * size[0] * size[1]:
            sppr = node.find(P+'spPr')
            return _fill(sppr) if sppr is not None else None
    return None


def slide_size(presentation_tree):
    size = presentation_tree.find('.//'+P+'sldSz')
    return (int(size.get('cx')), int(size.get('cy'))) if size is not None else (12192000, 6858000)


def _box(node):
    for path in (P+'spPr/'+A+'xfrm', P+'grpSpPr/'+A+'xfrm', P+'xfrm'):
        xf = node.find(path)
        if xf is not None:
            off, ext = xf.find(A+'off'), xf.find(A+'ext')
            if off is not None and ext is not None:
                return int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy'))
    return None


def _name(node):
    for el in node.iter():
        if el.tag.endswith('}cNvPr'):
            return el.get('name') or el.get('id')
    return '?'


def _text(node):
    return ''.join(t.text or '' for t in node.iter(A+'t')).strip()


def _sizes(node):
    return [int(r.get('sz')) / 100 for r in node.iter() if r.tag in (A+'rPr', A+'defRPr', A+'endParaRPr') and r.get('sz')]


def _segment(node, box):
    """Endpoints of a straight connector or line shape, honouring flips."""
    x, y, cx, cy = box
    xf = node.find('.//'+A+'xfrm')
    flip_h = xf is not None and xf.get('flipH') in ('1', 'true')
    flip_v = xf is not None and xf.get('flipV') in ('1', 'true')
    x1, x2 = (x + cx, x) if flip_h else (x, x + cx)
    y1, y2 = (y + cy, y) if flip_v else (y, y + cy)
    return (x1, y1), (x2, y2)


def _crosses(p1, p2, rect):
    """Does the segment pass through the rectangle's interior (inset so touching edges do not count)?"""
    x, y, w, h = rect
    inset_x, inset_y = w * 0.15, h * 0.2
    left, top, right, bottom = x + inset_x, y + inset_y, x + w - inset_x, y + h - inset_y
    if right <= left or bottom <= top:
        return False
    inside = lambda p: left <= p[0] <= right and top <= p[1] <= bottom
    if inside(p1) or inside(p2):
        return False  # a label attached at the line's end is fine
    steps = 40
    return any(inside((p1[0] + (p2[0] - p1[0]) * i / steps, p1[1] + (p2[1] - p1[1]) * i / steps)) for i in range(1, steps))


def _overlap(a, b):
    w = min(a[0]+a[2], b[0]+b[2]) - max(a[0], b[0])
    h = min(a[1]+a[3], b[1]+b[3]) - max(a[1], b[1])
    return w*h if w > 0 and h > 0 else 0


def _leaves(parent, transform=(0, 0, 1, 1)):
    """Yield (node, box) for drawable shapes, flattening group coordinate transforms."""
    ox, oy, sx, sy = transform
    for node in parent:
        if node.tag not in TOP:
            continue
        box = _box(node)
        if box is None:
            continue
        x, y, cx, cy = box
        mapped = (ox + x * sx, oy + y * sy, cx * sx, cy * sy)
        if node.tag == P+'grpSp':
            xf = node.find(P+'grpSpPr/'+A+'xfrm')
            ch_off, ch_ext = (xf.find(A+'chOff'), xf.find(A+'chExt')) if xf is not None else (None, None)
            if ch_off is not None and ch_ext is not None and int(ch_ext.get('cx')) and int(ch_ext.get('cy')):
                gsx, gsy = mapped[2] / int(ch_ext.get('cx')), mapped[3] / int(ch_ext.get('cy'))
                inner = (mapped[0] - int(ch_off.get('x')) * gsx, mapped[1] - int(ch_off.get('y')) * gsy, gsx, gsy)
            else:
                inner = transform
            yield from _leaves(node, inner)
        else:
            yield node, mapped


def plain_page(slide_tree, size, background_color):
    """Whether a slide lacks pictures, a second surface and display-sized text."""
    if any(slide_tree.find(path) is not None for path in (
            './/'+P+'pic', './/'+P+'spPr/'+A+'blipFill', './/'+P+'bgPr/'+A+'blipFill')):
        return False
    for paragraph in slide_tree.iter(A+'p'):
        default = paragraph.find(A+'pPr/'+A+'defRPr[@sz]')
        for run in paragraph:
            if run.tag not in (A+'r', A+'fld') or not _text(run):
                continue
            props = run.find(A+'rPr[@sz]')
            props = default if props is None else props
            if props is not None and int(props.get('sz')) >= 6000:
                return False
    tree = slide_tree.find('.//'+P+'spTree')
    frame = (0, 0, *size)
    page_area = size[0] * size[1]
    for node, box in _leaves(tree if tree is not None else []):
        if node.tag != P+'sp' or node.find(P+'spPr/'+A+'solidFill') is None:
            continue
        geom = node.find(P+'spPr/'+A+'prstGeom')
        if geom is not None and geom.get('prst') in ('line', 'lineInv'):
            continue
        area = _overlap(box, frame)
        if area == page_area and (not background_color or _fill(node.find(P+'spPr')) == background_color.upper()):
            continue
        if area * 100 >= page_area * 6:
            return False
    return True


def plain_pages(archive):
    """Interior page numbers in presentation order, independent of slide part filenames."""
    presentation = fromstring(archive.read('ppt/presentation.xml'))
    slides = presentation.findall(P+'sldIdLst/'+P+'sldId')
    if len(slides) < 3:
        return []
    size = slide_size(presentation)
    targets = {rel.get('Id'): rel.get('Target') for rel in fromstring(archive.read('ppt/_rels/presentation.xml.rels'))
               if rel.get('Type', '').endswith('/slide') and rel.get('TargetMode') != 'External'}
    found = []
    for number, slide in enumerate(slides[1:-1], 2):
        target = unquote(targets[slide.get(R+'id')])
        part = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt', target))
        tree = fromstring(archive.read(part))
        if plain_page(tree, size, background(tree, size)):
            found.append(number)
    return found


def _glyph_width(text, size_pt, bold=False):
    """Rough advance width in EMU: Latin/digits ~0.6 em (0.68 bold), CJK 1 em (no font metrics needed)."""
    em = size_pt * 12700
    latin = 0.68 if bold else 0.6
    return sum(em if '\u2e80' <= ch <= '\u9fff' or '\uff00' <= ch <= '\uffef' else latin * em for ch in text)


def _unit_collision(number, unit):
    """A 1-2 character unit whose box begins inside the inked width of a much larger,
    left-aligned number (2026-11-21: "单" printed over the "3" of a 126 pt "+23")."""
    (n_name, n_box, n_node), (u_name, u_box, u_node) = number, unit
    n_text, u_text = _text(n_node), _text(u_node)
    n_size, u_size = max(_sizes(n_node) or [0]), max(_sizes(u_node) or [0])
    if not (1 <= len(u_text) <= 2 and len(n_text) >= 1 and n_size >= 1.8 * max(u_size, 1)):
        return None
    if any(p.get('algn') in ('ctr', 'r', 'just', 'dist') for p in n_node.iter(A+'pPr')):
        return None  # ink position unknown without metrics; only judge left-aligned numbers
    ins = next((int(b.get('lIns')) for b in n_node.iter(A+'bodyPr') if b.get('lIns') is not None), 91440)
    ink_left = n_box[0] + ins
    bold = any(r.get('b') in ('1', 'true') for r in n_node.iter(A+'rPr'))
    ink_right = ink_left + _glyph_width(n_text, n_size, bold)
    vertical = min(n_box[1] + n_box[3], u_box[1] + u_box[3]) - max(n_box[1], u_box[1])
    # A label left of or above the number (最高, 设计) starts before its ink: not a unit.
    if (ink_left + 0.4 * (ink_right - ink_left) < u_box[0] < ink_right - 0.08 * n_size * 12700
            and vertical > 0.5 * u_box[3]):
        return n_name + ' / ' + u_name
    return None


def _straddles(fill, text):
    """A filled area's edge runs through the middle band of a text box (text sits across two surfaces)."""
    fx, fy, fw, fh = fill; tx, ty, tw, th = text
    if fw * fh <= tw * th or _overlap(fill, text) == 0:
        return False
    if fx <= tx and fy <= ty and fx + fw >= tx + tw and fy + fh >= ty + th:
        return False  # fully on this surface
    band_top, band_bottom = ty + th * 0.25, ty + th * 0.8
    band_left, band_right = tx + tw * 0.2, tx + tw * 0.8
    horizontal = any(band_top < edge < band_bottom for edge in (fy, fy + fh)) and fx < band_right and fx + fw > band_left
    vertical = any(band_left < edge < band_right for edge in (fx, fx + fw)) and fy < band_bottom and fy + fh > band_top
    return horizontal or vertical


def _near(color, palette, tolerance=24):
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return any(abs(r - int(p[0:2], 16)) + abs(g - int(p[2:4], 16)) + abs(b - int(p[4:6], 16)) <= tolerance for p in palette)


def off_palette(slide_tree, palette):
    """Fill, line and text colours on the slide that are not in the deck palette."""
    if not palette:
        return []
    allowed = set(palette) | {'FFFFFF', '000000'}
    used = {c.get('val').upper() for c in slide_tree.iter(A+'srgbClr') if c.get('val') and HEX.fullmatch(c.get('val'))
            and c.getparent().tag == A+'solidFill' and c.getparent().getparent().tag != A+'blipFill'}
    stray = sorted(c for c in used if not _near(c, allowed))
    return [{'kind': 'off_palette', 'object': 'page', 'detail': 'colours outside deck-style.json: ' + ', '.join(stray[:6])
             + '; use @tokens or add a deliberate colour to the palette'}] if stray else []


def check(slide_tree, size, *, min_pt=10, palette=None):
    width, height = size
    tree = slide_tree.find('.//'+P+'spTree')
    if tree is None:
        return []
    issues, texts, rules = [], [], []
    margin = int(0.01*width)
    colour = background(slide_tree, size)
    if is_cream(colour):
        issues.append({'kind': 'cream_background', 'object': 'page background',
                       'detail': f'#{colour} is in the excluded light warm-white/cream family; candidate_save will refuse it'})
    fills, content, full_bleed = [], [], False
    for node, box in _leaves(tree):
        x, y, cx, cy = box
        name = _name(node)
        footer = y > height*0.86 and (cy < height*0.03 or max(_sizes(node) or [99]) <= 12)
        if node.tag == P+'pic' and cx*cy >= width*height*0.9:
            full_bleed = True  # the composition lives in the picture
        elif not footer and cx*cy < width*height*0.9:
            content.append(box)
        if x < -margin or y < -margin or x+cx > width+margin or y+cy > height+margin:
            if not (node.tag == P+'pic' and cx >= width*0.9):  # full-bleed images may bleed
                issues.append({'kind': 'off_slide', 'object': name, 'detail': 'extends beyond the slide edge'})
        if node.tag == P+'sp' and _text(node):
            texts.append((name, box, node))
        sppr = node.find(P+'spPr')
        rect = sppr is not None and sppr.find(A+'prstGeom') is not None and sppr.find(A+'prstGeom').get('prst') in ('rect', 'roundRect')
        if node.tag == P+'sp' and rect and sppr.find(A+'solidFill') is not None and not _text(node):
            fills.append((name, box))
        geometry = node.find('.//'+A+'prstGeom')
        if node.tag == P+'cxnSp' or (geometry is not None and geometry.get('prst') in ('line', 'straightConnector1')):
            rules.append((name, _segment(node, box)))
    for name, box, node in texts:
        sizes = [s for s in _sizes(node) if s > 0]
        text = _text(node)
        if sizes and min(sizes) < min_pt and len(text) > 3:
            issues.append({'kind': 'small_text', 'object': name,
                           'detail': f'{min(sizes):g} pt text ("{text[:20]}") may be hard to read when projected'})
        if sizes:
            # Rough fill estimate: CJK glyphs ~1em wide, Latin ~0.55em, line height 1.2em.
            pt = max(sizes)
            em = pt*EMU_PT
            cjk = len(re.findall(r'[　-鿿＀-￯]', text))
            width_needed = (cjk + 0.55*(len(text)-cjk)) * em
            lines = max(1, width_needed / max(box[2], 1)) + text.count('\n')
            if lines*1.2*em > box[3]*1.35 and box[3] > 0:
                issues.append({'kind': 'text_may_overflow', 'object': name,
                               'detail': 'text looks larger than its box; check the render for clipping or spill'})
    for fill_name, fill_box in fills:
        for name, box, _ in texts:
            if _straddles(fill_box, box):
                issues.append({'kind': 'text_straddles_edge', 'object': fill_name + ' / ' + name,
                               'detail': 'the edge of a filled area runs through this text; move the text onto one surface'})
    for line_name, (p1, p2) in rules:
        for name, box, _ in texts:
            if _crosses(p1, p2, box):
                issues.append({'kind': 'line_crosses_text', 'object': line_name + ' / ' + name,
                               'detail': 'a line or connector runs through this text; reroute it or move the text'})
    for i in range(len(texts)):
        for j in range(i+1, len(texts)):
            a, b = texts[i][1], texts[j][1]
            area = _overlap(a, b)
            smaller = min(a[2]*a[3], b[2]*b[3]) or 1
            # A one- or two-character unit tucked against its number ("+23" / "单") is deliberate.
            if area / smaller > 0.3 and min(len(_text(texts[i][2])), len(_text(texts[j][2]))) > 2:
                issues.append({'kind': 'text_overlap', 'object': texts[i][0]+' / '+texts[j][0],
                               'detail': f'text boxes overlap by {round(100*area/smaller)}% of the smaller box'})
            elif area:
                collision = _unit_collision(texts[i], texts[j]) or _unit_collision(texts[j], texts[i])
                if collision:
                    issues.append({'kind': 'unit_over_number', 'object': collision,
                                   'detail': 'a short unit box starts inside its number\'s glyphs; move it right of the digits onto their baseline'})
    if content and not full_bleed:
        # Content stacked from the top with the lower part of the page simply left over.
        bottom = max(y + cy for _, y, _, cy in content)
        if height - bottom >= height*0.3:
            issues.append({'kind': 'empty_band', 'object': 'page',
                           'detail': f'content ends at {round(100*bottom/height)}% of the page height; the lower '
                                     f'{round(100*(1-bottom/height))}% is empty. Keep it only if that space is part of the '
                                     'composition; otherwise enlarge the focus or distribute the page'})
    # Edges that almost line up: a deliberate offset is larger than this, so it reads as a slip.
    emu_in = 914400
    # Large type is often nudged left on purpose (optical alignment), so only compare similar sizes.
    lefts = sorted((box[0], name, max(_sizes(node) or [0])) for name, box, node in texts)
    for (a, name_a, size_a), (b, name_b, size_b) in zip(lefts, lefts[1:]):
        similar = min(size_a, size_b) > 0 and max(size_a, size_b) / min(size_a, size_b) < 1.5
        if similar and 0.02*emu_in < b - a < 0.12*emu_in:
            issues.append({'kind': 'near_alignment', 'object': name_a + ' / ' + name_b,
                           'detail': f'left edges differ by {(b - a)/emu_in:.2f} in; align them exactly or offset clearly'})
            break
    issues += off_palette(slide_tree, palette)
    return issues[:20]


def _hue_chroma(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    high, low = max(r, g, b), min(r, g, b)
    chroma = high - low
    if chroma == 0:
        return None, 0, high
    if high == r:
        hue = 60 * (((g - b) / chroma) % 6)
    elif high == g:
        hue = 60 * ((b - r) / chroma + 2)
    else:
        hue = 60 * ((r - g) / chroma + 4)
    return hue, chroma, high


def is_muted_cool(hex_color):
    """Greyed sage / dusty teal / slate blue: cool hue at low chroma (the stock generated palette)."""
    hue, chroma, _ = _hue_chroma(hex_color)
    return hue is not None and 80 <= hue <= 240 and 8 <= chroma <= 70


def _card_fill(hex_color):
    """A light tinted panel: not white, not dark, low chroma (pale grey-green, beige, pale blue...)."""
    hue, chroma, high = _hue_chroma(hex_color)
    low = high - chroma
    return hex_color != 'FFFFFF' and low >= 190 and chroma <= 45


def surface_audit(archive):
    """Per-deck surface clues in presentation order: cream panels, tinted text cards, muted cool palette.

    2026-11-22 (Rick): beyond the slide ground, generated decks put text on many pale tinted
    rectangles (cream FFFCF5 cards, pale sage panels) in a greyed teal/sage palette. Clues only."""
    presentation = fromstring(archive.read('ppt/presentation.xml'))
    size = slide_size(presentation)
    page_area = size[0] * size[1]
    frame = (0, 0, *size)
    targets = {rel.get('Id'): rel.get('Target') for rel in fromstring(archive.read('ppt/_rels/presentation.xml.rels'))
               if rel.get('Type', '').endswith('/slide') and rel.get('TargetMode') != 'External'}
    cream, cards, colour_area = [], {}, {}
    for number, slide in enumerate(presentation.findall(P+'sldIdLst/'+P+'sldId'), 1):
        target = unquote(targets[slide.get(R+'id')])
        part = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt', target))
        tree = fromstring(archive.read(part))
        ground = background(tree, size)
        if ground:
            colour_area[ground] = colour_area.get(ground, 0) + 1.0
        spt = tree.find('.//'+P+'spTree')
        leaves = list(_leaves(spt if spt is not None else []))
        texts = [box for node, box in leaves if node.tag == P+'sp' and _text(node)]
        count = 0
        for node, box in leaves:
            if node.tag != P+'sp':
                continue
            sppr = node.find(P+'spPr')
            if sppr is None or sppr.find(A+'solidFill') is None:
                continue
            geom = sppr.find(A+'prstGeom')
            if geom is not None and geom.get('prst') not in ('rect', 'roundRect', 'snip1Rect', 'round2SameRect'):
                continue
            fill = _fill(sppr)
            share = _overlap(box, frame) / page_area
            if not fill or share >= 0.9 or share < 0.01:
                continue
            colour_area[fill] = colour_area.get(fill, 0) + share
            carries_text = bool(_text(node)) or any(_overlap(box, t) >= 0.6 * t[2] * t[3] for t in texts if t != box)
            if is_cream(fill) and share >= 0.08:
                cream.append((number, fill, round(share * 100)))
            if carries_text and 0.02 <= share <= 0.45 and (_card_fill(fill) or is_cream(fill)):
                count += 1
        if count:
            cards[number] = count
    chromatic = {c: a for c, a in colour_area.items() if _hue_chroma(c)[1] >= 8}
    total = sum(chromatic.values())
    muted = sum(a for c, a in chromatic.items() if is_muted_cool(c))
    return {'cream_surfaces': cream, 'card_pages': cards,
            'muted_cool_share': round(muted / total, 2) if total else 0.0,
            'muted_colours': sorted((c for c in chromatic if is_muted_cool(c)), key=lambda c: -chromatic[c])[:5]}
