#!/usr/bin/env python3
"""Build a local reference library of real slides from an exported folder (PNG/JPG/PDF).

Each page becomes a 1280-px JPEG with automatic tone (light/dark) and dominant colours.
Single tall PDF/PNG pages that hold a whole deck stacked vertically are split into 16:9 slides.
The library lives outside the repository (licences belong to the original authors).

  python tools/build-reference-library.py SOURCE_DIR --name pitch-decks \
      --source "Figma Community: 100+ Pitch decks that raised funds" --license "see source page"
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = 80_000_000
ROOT = Path.home() / '.rick-ppt' / 'reference-library'
WIDTH = 1280


def pages(path, temp):
    """Yield PIL images for every slide in a file."""
    if path.suffix.lower() == '.pdf':
        out = Path(temp) / path.stem
        subprocess.run(['pdftoppm', '-r', '110', '-png', str(path), str(out)], check=True, capture_output=True)
        files = sorted(Path(temp).glob(path.stem + '*.png'))
    else:
        files = [path]
    for f in files:
        with Image.open(f) as im:
            im = im.convert('RGB')
            ratio = im.height / im.width
            # A whole deck stacked into one tall page has no reliable slide boundaries; skip it
            # rather than store crops that cut across two slides.
            if 0.4 <= ratio <= 1.0:
                yield im.copy()


def describe(im):
    small = im.resize((64, 36))
    pixels = list(small.get_flattened_data()) if hasattr(small, 'get_flattened_data') else list(small.getdata())
    luminance = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in pixels) / len(pixels)
    quant = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    palette = quant.getpalette()[:18]
    counts = sorted(quant.getcolors(), reverse=True)
    colours = ['%02X%02X%02X' % tuple(palette[i * 3:i * 3 + 3]) for _, i in counts[:4]]
    return {'tone': 'light' if luminance >= 150 else 'dark' if luminance < 90 else 'mid',
            'luminance': round(luminance), 'colors': colours}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', type=Path)
    ap.add_argument('--name', required=True)
    ap.add_argument('--source-label', default='')
    ap.add_argument('--license', default='See the original source; use as reference, credit when shown.')
    args = ap.parse_args()
    target = ROOT / args.name
    (target / 'pages').mkdir(parents=True, exist_ok=True)
    items = []
    files = sorted(p for p in args.source.iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.pdf'))
    with tempfile.TemporaryDirectory() as temp:
        for path in files:
            try:
                for n, im in enumerate(pages(path, temp), 1):
                    ident = f'{len(items) + 1:04d}'
                    if im.width > WIDTH:
                        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)))
                    out = target / 'pages' / f'{ident}.jpg'
                    im.save(out, quality=85)
                    items.append({'id': ident, 'file': f'pages/{ident}.jpg', 'origin': path.name,
                                  'page': n, 'size': list(im.size), **describe(im)})
            except (OSError, subprocess.CalledProcessError) as error:
                print('skip', path.name, error)
    index = {'name': args.name, 'source': args.source_label, 'license': args.license, 'count': len(items), 'pages': items}
    (target / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1))
    tones = {}
    for item in items:
        tones[item['tone']] = tones.get(item['tone'], 0) + 1
    print(f'{len(items)} slides -> {target}', tones)


if __name__ == '__main__':
    main()
