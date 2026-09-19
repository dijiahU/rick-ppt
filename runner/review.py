#!/usr/bin/env python3
"""Read-only request/PPTX retrieval, with optional delivered ZIP. No queue writes."""
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
MAX_BUNDLE=250*1024*1024
DELIVERY_HEADER='X-Review-Delivery'
TASK_UUID=r'[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}'

def review_path(path):
    """Exact GET route allowlist; query text cannot become an endpoint path."""
    parsed=urllib.parse.urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError('Only read-only review routes are allowed.')
    match=re.fullmatch(r'/api/review/jobs(?:/('+TASK_UUID+r')(?:/(pptx|bundle))?)?',parsed.path)
    if not match:raise ValueError('Only read-only review routes are allowed.')
    query=urllib.parse.parse_qs(parsed.query,keep_blank_values=True)
    allowed={'q','status','page'} if not match[1] else {'include'} if not match[2] else set()
    if set(query)-allowed or any(len(values)!=1 for values in query.values()) or ('include' in query and query['include']!=['bundle']):
        raise ValueError('Unexpected review query.')
    return match[2]

def valid_etag(value):
    return isinstance(value,str) and 0<len(value)<=256 and not any(c in value for c in ('\r','\n','\x00'))

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
        if request.method!='GET' or not request.full_url.startswith(SITE+'/'):
            raise ValueError('Only this site’s read-only routes are allowed.')
        kind=review_path(request.full_url[len(SITE):])
        limit=getattr(request,'review_limit',MAX_BUNDLE if kind=='bundle' else MAX_PPTX)
        if type(limit) is not int or not 0<limit<=(MAX_BUNDLE if kind=='bundle' else MAX_PPTX):raise ValueError('Invalid response limit.')
        config=[]
        for name,value in request.header_items():
            if '\n' in value or '\r' in value:raise ValueError('Invalid request header.')
            escaped=(name+': '+value).replace('\\','\\\\').replace('"','\\"')
            config.append('header = "'+escaped+'"')
        with tempfile.TemporaryDirectory(prefix='pptx-review-http-') as temp:
            header_path=Path(temp)/'headers'
            # --disable is first so ~/.curlrc cannot silently enable redirects.
            # Read at most limit+1 bytes, independently of curl's size checking.
            process=subprocess.Popen(['/usr/bin/curl','--disable','--silent','--proto','=https','--max-redirs','0',
                '--max-time',str(timeout),'--max-filesize',str(limit),
                '--dump-header',str(header_path),'--config','-',request.full_url],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            try:
                process.stdin.write(('\n'.join(config)+'\n').encode());process.stdin.close()
                data=process.stdout.read(limit+1)
                if len(data)>limit:raise ValueError('Response exceeds size limit.')
                try:process.wait(timeout=timeout+5)
                except subprocess.TimeoutExpired:raise ValueError('Review request timed out; no task was changed.') from None
                if process.returncode:raise ValueError('Cannot read the review service; no task was changed.')
            finally:
                if process.poll() is None:process.kill();process.wait()
                if process.stdin and not process.stdin.closed:process.stdin.close()
                if process.stdout:process.stdout.close()
            try:
                blocks=header_path.read_text().strip().split('\n\n')
                response=[block for block in blocks if block.startswith('HTTP/')][-1]
                first,_,raw_headers=response.partition('\n')
                code=int(first.split()[1]);headers=Parser().parsestr(raw_headers)
            except (IndexError,ValueError,OSError):
                raise ValueError('Invalid review service response; no task was changed.') from None
            if code!=200:raise ValueError(f'Review access failed (HTTP {code}); no task was changed.')
            return CurlResponse(data,headers)

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

    def get(self,path,limit=2*1024*1024,etag=None,delivery_version=None):
        kind=review_path(path)
        if type(limit) is not int or not 0<limit<=(MAX_BUNDLE if kind=='bundle' else MAX_PPTX):raise ValueError('Invalid response limit.')
        headers={'Authorization':'Bearer '+self.token}
        if etag is not None:
            if not valid_etag(etag):raise ValueError('Invalid artifact ETag.')
            headers['If-Match']=etag
        if delivery_version is not None:
            if not isinstance(delivery_version,str) or not re.fullmatch('[a-f0-9]{64}',delivery_version):raise ValueError('Invalid delivery version.')
            headers[DELIVERY_HEADER]=delivery_version
        request=urllib.request.Request(self.site+path,headers=headers,method='GET')
        request.review_limit=limit
        try:
            with self.opener.open(request,timeout=60) as response:
                declared=response.headers.get('Content-Length')
                if declared and not 0<=int(declared)<=limit:raise ValueError('Response exceeds size limit.')
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

    def fetch(self,job_id,out_root,bundle=False):
        if not re.fullmatch(TASK_UUID,job_id):raise ValueError('Expected a task UUID.')
        metadata_path='/api/review/jobs/'+job_id+('?include=bundle' if bundle else '')
        metadata=self.metadata(metadata_path)
        if not isinstance(metadata,dict) or not isinstance(metadata.get('job'),dict):raise ValueError('Invalid request metadata.')
        if metadata.get('job',{}).get('id')!=job_id:raise ValueError('Request ID mismatch.')
        root=out_root.resolve()
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        folder=Path(tempfile.mkdtemp(prefix=job_id+'-',dir=root))
        save_json(folder/'request.json',metadata)
        artifact=metadata.get('artifact',{})
        if not isinstance(artifact,dict):raise ValueError('Invalid PPTX metadata.')
        manifest={'jobId':job_id,'source':self.site,'contentTrust':'untrusted-user-content','request':'request.json','pptx':None,'status':metadata['job']['status'],'artifactAvailable':bool(artifact.get('available'))}
        bundle_meta=metadata.get('bundle',{}) if bundle else {}
        if not isinstance(bundle_meta,dict):raise ValueError('Invalid ZIP metadata.')
        version=None
        if bundle:manifest['bundle']={'requested':True,'available':bool(bundle_meta.get('available')),'file':None,'archiveInspected':False,'currentDeliveryConfirmed':False}
        try:
            if bundle_meta.get('available'):
                version=metadata.get('deliveryVersion')
                if not isinstance(version,str) or not re.fullmatch('[a-f0-9]{64}',version) or artifact.get('deliveryVersion')!=version or bundle_meta.get('deliveryVersion')!=version:
                    raise ValueError('PPTX and ZIP delivery version linkage is missing or inconsistent.')
                if metadata['job']['status']!='complete' or artifact.get('available') is not True:raise ValueError('ZIP has no current completed PPTX.')
                if type(bundle_meta.get('bytes')) is not int or not 4<=bundle_meta['bytes']<=MAX_BUNDLE:raise ValueError('Invalid ZIP size; maximum is 250 MiB.')
                if not valid_etag(bundle_meta.get('etag')):raise ValueError('Invalid ZIP ETag.')
                manifest['deliveryVersion']=version
            if artifact.get('available'):
                if type(artifact.get('bytes')) is not int or not 0<artifact['bytes']<=MAX_PPTX:raise ValueError('Invalid PPTX size.')
                data,headers=self.get('/api/review/jobs/'+job_id+'/pptx',MAX_PPTX,artifact['etag'],version)
                if len(data)!=artifact['bytes'] or headers.get('ETag')!=artifact['etag'] or (version and headers.get(DELIVERY_HEADER)!=version):raise ValueError('PPTX changed or is incomplete; fetch again.')
                with zipfile.ZipFile(io.BytesIO(data)) as package:
                    entries=package.infolist();names={item.filename for item in entries}
                    if len(entries)>20000 or sum(item.file_size for item in entries)>512*1024*1024:raise ValueError('PPTX exceeds safe inspection limits.')
                    if not {'[Content_Types].xml','ppt/presentation.xml'}.issubset(names):raise ValueError('Not a native PPTX package.')
                    slides=sum(bool(re.fullmatch(r'ppt/slides/slide\d+\.xml',name)) for name in names)
                descriptor=os.open(folder/'output.pptx',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(descriptor,'wb') as stream:stream.write(data)
                manifest.update(pptx='output.pptx',sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),etag=artifact['etag'],slideCount=slides)
            else:manifest['reason']=artifact.get('reason','unavailable')
            if bundle_meta.get('available'):
                data,headers=self.get('/api/review/jobs/'+job_id+'/bundle',MAX_BUNDLE,bundle_meta['etag'],version)
                if len(data)!=bundle_meta['bytes'] or headers.get('ETag')!=bundle_meta['etag'] or headers.get(DELIVERY_HEADER)!=version or headers.get('X-Review-PPTX-ETag')!=artifact['etag']:
                    raise ValueError('ZIP changed or does not match the current PPTX; fetch again.')
                if headers.get('Content-Type','').split(';')[0].strip()!='application/zip' or data[:4] not in (b'PK\x03\x04',b'PK\x05\x06'):
                    raise ValueError('Review response is not a ZIP delivery.')
                # Preserve opaque ZIP bytes. Extraction, code execution and lesson
                # acceptance belong to a separate explicitly controlled inspection.
                descriptor=os.open(folder/'interactive.zip',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(descriptor,'wb') as stream:stream.write(data)
                manifest['bundle'].update(file='interactive.zip',bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),etag=bundle_meta['etag'],deliveryVersion=version,pptxEtag=artifact['etag'])
                current=self.metadata(metadata_path)
                if current.get('job',{}).get('id')!=job_id or current.get('job',{}).get('status')!='complete' or current.get('deliveryVersion')!=version or current.get('artifact')!=artifact or current.get('bundle')!=bundle_meta:
                    raise ValueError('Current delivery changed during retrieval; originals retained, fetch again.')
                manifest['bundle']['currentDeliveryConfirmed']=True
            elif bundle:
                manifest['bundle']['reason']=bundle_meta.get('reason','review_service_without_bundle_support')
        except (ValueError,OSError,zipfile.BadZipFile):
            if bundle:
                manifest['bundle'].update(currentDeliveryConfirmed=False,reason='download_failed_or_delivery_changed')
                save_json(folder/'manifest.json',manifest)
            raise
        save_json(folder/'manifest.json',manifest)
        return {'directory':str(folder),**manifest}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('configure',help='Create a separate local secret once; never print it.')
    listing=sub.add_parser('list');listing.add_argument('--search',default='');listing.add_argument('--status',choices=['queued','running','complete','failed'],default='');listing.add_argument('--page',type=int,default=1)
    fetch=sub.add_parser('fetch');fetch.add_argument('job_id');fetch.add_argument('--out',type=Path,default=ROOT.parent/'works'/'reviews');fetch.add_argument('--bundle',action='store_true',help='Also retrieve the current interactive ZIP, if delivered; never extract or run it.')
    args=parser.parse_args()
    try:
        if args.command=='configure':result=configure()
        else:
            cfg=load_config(CONFIG);client=ReviewClient(cfg['site'],cfg['token'],CurlOpener())
            result=client.listing(args.search,args.status,args.page) if args.command=='list' else client.fetch(args.job_id,args.out,bundle=args.bundle)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,zipfile.BadZipFile) as error:
        # Never dump config, request objects or raw remote error bodies.
        parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
