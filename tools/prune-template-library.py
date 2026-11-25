#!/usr/bin/env python3
"""Remove low-quality pages from the local template library.

Deletes matching entries from index.json, their page images and — when a
template has no pages left — the template record and its .pptx file.

    python3 tools/prune-template-library.py --quality 1            # dry run
    python3 tools/prune-template-library.py --quality 1 --delete
    python3 tools/prune-template-library.py --ids t1234abcd-03 ...  # specific pages
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

DEFAULT = Path.home() / '.rick-ppt/reference-library/templates'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--library', type=Path, default=DEFAULT)
    ap.add_argument('--quality', default='', help='Comma-separated quality scores to remove, e.g. 1,2')
    ap.add_argument('--ids', nargs='*', default=[], help='Explicit page ids to remove')
    ap.add_argument('--delete', action='store_true', help='Actually delete; default is a dry run')
    args = ap.parse_args()

    index_path = args.library / 'index.json'
    index = json.loads(index_path.read_text())
    scores = {float(x) for x in args.quality.split(',') if x.strip()}
    wanted = set(args.ids)
    doomed = [p for p in index['pages']
              if p['id'] in wanted or (scores and float(p.get('quality') or 3) in scores)]
    if not doomed:
        print('nothing to remove')
        return

    keep_ids = {p['id'] for p in index['pages']} - {p['id'] for p in doomed}
    keep_templates = {p['template'] for p in index['pages'] if p['id'] in keep_ids}
    drop_templates = [t for t in index['templates'] if t['id'] not in keep_templates]

    print(f'pages to remove: {len(doomed)}')
    for p in doomed:
        print(f"  {p['id']}  q={p.get('quality')}  [{p['category']}] {p['deck'][:28]}")
    print(f'templates left empty (removed with their file): {len(drop_templates)}')
    for t in drop_templates:
        print(f"  {t['id']}  [{t['category']}] {t['name'][:40]}")
    if not args.delete:
        print('\ndry run; add --delete to apply')
        return

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy2(index_path, index_path.with_name(f'index.backup-{stamp}.json'))
    for p in doomed:
        (args.library / p['file']).unlink(missing_ok=True)
    for t in drop_templates:
        (args.library / t['file']).unlink(missing_ok=True)

    index['pages'] = [p for p in index['pages'] if p['id'] in keep_ids]
    index['templates'] = [t for t in index['templates'] if t['id'] in keep_templates]
    index['count'] = len(index['pages'])
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    print(f"\nremoved {len(doomed)} pages, {len(drop_templates)} templates; "
          f"library now {len(index['pages'])} pages / {len(index['templates'])} templates")
    print(f'backup: index.backup-{stamp}.json')


if __name__ == '__main__':
    main()
