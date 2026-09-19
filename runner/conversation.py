"""Lease-fenced website inbox/outbox; all credentials remain in the host process."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from attachments import metadata, validate_content
from durable import RPCError, redact_text
from progress import read_scoped
from resilience import WorkerHTTPError


class RevisionPending(RuntimeError):
    """Return from an isolated review to the author when user input arrives."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


def _uuid(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('Invalid conversation identifier')
    return value


def _publish_task_file(root, relative, data):
    """Create immutable task data through pinned directories, rejecting symlinks."""
    relative = Path(relative)
    if relative.is_absolute() or not relative.parts or any(x in ('.', '..') for x in relative.parts):
        raise ValueError('Unsafe task attachment path')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.parts[:-1]:
            try: os.mkdir(part, 0o700, dir_fd=directory)
            except FileExistsError: pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory); directory = child
        pending = '.host-' + uuid.uuid4().hex
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        try:
            os.link(pending, relative.name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        except FileExistsError:
            if read_scoped(root, relative, len(data)) != data:
                raise ValueError('Existing conversation file differs from its verified content')
        finally:
            # Only our newly created staging link is removed. Final files remain.
            os.unlink(pending, dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(directory)
    return relative.as_posix()


class Conversation:
    def __init__(self, cfg, task, job, journal, send, *, reporter=None, clock=time.monotonic):
        self.cfg, self.task, self.job, self.journal, self.send = cfg, task, Path(job), journal, send
        self.reporter, self.clock = reporter, clock
        self.next_poll = 0.0; self.next_flush = 0.0; self.last_checkpoint = None
        self.server_revision = max((m['cursor'] for m in journal.state['inbox'].values() if m['changes_input']), default=0)
        self.pending_public = {}; self.sent_public = set(); self.website_acked = set(); self.website_applied = set()
        self.outbox = journal.root / 'public-outbox'; self.outbox.mkdir(mode=0o700, exist_ok=True)
        if self.outbox.is_symlink(): raise ValueError('Unsafe host outbox')
        for path in sorted(self.outbox.glob('*.json')):
            if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > 40000:
                raise ValueError('Invalid public outbox record')
            item = json.loads(path.read_text())
            _uuid(item['id'])
            if not (self.outbox / (item['id'] + '.sent')).exists(): self.pending_public[item['id']] = item

    def api(self, action, value=None, *, raw=False, query=''):
        return self.send(self.cfg, f'/api/worker/{self.task["id"]}/conversation?action={action}' + query,
                         _json(value or {}), self.task['lease'], raw=raw)

    def _network(self, callback):
        try: return callback()
        except WorkerHTTPError as error:
            if not error.retryable: raise
            if self.reporter: self.reporter.event('working', 'Conversation connection retrying', category='note')
            return None

    def accept(self, row):
        identifier = _uuid(row.get('id')); cursor = row.get('seq'); kind = row.get('kind'); body = row.get('body')
        if type(cursor) is not int or cursor <= 0 or kind not in ('chat', 'revision') or not isinstance(body, str) or len(body) > 8000:
            raise ValueError('Invalid website message')
        items = metadata(row.get('attachments')); attached = []
        for item in items:
            relative = f'conversation-assets/{identifier}/{item["id"]}.{item["ext"]}'
            try: data = read_scoped(self.job, relative, item['size'])
            except FileNotFoundError:
                data = self.api('attachment', raw=True, query=f'&message={identifier}&file={item["id"]}')
            if len(data) != item['size'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError('Conversation attachment checksum mismatch')
            validate_content(data, item['ext'])
            _publish_task_file(self.job, relative, data)
            attached.append({'id':item['id'], 'path':relative, 'name':item['name'], 'bytes':len(data), 'sha256':item['sha256']})
        prefix = ('A user modification request for the presentation follows. Incorporate it into the current work, update relevant source/outline/scene/export evidence, and keep prior versions. '
                  if kind == 'revision' else
                  'A user chat message follows. Answer it conversationally; do not change presentation requirements or files unless the user submits a modification request. ')
        existed = identifier in self.journal.state['inbox']
        result = self.journal.accept_message(identifier, prefix + '\n\n' + body, attachments=attached,
                                             cursor=cursor, changes_input=kind == 'revision')
        if kind == 'revision': self.server_revision = max(self.server_revision, cursor)
        return result, not existed

    def context(self):
        state = self.journal.state
        messages = [{'id':m['id'], 'kind':'revision' if m['changes_input'] else 'chat',
                     'text':m['text'], 'attachments':m['attachments'], 'status':m['state']}
                    for m in sorted(state['inbox'].values(), key=lambda m:m['cursor'])
                    if m['changes_input'] or m['state']!='applied']
        if not messages: return None
        path = f'conversation-inputs/event-{state["sequence"]:08d}.json'
        _publish_task_file(self.job, path, _json({'revision':state['input_revision'], 'requests':messages}))
        return path

    def poll(self, *, server=None, thread_id=None, allow_steer=True, force=False):
        if not allow_steer and any(m['state'] in ('accepted','delivering','uncertain') for m in self.journal.state['inbox'].values()):
            raise RevisionPending('Pending user input must return to the author')
        if not force and self.clock() < self.next_poll: return False
        self.next_poll = self.clock() + 3
        response = self._network(lambda:self.api('poll'))
        if response is None: return False
        if not isinstance(response.get('messages'), list) or len(response['messages']) > 100:
            raise ValueError('Invalid website inbox response')
        changed = False
        for row in sorted(response['messages'], key=lambda row:row['seq']):
            _, new = self.accept(row); changed = changed or new
        self.server_revision = max(self.server_revision, int(response.get('revision', 0)))
        if changed:
            self.context()
            if self.reporter:
                self.reporter.event('working', 'New user message received', category='note')
                for kind in ('content', 'visual'): self.reporter.review_state(kind, 'pending')
        if changed and not allow_steer:
            raise RevisionPending('User input arrived during isolated review')
        if allow_steer and server is not None and thread_id:
            for message in self.journal.state['inbox'].values():
                if message['state'] in ('delivering', 'uncertain'):
                    server.reconcile_delivery(self.journal, message['id'])
            uncertain = [m for m in self.journal.state['inbox'].values() if m['state'] in ('delivering', 'uncertain')]
            if uncertain:
                raise RuntimeError('An earlier user message has an uncertain delivery receipt; preserved for recovery')
            for message in self.journal.pending_messages()[:10]:
                active = server.active_turns.get(thread_id)
                try: server.deliver(self.journal, message['id'], thread_id, active)
                except RPCError as error:
                    if self.journal.state['inbox'][message['id']]['state'] != 'accepted': raise
                    # The rejected input is still pending. Let the transport
                    # process the completion notification before its next poll.
                    self.next_poll = self.clock(); break
        self.flush()
        return changed

    def assistant(self, event, *, scope):
        if event.get('type') != 'assistant.message' or not event.get('complete'): return
        text = redact_text(event.get('body', ''), secrets=(self.cfg['token'], self.task['lease']), roots=(str(self.job),))
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text).strip()
        if not text: return
        for index, start in enumerate(range(0, len(text), 3500)):
            identifier = str(uuid.uuid5(uuid.UUID(self.task['id']), f'{scope}:{event.get("id")}:{index}'))
            item = {'id':identifier, 'body':text[start:start+3500]}
            _publish_task_file(self.outbox, identifier + '.json', _json(item))
            if not (self.outbox / (identifier + '.sent')).exists(): self.pending_public[identifier] = item

    def flush(self, *, force=False):
        if not force and self.clock() < self.next_flush: return
        self.next_flush = self.clock() + 2
        for identifier, item in list(self.pending_public.items())[:10]:
            if self._network(lambda:self.api('assistant', item)) is None: return
            marker = self.outbox / (identifier + '.sent')
            try:
                with marker.open('x') as stream: stream.write('acknowledged\n')
            except FileExistsError: pass
            self.pending_public.pop(identifier, None)
        inbox = self.journal.state['inbox']
        ack = [m['id'] for m in inbox.values() if m['state'] in ('acknowledged','applied') and m['id'] not in self.website_acked]
        for start in range(0, len(ack), 100):
            batch = ack[start:start+100]
            if self._network(lambda:self.api('ack', {'ids':batch})) is None: return
            self.website_acked.update(batch)
        applied = [m['id'] for m in inbox.values() if m['state'] == 'applied' and m['id'] not in self.website_applied]
        for start in range(0, len(applied), 100):
            batch = applied[start:start+100]
            if self._network(lambda:self.api('applied', {'ids':batch,'revision':self.server_revision})) is None: return
            self.website_applied.update(batch)

    def complete_chats(self, completed_turns, *, context_message_ids=(), context_turn=None):
        context_completed=completed_turns.get(context_turn,{}).get('status')=='completed'
        ids = [m['id'] for m in self.journal.state['inbox'].values()
               if not m['changes_input'] and m['state'] == 'acknowledged' and m.get('delivery') and
               (completed_turns.get((m['delivery']['thread_id'], m['delivery']['turn_id']), {}).get('status') == 'completed'
                or context_completed and m['id'] in context_message_ids)]
        if ids: self.journal.mark_applied(ids, self.job, artifacts=[])
        self.flush(force=True)

    def validated(self, artifacts):
        messages = self.journal.state['inbox']
        if any(m['state'] not in ('acknowledged','applied') for m in messages.values()):
            raise RevisionPending('Accepted user input still awaits model delivery')
        if any(not m['changes_input'] and m['state']!='applied' for m in messages.values()):
            raise RevisionPending('A user chat still awaits a completed response')
        ids = [m['id'] for m in messages.values() if m['state'] == 'acknowledged']
        if ids: self.journal.mark_applied(ids, self.job, artifacts=artifacts)
        self.flush(force=True)

    def checkpoint(self, *, phase=None, force=False):
        state = self.journal.state
        if not state.get('snapshot_id'): return
        identity = (state['snapshot_id'], self.server_revision, state['message_cursor'], phase)
        if identity == self.last_checkpoint and not force: return
        value = {'checkpointId':state['snapshot_id'], 'runId':state['run_id'],
                 'phase':phase or (state['phase'] or {}).get('name') or 'ready',
                 'pluginVersion':state['plugin_version'], 'revision':self.server_revision,
                 'lastMessageSeq':state['message_cursor'], 'resumable':True}
        if self._network(lambda:self.api('checkpoint', value)) is not None: self.last_checkpoint = identity
