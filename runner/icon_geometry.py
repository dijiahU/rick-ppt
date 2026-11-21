"""Convert a library icon's SVG body into native PowerPoint path commands.

Input is untrusted text from an icon API. It is parsed without entities or
network, and only plain geometry is accepted: path/circle/ellipse/rect/line/
polyline/polygon inside optional <g>. Transforms, masks, clips, gradients,
text, images, <use> and partial opacity are rejected rather than approximated,
so a converted icon looks like its source or is not offered at all.

Output layers use absolute M/L/C/Z in viewBox units, matching
native_canvas.add_path. Fill is even-odd, as PowerPoint renders custGeom.
"""
import math
import re
from lxml import etree as E

SVG = 'http://www.w3.org/2000/svg'
SHAPES = {'path', 'circle', 'ellipse', 'rect', 'line', 'polyline', 'polygon'}
PAINT = ('fill', 'stroke', 'stroke-width', 'fill-rule', 'stroke-linecap', 'stroke-linejoin')
IGNORED = {'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit', 'fill-rule', 'clip-rule', 'd', 'cx', 'cy', 'r',
           'rx', 'ry', 'x', 'y', 'width', 'height', 'x1', 'y1', 'x2', 'y2', 'points', 'fill', 'stroke',
           'stroke-width', 'id', 'class', 'opacity', 'fill-opacity', 'stroke-opacity', 'color', 'vector-effect'}
MAX_COMMANDS = 4000


class IconError(ValueError):
    pass


def _number(value, name):
    try:
        number = float(str(value).strip().removesuffix('px'))
    except (TypeError, ValueError):
        raise IconError('Non-numeric ' + name) from None
    if not math.isfinite(number) or abs(number) > 100000:
        raise IconError('Out-of-range ' + name)
    return number


def _paint(value):
    """True/False for painted; currentColor and explicit colours both paint."""
    if value is None:
        return None
    value = value.strip().lower()
    if value in ('none', 'transparent'):
        return False
    if value.startswith('url('):
        raise IconError('Gradients/patterns are unsupported')
    return True


TOKEN = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?')


def _arc_to_cubic(x1, y1, rx, ry, phi, large, sweep, x2, y2):
    """SVG endpoint arc to cubic Beziers (SVG 1.1 implementation notes F.6)."""
    if (x1, y1) == (x2, y2):
        return []
    if rx == 0 or ry == 0:
        return [('L', x2, y2)]
    rx, ry = abs(rx), abs(ry)
    cos, sin = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    xp, yp = cos * dx + sin * dy, -sin * dx + cos * dy
    lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    den = rx * rx * yp * yp + ry * ry * xp * xp
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        coef = -coef
    cxp, cyp = coef * rx * yp / ry, -coef * ry * xp / rx
    cx = cos * cxp - sin * cyp + (x1 + x2) / 2
    cy = sin * cxp + cos * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = angle(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    dt = angle((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    segments = max(1, math.ceil(abs(dt) / (math.pi / 2) - 1e-9))
    delta = dt / segments
    k = 4 / 3 * math.tan(delta / 4)
    out = []
    for i in range(segments):
        a1, a2 = t1 + i * delta, t1 + (i + 1) * delta
        e1x, e1y = math.cos(a1), math.sin(a1)
        e2x, e2y = math.cos(a2), math.sin(a2)

        def point(px, py):
            px, py = px * rx, py * ry
            return cos * px - sin * py + cx, sin * px + cos * py + cy
        c1 = point(e1x - k * e1y, e1y + k * e1x)
        c2 = point(e2x + k * e2y, e2y - k * e2x)
        end = point(e2x, e2y)
        out.append(('C', *c1, *c2, *end))
    return out


def parse_path(d):
    """SVG path data to absolute M/L/C/Z commands (Q/T/S/H/V/A converted)."""
    tokens = TOKEN.findall(d or '')
    if not tokens or tokens[0] not in 'Mm':
        raise IconError('Path data must start with a move')
    out, i = [], 0
    x = y = sx = sy = 0.0
    last_c = last_q = None
    command = None

    def take(n):
        nonlocal i
        values = tokens[i:i + n]
        if len(values) != n or any(v.isalpha() for v in values):
            raise IconError('Truncated path data')
        i += n
        return [float(v) for v in values]
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]; i += 1
        elif command is None:
            raise IconError('Missing path command')
        rel = command.islower(); kind = command.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if kind == 'Z':
            out.append(('Z',)); x, y = sx, sy; last_c = last_q = None
            continue
        if kind == 'M':
            px, py = take(2); x, y = ox + px, oy + py; sx, sy = x, y
            out.append(('M', x, y)); command = 'l' if rel else 'L'; last_c = last_q = None
        elif kind == 'L':
            px, py = take(2); x, y = ox + px, oy + py; out.append(('L', x, y)); last_c = last_q = None
        elif kind == 'H':
            (px,) = take(1); x = ox + px; out.append(('L', x, y)); last_c = last_q = None
        elif kind == 'V':
            (py,) = take(1); y = oy + py; out.append(('L', x, y)); last_c = last_q = None
        elif kind in 'CS':
            if kind == 'C':
                a, b, c, e, f, g = take(6); c1 = (ox + a, oy + b)
            else:
                c, e, f, g = take(4)
                c1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
            c2 = (ox + c, oy + e); end = (ox + f, oy + g)
            out.append(('C', *c1, *c2, *end)); last_c = c2; last_q = None; x, y = end
        elif kind in 'QT':
            if kind == 'Q':
                a, b, f, g = take(4); q = (ox + a, oy + b)
            else:
                f, g = take(2)
                q = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
            end = (ox + f, oy + g)
            c1 = (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y))
            c2 = (end[0] + 2 / 3 * (q[0] - end[0]), end[1] + 2 / 3 * (q[1] - end[1]))
            out.append(('C', *c1, *c2, *end)); last_q = q; last_c = None; x, y = end
        elif kind == 'A':
            rx, ry, phi = take(3)
            # Flags may be written without separators ("a1 1 0 01 2 2").
            flags = []
            while len(flags) < 2:
                if i >= len(tokens) or tokens[i].isalpha():
                    raise IconError('Truncated arc flags')
                text = tokens[i]; i += 1
                while text and len(flags) < 2:
                    if text[0] not in '01':
                        raise IconError('Invalid arc flag')
                    flags.append(int(text[0])); text = text[1:]
                if text:
                    tokens.insert(i, text)
            px, py = take(2); end = (ox + px, oy + py)
            out.extend(_arc_to_cubic(x, y, rx, ry, phi, flags[0], flags[1], *end))
            x, y = end; last_c = last_q = None
        if len(out) > MAX_COMMANDS:
            raise IconError('Icon is too complex')
    return out


def _ellipse(cx, cy, rx, ry):
    k = 0.5522847498
    return [('M', cx + rx, cy),
            ('C', cx + rx, cy + k * ry, cx + k * rx, cy + ry, cx, cy + ry),
            ('C', cx - k * rx, cy + ry, cx - rx, cy + k * ry, cx - rx, cy),
            ('C', cx - rx, cy - k * ry, cx - k * rx, cy - ry, cx, cy - ry),
            ('C', cx + k * rx, cy - ry, cx + rx, cy - k * ry, cx + rx, cy), ('Z',)]


def _shape_commands(element, tag):
    get = lambda name, default=None: element.get(name, default)
    if tag == 'path':
        return parse_path(get('d'))
    if tag == 'circle':
        r = _number(get('r', 0), 'r')
        return _ellipse(_number(get('cx', 0), 'cx'), _number(get('cy', 0), 'cy'), r, r) if r > 0 else []
    if tag == 'ellipse':
        rx, ry = _number(get('rx', 0), 'rx'), _number(get('ry', 0), 'ry')
        return _ellipse(_number(get('cx', 0), 'cx'), _number(get('cy', 0), 'cy'), rx, ry) if rx > 0 and ry > 0 else []
    if tag == 'rect':
        x, y = _number(get('x', 0), 'x'), _number(get('y', 0), 'y')
        w, h = _number(get('width', 0), 'width'), _number(get('height', 0), 'height')
        if w <= 0 or h <= 0:
            return []
        rx = get('rx'); ry = get('ry')
        rx = _number(rx, 'rx') if rx is not None else None
        ry = _number(ry, 'ry') if ry is not None else None
        rx = rx if rx is not None else (ry or 0); ry = ry if ry is not None else rx
        rx, ry = min(rx, w / 2), min(ry, h / 2)
        if not rx or not ry:
            return [('M', x, y), ('L', x + w, y), ('L', x + w, y + h), ('L', x, y + h), ('Z',)]
        d = (f'M{x + rx} {y}H{x + w - rx}A{rx} {ry} 0 0 1 {x + w} {y + ry}V{y + h - ry}'
             f'A{rx} {ry} 0 0 1 {x + w - rx} {y + h}H{x + rx}A{rx} {ry} 0 0 1 {x} {y + h - ry}'
             f'V{y + ry}A{rx} {ry} 0 0 1 {x + rx} {y}Z')
        return parse_path(d)
    if tag == 'line':
        return [('M', _number(get('x1', 0), 'x1'), _number(get('y1', 0), 'y1')),
                ('L', _number(get('x2', 0), 'x2'), _number(get('y2', 0), 'y2'))]
    values = [float(v) for v in TOKEN.findall(get('points', '')) if not v.isalpha()]
    if len(values) < 4 or len(values) % 2:
        raise IconError('Invalid points')
    commands = [('M', values[0], values[1])] + [('L', values[n], values[n + 1]) for n in range(2, len(values), 2)]
    return commands + ([('Z',)] if tag == 'polygon' else [])


def convert(body, width, height):
    """Return {'viewbox': [w, h], 'layers': [...]} or raise IconError."""
    width, height = _number(width, 'width'), _number(height, 'height')
    if not 0 < width <= 4096 or not 0 < height <= 4096:
        raise IconError('Invalid icon viewBox')
    if not isinstance(body, str) or len(body) > 200000:
        raise IconError('Invalid icon body')
    parser = E.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_comments=True)
    try:
        root = E.fromstring(f'<svg xmlns="{SVG}">{body}</svg>'.encode(), parser)
    except E.XMLSyntaxError:
        raise IconError('Malformed icon SVG') from None
    layers = []

    def visit(element, inherited):
        if not isinstance(element.tag, str):
            return
        tag = E.QName(element).localname
        if E.QName(element).namespace not in (SVG, None):
            raise IconError('Foreign SVG element')
        if tag in ('title', 'desc'):
            return
        if tag not in SHAPES | {'g', 'svg'}:
            raise IconError('Unsupported SVG element: ' + tag)
        attributes = dict(element.attrib)
        if 'style' in attributes:
            for part in attributes.pop('style').split(';'):
                if ':' in part:
                    key, value = part.split(':', 1); attributes.setdefault(key.strip(), value.strip())
        for key in attributes:
            local = E.QName(key).localname
            if local == 'transform' or local.startswith(('mask', 'clip-path', 'filter')) or local in ('href',):
                raise IconError('Transforms/masks/clips/references are unsupported')
        for key in ('opacity', 'fill-opacity', 'stroke-opacity'):
            if key in attributes and _number(attributes[key], key) < 0.999:
                raise IconError('Partial opacity (duotone) is unsupported')
        state = dict(inherited)
        for key in PAINT:
            if key in attributes:
                state[key] = attributes[key]
        if tag in SHAPES:
            commands = _shape_commands(element, tag)
            fill = _paint(state.get('fill'))
            fill = True if fill is None else fill
            stroke = bool(_paint(state.get('stroke')))
            if tag in ('line', 'polyline'):
                fill = False
            if commands and (fill or stroke):
                width_value = _number(state.get('stroke-width', 1), 'stroke-width') if stroke else 0
                layer = {'fill': fill, 'stroke': stroke, 'stroke_width': width_value}
                if layers and all(layers[-1][k] == layer[k] for k in layer):
                    layers[-1]['commands'].extend(commands)
                else:
                    layers.append({**layer, 'commands': list(commands)})
        for child in element:
            visit(child, state)
    visit(root, {})
    total = sum(len(layer['commands']) for layer in layers)
    if not layers or not any(len(layer['commands']) > 1 for layer in layers):
        raise IconError('Icon has no drawable geometry')
    if total > MAX_COMMANDS:
        raise IconError('Icon is too complex')
    for layer in layers:
        layer['commands'] = [[c[0], *[round(v, 4) for v in c[1:]]] for c in layer['commands']]
    return {'viewbox': [width, height], 'layers': layers}


def _flatten(commands, steps=10):
    """Polylines per subpath for preview rendering only."""
    paths, current, x, y = [], [], 0.0, 0.0
    for command in commands:
        kind = command[0]
        if kind == 'M':
            if len(current) > 1:
                paths.append((current, False))
            x, y = command[1:3]; current = [(x, y)]
        elif kind == 'L':
            x, y = command[1:3]; current.append((x, y))
        elif kind == 'C':
            x0, y0 = x, y; c1x, c1y, c2x, c2y, x, y = command[1:]
            for n in range(1, steps + 1):
                t = n / steps; u = 1 - t
                current.append((u ** 3 * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t ** 3 * x,
                                u ** 3 * y0 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t ** 3 * y))
        elif kind == 'Z':
            if len(current) > 1:
                paths.append((current, True))
            current = [current[0]] if current else []
    if len(current) > 1:
        paths.append((current, False))
    return paths


def render(icon, size=96, ink=(20, 20, 20)):
    """Preview raster of the converted geometry (what PowerPoint will draw)."""
    from PIL import Image, ImageChops, ImageDraw
    scale_factor = 4
    big = size * scale_factor
    vw, vh = icon['viewbox']; scale = big * 0.84 / max(vw, vh)
    ox, oy = (big - vw * scale) / 2, (big - vh * scale) / 2
    image = Image.new('L', (big, big), 0)
    for layer in icon['layers']:
        subpaths = _flatten(layer['commands'])
        mapped = [([(ox + px * scale, oy + py * scale) for px, py in points], closed) for points, closed in subpaths]
        if layer['fill']:
            mask = Image.new('1', (big, big), 0)
            for points, _ in mapped:
                if len(points) > 2:
                    one = Image.new('1', (big, big), 0)
                    ImageDraw.Draw(one).polygon(points, fill=1)
                    mask = ImageChops.logical_xor(mask, one)
            image.paste(255, mask=mask)
        if layer['stroke']:
            draw = ImageDraw.Draw(image)
            width = max(1, round(layer['stroke_width'] * scale))
            for points, closed in mapped:
                draw.line(points + ([points[0]] if closed else []), fill=255, width=width, joint='curve')
    image = image.resize((size, size), Image.LANCZOS)
    out = Image.new('RGB', (size, size), (255, 255, 255))
    out.paste(Image.new('RGB', (size, size), ink), mask=image)
    return out
