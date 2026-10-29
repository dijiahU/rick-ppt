"""Bounded output-based continuity for the author, never an aesthetic gate.

Only completed tools advance the counter. Waiting for an API, rendering or user
input never does. State is host-private and survives worker recovery.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import uuid
import zipfile

from progress import read_scoped

MARKER = 'references/execution-continuity.md'
TOOLS = {'command_execution', 'image_view', 'web_search', 'mcp_tool_call',
         'dynamic_tool_call', 'file_change', 'image_generation'}
SKIP = {'tmp', 'fonts', 'render-requests', 'font-requests', 'media-requests',
        'support-versions', 'material-prefetch', '.git', '__pycache__', 'snapshots',
        'renders', 'review-packet', 'host-evaluation', 'references'}


class ProgressStalled(RuntimeError):
    pass


def enabled(cfg):
    return (Path(cfg['plugin']) / 'skills/pptx' / MARKER).is_file()


def stage_role(name):
    if name == 'research': return 'research'
    if name == 'author' or re.fullmatch(r'repair-[12]', name): return 'author'
    return None


def compact_resume(job, name, context=None):
    """Pointers to current evidence, not another copy of all phase instructions."""
    root = Path(job)
    names = ['request.json', 'outline.json', 'source-notes.md', 'decision-plan.json', 'planning-input.json',
             'assets/web-index.json',
             'repair-target.json', 'tool-manifest.json', 'tool-quickstart.md']
    documents = []
    for name_ in names:
        try: body = read_scoped(root, name_, 2 * 1024 * 1024)
        except FileNotFoundError: continue
        except (OSError, ValueError):
            documents.append({'path': name_, 'read_current_file': True}); continue
        documents.append({'path': name_, 'sha256': hashlib.sha256(body).hexdigest()})
    return ('HOST PHASE CONTINUATION\n'
            f'Continue the interrupted {name} phase in the CURRENT working directory. '
            'Use task-relative paths; absolute paths in old messages are historical. '
            'Retain actual pages, source material, protected edits and native behavior. '
            'The original phase requirements still apply; they are not being relaxed. '
            'Read current request.json and changed/needed evidence below. Use the exact '
            'interpreter, selected parts directory and commands in tool-quickstart.md / '
            'tool-manifest.json. Do not scan tool source or repeat unchanged preparation '
            'without a specific unresolved API question. Continue from saved work.\n'
            + json.dumps({'stage': name, 'current_documents': documents,
                          'conversation_context': context}, ensure_ascii=False))


def progress_note(role):
    action = ('Record verified findings and unresolved questions in source-notes.md, '
              'then complete the supported outline/decision handoff when ready. '
              'Do not invent evidence or pretend unresolved required inputs exist.'
              if role == 'research' else
              'Apply the main relationship to the current native page in presentation '
              'order, or execute saved authoring work. Inspect the actual render before '
              'fine color/spacing work. A partial page is revisable; do not lock a failed '
              'composition. Preserve scope, meaning, editability and required animation.')
    return ('HOST OUTPUT-PROGRESS CHECK: completed tool actions have not changed the '
            'phase outputs. Repeated file listing, tool-source reading, image crops, '
            'color sampling and status messages alone are not a completed handoff/page. '
            + action + ' All normal validation and independent reviews remain required.')


def fresh_prompt(cfg, root, name, original, context=None):
    from phase_context import prepared_phase_context
    prefix = original.split('\n\nHOST-PREPARED CURRENT PHASE DOCUMENTS\n', 1)[0]
    stage = 'repair' if name.startswith('repair-') else name
    return (prefix + prepared_phase_context(cfg, root, stage) + '\n'
            + compact_resume(root, name, context))


def same_phase_recovery(state, name, thread):
    previous = state.get('phase') or {}
    return bool(thread and previous.get('name') == name
                and previous.get('status') == 'interrupted'
                and previous.get('thread_id') == thread
                and previous.get('input_revision') == state.get('input_revision'))


def inbox_clear(journal):
    return not any(m['state'] != 'applied' for m in journal.state['inbox'].values())


def declared_output(root,recoveries=()):
    """A declared candidate is a phase handoff, never an accepted delivery.

    Full authored-contract checks, frozen rendering and independent reviews run
    after this boundary. Never select a file by its age or a model's prose.
    """
    try:
        value=json.loads(read_scoped(root,'delivery.json',10000))
        if not isinstance(value,dict):return None
        from recovery_workspace import resolve_delivery
        value=resolve_delivery(value,root,recoveries)
        path=value.get('path')
        if not isinstance(path,str) or Path(path).suffix.lower()!='.pptx':return None
        body=read_scoped(Path(root).resolve(strict=True),Path(path),30*1024*1024)
        from office_policy import validate_delivery
        validate_delivery(body,single_file=True)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            if 'ppt/presentation.xml' not in archive.namelist() or '[Content_Types].xml' not in archive.namelist():return None
        return {'path':path,'sha256':hashlib.sha256(body).hexdigest()}
    except (OSError,ValueError,zipfile.BadZipFile):return None


class OutputProgress:
    def __init__(self, root, records, task_id, name, revision, window=12):
        if type(window) is not int or not 4 <= window <= 100:
            raise ValueError('progress_action_window must be an integer from 4 to 100')
        self.root, self.records = Path(root), Path(records)
        self.role, self.window = stage_role(name), window
        self.active, self.seen, self.pending = set(), set(), 0
        self.cache = {}
        key = hashlib.sha256(json.dumps([task_id, name, revision]).encode()).hexdigest()
        self.path = self.records / ('output-progress-' + key + '.json')
        try: self.state = json.loads(read_scoped(self.records, self.path.name, 32768))
        except FileNotFoundError:
            self.state = {'fingerprint': None, 'quiet_actions': 0, 'nudged': False, 'rebuilds': 0}
        if (not isinstance(self.state, dict) or set(self.state) != {'fingerprint', 'quiet_actions', 'nudged', 'rebuilds'}
                or type(self.state['quiet_actions']) is not int or self.state['quiet_actions'] < 0
                or type(self.state['nudged']) is not bool or type(self.state['rebuilds']) is not int
                or self.state['rebuilds'] not in (0, 1)):
            raise ValueError('Invalid host output-progress state')
        initial = self.fingerprint()
        if initial is not None and initial != self.state['fingerprint']:
            self.state.update(fingerprint=initial, quiet_actions=0, nudged=False)
        self.save()

    def save(self):
        temp = self.path.with_name('.' + self.path.name + '-' + uuid.uuid4().hex)
        with os.fdopen(os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as f:
            json.dump(self.state, f)
        os.replace(temp, self.path)

    def fingerprint(self):
        entries, scanned, total = [], 0, 0
        for base, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not (Path(base) / d).is_symlink())
            for filename in sorted(files):
                scanned += 1
                if scanned > 20000: return None  # Cannot establish stagnation.
                p = Path(base) / filename; rel = p.relative_to(self.root)
                planning = self.role == 'research' and rel.as_posix() in (
                    'outline.json', 'source-notes.md', 'decision-plan.json', 'planning-input.json',
                    'assets/index.json', 'assets/web-index.json')
                native = self.role == 'author' and (('ppt' in rel.parts and any(
                    x in rel.parts for x in ('slides', 'charts', 'media', 'embeddings')))
                    or 'native-pages' in rel.parts and p.suffix == '.json'
                    or p.suffix == '.pptx' and filename not in ('blank.pptx', 'original.pptx'))
                if not (planning or native) or p.is_symlink(): continue
                try:
                    st = p.stat(); sig = (st.st_size, st.st_mtime_ns)
                    if self.cache.get(str(rel), (None,))[0] == sig:
                        digest = self.cache[str(rel)][1]
                    elif p.suffix == '.pptx':
                        with zipfile.ZipFile(io.BytesIO(read_scoped(self.root, rel, 64 * 1024 * 1024))) as z:
                            if len(z.namelist()) > 20000: return None
                            parts = sorted(n for n in z.namelist() if re.fullmatch(
                                r'ppt/(slides|charts)/[^/]+\.xml', n))
                            if sum(z.getinfo(n).file_size for n in parts) > 32 * 1024 * 1024: return None
                            digest = hashlib.sha256(b''.join(n.encode() + z.read(n) for n in parts)).hexdigest()
                    else:
                        if st.st_size > 32 * 1024 * 1024: return None
                        body = read_scoped(self.root, rel, 32 * 1024 * 1024)
                        if planning and rel.as_posix() == 'planning-input.json':
                            # planning_commit's real draft is saved before the
                            # three canonical outputs exist. Count substantive
                            # content changes, never formatting or a placeholder.
                            try:
                                draft = json.loads(body)
                                from outline import validate_outline
                                if (not isinstance(draft, dict) or draft.get('version') != 1
                                        or not isinstance(draft.get('decisions'), dict)
                                        or not isinstance(draft.get('source_notes'), str)
                                        or not draft['source_notes'].strip()):
                                    continue
                                validate_outline(draft.get('outline'))
                                body = json.dumps(draft, sort_keys=True, ensure_ascii=False,
                                                  separators=(',', ':')).encode()
                            except (ValueError, TypeError):
                                continue
                        total += len(body)
                        if total > 128 * 1024 * 1024: return None
                        digest = hashlib.sha256(body).hexdigest()
                    self.cache[str(rel)] = (sig, digest); entries.append((str(rel), digest))
                    if (p.stat().st_size, p.stat().st_mtime_ns) != sig: return None
                except (OSError, ValueError, zipfile.BadZipFile): return None
        return hashlib.sha256(json.dumps(sorted(entries)).encode()).hexdigest()

    def observe(self, event):
        item = event.get('item') or {}
        if item.get('type') not in TOOLS: return
        key = (event.get('thread_id'), event.get('turn_id'), item.get('id'))
        if not key[-1]: return
        if event.get('type') == 'item.started': self.active.add(key)
        if event.get('type') == 'item.completed':
            # A yielded shell command has not finished. Leave it active until
            # its terminal receipt; never rebuild while it may still write.
            if item.get('type') == 'command_execution' and item.get('exit_code') is None:
                self.active.add(key)
                return
            self.active.discard(key)
            if key not in self.seen:
                self.seen.add(key); self.pending += 1

    def action(self, *, missing_outputs=False):
        if self.active or not self.pending and not missing_outputs: return None
        fingerprint = self.fingerprint()
        if fingerprint is None: return None
        if fingerprint != self.state['fingerprint']:
            self.state.update(fingerprint=fingerprint, quiet_actions=0, nudged=False)
        else: self.state['quiet_actions'] += self.pending
        self.pending = 0; self.save()
        if not missing_outputs and self.state['quiet_actions'] < self.window: return None
        if not self.state['nudged']: return 'nudge'
        if self.state['rebuilds'] == 0: return 'rebuild'
        return 'stalled'

    def applied(self, action):
        self.state.update(quiet_actions=0, nudged=True)
        if action == 'rebuild': self.state['rebuilds'] = 1
        self.save()

    def outputs_present(self):
        required = ('outline.json', 'source-notes.md', 'decision-plan.json') if self.role == 'research' else ('delivery.json',)
        return all((self.root / name).is_file() for name in required)
