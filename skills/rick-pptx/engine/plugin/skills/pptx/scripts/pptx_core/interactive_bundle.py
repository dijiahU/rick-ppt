"""Immutable portable distributions with verified, process-scoped lifecycle control."""
from __future__ import annotations
import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from .common import PptxError,atomic_json,sha256
from .manifest import manifest,changed_paths
from .package import export
from .interactive_validate import PLUGIN_ROOT,validate_interactive,validate_bundle_manifest,read_json

# The standalone controller uses only stdlib until a verified server is started.
# Its token and process records live outside the HTTP-served bundle directory.
CONTROL_SOURCE = r'''from __future__ import annotations
import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[1]

def cache_dir(root=ROOT):
    identity=hashlib.sha256(str(root.resolve()).encode()).hexdigest()
    base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'rick-ppt-runtime'/identity
    base.mkdir(parents=True,exist_ok=True,mode=0o700)
    return base

def state_path(root=ROOT):return cache_dir(root)/'state.json'

def save(path,value):
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)

def state(root=ROOT):
    path=state_path(root)
    if not path.exists():return None
    value=json.loads(path.read_text())
    if value.get('root')!=str(root.resolve()):raise RuntimeError('Runtime record belongs to another bundle')
    return value

@contextlib.contextmanager
def lifecycle_lock():
    with (cache_dir()/'lifecycle.lock').open('a+b') as stream:
        if os.name=='nt':
            import msvcrt
            stream.seek(0);stream.write(b'0');stream.flush();stream.seek(0)
            msvcrt.locking(stream.fileno(),msvcrt.LK_LOCK,1)
            try:yield
            finally:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(stream,fcntl.LOCK_UN)

def checked(root,name):
    path=PurePosixPath(name)
    if not name or path.is_absolute() or any(x in ('','.','..') for x in name.split('/')) or any(x in name for x in ('\\',':','\x00')):raise RuntimeError('Unsafe bundle inventory path')
    value=root/name
    if any(p.is_symlink() for p in [value,*value.parents] if p.is_relative_to(root)):raise RuntimeError('Symlink in bundle')
    if not value.is_file() or not value.resolve().is_relative_to(root.resolve()):raise RuntimeError('Missing bundle file: '+name)
    return value

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def verify(root=ROOT):
    root=root.resolve();index=json.loads(checked(root,'checksums.json').read_text())
    if not isinstance(index,dict) or not index or len(index)>50000:raise RuntimeError('Invalid bundle checksum inventory')
    for name,expected in index.items():
        if not isinstance(expected,str) or len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise RuntimeError('Invalid bundle checksum')
        if digest(checked(root,name))!=expected:raise RuntimeError('Bundle checksum mismatch: '+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.relative_to(root).as_posix()!='checksums.json'}
    if actual!=set(index):raise RuntimeError('Bundle file inventory changed')
    from pptx_core.interactive_validate import validate_bundle_manifest,read_json
    bundle=validate_bundle_manifest(read_json(root/'deck/bundle.json'),root/'deck')
    if digest(root/'presentation.pptx')!=bundle['pptxHash']:raise RuntimeError('Presentation hash differs from bundle')
    return {'ok':True,'deckId':bundle['deckId'],'files':len(index),'pptxHash':bundle['pptxHash']}

def control(record,stop=False):
    if not record or record.get('status')=='stopped':return None
    port=record.get('controlPort')
    if not isinstance(port,int) or not 0<port<65536:raise RuntimeError('Invalid control port')
    request=urllib.request.Request('http://127.0.0.1:'+str(port)+('/stop' if stop else '/status'),data=b'' if stop else None,headers={'Authorization':'Bearer '+record['token']})
    try:
        with urllib.request.urlopen(request,timeout=2) as response:result=json.load(response)
    except (urllib.error.URLError,TimeoutError,ConnectionError):return None
    if result.get('pid')!=record.get('pid') or result.get('instance')!=record.get('instance') or result.get('root')!=str(ROOT):raise RuntimeError('Control endpoint identity mismatch; no process was signaled')
    return result

def public(record,running=True):return {'running':running,'pid':record.get('pid'),'url':record.get('url'),'root':record.get('root')}

def start(args):
    verify()
    with lifecycle_lock():
        current=state()
        if control(current):return {**public(current),'alreadyRunning':True}
        instance=uuid.uuid4().hex;log=cache_dir()/('runtime-'+instance+'.log')
        command=[sys.executable,str(Path(__file__).resolve()),'run','--instance',instance,'--port',str(args.port)]
        if args.http:command+=['--http']
        if args.cert:command+=['--cert',args.cert]
        if args.key:command+=['--key',args.key]
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        with log.open('xb') as stream:
            options={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP}
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,**options)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            current=state()
            if current and current.get('instance')==instance and control(current):return {**public(current),'log':str(log)}
            if process.poll() is not None:raise RuntimeError('Runtime failed to start; inspect '+str(log))
            time.sleep(.1)
        raise RuntimeError('Runtime start is still pending; inspect '+str(log)+' or run status before retrying')

def stop():
    with lifecycle_lock():
        current=state()
        if not control(current):return {'running':False,'stopped':False}
        # A stale/reused PID alone cannot signal anything. Both status and stop
        # authenticate a per-instance token against the running controller.
        control(current,True)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if not control(current):return {**public(current,False),'stopped':True}
            time.sleep(.1)
        raise RuntimeError('This bundle runtime has not finished stopping; no other process was signaled')

async def run(args):
    verify()
    from pptx_core.interactive_server import start_server
    runner,url=await start_server(ROOT,ROOT/'runtime/dist',args.port,not args.http,args.cert,args.key)
    loop=asyncio.get_running_loop();stopped=asyncio.Event();token=secrets.token_urlsafe(32);instance=args.instance or uuid.uuid4().hex
    identity={'root':str(ROOT),'pid':os.getpid(),'instance':instance}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def handle_control(self,stop_request=False):
            if not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):self.send_error(403);return
            if self.path!=('/stop' if stop_request else '/status'):self.send_error(404);return
            payload=json.dumps(identity).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);self.wfile.flush()
            if stop_request:loop.call_soon_threadsafe(stopped.set)
        def do_GET(self):self.handle_control()
        def do_POST(self):self.handle_control(True)
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler);http.daemon_threads=True
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    record={**identity,'url':url,'controlPort':http.server_address[1],'token':token,'status':'running','startedAt':time.time()}
    save(cache_dir()/('run-'+instance+'.json'),record);save(state_path(),record)
    for sig in (signal.SIGINT,signal.SIGTERM):
        try:loop.add_signal_handler(sig,stopped.set)
        except (NotImplementedError,RuntimeError):pass
    print(json.dumps(public(record)),flush=True)
    try:await stopped.wait()
    finally:
        await runner.cleanup();await asyncio.to_thread(http.shutdown);http.server_close();thread.join(timeout=2)
        record.update(status='stopped',stoppedAt=time.time());save(cache_dir()/('run-'+instance+'.json'),record)
        current=state()
        if current and current.get('instance')==instance:save(state_path(),record)

def main(argv=None):
    parser=argparse.ArgumentParser(description='Verify and control this presentation runtime only')
    parser.add_argument('command',choices=['verify','start','stop','status','run']);parser.add_argument('--port',type=int,default=41973);parser.add_argument('--http',action='store_true');parser.add_argument('--cert');parser.add_argument('--key');parser.add_argument('--instance')
    args=parser.parse_args(argv)
    try:
        if args.command=='run':asyncio.run(run(args));return
        if args.command=='verify':result=verify()
        elif args.command=='start':result=start(args)
        elif args.command=='stop':result=stop()
        else:
            current=state();result=public(current,bool(control(current))) if current else {'running':False}
        print(json.dumps(result))
    except Exception as error:print(json.dumps({'error':str(error)}),file=sys.stderr);raise SystemExit(1)

if __name__=='__main__':main()
'''


def write_controller(stage):
    scripts=stage/'scripts';scripts.mkdir()
    (scripts/'bundle_control.py').write_text(CONTROL_SOURCE)
    (scripts/'serve.py').write_text('import sys\nfrom bundle_control import main\nmain(["run",*sys.argv[1:]])\n')
    (scripts/'requirements.txt').write_text('aiohttp>=3.11,<4\njsonschema>=4.23,<5\nlxml>=5\n')
    for operation in ('start','stop'):
        (scripts/f'{operation}.command').write_text('#!/bin/sh\nset -eu\nPPTX_BUNDLE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nif [ -n "${PPTX_PYTHON:-}" ]; then PPTX_BUNDLE_PYTHON=$PPTX_PYTHON; elif command -v python3.11 >/dev/null 2>&1; then PPTX_BUNDLE_PYTHON=python3.11; else PPTX_BUNDLE_PYTHON=python3; fi\nexec "$PPTX_BUNDLE_PYTHON" "$PPTX_BUNDLE_DIR/bundle_control.py" '+operation+' "$@"\n')
        (scripts/f'{operation}.command').chmod(0o755)
        (scripts/f'{operation}.ps1').write_text('$ErrorActionPreference = "Stop"\n$BundlePython = if ($env:PPTX_PYTHON) { $env:PPTX_PYTHON } else { "python" }\n& $BundlePython (Join-Path $PSScriptRoot "bundle_control.py") '+operation+' @args\nexit $LASTEXITCODE\n')
    return scripts


def assemble_bundle(ws,destination,zip_output=False):
    destination=Path(destination).absolute();zipped=destination.with_suffix('.zip') if zip_output else None
    if destination.exists() or destination.is_symlink():raise PptxError('Bundle destination already exists; choose a new directory')
    if zipped and (zipped.exists() or zipped.is_symlink()):raise PptxError('Bundle ZIP destination already exists; choose a new directory')
    if destination.resolve().is_relative_to(ws.home.resolve()):raise PptxError('Bundle destination must be outside its workspace home')
    with ws.lock():
        ws.check_original();report=validate_interactive(ws.root,require_runtime=True)
        if not report['ok']:raise PptxError('; '.join(report['errors']))
        if not report['instances']:raise PptxError('No interactive instances to bundle')
        native_before=manifest(ws.root);sidecar=ws.home/'interactive/deck';sidecar_before=manifest(sidecar)
    runtime=PLUGIN_ROOT/'runtime/dist';runtime_before=manifest(runtime)
    if not (runtime/'preview.html').is_file():raise PptxError('Build runtime before bundling')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Export into an immutable, durable workspace output generation. A failed
    # bundle never leaves latest_output referring to a deleted temporary stage.
    native_output=export(ws,ws.home/'output'/f'bundle-source-{uuid.uuid4().hex}.pptx')
    with tempfile.TemporaryDirectory(prefix='.interactive-bundle-',dir=destination.parent) as tmp:
        stage=Path(tmp)/'bundle';stage.mkdir();shutil.copyfile(native_output,stage/'presentation.pptx')
        shutil.copytree(sidecar,stage/'deck');shutil.copytree(runtime,stage/'runtime/dist');shutil.copytree(PLUGIN_ROOT/'runtime/manifests',stage/'manifests')
        scripts=write_controller(stage);server=scripts/'pptx_core';server.mkdir()
        for filename in ('__init__.py','common.py','interactive_server.py','interactive_validate.py'):
            shutil.copyfile(Path(__file__).parent/filename,server/filename)
        (server/'interactive_validate.py').write_text((server/'interactive_validate.py').read_text().replace('PLUGIN_ROOT = Path(__file__).resolve().parents[4]','PLUGIN_ROOT = Path(__file__).resolve().parents[2]'))
        shutil.copyfile(PLUGIN_ROOT/'runtime/config.json',stage/'runtime/config.json');shutil.copytree(PLUGIN_ROOT/'skills/pptx/schemas',stage/'skills/pptx/schemas')
        bundle=read_json(stage/'deck/bundle.json');bundle['pptxHash']=sha256(stage/'presentation.pptx');atomic_json(stage/'deck/bundle.json',bundle);validate_bundle_manifest(bundle,stage/'deck')
        (stage/'README.txt').write_text('Interactive presentation bundle\n\n1. Install Python 3.11+ and run python3 -m pip install -r scripts/requirements.txt\n2. Install a trusted localhost certificate with office-addin-dev-certs on this computer.\n3. Sideload manifests/manifest.addin.xml in PowerPoint (or unified manifest on supported hosts).\n4. Run scripts/start.command (macOS/Linux) or scripts/start.ps1 (Windows).\n5. Open presentation.pptx. Stop only this runtime with scripts/stop.command or scripts/stop.ps1.\n\nThe start command verifies every distributed file and runs the runtime in the background. Logs and private process control records are outside the served bundle, in your user cache/rick-ppt-runtime directory. Starting twice returns the existing instance. Stop authenticates this bundle instance and never kills by PID. Set PPTX_PYTHON to choose an installed Python interpreter.\n\nVerification/status: python3 scripts/bundle_control.py verify (or status)\nExplicit browser-only HTTP: python3 scripts/bundle_control.py start --http --port 41975\nPowerPoint requires HTTPS on the origin declared by its manifest.\n\nStandalone preview: https://localhost:41973/preview.html?deck='+bundle['deckId']+'&scene='+next(iter(bundle['scenes']))+'\nOffice.js is loaded from Microsoft; all deck assets and feature packs are local.\nBrowser tests do not certify PowerPoint playback. See verification.json.\n')
        atomic_json(stage/'verification.json',report)
        atomic_json(stage/'checksums.json',{k:v['hash'] for k,v in manifest(stage).items()})
        zip_candidate=Path(tmp)/'bundle.zip'
        if zipped:
            with zipfile.ZipFile(zip_candidate,'x',zipfile.ZIP_DEFLATED) as archive:
                for name in manifest(stage):archive.write(stage/name,destination.name+'/'+name)
        with ws.lock():
            ws.check_original()
            altered=[]
            if changed_paths(native_before,manifest(ws.root)):altered.append('Native workspace')
            if changed_paths(sidecar_before,manifest(sidecar)):altered.append('Sidecar')
            if changed_paths(runtime_before,manifest(runtime)):altered.append('Runtime build')
            if altered:
                ws.refresh();raise PptxError(', '.join(altered)+' changed during bundle assembly')
            final_report=validate_interactive(ws.root,require_runtime=True)
            if not final_report['ok']:raise PptxError('; '.join(final_report['errors']))
            destination.mkdir()  # Reserve a new location without replacing user data.
            for child in sorted(stage.iterdir(),key=lambda path:path.name=='checksums.json'):
                shutil.move(str(child),destination/child.name)
            ws.state.update(latest_bundle=str(destination),latest_output=str(destination/'presentation.pptx'),baseline=native_before,interactive_baseline=sidecar_before,native_dirty=False,interactive_dirty=False,dirty=False,changed_files=[],changed_slides=[],interactive_changed_files=[],stop_failures=0)
            ws.save()
            if zipped:os.link(zip_candidate,zipped)  # Atomic no-overwrite publication.
    return {'bundle':str(destination),'zip':str(zipped) if zipped else None,'pptx':str(destination/'presentation.pptx'),'runtime_verified':report['runtime_verified'],'powerpoint_playback_verified':False,'native_unchanged':True,'sidecar_unchanged':True}
