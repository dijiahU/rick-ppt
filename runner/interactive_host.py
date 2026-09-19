"""Host-only broker for task-scoped interactive renders and independent freezing.

The author process never gets loopback/network permission. Inputs are copied with
openat/O_NOFOLLOW into a private host snapshot before the existing renderer runs.
Author-written verification receipts are deliberately never imported.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from urllib.parse import urlsplit

MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_FILES = 4096
MAX_REQUEST = 16384
_VERIFIED: dict[str, dict] = {}


def _record(trajectory, event, value):
    if trajectory is not None:
        from trajectory import record
        record(trajectory, 'emit', event, value)


class InteractiveHostError(ValueError):
    pass


def _root(path):
    value = Path(path).absolute()
    if value.is_symlink() or not value.is_dir():
        raise InteractiveHostError('Invalid task root')
    return value.resolve(strict=True)


def _parts(root, path, allow_root=False):
    raw = os.fspath(path)
    if not isinstance(raw, str) or not raw or any(c in raw for c in ('\\', '\x00', ':')):
        raise InteractiveHostError('Invalid task path')
    if any(part in ('.', '..') for part in raw.split('/')):
        raise InteractiveHostError('Task path traversal rejected')
    value = Path(raw)
    try:
        relative = value.relative_to(root) if value.is_absolute() else value
    except ValueError as error:
        raise InteractiveHostError('Path outside task') from error
    if not relative.parts and not allow_root:
        raise InteractiveHostError('Task path must name a child')
    return relative.parts


def _directory(root, parts=(), create=False):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
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
                raise InteractiveHostError('Unsafe or oversized task file')
            body = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            if len(body) > limit or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise InteractiveHostError('Task file changed during snapshot')
            return body
    finally:
        os.close(parent)


def _decode_json(body):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result or key in {'__proto__', 'constructor', 'prototype'}:
                raise InteractiveHostError('Duplicate or forbidden JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(InteractiveHostError('Nonfinite JSON number')))


def _json(root, path, limit=8 * 1024 * 1024):
    return _decode_json(_read(root, path, limit))


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _relative(value):
    if not isinstance(value, str) or not value or value.startswith('/') or any(c in value for c in ('\\', ':', '\x00', '%')) or any(p in ('', '.', '..') for p in value.split('/')):
        raise InteractiveHostError('Invalid sidecar-relative path')
    return PurePosixPath(value)


def _put(root, relative, body, *, mode=0o600):
    """Publish a new file, never replacing an existing file or symlink."""
    parts = _parts(root, relative)
    fd = _directory(root, parts[:-1], create=True)
    try:
        child = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=fd)
        with os.fdopen(child, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def _reserve(root, relative):
    parts = _parts(root, relative)
    parent = _directory(root, parts[:-1], create=True)
    try:
        os.mkdir(parts[-1], 0o700, dir_fd=parent)
    finally:
        os.close(parent)
    return root.joinpath(*parts)


def _reply(job, identifier, value):
    """Readers see a complete reply; linking refuses an existing reply atomically."""
    queue = _directory(job, ('interactive-requests',))
    pending = identifier + '.' + uuid.uuid4().hex + '.host-pending'
    try:
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=queue)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(pending, identifier + '.reply.json', src_dir_fd=queue, dst_dir_fd=queue, follow_symlinks=False)
    finally:
        try:
            os.unlink(pending, dir_fd=queue)  # Only our own transient publication link.
        except FileNotFoundError:
            pass
        os.close(queue)


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
                    raise InteractiveHostError('Interactive snapshot budget exceeded')
                result['/'.join(rel)] = {'sha256': _sha(body), 'bytes': len(body)}
            else:
                raise InteractiveHostError('Non-regular file or symlink in interactive snapshot')
    try:
        visit(base, ())
    finally:
        os.close(base)
    return result


def _workspace(root, value):
    parts = _parts(root, value)
    if parts[-1] in ('workspace', 'state.json'):
        parts = parts[:-1]
    if not parts:
        raise InteractiveHostError('Workspace must have its own task subdirectory')
    home = root.joinpath(*parts)
    fd = _directory(root, parts + ('workspace',))
    os.close(fd)
    state = _json(root, Path(*parts, 'state.json'))
    if state.get('version') not in (1, 2) or state.get('workspace') != str(home / 'workspace'):
        raise InteractiveHostError('Workspace state identity mismatch')
    source = state.get('source')
    if not isinstance(source, str):
        raise InteractiveHostError('Workspace original source missing')
    original = _read(root, Path(*parts, 'original.pptx'), 120 * 1024 * 1024)
    if _sha(original) != state.get('source_hash') or _sha(_read(root, source, 120 * 1024 * 1024)) != state.get('source_hash'):
        raise InteractiveHostError('Workspace protected source mismatch')
    return home


def _policy(cfg, scene):
    options = scene.get('runtimeOptions', {})
    approved_origins = set(cfg.get('interactive_network_allowlist', []))
    if not set(options.get('networkAllowlist', [])).issubset(approved_origins):
        raise InteractiveHostError('Scene network origins need host approval; import assets locally')
    approved_plugins = cfg.get('interactive_plugin_hashes', {})
    for plugin in scene.get('plugins', []):
        if approved_plugins.get(plugin.get('id')) != plugin.get('sha256'):
            raise InteractiveHostError('Custom deck plugin bytes need explicit host approval')
    tests = scene.get('testPlan', [])
    if len(tests) > 100 or sum(len(t.get('actions', [])) for t in tests) > 1000:
        raise InteractiveHostError('Scene test plan exceeds host budget')


def _snapshot_scene(cfg, job, spec_path, target):
    parts = _parts(job, spec_path)
    source_parent = Path(*parts[:-1])
    source_bytes = _read(job, Path(*parts), 8 * 1024 * 1024)
    scene = _decode_json(source_bytes)
    _policy(cfg, scene)
    assets = scene.get('assets', {})
    wanted = {parts[-1]}
    def add(value):
        if not isinstance(value, str) or value in assets or urlsplit(value).scheme:
            return
        wanted.add(str(_relative(value)))
    for asset in assets.values():
        add(asset['path'])
    for source in scene.get('dataSources', {}).values():
        if source.get('path'):
            add(source['path'])
    for plugin in scene.get('plugins', []):
        add(plugin['path'])
    def nodes(items):
        for node in items:
            for name in ('src', 'poster', 'model', 'before', 'after'):
                add(node.get('props', {}).get(name))
            if node.get('component')=='carousel':
                for item in node.get('props',{}).get('items',[]):
                    add(item.get('src') if isinstance(item,dict) else item)
            nodes(node.get('children', []))
    nodes(scene.get('nodes', []))
    copied = {}
    total = 0
    while wanted:
        name = sorted(wanted)[0]
        wanted.remove(name)
        if name in copied:
            continue
        body = source_bytes if name == parts[-1] else _read(job, source_parent / name)
        total += len(body)
        if len(copied) >= MAX_FILES or total > MAX_TOTAL:
            raise InteractiveHostError('Scene snapshot budget exceeded')
        _put(target, name, body)
        copied[name] = _sha(body)
        if name.lower().endswith('.gltf'):
            gltf = json.loads(body)
            for item in [*gltf.get('buffers', []), *gltf.get('images', [])]:
                uri = item.get('uri')
                if uri and not urlsplit(uri).scheme:
                    wanted.add(str(PurePosixPath(name).parent / _relative(uri)))
    return target / parts[-1], copied


def _snapshot_deck(cfg, job, deck_path, target):
    prefix = Path(*_parts(job, deck_path))
    body = _read(job, prefix / 'bundle.json', 8 * 1024 * 1024)
    bundle = json.loads(body)
    if not isinstance(bundle.get('scenes'), dict) or not isinstance(bundle.get('assets'), dict):
        raise InteractiveHostError('Invalid scene bundle inventory')
    paths = {'bundle.json': body}
    expected = dict(bundle['assets'])
    for scene in bundle['scenes'].values():
        name = str(_relative(scene['path']))
        if name in expected and expected[name] != scene['sha256']:
            raise InteractiveHostError('Conflicting bundle hashes')
        expected[name] = scene['sha256']
    if len(expected) > MAX_FILES:
        raise InteractiveHostError('Too many sidecar files')
    total = len(body)
    for name, sha in expected.items():
        name = str(_relative(name))
        data = _read(job, prefix / name)
        if _sha(data) != sha:
            raise InteractiveHostError('Sidecar hash mismatch')
        paths[name] = data
        total += len(data)
        if total > MAX_TOTAL:
            raise InteractiveHostError('Sidecar budget exceeded')
    for scene in bundle['scenes'].values():
        _policy(cfg, json.loads(paths[scene['path']]))
    for name, data in paths.items():
        _put(target, name, data)
    return bundle


def _private_root():
    # Kept for recovery/debugging; never delete an earlier output generation.
    return Path(tempfile.mkdtemp(prefix='pptx-interactive-host-')).resolve()


def _runtime_inventory(cfg):
    plugin = _root(Path(cfg['plugin']).resolve(strict=True))
    return {'plugin': str(plugin), 'runtime': _inventory(plugin, 'runtime/dist'),
            'config': _sha(_read(plugin, 'runtime/config.json')),
            'manifests': _inventory(plugin, 'runtime/manifests')}


def _archive_parts(body):
    """Compare bounded package parts without extracting or trusting ZIP metadata."""
    result, total = {}, 0
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES:
                raise InteractiveHostError('Archive part count exceeds host budget')
            seen = set()
            for entry in entries:
                name = entry.filename.rstrip('/') if entry.is_dir() else entry.filename
                _relative(name)
                if name in seen or entry.flag_bits & 1:
                    raise InteractiveHostError('Duplicate or encrypted archive part')
                seen.add(name)
                if entry.is_dir():
                    continue
                total += entry.file_size
                if entry.file_size > MAX_FILE or total > MAX_TOTAL:
                    raise InteractiveHostError('Archive parts exceed host budget')
                result[name] = _sha(archive.read(entry))
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
        raise InteractiveHostError('Invalid presentation archive') from error
    return result


def _publish_reviewed_bundle(private, assembled, frozen_root, target, reviewed, *, zip_output):
    """Publish a new generation containing the exact independently reviewed PPTX.

    The plugin's fresh export must first have identical part bytes. A content
    mismatch is an error, never something to hide by replacing its presentation.
    The intermediate plugin distribution stays intact in the private directory.
    """
    assembled = Path(assembled)
    source = assembled.relative_to(private)
    inventory = _inventory(private, source)
    generated = _read(private, source / 'presentation.pptx', 30 * 1024 * 1024)
    if _archive_parts(generated) != _archive_parts(reviewed):
        raise InteractiveHostError('Re-exported PPTX parts differ from the reviewed presentation')
    bundle = _json(private, source / 'deck/bundle.json')
    bundle['pptxHash'] = _sha(reviewed)
    replacements = {'presentation.pptx': reviewed,
                    'deck/bundle.json': (json.dumps(bundle, ensure_ascii=False, indent=2) + '\n').encode()}
    destination = target.relative_to(frozen_root)
    _reserve(frozen_root, destination)
    checksums = {}
    executable = {'scripts/start.command', 'scripts/stop.command'}
    for name, expected in inventory.items():
        if name == 'checksums.json':
            continue
        body = _read(private, source / name)
        if _sha(body) != expected['sha256']:
            raise InteractiveHostError('Intermediate bundle changed during publication')
        body = replacements.get(name, body)
        _put(frozen_root, destination / name, body, mode=0o700 if name in executable else 0o600)
        checksums[name] = _sha(body)
    if not set(replacements).issubset(checksums):
        raise InteractiveHostError('Intermediate bundle lacks its native presentation or manifest')
    _put(frozen_root, destination / 'checksums.json',
         (json.dumps(checksums, ensure_ascii=False, indent=2) + '\n').encode())
    published = _inventory(frozen_root, destination)
    if {name: value['sha256'] for name, value in published.items() if name != 'checksums.json'} != checksums:
        raise InteractiveHostError('Published bundle checksum verification failed')
    if (_read(frozen_root, destination / 'presentation.pptx', 30 * 1024 * 1024) != reviewed or
            _json(frozen_root, destination / 'deck/bundle.json').get('pptxHash') != _sha(reviewed)):
        raise InteractiveHostError('Published bundle lost reviewed presentation identity')
    zipped = None
    if zip_output:
        candidate = private / ('reviewed-bundle-' + uuid.uuid4().hex + '.zip')
        with zipfile.ZipFile(candidate, 'x', zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(published):
                body = _read(frozen_root, destination / name)
                if _sha(body) != published[name]['sha256']:
                    raise InteractiveHostError('Bundle changed during ZIP assembly')
                entry = zipfile.ZipInfo(target.name + '/' + name)
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = (stat.S_IFREG | (0o700 if name in executable else 0o600)) << 16
                archive.writestr(entry, body)
        body = _read(private, candidate)
        expected = {target.name + '/' + name: value['sha256'] for name, value in published.items()}
        if _archive_parts(body) != expected:
            raise InteractiveHostError('Portable ZIP differs from verified bundle files')
        zipped = target.with_suffix('.zip')
        _put(frozen_root, zipped.relative_to(frozen_root), body)
        if _sha(_read(frozen_root, zipped)) != _sha(body):
            raise InteractiveHostError('Published ZIP checksum verification failed')
    return {'bundle': str(target), 'zip': str(zipped) if zipped else None,
            'pptx': str(target / 'presentation.pptx'), 'pptx_sha256': _sha(reviewed),
            'exact_reviewed_pptx': True}


def _run_worker(cfg, operation, root, *, tick=None, native_service=None, timeout=240):
    request_file = root / ('host-operation-' + uuid.uuid4().hex + '.json')
    operation = {**operation, 'plugin': str(Path(cfg['plugin']).resolve(strict=True))}
    request_file.write_text(json.dumps(operation))
    log_path = root / ('host-operation-' + uuid.uuid4().hex + '.log')
    env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'HOME') if key in os.environ}
    env['TMPDIR'] = str(root)
    env['PYTHONNOUSERSITE'] = '1'
    if operation.get('nativeProxy'):
        env['PPTX_SOFFICE'] = operation['nativeProxy']
    # No bridge token, task proxy, Python path, API credential or proxy credential.
    # Preserve the venv executable path: resolving its symlink loses pyvenv.cfg.
    executable = Path(cfg['python']).absolute()
    if not executable.is_file():
        raise InteractiveHostError('Configured host Python is unavailable')
    command = [str(executable), '-I', str(Path(__file__).resolve()), '--worker', str(request_file)]
    with log_path.open('wb') as output:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, env=env, cwd=root, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if tick:
                    tick()
                if native_service:
                    native_service()
                if time.monotonic() > deadline:
                    raise TimeoutError('Host interactive operation timed out')
                if log_path.stat().st_size > 2 * 1024 * 1024:
                    raise InteractiveHostError('Host renderer diagnostic limit exceeded')
                time.sleep(.1)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
    text = log_path.read_text(errors='replace')
    lines = [line for line in text.splitlines() if line.startswith('{')]
    value = json.loads(lines[-1]) if lines else {}
    if process.returncode or not value.get('ok'):
        reason = str(value.get('error') or 'Host renderer failed')[:1800]
        raise InteractiveHostError(reason.replace(str(root), '$HOST').replace(str(Path(cfg['plugin'])), '$PLUGIN'))
    return value['result']


def _copy_outputs(private, source, job, output, report):
    try:
        target = _reserve(job, output)
    except FileExistsError:
        # A crash may have published captures before its reply. Retest and keep
        # that generation; never accept its author-writable report as evidence.
        parts = _parts(job, output)
        existing = _directory(job, parts)  # Reject a file or symlink collision.
        os.close(existing)
        target = _reserve(job, Path(*parts[:-1], parts[-1] + '-host-' + uuid.uuid4().hex[:10]))
    inventory = _inventory(private, source.relative_to(private))
    translated = {**report, 'directory': str(target)}
    for name in inventory:
        if name == 'report.json':
            continue
        _put(job, target.relative_to(job) / name, _read(private, source.relative_to(private) / name))
    _put(job, target.relative_to(job) / 'report.json', json.dumps(translated, indent=2).encode())
    return translated


class InteractiveHostBroker:
    def __init__(self, cfg, job, trajectory=None):
        self.cfg, self.job, self.trajectory = cfg, _root(job), trajectory
        fd = _directory(self.job, ('interactive-requests',), create=True)
        os.close(fd)
        self.processed = set()
        self.worker = None
        self.current = None
        self.result = None

    def _execute(self, data):
        private = _private_root()
        try:
            if not isinstance(data, dict) or data.get('version') != 1 or data.get('operation') != 'render':
                raise InteractiveHostError('Unsupported interactive host request')
            if set(data) - {'version', 'operation', 'spec', 'output', 'deckRoot', 'deckId', 'workspace', 'scene'}:
                raise InteractiveHostError('Unknown interactive request fields')
            output = data.get('output')
            _parts(self.job, output)
            stage = private / 'input'
            stage.mkdir()
            deck_id = None
            deck = None
            if data.get('workspace'):
                home = _workspace(self.job, data['workspace'])
                deck = home / 'interactive/deck'
            elif data.get('deckRoot'):
                deck = self.job.joinpath(*_parts(self.job, data['deckRoot']))
            if deck:
                bundle = _snapshot_deck(self.cfg, self.job, deck, stage)
                deck_id = bundle['deckId']
                if data.get('deckId') and data['deckId'] != deck_id:
                    raise InteractiveHostError('Requested deck identity differs from sidecar')
                if data.get('scene'):
                    scene_id = data['scene']
                else:
                    scene_id = _json(self.job, data['spec'])['id']
                    expected = str(deck / bundle['scenes'][scene_id]['path'])
                    if self.job.joinpath(*_parts(self.job, data['spec'])) != Path(expected):
                        raise InteractiveHostError('Spec is not the bundled scene path')
                source = stage / str(_relative(bundle['scenes'][scene_id]['path']))
            else:
                source, _ = _snapshot_scene(self.cfg, self.job, data.get('spec'), stage)
            report = _run_worker(self.cfg, {'operation': 'render', 'spec': str(source), 'output': str(private / 'render'), 'deckRoot': str(stage) if deck else None, 'deckId': deck_id}, private)
            copied = _copy_outputs(private, private / 'render', self.job, output, report)
            self.result = {'ok': True, 'report': copied}
            _record(self.trajectory, 'interactive.render.completed', {'request_id': self.current, 'scene_id': report['sceneId'], 'spec_hash': report['specHash'], 'test_count': report['testCount'], 'output': str(output)})
        except Exception as error:
            self.result = {'ok': False, 'error': str(error).replace(str(private), '$HOST').replace(str(self.job), '$TASK')[:1800], 'kind': type(error).__name__}
            _record(self.trajectory, 'interactive.render.failed', {'request_id': self.current, 'error': self.result['error']})

    def poll(self, start_new=True):
        queue = _directory(self.job, ('interactive-requests',))
        try:
            if self.worker:
                if self.worker.is_alive():
                    return
                self.worker.join()
                self.worker = None
                try:
                    _reply(self.job, self.current, self.result)
                except FileExistsError:
                    pass  # An author-created reply cannot replace a host receipt.
                self.current = None
                self.result = None
            if not start_new:
                return
            names = set(os.listdir(queue))
            for name in sorted(names)[:2048]:
                if not re.fullmatch(r'[0-9a-f]{32}\.request\.json', name):
                    continue
                identifier = name[:32]
                if identifier in self.processed or identifier + '.reply.json' in names:
                    continue
                if len(self.processed) >= 128:
                    self.processed.add(identifier)
                    try:
                        _reply(self.job, identifier, {'ok': False, 'error': 'Per-task interactive render limit reached (128)'})
                    except FileExistsError:
                        pass
                    continue
                # Atomic request publication uses a transient second hard link;
                # wait for it to settle rather than treating that instant as bad.
                info = os.stat(name, dir_fd=queue, follow_symlinks=False)
                if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                    continue
                self.processed.add(identifier)
                try:
                    data = _json(self.job, Path('interactive-requests') / name, MAX_REQUEST)
                except (ValueError, OSError):
                    try:
                        _reply(self.job, identifier, {'ok': False, 'error': 'Invalid task-scoped request'})
                    except FileExistsError:
                        pass
                    continue
                self.current = identifier
                _record(self.trajectory, 'interactive.render.started', {'request_id': identifier, 'spec': data.get('spec'), 'output': data.get('output')})
                self.worker = threading.Thread(target=self._execute, args=(data,), daemon=True, name='interactive-render')
                self.worker.start()
                break
        finally:
            os.close(queue)

    def drain(self, timeout=250, tick=None):
        deadline = time.monotonic() + timeout
        while self.worker is not None and time.monotonic() < deadline:
            if tick:
                tick()
            self.poll(start_new=False)
            if self.worker:
                time.sleep(.1)
        if self.worker:
            raise TimeoutError('Interactive host operation did not drain')


def verify_frozen(cfg, author_job, delivery, frozen_root, frozen_workspace, *, tick=None, trajectory=None):
    author_job, frozen_root = _root(author_job), _root(frozen_root)
    frozen_home = _workspace(frozen_root, frozen_workspace)
    private = _private_root()
    inspection = _run_worker(cfg, {'operation': 'inspect', 'workspace': str(frozen_home)}, private, tick=tick)
    if not inspection['instances']:
        return {'interactive': False, 'runtime_verified': False, 'powerpoint_playback_verified': False}
    reviewed_path = frozen_home.relative_to(frozen_root) / 'original.pptx'
    reviewed_sha = _sha(_read(frozen_root, reviewed_path, 30 * 1024 * 1024))
    if not isinstance(delivery, dict) or not isinstance(delivery.get('workspace'), str):
        raise InteractiveHostError('Interactive delivery.json must include its author workspace')
    source_home = _workspace(author_job, delivery['workspace'])
    staged = private / 'deck'
    staged.mkdir()
    bundle = _snapshot_deck(cfg, author_job, source_home / 'interactive/deck', staged)
    # Check identity/hash against the frozen exported OOXML, not author state.
    for instance in inspection['instances']:
        scene = bundle['scenes'].get(instance['sceneId'])
        if instance['deckId'] != bundle['deckId'] or not scene or instance['specHash'] != scene['sha256']:
            raise InteractiveHostError('Delivered OOXML does not match the supplied scene sidecar')
    target = _reserve(frozen_root, frozen_home.relative_to(frozen_root) / 'interactive/deck')
    for name in _inventory(private, 'deck'):
        _put(frozen_root, target.relative_to(frozen_root) / name, _read(private, Path('deck') / name))
    runtime_before = _runtime_inventory(cfg)
    result = _run_worker(cfg, {'operation': 'verify', 'workspace': str(frozen_home)}, private, tick=tick, timeout=900)
    if _runtime_inventory(cfg) != runtime_before:
        raise InteractiveHostError('Installed runtime changed during host verification')
    if _sha(_read(frozen_root, reviewed_path, 30 * 1024 * 1024)) != reviewed_sha:
        raise InteractiveHostError('Frozen presentation changed during host verification')
    token = uuid.uuid4().hex
    record = {'root': str(frozen_root), 'home': str(frozen_home), 'native': _inventory(frozen_root, frozen_home.relative_to(frozen_root) / 'workspace'), 'interactive': _inventory(frozen_root, frozen_home.relative_to(frozen_root) / 'interactive'), 'runtime': runtime_before, 'reports': result['reports'], 'reviewed_pptx': reviewed_path.as_posix(), 'reviewed_sha256': reviewed_sha}
    _VERIFIED[token] = record
    _record(trajectory, 'interactive.frozen.verified', {'deck_id': bundle['deckId'], 'scenes': sorted(result['reports']), 'scene_hashes': {key: value['specHash'] for key, value in result['reports'].items()}})
    return {'interactive': True, 'runtime_verified': True, 'powerpoint_playback_verified': False, 'receipt': token, 'deckId': bundle['deckId'], 'scenes': sorted(result['reports']), 'reports': result['reports'], 'workspace': str(frozen_home / 'workspace'), 'reviewed_pptx_sha256': reviewed_sha}


def bundle_frozen(cfg, frozen_root, frozen_workspace, verification, output, *, zip_output=True, tick=None, native_service=None, trajectory=None):
    frozen_root = _root(frozen_root)
    home = _workspace(frozen_root, frozen_workspace)
    record = _VERIFIED.get(verification.get('receipt')) if isinstance(verification, dict) else None
    if not record or record['root'] != str(frozen_root) or record['home'] != str(home):
        raise InteractiveHostError('A fresh host-owned verification receipt is required')
    if _inventory(frozen_root, home.relative_to(frozen_root) / 'workspace') != record['native'] or _inventory(frozen_root, home.relative_to(frozen_root) / 'interactive') != record['interactive']:
        raise InteractiveHostError('Frozen native/scene/test bytes changed after host verification')
    if _runtime_inventory(cfg) != record['runtime']:
        raise InteractiveHostError('Installed runtime changed after host verification')
    reviewed = _read(frozen_root, record['reviewed_pptx'], 30 * 1024 * 1024)
    if _sha(reviewed) != record['reviewed_sha256']:
        raise InteractiveHostError('Frozen presentation changed after host verification')
    target = frozen_root.joinpath(*_parts(frozen_root, output))
    parent = _directory(frozen_root, target.parent.relative_to(frozen_root).parts, create=True)
    try:
        if target.name in os.listdir(parent) or zip_output and target.with_suffix('.zip').name in os.listdir(parent):
            raise InteractiveHostError('Bundle output already exists')
    finally:
        os.close(parent)
    private = _private_root()
    # The plugin export remains an independently validated intermediate. Only the
    # host publishes a distribution containing the original reviewed ZIP bytes.
    assembled = private / 'validated-native-bundle'
    operation = {'operation': 'bundle', 'workspace': str(home), 'output': str(assembled), 'zip': False}
    helper = frozen_root / 'soffice-proxy.py'
    if helper.exists() or helper.is_symlink() or native_service is not None:
        if native_service is None:
            raise InteractiveHostError('Production native export requires its renderer service callback')
        if _read(frozen_root, 'soffice-proxy.py', 65536) != Path(__file__).with_name('soffice-proxy.py').read_bytes():
            raise InteractiveHostError('Native rendering proxy differs from the trusted runner helper')
        operation['nativeProxy'] = str(helper)
    result = _run_worker(cfg, operation, private, tick=tick, native_service=native_service, timeout=600)
    if _runtime_inventory(cfg) != record['runtime']:
        raise InteractiveHostError('Installed runtime changed during bundle assembly')
    if (_inventory(frozen_root, home.relative_to(frozen_root) / 'workspace') != record['native'] or
            _inventory(frozen_root, home.relative_to(frozen_root) / 'interactive') != record['interactive'] or
            _sha(_read(frozen_root, record['reviewed_pptx'], 30 * 1024 * 1024)) != record['reviewed_sha256']):
        raise InteractiveHostError('Frozen presentation or scene changed during bundle assembly')
    published = _publish_reviewed_bundle(private, assembled, frozen_root, target, reviewed, zip_output=zip_output)
    if _runtime_inventory(cfg) != record['runtime']:
        raise InteractiveHostError('Installed runtime changed during bundle publication')
    _record(trajectory, 'interactive.bundle.completed', {'output': str(target), 'runtime_verified': result['runtime_verified'], 'reviewed_pptx_sha256': record['reviewed_sha256'], 'exact_reviewed_pptx': True})
    return {**result, **published}


def _worker_main(path):
    operation = json.loads(Path(path).read_text())
    plugin = Path(operation['plugin'])
    sys.path.insert(0, str(plugin / 'skills/pptx/scripts'))
    from pptx_core.package import select
    from pptx_core.interactive import scene_render
    from pptx_core.interactive_validate import validate_interactive, config
    from pptx_core.interactive_ooxml import discover_content_addins
    from pptx_core.validator import validate
    if operation['operation'] == 'render':
        from interactive_render import render_scene
        return render_scene(operation['spec'], operation['output'], deck_root=operation.get('deckRoot'), deck_id=operation.get('deckId'))
    workspace = select(operation['workspace'])
    validate(workspace.root).require()
    if operation['operation'] == 'inspect':
        return {'instances': [item for item in discover_content_addins(workspace.root) if item.get('addinId') == config()['addinId']]}
    if operation['operation'] == 'verify':
        initial = validate_interactive(workspace.root)
        if not initial['ok']:
            raise InteractiveHostError('; '.join(initial['errors']))
        reports = {}
        for scene in sorted({item['sceneId'] for item in initial['instances']}):
            report = scene_render(workspace, scene)
            if not report.get('ok') or not report.get('runtime_verified') or not report.get('testCount') or any(not item.get('assertions') for item in report['tests']):
                raise InteractiveHostError('Each attached scene needs a passing, nonempty host testPlan')
            reports[scene] = report
        final = validate_interactive(workspace.root, require_runtime=True)
        if not final['ok'] or not final['runtime_verified']:
            raise InteractiveHostError('Host interactive verification failed')
        return {'reports': reports, 'validation': final}
    if operation['operation'] == 'bundle':
        from pptx_core.interactive_bundle import assemble_bundle
        return assemble_bundle(workspace, operation['output'], operation.get('zip', True))
    raise InteractiveHostError('Unknown host operation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    try:
        result = _worker_main(args.worker)
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error), 'kind': type(error).__name__}, ensure_ascii=False))
        raise SystemExit(1)
