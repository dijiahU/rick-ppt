"""Host broker for public HTTPS media through direct or trusted local transport.

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
DOWNLOAD_BUDGET=65

class MediaError(ValueError):
    def __init__(self,code,message,**details):
        super().__init__(message);self.code=code;self.details=details

def local_proxy(environ=None):
    """Only host-owned, unauthenticated loopback HTTP proxies are supported."""
    env=os.environ if environ is None else environ
    value=next((env[k] for k in ('HTTPS_PROXY','https_proxy','HTTP_PROXY','http_proxy') if env.get(k)),None)
    if value is None:return None
    try:
        u=urlsplit(value);host=u.hostname
        if host=='localhost':host='127.0.0.1'
        if (u.scheme!='http' or not host or not ipaddress.ip_address(host).is_loopback
            or not u.port or u.username is not None or u.password is not None
            or u.path not in ('','/') or u.query or u.fragment):raise ValueError()
    except ValueError:
        raise MediaError('proxy_configuration','Media proxy must be an unauthenticated loopback HTTP endpoint') from None
    return f'http://{"["+host+"]" if ":" in host else host}:{u.port}'

def proxy_args(proxy):
    return ['--proxy',proxy or '', '--noproxy','' if proxy else '*']

def dns_addresses(host,proxy,timeout=8):
    # Use a fixed external resolver over the trusted proxy. Local VPN fake-IP
    # DNS and the old direct resolver can disagree with the destination network.
    resolver='https://dns.google/resolve' if proxy else 'https://dns.alidns.com/resolve'
    endpoint=resolver+'?'+urlencode({'name':host,'type':'A'})
    command=['/usr/bin/curl','-q',*proxy_args(proxy),'--silent','--show-error','--fail',
             '--connect-timeout',str(min(8,timeout)),'--max-time',str(timeout),
             '--max-filesize','65536','--url',endpoint]
    try:response=subprocess.run(command,capture_output=True,timeout=timeout+2,env={'PATH':'/usr/bin:/bin'})
    except subprocess.TimeoutExpired:
        raise MediaError('dns_timeout','Public DNS verification timed out',host=host) from None
    if response.returncode:
        raise MediaError('dns_unavailable','Public DNS verification unavailable',host=host,curl_exit=response.returncode)
    try:
        answer=json.loads(response.stdout)
        if answer.get('Status',0)!=0:raise ValueError()
        return [a['data'] for a in answer.get('Answer',[]) if a.get('type')==1]
    except (ValueError,KeyError,TypeError,AttributeError):
        raise MediaError('dns_response','Public DNS returned an invalid response',host=host) from None

def resolve_url(value,proxy=None,timeout=8):
    if not isinstance(value,str) or len(value)>3000 or any(ord(c)<33 for c in value):raise ValueError('Invalid URL')
    u=urlsplit(value)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):raise ValueError('Only public HTTPS on port 443, without credentials')
    host=u.hostname.encode('idna').decode('ascii').lower()
    if '.' not in host or host.endswith(('.localhost','.local','.internal')):raise ValueError('Local host forbidden')
    try:literal=ipaddress.ip_address(host)
    except ValueError:literal=None
    if literal and not literal.is_global:raise MediaError('non_public_address','Non-public address forbidden',host=host)
    if literal:addresses=[str(literal)]
    elif proxy:addresses=dns_addresses(host,proxy,timeout)
    else:
        try:addresses=sorted({x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
        except socket.gaierror:addresses=[]
    if not proxy and (not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses)):
        # Some VPN DNS proxies return 198.18/15 fake IPs. Never allow those as
        # media targets. Ask a fixed HTTPS resolver and still pin the real IP.
        addresses=dns_addresses(host,None,timeout)
    if not addresses:raise MediaError('dns_no_address','Public DNS returned no usable A records',host=host)
    if any(not ipaddress.ip_address(a).is_global for a in addresses):raise MediaError('non_public_address','Non-public address forbidden',host=host)
    # Prefer IPv4 when both are valid. curl keeps TLS hostname verification.
    ip=next((a for a in addresses if ':' not in a),addresses[0])
    pinned=f'[{ip}]' if ':' in ip else ip
    return urlunsplit(('https',host,u.path or '/',u.query,'')),f'{host}:443:{pinned}'

def download(url):
    proxy=local_proxy();route='local_proxy' if proxy else 'direct'
    deadline=time.monotonic()+DOWNLOAD_BUDGET
    for _ in range(4):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise MediaError('download_timeout','Media download time budget exhausted',route=route)
        url,pin=resolve_url(url,proxy,timeout=min(8,remaining))
        host=urlsplit(url).hostname
        remaining=deadline-time.monotonic()
        if remaining<=0:raise MediaError('download_timeout','Media download time budget exhausted',host=host,route=route)
        with tempfile.NamedTemporaryFile(prefix='pptx-media-headers-') as headers:
            # --resolve alone does not pin the CONNECT target of an HTTP proxy.
            # --connect-to pins that target while retaining the URL's TLS/SNI name.
            pin_args=['--connect-to',pin+':443'] if proxy else ['--resolve',pin]
            command=['/usr/bin/curl','-q','--silent','--show-error',*proxy_args(proxy),
                '--proto','=https','--proto-redir','=https','--connect-timeout','8','--max-time',str(min(50,remaining)),
                '--max-filesize',str(MAX_DOWNLOAD),*pin_args,'--dump-header',headers.name,
                '--user-agent','PPTX-Lab-Media/1.0','--url',url]
            for attempt in range(2):
                remaining=deadline-time.monotonic()
                if remaining<=0:raise MediaError('download_timeout','Media download time budget exhausted',host=host,route=route)
                command[command.index('--max-time')+1]=str(min(50,remaining))
                try:run=subprocess.run(command,capture_output=True,timeout=min(50,remaining)+2,env={'PATH':'/usr/bin:/bin'})
                except subprocess.TimeoutExpired:
                    raise MediaError('download_timeout','Media download timed out',host=host,route=route) from None
                # One retry for an empty, transient transport failure. Never retry
                # HTTP rejections, certificate/size failures or partial downloads.
                if attempt==0 and run.returncode in (7,28,35,52,55,56) and not run.stdout:continue
                break
            if run.returncode:
                codes={5:('proxy_dns','Media proxy address could not be resolved'),6:('dns_unavailable','Media host could not be resolved'),
                       7:('connection_failed','Media connection failed'),18:('incomplete_download','Media transfer ended before the file was complete'),
                       28:('download_timeout','Media connection or download timed out'),35:('tls_handshake','Media TLS handshake failed'),
                       60:('tls_certificate','Media TLS certificate verification failed'),63:('download_too_large','Media exceeds the download size limit')}
                code,message=codes.get(run.returncode,('download_failed','Media transport failed'))
                raise MediaError(code,message,host=host,route=route,curl_exit=run.returncode,attempts=attempt+1)
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
        if status!=200:raise MediaError('http_status',f'Media URL returned HTTP {status}',host=host,route=route,http_status=status)
        content_type=fields.get('content-type','').split(';')[0].lower()
        if content_type in ('text/html','application/json') or not run.stdout:raise MediaError('not_media','URL is a page, not a downloadable media file',host=host)
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
        except MediaError as error:self.result={'ok':False,'error':str(error),'error_code':error.code,'details':error.details}
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
