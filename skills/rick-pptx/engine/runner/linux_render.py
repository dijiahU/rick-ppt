"""Native LibreOffice renderer with per-request Landlock/seccomp isolation."""
import os
import json
import math
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time
import uuid
from functools import lru_cache
from render_options import pdf_filter


def installation():
    selected=Path(__file__).resolve().parents[1]/'deploy/libexec/libreoffice-current'
    prefix=selected.resolve(strict=True) if selected.exists() or selected.is_symlink() else Path('/usr/lib/libreoffice')
    for name in ('soffice.bin','sofficerc','fundamentalrc'):
        if not (prefix/'program'/name).is_file():raise RuntimeError('Incomplete LibreOffice installation')
    return prefix


def supports_page_range():
    prefix=installation();manifest=prefix/'share/rick-ppt-renderer.json'
    return manifest.is_file() and json.loads(manifest.read_text()).get('page_range_verified') is True


@lru_cache(maxsize=4)
def _version(prefix,stamp):
    return subprocess.check_output([str(Path(prefix)/'program/soffice'),'--version'],text=True,timeout=20).strip()


def renderer_version():
    prefix=installation();info=(prefix/'program/soffice.bin').stat()
    return _version(str(prefix),(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns))


def office_command(root,name,page=None,*,prefix=None):
    prefix=Path(prefix) if prefix is not None else installation()
    return [str(prefix/'program/soffice.bin'),
            '-env:INIFILENAME=vnd.sun.star.pathname:'+str(prefix/'program/sofficerc'),
            '-env:OSL_SOCKET_PATH='+str(root),'-env:UserInstallation='+(root/'profile').as_uri(),
            '--headless','--norestore','--convert-to',pdf_filter(page),
            '--outdir',str(root/'output'),str(root/name)]

def render_parallelism(*, cpu_limit=None, affinity=None):
    """Size Office's pool for the container, rather than the physical host."""
    if affinity is None:
        affinity=len(os.sched_getaffinity(0))
    available=max(1,affinity)
    try:
        raw=Path('/sys/fs/cgroup/cpu.max').read_text() if cpu_limit is None else cpu_limit
        quota,period=raw.split()
        if quota!='max':
            quota,period=int(quota),int(period)
            if quota<=0 or period<=0:raise ValueError('Invalid CPU quota')
            available=min(available,max(1,math.ceil(quota/period)))
    except (OSError,ValueError):
        pass
    return available

def fresh_profile(command):
    """Keep immutable input/output arguments; retain a killed profile for diagnosis."""
    result=list(command)
    for index,arg in enumerate(result):
        if arg.startswith('-env:UserInstallation='):
            result[index]=arg+'-retry-'+uuid.uuid4().hex
            return result
    raise ValueError('Isolated LibreOffice profile required')

def convert(command,*,interrupted_retry=None):
    """Bounded retries for LO bootstrap and one interrupted pure conversion."""
    bootstrap_retries=0;killed_retries=0
    while True:
        result=subprocess.run(command)
        if result.returncode==81 and bootstrap_retries<2:
            bootstrap_retries+=1
            continue
        if result.returncode in (-9,247) and killed_retries<1:
            killed_retries+=1
            print(f'LibreOffice conversion exited {result.returncode}; retrying once.',file=sys.stderr,flush=True)
            if interrupted_retry:command=interrupted_retry(command)
            continue
        if result.returncode not in (0,81):
            print(f'LibreOffice conversion failed with exit status {result.returncode}.',file=sys.stderr,flush=True)
        return result

def render(job,input_dir,output_dir,font_dir,name,metadata,*,tick=None,page=None):
    if page is not None and not supports_page_range():raise RuntimeError('Selected-page export requires the verified modern renderer')
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='pptx-r-') as private:
        root=Path(private)
        source=root/name;source.write_bytes((input_dir/name).read_bytes())
        out=root/'output';out.mkdir()
        fonts=root/'fonts';fonts.mkdir()
        (root/'office_tmp.so').write_bytes((Path(__file__).resolve().parents[1]/'deploy/office_tmp.so').read_bytes())
        for path in font_dir.iterdir():
            if path.suffix in ('.ttf','.otf'):shutil.copyfile(path,fonts/path.name)
        (root/'fonts.conf').write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><include>/etc/fonts/fonts.conf</include><dir>'+str(fonts)+'</dir><cachedir>'+str(root/'cache')+'</cachedir></fontconfig>')
        command=[sys.executable,str(Path(__file__).resolve()),'--child',str(root),name]
        if page is not None:command+=['--page',str(page)]
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(root),'TMPDIR':str(root),'OSL_SOCKET_PATH':str(root),'FONTCONFIG_FILE':str(root/'fonts.conf')}
        staged=time.monotonic()
        process=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        deadline=time.monotonic()+120
        try:
            while True:
                if tick:tick()
                if time.monotonic()>deadline:raise TimeoutError('Native Linux render timed out')
                try:stdout,stderr=process.communicate(timeout=.25);break
                except subprocess.TimeoutExpired:pass
            completed=time.monotonic()
            if process.returncode==0:
                pdf=out/(Path(name).stem+'.pdf')
                if not pdf.is_file():return subprocess.CompletedProcess(command,1,stdout,stderr+'\nNo PDF produced')
                (output_dir/pdf.name).write_bytes(pdf.read_bytes())
            result=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
            result.timings={'private_staging_seconds':round(staged-started,4),
                            'office_process_seconds':round(completed-staged,4),
                            'host_conversion_seconds':round(time.monotonic()-started,4)}
            return result
        finally:
            if process.poll() is None:
                import signal
                os.killpg(process.pid,signal.SIGKILL);process.communicate()

if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
    from linux_sandbox import restrict
    root=Path(sys.argv[2]);name=sys.argv[3]
    page=None
    if len(sys.argv)>4:
        if len(sys.argv)!=6 or sys.argv[4]!='--page':raise ValueError('Invalid render arguments')
        page=int(sys.argv[5])
        if not 1<=page<=200 or not supports_page_range():raise ValueError('Selected-page export is unavailable')
    prefix=installation()
    command=office_command(root,name,page,prefix=prefix)
    # Read the host-owned quota before the filesystem restriction. LibreOffice
    # 7.3 otherwise uses hardware_concurrency(), ignoring cpu.max entirely.
    parallelism=render_parallelism()
    # Each conversion gets its own uid as well as its own profile/socket path.
    # A shared service uid lets separate LO lifecycles interfere with each other.
    restrict(root,reads=[str(prefix),'/var/lib/libreoffice','/var/spool/libreoffice','/var/cache/fontconfig'],local_socket_server=True)
    os.environ['LD_PRELOAD']=str(root/'office_tmp.so')
    os.environ['URE_BOOTSTRAP']='vnd.sun.star.pathname:'+str(prefix/'program/fundamentalrc')
    os.environ['SAL_USE_VCLPLUGIN']='svp'
    os.environ['MAX_CONCURRENCY']=str(parallelism)
    result=convert(command,interrupted_retry=fresh_profile)
    raise SystemExit(result.returncode)
