"""Bounded material preparation for one sequential presentation author.

Only the owner thread publishes task files, assets, progress and trajectory.
Workers receive a concrete request and copies of PNG references, not the deck,
author state, provider profile or parent Execution callbacks. Ready means prepared
evidence, never inspected/accepted by the author. No expensive automatic retries.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import time
import uuid

from assets import AssetImporter
from auxiliary_tools import AuxiliaryTools
from progress import read_scoped, public_text
from trajectory import record as capture

VERSION = 1
MAX_REQUEST = 64 * 1024
MAX_RESULT = 256 * 1024
MAX_TASKS = 64
STATES = {'queued', 'running', 'ready', 'failed', 'stale', 'cancelled', 'interrupted'}
IDENT = re.compile(r'[0-9a-f]{32}')
PAGE_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _tool_request(payload):
    return payload['request'] + '\nPurpose: ' + payload['purpose']


def _asset_key(record):
    """Preserve the key used by the ordinary importer when restoring a PNG."""
    name = record.get('file', '')
    provider = re.fullmatch(r'generated-(exec-[0-9a-f-]{36}\.png)', name)
    if provider:
        return provider.group(1)
    prefetched = re.fullmatch(r'generated-prefetch-([0-9a-f]{32})-(\d+)\.png', name)
    if prefetched:
        return 'prefetch:' + prefetched.group(1) + ':' + prefetched.group(2)
    return None


def _json(root, name, limit=2 * 1024 * 1024, optional=False):
    try:
        return json.loads(read_scoped(root, name, limit))
    except FileNotFoundError:
        if optional:
            return None
        raise


def _normal_page(page):
    # Asset readiness/file bookkeeping is not a change to the chosen expression.
    if not isinstance(page, dict):
        raise ValueError('Invalid decision page')
    result = dict(page)
    result['assets'] = [{key: value for key, value in asset.items()
                         if key not in ('file', 'status')}
                        for asset in page.get('assets', [])]
    return result


def file_basis(root, payload):
    """Public, task-file dependency contract, also reproduced by the CLI client."""
    outline = _json(root, 'outline.json')
    pages = {page['id']: page for page in outline['slides']}
    if any(ident not in pages for ident in payload['page_ids']):
        raise ValueError('Target page is absent from the current outline')
    plan = _json(root, 'decision-plan.json', optional=True)
    decisions = {page['id']: page for page in (plan or {}).get('pages', [])}
    caps = _json(root, 'capabilities.json', optional=True) or {}
    result = {'request': digest(_json(root, 'request.json', optional=True)),
              'outline': digest({key: value for key, value in outline.items()
                                 if key not in ('slides', 'revision')}),
              'pages': [{'id': ident, 'sha256': digest(pages[ident])} for ident in payload['page_ids']],
              'decision_task': (plan or {}).get('task'),
              'design_direction': digest((plan or {}).get('design_direction')),
              'decisions': [{'id': ident, 'sha256': digest(_normal_page(decisions[ident])),
                             'assets': [{key: asset.get(key) for key in ('route', 'kind')}
                                        for asset in decisions[ident].get('assets', [])]}
                            if ident in decisions else None
                            for ident in payload['page_ids']],
              'capabilities': {key: caps.get(key)
                               for key in ('web_search', 'image_generation')},
              'references': []}
    for name in payload['reference_files']:
        body = read_scoped(root, name, 20 * 1024 * 1024)
        if not AssetImporter.valid_png(body):
            raise ValueError('Generation references must be valid PNG files')
        result['references'].append({'file': name, 'sha256': hashlib.sha256(body).hexdigest()})
    return result


def validate_payload(value):
    if not isinstance(value, dict) or set(value) - {'kind', 'request', 'purpose', 'page_ids', 'reference_files', 'retry_of'}:
        raise ValueError('Unknown material request fields')
    result = dict(value)
    if result.get('kind') not in ('search', 'generate'):
        raise ValueError('Material kind must be search or generate')
    for key, limit in (('request', 8000), ('purpose', 800)):
        if not isinstance(result.get(key), str) or not 1 <= len(result[key].strip()) <= limit:
            raise ValueError('Provide a bounded concrete request and purpose')
        result[key] = result[key].strip()
    if len(_tool_request(result)) > 8000:
        raise ValueError('Request plus purpose exceeds the hosted tool 8000-character limit')
    ids = result.get('page_ids')
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 50 or
            any(not isinstance(item, str) or not PAGE_ID.fullmatch(item) for item in ids) or len(ids) != len(set(ids))):
        raise ValueError('Provide unique stable target page IDs')
    result['page_ids'] = sorted(ids)
    refs = result.setdefault('reference_files', [])
    if (not isinstance(refs, list) or len(refs) > 5 or
            any(not isinstance(name, str) or not re.fullmatch(r'assets/[A-Za-z0-9_.-]+\.png', name)
                or '..' in name for name in refs) or len(refs) != len(set(refs))):
        raise ValueError('References must be up to five task-local assets/*.png files')
    if result['kind'] == 'search' and refs:
        raise ValueError('Search requests do not accept image references')
    if 'retry_of' in result and (not isinstance(result['retry_of'], str) or not IDENT.fullmatch(result['retry_of'])):
        raise ValueError('retry_of must identify an earlier request')
    return result


class PrefetchCancelled(RuntimeError):
    pass


class MaterialToolFailure(ValueError):
    def __init__(self, message, calls=()):
        super().__init__(message)
        self.calls = list(calls)


class MaterialPrefetchBroker:
    def __init__(self, cfg, job, *, images=None, reporter=None, trajectory=None,
                 lease_check=None, input_revision=None, deadline=None):
        self.job = Path(job).absolute()
        # Opening before resolving refuses a symlinked task root.
        fd = os.open(self.job, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        os.close(fd)
        self.cfg = {key: cfg[key] for key in ('default_model', 'default_reasoning_effort', '_usage_ledger') if key in cfg}
        self.cfg['_usage_stage'] = 'prefetch'
        self.images = images if images is not None else {}
        self.reporter, self.trajectory = reporter, trajectory
        self.lease_check, self.input_revision, self.deadline = lease_check, input_revision, deadline
        self.owner = threading.get_ident()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='pptx-material')
        self.pending, self.records = {}, {}
        self.closed = False
        self._mkdir('prefetch-requests')
        self._mkdir('material-prefetch')
        # Migrate any prior restoration aliases in place. The normal importer
        # tests its exact provider filename key, so a second alias consumes quota.
        by_file = {}
        for key, record in list(self.images.items()):
            if not isinstance(record, dict) or not isinstance(record.get('file'), str):
                continue
            canonical = _asset_key(record) or key
            if record['file'] not in by_file:
                by_file[record['file']] = canonical
                if canonical != key:
                    self.images.setdefault(canonical, record)
            if key != by_file[record['file']]:
                self.images.pop(key, None)
        # Merge actual existing image records without replacing the shared object.
        for record in (_json(self.job, 'assets/index.json', optional=True) or {}).get('images', []):
            if not isinstance(record, dict) or not isinstance(record.get('file'), str):
                continue
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.png', record['file']):
                continue
            try:
                body = read_scoped(self.job, 'assets/' + record['file'], 20 * 1024 * 1024)
                if not AssetImporter.valid_png(body) or hashlib.sha256(body).hexdigest() != record.get('sha256'):
                    continue
                if record['file'] not in by_file:
                    key = _asset_key(record) or 'restored:' + record['file']
                    self.images[key] = record
                    by_file[record['file']] = key
            except (OSError, ValueError):
                continue
        self._restore()
        self._index()

    def _owner(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError('Material broker publication belongs to the owner thread')

    def _mkdir(self, relative):
        fd = os.open(self.job, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for component in Path(relative).parts:
                if component in ('.', '..') or '/' in component:
                    raise ValueError('Invalid material directory')
                try:
                    os.mkdir(component, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
        finally:
            os.close(fd)

    def _publish(self, relative, body):
        path = Path(relative)
        if path.is_absolute() or any(part in ('.', '..') for part in path.parts):
            raise ValueError('Invalid material output path')
        fd = os.open(self.job, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in path.parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            name = '.host-' + uuid.uuid4().hex
            child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(child, 'wb') as stream:
                stream.write(body)
            os.replace(name, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        finally:
            os.close(fd)

    def _revision(self):
        value = self.input_revision() if callable(self.input_revision) else self.input_revision
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('Invalid material input revision')
        return value

    def _basis(self, payload):
        return {'files': file_basis(self.job, payload), 'input_revision': self._revision()}

    def _allowed(self, payload, basis):
        data = basis['files']
        task = data['decision_task'] or {}
        caps = data['capabilities']
        if payload['kind'] == 'search':
            if task.get('research') not in ('topic_research', 'targeted_verification'):
                raise ValueError('Select an existing permitted research branch before prefetching search material')
            if (caps.get('web_search') or {}).get('mode') in ('disabled', 'unavailable'):
                raise ValueError('The current task search channel is disabled')
        else:
            if (caps.get('image_generation') or {}).get('mode') in ('disabled', 'unavailable'):
                raise ValueError('Image generation is disabled for this task')
            if not data['decisions'] or any(page is None or not any(
                    asset.get('route') == 'generate' and asset.get('kind') == 'illustrative'
                    for asset in page.get('assets', [])) for page in data['decisions']):
                raise ValueError('Select a generate/illustrative asset route on each target page first')
            if len(self.images) >= 12:
                raise ValueError('Global generated-image limit reached; reuse existing material')

    def _save(self, record):
        self._publish('material-prefetch/' + record['id'] + '.json', encoded(record))

    def _index(self):
        self._publish('material-prefetch/index.json', encoded({'version': VERSION, 'requests': [
            self._view(record) for record in self.records.values()]}))

    def _view(self, record, full=False):
        fields = ('id', 'state', 'payload_sha256', 'basis_sha256', 'result_sha256', 'error',
                  'created_at', 'updated_at', 'started_at', 'completed_at', 'seconds', 'calls')
        view = {key: record[key] for key in fields if key in record}
        view['payload'] = record['payload'] if full else {key: record['payload'][key]
                         for key in ('kind', 'page_ids', 'purpose')}
        if full:
            view['basis'] = record['basis']
        return view

    def _restore(self):
        fd = os.open(self.job / 'material-prefetch', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            names = sorted(name for name in os.listdir(fd) if re.fullmatch(r'[0-9a-f]{32}\.json', name))
        finally:
            os.close(fd)
        for name in names[:MAX_TASKS + 1]:
            if not re.fullmatch(r'[0-9a-f]{32}\.json', name):
                continue
            try:
                record = _json(self.job, 'material-prefetch/' + name, MAX_REQUEST + MAX_RESULT)
                if record.get('id') + '.json' != name or record.get('version') != VERSION or record.get('state') not in STATES:
                    continue
                payload = validate_payload(record['payload'])
                if digest(payload) != record['payload_sha256'] or digest(record['basis']) != record['basis_sha256']:
                    continue
                if record['state'] in ('queued', 'running'):
                    record.update(state='interrupted', error='Previous execution ended; submit an explicit retry to run again')
                if record['state'] == 'ready':
                    result = _json(self.job, 'material-prefetch/' + record['id'] + '.result.json', MAX_RESULT)
                    if digest(result) != record['result_sha256']:
                        raise ValueError('Saved material result changed')
                    self._verify_result(result)
                self.records[record['id']] = record
                self._refresh(record)
                self._save(record)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                # A corrupt record cannot authorize a run or return a ready result.
                continue

    def _refresh(self, record):
        if record['state'] in ('stale', 'cancelled', 'failed', 'interrupted'):
            return True
        try:
            same = digest(self._basis(record['payload'])) == record['basis_sha256']
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            # A sequential author can be in the middle of writing JSON. This is
            # not evidence that every prepared result became permanently stale.
            return False
        except ValueError:
            same = False
        if not same:
            self._transition(record, 'stale', 'Target content, selected route or task inputs changed')
            if record['id'] in self.pending:
                self.pending[record['id']][1].set()
        return True

    def _transition(self, record, state, error=None):
        record.update(state=state, updated_at=time.time())
        if state == 'running':
            record.setdefault('started_at', time.time())
        if state in ('ready', 'failed', 'stale', 'cancelled', 'interrupted'):
            record['completed_at'] = time.time()
            record['seconds'] = round(max(0, record['completed_at'] - record.get('started_at', record['completed_at'])), 3)
        if error:
            record['error'] = public_text(error)
        self._save(record)
        if self.reporter:
            self.reporter.event('edited' if state == 'ready' else 'working',
                                'Material preparation ' + state + ': ' + public_text(record['payload']['purpose'], 180),
                                state='completed' if state == 'ready' else 'failed' if state == 'failed' else 'started',
                                category='search' if record['payload']['kind'] == 'search' else 'media')
        capture(self.trajectory, 'emit', 'material_prefetch.state', {'id': record['id'], 'state': state,
                'kind': record['payload']['kind'], 'page_ids': record['payload']['page_ids']})

    def submit(self, payload, *, identifier=None):
        self._owner()
        if self.closed:
            raise ValueError('Material preparation is closed')
        if self.lease_check:
            self.lease_check()
        payload = validate_payload(payload)
        if payload.get('retry_of') and payload['retry_of'] not in self.records:
            raise ValueError('Explicit retry must identify an existing material request')
        basis = self._basis(payload)
        self._allowed(payload, basis)
        payload_hash, basis_hash = digest(payload), digest(basis)
        for record in self.records.values():
            self._refresh(record)
            if record['payload_sha256'] == payload_hash and record['basis_sha256'] == basis_hash:
                # Failed/interrupted results also deduplicate: rerun is always explicit.
                return self._view(record)
        if len(self.records) >= MAX_TASKS:
            raise ValueError('Task material request limit reached')
        ident = identifier or uuid.uuid4().hex
        if not IDENT.fullmatch(ident) or ident in self.records:
            raise ValueError('Invalid or reused material request ID')
        self._mkdir('material-prefetch')
        record = {'version': VERSION, 'id': ident, 'payload': payload,
                  'payload_sha256': payload_hash, 'basis': basis, 'basis_sha256': basis_hash,
                  'state': 'queued', 'created_at': time.time(), 'updated_at': time.time()}
        self.records[ident] = record
        self._save(record)
        self._index()
        return self._view(record)

    def status(self, identifiers=None):
        self._owner()
        records = list(self.records.values()) if identifiers is None else [self.records[self._resolve(ident)] for ident in identifiers]
        views = []
        for record in records:
            verified = self._refresh(record)
            view = self._view(record)
            if not verified:
                view.update(state='interrupted', verification_pending=True,
                            error='Current inputs are being written or cannot yet be verified; check again')
            views.append(view)
        self._index()
        return views

    def _verify_result(self, result):
        if not isinstance(result, dict) or not isinstance(result.get('text'), str) or len(result['text']) > 32000:
            raise ValueError('Invalid prepared evidence')
        files = result.get('files', [])
        if not isinstance(files, list) or len(files) > 12:
            raise ValueError('Invalid material files')
        for record in files:
            name = record.get('path', '')
            if not re.fullmatch(r'assets/generated-prefetch-[0-9a-f]{32}-\d+\.png', name):
                raise ValueError('Invalid prepared asset path')
            body = read_scoped(self.job, name, 20 * 1024 * 1024)
            if not AssetImporter.valid_png(body) or hashlib.sha256(body).hexdigest() != record.get('sha256'):
                raise ValueError('Prepared asset checksum changed')

    def _resolve(self, identifier):
        if not isinstance(identifier, str) or not IDENT.fullmatch(identifier):
            raise ValueError('Invalid material request ID')
        if identifier in self.records:
            return identifier
        reply = _json(self.job, 'prefetch-requests/' + identifier + '.reply.json', MAX_REQUEST, optional=True)
        actual = (reply or {}).get('request', {}).get('id')
        if not isinstance(actual, str) or not IDENT.fullmatch(actual) or actual not in self.records:
            raise KeyError(identifier)
        return actual

    def get(self, identifier):
        self._owner()
        identifier = self._resolve(identifier)
        record = self.records[identifier]
        verified = self._refresh(record)
        view = self._view(record, full=True)
        if not verified:
            view.update(state='interrupted', verification_pending=True,
                        error='Current inputs are being written or cannot yet be verified; check again')
            return view
        if record['state'] == 'ready':
            try:
                result = _json(self.job, 'material-prefetch/' + identifier + '.result.json', MAX_RESULT)
                if digest(result) != record['result_sha256']:
                    raise ValueError('Prepared result checksum changed')
                self._verify_result(result)
                view['result'] = result
            except (OSError, ValueError):
                self._transition(record, 'failed', 'Prepared result or asset checksum changed')
                view = self._view(record, full=True)
        self._index()
        return view

    def cancel(self, identifier):
        self._owner()
        identifier = self._resolve(identifier)
        record = self.records[identifier]
        if record['state'] in ('queued', 'running'):
            if identifier in self.pending:
                self.pending[identifier][1].set()
            self._transition(record, 'cancelled', 'Cancelled by the author or task owner')
        self._index()
        return self._view(record)

    def _worker(self, payload, references, cancelled):
        # Never run the parent tick, importer, trajectory or reporter in a worker.
        def tick():
            if cancelled.is_set() or self.closed:
                raise PrefetchCancelled('Material preparation cancelled')
            if self.deadline is not None and time.monotonic() >= self.deadline:
                raise PrefetchCancelled('Material preparation deadline exceeded')
            if self.lease_check:
                self.lease_check()
        tick()
        with tempfile.TemporaryDirectory(prefix='pptx-material-worker-') as directory:
            stage = Path(directory).resolve()
            (stage / 'assets').mkdir()
            for name, body in references:
                (stage / 'assets' / name).write_bytes(body)
            helper = AuxiliaryTools(self.cfg, stage, importer=AssetImporter(stage), tick=tick)
            args = {'request': _tool_request(payload)}
            if payload['kind'] == 'generate':
                args['reference_files'] = ['assets/' + name for name, _ in references]
            response = helper.handle({'tool': 'pptx_search_sources' if payload['kind'] == 'search' else 'pptx_generate_image',
                                      'arguments': args})
            tick()
            if response.get('success') is not True:
                diagnostic = '\n'.join(item.get('text', '') for item in response.get('contentItems', [])
                                       if isinstance(item, dict) and isinstance(item.get('text'), str))
                raise MaterialToolFailure(public_text(diagnostic, 1600) or 'Hosted material tool did not complete', helper.calls)
            output = json.loads(response['contentItems'][0]['text'])
            if not isinstance(output, dict) or not isinstance(output.get('text'), str) or len(output['text']) > 32000:
                raise ValueError('Hosted material tool returned an invalid result')
            files = output.get('files', [])
            if not isinstance(files, list) or len(files) > 12 or (payload['kind'] == 'search' and files):
                raise ValueError('Unexpected hosted material files')
            collected = []
            for item in files:
                name = item.get('file', '')
                if not re.fullmatch(r'generated-exec-[0-9a-f-]{36}\.png', name):
                    raise ValueError('Hosted material output is not a generated PNG')
                body = read_scoped(stage, 'assets/' + name, 20 * 1024 * 1024)
                if not AssetImporter.valid_png(body) or hashlib.sha256(body).hexdigest() != item.get('sha256'):
                    raise ValueError('Hosted material PNG failed validation')
                collected.append(body)
            if payload['kind'] == 'generate' and not collected:
                raise ValueError('No actual generated PNG was prepared')
            return {'text': output['text'], 'model': output.get('model'), 'files': collected,
                    'calls': helper.calls, 'kind': payload['kind']}

    def _finish(self, record, result):
        bodies = result.pop('files')
        record['calls'] = result.get('calls', [])
        if len(self.images) + len(bodies) > 12:
            raise ValueError('Global generated-image limit reached; prepared files were not imported')
        imported = AssetImporter(self.job, trajectory=self.trajectory)
        output = {**result, 'files': [], 'page_ids': record['payload']['page_ids'],
                  'purpose': record['payload']['purpose'], 'author_inspection': 'not_yet_inspected_or_selected',
                  'source': 'hosted search evidence' if record['payload']['kind'] == 'search' else 'built-in generated concept; not documentary evidence'}
        for index, body in enumerate(bodies):
            name = 'generated-prefetch-' + record['id'] + '-' + str(index) + '.png'
            key = 'prefetch:' + record['id'] + ':' + str(index)
            asset = {'file': name, 'sha256': hashlib.sha256(body).hexdigest(), 'source': 'built-in image generation',
                     'prefetch_request_id': record['id']}
            imported._publish(name, body, {**self.images, key: asset})
            self.images[key] = asset
            output['files'].append({**asset, 'path': 'assets/' + name})
        raw = encoded(output)
        if len(raw) > MAX_RESULT:
            raise ValueError('Prepared material result exceeds its limit')
        self._publish('material-prefetch/' + record['id'] + '.result.json', raw)
        record['result_sha256'] = digest(output)
        self._transition(record, 'ready')

    def _requests(self):
        fd = os.open(self.job / 'prefetch-requests', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            entries = set(os.listdir(fd))
            # Finished history is immutable and may grow. Apply the work budget
            # only after filtering receipts, otherwise old low IDs starve new IDs.
            names = sorted(name for name in entries
                           if re.fullmatch(r'[0-9a-f]{32}\.request\.json', name)
                           and name.split('.')[0] + '.reply.json' not in entries)[:512]
        finally:
            os.close(fd)
        # Submits are registered before cancellations even when random request
        # filenames sort in the opposite order. No task starts until both passes.
        for action in ('submit', 'cancel'):
            for name in names:
                if not re.fullmatch(r'[0-9a-f]{32}\.request\.json', name):
                    continue
                ident = name.split('.')[0]
                try:
                    read_scoped(self.job, 'prefetch-requests/' + ident + '.reply.json', MAX_REQUEST)
                    continue
                except FileNotFoundError:
                    pass
                except (OSError, ValueError):
                    self._publish('prefetch-requests/' + ident + '.reply.json', encoded(
                        {'ok': False, 'request_id': ident, 'state': 'failed', 'error': 'Invalid material queue receipt'}))
                    continue
                try:
                    data = _json(self.job, 'prefetch-requests/' + name, MAX_REQUEST)
                    if not isinstance(data, dict) or set(data) - {'action', 'payload', 'id'}:
                        raise ValueError('Unknown material queue fields')
                    if data.get('action') not in ('submit', 'cancel'):
                        raise ValueError('Unknown material queue action')
                    if data['action'] != action:
                        continue
                    if action == 'submit':
                        view = self.submit(data.get('payload'), identifier=ident)
                    elif isinstance(data.get('id'), str):
                        view = self.cancel(data['id'])
                    else:
                        raise ValueError('Invalid material cancellation ID')
                    response = {'ok': True, 'request_id': ident, 'request': view}
                except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                    response = {'ok': False, 'request_id': ident, 'state': 'failed',
                                'error': public_text(str(error)) or type(error).__name__}
                self._publish('prefetch-requests/' + ident + '.reply.json', encoded(response))

    def poll(self, start_new=True):
        self._owner()
        if self.closed:
            return
        try:
            if self.lease_check:
                self.lease_check()
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self.close()
                return
            for record in self.records.values():
                self._refresh(record)
            for ident, (future, cancelled) in list(self.pending.items()):
                if not future.done():
                    continue
                record = self.records[ident]
                if not self._refresh(record):
                    continue
                del self.pending[ident]
                try:
                    result = future.result()
                    if record['state'] == 'running':
                        self._finish(record, result)
                except Exception as error:
                    if record['state'] == 'running':
                        if hasattr(error, 'calls'):
                            record['calls'] = error.calls
                        else:
                            record.setdefault('calls', [])
                        self._transition(record, 'cancelled' if isinstance(error, PrefetchCancelled) else 'failed',
                                         public_text(str(error), 1600) or type(error).__name__)
            self._requests()
            if start_new:
                for record in self.records.values():
                    if len(self.pending) >= 2:
                        break
                    if record['state'] != 'queued':
                        continue
                    if not self._refresh(record):
                        continue
                    if record['state'] != 'queued':
                        continue
                    # Reserve at least one image slot for each active generation
                    # so a known exhausted quota does not trigger a paid attempt.
                    active_generations = sum(self.records[ident]['payload']['kind'] == 'generate'
                                             for ident in self.pending)
                    if (record['payload']['kind'] == 'generate' and len(self.images) < 12
                            and len(self.images) + active_generations >= 12):
                        continue
                    try:
                        self._allowed(record['payload'], record['basis'])
                        refs = [(Path(name).name, read_scoped(self.job, name, 20 * 1024 * 1024))
                                for name in record['payload']['reference_files']]
                        cancelled = threading.Event()
                        self._transition(record, 'running')
                        self.pending[record['id']] = (self.pool.submit(self._worker, record['payload'], refs, cancelled), cancelled)
                    except (OSError, ValueError) as error:
                        self._transition(record, 'failed', str(error))
            self._index()
        except BaseException:
            self.close()
            raise

    def close(self):
        self._owner()
        if self.closed:
            return
        self.closed = True
        for future, cancelled in self.pending.values():
            cancelled.set()
            future.cancel()
        for record in self.records.values():
            if record['state'] in ('queued', 'running'):
                self._transition(record, 'interrupted', 'Execution stopped; completed historical results are retained')
        self._index()
        self.pool.shutdown(wait=False, cancel_futures=True)
