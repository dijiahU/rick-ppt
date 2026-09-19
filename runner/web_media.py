"""Host broker for public HTTPS media. No credentials, proxies or private network.

DNS is validated AND pinned for each redirect; decoding is isolated in Docker.
Task-controlled paths are never used as host output or executable paths.
"""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import time
from urllib.parse import urlsplit,urlunsplit,urljoin,urlencode
import uuid
from progress import read_scoped,public_text,public_url
from trajectory import record as capture
import mimetypes

MAX_DOWNLOAD=30*1024*1024

def resolve_url(value):
    if not isinstance(value,str) or len(value)>3000 or any(ord(c)<33 for c in value):raise ValueError('Invalid URL')
    u=urlsplit(value)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):raise ValueError('Only public HTTPS on port 443, without credentials')
    host=u.hostname.encode('idna').decode('ascii').lower()
    if '.' not in host or host.endswith(('.localhost','.local','.internal')):raise ValueError('Local host forbidden')
    try:addresses=sorted({x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
    except socket.gaierror:addresses=[]
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        # Some VPN DNS proxies return 198.18/15 fake IPs. Never allow those as
        # media targets. Ask a fixed HTTPS resolver and still pin the real IP.
        endpoint='https://dns.alidns.com/resolve?'+urlencode({'name':host,'type':'A'})
        response=subprocess.run(['/usr/bin/curl','-q','--proxy','','--noproxy','*','--silent','--show-error','--fail','--max-time','8','--max-filesize','65536','--url',endpoint],capture_output=True,timeout=10,env={'PATH':'/usr/bin:/bin'})
        if response.returncode:raise ValueError('Public DNS verification unavailable')
        answer=json.loads(response.stdout)
        addresses=[a['data'] for a in answer.get('Answer',[]) if a.get('type')==1]
    if not addresses:raise ValueError('Public DNS returned no usable A records')
    if any(not ipaddress.ip_address(a).is_global for a in addresses):raise ValueError('Non-public address forbidden')
    # Prefer IPv4 when both are valid. curl keeps TLS hostname verification.
    ip=next((a for a in addresses if ':' not in a),addresses[0])
    pinned=f'[{ip}]' if ':' in ip else ip
    return urlunsplit(('https',host,u.path or '/',u.query,'')),f'{host}:443:{pinned}'

def download(url):
    for _ in range(4):
        url,pin=resolve_url(url)
        with tempfile.NamedTemporaryFile(prefix='pptx-media-headers-') as headers:
            command=['/usr/bin/curl','-q','--silent','--show-error','--proxy','','--noproxy','*',
                '--proto','=https','--proto-redir','=https','--connect-timeout','8','--max-time','25',
                '--max-filesize',str(MAX_DOWNLOAD),'--resolve',pin,'--dump-header',headers.name,
                '--user-agent','PPTX-Lab-Media/1.0','--url',url]
            run=subprocess.run(command,capture_output=True,timeout=30,env={'PATH':'/usr/bin:/bin'})
            if run.returncode:raise ValueError('Public media download failed (HTTP/network/size limit)')
            if len(run.stdout)>MAX_DOWNLOAD:raise ValueError('Download too large')
            raw=headers.read(65537)
        if len(raw)>65536:raise ValueError('Headers too large')
        blocks=raw.decode('latin1').strip().split('\r\n\r\n');block=next((b for b in reversed(blocks) if b.startswith('HTTP/')),None)
        if not block:raise ValueError('No HTTP status')
        lines=block.splitlines();status=int(lines[0].split()[1]);fields={}
        for line in lines[1:]:
            if ':' in line:
                k,v=line.split(':',1);fields[k.lower()]=v.strip()
        if status in (301,302,303,307,308):
            if not fields.get('location'):raise ValueError('Invalid redirect')
            url=urljoin(url,fields['location']);continue
        if status!=200:raise ValueError('Media URL must return HTTP 200')
        content_type=fields.get('content-type','').split(';')[0].lower()
        if content_type in ('text/html','application/json') or not run.stdout:raise ValueError('URL is a page, not a downloadable media file')
        return run.stdout,url,content_type
    raise ValueError('Too many redirects')

def normalize(data):
    with tempfile.TemporaryDirectory(prefix='pptx-media-decode-') as directory:
        root=Path(directory);(root/'input').write_bytes(data)
        container='pptx-media-'+uuid.uuid4().hex
        command=['/usr/local/bin/docker','run','--name',container,'--rm','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','128','--memory','1g','--cpus','1',
            '--user',f'{os.getuid()}:{os.getgid()}','--tmpfs','/tmp:rw,nosuid,nodev,size=128m',
            '--mount',f'type=bind,source={root},target=/work','pptx-lab-media:1']
        try:run=subprocess.run(command,capture_output=True,timeout=130)
        finally:subprocess.run(['/usr/local/bin/docker','rm','-f',container],capture_output=True,timeout=15)
        if run.returncode:raise ValueError('Media format/codec/limits could not be validated or converted')
        result=json.loads(read_scoped(root,Path('result.json'),4096))
        if result.get('kind') not in ('image','gif','video','audio'):raise ValueError('Invalid decoded media')
        if result.get('file') not in ('media.png','media.gif','media.mp4','media.mp3'):raise ValueError('Unexpected decoded file')
        files={result['file']:read_scoped(root,Path(result['file']),28*1024*1024)}
        if result.get('poster')=='poster.png':files['poster.png']=read_scoped(root,Path('poster.png'),12*1024*1024)
        return result,files

class WebMediaBroker:
    def __init__(self,job,reporter=None,trajectory=None):
        self.job=job;self.reporter=reporter;self.processed=set();self.records=[];self.bytes=0
        self.worker=None;self.result=None;self.current=None
        self.trajectory=trajectory

    def fetch(self,data):
        try:
            if len(self.records)>=16 or len(self.processed)>32:raise ValueError('Per-task media import limit reached')
            if not isinstance(data.get('purpose'),str) or not data['purpose'].strip():raise ValueError('Asset purpose required')
            blob,final_url,mime=download(data.get('url'))
            source={'request_id':self.current,'requested_url':data.get('url'),'final_url':final_url,
                    'source_page':data.get('source_page'),'purpose':data.get('purpose'),'content_type':mime}
            capture(self.trajectory,'artifact',blob,'original'+(mimetypes.guess_extension(mime) or '.bin'),'download-originals',source)
            metadata,files=normalize(blob)
            for name,body in files.items():capture(self.trajectory,'artifact',body,name,'download-converted',{**source,'source_sha256':hashlib.sha256(blob).hexdigest(),'conversion':metadata})
            total=sum(map(len,files.values()))
            if self.bytes+total>60*1024*1024:raise ValueError('Task media total exceeds 60 MB')
            self.result=(metadata,files,dict(url=final_url,sourcePage=public_url(data.get('source_page')),purpose=public_text(data['purpose']),sourceSha256=hashlib.sha256(blob).hexdigest(),contentType=mime))
        except Exception as error:self.result={'ok':False,'error':public_text(str(error)) or type(error).__name__}

    @staticmethod
    def publish(fd,name,body):
        pending='host-'+uuid.uuid4().hex+'.tmp'
        f=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
        with os.fdopen(f,'wb') as stream:stream.write(body)
        os.replace(pending,name,src_dir_fd=fd,dst_dir_fd=fd)

    def poll(self,start_new=True):
        import threading
        root=os.open(self.job,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            qfd=os.open('media-requests',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root)
            try:
                if self.worker:
                    if self.worker.is_alive():return
                    self.worker.join();self.worker=None;result=self.result
                    if isinstance(result,tuple):
                        metadata,files,origin=result
                        afd=os.open('assets',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root)
                        try:
                            for name,body in files.items():self.publish(afd,'web-'+self.current+'-'+name,body)
                            record={**metadata,**origin,'id':self.current,'file':'web-'+self.current+'-'+metadata['file'],'sha256':hashlib.sha256(files[metadata['file']]).hexdigest()}
                            if metadata.get('poster'):record['poster']='web-'+self.current+'-poster.png'
                            self.records.append(record);self.bytes+=sum(map(len,files.values()))
                            self.publish(afd,'web-index.json',json.dumps({'assets':self.records},ensure_ascii=False).encode())
                        finally:os.close(afd)
                        result={'ok':True,**record,'path':str(self.job/'assets'/record['file'])}
                        if self.reporter:self.reporter.event('edited','Imported '+metadata['kind']+': '+origin['purpose'],url=origin['sourcePage'] or origin['url'],state='completed',category='media')
                    elif self.reporter:self.reporter.event('working',result.get('error','Media import failed'),state='failed',category='media')
                    self.publish(qfd,self.current+'.reply.json',json.dumps(result,ensure_ascii=False).encode())
                    self.current=None;self.result=None
                if not start_new or len(self.processed)>=32:return
                for name in sorted(os.listdir(qfd))[:1000]:
                    if not re.fullmatch(r'[0-9a-f]{32}\.request\.json',name):continue
                    ident=name.split('.')[0]
                    if ident in self.processed:continue
                    if ident+'.reply.json' in os.listdir(qfd):continue
                    self.processed.add(ident)
                    try:
                        data=json.loads(read_scoped(self.job,Path('media-requests')/name,8192))
                        if not isinstance(data,dict):raise ValueError('Invalid request')
                    except (ValueError,OSError):
                        self.publish(qfd,ident+'.reply.json',b'{"ok":false,"error":"Invalid request file"}');continue
                    self.current=ident;self.worker=threading.Thread(target=self.fetch,args=(data,),daemon=True,name='media-import')
                    capture(self.trajectory,'emit','media.request',{'request_id':ident,'request':data})
                    if self.reporter:self.reporter.event('working','Download media: '+public_text(data.get('purpose')),url=data.get('url'),state='started',category='media')
                    self.worker.start();break
            finally:os.close(qfd)
        finally:os.close(root)

    def drain(self,timeout=280):
        deadline=time.monotonic()+max(0,timeout)
        while self.worker is not None and time.monotonic()<deadline:
            self.poll(start_new=False)
            if self.worker is not None:time.sleep(.2)
        if self.worker is not None:
            capture(self.trajectory,'gap','unfinished_media_import',{'request_id':self.current})
