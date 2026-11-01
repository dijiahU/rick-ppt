"""Task-local crops and same-scale comparisons; no tracing or quality verdicts.

Coordinates use EXIF-oriented source pixels. Diagnostics must actually be opened
with the host image tool; producing a file is not evidence of visual inspection.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageOps
from native_batch import _scoped


def load_image(root, value):
    path = _scoped(root, value)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Image exceeds 32MB')
    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as image:
        if (image.format not in ('PNG', 'JPEG', 'WEBP') or
                getattr(image, 'n_frames', 1) != 1 or image.width * image.height > 24_000_000):
            raise ValueError('Use a single PNG/JPEG/WebP within 24 million pixels')
        oriented = ImageOps.exif_transpose(image).convert('RGBA')
    # Explicit white compositing, not black transparent pixels in comparisons.
    rgb = Image.new('RGB', oriented.size, 'white')
    rgb.paste(oriented, mask=oriented.getchannel('A'))
    return rgb, {'file': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
                 'oriented_pixels': list(rgb.size)}


def box(value, size):
    if (not isinstance(value, list) or len(value) != 4 or
            any(type(n) is not int for n in value)):
        raise ValueError('Crop box requires integer source pixels [left, top, right, bottom]')
    left, top, right, bottom = value
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError('Crop is empty or outside the image')
    return tuple(value)


def regions(root, value, source):
    if value is None:
        return []
    path = _scoped(root, value)
    if path.stat().st_size > 128 * 1024:
        raise ValueError('Region specification exceeds 128KB')
    document = json.loads(path.read_text())
    if not isinstance(document, dict):
        raise ValueError('Use an object containing regions')
    # An inspect receipt can be reused directly, but never on another source.
    if 'source' in document:
        old = document['source']
        if not isinstance(old, dict) or any(old.get(k) != source[k] for k in ('sha256', 'oriented_pixels')):
            raise ValueError('Regions belong to a different source image')
    selected = document.get('regions')
    if not isinstance(selected, list) or len(selected) > 32:
        raise ValueError('Use at most 32 explicitly selected regions')
    result, names = [], set()
    for entry in selected:
        if not isinstance(entry, dict):
            raise ValueError('Each region needs id and box')
        ident = entry.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', ident) or ident in names:
            raise ValueError('Region IDs must be unique filename-safe names')
        names.add(ident)
        result.append({'id': ident, 'box': list(box(entry.get('box'), source['oriented_pixels']))})
    return result


def output_path(root, value):
    path = Path(value)
    path = path if path.is_absolute() else root / path
    # Resolve the parent through the same task scope/symlink checks as inputs.
    parent = _scoped(root, path.parent, directory=True)
    result = parent / path.name
    if result.exists() or result.is_symlink() or path.name in ('.', '..', ''):
        raise ValueError('Choose a fresh output directory; existing evidence is preserved')
    return result


def run(root, source_path, out, *, region_file=None, grid=0, render_path=None, render_box=None):
    root = Path(root).resolve(strict=True)
    destination = output_path(root, out)
    source, source_info = load_image(root, source_path)
    selected = regions(root, region_file, source_info)
    if type(grid) is not int or grid < 0 or (grid and grid < 32):
        raise ValueError('Grid spacing is 0 (off) or at least 32 source pixels')
    if render_box is not None and render_path is None:
        raise ValueError('render_box requires a rendered image')
    rendered = aligned = render_info = None
    if render_path:
        rendered, render_info = load_image(root, render_path)
        roi = box(render_box, rendered.size) if render_box is not None else (0, 0, *rendered.size)
        rendered = rendered.crop(roi)
        # Permit at most a pixel of raster rounding. Never stretch mismatched
        # slide ratios; letterboxed slides need an explicit content crop.
        sw, sh = source.size; rw, rh = rendered.size
        if abs(rw * sh - rh * sw) > max(sw, sh, rw, rh):
            raise ValueError('Aspect ratios differ; supply the exact render_box instead of stretching')
        aligned = ImageOps.contain(rendered, source.size, Image.Resampling.LANCZOS)
        if aligned.size != source.size:
            centered = Image.new('RGB', source.size, 'white')
            centered.paste(aligned, ((sw - aligned.width) // 2, (sh - aligned.height) // 2))
            aligned = centered
        render_info = {**render_info, 'content_box': list(roi), 'aligned_pixels': list(source.size),
                       'alignment': 'uniform_contain_center; at most one pixel rounding'}
    report = {'version': 1, 'operation': 'compare' if render_path else 'inspect',
              'source': source_info, 'regions': selected, 'outputs': {},
              'inspection_claimed': False, 'quality_assessed': False,
              'note': 'Open these diagnostics with a visual tool. Pixel differences are not a fidelity score.'}
    if render_info:
        report['render'] = render_info
    with tempfile.TemporaryDirectory(prefix='.recreation-', dir=destination.parent) as temp:
        stage = Path(temp) / 'output'; stage.mkdir()
        def save(name, image):
            image.save(stage / name, format='PNG')
            return str(destination / name)
        if grid:
            guide = source.copy(); draw = ImageDraw.Draw(guide)
            for x in range(0, source.width, grid):
                draw.line((x, 0, x, source.height), fill='#d9428f')
                draw.text((x + 2, 2), str(x), fill='black', stroke_fill='white', stroke_width=1)
            for y in range(0, source.height, grid):
                draw.line((0, y, source.width, y), fill='#d9428f')
                draw.text((2, y + 2), str(y), fill='black', stroke_fill='white', stroke_width=1)
            report['outputs']['coordinate_guide'] = save('coordinate-guide.png', guide)
        def comparison(name, left, right):
            pair = Image.new('RGB', (left.width * 2, left.height), 'white')
            pair.paste(left); pair.paste(right, (left.width, 0))
            return {'source_left_render_right': save(name + '-pair.png', pair),
                    'overlay': save(name + '-overlay.png', Image.blend(left, right, .5))}
        if aligned:
            report['outputs'].update(comparison('page', source, aligned))
            report['outputs']['difference'] = save('page-difference.png', ImageChops.difference(source, aligned))
        for entry in selected:
            cropped = source.crop(entry['box'])
            entry['source_crop'] = save('region-' + entry['id'] + '-source.png', cropped)
            if aligned:
                entry.update(comparison('region-' + entry['id'], cropped, aligned.crop(entry['box'])))
        (stage / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        stage.rename(destination)
    return {**report, 'receipt': str(destination / 'receipt.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inspect', 'compare'))
    parser.add_argument('--task-root', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True, help='Fresh task-local directory under an existing parent')
    parser.add_argument('--regions', help='Task-local JSON regions or an earlier inspect receipt')
    parser.add_argument('--grid', type=int, default=0)
    parser.add_argument('--render')
    parser.add_argument('--render-box', nargs=4, type=int)
    args = parser.parse_args()
    try:
        if (args.mode == 'compare') != bool(args.render):
            raise ValueError('compare requires --render; inspect does not accept it')
        result = run(args.task_root, args.source, args.out, region_file=args.regions,
                     grid=args.grid, render_path=args.render, render_box=args.render_box)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'rejected', 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
