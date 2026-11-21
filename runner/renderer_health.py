"""Gate queue admission on the actual local rendering dependency, before model work."""
import subprocess,time,threading,sys,shutil,os,signal

DOCKER='/usr/local/bin/docker'
IMAGE='pptx-lab-renderer:1'
QUALIFIED_IMAGE='docker.io/library/'+IMAGE

def run_group(args,*,capture_output=True,text=True,timeout=None):
    """subprocess.run that also kills the command's children on timeout.

    A wedged Docker Desktop makes `docker info` hang in its CLI-plugin metadata
    children; plain run() kills only the docker CLI, leaving one orphan per check."""
    proc=subprocess.Popen(args,stdout=subprocess.PIPE if capture_output else None,
                          stderr=subprocess.PIPE if capture_output else None,text=text,start_new_session=True)
    try:out,err=proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except OSError:pass
        proc.communicate()
        raise
    return subprocess.CompletedProcess(args,proc.returncode,out,err)

class RendererReadiness:
    def __init__(self,*,run=run_group,clock=time.monotonic,on_state=None,log=print,min_free_gb=3,free_bytes=None):
        self.run,self.clock,self.on_state,self.log=run,clock,on_state,log
        # A job needs a few GB of temp space; admitting one on a nearly full disk fails it midway.
        self.min_free=min_free_gb*1024**3
        self.free_bytes=free_bytes or (lambda:shutil.disk_usage(__import__('tempfile').gettempdir()).free)
        self.next_check=0;self.next_launch=0;self.available=False;self.reason=None
        self.lock=threading.Lock()

    def _command(self,args,timeout):
        return self.run(args,capture_output=True,text=True,timeout=timeout)

    def ready(self):
        with self.lock:return self._ready()

    def _ready(self):
        now=self.clock()
        if now<self.next_check:return self.available
        reason='renderer_ready'
        try:
            if self.min_free and self.free_bytes()<self.min_free:
                self.available=False;self.next_check=self.clock()+30
                if self.reason!='disk_low':
                    self.reason='disk_low'
                    self.log(f'Free disk below {self.min_free//1024**3} GB; tasks remain queued.',flush=True)
                    if self.on_state:self.on_state(False,'disk_low')
                return False
            if sys.platform=='linux':
                from linux_render import installation,supports_page_range
                result=self._command([str(installation()/'program/soffice'),'--version'],6)
                available=result.returncode==0 and bool(shutil.which('pdftoppm'))
                if supports_page_range():available=available and bool(shutil.which('pdfinfo'))
                self.available=available;self.next_check=self.clock()+(15 if available else 5)
                reason='renderer_ready' if available else 'linux_renderer_unavailable'
                if reason!=self.reason:
                    self.reason=reason
                    self.log('Linux renderer ready.' if available else 'Linux renderer unavailable; tasks remain queued.',flush=True)
                    if self.on_state:self.on_state(available,reason)
                return available
            engine=self._command([DOCKER,'info','--format','{{.ServerVersion}}'],6)
            if engine.returncode or not engine.stdout.strip():
                reason='docker_not_ready'
            else:
                image=self._command([DOCKER,'image','inspect',IMAGE,'--format','{{.Id}}'],6)
                if image.returncode or not image.stdout.strip().startswith('sha256:'):
                    # Docker Desktop can temporarily fail a short-name lookup for
                    # an installed image. Recheck the equivalent qualified local
                    # reference, without a pull or any container execution.
                    image=self._command([DOCKER,'image','inspect',QUALIFIED_IMAGE,'--format','{{.Id}}'],6)
                    if image.returncode or not image.stdout.strip().startswith('sha256:'):reason='renderer_image_missing'
        except subprocess.TimeoutExpired:reason='linux_renderer_unavailable' if sys.platform=='linux' else 'docker_not_ready'
        except (OSError,ValueError,RuntimeError):reason='linux_renderer_unavailable' if sys.platform=='linux' else 'docker_command_unavailable'
        if reason=='docker_not_ready' and now>=self.next_launch:
            self.next_launch=now+120
            try:self._command(['/usr/bin/open','-g','-a','/Applications/Docker.app'],5)
            except (OSError,subprocess.TimeoutExpired):pass
        self.available=reason=='renderer_ready';self.next_check=self.clock()+(15 if self.available else 5)
        if reason!=self.reason:
            self.reason=reason
            message='Renderer ready; queue admission enabled.' if self.available else ('Linux renderer unavailable; tasks remain queued.' if sys.platform=='linux' else 'Renderer unavailable ('+reason+'); tasks remain queued. Docker startup requested when needed.')
            self.log(message,flush=True)
            if self.on_state:self.on_state(self.available,reason)
        return self.available

    def claim(self,callback):
        # No queue request means no lease, model call, quota use or failed user attempt.
        return callback() if self.ready() else None

def start_heartbeat(health,send,backends,stop,*,interval=20,log=print):
    """Liveness is independent of queue claims, rendering and model execution."""
    import json
    def loop():
        failed=False
        while not stop.is_set():
            try:
                ready=health.ready()
                reply=send('/api/worker?action=heartbeat',json.dumps({'execution_backends':backends if ready else []}).encode())
                if reply.get('ok') is not True:raise ValueError('Invalid worker heartbeat acknowledgement')
                if failed:log('Worker heartbeat recovered.',flush=True)
                failed=False
            except Exception as error:
                # WorkerHTTPError deliberately excludes credentials and bodies.
                from resilience import WorkerHTTPError
                if not failed:log('Worker heartbeat:',str(error) if isinstance(error,WorkerHTTPError) else type(error).__name__,flush=True)
                failed=True
            stop.wait(interval)
    thread=threading.Thread(target=loop,name='pptx-worker-heartbeat',daemon=True)
    thread.start();return thread
