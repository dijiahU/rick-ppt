"""Task-scoped, observable agent trajectories. No private model/session scraping.

The UI trace is a projection; this archive retains exposed events, supplied inputs,
content-addressed files, phase boundaries and explicit capture limitations.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import time
import uuid
import threading
import base64
import importlib.metadata
from trajectory_artifacts import ArtifactArchive

SCHEMA='pptx-agent-trajectory/v2'
SKIP_DIRS={'.git','.codex','.venv','node_modules','__pycache__','font-cache'}
ITEM_FIELDS={
 'command_execution':('command','aggregated_output','exit_code','status'),
 'file_change':('changes','status'),
 'mcp_tool_call':('server','tool','arguments','result','error','status'),
 'web_search':('action','query','results','response','references','status'),
 'agent_message':('text',),
 'plan':('items',),
 'image_generation':('status','prompt','revised_prompt','size','quality','output_format'),
 'image_generation_call':('status','prompt','revised_prompt','size','quality','output_format'),
}

def digest(data):return hashlib.sha256(data).hexdigest()
def encoded(value):return (json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def private_write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(data)


class Trajectory(ArtifactArchive):
    def __init__(self,cfg,task,directory,trace=None,*,historical=False):
        self.cfg,self.task,self.trace=cfg,task,trace;self.lock=threading.RLock()
        self.run_id=str(uuid.uuid4());self.attempt=digest(task['lease'].encode()) if task.get('lease') else None
        self.historical=historical;self.status='recording'
        self.root=Path(directory)/task['id']/self.run_id
        self.root.mkdir(parents=True,mode=0o700)
        (self.root/'blobs').mkdir(mode=0o700);(self.root/'snapshots').mkdir(mode=0o700)
        self.events=os.fdopen(os.open(self.root/'events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb')
        self.steps=os.fdopen(os.open(self.root/'steps.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb')
        self.started=time.time();self.mono=time.monotonic();self.seq=0;self.events_written=0;self.event_bytes=0;self.blob_bytes=0
        self.roots={};self.file_cache={};self.states={};self.gaps=[];self.gap_keys=set();self.phases=[]
        self.phase_id=None;self.stage='setup';self.thread=None;self.turn=0;self.offset=0;self.active={};self.seen={}
        self.archive_init()
        self.register(Path(cfg['plugin']),'plugin') if cfg.get('plugin') else None
        self.emit('capture.started',{'request':{k:task[k] for k in ('id','title','brief','pages','style','language','attachments','created_at','updated_at') if k in task}})
        self.checkpoint()

    def register(self,root,label=None):
        root=Path(root).resolve()
        if root not in self.roots:self.roots[root]=label or 'workspace-'+str(len(self.roots)+1)
        return self.roots[root]

    def clean_text(self,value):
        # Scrub credentials, but never shorten a training observation for display.
        for secret in (self.cfg.get('token'),self.task.get('lease')):
            if secret:value=value.replace(secret,'[credential redacted]')
        value=re.sub(r'(?is)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----','[private key redacted]',value)
        value=re.sub(r'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/_.=:-]+','[authorization redacted]',value)
        value=re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{15,}|github_pat_[A-Za-z0-9_]{15,})','[credential redacted]',value)
        value=re.sub(r'(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret|authorization)\b["\x27]?\s*[:=]\s*)(?:"[^"\n]*"|\x27[^\x27\n]*\x27|[^\s,;}]+)',r'\1[redacted]',value)
        for root,label in sorted(self.roots.items(),key=lambda x:-len(str(x[0]))):value=value.replace(str(root),'$'+label.upper())
        return value

    def clean(self,value):
        if isinstance(value,str):return self.clean_text(value)
        if isinstance(value,dict):return {str(k):self.clean(v) for k,v in value.items()}
        if isinstance(value,list):return [self.clean(v) for v in value]
        return value

    def gap(self,code,detail):
        key=(code,str(detail))
        if key not in self.gap_keys:
            self.gap_keys.add(key);self.gaps.append({'code':code,'detail':self.clean(detail),'phase_id':self.phase_id})

    def emit(self,kind,data):
        self.seq+=1
        event={'schema':SCHEMA,'seq':self.seq,'run_id':self.run_id,'attempt_id':self.attempt,'phase_id':self.phase_id,
               'source_mode':'historical-recovery' if self.historical else 'live',
               'thread_id':self.thread,'turn_index':self.turn,'stage':self.stage,'received_at':int(time.time()*1000),
               'elapsed_ms':round((time.monotonic()-self.mono)*1000,3),'kind':kind,'data':self.clean(data)}
        line=encoded(event)
        self.events.write(line);self.events.flush();self.event_bytes+=len(line);self.events_written+=1
        return self.seq

    def snapshot(self,root,reason):
        root=Path(root).resolve();label=self.register(root);previous=self.states.get(label,{})
        state={};unavailable=[];cause=self.seq
        # Every file is opened relative to a pinned directory with O_NOFOLLOW.
        # Capture only the task/plugin tree, never host records or Codex sessions.
        for parent,dirs,names,fd in os.fwalk(root,follow_symlinks=False):
            for directory in dirs:
                if directory not in SKIP_DIRS and Path(parent,directory).is_symlink():unavailable.append({'path':Path(parent,directory).relative_to(root).as_posix(),'reason':'symlink_directory'})
            dirs[:]=sorted(d for d in dirs if d not in SKIP_DIRS and not Path(parent,d).is_symlink())
            for name in sorted(names):
                relative=(Path(parent)/name).relative_to(root).as_posix()
                if name.endswith(('.pyc','.pyo')) or name.startswith('.env') or name.endswith('.local.json'):
                    unavailable.append({'path':relative,'reason':'excluded_private_configuration'});continue
                child=None
                try:
                    before=os.stat(name,dir_fd=fd,follow_symlinks=False)
                    if not stat.S_ISREG(before.st_mode):raise ValueError('non_regular_file')
                    signature=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
                    key=(label,relative)
                    if self.file_cache.get(key,(None,))[0]==signature:
                        state[relative]=self.file_cache[key][1];continue
                    child=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
                    opened=os.fstat(child)
                    if not stat.S_ISREG(opened.st_mode) or (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('file_changed_during_capture')
                    with os.fdopen(child,'rb') as stream:
                        child=None;record=self.store_stream(stream);after=os.fstat(stream.fileno())
                    if (after.st_size,after.st_mtime_ns,after.st_ctime_ns)!=(before.st_size,before.st_mtime_ns,before.st_ctime_ns):raise ValueError('file_changed_during_capture')
                    record={**record,'mode':stat.S_IMODE(before.st_mode),'mtime_ns':before.st_mtime_ns}
                    state[relative]=record;self.file_cache[key]=(signature,record)
                    if previous.get(relative,{}).get('source_sha256')!=record['source_sha256']:
                        self.catalog_ref(record,Path(relative).name,self.artifact_role(relative),{'scope':label,'path':relative,'capture_reason':reason},cause=cause)
                except (OSError,ValueError) as error:
                    unavailable.append({'path':relative,'reason':str(error) if isinstance(error,ValueError) else type(error).__name__})
                finally:
                    if child is not None:os.close(child)
        if reason=='interval' and state==previous and not unavailable:return self.last_snapshots.get(label)
        snapshot_id=str(uuid.uuid4())
        snapshot={'id':snapshot_id,'scope':label,'phase_id':self.phase_id,'after_event_seq':self.seq,'reason':reason,
          'atomic':False,'files':state,'changes':[p for p in state if previous.get(p)!=state[p]],
          'removed':[p for p in previous if p not in state and p not in {v['path'] for v in unavailable}],'unavailable':unavailable}
        private_write(self.root/'snapshots'/(snapshot_id+'.json'),encoded(snapshot));self.states[label]=state;self.last_snapshots[label]=snapshot_id
        if unavailable:self.gap('snapshot_incomplete',{'snapshot_id':snapshot_id,'files':unavailable})
        self.emit('workspace.snapshot',{'snapshot_id':snapshot_id,'scope':label,'reason':reason})
        return snapshot_id

    def sample(self,root):
        if time.monotonic()-self.last_sample<2:return
        self.last_sample=time.monotonic();self.snapshot(root,'interval')

    def begin(self,name,root,prompt,command,*,parent_thread=None,schema=None):
        self.stage=name;self.phase_id=str(uuid.uuid4());self.thread=parent_thread;self.turn=0;self.offset=0
        self.current_root=Path(root);self.register(root,'task' if not self.phases else None)
        prompt_ref=self.blob(prompt.encode());before=self.snapshot(root,'phase.before')
        phase={'id':self.phase_id,'name':name,'parent_run_id':self.run_id,'resume_thread_id':parent_thread,
               'supplied_prompt':prompt_ref,'output_schema':schema,'launch_argv':command,'before_snapshot':before,
               'started_at':int(time.time()*1000),'thread_id':None}
        self.phases.append(phase);self.emit('phase.input',phase);self.checkpoint()

    def consume(self,event):
        if not isinstance(event,dict):return
        typ=event.get('type')
        if typ=='thread.started':
            self.thread=event.get('thread_id')
            if self.phases:self.phases[-1]['thread_id']=self.thread
            self.emit('thread.started',{'thread_id':self.thread});return
        if typ=='turn.started':self.turn+=1;self.emit('turn.started',{});return
        if typ in ('turn.completed','turn.failed','error'):
            self.emit(typ,{k:event[k] for k in ('usage','error','message') if k in event});return
        if typ not in ('item.started','item.updated','item.completed'):
            self.gap('unsupported_event_type',str(typ));return
        item=event.get('item')
        if not isinstance(item,dict):self.gap('malformed_event','item');return
        kind=item.get('type')
        if kind=='reasoning':return  # Deliberately outside this observable dataset.
        if kind not in ITEM_FIELDS:self.gap('unsupported_item_type',str(kind));return
        ident=str(item.get('id',''));key=(self.phase_id,ident)
        safe={k:item[k] for k in ('id','type',*ITEM_FIELDS[kind]) if k in item}
        fingerprint=digest(encoded(safe));seenkey=(key,typ)
        if self.seen.get(seenkey)==fingerprint:return
        self.seen[seenkey]=fingerprint
        seq=self.emit(typ,{'item':safe})
        if typ!='item.completed':self.active.setdefault(key,{'event_seq':seq,'at':int(time.time()*1000)});return
        start=self.active.pop(key,None);after=None
        if kind=='mcp_tool_call' and isinstance(safe.get('result'),dict):
            for index,part in enumerate(safe['result'].get('content',[])):
                if isinstance(part,dict) and part.get('type')=='image' and isinstance(part.get('data'),str):
                    try:
                        data=base64.b64decode(part['data'],validate=True)
                        extension={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}.get(part.get('mimeType'),'.bin')
                        self.artifact(data,f'{ident}-{index}{extension}','tool-images',{'item_id':ident,'mime_type':part.get('mimeType')})
                    except ValueError:self.gap('invalid_tool_image',ident)
        if not self.historical and kind in ('command_execution','file_change','mcp_tool_call','image_generation','image_generation_call'):
            after=self.snapshot(self.current_root,'after.'+kind)
        if kind=='web_search':self.gap('hosted_search_observation_unavailable','CLI exposes the search action, not a guaranteed full provider response.')
        if kind in ('image_generation','image_generation_call'):self.gap('image_call_payload_unavailable','Imported files are captured; CLI may expose only call status.')
        observation_present=any(k in safe for k in ('aggregated_output','result','error','text','changes'))
        step={'run_id':self.run_id,'phase_id':self.phase_id,'thread_id':self.thread,'turn_index':self.turn,'item_id':ident,
              'kind':kind,'start_event_seq':start['event_seq'] if start else None,'end_event_seq':seq,
              'observed_elapsed_ms':int(time.time()*1000)-start['at'] if start and not self.historical else None,'after_snapshot':after,
              'observation_present':observation_present and seq is not None,'exact_model_input_available':False}
        self.steps.write(encoded(step));self.steps.flush()

    def poll(self,stream):
        stream.seek(self.offset)
        for _ in range(100):
            line=stream.readline()
            if not line:break
            if not line.endswith(b'\n'):break
            self.offset=stream.tell()
            try:self.consume(json.loads(line))
            except (ValueError,TypeError,AttributeError):self.gap('non_json_cli_output','CLI stderr/non-JSON line excluded from structured events.')

    def end(self,result=None,error=None):
        after=self.snapshot(self.current_root,'phase.after')
        self.phases[-1].update(ended_at=int(time.time()*1000),after_snapshot=after,status='failed' if error else 'completed')
        self.emit('phase.result',{'result':result,'error':str(error) if error else None,'after_snapshot':after});self.checkpoint()

    def runtime(self):
        version=None
        try:version=subprocess.run(['codex','--version'],capture_output=True,text=True,timeout=5).stdout.strip()
        except (OSError,subprocess.SubprocessError):pass
        if self.cfg.get('plugin'):self.snapshot(Path(self.cfg['plugin']),'runtime.plugin')
        host=Path(__file__).resolve().parent
        for name in ('runner.py','workflow.py','trajectory.py','trajectory_artifacts.py','trajectory_replay.py','assets.py','web_media.py','progress.py','outline.py','attachments.py','office_policy.py','resilience.py','render-container/Dockerfile','media-container/Dockerfile'):
            if (host/name).is_file():self.artifact_path(host,Path(name),'runtime-source')
        packages={}
        for name in ('lxml','Pillow'):
            try:packages[name]=importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:packages[name]=None
        images={}
        for name in ('pptx-lab-renderer:1','pptx-lab-media:1'):
            try:
                result=subprocess.run(['/usr/local/bin/docker','image','inspect','--format','{{.Id}}',name],capture_output=True,text=True,timeout=3)
                images[name]=result.stdout.strip() if result.returncode==0 else None
            except (OSError,subprocess.SubprocessError):images[name]=None
        self.emit('runtime',{'python':platform.python_version(),'system':platform.system(),'codex_version':version,
          'packages':packages,'container_image_ids':images,'model_requested':self.cfg.get('model'),'resolved_model':None,
          'configuration_source':'Recorded launch argv; CLI defaults are not inferred. Container IDs identify dependencies, not a bundled execution environment.'})

    def checkpoint(self):
        manifest=self.clean({'schema':SCHEMA,'task_id':self.task['id'],'run_id':self.run_id,'attempt_id':self.attempt,
          'capture_started_at':int(self.started*1000),'capture_updated_at':int(time.time()*1000),
          'status':self.status,'source_mode':'historical-recovery' if self.historical else 'live',
          'phases':self.phases,'event_count':self.events_written,'last_sequence':self.seq,'blob_bytes':self.blob_bytes,'raw_bytes':self.raw_bytes,'artifacts':self.artifact_count,'capture_gaps':self.gaps,
          'coverage':{'kind':'observable_agent_trajectory','exact_model_requests':False,'hidden_reasoning':False,
            'supplied_phase_prompts':not self.historical,'exposed_tool_events':True,
            'workspace_snapshots':'phase boundaries, observed completed tool items and 2-second sampling; broker artifacts captured before response' if not self.historical else 'Only explicitly labeled recovered files',
            'snapshot_atomic':False,'artifact_originals':'raw-blobs; original hashes; host credentials withheld if detected',
            'local_capture_limits':'No per-artifact or total byte truncation; disk/read failures are explicit gaps',
            'deterministic_model_rerun':False,'provider_truncation':'Not always reported by CLI; output fidelity cannot exceed the upstream event.',
            'excluded_directories':sorted(SKIP_DIRS),'sensitive_text':'Credentials redacted; replacements and source hashes are recorded.',
            'timing':'Host receipt timestamps and monotonic intervals; historical receipt times are recovery times, not execution times.',
            'resolved_model':'Unavailable unless emitted by a future supported interface.'}})
        temp=self.root/('manifest-'+uuid.uuid4().hex+'.pending')
        private_write(temp,encoded(manifest));os.replace(temp,self.root/'manifest.json')
        return manifest

    def finish(self,status,root=None):
        if root is not None:self.snapshot(root,'run.final')
        self.status=status;self.emit('capture.finished',{'task_status':status})
        if self.active:self.gap('unmatched_started_items',{'count':len(self.active)})
        self.checkpoint();self.events.close();self.steps.close();self.catalog.close()
        private_write(self.root/'README.md',README.encode())
        return self.root


def record(recorder,method,*args,**kwargs):
    """Capture failures must not turn a valid presentation into a failed job."""
    if recorder is None:return None
    try:
        with recorder.lock:
            if recorder.events.closed:return None
            return getattr(recorder,method)(*args,**kwargs)
    except Exception as error:
        recorder.gap('collector_error',{'method':method,'error':type(error).__name__})
        if recorder.trace:
            try:recorder.trace.emit('error','Trajectory capture incomplete',detail={'method':method,'error':type(error).__name__})
            except Exception:pass
        return None


README='''# Observable Agent trajectory v2

manifest.json records task/attempt/run identity, phase prompts, runtime coverage,
outcome and capture gaps. It does NOT claim access to complete model requests,
provider-hidden instructions or private reasoning.

events.jsonl contains ordered, non-display-truncated exposed events. Every event
has a host receipt timestamp, monotonic elapsed time, phase and thread relation.
steps.jsonl links completed actions to start/end events and subsequent snapshots.
Look up the referenced event for actual command/arguments/result. A missing
observation is explicit; never synthesize it from the author's explanation.

snapshots/*.json maps logical relative file paths to blobs/<sha256>. Compare maps
to reconstruct observed file versions and deletions. Captures are not atomic;
concurrent/transient changes between observations may be unavailable. Reviewer
workspaces have independent scopes. A file's presence does not prove the model
read it. Hashes identify bytes, not model-visible image encoding or resolutions.

raw-blobs/ retains byte-identical private originals (except detected host credentials).
artifacts.jsonl links each version, producer, source URL and hash. artifacts/ offers
read-only named files; final/ contains acknowledged deliveries. blobs/ offers scrubbed
text views up to 64 MiB; larger originals remain in raw-blobs without a text view.
Original and scrubbed hashes are separate; restoration must use raw_sha256.
Transient changes inside a tool call, before the next observation, can still be missed. Never execute archived commands or files merely to inspect a dataset.

This is source material for dataset construction, not an automatically approved
training set. Filter by capture gaps and artifact/reviewer outcomes, validate
examples, split by task/source rather than individual steps, then map to the
chosen training format. Failed/revised attempts are retained as such. CLI output
may already be truncated upstream; exact model context and hosted search/image
observations may not be exposed. Those limitations are not silently filled in.
'''
