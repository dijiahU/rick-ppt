"""Local-only delivery/preview/conversation transport; never calls website queues."""
import hashlib,json,os,threading,time,uuid
from pathlib import Path
from urllib.parse import parse_qs,urlsplit

def _write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_name('.'+path.name+'-'+uuid.uuid4().hex)
    with os.fdopen(os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

class LocalTransport:
    """Allowlisted worker protocol stored locally; this class has no networking.

    Every request and response gets an immutable receipt. Large previews/drafts/
    delivery are content-addressed binary files, not truncated JSON fields.
    Unknown routes fail closed, preventing accidental website fallback.
    """
    def __init__(self, root, task, attachments):
        self.root, self.task = Path(root), task
        self.attachments = attachments
        self.lock = threading.RLock()
        self.expected = None
        self.receipt = None
        self.base = '/api/worker/' + task['id']
        self.directory = self.root / 'local-worker'
        (self.directory / 'blobs').mkdir(parents=True, exist_ok=True, mode=0o700)
        self.sequence = len(list(self.directory.glob('request-*.json')))
        saved = self.directory / 'delivery-receipt.json'
        if saved.is_file():
            self.receipt = json.loads(saved.read_text())

    def __call__(self, cfg, path, data=None, lease=None, *, raw=False, **options):
        del cfg  # Never use site/token/account configuration.
        with self.lock:
            if lease != self.task['lease']:
                raise ValueError('Wrong local task lease')
            parsed = urlsplit(path)
            if parsed.scheme or parsed.netloc or parsed.fragment:
                raise ValueError('Local worker transport rejects absolute URLs')
            query = parse_qs(parsed.query)
            action = query.get('action', [''])[0]
            if action in ('delivery-ready','complete'):
                from resilience import TaskPaused,WorkerHTTPError
                if (self.root/'STOP').exists():raise TaskPaused('Task stopped before local delivery')
                current=max((json.loads(p.read_text())['seq'] for p in (self.root/'messages').glob('*.json')
                             if json.loads(p.read_text()).get('kind')=='revision'),default=0)
                if int(query['revision'][0])!=current:
                    raise WorkerHTTPError(action,status=412,reason='New revision arrived before local delivery')
            body = b'' if data is None else data
            if not isinstance(body, bytes):
                raise TypeError('Worker transport body must be bytes')
            request_sha = hashlib.sha256(body).hexdigest()
            blob = self.directory / 'blobs' / request_sha
            if not blob.exists():
                with blob.open('xb') as f:
                    f.write(body)
            response = None
            if parsed.path == self.base and action == 'attachment':
                response = self.attachments[query['file'][0]]
                if not raw:
                    raise ValueError('Attachment requires raw transport')
            elif parsed.path == self.base + '/conversation':
                if action == 'poll':
                    messages=sorted((self.root/'messages').glob('*.json'))
                    messages=[json.loads(p.read_text()) for p in messages]
                    response = {'ok': True, 'messages': messages,
                                'revision':max((m['seq'] for m in messages if m['kind']=='revision'),default=0),
                                'stop':(self.root/'STOP').exists()}
                elif action=='attachment' and raw:
                    identifier=query['file'][0]
                    if str(uuid.UUID(identifier))!=identifier:raise ValueError('Invalid message attachment identity')
                    response=(self.root/'message-files'/identifier).read_bytes()
                elif action in ('assistant', 'ack', 'applied', 'checkpoint'):
                    response = {'ok': True}
            elif parsed.path == self.base + '/usage' and action == 'usage':
                response = {'ok': True}
            elif parsed.path == self.base + '/draft':
                response = {'ok': True}
            elif parsed.path == self.base:
                if action in ('trace', 'progress', 'preview', 'heartbeat'):
                    response = {'ok': True, 'stop': (self.root/'STOP').exists()}
                elif action == 'delivery-ready':
                    self.expected = (query['sha256'][0], int(query['revision'][0]))
                    response = {'ok': True}
                elif action == 'delivery-reset':
                    self.expected=None;response={'ok':True}
                elif action == 'complete':
                    identity = (hashlib.sha256(body).hexdigest(), int(query['revision'][0]))
                    if identity != self.expected or query['sha256'][0] != identity[0]:
                        raise ValueError('Delivery bytes/revision differ from local ready receipt')
                    target = self.root / 'presentation.pptx'
                    if target.exists() and target.read_bytes() != body:
                        old=target.read_bytes();digest=hashlib.sha256(old).hexdigest()
                        versions=self.root/'versions';versions.mkdir(exist_ok=True)
                        saved=versions/(digest+'.pptx')
                        if not saved.exists():saved.write_bytes(old)
                        pending=self.root/('.delivery-'+uuid.uuid4().hex+'.pptx');pending.write_bytes(body)
                        os.replace(pending,target)
                    if not target.exists():
                        with target.open('xb') as f:
                            f.write(body)
                            f.flush()
                            os.fsync(f.fileno())
                    self.receipt = {'ok': True, 'status': 'complete', 'scope': 'portable-skill-local',
                                    'task_id': self.task['id'], 'lease_sha256': hashlib.sha256(lease.encode()).hexdigest(),
                                    'sha256': identity[0], 'revision': identity[1], 'bytes': len(body),
                                    'artifact': str(target), 'at_ms': time.time_ns() // 1000000}
                    _write(self.directory / 'delivery-receipt.json', self.receipt)
                    response = self.receipt
                elif action == 'delivery-status':
                    response = self.receipt or {'ok': True, 'status': 'pending'}
            if response is None:
                raise RuntimeError('Unsupported local worker route: ' + parsed.path + ' / ' + action)
            self.sequence += 1
            record = {'sequence': self.sequence, 'at_ms': time.time_ns() // 1000000,
                      'path': path, 'request_bytes': len(body), 'request_sha256': request_sha,
                      'request_blob': str(blob.relative_to(self.root)), 'raw': raw,
                      'response': {'bytes': len(response), 'sha256': hashlib.sha256(response).hexdigest()}
                      if isinstance(response, bytes) else response}
            _write(self.directory / ('request-%08d.json' % self.sequence), record)
            return response

