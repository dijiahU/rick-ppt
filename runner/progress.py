"""Task-scoped, allowlisted public activity. Never upload raw model text or commands."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from urllib.parse import urlsplit, urlunsplit,parse_qsl,urlencode
from outline import validate_outline, page_version, MAX_SLIDES, MAX_OUTLINE_BYTES, MAX_JOURNAL_BYTES
from draft_progress import DraftProgress

def public_text(value, limit=800):
    if not isinstance(value,str):return ''
    # Do not publish local paths, credentials or control characters.
    value=re.sub(r'(?:/Users/|/private/|/tmp/|[A-Z]:\\)[^\s]*','[local path]',value)
    value=re.sub(r'(?i)(?:bearer\s+\S+|(?:token|password|api[_-]?key|secret)\s*[:=]\s*\S+|sk-[\w-]{10,})','[redacted]',value)
    return ' '.join(value.split())[:limit]

def public_url(value):
    if not isinstance(value,str):return None
    try:
        url=urlsplit(value)
        if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:return None
        if len(value)>2000:return None
        # Retain only resource identity parameters (e.g. a video's v= ID),
        # never authentication/tracking parameters or local/private links.
        import ipaddress
        host=url.hostname.lower()
        if host=='localhost' or '.' not in host or host.endswith(('.local','.internal')):return None
        try:
            if not ipaddress.ip_address(host).is_global:return None
        except ValueError:pass
        pairs=[(k,v) for k,v in parse_qsl(url.query) if k in ('id','v','page','lang','title','article','app','appid','app_id','p') and len(v)<=200 and public_text(v,200)==v]
        result=urlunsplit((url.scheme,url.netloc,url.path,urlencode(pairs),''))
        return result if len(result)<=1200 and public_text(result,1200)==result else None
    except ValueError:return None

def read_scoped(root, path, limit):
    path=Path(path)
    relative=path.relative_to(root) if path.is_absolute() else path
    if not relative.parts or any(p in ('.','..') for p in relative.parts):raise ValueError('Invalid task path')
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for component in relative.parts[:-1]:
            next_fd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        child=os.open(relative.parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        with os.fdopen(child,'rb') as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size>limit:raise ValueError('File exceeds limit')
            data=stream.read(limit+1)
            if len(data)>limit:raise ValueError('File exceeds limit')
            return data
    finally:os.close(fd)

class Reporter:
    def __init__(self,cfg,task,job,send,*,explicit_previews=False):
        self.cfg,self.task,self.job,self.send=cfg,task,job,send
        self.explicit_previews=explicit_previews
        self.events=[];self.seq=0;self.offset=0;self.previews={};self.pending={};self.last_sent=0;self.dirty=True
        self.public_revision=0
        self.journal_offset=0;self.journal_identity=None;self.notes=[];self.urgent=False
        self.outline=None;self.preview_content={};self.pending_content={}
        self.reviews={'content':'pending','visual':'pending'}
        self.drafts=DraftProgress(cfg,task,job,lambda *args:self.send(*args))
        self.event('started')

    def set_outline(self,value):
        outline=validate_outline(value,self.task.get('pages'))
        if self.outline and self.outline['revision']==outline['revision']:return
        self.outline=outline
        self.reviews={'content':'pending','visual':'pending'}
        for slide in list(self.previews):
            if self.preview_content.get(slide)!=page_version(outline,slide):
                self.previews.pop(slide,None);self.preview_content.pop(slide,None)
        for slide in list(self.pending):
            if self.pending_content.get(slide)!=page_version(outline,slide):
                self.pending.pop(slide,None);self.pending_content.pop(slide,None)
        self.dirty=True;self.urgent=True

    def review_state(self,kind,state):
        if kind not in self.reviews or state not in ('pending','reviewing','changes_requested','passed','unverified'):raise ValueError('Invalid review state')
        self.reviews[kind]=state;self.dirty=True;self.urgent=True

    def event(self,code,detail=None,*,url=None,reported=False,state=None,category=None,phase=None,slide=None,next_step=None):
        fields={'code':code}
        if detail:
            cleaned=public_text(detail)
            if cleaned:fields['detail']=cleaned
        safe_url=public_url(url)
        if safe_url:fields['url']=safe_url
        if reported:fields['reported']=True
        if phase in ('research','planning','design','building','rendering','review'):fields['phase']=phase
        if type(slide) is int and 1<=slide<=MAX_SLIDES:fields['slide']=slide
        if next_step:
            cleaned=public_text(next_step,400)
            if cleaned:fields['next']=cleaned
        if state in ('started','completed','failed'):fields['state']=state
        if category in ('search','source','file','command','media','render','note','lifecycle'):fields['category']=category
        if self.events and {k:v for k,v in self.events[-1].items() if k not in ('seq','at')}==fields:return
        self.seq+=1
        self.events.append({'seq':self.seq,'at':int(time.time()*1000),**fields})
        self.events=self.events[-500:];self.dirty=True
        if reported:
            self.notes.append(self.events[-1]);self.notes=self.notes[-80:];self.urgent=True

    def consume(self,event):
        # Explicitly discard reasoning, agent messages, command output and error text.
        if event.get('type') not in ('item.started','item.completed'):return
        item=event.get('item',{});kind=item.get('type')
        state='started' if event['type']=='item.started' else 'failed' if item.get('status')=='failed' else 'completed'
        if kind=='web_search':
            action=item.get('action') or {}
            if isinstance(action,dict):
                query=action.get('query') or item.get('query')
                queries=action.get('queries') if isinstance(action.get('queries'),list) else []
                if query:queries=[query,*queries]
                for q in dict.fromkeys(q for q in queries if isinstance(q,str)):
                    self.event('working',q,state=state,category='search')
                urls=action.get('urls') if isinstance(action.get('urls'),list) else []
                if isinstance(action.get('url'),str):urls=[action['url'],*urls]
                for url in dict.fromkeys(u for u in urls if isinstance(u,str)):
                    self.event('working',action.get('pattern') or action.get('type') or 'Open source',url=url,state=state,category='source')
                if not queries and not urls:self.event('working','Web research',state=state,category='search')
            return
        if kind=='file_change':
            for change in item.get('changes',[])[:100]:
                if isinstance(change,dict) and isinstance(change.get('path'),str):
                    self.event('edited',Path(change['path']).name,state=state,category='file')
        if kind in ('image_generation','image_generation_call'):
            self.event('working','Image generation',state=state,category='media')
        if kind=='command_execution':
            # Expose a bounded operation label, not scripts, stdout or secrets.
            command=item.get('command','');label=None
            if isinstance(command,str):
                for name in ('web-media-proxy.py','media-embed.py','pptx.py','soffice-proxy.py'):
                    if name in command:
                        label=name
                        match=re.search(r'\b(unpack|validate|render|export|snapshot|review|finalize)\b',command)
                        if match:label+=' · '+match[1]
                        break
            failed=item.get('exit_code') not in (None,0) or state=='failed'
            self.event('working',label or ('Execution failed' if failed else 'Task command'),state='failed' if failed else state,category='command')
        if event.get('type')!='item.completed':return
        # Progressive tasks publish logical deck pages through the explicit journal.
        # Generic render results can belong to animation-state review copies or
        # isolated native review copies; their local page numbers are not deck IDs.
        if self.explicit_previews:return
        if kind=='command_execution' and item.get('exit_code')==0:
            # Only successful structured render results provide preview paths.
            try:result=json.loads(item.get('aggregated_output',''))
            except (ValueError,TypeError):return
            if isinstance(result,dict) and isinstance(result.get('render'),dict):result=result['render']
            if isinstance(result,dict) and result.get('ok') is True and result.get('renderer')=='LibreOffice' and isinstance(result.get('pages'),list):
                for page in result['pages'][:MAX_SLIDES]:
                    if not isinstance(page,str):continue
                    match=re.fullmatch(r'slide-(\d+)\.png',Path(page).name)
                    if match and 1<=int(match[1])<=MAX_SLIDES:self.pending[int(match[1])]=(self.job,Path(page))

    def poll(self,log):
        # log is a pinned, host-owned read descriptor, never reopen an agent path.
        log.seek(self.offset)
        for _ in range(100):
            start=log.tell();line=log.readline(2*1024*1024)
            if not line or not line.endswith(b'\n'):
                log.seek(start);break
            self.offset=log.tell()
            try:self.consume(json.loads(line))
            except (ValueError,TypeError,AttributeError):pass
        self.poll_public_status()
        self.poll_public_journal()
        self.flush()

    def poll_public_status(self):
        # Explicit public-facing summary contract, NOT arbitrary model messages,
        # reasoning logs, source notes or command stdout.
        try:
            value=json.loads(read_scoped(self.job,Path('public-status.json'),4096))
            revision=value.get('revision')
            if type(revision) is not int or revision<=self.public_revision:return
            phase=value.get('phase')
            codes={'research':'working','planning':'working','design':'working','building':'working','rendering':'rendering','review':'checking'}
            if phase not in codes or not isinstance(value.get('summary'),str) or not value['summary'].strip():return
            self.event(codes[phase],value['summary'],reported=True,category='note',phase=phase,slide=value.get('slide'),next_step=value.get('next'))
            self.public_revision=revision
        except (ValueError,OSError,TypeError,AttributeError):pass

    def poll_public_journal(self):
        # Explicit opt-in public records only. Never scan private assistant text.
        # Pin each open file, reject links/FIFOs, bound bytes, and retry partial lines.
        try:
            root_fd=os.open(self.job,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:fd=os.open('public-progress.jsonl',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=root_fd)
            finally:os.close(root_fd)
            with os.fdopen(fd,'rb') as stream:
                info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_JOURNAL_BYTES:return
                identity=(info.st_dev,info.st_ino)
                if self.journal_identity is not None and identity!=self.journal_identity:return
                self.journal_identity=identity
                stream.seek(self.journal_offset)
                for _ in range(100):
                    start=stream.tell();line=stream.readline(MAX_OUTLINE_BYTES+1)
                    if not line or not line.endswith(b'\n'):break
                    self.journal_offset=stream.tell()
                    try:
                        value=json.loads(line)
                        if not isinstance(value,dict):continue
                        slide=value.get('slide')
                        if slide is not None and (type(slide) is not int or not 1<=slide<=MAX_SLIDES):continue
                        if value.get('kind')=='outline':
                            self.set_outline(value.get('outline'))
                        elif value.get('kind')=='note':
                            phase=value.get('phase')
                            if phase not in ('research','planning','design','building','rendering','review'):continue
                            if not isinstance(value.get('summary'),str) or not value['summary'].strip():continue
                            code='rendering' if phase=='rendering' else 'checking' if phase=='review' else 'working'
                            self.event(code,value['summary'],reported=True,category='note',phase=phase,slide=slide,next_step=value.get('next'))
                        elif value.get('kind')=='preview' and slide is not None:
                            rendered=value.get('render')
                            if not isinstance(rendered,dict) or rendered.get('ok') is not True or rendered.get('renderer')!='LibreOffice':continue
                            pages=rendered.get('pages')
                            if not isinstance(pages,list) or len(pages)!=1 or not isinstance(pages[0],str):continue
                            version=value.get('contentVersion')
                            if self.outline and version!=page_version(self.outline,slide):continue
                            self.pending[slide]=(self.job,Path(pages[0]));self.pending_content[slide]=version;self.urgent=True
                    except (ValueError,TypeError,AttributeError):continue
        except (OSError,ValueError):pass

    def flush(self,force=False,tick=None):
        # Scan/validate/upload in one background thread, including restored jobs
        # that enter private review and only call flush rather than public poll.
        self.drafts.poll()
        if not force and time.monotonic()-self.last_sent<(1 if self.urgent else 5):return
        self.last_sent=time.monotonic()
        base=f'/api/worker/{self.task["id"]}'
        # At most one image per normal tick; failed sync must not fail a PPT job.
        for slide in list(self.pending)[:MAX_SLIDES if force else 1]:
            if tick:tick()
            root,path=self.pending[slide]
            try:
                data=read_scoped(root,path,2*1024*1024)
                if data[:8]!=b'\x89PNG\r\n\x1a\n' or len(data)<24:raise ValueError('PNG required')
                width=int.from_bytes(data[16:20],'big');height=int.from_bytes(data[20:24],'big')
                if not (0<width<=4096 and 0<height<=4096):raise ValueError('Invalid dimensions')
                digest=hashlib.sha256(data).hexdigest()
                if self.previews.get(slide)!=digest:
                    self.send(self.cfg,base+f'?action=preview&slide={slide}',data,self.task['lease'])
                    self.previews[slide]=digest;self.dirty=True
                    self.event('rendered',state='completed',category='render',phase='rendering',slide=slide)
                if self.outline:self.preview_content[slide]=page_version(self.outline,slide)
                del self.pending[slide]
            except (OSError,ValueError):del self.pending[slide]
            except Exception:break
            if tick:tick()
        if self.dirty or force:
            body={'updatedAt':int(time.time()*1000),'events':self.events,'notes':self.notes,'previews':sorted(self.previews),'previewVersions':{str(n):digest[:16] for n,digest in self.previews.items()}}
            if self.outline:body['outline']=self.outline
            body['reviews']=dict(self.reviews)
            while len(json.dumps(body).encode())>480000 and len(body['events'])>1:
                body['events']=body['events'][1:]
            while len(json.dumps(body).encode())>480000 and len(body['notes'])>1:
                body['notes']=body['notes'][1:]
            try:
                self.send(self.cfg,base+'?action=progress',json.dumps(body).encode(),self.task['lease'])
                self.dirty=False;self.urgent=bool(self.pending)
            except Exception:pass

    def finish_drafts(self,timeout=2):
        """Best-effort final synchronization; never an unbounded worker shutdown."""
        self.drafts.finish(timeout)
