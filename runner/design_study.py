"""pptx_study_reference: turn a reference image into measurable design properties.

Models describe a reference in adjectives ("elegant, airy") and then cannot transfer it.
This tool measures what a designer would take from it: the palette with area shares,
the light/mid/dark mass, where the focal point and the quiet space are, and returns a
study sheet (original with thirds grid and focal mark, three-value map, quiet-space
map, palette strip) so the reading is concrete and transferable to a slide.
"""
import base64
import hashlib
import io
import json
import math
import random
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat
from design_roles import reference_transfer_enabled

TOOL = 'pptx_study_reference'
GRID = 12  # analysis cells per side


def _load(path):
    """Any mode (P, LA, CMYK, I;16) as RGB; transparency reads as the white page it will sit on."""
    with Image.open(path) as source:
        rgba = source.convert('RGBA')
    return Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')


def _lab(rgb):
    """CIELAB, so 'distinct colour' means distinct to the eye: in RGB a dark red tablecloth sat only 58 apart
    from the olive shadow it lies in and was dropped as a duplicate."""
    r, g, b = (((c / 255 + .055) / 1.055) ** 2.4 if c > 10 else c / 255 / 12.92 for c in rgb)
    x, y, z = ((.4124 * r + .3576 * g + .1805 * b) / .9505, .2126 * r + .7152 * g + .0722 * b,
               (.0193 * r + .1192 * g + .9505 * b) / 1.089)
    fx, fy, fz = (t ** (1 / 3) if t > .008856 else 7.787 * t + 16 / 116 for t in (x, y, z))
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _palette(im):
    """Main colours by area plus small, distinct accents (a red title, a teal band) that area-based
    quantisation would merge away."""
    # 320 px keeps thin type strokes as their own colour instead of grey blends with the ground.
    small = im.resize((320, max(1, round(320 * im.height / im.width))))
    quant = small.quantize(colors=16, method=Image.Quantize.MAXCOVERAGE)
    raw = quant.getpalette()[:48]
    total = small.width * small.height
    rows = []
    for share, index in sorted(quant.getcolors(), reverse=True):
        r, g, b = raw[index * 3:index * 3 + 3]
        mx, mn = max(r, g, b), min(r, g, b)
        rows.append({'hex': '%02X%02X%02X' % (r, g, b), 'share': round(share / total, 3),
                     'rgb': (r, g, b), 'lab': _lab((r, g, b)),
                     'saturation': round((mx - mn) / mx, 2) if mx else 0.0,
                     'lightness': round((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255, 2)})

    def far(a, b):
        return math.dist(a['lab'], b['lab']) > 12

    main = []
    for row in rows:
        if len(main) < 4 and (not main or row['share'] >= .03) and all(far(row, m) for m in main):
            main.append(row)
    main[0]['role'] = 'dominant'  # the largest area of the picture, usually not a good page ground
    ground = main[0]

    def fringe(c):
        """A small colour lying on the straight blend between the ground and another colour is the anti-aliased
        edge of type or a shape, not a colour of the design."""
        for o in rows:
            d = [y - x for x, y in zip(ground['rgb'], o['rgb'])]
            n = sum(v * v for v in d)
            if o is c or not n or o['share'] < c['share']:  # the edge of a thing is not bigger than the thing
                continue
            t = sum((x - g) * v for x, g, v in zip(c['rgb'], ground['rgb'], d)) / n
            if .1 < t < .9 and sum((g + t * v - x) ** 2 for g, v, x in zip(ground['rgb'], d, c['rgb'])) < 14 ** 2:
                return True
        return False
    candidates = [r for r in rows if r not in main and r['share'] >= .004 and all(far(r, m) for m in main)
                  and (r['share'] >= .01 or not fringe(r))]
    # Accents differ from the ground in chroma or in plain distance (dark title ink counts). Distance to the ground,
    # not lightness alone, keeps the anti-aliased fringe of a logo from outranking the logo colour itself.
    candidates.sort(key=lambda r: -(r['saturation'] + math.dist(r['lab'], ground['lab']) / 100))
    accents = []
    for row in candidates:
        if len(accents) < 3 and all(far(row, a) for a in accents):
            # ink is type-strength contrast with the ground: dark on light, or white type on a dark slide
            row['role'] = ('accent' if row['saturation'] > .3 else
                           'ink' if abs(row['lightness'] - ground['lightness']) > .5 else 'detail')
            accents.append(row)
    return [{k: v for k, v in r.items() if k not in ('rgb', 'lab')} for r in main + accents]


def _mix(hex_colour, target, amount):
    rgb = [int(hex_colour[i:i + 2], 16) for i in (0, 2, 4)]
    return '%02X%02X%02X' % tuple(round(c + (t - c) * amount) for c, t in zip(rgb, target))


def _suggest(palette):
    """Page colours derived from the picture: a light clean ground of its family (never its mid-tone), a deep anchor
    for text, and the strongest small accent. Starting points to judge by eye, not rules."""
    dominant = palette[0]['hex']
    deepest = min(palette, key=lambda c: c['lightness'])
    accent = next((c['hex'] for c in palette if c.get('role') == 'accent'), None)
    return {'light_ground': [_mix(dominant, (255, 255, 255), a) for a in (.82, .9)],
            'deep_anchor': deepest['hex'] if deepest['lightness'] < .25 else _mix(deepest['hex'], (15, 15, 18), .7),
            'accent': accent,
            'note': 'Keep the picture its own light and colour; give the page a light clean ground of the same family and '
                    'a deep anchor for type. Check the lightness steps between ground, picture and type.'}


def _cells(gray, detail):
    w, h = gray.size
    cw, ch = w / GRID, h / GRID
    cells = []
    for j in range(GRID):
        for i in range(GRID):
            box = (round(i * cw), round(j * ch), round((i + 1) * cw), round((j + 1) * ch))
            stat = ImageStat.Stat(gray.crop(box))
            # Local contrast (spread of values) plus edges: letters and objects are busy, sky and paper are quiet.
            cells.append({'i': i, 'j': j, 'detail': stat.stddev[0] + ImageStat.Stat(detail.crop(box)).mean[0],
                          'value': stat.mean[0]})
    return cells


def study(path):
    im = _load(path)
    scale = min(960, max(240, *im.size)) / max(im.size)  # tiny icons are enlarged so every cell has pixels
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    w, h = im.size
    gray = im.convert('L')
    # PIL kernel filters leave the outer pixel row unfiltered (raw value), which made every border cell look busy.
    edges = ImageOps.expand(ImageOps.crop(gray.filter(ImageFilter.FIND_EDGES), 1), 1, fill=0)
    detail = edges.filter(ImageFilter.BoxBlur(3))
    cells = _cells(gray, detail)
    mean_value = sum(c['value'] for c in cells) / len(cells)
    quiet_limit = sorted(c['detail'] for c in cells)[len(cells) // 3] * 1.15 + 1
    quiet = [c for c in cells if c['detail'] <= quiet_limit]
    # Focal point: where detail and departure from the average value are strongest. Detail shared by a whole
    # row or column (a frame, a scroll mount, a full-width rule, even texture) is structure, not a subject.
    col_floor = [min(c['detail'] for c in cells if c['i'] == i) for i in range(GRID)]
    row_floor = [min(c['detail'] for c in cells if c['j'] == j) for j in range(GRID)]
    weight = [(c['detail'] - max(col_floor[c['i']], row_floor[c['j']]) + abs(c['value'] - mean_value) * .6) ** 2
              for c in cells]
    # Focal region: strong cells clustered around the strongest one; the mark is their weighted centre, so it
    # sits on the subject rather than in the empty middle between two busy areas.
    peak = max(range(len(cells)), key=weight.__getitem__)
    pi, pj = cells[peak]['i'], cells[peak]['j']
    # A flat picture has no focus: the box then covers the whole frame.
    cluster = [(c, wt) for c, wt in zip(cells, weight) if wt >= weight[peak] * .35 and (
               not weight[peak] or abs(c['i'] - pi) <= GRID // 4 and abs(c['j'] - pj) <= GRID // 4)]
    strong = [c for c, _ in cluster]
    total = sum(wt for _, wt in cluster) or 1
    fx = sum((c['i'] + .5) / GRID * wt for c, wt in cluster) / total if weight[peak] else .5
    fy = sum((c['j'] + .5) / GRID * wt for c, wt in cluster) / total if weight[peak] else .5
    xs = [c['i'] for c in strong]; ys = [c['j'] for c in strong]
    focal_box = [round(min(xs) / GRID, 2), round(min(ys) / GRID, 2),
                 round((max(xs) + 1 - min(xs)) / GRID, 2), round((max(ys) + 1 - min(ys)) / GRID, 2)]
    values = [c['value'] for c in cells]
    histogram = gray.histogram()
    pixels = sum(histogram)
    masses = {'dark': sum(histogram[:85]) / pixels, 'mid': sum(histogram[85:170]) / pixels,
              'light': sum(histogram[170:]) / pixels}
    halves = {
        'left': sum(1 for c in quiet if c['i'] < GRID / 2), 'right': sum(1 for c in quiet if c['i'] >= GRID / 2),
        'top': sum(1 for c in quiet if c['j'] < GRID / 2), 'bottom': sum(1 for c in quiet if c['j'] >= GRID / 2)}
    palette = _palette(im)
    suggested = _suggest(palette)
    reading = {
        'aspect': round(w / h, 2),
        'palette': palette,
        'suggested': suggested,
        'value_masses': {k: round(v, 2) for k, v in masses.items()},
        'value_contrast': round((max(values) - min(values)) / 255, 2),
        'focal_point': {'centre': [round(fx, 2), round(fy, 2)], 'box': focal_box,
                        'area_share': round(focal_box[2] * focal_box[3], 2)},
        'quiet_space': {'share': round(len(quiet) / len(cells), 2),
                        'mostly': max(halves, key=halves.get)},
    }
    return reading, _sheet(im, gray, detail, cells, quiet, (fx, fy), focal_box, palette)


def _sheet(im, gray, detail, cells, quiet, focal, focal_box, palette):
    w, h = im.size
    slot, sheet_w = 420, 420 * 3 + 40
    # Each panel fits a 420 x 560 slot, so a tall poster or scroll does not become a 4000 px strip.
    panel = max(1, min(slot, round(560 * w / h)))
    ph = max(1, round(h * panel / w))
    font = ImageFont.load_default(14)
    out = Image.new('RGB', (sheet_w, ph + 96), 'white')
    draw = ImageDraw.Draw(out)
    left = (slot - panel) // 2
    # 1. original with thirds grid and focal box
    a = im.resize((panel, ph))
    da = ImageDraw.Draw(a)
    for k in (1, 2):
        da.line([(panel * k / 3, 0), (panel * k / 3, ph)], fill=(255, 255, 255), width=1)
        da.line([(0, ph * k / 3), (panel, ph * k / 3)], fill=(255, 255, 255), width=1)
    x, y, bw, bh = focal_box
    da.rectangle([x * panel, y * ph, (x + bw) * panel, (y + bh) * ph], outline=(230, 30, 30), width=3)
    da.ellipse([focal[0] * panel - 6, focal[1] * ph - 6, focal[0] * panel + 6, focal[1] * ph + 6], fill=(230, 30, 30))
    out.paste(a, (left, 0))
    # 2. three-value map
    out.paste(notan(gray, (panel, ph)), (left + slot + 20, 0))
    # 3. quiet space (where words can sit) over a faded image
    c = Image.blend(im.resize((panel, ph)), Image.new('RGB', (panel, ph), 'white'), .55)
    dc = ImageDraw.Draw(c, 'RGBA')
    cw, ch = panel / GRID, ph / GRID
    for cell in quiet:
        dc.rectangle([cell['i'] * cw, cell['j'] * ch, (cell['i'] + 1) * cw, (cell['j'] + 1) * ch], fill=(40, 120, 230, 90))
    out.paste(c, (left + slot * 2 + 40, 0))
    # palette strip proportional to area; labels flow in their own row with a swatch, so small accents stay legible
    x = 0
    for colour in palette:
        width = max(6, round(colour['share'] * sheet_w))
        draw.rectangle([x, ph + 8, x + width, ph + 36], fill='#' + colour['hex'])
        x += width
    draw.rectangle([0, ph + 8, x, ph + 36], outline=(150, 150, 150))  # a white or black ground stays visible
    x, y = 4, ph + 44
    for colour in palette:
        label = colour['hex'] + (' ' + colour['role'] if colour.get('role') else '') + f" {round(colour['share'] * 100)}%"
        size = 18 + draw.textlength(label, font=font)
        if x + size > sheet_w:
            x, y = 4, y + 22
        draw.rectangle([x, y + 2, x + 12, y + 14], fill='#' + colour['hex'], outline=(150, 150, 150))
        draw.text((x + 16, y), label, fill=(50, 50, 50), font=font)
        x += size + 14
    for k, name in enumerate(('focal + thirds', 'mass study', 'quiet space')):
        draw.text((slot * k + 20 * k + 4, ph - 20), name, fill=(255, 255, 255), font=font, stroke_width=2,
                  stroke_fill=(40, 40, 40))
    buffer = io.BytesIO()
    out.save(buffer, 'JPEG', quality=82)
    return buffer.getvalue()


def _three_values(hist):
    """Two thresholds splitting the histogram into the three most distinct value groups (multi-level Otsu).
    Fixed 85/170 cuts lost the structure of low-key paintings and of slides, where text blocks are light grey."""
    count, moment = [0], [0]
    for value, n in enumerate(hist):
        count.append(count[-1] + n); moment.append(moment[-1] + value * n)

    def spread(a, b):
        n = count[b] - count[a]
        return (moment[b] - moment[a]) ** 2 / n if n else 0
    return max(((t1, t2) for t1 in range(1, 255) for t2 in range(t1 + 1, 256)),
               key=lambda t: spread(0, t[0]) + spread(t[0], t[1]) + spread(t[1], 256))


def notan(gray, size):
    """Three-value mass study: blur away texture and detail, keep the big shapes, split at the image's own
    value groups (a squint: the darkest, middle and lightest masses of this picture)."""
    small = gray.resize(size).filter(ImageFilter.GaussianBlur(max(1, size[0] / 140)))
    if small.getextrema()[1] - small.getextrema()[0] < 24:  # one flat value: no structure to split
        return Image.new('RGB', size, (235, 235, 235) if small.getextrema()[0] >= 128 else (30, 30, 30))
    dark, light = _three_values(small.histogram())
    return small.point(lambda v: 30 if v < dark else 128 if v < light else 235).convert('RGB')


def compare(reference, page):
    """Reference and page side by side, each with its mass study, at one height."""
    height = 300
    rows = []
    for path in (reference, page):
        im = _load(path)
        width = max(1, min(900, round(im.width * height / im.height)))
        im = im.resize((width, height))
        rows.append((im, notan(im.convert('L'), (width, height))))
    total = max(a.width + b.width for a, b in rows) + 20
    out = Image.new('RGB', (total, height * 2 + 50), 'white')
    draw = ImageDraw.Draw(out)
    for row, (label, (image, masses)) in enumerate(zip(('reference', 'this page'), rows)):
        y = row * (height + 25) + 20
        out.paste(image, (0, y)); out.paste(masses, (image.width + 20, y))
        draw.text((4, y - 16), label, fill=(200, 0, 0))
    buffer = io.BytesIO()
    out.save(buffer, 'JPEG', quality=82)
    return buffer.getvalue()


def strip(paths):
    """The deck in order, each page over its mass study: a colour script for judging rhythm."""
    cell_w, cell_h = 240, 135
    out = Image.new('RGB', (cell_w * len(paths) + 10 * (len(paths) - 1), cell_h * 2 + 34), 'white')
    draw = ImageDraw.Draw(out)
    for i, path in enumerate(paths):
        im = _load(path).resize((cell_w, cell_h))
        x = i * (cell_w + 10)
        out.paste(im, (x, 18)); out.paste(notan(im.convert('L'), (cell_w, cell_h)), (x, 18 + cell_h + 6))
        draw.text((x + 2, 2), str(i + 1), fill=(200, 0, 0))
    buffer = io.BytesIO()
    out.save(buffer, 'JPEG', quality=82)
    return buffer.getvalue()


def _font(size):
    """A CJK-capable label font (Chinese names and labels), falling back to the default bitmap font."""
    from PIL import ImageFont
    for candidate in sorted((Path(__file__).resolve().parent / 'font-cache.local' / 'fonts').glob('simsun*.tt[fc]')):
        return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def crops(path, aspects=(16 / 9, 3 / 1, 2 / 3, 1.0)):
    """Crop candidates around the focal point: whole, tight, strip, tall, and off-centre placements.

    Returns (candidates, sheet); each candidate's crop is [left, top, right, bottom] as fractions to trim."""
    reading, _ = study(path)
    im = _load(path)
    W, H = im.size
    fx, fy = reading['focal_point']['centre']
    out_list = [{'name': 'whole', 'crop': [0, 0, 0, 0]}]

    def window(aspect, scale, cx, cy):
        w = min(W, H * aspect) * scale; h = w / aspect
        if h > H:
            h = H; w = h * aspect
        x = min(max(cx * W - w / 2, 0), W - w); y = min(max(cy * H - h / 2, 0), H - h)
        return [round(x / W, 3), round(y / H, 3), round(1 - (x + w) / W, 3), round(1 - (y + h) / H, 3)]

    out_list += [{'name': '16:9 tight on focus', 'crop': window(16 / 9, .6, fx, fy)},
                 {'name': '3:1 strip through focus', 'crop': window(3, 1, fx, fy)},
                 {'name': '2:3 tall on focus', 'crop': window(2 / 3, 1, fx, fy)},
                 {'name': '16:9 focus on left third', 'crop': window(16 / 9, .75, fx + .25, fy)},
                 {'name': '16:9 focus on right third', 'crop': window(16 / 9, .75, fx - .25, fy)}]
    cell = 300
    sheet = Image.new('RGB', (3 * (cell + 12), 2 * (cell * 2 // 3 + 34)), 'white')
    draw = ImageDraw.Draw(sheet)
    for n, item in enumerate(out_list):
        l, t, r, b = item['crop']
        part = im.crop((round(l * W), round(t * H), round(W - r * W), round(H - b * H)))
        part.thumbnail((cell, cell * 2 // 3))
        x, y = (n % 3) * (cell + 12), (n // 3) * (cell * 2 // 3 + 34) + 18
        draw.text((x, y - 16), f"{n + 1}. {item['name']}", fill=(200, 0, 0), font=_font(13))
        sheet.paste(part, (x, y))
    buffer = io.BytesIO()
    sheet.save(buffer, 'JPEG', quality=82)
    return out_list, buffer.getvalue()


TONES = {'dark': (40, 40, 44), 'mid': (150, 150, 152), 'light': (226, 226, 228), 'accent': (200, 70, 50)}
GROUNDS = {'light': (255, 255, 255), 'dark': (28, 28, 30), 'mid': (170, 170, 172)}


def sketch(arrangements):
    """Grey-block thumbnails of several arrangements (or of a reference's structure) side by side.

    Each arrangement: {"name": "...", "ground": "light|dark|mid", "blocks": [[x, y, w, h, tone, label], ...]}
    with x, y, w, h in slide inches (13.333 x 7.5) and tone dark|mid|light|accent.
    """
    w, h = 320, 180
    scale = w / 13.333
    cols = min(3, len(arrangements))
    rows = (len(arrangements) + cols - 1) // cols
    anchored = any(item.get('_anchor_path') for item in arrangements)
    top = (h // 2 + 22) if anchored else 0  # room for the anchor's mass study above each sketch
    out = Image.new('RGB', (cols * (w + 16), rows * (h + 30 + top)), 'white')
    draw = ImageDraw.Draw(out)
    for n, item in enumerate(arrangements):
        x0, y0 = (n % cols) * (w + 16), (n // cols) * (h + 30 + top) + 18
        label = f"{n + 1}. {str(item.get('name', ''))[:30]}"
        if item.get('task_fit') is not None:
            label += f"  表达 {item['task_fit']}/5"
        elif item.get('typicality') is not None:
            label += f"  典型度 {item['typicality']}"
        draw.text((x0, y0 - 17), label, fill=(200, 0, 0), font=_font(14))
        if item.get('_anchor_path'):
            ref = _load(item['_anchor_path'])
            rw = round((h // 2) * ref.width / ref.height)
            out.paste(notan(ref.convert('L'), (min(rw, w), h // 2)), (x0, y0))
            draw.text((x0 + min(rw, w) + 6, y0 + 2), '参照结构', fill=(120, 120, 120), font=_font(12))
            y0 += h // 2 + 6
        elif item.get('concept'):
            draw.text((x0, y0 + 2), '概念：' + str(item['concept'])[:34], fill=(80, 80, 80), font=_font(12))
            y0 += h // 2 + 6 if anchored else 0
        page = Image.new('RGB', (w, h), GROUNDS.get(item.get('ground', 'light'), GROUNDS['light']))
        pd = ImageDraw.Draw(page)
        for block in item.get('blocks', []):
            x, y, bw, bh, tone = block[:5]
            box = [x * scale, y * scale, (x + bw) * scale, (y + bh) * scale]
            pd.rectangle(box, fill=TONES.get(tone, TONES['mid']))
            if len(block) > 5 and block[5]:
                pd.text((box[0] + 3, box[1] + 2), str(block[5])[:18], font=_font(12),
                        fill=(255, 255, 255) if tone in ('dark', 'accent') else (60, 60, 60))
        out.paste(page, (x0, y0))
        draw.rectangle([x0 - 1, y0 - 1, x0 + w, y0 + h], outline=(180, 180, 180))
    buffer = io.BytesIO()
    out.save(buffer, 'JPEG', quality=85)
    return buffer.getvalue()


def fresh_eyes(path):
    """See your own page as a stranger would: blurred, stamp-sized, mirrored, and as masses."""
    im = _load(path)
    w, h = 400, round(400 * im.height / im.width)
    base = im.resize((w, h))
    views = [('blur', base.filter(ImageFilter.GaussianBlur(6))),
             ('stamp', im.resize((96, round(96 * h / w))).resize((w, h), Image.NEAREST)),
             ('mirror', base.transpose(Image.FLIP_LEFT_RIGHT)),
             ('masses', notan(base.convert('L'), (w, h)))]
    out = Image.new('RGB', (w * 2 + 10, (h + 18) * 2), 'white')
    draw = ImageDraw.Draw(out)
    for i, (label, view) in enumerate(views):
        x, y = (i % 2) * (w + 10), (i // 2) * (h + 18)
        draw.text((x, y), label, fill=(200, 0, 0)); out.paste(view, (x, y + 16))
    buffer = io.BytesIO()
    out.save(buffer, 'JPEG', quality=82)
    return buffer.getvalue()


class DesignStudy:
    def __init__(self, cfg, job, *, trajectory=None):
        self.cfg = cfg; self.job = Path(job).resolve(); self.trajectory = trajectory
        self.audience_first = reference_transfer_enabled(cfg)
        self._sketch_draws = {}

    def specs(self):
        spec = {'type': 'function', 'name': TOOL, 'description': (
            'Study a reference image you saved in this task (a slide, poster, painting, film still, photograph, editorial '
            'page) the way designers do: a mass study (light/mid/dark shapes with texture removed) shows the composition '
            'underneath the content, plus thirds grid, a rough focal mark, quiet space and the palette with area shares. '
            'Read it yourself: where the eye lands first and where it goes next, how the big shapes balance or pull, what '
            'is grouped, what is left empty and why the whole works; then decide what this page takes from it. With '
            'compare (a rendered page) it shows reference and page side by side with both mass studies, so you can see '
            'whether the page has the structure you meant to borrow and what to change.'),
            'inputSchema': {'type': 'object', 'additionalProperties': False, 'properties': {
                'file': {'type': 'string', 'description': 'Task-relative image path, e.g. references/pinterest/2.jpg'},
                'compare': {'type': 'string', 'description': 'Optional task-relative render of your page to set beside it.'},
                'sketch': {'type': 'array', 'maxItems': 9, 'items': {'type': 'object'},
                           'description': 'Instead of a reference: grey-block thumbnails before building. Each item '
                                          '{"name", "ground": light|dark|mid, "blocks": [[x, y, w, h, tone, label]], and for three or '
                                          'more options "anchor": a saved reference image whose structure it carries over, or '
                                          '"concept": one sentence, plus "typicality": 0-1} in slide '
                                          'inches (13.333 x 7.5), tone dark|mid|light|accent. Sketch options anchored outside your habits '
                                          '(a master\'s structure, another field\'s structure, a one-sentence concept) that differ in '
                                          'focus, title bar and figure-ground, or rebuild a reference\'s structure in blocks (a '
                                          'master copy) before translating it to your content.'},
                'crops': {'type': 'string', 'description': 'Instead of a reference: a picture you will place; returns '
                                                           'numbered crop candidates around its focal point (tight, strip, '
                                                           'tall, off-centre) with their crop fractions for edit_objects crop.'},
                'fresh_eyes': {'type': 'string', 'description': 'Instead of a reference: your rendered page shown blurred, '
                                                                 'stamp-sized, mirrored and as masses, to see it as a stranger '
                                                                 'would: is there one focal point, does the structure hold?'},
                'sequence': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 30,
                             'description': 'Instead of a reference: your rendered pages in order, shown as a strip over their '
                                            'mass studies to judge the rhythm of the deck (peaks, working pages, rests).'}}}}
        if self.audience_first:
            props = spec['inputSchema']['properties']
            props['sketch']['description'] = (
                'Show grey-block alternatives in slide inches, each with name, ground, blocks '
                '[[x,y,w,h,tone,label]], an optional anchor (saved reference path), and distance '
                '(near = keeps the source\'s kind of object, middle = swaps it for one of your own, '
                'far = keeps only the principle). For a key page draw three at different distances, '
                'each naming the principle it carries. After looking, pass audience_task and rate how '
                'directly each sketch shows it with task_fit (integer 1–5), a short fit_evidence '
                'naming a visible feature or omission, and typicality (0–1, the chance a generic deck '
                'would produce it). No rating is needed just to see the sketches.')
            props['audience_task'] = {
                'type': 'string', 'description': 'With sketch: what a viewer should be able to see or compare.'}
            props['migrate'] = {
                'type': 'object', 'additionalProperties': False, 'required': ['file', 'page_job'],
                'properties': {
                    'file': {'type': 'string', 'description': 'Saved reference image in this task.'},
                    'page_job': {'type': 'string', 'description': 'What this page must let the audience see or compare.'},
                    'content': {'type': 'string', 'description': 'The page\'s actual facts, numbers or lines.'},
                },
                'description': 'A second model reads the reference and returns three migrations of its decision - '
                               'near, middle, far - with the roles mapped onto this page. Use it before drawing the '
                               'sketches on a key page (references/borrowing.md).'}
            props['asset_check'] = {
                'type': 'object', 'additionalProperties': False, 'required': ['file', 'detail'],
                'properties': {
                    'file': {'type': 'string', 'description': 'Task-relative candidate picture.'},
                    'detail': {'type': 'string', 'description': 'Specific visible thing the asset needs to demonstrate.'},
                    'crop': {'type': 'array', 'minItems': 4, 'maxItems': 4, 'items': {'type': 'number'},
                             'description': 'Fractions to trim on left, top, right and bottom. Default: whole image.'},
                    'width': {'type': 'integer', 'minimum': 1, 'maximum': 1200,
                              'description': 'Placement width in pixels at intended reading size. Default: 600.'},
                    'realism': {'type': 'boolean',
                                'description': 'For a generated picture meant to look like a photograph: a second model '
                                               'lists the tells that make it read as AI-generated, and what to change.'},
                },
                'description': 'Before committing a key asset, see its actual crop at placement scale and inspect the required detail. '
                               'Use realism=true on every generated photographic picture before placing it.',
            }
        return [spec]

    def _asset_check(self, args):
        path = (self.job / str(args.get('file') or '')).resolve()
        if not path.is_relative_to(self.job) or not path.is_file():
            return self._reply(False, {'status': 'not_found', 'hint': 'Use a picture inside the task.'})
        detail = args.get('detail')
        width = args.get('width', 600)
        crop = args.get('crop', [0, 0, 0, 0])
        if (not isinstance(detail, str) or not detail.strip() or type(width) is not int or not 1 <= width <= 1200
                or not isinstance(crop, list) or len(crop) != 4
                or any(type(v) not in (int, float) or not 0 <= v < 1 for v in crop)
                or crop[0] + crop[2] >= 1 or crop[1] + crop[3] >= 1):
            return self._reply(False, {'status': 'invalid', 'hint': 'Specify a visible detail, placement width and a nonempty crop.'})
        try:
            image = _load(path)
            left, top, right, bottom = crop
            w, h = image.size
            picture = image.crop((round(left*w), round(top*h), round((1-right)*w), round((1-bottom)*h)))
            if not all(picture.size):
                return self._reply(False, {'status': 'invalid', 'hint': 'The crop contains no source pixels.'})
            preview = ImageOps.contain(picture, (width, 900), Image.Resampling.LANCZOS)
        except (OSError, ValueError) as error:
            return self._reply(False, {'status': 'unreadable', 'error': str(error)})
        buffer = io.BytesIO()
        preview.save(buffer, 'JPEG', quality=90)
        realism = self._realism(picture, detail.strip()) if args.get('realism') is True else None
        return self._reply(True, {**({'realism': realism} if realism else {}),
                                  'file': str(path.relative_to(self.job)), 'detail': detail.strip(),
                                  'crop': crop, 'source_pixels': list(picture.size),
                                  'preview_pixels': list(preview.size),
                                  'meaning': 'Point to the requested detail in this actual crop. If it is missing or '
                                             'unclear, change the crop, viewpoint, asset or native explanation.'}, buffer.getvalue())

    REALISM_TELLS = ('waxy or plastic skin', 'posed stock smiles and eye contact with the camera', 'everyone attractive and '
                     'tidy', 'perfect symmetry or a centred hero object', 'uniform golden or teal-orange grading', 'glossy '
                     'over-detailed texture with no grain', 'impossible hands, fingers, tools or reflections', 'garbled '
                     'lettering', 'empty, staged surroundings', 'the same light direction on every surface')

    def _realism(self, picture, detail):
        """A second model's verdict on whether a generated picture reads as a real photograph (2026-11-26)."""
        checklist = ('Look at it at full size for: ' + '; '.join(self.REALISM_TELLS) + '. If it reads as generated, '
                     'search a real photograph first; otherwise regenerate in documentary terms (candid, available '
                     'light, mixed colour temperature, clutter, grain, people turned away or cropped, hands and objects '
                     'rather than faces) or switch to an openly illustrative style.')
        import tempfile
        import claude_vision
        if not claude_vision.available(self.cfg, 'critique'):
            return {'status': 'self_check', 'checklist': checklist}
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['verdict', 'tells', 'fix'],
                  'properties': {'verdict': {'type': 'string', 'enum': ['convincing', 'some_tells', 'obviously_generated']},
                                 'tells': {'type': 'array', 'maxItems': 8, 'items': {'type': 'string', 'maxLength': 160}},
                                 'fix': {'type': 'string', 'maxLength': 500}}}
        prompt = ('This picture was generated for a presentation and is meant to read as a real photograph of: '
                  + detail + '. Would an ordinary viewer believe it is a photograph? Name the specific visible tells '
                  'that give it away (look for: ' + '; '.join(self.REALISM_TELLS) + '). Then say concretely what would '
                  'make it convincing: a different subject framing, light, crop, imperfection, or using a real photo '
                  'or an openly illustrative style instead. Be strict; tidy stock-like images count as tells.')
        try:
            with tempfile.TemporaryDirectory(prefix='pptx-realism-') as temp:
                image = Path(temp) / 'candidate.jpg'
                ImageOps.contain(picture.convert('RGB'), (1600, 1600)).save(image, 'JPEG', quality=90)
                answer = claude_vision.ask(self.cfg, prompt, [image], schema, timeout=240, slot='critique')
            return {'status': 'reviewed', **(answer.get('structured') or {}),
                    'by': str(answer.get('adapter') or 'claude') + ':' + answer['model']}
        except claude_vision.ClaudeUnavailable as error:
            return {'status': 'self_check', 'checklist': checklist, 'note': str(error)[:200]}

    MIGRATION_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['decision', 'principle', 'migrations'],
        'properties': {
            'decision': {'type': 'string', 'maxLength': 300,
                         'description': 'What this work does that an ordinary version of the same thing would not.'},
            'principle': {'type': 'string', 'maxLength': 300,
                          'description': 'The relation behind it, stated with no subject from the source.'},
            'migrations': {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['distance', 'roles', 'page'],
                'properties': {
                    'distance': {'type': 'string', 'enum': ['near', 'middle', 'far']},
                    'roles': {'type': 'string', 'maxLength': 400,
                              'description': 'Who or what plays each of the source\'s parts on this page.'},
                    'page': {'type': 'string', 'maxLength': 600,
                             'description': 'The concrete page: what is where, at what scale, with what colour or crop.'},
                    'risk': {'type': 'string', 'maxLength': 200, 'description': 'What could make this unreadable.'}}}}}}

    def _migrate(self, args):
        """A second model's reading of the reference and three migrations of its decision (2026-11-26)."""
        path = (self.job / str(args.get('file') or '')).resolve()
        if not path.is_relative_to(self.job) or not path.is_file():
            return self._reply(False, {'status': 'not_found', 'hint': 'Use a saved picture inside the task.'})
        page_job = args.get('page_job')
        content = args.get('content') or ''
        if not isinstance(page_job, str) or not page_job.strip():
            return self._reply(False, {'status': 'invalid', 'hint': 'Say what the page must let the audience see.'})
        protocol = ('Name the decision (what an ordinary version would not do), strip it to a principle with no '
                    'subject, map its parts onto this page, then try it at near, middle and far distance '
                    '(references/borrowing.md).')
        import claude_vision
        if not claude_vision.available(self.cfg, 'advisor'):
            return self._reply(True, {'status': 'self_work', 'protocol': protocol,
                                      'prompt_to_answer_twice': ['What is the decision?', 'What principle?',
                                                                 'Who plays each role here?', 'Near / middle / far?']})
        prompt = ('You are a design director helping an author borrow from a reference without copying it. '
                  'The picture is the reference. The page the author must design is for: ' + page_job.strip() +
                  '.\nThe page\'s actual content: ' + (content.strip() or '(not supplied)') + '\n\n'
                  'Read the reference first. Say what it does that a competent but ordinary version of the same '
                  'thing would not (the decision), then state the relation behind it with none of the source\'s '
                  'subject left in it (the principle). Then give exactly three migrations onto the author\'s page: '
                  'near (keeps the kind of object the source uses), middle (the same relation carried by an object '
                  'of the author\'s own kind) and far (only the principle survives, in a form this page has not '
                  'used). For each, name who plays each of the source\'s parts, then the concrete page: what is '
                  'where, at what scale, with what colour, crop or spacing; and the risk that would make it '
                  'unreadable. Be specific to this content; a migration that would fit any page is useless.')
        def valid(value):
            rows = (value or {}).get('migrations')
            if not isinstance(rows, list) or len(rows) != 3:
                return None
            ordered = sorted(rows, key=lambda r: ['near', 'middle', 'far'].index(r.get('distance'))
                             if isinstance(r, dict) and r.get('distance') in ('near', 'middle', 'far') else 9)
            if [r.get('distance') for r in ordered] != ['near', 'middle', 'far']:
                return None
            if not all(isinstance(r.get('page'), str) and r['page'].strip() for r in ordered):
                return None
            return ordered

        try:
            answer = claude_vision.ask(self.cfg, prompt, [path], self.MIGRATION_SCHEMA, timeout=300, slot='advisor')
            value = answer.get('structured') or {}
            rows = valid(value)
            if rows is None:  # The relay does not validate the schema: ask once more for the three distances.
                retry = claude_vision.ask(self.cfg, prompt + '\nYour previous reply did not give exactly three migrations '
                                          'with distances near, middle and far. Reply again with all three.',
                                          [path], self.MIGRATION_SCHEMA, timeout=300, slot='advisor')
                value = retry.get('structured') or {}
                rows = valid(value)
            result = {'status': 'reviewed', 'reference': str(path.relative_to(self.job)),
                      'decision': value.get('decision'), 'principle': value.get('principle'),
                      'migrations': rows or value.get('migrations'),
                      'by': str(answer.get('adapter') or 'claude') + ':' + answer['model']}
            if rows is None:
                result['partial'] = True
                result['meaning'] = ('The advisor did not return three clean distances; use what is usable and work '
                                     'the missing distances yourself: ' + protocol)
            return self._reply(True, result)
        except claude_vision.ClaudeUnavailable as error:
            return self._reply(True, {'status': 'self_work', 'protocol': protocol, 'note': str(error)[:200]})

    def handle(self, params):
        args = params.get('arguments') or {}
        if self.audience_first and isinstance(args.get('migrate'), dict):
            return self._migrate(args['migrate'])
        if self.audience_first and isinstance(args.get('asset_check'), dict):
            return self._asset_check(args['asset_check'])
        if args.get('sketch'):
            items = args['sketch']
            if not isinstance(items, list) or not all(isinstance(i, dict) and isinstance(i.get('blocks'), list) for i in items):
                return self._reply(False, {'status': 'invalid', 'hint': 'sketch takes [{"name", "ground", "blocks": [[x, y, w, h, tone, label]]}]'})
            if self.audience_first or len(items) >= 3:
                problems = []; seen = set()
                for item in items:
                    name = item.get('name')
                    if not isinstance(name, str) or not name.strip() or name in seen:
                        problems.append('each sketch needs a unique non-empty name')
                    else:
                        seen.add(name)
                    anchor = item.get('anchor')
                    if anchor:
                        path = (self.job / str(anchor)).resolve()
                        if not path.is_relative_to(self.job) or not path.is_file():
                            problems.append(f'{item.get("name")}: anchor {anchor} is not a saved reference image')
                        else:
                            item['_anchor_path'] = path
                    elif not self.audience_first and not (isinstance(item.get('concept'), str) and item['concept'].strip()):
                        problems.append(f'{item.get("name")}: needs an anchor (a saved reference whose structure it carries over) or a one-sentence concept')
                    typical = item.get('typicality')
                    if not self.audience_first and (type(typical) not in (int, float) or not 0 <= typical <= 1):
                        problems.append(f'{item.get("name")}: needs typicality, the chance (0-1) a generic AI deck would produce it')
                if not self.audience_first and (not any(i.get('anchor') for i in items) or not any(i.get('concept') for i in items)):
                    problems.append('at least one option must carry over a saved reference (anchor) and one must be a concept')
                if problems:
                    return self._reply(False, {'status': 'invalid', 'problems': problems,
                                               'hint': 'Anchor options to a master or another field (painting, photograph, poster) '
                                                       'you saved, rebuild its structure in blocks, and add one concept option.'})
            try:
                image = sketch(items)
            except (TypeError, ValueError) as error:
                return self._reply(False, {'status': 'invalid', 'error': str(error)})
            if self.audience_first:
                audience_task = args.get('audience_task')
                audience_task = audience_task.strip() if isinstance(audience_task, str) else ''
                value = {'sketches': len(items), 'audience_task': audience_task,
                         'meaning': 'Compare the visible alternatives against the audience task. Use the layout with '
                                    'the clearest evidence and reading path; keep a direct solution when it works best.'}
                rated = audience_task and all(
                    type(i.get('task_fit')) is int and 1 <= i['task_fit'] <= 5
                    and isinstance(i.get('fit_evidence'), str) and i['fit_evidence'].strip() for i in items)
                if rated:
                    order = sorted(items, key=lambda i: (-i['task_fit'], i['name']))
                    highest = order[0]['task_fit']
                    value['by_task_fit'] = [{k: i[k] for k in ('name', 'task_fit', 'fit_evidence')} for i in order]
                    value['best_fit'] = [i['name'] for i in order if i['task_fit'] == highest]
                    value['meaning'] += ' Rule out anything below 4 at the viewing distance first.'
                    # Readable options only, then the least typical one: a borrowing that lands on an
                    # arrangement a generic deck would also produce has not been carried across (2026-11-26).
                    readable = [i for i in items if i['task_fit'] >= max(4, highest - 1)]
                    typed = [i for i in readable if type(i.get('typicality')) in (int, float)]
                    if typed:
                        ranked = sorted(typed, key=lambda i: (i['typicality'], -i['task_fit'], i['name']))
                        value['least_typical'] = [i['name'] for i in ranked if i['typicality'] == ranked[0]['typicality']]
                    unlabelled = [i['name'] for i in items if i.get('anchor') and not
                                  (isinstance(i.get('principle'), str) and i['principle'].strip())]
                    if unlabelled:
                        # 2026-11-27: the distances were drawn but never named, so the borrowing
                        # could not be checked against the render. Ask for the principle now.
                        value['name_the_principle'] = unlabelled
                        value['meaning'] += (' Name the principle each anchored sketch carries (what relation it took '
                                             'from the reference) and the distance (near/middle/far); the visual review '
                                             'judges the borrowing from that record.')
                        value['typicality_order'] = [{'name': i['name'], 'typicality': round(i['typicality'], 2),
                                                      'distance': i.get('distance')} for i in ranked]
                        if len({round(i['typicality'], 1) for i in typed}) == 1:
                            value['meaning'] += (' All options are about equally typical: the borrowing distances '
                                                 'were too close. Redraw, with one option that changes scale, '
                                                 'material or count, not only arrangement.')
                        else:
                            value['meaning'] += (' Among the readable options prefer least_typical; say in the page '
                                                 'notes what makes it less typical than the others.')
                    if any(i.get('distance') for i in items):
                        value['distances'] = {i.get('distance') or 'unspecified': [n['name'] for n in items
                                                                                    if (n.get('distance') or 'unspecified') == (i.get('distance') or 'unspecified')]
                                              for i in items}
                        if len({i.get('distance') for i in items} & {'near', 'middle', 'far'}) < 3:
                            value['meaning'] += (' Mark the three options near, middle and far; the far one is where '
                                                 'a new page usually comes from.')
                return self._reply(True, value, image)
            order = sorted((i.get('typicality', 1), i.get('name')) for i in items)
            value = {'sketches': len(items), 'by_typicality': [n for _, n in order],
                     'meaning': 'Each anchored sketch sits under its reference\'s mass study: does it really carry '
                                'that structure, or only the usual title bar over boxes? If the options share one '
                                'skeleton, redo them. Choose the least typical option that carries the message.'}
            if len(items) >= 3:
                names = tuple(sorted(seen))
                # Keep the first valid draw for these names even if the author rescores them.
                if names not in self._sketch_draws:
                    cutoff = median(t for t, _ in order)
                    candidates = sorted(n for t, n in order if t <= cutoff)
                    seed = hashlib.sha256(json.dumps([self.job.name, names]).encode()).digest()
                    random.Random(seed).shuffle(candidates)
                    self._sketch_draws[names] = candidates + [n for t, n in order if t > cutoff]
                first, *fallback = self._sketch_draws[names]
                value.update(try_first=first, fallback_order=fallback,
                             meaning='Make a serious attempt to build try_first. If it cannot carry the message or cannot '
                                     'be built with the available assets, take the next option in fallback_order and write '
                                     'one sentence in your notes explaining the switch.')
            return self._reply(True, value, image)
        if args.get('crops'):
            path = (self.job / str(args['crops'])).resolve()
            if not path.is_relative_to(self.job) or not path.is_file():
                return self._reply(False, {'status': 'not_found', 'hint': 'crops takes a task-relative picture.'})
            candidates, image = crops(path)
            return self._reply(True, {'candidates': candidates, 'meaning': 'A bold crop can make the page: pick the one '
                                      'that serves its focal point and open space, then pass its crop to edit_objects '
                                      'with a box of the same aspect.'}, image)
        if args.get('fresh_eyes'):
            path = (self.job / str(args['fresh_eyes'])).resolve()
            if not path.is_relative_to(self.job) or not path.is_file():
                return self._reply(False, {'status': 'not_found', 'hint': 'fresh_eyes takes a task-relative rendered page.'})
            return self._reply(True, {'meaning': 'In the blurred and stamp views, where does the eye land first? If you cannot '
                                      'point to one place, the page has no focal point. In the mirror, what looks wrong now?'},
                               fresh_eyes(path))
        if args.get('sequence'):
            paths = [(self.job / str(p)).resolve() for p in args['sequence']]
            if any(not p.is_relative_to(self.job) or not p.is_file() for p in paths):
                return self._reply(False, {'status': 'not_found', 'hint': 'sequence takes task-relative rendered page images.'})
            return self._reply(True, {'pages': len(paths), 'meaning': 'Read it like a colour script: do the planned peaks '
                                      'stand out, do working pages share a system, is there rest, or do all pages weigh '
                                      'the same?'}, strip(paths))
        path = (self.job / str(args.get('file') or '')).resolve()
        if not path.is_relative_to(self.job) or not path.is_file():
            return self._reply(False, {'status': 'not_found', 'hint': 'Pass a task-relative image path you saved or picked.'})
        other = (self.job / str(args['compare'])).resolve() if args.get('compare') else None
        if other is not None and (not other.is_relative_to(self.job) or not other.is_file()):
            return self._reply(False, {'status': 'not_found', 'hint': 'compare takes a task-relative rendered page image.'})
        try:
            if other is not None:
                return self._reply(True, {'reference': str(path.relative_to(self.job)), 'page': str(other.relative_to(self.job)),
                                          'meaning': 'Compare the mass studies first: are the big shapes, the eye path and the '
                                                     'empty field arranged as you intended? Name what differs and change the page.'},
                                   compare(path, other))
            reading, sheet = study(path)
        except OSError as error:
            return self._reply(False, {'status': 'unreadable', 'error': str(error)})
        reading['file'] = str(path.relative_to(self.job))
        reading['meaning'] = ('The numbers are rough aids (fractions from the top left; blue cells are quiet space; '
                              'value_masses are absolute, the mass study splits at this picture\'s own darkest, middle '
                              'and lightest groups). The '
                              'composition is yours to read in the mass study: eye path, big shapes, grouping, tension, '
                              'emptiness. Borrow that structure, never the picture or its content.')
        return self._reply(True, reading, sheet)

    @staticmethod
    def _reply(ok, value, image=None):
        items = [{'type': 'inputText', 'text': json.dumps(value, ensure_ascii=False)}]
        if image:
            items.append({'type': 'inputImage', 'imageUrl': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()})
        return {'success': ok, 'contentItems': items}


if __name__ == '__main__':
    import sys
    result, image = study(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_bytes(image)
