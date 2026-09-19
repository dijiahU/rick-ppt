"""Private, content-addressed original artifacts with human-readable aliases."""
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import stat
import uuid

TEXT_VIEW_LIMIT=64*1024*1024


class ArtifactArchive:
    def archive_init(self):
        for folder in ('raw-blobs','artifacts','final'):(self.root/folder).mkdir(mode=0o700)
        self.catalog=os.fdopen(os.open(self.root/'artifacts.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb')
        self.artifact_count=0;self.raw_bytes=0;self.catalog_seen=set();self.last_snapshots={};self.last_sample=0

    def store_stream(self,stream):
        pending=self.root/'raw-blobs'/('.'+uuid.uuid4().hex+'.pending')
        sha=hashlib.sha256();size=0;tail=b'';host_secret=False
        secrets=[v.encode() for v in (self.cfg.get('token'),self.task.get('lease')) if v]
        overlap=max(map(len,secrets),default=1)
        try:
            with os.fdopen(os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as target:
                while data:=stream.read(1024*1024):
                    combined=tail+data
                    host_secret|=any(secret in combined for secret in secrets)
                    tail=combined[-overlap:];sha.update(data);size+=len(data);target.write(data)
            source_hash=sha.hexdigest();raw=self.root/'raw-blobs'/source_hash
            # Host credentials are not part of the task dataset. Other original
            # task bytes stay private and exact; training views remain scrubbed.
            if host_secret:
                self.gap('host_credential_in_artifact','Original bytes withheld; only a scrubbed view can be retained.')
            elif raw.exists():pending.unlink()
            else:os.chmod(pending,0o400);os.replace(pending,raw);self.raw_bytes+=size
            original=pending if host_secret else raw
            safe_hash=None;safe_size=None;transformed=None
            if size<=TEXT_VIEW_LIMIT:
                data=original.read_bytes()
                try:cleaned=self.clean_text(data.decode('utf-8')).encode()
                except UnicodeDecodeError:
                    cleaned=data
                    if host_secret:
                        for secret in secrets:cleaned=cleaned.replace(secret,b'[host credential redacted]')
                transformed=cleaned!=data;safe_hash=hashlib.sha256(cleaned).hexdigest();safe_size=len(cleaned)
                safe=self.root/'blobs'/safe_hash
                if not safe.exists():
                    if not transformed and not host_secret:os.link(raw,safe)
                    else:
                        with os.fdopen(os.open(safe,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(cleaned)
                    self.blob_bytes+=safe_size
            if host_secret:pending.unlink()
            return {'raw_sha256':None if host_secret else source_hash,'raw_bytes':size,
                    'sha256':safe_hash,'bytes':safe_size,'source_sha256':source_hash,
                    'sanitized':transformed,'view_available':safe_hash is not None}
        finally:
            if pending.exists():pending.unlink()

    def blob(self,data,*,sanitize=True):
        # Original and training-view references are separate; never substitute a
        # redacted/normalized text file for an exact restoration.
        return self.store_stream(io.BytesIO(data))

    def catalog_ref(self,ref,name,role,source=None,*,cause=None,final=False):
        if not ref:return None
        source=self.clean(source or {})
        key=(role,name,ref.get('raw_sha256'),json.dumps(source,sort_keys=True))
        if key in self.catalog_seen:return None
        self.catalog_seen.add(key);self.artifact_count+=1
        ident=f'a{self.artifact_count:07d}'
        filename=re.sub(r'[\x00-\x1f/\\:]','_',Path(name).name)[:180] or 'artifact.bin'
        group=role if re.fullmatch(r'[a-z][a-z0-9_-]{0,40}',role) else 'files'
        relative=Path('artifacts')/group/(ident+'-'+filename);target=self.root/relative
        target.parent.mkdir(mode=0o700,exist_ok=True)
        if ref.get('raw_sha256'):os.link(self.root/'raw-blobs'/ref['raw_sha256'],target)
        entry={'id':ident,'phase_id':self.phase_id,'thread_id':self.thread,'stage':self.stage,
               'cause_event_seq':self.seq if cause is None else cause,'role':role,'name':name,'source':source,
               'original':ref,'path':relative.as_posix() if ref.get('raw_sha256') else None,
               'content_type':mimetypes.guess_type(filename)[0] or 'application/octet-stream',
               'historical':self.historical}
        if final and ref.get('raw_sha256'):
            finalpath=self.root/'final'/(ident+'-'+filename);os.link(target,finalpath)
            entry['final_path']=finalpath.relative_to(self.root).as_posix()
        self.catalog.write((json.dumps(entry,ensure_ascii=False)+'\n').encode());self.catalog.flush()
        self.emit('artifact.created',{'artifact_id':ident,'role':role,'original':ref,'path':entry['path'],'source':source})
        return entry

    def artifact(self,data,name,role,source=None,*,final=False):
        return self.catalog_ref(self.blob(data),name,role,source,final=final)

    def artifact_stream(self,stream,name,role,source=None):
        return self.catalog_ref(self.store_stream(stream),name,role,source)

    def artifact_path(self,root,path,role,source=None):
        root=Path(root).resolve();path=Path(path)
        relative=path.relative_to(root) if path.is_absolute() else path
        if not relative.parts or any(p in ('.','..') for p in relative.parts):raise ValueError('Invalid artifact path')
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            for component in relative.parts[:-1]:
                child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
            child=os.open(relative.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
            with os.fdopen(child,'rb') as stream:
                before=os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):raise ValueError('Not a regular artifact')
                ref=self.store_stream(stream);after=os.fstat(stream.fileno())
            if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                self.gap('artifact_changed_during_capture',str(relative));return None
            return self.catalog_ref(ref,relative.name,role,{'scope':self.register(root),'path':relative.as_posix(),**(source or {})})
        finally:os.close(fd)

    @staticmethod
    def artifact_role(path):
        suffix=Path(path).suffix.lower()
        if suffix=='.pptx':return 'pptx-versions'
        if suffix in ('.png','.jpg','.jpeg','.webp','.gif','.svg'):return 'images'
        if suffix=='.pdf':return 'rendered-pdf'
        if suffix in ('.mp3','.mp4','.mov','.wav','.webm'):return 'media'
        if suffix in ('.md','.txt','.json','.csv','.xlsx','.docx'):return 'documents'
        return 'files'
