#!/usr/bin/env python3
"""Merge per-slide tags (JSON Lines from vision passes) into a template library index.

Each line: {"id": "t1a2b3c4d-05", "page_type": "data", "layout": "...", "description": "...",
"strength": "...", "surface": "light|dark|colour", "quality": 1-5, "keywords": "..."}.
Slides with quality 1 are dropped from search results by default (kept in the index).

  python tools/tag-template-library.py ~/.rick-ppt/reference-library/templates TAGS_DIR
"""
import json
import sys
from pathlib import Path

KEYS = ('page_type', 'layout', 'description', 'strength', 'surface', 'quality', 'keywords')
SURFACES = {'light', 'dark', 'colour'}


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
                tags[row['id']] = row
            except (ValueError, KeyError):
                bad += 1
    merged = 0
    for page in index['pages']:
        row = tags.get(page['id'])
        if not row:
            continue
        for key in KEYS:
            if row.get(key) not in (None, ''):
                page[key] = row[key]
        if page.get('surface') not in SURFACES:
            page.pop('surface', None)
        if not isinstance(page.get('quality'), int):
            page.pop('quality', None)
        merged += 1
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    missing = [p['id'] for p in index['pages'] if p['id'] not in tags]
    print(f'merged {merged}/{len(index["pages"])}, bad lines {bad}, untagged {len(missing)}', missing[:20])


if __name__ == '__main__':
    main(*sys.argv[1:3])
