"""Bounded HTTP recovery and one independent lease keeper per execution."""
import json
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit,parse_qs

class WorkerHTTPError(RuntimeError):
    def __init__(self,action,*,status=0,curl=0,reason='request failed',retryable=False):
        self.action,self.status,self.curl,self.retryable=action,status,curl,retryable
        # Never include response bodies, headers, request URLs or credentials.
        super().__init__(f'{action}: {reason}; HTTP {status or "unavailable"}; curl {curl}')

class HeartbeatLost(RuntimeError):
    pass

def request(cfg,path,body=b'{}',lease=None,raw=False):
    action=parse_qs(urlsplit(path).query).get('action',['claim'])[0]
    headers={'Authorization':'Bearer '+cfg['token'],'Content-Type':'application/json'}
    if lease:headers['X-Job-Lease']=lease
    if isinstance(body,bytes) and body[:2]==b'PK':headers['Content-Type']='application/vnd.openxmlformats-officedocument.presentationml.presentation'
    if isinstance(body,bytes) and body[:8]==b'\x89PNG\r\n\x1a\n':headers['Content-Type']='image/png'
    limit=10 if action in ('heartbeat','progress','preview','trace') else 180 if action=='bundle' else 20 if action=='claim' else 45
    maximum=10*1024*1024 if raw else 1024*1024
    # Claim can assign a different job if its response is lost. Retry/requeue is
    # version-conditional and requires an explicit operator decision on ambiguity.
    # Heartbeats and previews already have their own bounded background retries.
    attempts=3 if lease and action in ('attachment','complete','bundle','fail') else 1
    with tempfile.NamedTemporaryFile(prefix='pptx-request-') as payload, tempfile.NamedTemporaryFile(prefix='pptx-response-') as response:
        payload.write(body);payload.flush()
        config='url = '+json.dumps(cfg['site'].rstrip('/')+path)+'\nrequest = "POST"\n'
        for key,value in headers.items():config+='header = '+json.dumps(key+': '+value)+'\n'
        config+='data-binary = '+json.dumps('@'+payload.name)+'\n'
        command=['/usr/bin/curl','--silent','--show-error','--fail-with-body','--connect-timeout','8','--max-time',str(limit),
                 '--max-filesize',str(maximum),'--output',response.name,'--write-out','%{http_code}','--config','-']
        for attempt in range(attempts):
            response.seek(0);response.truncate()
            try:
                result=subprocess.run(command,input=config.encode(),capture_output=True,timeout=limit+5)
                try:status=int(result.stdout.strip())
                except (ValueError,TypeError):status=0
                if result.returncode or not 200<=status<300:
                    # curl16 is an HTTP/2 framing failure; defer it like a lost response.
                    transient=status in (408,425,429,500,502,503,504) or ((not status or 200<=status<300) and result.returncode in (5,6,7,16,18,28,35,52,55,56,92))
                    raise WorkerHTTPError(action,status=status,curl=result.returncode,retryable=transient)
                response.seek(0);data=response.read(maximum+1)
                if len(data)>maximum:raise WorkerHTTPError(action,status=status,reason='response too large')
                if raw:return data
                try:
                    value=json.loads(data)
                    if not isinstance(value,dict):raise ValueError()
                except (ValueError,UnicodeDecodeError):
                    raise WorkerHTTPError(action,status=status,reason='invalid JSON response',retryable=True) from None
                return value
            except subprocess.TimeoutExpired:
                error=WorkerHTTPError(action,curl=28,reason='transport timeout',retryable=True)
            except WorkerHTTPError as caught:
                error=caught
            if not error.retryable or attempt+1==attempts:raise error
            print(f'Worker request retry {attempt+1}/{attempts-1}: {error}',flush=True)
            time.sleep((1,3)[attempt])

class LeaseKeeper:
    def __init__(self,send,*,interval=20,retry_interval=5,max_silence=150,clock=time.monotonic,log=print):
        self.send,self.interval,self.retry_interval,self.max_silence=send,interval,retry_interval,max_silence
        self.clock,self.log=clock,log
        self.last_success=clock();self.error=None;self.fatal=None
        self.finished=threading.Event();self.thread=None

    def pulse(self):
        try:
            response=self.send()
            if response.get('ok') is not True:raise WorkerHTTPError('heartbeat',reason='invalid acknowledgement',retryable=True)
            self.last_success=self.clock()
            if self.error:self.log('Heartbeat recovered')
            self.error=None
            return True
        except WorkerHTTPError as error:
            # Completion may commit while an already-sent heartbeat is in flight.
            # Once the execution has exited, its final lease rejection is expected.
            if self.finished.is_set():return False
            self.error=error
            if not error.retryable:self.fatal=error
            self.log(f'Heartbeat retry: {error}' if error.retryable else f'Heartbeat rejected: {error}')
            return False
        except Exception as error:
            # Unknown local/programming errors are not presumed to be networking.
            self.fatal=error
            return False

    def check(self):
        if self.fatal:raise self.fatal
        if self.clock()-self.last_success>=self.max_silence:
            raise HeartbeatLost(f'No successful heartbeat for {self.max_silence} seconds; last error: {self.error}')

    def _loop(self):
        while not self.finished.is_set():
            success=self.pulse()
            if self.fatal:return
            if self.finished.wait(self.interval if success else self.retry_interval):return

    def __enter__(self):
        self.thread=threading.Thread(target=self._loop,name='pptx-lease',daemon=True)
        self.thread.start()
        return self

    def __exit__(self,*_):
        self.finish()
        if self.thread:self.thread.join(timeout=16)

    def finish(self):
        self.finished.set()
