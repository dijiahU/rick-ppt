#!/usr/bin/env python3
"""Nonblocking task-local material requests. No network or host imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

ROOT = Path(__file__).absolute().parent
MAX_REQUEST = 64 * 1024
IDENT = re.compile(r'[0-9a-f]{32}')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read(name, limit=2 * 1024 * 1024, optional=False):
    path = Path(name)
    if path.is_absolute() or any(part in ('.', '..') for part in path.parts):
        raise ValueError('Only task-local files are permitted')
    fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(child, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise ValueError('Input exceeds its file limit')
            body = stream.read(limit + 1)
            if len(body) > limit:
                raise ValueError('Input exceeds its file limit')
            return body
    except FileNotFoundError:
        if optional:
            return None
        raise
    finally:
        os.close(fd)


def load(name, optional=False):
    body = read(name, optional=optional)
    return json.loads(body) if body is not None else None


def basis(payload):
    outline = load('outline.json')
    pages = {page['id']: page for page in outline['slides']}
    plan = load('decision-plan.json', optional=True) or {}
    decisions = {page['id']: page for page in plan.get('pages', [])}
    selected = []
    for ident in payload['page_ids']:
        page = decisions.get(ident)
        if page is not None:
            page = dict(page)
            page['assets'] = [{key: value for key, value in asset.items() if key not in ('file', 'status')}
                              for asset in page.get('assets', [])]
        selected.append({'id': ident, 'sha256': digest(page),
                         'assets': [{key: asset.get(key) for key in ('route', 'kind')}
                                    for asset in page.get('assets', [])]} if page is not None else None)
    caps = load('capabilities.json', optional=True) or {}
    return {'request': digest(load('request.json', optional=True)),
            'outline': digest({key: value for key, value in outline.items() if key not in ('slides', 'revision')}),
            'pages': [{'id': ident, 'sha256': digest(pages[ident])} for ident in payload['page_ids']],
            'decision_task': plan.get('task'), 'design_direction': digest(plan.get('design_direction')),
            'decisions': selected,
            'capabilities': {key: caps.get(key) for key in ('web_search', 'image_generation')},
            'references': [{'file': name, 'sha256': hashlib.sha256(read(name, 20 * 1024 * 1024)).hexdigest()}
                           for name in payload.get('reference_files', [])]}


def enqueue(data):
    raw = encoded(data)
    if len(raw) > MAX_REQUEST:
        raise ValueError('Material request exceeds its limit')
    ident = uuid.uuid4().hex
    fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        child = os.open('prefetch-requests', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        os.close(fd)
        fd = child
        name = ident + '.pending'
        child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(child, 'wb') as stream:
            stream.write(raw)
        os.replace(name, ident + '.request.json', src_dir_fd=fd, dst_dir_fd=fd)
    finally:
        os.close(fd)
    return {'id': ident, 'state': 'queued'}


def view(ident, include_result=False):
    if not IDENT.fullmatch(ident):
        raise ValueError('Invalid material request ID')
    reply = load('prefetch-requests/' + ident + '.reply.json', optional=True)
    if reply and reply.get('ok') is False:
        return {'id': ident, 'state': 'failed', 'error': reply.get('error', 'Material request rejected')}
    actual = (reply or {}).get('request', {}).get('id', ident)
    if not isinstance(actual, str) or not IDENT.fullmatch(actual):
        raise ValueError('Invalid host material receipt')
    record = load('material-prefetch/' + actual + '.json', optional=True)
    if record is None:
        return {'id': ident, 'state': 'queued'}
    if (digest(record['payload']) != record['payload_sha256'] or
            digest(record['basis']) != record['basis_sha256']):
        return {'id': actual, 'state': 'failed', 'error': 'Material receipt checksum changed'}
    if record['state'] in ('ready', 'queued', 'running'):
        try:
            if digest(basis(record['payload'])) != digest(record['basis']['files']):
                record = {**record, 'state': 'stale', 'error': 'Target content, selected route or task inputs changed'}
        except (OSError, json.JSONDecodeError, TypeError):
            record = {**record, 'state': 'interrupted', 'verification_pending': True,
                      'error': 'Current inputs are being written or cannot yet be verified; check again'}
        except KeyError:
            record = {**record, 'state': 'stale', 'error': 'Target page is absent from the current outline'}
    # No absolute staging paths are returned. Host-only input revisions are
    # checked at each owner poll; file changes are also checked immediately here.
    if include_result and record['state'] == 'ready':
        result = load('material-prefetch/' + actual + '.result.json')
        if digest(result) != record.get('result_sha256'):
            return {'id': actual, 'state': 'failed', 'error': 'Material result checksum changed'}
        for item in result.get('files', []):
            name = item.get('path', '')
            if not re.fullmatch(r'assets/generated-prefetch-[0-9a-f]{32}-\d+\.png', name):
                return {'id': actual, 'state': 'failed', 'error': 'Invalid prepared asset path'}
            if hashlib.sha256(read(name, 20 * 1024 * 1024)).hexdigest() != item.get('sha256'):
                return {'id': actual, 'state': 'failed', 'error': 'Material asset checksum changed'}
        record['result'] = result
    if not include_result:
        summary = {key: record[key] for key in ('id', 'state', 'created_at', 'updated_at', 'started_at',
                   'completed_at', 'seconds', 'error', 'calls', 'verification_pending') if key in record}
        summary['payload'] = {key: record['payload'][key] for key in ('kind', 'purpose', 'page_ids')}
        return summary
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    submit = sub.add_parser('submit')
    submit.add_argument('--batch', help='Task-relative JSON file containing a request array')
    submit.add_argument('--page-id', action='append', default=[])
    submit.add_argument('--purpose')
    group = submit.add_mutually_exclusive_group()
    group.add_argument('--search')
    group.add_argument('--generate')
    submit.add_argument('--reference-file', action='append', default=[])
    submit.add_argument('--retry-of')
    status = sub.add_parser('status')
    status.add_argument('ids', nargs='*')
    get = sub.add_parser('get')
    get.add_argument('id')
    cancel = sub.add_parser('cancel')
    cancel.add_argument('id')
    args = parser.parse_args()
    if args.action == 'submit':
        if args.batch:
            if args.search or args.generate or args.page_id or args.purpose or args.reference_file or args.retry_of:
                raise ValueError('Use either a batch file or individual request arguments')
            payloads = load(args.batch)
            if not isinstance(payloads, list) or not 1 <= len(payloads) <= 16 or any(not isinstance(item, dict) for item in payloads):
                raise ValueError('Batch must contain 1–16 material request objects')
        else:
            if not (args.search or args.generate) or not args.page_id or not args.purpose:
                raise ValueError('Provide page IDs, purpose and one search/generate request')
            payload = {'kind': 'search' if args.search else 'generate', 'request': args.search or args.generate,
                       'page_ids': args.page_id, 'purpose': args.purpose, 'reference_files': args.reference_file}
            if args.retry_of:
                payload['retry_of'] = args.retry_of
            payloads = [payload]
        result = {'ok': True, 'requests': [enqueue({'action': 'submit', 'payload': payload}) for payload in payloads]}
    elif args.action == 'cancel':
        if not IDENT.fullmatch(args.id):
            raise ValueError('Invalid material request ID')
        # Resolve a deduplicated submit alias before queueing cancellation.
        actual = view(args.id)['id']
        result = {'ok': True, 'request': enqueue({'action': 'cancel', 'id': actual}), 'target_id': actual}
    elif args.action == 'get':
        result = {'ok': True, 'request': view(args.id, include_result=True)}
    else:
        ids = args.ids
        if not ids:
            index = load('material-prefetch/index.json', optional=True) or {}
            ids = [item['id'] for item in index.get('requests', [])]
        result = {'ok': True, 'requests': [view(ident) for ident in ids]}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        # Input errors are local diagnostics; do not include raw host paths.
        print(json.dumps({'ok': False, 'error': type(error).__name__ + ': material command failed'}))
        raise SystemExit(1)
