"""Export a fresh complete candidate and atomically declare its exact file.

Reuses native export/render and the existing authored decision check. This is a
candidate checkpoint, not independent review, aesthetic approval or delivery.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import uuid
import zipfile

if __package__:
    from .page_design import scoped, read
    from .pptx_core.common import NS, PptxError, sha256
    from .pptx_core.package import select, export
    from .workflow_decisions import validate_plan, MAX_PLAN_BYTES
else:
    from page_design import scoped, read
    from pptx_core.common import NS, PptxError, sha256
    from pptx_core.package import select, export
    from workflow_decisions import validate_plan, MAX_PLAN_BYTES


def _declare(root, value, previous):
    target = scoped(root, 'delivery.json')
    current = read(root, 'delivery.json', 10000) if target.exists() else None
    if current != previous:
        raise ValueError('Delivery declaration changed while saving candidate')
    pending = root / ('.delivery-' + uuid.uuid4().hex + '.json')
    try:
        with pending.open('xb') as stream:
            stream.write((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def save_candidate(task_root, workspace, output, *, allow_legacy=False):
    root = Path(task_root).resolve(strict=True)
    ws = select(scoped(root, workspace))
    scoped(root, ws.home)
    scoped(root, ws.root)
    destination = scoped(root, output)
    declaration = scoped(root, 'delivery.json')
    lock = scoped(root, '.candidate-save.lock')
    with os.fdopen(os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        previous = read(root, 'delivery.json', 10000) if declaration.exists() else None
        request = json.loads(read(root, 'request.json')) if scoped(root, 'request.json').exists() else {}
        # A new path is created by native export; existing exports are immutable.
        artifact = export(ws, destination)
        from lxml import etree
        with zipfile.ZipFile(artifact) as archive:
            tree = etree.fromstring(archive.read('ppt/presentation.xml'))
            count = len(tree.findall('p:sldIdLst/p:sldId', NS))
        expected = request.get('pages')
        if type(expected) is int and expected > 0 and count != expected:
            raise ValueError('Complete candidate page count differs from request')
        has_plan = scoped(root, 'decision-plan.json').exists()
        has_outline = scoped(root, 'outline.json').exists()
        if has_plan != has_outline:
            raise ValueError('Retain and reconcile both outline and decision plan before declaring a candidate')
        authored = None
        if has_plan:
            plan = json.loads(read(root, 'decision-plan.json', MAX_PLAN_BYTES))
            outline = json.loads(read(root, 'outline.json'))
            authored = validate_plan(plan, outline, stage='authored', root=root,
                                     artifact=artifact,
                                     mode=request.get('mode') or plan.get('task', {}).get('operation') or 'create',
                                     allow_legacy=allow_legacy,
                                     require_click_reveal=False if allow_legacy else None)
        digest = sha256(artifact)
        value = {'path': str(artifact), 'workspace': str(ws.root)}
        _declare(root, value, previous)
        return {'ok': True, 'candidate': value, 'sha256': digest, 'pages': count,
                'authored': authored, 'native_render': ws.state.get('last_render'),
                'meaning': 'Complete exported candidate declared. Independent review and host delivery checks remain required.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-root', default='.')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--output', required=True, help='Fresh task-local PPTX; native export preserves existing versions')
    parser.add_argument('--allow-legacy', action='store_true', help='Only for an explicitly historically admitted contract')
    args = parser.parse_args()
    try:
        result = save_candidate(args.task_root, args.workspace, args.output, allow_legacy=args.allow_legacy)
    except (OSError, ValueError, KeyError, PptxError, zipfile.BadZipFile) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
