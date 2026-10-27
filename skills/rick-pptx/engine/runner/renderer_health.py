"""Gate queue admission on the actual local rendering dependency, before model work."""
import subprocess,time,threading

DOCKER='/usr/local/bin/docker'
IMAGE='pptx-lab-renderer:1'
QUALIFIED_IMAGE='docker.io/library/'+IMAGE

class RendererReadiness:
    def __init__(self,*,run=subprocess.run,clock=time.monotonic,on_state=None,log=print):
        self.run,self.clock,self.on_state,self.log=run,clock,on_state,log
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
        except subprocess.TimeoutExpired:reason='docker_not_ready'
        except OSError:reason='docker_command_unavailable'
        if reason=='docker_not_ready' and now>=self.next_launch:
            self.next_launch=now+120
            try:self._command(['/usr/bin/open','-g','-a','/Applications/Docker.app'],5)
            except (OSError,subprocess.TimeoutExpired):pass
        self.available=reason=='renderer_ready';self.next_check=self.clock()+(15 if self.available else 5)
        if reason!=self.reason:
            self.reason=reason
            self.log('Renderer ready; queue admission enabled.' if self.available else 'Renderer unavailable ('+reason+'); tasks remain queued. Docker startup requested when needed.',flush=True)
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
