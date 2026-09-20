"""Host-private, append-only receipts for completed independent review passes.

This is deliberately not turn resumption. An unfinished attempt remains pending
and a later attempt starts an independent reviewer. Only a matching completed
turn followed by a validated report can create a reusable receipt.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from interactive_host import _directory, _inventory, _read, _root, _runtime_inventory


VERSION = 1
ROLES = frozenset({'content-first', 'content-evidence', 'visual'})
ZERO = '0' * 64
ENTRY = re.compile(r'([0-9]{8})-([0-9a-f]{64})\.json\Z')
ATTEMPT = re.compile(r'[0-9a-f]{32}\Z')
TERMINAL = frozenset({'completed', 'interrupted', 'failed'})


class ReviewSessionError(ValueError):
    pass


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def file_receipt(body):
    return {'sha256': digest(body), 'bytes': len(body)}


def selected_files(root, names):
    root = _root(root)
    return {name: file_receipt(_read(root, name)) for name in sorted(set(names))}


def runtime_identity(cfg):
    """Hash actual installed files, not a caller-supplied version label alone."""
    value = _runtime_inventory(cfg)
    plugin = Path(value['plugin'])
    value['plugin_manifest'] = file_receipt(_read(plugin, '.codex-plugin/plugin.json'))
    value['review_references'] = selected_files(plugin, [
        'skills/pptx/references/content-review.md', 'skills/pptx/references/visual-review.md'])
    return value


def candidate_identity(task_id, revision, artifact, rendered, packet, runtime, plugin_version=None):
    if not isinstance(task_id, str) or not task_id or len(task_id) > 256:
        raise ReviewSessionError('Invalid review task identity')
    if type(revision) is not int or revision < 0:
        raise ReviewSessionError('Invalid review input revision')
    pages = {}
    for number, path in enumerate(rendered['pages'], 1):
        path = Path(path)
        pages[f'page-{number}.png'] = file_receipt(_read(_root(path.parent), path.name))
    if not pages:
        raise ReviewSessionError('Review requires rendered pages')
    packet = _root(packet)
    packet_files = _inventory(_root(packet.parent), packet.name)
    if set(pages) & set(packet_files):
        raise ReviewSessionError('Review packet shadows a rendered page')
    return {'version': VERSION, 'task_id': task_id, 'input_revision': revision,
            'plugin_version': plugin_version, 'artifact': file_receipt(artifact),
            'runtime': runtime, 'pages': pages, 'packet': packet_files}


def _mkdir(root, parts):
    fd = _directory(root)
    try:
        for name in parts:
            try:
                os.mkdir(name, 0o700, dir_fd=fd)
                os.fsync(fd)
            except FileExistsError:
                pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
    finally:
        os.close(fd)
    return root.joinpath(*parts)


def _publish(root, name, body):
    # No final filename is visible until all bytes have been flushed. A crash
    # leaves only an explicitly uncommitted .pending-* file, or a complete final
    # file (possibly still linked to our temporary). Never replace an old file.
    fd = _directory(root)
    temporary = '.pending-' + uuid.uuid4().hex
    created = False
    try:
        child = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        created = True
        with os.fdopen(child, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        os.fsync(fd)
    finally:
        if created:
            try:
                os.unlink(temporary, dir_fd=fd)  # Only this call's own temporary.
                os.fsync(fd)
            except OSError:
                pass  # A retained link is safe and remains private/uncommitted.
        os.close(fd)


def _read_record(root, name, limit=32 * 1024 * 1024):
    """Read host-owned records, including a published link left by a crash.

Unlike model-supplied assets, a ledger file may have two hard links when the
process died after atomic publication but before cleaning its private temporary.
Checksums/context are still mandatory at every call site.
"""
    parent = _directory(root)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise ReviewSessionError('Unsafe or oversized review record')
            body = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            if (len(body) > limit or (before.st_ino,before.st_size,before.st_mtime_ns) !=
                    (after.st_ino,after.st_size,after.st_mtime_ns)):
                raise ReviewSessionError('Review record changed while reading')
            return body
    finally:
        os.close(parent)


def _publish_same(root, name, body):
    try:
        _publish(root, name, body)
    except FileExistsError:
        if _read_record(root, name) != body:
            raise ReviewSessionError('Review identity record changed')


def _load_attempt(root):
    entries = sorted(name for name in os.listdir(root) if ENTRY.fullmatch(name))
    if not entries:
        # mkdir / first-publication crash: preserve the directory and any
        # uncommitted temporary; it has no completion authority to reuse.
        return None, ZERO, 0
    previous, state = ZERO, None
    for sequence, name in enumerate(entries):
        match = ENTRY.fullmatch(name)
        body = _read_record(root, name)
        if int(match[1]) != sequence or digest(body) != match[2]:
            raise ReviewSessionError('Review record checksum or sequence mismatch')
        value = json.loads(body)
        if (value.get('version') != VERSION or value.get('sequence') != sequence or
                value.get('previous') != previous or not isinstance(value.get('state'), dict)):
            raise ReviewSessionError('Invalid review record chain')
        previous, state = match[2], value['state']
    return state, previous, len(entries)


class ReviewSessions:
    def __init__(self, records, identity, *, author_root, plugin_root):
        records = _root(records)
        for exposed in (author_root, plugin_root):
            exposed = _root(exposed)
            if records == exposed or records.is_relative_to(exposed):
                raise ReviewSessionError('Review records must be outside model-readable roots')
        self.identity = copy.deepcopy(identity)
        self.key = digest(encoded(identity))
        task_key = digest(identity['task_id'].encode())
        self.root = _mkdir(records, ('review-sessions', task_key, self.key))
        _publish_same(self.root, 'candidate.json', encoded(identity))

    def role(self, role, prompt, files):
        if role not in ROLES:
            raise ReviewSessionError('Invalid reviewer role')
        context = {'role': role, 'candidate': self.key, 'prompt_sha256': digest(prompt.encode()),
                   'files': copy.deepcopy(files)}
        root = _mkdir(self.root, (role, digest(encoded(context))))
        _publish_same(root, 'context.json', encoded(context))
        return ReviewRole(root, context)


class ReviewRole:
    def __init__(self, root, context):
        self.root, self.context = root, context

    def cached(self, validate):
        found = None
        for name in sorted(os.listdir(self.root)):
            if name == 'context.json' or re.fullmatch(r'\.pending-[0-9a-f]{32}', name):
                continue
            if not ATTEMPT.fullmatch(name):
                raise ReviewSessionError('Unexpected review ledger entry')
            root = _root(self.root / name)
            state, _, _ = _load_attempt(root)
            if state is None:
                continue  # Unpublished attempt is pending, never a cache hit.
            if state.get('context') != self.context:
                raise ReviewSessionError('Review receipt context mismatch')
            if state.get('status') != 'validated':
                continue
            if (state.get('report_status') != 'validated' or state.get('terminal_status') != 'completed' or
                    not state.get('thread_id') or not state.get('turn_id')):
                raise ReviewSessionError('Review receipt lacks a completed turn')
            receipt = state.get('report', {})
            sha = receipt.get('sha256', '')
            if not re.fullmatch(r'[0-9a-f]{64}', sha):
                raise ReviewSessionError('Invalid review report identity')
            body = _read_record(root, 'report-' + sha + '.json', 8 * 1024 * 1024)
            if file_receipt(body) != receipt:
                raise ReviewSessionError('Review report checksum mismatch')
            report = validate(json.loads(body))
            found = (copy.deepcopy(report), copy.deepcopy(state))
        return found

    def begin(self, root):
        directory = _mkdir(self.root, (uuid.uuid4().hex,))
        state = {'context': self.context, 'root': str(_root(root)), 'status': 'pending', 'report_status': 'pending',
                 'thread_id': None, 'turn_id': None, 'terminal_status': 'not_started',
                 'restart_policy': 'fresh_independent_review', 'phase_id': None, 'log': None}
        return ReviewAttempt(directory, state)


class ReviewAttempt:
    def __init__(self, root, state):
        self.root, self.state = root, copy.deepcopy(state)
        self.head, self.sequence = ZERO, 0
        self._append('prepared')

    def _append(self, event):
        body = encoded({'version': VERSION, 'sequence': self.sequence, 'previous': self.head,
                        'event': event, 'recorded_ns': time.time_ns(), 'state': self.state})
        sha = digest(body)
        _publish(self.root, f'{self.sequence:08d}-{sha}.json', body)
        self.head, self.sequence = sha, self.sequence + 1

    def started(self, phase_id, log, client_message_id):
        self.state.update(phase_id=phase_id, log=str(log), client_message_id=client_message_id)
        self._append('phase_started')

    def bind(self, thread_id, turn_id=None):
        if (not isinstance(thread_id, str) or not 1 <= len(thread_id) <= 256 or
                (turn_id is not None and (not isinstance(turn_id, str) or not 1 <= len(turn_id) <= 256))):
            raise ReviewSessionError('Invalid reviewer session identity')
        if self.state['thread_id'] not in (None, thread_id) or (turn_id and self.state['turn_id'] not in (None, turn_id)):
            raise ReviewSessionError('Reviewer session changed within an attempt')
        changed = self.state['thread_id'] != thread_id or (turn_id and self.state['turn_id'] != turn_id)
        self.state['thread_id'] = thread_id
        if turn_id:
            self.state['turn_id'] = turn_id
            if self.state['terminal_status'] not in TERMINAL:
                self.state['terminal_status'] = 'inProgress'
        if changed:
            self.state['status'] = 'running'
            self._append('session_bound')

    def observe(self, event):
        kind = event.get('type')
        if event.get('thread_id') != self.state['thread_id']:
            return  # Unrelated/subagent events are not the independent role's receipt.
        if kind == 'turn.started':
            self.bind(event['thread_id'], event.get('turn_id'))
        elif kind in ('turn.completed', 'turn.interrupted', 'turn.failed'):
            if (event.get('thread_id'), event.get('turn_id')) != (self.state['thread_id'], self.state['turn_id']):
                raise ReviewSessionError('Terminal event belongs to another reviewer turn')
            status = event.get('status')
            expected = {'turn.completed': 'completed', 'turn.interrupted': 'interrupted', 'turn.failed': 'failed'}[kind]
            if status != expected:
                raise ReviewSessionError('Invalid reviewer terminal status')
            self.state['terminal_status'] = status
            self._append('turn_terminal')
        # Generic errors and progress text are neither terminal nor approval.

    def pending(self, reason):
        if self.state['status'] == 'validated':
            raise ReviewSessionError('Cannot invalidate a committed report in place')
        self.state.update(status='pending', reason=str(reason))
        self._append('pending_fresh_review')

    def complete(self, report, validate):
        if (self.state['terminal_status'] != 'completed' or
                not self.state['thread_id'] or not self.state['turn_id']):
            raise ReviewSessionError('Only a completed reviewer turn can commit a report')
        report = validate(report)
        body = encoded(report)
        if len(body) > 8 * 1024 * 1024:
            raise ReviewSessionError('Reviewer report exceeds its limit')
        receipt = file_receipt(body)
        _publish(self.root, 'report-' + receipt['sha256'] + '.json', body)
        self.state.update(status='validated', report_status='validated', report=receipt)
        self._append('report_validated')
        # The first-view file must have identical serialization on an initial
        # pass and a cached pass; both return the canonical stored key order.
        return json.loads(body)
