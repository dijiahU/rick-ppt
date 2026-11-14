"""Native LibreOffice renderer with per-request Landlock/seccomp isolation."""
import os
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

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

def render(job,input_dir,output_dir,font_dir,name,metadata,*,tick=None):
    with tempfile.TemporaryDirectory(prefix='pptx-r-') as private:
        root=Path(private)
        source=root/name;source.write_bytes((input_dir/name).read_bytes())
        out=root/'output';out.mkdir()
        fonts=root/'fonts';fonts.mkdir()
        (root/'office_tmp.so').write_bytes((Path(__file__).resolve().parents[1]/'deploy/office_tmp.so').read_bytes())
        for path in font_dir.iterdir():
            if path.suffix in ('.ttf','.otf'): (fonts/path.name).write_bytes(path.read_bytes())
        (root/'fonts.conf').write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><include>/etc/fonts/fonts.conf</include><dir>'+str(fonts)+'</dir><cachedir>'+str(root/'cache')+'</cachedir></fontconfig>')
        command=[sys.executable,str(Path(__file__).resolve()),'--child',str(root),name]
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(root),'TMPDIR':str(root),'OSL_SOCKET_PATH':str(root),'FONTCONFIG_FILE':str(root/'fonts.conf')}
        process=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        deadline=time.monotonic()+120
        try:
            while True:
                if tick:tick()
                if time.monotonic()>deadline:raise TimeoutError('Native Linux render timed out')
                try:stdout,stderr=process.communicate(timeout=.25);break
                except subprocess.TimeoutExpired:pass
            if process.returncode==0:
                pdf=out/(Path(name).stem+'.pdf')
                if not pdf.is_file():return subprocess.CompletedProcess(command,1,stdout,stderr+'\nNo PDF produced')
                (output_dir/pdf.name).write_bytes(pdf.read_bytes())
            return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
        finally:
            if process.poll() is None:
                import signal
                os.killpg(process.pid,signal.SIGKILL);process.communicate()

if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
    from linux_sandbox import restrict
    root=Path(sys.argv[2]);name=sys.argv[3]
    # Read the host-owned quota before the filesystem restriction. LibreOffice
    # 7.3 otherwise uses hardware_concurrency(), ignoring cpu.max entirely.
    parallelism=render_parallelism()
    # Each conversion gets its own uid as well as its own profile/socket path.
    # A shared service uid lets separate LO lifecycles interfere with each other.
    restrict(root,reads=['/var/lib/libreoffice','/var/spool/libreoffice','/var/cache/fontconfig'],local_socket_server=True)
    os.environ['LD_PRELOAD']=str(root/'office_tmp.so')
    os.environ['URE_BOOTSTRAP']='vnd.sun.star.pathname:/usr/lib/libreoffice/program/fundamentalrc'
    os.environ['SAL_USE_VCLPLUGIN']='svp'
    os.environ['MAX_CONCURRENCY']=str(parallelism)
    command=['/usr/lib/libreoffice/program/soffice.bin','-env:INIFILENAME=vnd.sun.star.pathname:/usr/lib/libreoffice/program/sofficerc','-env:OSL_SOCKET_PATH='+str(root),'-env:UserInstallation='+ (root/'profile').as_uri(),'--headless','--norestore','--convert-to','pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}','--outdir',str(root/'output'),str(root/name)]
    result=convert(command,interrupted_retry=fresh_profile)
    raise SystemExit(result.returncode)
