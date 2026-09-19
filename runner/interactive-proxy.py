#!/usr/bin/env python3
"""Task-local file protocol. This helper opens no socket and reads no host secret."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import time
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--deck-root')
    parser.add_argument('--deck-id')
    parser.add_argument('--timeout', type=float, default=260)
    args = parser.parse_args()
    root = Path(__file__).absolute().parent
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            os.mkdir('interactive-requests', 0o700, dir_fd=fd)
        except FileExistsError:
            pass
        queue = os.open('interactive-requests', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
    finally:
        os.close(fd)
    identifier = uuid.uuid4().hex
    request = {'version': 1, 'operation': 'render', 'spec': str(Path(args.spec).absolute()), 'output': str(Path(args.output).absolute())}
    if args.deck_root:
        request['deckRoot'] = str(Path(args.deck_root).absolute())
    if args.deck_id:
        request['deckId'] = args.deck_id
    try:
        pending = identifier + '.pending'
        child = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=queue)
        with os.fdopen(child, 'w') as stream:
            json.dump(request, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(pending, identifier + '.request.json', src_dir_fd=queue, dst_dir_fd=queue, follow_symlinks=False)
        os.unlink(pending, dir_fd=queue)  # Only the helper's completed temporary link.
        deadline = time.monotonic() + min(600, max(5, args.timeout))
        while time.monotonic() < deadline:
            try:
                response = os.open(identifier + '.reply.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=queue)
            except FileNotFoundError:
                time.sleep(.2)
                continue
            with os.fdopen(response, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 2 * 1024 * 1024:
                    raise ValueError('Invalid host response')
                value = json.loads(stream.read(2 * 1024 * 1024 + 1))
            if not value.get('ok'):
                raise ValueError(value.get('error') or 'Host interactive rendering failed')
            print(json.dumps(value['report'], ensure_ascii=False))
            return
        raise TimeoutError('Interactive host broker did not respond; keep the runner active')
    finally:
        os.close(queue)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
