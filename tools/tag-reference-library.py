#!/usr/bin/env python3
"""Merge per-slide content tags (JSON Lines from vision passes) into a reference library index.

Deck boundaries come from the brand names read on each slide: an unnamed slide inherits the
deck of its neighbour when both come from the same export group (file name without the page
suffix), so only the edges of each run decide where one deck ends and the next begins.

  python tools/tag-reference-library.py ~/.rick-ppt/reference-library/pitch-decks TAGS_DIR
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

KEYS = ('deck', 'page_type', 'layout', 'description', 'strength', 'surface', 'quality')


def group(origin):
    return re.sub(r'(-\d+)?\.(png|jpe?g|pdf)$', '', origin, flags=re.I)


def main(library, tags_dir):
    index_path = Path(library) / 'index.json'
    index = json.loads(index_path.read_text())
    tags, bad = {}, 0
    for part in sorted(Path(tags_dir).glob('*.jsonl')):
        for line in part.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                tags[str(row['id']).zfill(4)] = row
            except (ValueError, KeyError):
                bad += 1
    pages = index['pages']
    missing = [p['id'] for p in pages if p['id'] not in tags]
    for page in pages:
        row = tags.get(page['id'], {})
        for key in KEYS:
            if key in row:
                page[key] = row[key]
        page['deck'] = (page.get('deck') or '').strip()
    # Normalise spelling variants of one brand to its most common form.
    canonical = {}
    for name, _ in Counter(p['deck'] for p in pages if p['deck']).most_common():
        canonical.setdefault(name.lower(), name)
    for page in pages:
        page['deck'] = canonical.get(page['deck'].lower(), page['deck'])
    # Fill unnamed slides from neighbours in the same export group (forward, then backward).
    for order in (range(len(pages)), range(len(pages) - 1, -1, -1)):
        last = None
        for i in order:
            page = pages[i]
            if page['deck']:
                last = (group(page['origin']), page['deck'])
            elif last and last[0] == group(page['origin']):
                page['deck'] = last[1]; page['deck_inferred'] = True
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    decks = Counter(p['deck'] or '(unknown)' for p in pages)
    print(f'tagged {len(pages) - len(missing)}/{len(pages)} slides, bad lines {bad}, missing {missing[:10]}')
    print(f'{len(decks)} decks:', ', '.join(f'{d} ({n})' for d, n in decks.most_common(40)))
    print('page types:', dict(Counter(p.get('page_type') for p in pages).most_common()))
    print('quality:', dict(sorted(Counter(p.get('quality') for p in pages).items(), key=lambda x: str(x[0]))))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
