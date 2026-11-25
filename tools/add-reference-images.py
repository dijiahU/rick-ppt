#!/usr/bin/env python3
"""Import a folder of reference images (posters, paintings, stills) into a named
reference-library collection so pptx_reference_library can search them.

    python3 tools/add-reference-images.py ~/Pictures/posters --name posters \
        --provenance posters-provenance.json

Copies each image, appends an index entry and leaves style fields empty; run
tools/annotate-template-library.py --library <collection> to add them, or skip
annotation — the collection also works as raw material for study.

provenance.json (optional):
    {"file.jpg": {"title": "...", "creator": "...", "source": "https://...", "note": "..."}}
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image

ROOT = Path.home() / '.rick-ppt/reference-library'
EXTS = ('.jpg', '.jpeg', '.png', '.webp')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', type=Path)
    ap.add_argument('--name', default='posters')
    ap.add_argument('--library-root', type=Path, default=ROOT)
    ap.add_argument('--provenance', type=Path)
    ap.add_argument('--category', default='参考图')
    ap.add_argument('--quality', type=float, default=4)
    args = ap.parse_args()

    target = args.library_root / args.name
    (target / 'pages').mkdir(parents=True, exist_ok=True)
    index_path = target / 'index.json'
    index = (json.loads(index_path.read_text()) if index_path.is_file() else
             {'name': args.name, 'kind': 'images', 'source': 'personal reference collection',
              'license': 'Personal reference use; do not redistribute.', 'count': 0, 'templates': [], 'pages': []})
    provenance = json.loads(args.provenance.read_text()) if args.provenance and args.provenance.is_file() else {}
    known = {page['file'] for page in index['pages']}
    added = []
    for path in sorted(args.source.rglob('*')):
        if path.suffix.lower() not in EXTS or not path.is_file():
            continue
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in path.stem)[:60] or 'image'
        ident = f'i{safe.lower()}'
        n, candidate = 1, ident
        taken = {page['id'] for page in index['pages']}
        while candidate in taken:
            n += 1
            candidate = f'{ident}-{n}'
        rel = f'pages/{candidate}{path.suffix.lower()}'
        if rel in known:
            continue
        shutil.copy2(path, target / rel)
        with Image.open(target / rel) as im:
            size = list(im.size)
        info = provenance.get(path.name, {})
        index['pages'].append({
            'id': candidate, 'file': rel, 'kind': 'image', 'size': size,
            'category': args.category, 'quality': args.quality,
            'title': info.get('title') or path.stem,
            'creator': info.get('creator'), 'source': info.get('source'),
            'description': info.get('note') or '', 'annotated': None})
        added.append(candidate)
    index['pages'] = [p for p in index['pages'] if p.get('id') and p.get('file')]
    index['count'] = len(index['pages'])
    index['updated'] = datetime.now().strftime('%Y-%m-%d')
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    print(f'{len(added)} images added; {index["count"]} in {target}')


if __name__ == '__main__':
    main()
