"""Rick's login-session service keeper. No task credentials or model requests."""
import datetime,json,os,plistlib,re,socket,subprocess,time,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WORKER=ROOT if (ROOT/'production_bridge.py').is_file() else ROOT.parent/'.work/interactive-runtime-20260920/repo/runner'
STATE=ROOT/'service-watchdog.local.json'
LOGIN=Path.home()/'Library/LaunchAgents/chat.rickppt.worker.plist'

def command(args,timeout=6):
    try:return subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired):return None

def local_proxy_ready():
    # Reuse the existing private login transport; do not alter network settings.
    try:env=plistlib.loads(LOGIN.read_bytes()).get('EnvironmentVariables',{})
    except (OSError,ValueError):return True
    from urllib.parse import urlsplit
    targets=set()
    for keys in [('https_proxy','HTTPS_PROXY','all_proxy','ALL_PROXY'),('http_proxy','HTTP_PROXY','all_proxy','ALL_PROXY')]:
        value=next((env[k] for k in keys if env.get(k)),'')
        try:
            u=urlsplit(value)
            if u.hostname in ('127.0.0.1','localhost','::1') and u.port:targets.add((u.hostname,u.port))
        except ValueError:continue
    for host,port in targets:
        try:
            with socket.create_connection((host,port),timeout=.5):pass
        except OSError:return False
    return True

def check(previous=None,now=None):
    now=time.time() if now is None else now
    previous=previous or {};attempts=dict(previous.get('last_launch',{}));status={}
    def launch(name,args,interval=60,timeout=6):
        if now-attempts.get(name,0)<interval:return
        attempts[name]=now;command(args,timeout)
    power=command(['/usr/bin/pmset','-g'])
    disabled=bool(power and re.search(r'SleepDisabled\s+1',power.stdout))
    if not disabled:
        enabled=command(['/usr/bin/sudo','-n','/usr/bin/pmset','-a','disablesleep','1'])
        disabled=bool(enabled and enabled.returncode==0)
    status['sleep_protected']=disabled
    amp=command(['/usr/bin/pgrep','-x','Amphetamine'])
    status['amphetamine_running']=bool(amp and amp.returncode==0)
    if not status['amphetamine_running']:launch('amphetamine',['/usr/bin/open','-g','-a','/Applications/Amphetamine.app'])
    status['local_proxy_ready']=local_proxy_ready()
    if not status['local_proxy_ready']:
        clash=command(['/usr/bin/pgrep','-f','/Applications/Clash Verge.app/Contents/MacOS/clash-verge'])
        if not clash or clash.returncode:launch('proxy',['/usr/bin/open','-g','-a','/Applications/Clash Verge.app'])
    docker=command(['/usr/local/bin/docker','info','--format','{{.ServerVersion}}'])
    status['docker_ready']=bool(docker and docker.returncode==0 and docker.stdout.strip())
    if not status['docker_ready']:launch('docker',['/usr/bin/open','-g','-a','/Applications/Docker.app'],120)
    image=command(['/usr/local/bin/docker','image','inspect','pptx-lab-renderer:1','--format','{{.Id}}']) if status['docker_ready'] else None
    if status['docker_ready'] and not (image and image.returncode==0 and image.stdout.strip().startswith('sha256:')):
        image=command(['/usr/local/bin/docker','image','inspect','docker.io/library/pptx-lab-renderer:1','--format','{{.Id}}'])
    status['renderer_ready']=bool(image and image.returncode==0 and image.stdout.strip().startswith('sha256:'))
    try:pid=(WORKER/'worker.lock').read_text().strip()
    except OSError:pid=''
    process=command(['/bin/ps','-p',pid,'-o','command=']) if pid.isdigit() else None
    status['worker_running']=bool(process and process.returncode==0 and str(WORKER/'runner.py') in process.stdout)
    if not status['worker_running']:launch('worker',[sys.executable,str(ROOT/'start-worker.py')],30,12)
    site=command(['/usr/bin/curl','--disable','--silent','--connect-timeout','3','--max-time','5','--output','/dev/null','--write-out','%{http_code}','https://rickppt.aaarickmorty.chatgpt.site/api/account']) if status['local_proxy_ready'] else None
    status['site_reachable']=bool(site and site.returncode==0 and site.stdout.strip()=='200')
    return {'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':status,'last_launch':attempts}

def main():
    try:previous=json.loads(STATE.read_text())
    except (OSError,ValueError):previous={}
    current=check(previous)
    if current['status']!=previous.get('status'):
        with (ROOT/'service-watchdog-events.local.jsonl').open('a') as out:out.write(json.dumps({'at':current['checked_at'],**current['status']})+'\n')
    pending=STATE.with_suffix('.pending')
    fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out:json.dump(current,out)
    os.replace(pending,STATE)

if __name__=='__main__':main()
