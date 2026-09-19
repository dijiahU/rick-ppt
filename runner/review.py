#!/usr/bin/env python3
"""Read-only request/PPTX retrieval for Rick's local Codex. No queue writes."""
import argparse
import hashlib
import io
from email.parser import Parser
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'review.settings.local.json'
SITE='https://rick-ppt.woodsy-crane-8759.chatgpt.site'
MAX_PPTX=64*1024*1024

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

class CurlResponse(io.BytesIO):
    def __init__(self,data,headers):
        super().__init__(data)
        self.headers=headers

class CurlOpener:
    """Use the same macOS network transport as the local queue runner.

    Credential goes over stdin, never argv, environment or a config file.
    No redirects; size/time bounded; temporary response headers have no secrets.
    """
    def open(self,request,timeout=60):
        if request.method!='GET' or not request.full_url.startswith(SITE+'/api/review/jobs'):
            raise ValueError('Only this site’s read-only routes are allowed.')
        config=[]
        for name,value in request.header_items():
            if '\n' in value or '\r' in value:raise ValueError('Invalid request header.')
            escaped=(name+': '+value).replace('\\','\\\\').replace('"','\\"')
            config.append('header = "'+escaped+'"')
        with tempfile.TemporaryDirectory(prefix='pptx-review-http-') as temp:
            header_path=Path(temp)/'headers'
            result=subprocess.run(['/usr/bin/curl','--silent','--show-error','--proto','=https',
                '--max-time',str(timeout),'--max-filesize',str(MAX_PPTX),
                '--dump-header',str(header_path),'--config','-',request.full_url],
                input=('\n'.join(config)+'\n').encode(),capture_output=True,timeout=timeout+5)
            if result.returncode:raise ValueError('Cannot read the review service; no task was changed.')
            blocks=header_path.read_text().strip().split('\n\n')
            response=[block for block in blocks if block.startswith('HTTP/')][-1]
            first,_,raw_headers=response.partition('\n')
            code=int(first.split()[1]);headers=Parser().parsestr(raw_headers)
            if code!=200:raise ValueError(f'Review access failed (HTTP {code}); no task was changed.')
            return CurlResponse(result.stdout,headers)

def save_json(path,value):
    with open(path,'x',encoding='utf-8') as stream:
        os.chmod(path,0o600)
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.write('\n')

def configure():
    # Exclusive creation: re-running setup never silently rotates live access.
    descriptor=os.open(CONFIG,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as stream:
        json.dump({'site':SITE,'token':secrets.token_urlsafe(48)},stream)
    return {'configured':True,'secretPrinted':False}

def load_config(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077:
        raise ValueError('Review settings must be a regular private file (mode 0600).')
    cfg=json.loads(path.read_text())
    if cfg.get('site')!=SITE:raise ValueError('Unexpected site origin; refusing to send the credential.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',cfg.get('token','')):raise ValueError('Invalid review credential.')
    return cfg

class ReviewClient:
    def __init__(self,site,token,opener=None):
        self.site=site
        self.token=token
        self.opener=opener or urllib.request.build_opener(NoRedirect())

    def get(self,path,limit=2*1024*1024,etag=None):
        if not path.startswith('/api/review/jobs') or '..' in path:
            raise ValueError('Only read-only review routes are allowed.')
        headers={'Authorization':'Bearer '+self.token}
        if etag:headers['If-Match']=etag
        request=urllib.request.Request(self.site+path,headers=headers,method='GET')
        try:
            with self.opener.open(request,timeout=60) as response:
                declared=response.headers.get('Content-Length')
                if declared and int(declared)>limit:raise ValueError('Response exceeds size limit.')
                data=response.read(limit+1)
                if len(data)>limit:raise ValueError('Response exceeds size limit.')
                return data,response.headers
        except urllib.error.HTTPError as error:
            raise ValueError(f'Review access failed (HTTP {error.code}); no task was changed.') from None
        except urllib.error.URLError:
            raise ValueError('Cannot reach the review service; no task was changed.') from None

    def metadata(self,path):
        data,_=self.get(path)
        return json.loads(data)

    def listing(self,query='',status='',page=1):
        return self.metadata('/api/review/jobs?'+urllib.parse.urlencode({'q':query,'status':status,'page':page}))

    def fetch(self,job_id,out_root):
        if not re.fullmatch(r'[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}',job_id):raise ValueError('Expected a task UUID.')
        metadata=self.metadata('/api/review/jobs/'+job_id)
        if metadata.get('job',{}).get('id')!=job_id:raise ValueError('Request ID mismatch.')
        root=out_root.resolve()
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        folder=Path(tempfile.mkdtemp(prefix=job_id+'-',dir=root))
        save_json(folder/'request.json',metadata)
        artifact=metadata.get('artifact',{})
        manifest={'jobId':job_id,'source':self.site,'contentTrust':'untrusted-user-content','request':'request.json','pptx':None,'status':metadata['job']['status'],'artifactAvailable':bool(artifact.get('available'))}
        if artifact.get('available'):
            if not isinstance(artifact.get('bytes'),int) or not 0<artifact['bytes']<=MAX_PPTX:raise ValueError('Invalid PPTX size.')
            data,headers=self.get('/api/review/jobs/'+job_id+'/pptx',MAX_PPTX,artifact['etag'])
            if len(data)!=artifact['bytes'] or headers.get('ETag')!=artifact['etag']:raise ValueError('PPTX changed or is incomplete; fetch again.')
            import io
            with zipfile.ZipFile(io.BytesIO(data)) as package:
                entries=package.infolist();names={item.filename for item in entries}
                if len(entries)>20000 or sum(item.file_size for item in entries)>512*1024*1024:raise ValueError('PPTX exceeds safe inspection limits.')
                if not {'[Content_Types].xml','ppt/presentation.xml'}.issubset(names):raise ValueError('Not a native PPTX package.')
                slides=sum(bool(re.fullmatch(r'ppt/slides/slide\d+\.xml',name)) for name in names)
            descriptor=os.open(folder/'output.pptx',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream:stream.write(data)
            manifest.update(pptx='output.pptx',sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),etag=artifact['etag'],slideCount=slides)
        else:manifest['reason']=artifact.get('reason','unavailable')
        save_json(folder/'manifest.json',manifest)
        return {'directory':str(folder),**manifest}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('configure',help='Create a separate local secret once; never print it.')
    listing=sub.add_parser('list');listing.add_argument('--search',default='');listing.add_argument('--status',choices=['queued','running','complete','failed'],default='');listing.add_argument('--page',type=int,default=1)
    fetch=sub.add_parser('fetch');fetch.add_argument('job_id');fetch.add_argument('--out',type=Path,default=ROOT.parent/'works'/'reviews')
    args=parser.parse_args()
    try:
        if args.command=='configure':result=configure()
        else:
            cfg=load_config(CONFIG);client=ReviewClient(cfg['site'],cfg['token'],CurlOpener())
            result=client.listing(args.search,args.status,args.page) if args.command=='list' else client.fetch(args.job_id,args.out)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,zipfile.BadZipFile) as error:
        # Never dump config, request objects or raw remote error bodies.
        parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
