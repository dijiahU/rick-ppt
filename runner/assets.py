"""Import only images produced by the current trusted CLI thread into its job."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
from trajectory import record as capture

class AssetImporter:
    def __init__(self,job,generated_root=None,trajectory=None):
        self.job=job
        self.generated_root=generated_root or Path.home()/'.codex/generated_images'
        self.thread=None;self.offset=0;self.imported={}
        self.trajectory=trajectory;self.archived=set()

    def consume(self,event):
        # Source must be the host-owned CLI log, never a task-supplied manifest.
        if self.thread is None and event.get('type')=='thread.started':
            value=event.get('thread_id')
            try:
                if str(uuid.UUID(value))==value:self.thread=value
            except (ValueError,TypeError,AttributeError):pass

    def poll(self,log):
        log.seek(self.offset)
        for _ in range(100):
            start=log.tell();line=log.readline(2*1024*1024)
            if not line or not line.endswith(b'\n'):log.seek(start);break
            self.offset=log.tell()
            try:self.consume(json.loads(line))
            except (ValueError,TypeError,AttributeError):pass
        if self.thread:self.import_images()

    def import_images(self):
        try:base=os.open(self.generated_root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        except OSError:return
        try:
            try:source=os.open(self.thread,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=base)
            except OSError:return
            try:self._copy(source)
            finally:os.close(source)
        finally:os.close(base)

    def _copy(self,source):
        # Bound imports independently of optional model decisions. No user-supplied paths.
        for name in sorted(os.listdir(source)):
            if name in self.imported and (self.trajectory is None or name in self.archived):continue
            if not re.fullmatch(r'exec-[0-9a-f-]{36}\.png',name):continue
            try:
                fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=source)
                with os.fdopen(fd,'rb') as stream:
                    info=os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode):continue
                    # Archive complete trusted-thread outputs even when the PPT
                    # import quota is full; that quota is not a recording quota.
                    header=stream.read(8)
                    if info.st_size<32:continue
                    stream.seek(-12,os.SEEK_END);tail=stream.read(12);stream.seek(0)
                    if header!=b'\x89PNG\r\n\x1a\n' or tail!=b'\x00\x00\x00\x00IEND\xaeB`\x82':continue
                    if self.trajectory is not None and name not in self.archived:
                        archived=capture(self.trajectory,'artifact_stream',stream,name,'generated-images',{'producer_thread_id':self.thread,'provider_file':name,'selected_for_import':name in self.imported or len(self.imported)<12})
                        if archived:self.archived.add(name)
                    if self.job is None or name in self.imported or len(self.imported)>=12 or info.st_size>20*1024*1024:continue
                    stream.seek(0)
                    data=stream.read(20*1024*1024+1)
                if not self.valid_png(data):continue
                destination='generated-'+name
                record={'file':destination,'sha256':hashlib.sha256(data).hexdigest(),'source':'built-in image generation'}
                self._publish(destination,data,{**self.imported,name:record})
                self.imported[name]=record
            except OSError:continue

    @staticmethod
    def valid_png(data):
        if len(data)<32 or len(data)>20*1024*1024 or data[:8]!=b'\x89PNG\r\n\x1a\n' or data[-12:]!=b'\x00\x00\x00\x00IEND\xaeB`\x82':return False
        width=int.from_bytes(data[16:20],'big');height=int.from_bytes(data[20:24],'big')
        return 0<width<=8192 and 0<height<=8192 and width*height<=33554432

    def _publish(self,name,data,records):
        root=os.open(self.job,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            dest=os.open('assets',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root)
            try:
                for target,body in [(name,data),('index.json',json.dumps({'images':list(records.values())},indent=2).encode())]:
                    pending='host-'+uuid.uuid4().hex+'.tmp'
                    fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=dest)
                    with os.fdopen(fd,'wb') as stream:stream.write(body)
                    os.replace(pending,target,src_dir_fd=dest,dst_dir_fd=dest)
            finally:os.close(dest)
        finally:os.close(root)
