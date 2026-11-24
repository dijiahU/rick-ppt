"""Bounded file reads and hash inventories for isolated review packets."""
import hashlib
import os
from pathlib import Path
import stat

MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_FILES = 4096


class ReviewArtifactError(ValueError):
    pass


def _root(path):
    value = Path(path).absolute()
    if value.is_symlink() or not value.is_dir():
        raise ReviewArtifactError('Invalid task root')
    return value.resolve(strict=True)


def _parts(root, path, allow_root=False):
    raw = os.fspath(path)
    if not isinstance(raw, str) or not raw or any(c in raw for c in ('\\', '\x00', ':')):
        raise ReviewArtifactError('Invalid task path')
    if any(part in ('.', '..') for part in raw.split('/')):
        raise ReviewArtifactError('Task path traversal rejected')
    value = Path(raw)
    try:
        relative = value.relative_to(root) if value.is_absolute() else value
    except ValueError as error:
        raise ReviewArtifactError('Path outside task') from error
    if not relative.parts and not allow_root:
        raise ReviewArtifactError('Task path must name a child')
    return relative.parts


def _directory(root, parts=()):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read(root, path, limit=MAX_FILE):
    parts = _parts(root, path)
    parent = _directory(root, parts[:-1])
    try:
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
                raise ReviewArtifactError('Unsafe or oversized task file')
            body = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            if len(body) > limit or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ReviewArtifactError('Task file changed during snapshot')
            return body
    finally:
        os.close(parent)


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _inventory(root, relative):
    parts = _parts(root, relative, allow_root=True)
    base = _directory(root, parts)
    result = {}
    total = 0
    def visit(fd, prefix):
        nonlocal total
        for name in sorted(os.listdir(fd)):
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            rel = prefix + (name,)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    visit(child, rel)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                body = _read(root, Path(*parts, *rel))
                total += len(body)
                if len(result) >= MAX_FILES or total > MAX_TOTAL:
                    raise ReviewArtifactError('Review snapshot budget exceeded')
                result['/'.join(rel)] = {'sha256': _sha(body), 'bytes': len(body)}
            else:
                raise ReviewArtifactError('Non-regular file or symlink in review snapshot')
    try:
        visit(base, ())
    finally:
        os.close(base)
    return result


def _runtime_inventory(cfg):
    plugin = _root(Path(cfg['plugin']).resolve(strict=True))
    return {'plugin': str(plugin), 'runtime': _inventory(plugin, 'runtime/dist'),
            'config': _sha(_read(plugin, 'runtime/config.json')),
            'manifests': _inventory(plugin, 'runtime/manifests')}
