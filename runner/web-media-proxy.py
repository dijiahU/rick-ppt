#!/usr/bin/env python3
"""Task-side media client; submit-only permits preparation during page authoring."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

def reply(queue, ident):
    if not re.fullmatch(r'[0-9a-f]{32}', ident):
        raise ValueError('Invalid media request ID')
    fd = os.open(queue, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            source = os.open(ident + '.reply.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            try:
                source = os.open(ident + '.request.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            except FileNotFoundError:
                return {'id': ident, 'status': 'unknown'}
            else:
                os.close(source)
                return {'id': ident, 'status': 'pending'}
        with os.fdopen(source, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                raise ValueError('Invalid media reply')
            result = json.loads(stream.read(65537))
        return {**result, 'id': ident, 'status': 'ready' if result.get('ok') else 'failed'}
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', nargs='?')
    parser.add_argument('--source-page')
    parser.add_argument('--purpose')
    parser.add_argument('--submit-only', action='store_true')
    parser.add_argument('--status', nargs='+', metavar='ID')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    queue = root / 'media-requests'
    if args.status:
        if args.url or args.submit_only:
            parser.error('--status cannot submit a new download')
        print(json.dumps({'requests': [reply(queue, ident) for ident in args.status]}, ensure_ascii=False))
        return
    if not args.url or not args.source_page or not args.purpose:
        parser.error('A URL, --source-page and --purpose are required')
    ident = uuid.uuid4().hex
    data = json.dumps({'url': args.url, 'source_page': args.source_page, 'purpose': args.purpose}).encode()
    if len(data) > 8192:
        parser.error('Request too large')
    fd = os.open(queue, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        pending = ident + '.pending'
        target = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(target, 'wb') as stream:
            stream.write(data)
        os.replace(pending, ident + '.request.json', src_dir_fd=fd, dst_dir_fd=fd)
    finally:
        os.close(fd)
    if args.submit_only:
        print(json.dumps({'id': ident, 'status': 'pending'}))
        return
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        result = reply(queue, ident)
        if result['status'] in ('ready', 'failed'):
            print(json.dumps(result, ensure_ascii=False))
            raise SystemExit(0 if result.get('ok') else 1)
        time.sleep(.25)
    raise SystemExit('Media import timed out; check the reply before retrying: ' + ident)


if __name__ == '__main__':
    main()
