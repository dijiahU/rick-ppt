"""Seed native corrections from host-verified frozen bytes, never an old draft.

The caller supplies authority from the existing review/journal contract. This
helper does not choose a candidate, alter journal state, or approve a repair.
Repeated calls retain legitimate partial edits while checking their immutable
source and baseline. A broken/incomplete seed is an error, not permission to
discard progress or silently bootstrap an older presentation.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile


MAX_ARTIFACT = 30 * 1024 * 1024
MAX_JSON = 32 * 1024 * 1024
MAX_PARTS = 50_000
MAX_UNCOMPRESSED = 2 * 1024**3


class RepairBootstrapError(ValueError):
    pass


def _encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':'), allow_nan=False) + '\n').encode()


def _digest(body):
    return hashlib.sha256(body).hexdigest()


def _regular(path):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise RepairBootstrapError('Repair bootstrap requires regular files')
    return path


def _read_json(path):
    _regular(path)
    if path.stat().st_size > MAX_JSON:
        raise RepairBootstrapError('Repair bootstrap JSON exceeds limit')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RepairBootstrapError('Duplicate repair bootstrap JSON key')
            result[key] = value
        return result

    value = json.loads(path.read_bytes(), object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise RepairBootstrapError('Repair bootstrap JSON must be an object')
    return value


def _scoped(root, relative):
    value = Path(relative)
    if value.is_absolute() or '..' in value.parts or '\\' in str(relative):
        raise RepairBootstrapError('Repair bootstrap path is outside the task')
    path = root
    for part in value.parts:
        path /= part
        if path.is_symlink():
            raise RepairBootstrapError('Repair bootstrap paths cannot contain symlinks')
    if not path.resolve().is_relative_to(root):
        raise RepairBootstrapError('Repair bootstrap path escapes task')
    return path


def _safe_tree(root):
    if root.is_symlink() or not root.is_dir():
        raise RepairBootstrapError('Repair workspace is missing or unsafe')
    count = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in [*dirs, *files]:
            count += 1
            node = Path(directory) / name
            if count > MAX_PARTS or node.is_symlink():
                raise RepairBootstrapError('Repair workspace exceeds limits or contains symlinks')
            mode = node.stat().st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise RepairBootstrapError('Repair workspace contains a special file')


def _parts(artifact):
    result = {}
    try:
        with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_PARTS or sum(e.file_size for e in entries) > MAX_UNCOMPRESSED:
                raise RepairBootstrapError('Frozen candidate exceeds package limits')
            seen = set()
            for entry in entries:
                name = entry.filename
                part = PurePosixPath(name)
                normalized = str(part)
                if (not name or part.is_absolute() or '..' in part.parts or
                        '\\' in name or ':' in name or '\x00' in name or
                        normalized.casefold() in seen or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise RepairBootstrapError('Unsafe or duplicate frozen package part')
                seen.add(normalized.casefold())
                if entry.is_dir():
                    continue
                h = hashlib.sha256()
                with archive.open(entry) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        h.update(chunk)
                result[normalized] = {'hash': h.hexdigest(), 'size': entry.file_size}
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise RepairBootstrapError('Invalid frozen PowerPoint package') from error
    if not {'[Content_Types].xml', 'ppt/presentation.xml'}.issubset(result):
        raise RepairBootstrapError('Frozen candidate lacks PowerPoint parts')
    return result


def _baseline(value):
    if not isinstance(value, dict):
        raise RepairBootstrapError('Missing repair workspace baseline')
    try:
        return {name: {'hash': item['hash'], 'size': item['size']}
                for name, item in value.items()}
    except (KeyError, TypeError) as error:
        raise RepairBootstrapError('Invalid repair workspace baseline') from error


def _check_workspace(job, home, workspace_relative, seed, binding, parts, *, fresh):
    workspace = _scoped(job, workspace_relative)
    if not workspace.is_relative_to(home) or workspace.name != 'workspace':
        raise RepairBootstrapError('Unpacked repair workspace is outside its bootstrap')
    _safe_tree(workspace)
    state = _read_json(workspace.parent / 'state.json')
    seed = _regular(seed)
    original = _regular(workspace.parent / 'original.pptx')
    if seed.stat().st_size > MAX_ARTIFACT or original.stat().st_size > MAX_ARTIFACT:
        raise RepairBootstrapError('Protected repair candidate exceeds size limit')
    if _digest(seed.read_bytes()) != binding['artifact_sha256'] or _digest(original.read_bytes()) != binding['artifact_sha256']:
        raise RepairBootstrapError('Protected repair candidate bytes changed')
    if (state.get('version') not in (1, 2) or state.get('source_hash') != binding['artifact_sha256'] or
            state.get('workspace') != str(workspace)):
        raise RepairBootstrapError('Repair workspace source identity disagrees')
    source_value = state.get('source')
    if not isinstance(source_value, str):
        raise RepairBootstrapError('Repair workspace lacks protected source')
    source = Path(source_value)
    # Existing recovery relocation may point source to its protected original.
    if source not in (seed, original) or _digest(_regular(source).read_bytes()) != binding['artifact_sha256']:
        raise RepairBootstrapError('Repair source is not the frozen candidate')
    for key in ('baseline', 'original_manifest'):
        if _baseline(state.get(key)) != parts:
            raise RepairBootstrapError('Repair baseline is not the frozen candidate')
    if fresh:
        actual = {p.relative_to(workspace).as_posix():
                  {'hash': _digest(p.read_bytes()), 'size': p.stat().st_size}
                  for p in workspace.rglob('*') if p.is_file()}
        if actual != parts:
            raise RepairBootstrapError('Unpack changed frozen candidate parts')
    return workspace


@contextmanager
def _lock(job):
    path = _scoped(job, '.repair-bootstrap.lock')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'a+') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RepairBootstrapError('Unsafe repair bootstrap lock')
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def bootstrap_repair_workspace(job, cfg, *, artifact, artifact_sha256, task_id,
                               input_revision, plugin_version, repair_round, unpack=None):
    """Return a bound editable workspace and preserve any same-binding edits.

    ``unpack(source, base)`` may call the existing sandbox/run_check mechanism
    and return its parsed CLI JSON. Without it, the pinned configured Python
    invokes the configured plugin CLI directly. Candidate bytes/hash and all
    identity fields must come from the host's existing freeze/recovery checks.
    This function never reads delivery.json or infers an execution revision.
    """
    given = Path(job)
    if given.is_symlink():
        raise RepairBootstrapError('Task root cannot be a symlink')
    job = given.resolve(strict=True)
    if not job.is_dir():
        raise RepairBootstrapError('Task root must be a directory')
    if (not isinstance(artifact, bytes) or not 0 < len(artifact) <= MAX_ARTIFACT or
            not isinstance(artifact_sha256, str) or not re.fullmatch('[0-9a-f]{64}', artifact_sha256) or
            _digest(artifact) != artifact_sha256):
        raise RepairBootstrapError('Frozen candidate hash mismatch or size invalid')
    if (not isinstance(task_id, str) or not task_id or len(task_id) > 256 or
            type(input_revision) is not int or input_revision < 0 or
            not isinstance(plugin_version, str) or not plugin_version or len(plugin_version) > 256 or
            type(repair_round) is not int or repair_round not in (1, 2)):
        raise RepairBootstrapError('Invalid host repair identity')
    binding = {'task_id': task_id, 'input_revision': input_revision,
               'plugin_version': plugin_version, 'repair_round': repair_round,
               'artifact_sha256': artifact_sha256}
    parts = _parts(artifact)
    generation = _digest(_encoded(binding))
    relative_home = 'repair-workspaces/round-' + str(repair_round) + '-' + generation
    with _lock(job):
        home = _scoped(job, relative_home)
        seed = home / 'candidate.pptx'
        receipt_path = home / 'bootstrap.json'
        reused = home.exists()
        if reused:
            if not receipt_path.is_file():
                raise RepairBootstrapError('Incomplete repair bootstrap retained; inspect before recovery')
            receipt = _read_json(receipt_path)
            if receipt.get('version') != 1 or receipt.get('binding') != binding or receipt.get('generation') != generation:
                raise RepairBootstrapError('Repair bootstrap binding disagrees')
            if receipt.get('baseline_parts') != parts:
                raise RepairBootstrapError('Repair bootstrap part identity disagrees')
            workspace_relative = receipt.get('workspace_relative')
            if not isinstance(workspace_relative, str):
                raise RepairBootstrapError('Repair bootstrap workspace is missing')
            _regular(seed)
        else:
            home.mkdir(parents=True, exist_ok=False)
            with seed.open('xb') as stream:
                stream.write(artifact)
                stream.flush()
                os.fsync(stream.fileno())
            seed.chmod(0o444)
            base = home / 'native'
            if unpack is None:
                command = [cfg['python'], str(Path(cfg['plugin']) / 'skills/pptx/scripts/pptx.py'),
                           'unpack', str(seed), '--base', str(base)]
                completed = subprocess.run(command, cwd=job, capture_output=True,
                                           text=True, timeout=180, check=True)
                result = json.loads(completed.stdout)
            else:
                result = unpack(seed, base)
                if isinstance(result, str):
                    result = json.loads(result)
            if not isinstance(result, dict) or not isinstance(result.get('workspace'), str):
                raise RepairBootstrapError('Unpack did not return a native workspace')
            value = Path(result['workspace'])
            if not value.is_absolute() or not value.is_relative_to(home):
                raise RepairBootstrapError('Unpack returned an out-of-scope workspace')
            workspace_relative = value.relative_to(job).as_posix()
            receipt = {'version': 1, 'binding': binding, 'generation': generation,
                       'workspace_relative': workspace_relative, 'baseline_parts': parts}
        workspace = _check_workspace(job, home, workspace_relative, seed, binding, parts, fresh=not reused)
        if not reused:
            # Append-only completed marker. Never overwrite an earlier receipt.
            with receipt_path.open('xb') as stream:
                stream.write(_encoded(receipt))
                stream.flush()
                os.fsync(stream.fileno())
        return {'binding': binding, 'generation': generation, 'reused': reused,
                'workspace': str(workspace), 'home': str(home), 'candidate_path': str(seed),
                'receipt_path': str(receipt_path), 'baseline_parts': parts,
                'partial_edits_retained': reused, 'new_review_required': True}
