#!/usr/bin/env python3
"""Full local production workflow, selected harness adapter, no website queue."""
import argparse
from contextlib import contextmanager
import datetime
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import uuid

SKILL=Path(__file__).resolve().parents[1]


def atomic(path,value):
    from portable_transport import _write
    _write(path,value)


def write_status(root,value,trajectory=None):
    if trajectory is not None:
        from execution_identity import phase_summary
        receipt={'format':1,'run_id':trajectory.run_id,'state':value['state'],
                 'execution':trajectory.execution,'phases':phase_summary(trajectory.phases),
                 'trajectory_manifest':str(trajectory.root/'manifest.json'), 'review_runs':[]}
        for child in trajectory.child_runs:
            # References originate in the coordinator's real review.child event,
            # not in a model-supplied claim about which reviews ran.
            ident=str(uuid.UUID(child['run_id']))
            path=trajectory.root.parent/ident/'manifest.json'
            row={**child,'status':'unknown','phases':[]}
            try:
                manifest=json.loads(path.read_text())
                if manifest.get('run_id')==ident:
                    row.update(status=manifest['status'],phases=phase_summary(manifest['phases']))
            except (OSError,ValueError,KeyError):pass
            receipt['review_runs'].append(row)
        atomic(root/'host/execution.json',trajectory.clean(receipt))
        value={**value,'execution_receipt':str(root/'host/execution.json')}
    atomic(root/'status.json',value)


@contextmanager
def preserving_journal(journal):
    with journal:
        try:yield journal
        except BaseException:
            try:
                journal.interrupt(reason='portable_interrupted')
                workspace=journal.state.get('workspace')
                if workspace:journal.checkpoint(workspace,reason='interrupted_workspace')
            except Exception:pass
            raise


def load_runtime():
    engine=SKILL/'engine';directory=engine/'runner'
    if not (directory/'workflow.py').is_file():raise RuntimeError('This package lacks the complete engine; use the full release ZIP')
    from doctor import package_integrity
    integrity=package_integrity(SKILL)
    if not integrity['verified']:
        raise RuntimeError('Full package payload verification failed; reinstall a matching release. '+json.dumps(integrity))
    for name in ('runner','workflow','durable'):
        module=sys.modules.get(name)
        if module is not None and getattr(module,'__file__',None) and not Path(module.__file__).resolve().is_relative_to(directory):
            raise RuntimeError('Use a fresh portable_workflow.py process; another execution runtime is already imported: '+name)
    sys.path.insert(0,str(directory))
    return SimpleNamespace(**{name:importlib.import_module(name) for name in (
        'runner','workflow','durable','trajectory','progress','attachments','decision_routing',
        'admin_trace','conversation','delivery','model_backend')})


def portable_configuration(root,*,read_roots=(),tool_env=None,web_search='live',**kwargs):
    # DSH owns the model/tool sandbox. Never load Codex configs or auth files.
    return {'shell_environment_policy':{'inherit':'none','set':tool_env or {}},
            'web_search':web_search,'features':{},'portable_read_roots':list(map(str,read_roots))}


class NativeUsage:
    """Native-harness usage is not an independently verified provider bill."""
    def __init__(self,root):self.root=root/'usage';self.root.mkdir(exist_ok=True);self.lock=threading.Lock()
    def codex_sink(self,stage,model):
        def capture(value):
            row={'stage':stage,'model':model,'source':'dsh-native-reported','at':time.time(),**value,'provider_cost':None}
            with self.lock:
                with (self.root/'receipts.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        return capture
    def close(self):pass


class StopLease:
    def __init__(self,root,seconds):self.root=root;self.deadline=time.monotonic()+seconds
    def check(self):
        from resilience import TaskPaused
        if (self.root/'STOP').exists():raise TaskPaused('Task stopped by its owner')
        if time.monotonic()>self.deadline:raise TimeoutError('Portable task deadline exceeded')
    def finish(self):pass


def install_runtime(runtime,root,options):
    from dsh_adapter import DshServer
    DshServer.options=options
    runtime.workflow.AppServer=DshServer
    runtime.workflow.task_configuration=portable_configuration
    runtime.workflow.public_identity=lambda profile:{'backend':'dsh','provider':options['provider'],'model':options['model']}
    import auxiliary_tools
    auxiliary_tools.AppServer=DshServer;auxiliary_tools.task_configuration=portable_configuration
    from portable_auxiliary import install
    install(runtime)
    # Only engine-owned validation commands use this function; model shell
    # commands remain DSH tools governed by the selected DSH profile.
    def validation_command(cfg,job,command):
        if (len(command)<2 or Path(command[0]).resolve()!=Path(cfg['python']).resolve()
                or not Path(command[1]).resolve().is_relative_to(Path(cfg['plugin']).resolve())):
            raise ValueError('Only packaged trusted validation scripts may run on the host')
        return command
    runtime.runner.sandbox=validation_command
    original_environment=runtime.runner.environment
    def environment(job):
        env=original_environment(job)
        env['PATH']=str(Path(sys.executable).parent)+':'+env.get('PATH','')
        return env
    runtime.runner.environment=environment


def make_options(args,root):
    cfg={}
    if args.config:
        path=Path(args.config).expanduser().resolve(strict=True)
        cfg=json.loads(path.read_text())
        if any(k in cfg for k in ('api_key','token','authorization')):
            raise ValueError('Configuration must use api_key_env, not embedded credentials')
    allowed={'provider','model','reasoning_effort','max_tokens','dsh_home','profile','dsh_bin','base_url','api_key_env','api_key_file','patches','generation_tool_names'}
    if set(cfg)-allowed:raise ValueError('Unknown DSH configuration keys: '+','.join(sorted(set(cfg)-allowed)))
    for key in ('model','provider','reasoning_effort','dsh_home','dsh_bin'):
        value=getattr(args,key,None)
        if value:cfg[key]=value
    cfg.setdefault('provider','deepseek-official');cfg.setdefault('profile','sdk')
    if not cfg.get('model'):raise ValueError('Select the exact DSH model with --model or --config; no implicit model substitution')
    if cfg['profile']=='sdk-minimal':raise ValueError('The complete workflow requires the full sdk profile or a full custom SDK profile')
    if 'max_tokens' in cfg and (type(cfg['max_tokens']) is not int or not 1024<=cfg['max_tokens']<=131072):
        raise ValueError('max_tokens must be an integer from 1024 to 131072, within the selected provider limit')
    cfg['dsh_home']=str(Path(cfg.get('dsh_home',root/'host/dsh-home')).expanduser().absolute())
    cfg['python']=sys.executable;cfg['records']=str(root/'host/records')
    if cfg.get('api_key_env'):
        key=os.environ.get(cfg.pop('api_key_env'))
        if not key:raise ValueError('Configured API key environment variable is empty')
        cfg['api_key']=key
    if cfg.get('api_key_file'):
        if cfg.get('api_key'):raise ValueError('Select api_key_env or api_key_file, not both')
        credential=Path(cfg['api_key_file']).expanduser().resolve(strict=True)
        if credential.stat().st_mode&0o077:raise ValueError('API credential file must be private (mode 0600)')
        key=json.loads(credential.read_text()).get('api_key')
        if not isinstance(key,str) or not key:raise ValueError('Credential file has no api_key field')
        cfg['api_key']=key;cfg['api_key_file']=str(credential)
    cfg['patches']=tuple(str(Path(p).expanduser().resolve(strict=True)) for p in cfg.get('patches',()))
    return cfg


def check_resume_identity(previous,current):
    changed={k for k in set(previous)|set(current) if previous.get(k)!=current.get(k)}
    if changed-{'max_tokens'}:
        raise ValueError('Resume must retain the same DSH provider/model/home/profile/options')
    return {k:{'previous':previous.get(k),'current':current.get(k)} for k in sorted(changed)}


def request_data(path,root,runtime):
    path=Path(path).expanduser().resolve(strict=True);request=json.loads(path.read_text())
    if not isinstance(request,dict) or not isinstance(request.get('brief'),str) or not request['brief'].strip():raise ValueError('request.json requires the actual user brief')
    pages=request.get('pages')
    if pages is not None and (type(pages) is not int or not 1<=pages<=50):raise ValueError('pages must be 1–50')
    if request.get('mode','create') not in ('create','edit'):raise ValueError('mode must be create or edit')
    items=[];bodies={}
    for source in request.get('attachments',[]):
        src=Path(source if isinstance(source,str) else source['path']).expanduser()
        if not src.is_absolute():src=path.parent/src
        data=src.read_bytes();ext=src.suffix.lower().lstrip('.')
        runtime.attachments.validate_content(data,ext)
        ident=str(uuid.uuid4());digest=hashlib.sha256(data).hexdigest()
        items.append({'id':ident,'name':src.name,'ext':ext,'size':len(data),'sha256':digest});bodies[ident]=data
    runtime.attachments.metadata(items)
    saved=root/'host/input-files';saved.mkdir(exist_ok=True)
    for ident,body in bodies.items():(saved/ident).write_bytes(body)
    task={'id':str(uuid.uuid4()),'lease':'portable-'+uuid.uuid4().hex,
          'title':request.get('title','Presentation'),'brief':request['brief'],'pages':pages,
          'language':request.get('language','zh-CN'),'style':request.get('style',''),
          'mode':request.get('mode','create'),'attachments':items,'execution_backend':'api'}
    task['harness']='dsh';atomic(root/'host/task.json',task)
    return task,bodies


def run(args):
    from portable_transport import LocalTransport
    runtime=load_runtime();root=Path(args.out).expanduser().absolute();root.mkdir(parents=True,exist_ok=True,mode=0o700)
    for name in ('host','host/records','state','trajectory','workspaces'):(root/name).mkdir(exist_ok=True,parents=True,mode=0o700)
    with (root/'host/run.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.resume:
            task=json.loads((root/'host/task.json').read_text());task['lease']='portable-'+uuid.uuid4().hex
            bodies={row['id']:(root/'host/input-files'/row['id']).read_bytes() for row in task['attachments']}
            (root/'STOP').unlink(missing_ok=True)
        else:
            if (root/'host/task.json').exists():raise ValueError('Task already exists; use resume or a new --out directory')
            task,bodies=request_data(args.request,root,runtime)
        options=make_options(args,root);install_runtime(runtime,root,options)
        identity=json.loads(json.dumps({k:v for k,v in options.items() if k not in ('api_key','python','records')}))
        previous=root/'host/harness-identity.json'
        if args.resume and previous.exists():
            changes=check_resume_identity(json.loads(previous.read_text()),identity)
            if changes:
                atomic(root/'host/records'/('resume-options-'+uuid.uuid4().hex+'.json'),
                       {'at':time.time(),'explicit_configuration_changes':changes,'reason':'Resume configuration; no model/provider substitution or review exemption'})
        atomic(previous,identity)
        cfg={'plugin':str(SKILL/'engine/plugin'),'python':sys.executable,'token':'local-'+uuid.uuid4().hex,
             'site':'https://portable.local.invalid','default_model':options['model'],
             'default_reasoning_effort':options.get('reasoning_effort','high'),'single_file_pptx':True,
             'parallel_reviews':True,'progressive_canvas':False,'job_timeout_seconds':args.timeout,
             'state_directory':str(root/'state'),'font_cache_directory':str(root/'host/font-cache'),
             '_harness_command':['dsh','--profile',options['profile']],'_harness_transport':'dsh-sdk',
             '_harness_identity':{k:options[k] for k in ('provider','model','profile','reasoning_effort') if k in options},
             '_package_manifest':str(SKILL/'assets/package-manifest.json'),
             '_allow_declared_author_handoff':True,'_reuse_planning_for_author_resume':True}
        cfg['blank']=str(Path(cfg['plugin'])/'skills/pptx/assets/blank.pptx')
        transport=LocalTransport(root,task,bodies);lease=StopLease(root,args.timeout)
        old_prepare=runtime.runner.prepare
        def configure_workspace(target):
            for name in ('soffice-proxy.py','font-proxy.py','interactive-proxy.py'):
                p=target/name
                if p.is_file() and p.read_text().startswith('#!'):
                    p.write_text('#!'+sys.executable+'\n'+p.read_text().split('\n',1)[1]);p.chmod(0o755)
            from font_assets import configure
            configure(target)
            caps=json.loads((target/'capabilities.json').read_text())
            caps['execution_harness']={'name':'dsh','profile':options['profile'],'provider':options['provider'],'model':options['model']}
            caps['model']={'backend':'dsh','provider':options['provider'],'model':options['model']}
            caps['web_search']={'mode':'selected-dsh-profile','optional':True,'use':'Use actually registered DSH search tools; supplied-only/offline constraints remain binding.'}
            caps['image_generation']={'mode':'selected-dsh-profile','optional':True,'use':'Use an actually configured DSH image-generation tool/provider, inspect and embed its real task-local output. Missing service is an unmet capability, never permission to fabricate evidence.'}
            caps['asset_import']={'mode':'task-local-files','use':'Save actual acquired/generated assets under assets/, inspect them, and record provenance. No personal Codex image cache is used.'}
            atomic(target/'capabilities.json',caps)
            return target
        def prepare(config):
            job=old_prepare(config);target=root/'workspaces'/('workspace-'+uuid.uuid4().hex)
            shutil.move(str(job),target)
            return configure_workspace(target)
        bridge=SimpleNamespace(ROOT=root/'host',request=transport,prepare=prepare,environment=runtime.runner.environment,
            sandbox=runtime.runner.sandbox,render_requests=runtime.runner.render_requests,run_with_renderer=runtime.runner.run_with_renderer)
        ledger=NativeUsage(root/'host');cfg['_usage_ledger']=ledger
        trace=runtime.admin_trace.AdminTrace(cfg,task,transport,root/'host/records')
        version=runtime.runner._installed_plugin_version(cfg);outcome='failed';trajectory=None;reporter=None;job=None
        def stop_handler(*unused):(root/'STOP').touch()
        signal.signal(signal.SIGTERM,stop_handler);signal.signal(signal.SIGINT,stop_handler)
        started=time.monotonic()
        try:
            with preserving_journal(runtime.durable.Journal(root/'state',task['id'],plugin_version=version,
                  limits=runtime.durable.HOST_JOURNAL_LIMITS,secrets=tuple(x for x in (cfg['token'],task['lease'],options.get('api_key')) if x))) as journal:
                plan=None
                if args.resume and journal.state.get('snapshot_id'):
                    from recovery_workspace import relocate_task
                    old=journal.state['workspace'];job=root/'workspaces'/('resumed-'+uuid.uuid4().hex)
                    plan=journal.recover(job,plugin_version=version,recovery_id=task['lease'],allow_plugin_upgrade=False)
                    relocate_task(old,job,cfg);runtime.runner.refresh_support(cfg,job)
                    configure_workspace(job)
                else:job=prepare(cfg)
                trajectory=runtime.trajectory.Trajectory(cfg,task,root/'trajectory',trace=trace)
                runtime.trajectory.record(trajectory,'register',job,'task');runtime.trajectory.record(trajectory,'runtime')
                from language import presentation_request
                payload=presentation_request(task)
                payload['attachments']=runtime.attachments.receive(cfg,task,job,transport,recover=bool(plan),check=lease.check)
                atomic(job/'request.json',payload);journal.checkpoint(job,reason='task_inputs_ready')
                reporter=runtime.progress.Reporter(cfg,task,job,transport,explicit_previews=True)
                write_status(root,{'state':'running','harness':'dsh','pid':os.getpid(),'task_id':task['id'],'job':str(job)},trajectory)
                from resilience import WorkerHTTPError
                while True:
                    result=runtime.workflow.run_workflow(bridge,cfg,task,job,payload,lease,reporter,trace=trace,trajectory=trajectory,journal=journal,recovery_plan=plan)
                    plan=None
                    try:
                        runtime.delivery.deliver(cfg,task,result['artifact'],result['revision'],transport,check=lease.check)
                        break
                    except WorkerHTTPError as error:
                        if error.status!=412:raise
                        transport.expected=None
                        reporter.event('working','New revision arrived before delivery; continuing the same task',category='note')
                outcome='complete'
                runtime.trajectory.record(trajectory,'artifact',result['artifact'],'presentation.pptx','delivered',final=True)
                write_status(root,{'state':'complete','harness':'dsh','task_id':task['id'],'artifact':str(root/'presentation.pptx'),'sha256':hashlib.sha256(result['artifact']).hexdigest(),'review_summary':result.get('review_summary'),'seconds':time.monotonic()-started},trajectory)
        except BaseException as error:
            from resilience import TaskPaused
            outcome='paused' if isinstance(error,TaskPaused) else 'failed'
            if job is not None:
                try:journal.interrupt(reason='portable_interrupted');journal.checkpoint(job,reason='interrupted_workspace')
                except Exception:pass
            message=str(error)
            for secret in (cfg['token'],task['lease'],options.get('api_key')):
                if secret:message=message.replace(secret,'[redacted]')
            write_status(root,{'state':outcome,'harness':'dsh','task_id':task['id'],'error_type':type(error).__name__,'detail':message,'job':str(job),'seconds':time.monotonic()-started},trajectory)
            raise RuntimeError(message) from None
        finally:
            if reporter:reporter.finish_drafts(timeout=2)
            ledger.close();runtime.trajectory.record(trajectory,'finish',outcome,job);trace.close()
        print((root/'status.json').read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for name in ('run','resume'):
        s=sub.add_parser(name);s.add_argument('--out',required=True);s.add_argument('--request',required=name=='run')
        s.add_argument('--backend',choices=['dsh'],default='dsh');s.add_argument('--config');s.add_argument('--model');s.add_argument('--provider');s.add_argument('--reasoning-effort');s.add_argument('--dsh-home');s.add_argument('--dsh-bin');s.add_argument('--timeout',type=int,default=10800);s.set_defaults(resume=name=='resume')
    s=sub.add_parser('status');s.add_argument('--out',required=True)
    s=sub.add_parser('stop');s.add_argument('--out',required=True)
    s=sub.add_parser('message');s.add_argument('--out',required=True);s.add_argument('--kind',choices=['chat','revision'],default='revision');s.add_argument('--text',required=True);s.add_argument('--attachment',action='append',default=[])
    args=p.parse_args()
    if args.command in ('run','resume'):
        if not 60<=args.timeout<=10800:p.error('timeout must be 60–10800 seconds')
        run(args);return
    root=Path(args.out).expanduser().resolve(strict=True)
    if args.command=='status':print((root/'status.json').read_text());return
    if args.command=='stop':
        (root/'STOP').touch();print(json.dumps({'stop_requested':True,'checkpoint_pending':'wait for paused status before resume'}));return
    runtime=load_runtime();messages=root/'messages';messages.mkdir(exist_ok=True)
    with (root/'host/messages.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        seq=max([int(p.stem) for p in messages.glob('*.json')]+[0])+1;items=[]
        for name in args.attachment:
            src=Path(name).expanduser().resolve(strict=True);body=src.read_bytes();ext=src.suffix.lower().lstrip('.')
            runtime.attachments.validate_content(body,ext);ident=str(uuid.uuid4());target=root/'message-files';target.mkdir(exist_ok=True)
            (target/ident).write_bytes(body);items.append({'id':ident,'name':src.name,'ext':ext,'size':len(body),'sha256':hashlib.sha256(body).hexdigest()})
        runtime.attachments.metadata(items)
        if not 1<=len(args.text)<=8000:raise ValueError('message text must be 1–8000 characters')
        atomic(messages/(f'{seq:08d}.json'),{'id':str(uuid.uuid4()),'seq':seq,'kind':args.kind,'body':args.text,'attachments':items})
        print(json.dumps({'queued':True,'seq':seq,'kind':args.kind,'attachment_count':len(items)}))


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError) as e:raise SystemExit(str(e))
