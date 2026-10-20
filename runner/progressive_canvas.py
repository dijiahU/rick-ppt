"""Publish finished native pages from already-rendered, host-frozen input bytes."""
import hashlib,json,threading,time,uuid
from pathlib import Path
from canvas_snapshot import native_pages
from progress import read_scoped
from user_pages import load,graft,fingerprint

class ProgressiveCanvas:
    def __init__(self,cfg,task,root,send):
        self.cfg,self.task,self.root,self.send=cfg,task,Path(root),send
        self.pending={};self.ready={};self.lock=threading.Lock();self.thread=None;self.last_error=None;self.next_poll=0
    def offer(self,page,source_sha,png):
        if not isinstance(source_sha,str) or len(source_sha)!=64:return
        with self.lock:self.pending[page]=(source_sha,png)
        self.poll()
    def poll(self):
        with self.lock:
            if self.thread and self.thread.is_alive() or not self.pending or time.monotonic()<self.next_poll:return
            self.thread=threading.Thread(target=self.synchronize,name='pptx-progressive-canvas',daemon=True);self.thread.start()
    def synchronize(self):
        try:
            with self.lock:page=next(iter(self.pending));source_sha,png=self.pending[page]
            source=read_scoped(self.root,Path('raw-blobs')/source_sha,30*1024*1024)
            if hashlib.sha256(source).hexdigest()!=source_sha:raise ValueError('Progress render input differs')
            self.ready[page]={'content':fingerprint(source,page),'png':png}
            overlays,locks=load(self.cfg,self.task,self.send,images=True);artifact=graft(source,overlays);pages=native_pages(artifact);images={};protected={r['page']:r for r in locks}
            for p in pages:
                n=p['number'];p['contentSha256']=fingerprint(artifact,n);record=self.ready.get(n)
                if n in protected:images[n]=protected[n]['png']
                elif record and record['content']==p['contentSha256']:images[n]=record['png']
                p['imageSha256']=hashlib.sha256(images[n]).hexdigest() if n in images else '0'*64
            if not images:return
            sha=hashlib.sha256(artifact).hexdigest();snapshot={'schema':'rickppt-canvas/v1','sha256':sha,'versionId':str(uuid.uuid5(uuid.NAMESPACE_URL,'rickppt-canvas:'+sha)),'createdAt':int(time.time()*1000),'pages':pages,'readyPages':sorted(images)}
            base=f'/api/worker/{self.task["id"]}/canvas?sha256={sha}'
            self.send(self.cfg,base+'&action=artifact',artifact,self.task['lease'])
            from concurrent.futures import ThreadPoolExecutor
            def upload(item):
                n,data=item;return self.send(self.cfg,base+f'&action=page&page={n}',data,self.task['lease'])
            with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(upload,images.items()))
            # Get the same head used by lock loading; CAS prevents a newly saved user page being overwritten.
            # load() retains this host-only parent receipt on its lock list wrapper.
            parent=getattr(locks,'head_sha','')
            result=self.send(self.cfg,base+'&action=manifest&progressive=1&parent='+parent,json.dumps(snapshot,separators=(',',':'),ensure_ascii=False).encode(),self.task['lease'])
            if result.get('ok') is not True:raise ValueError('Progress canvas publication was not acknowledged')
            with self.lock:
                if self.pending.get(page,(None,None))[0]==source_sha:self.pending.pop(page,None)
            self.last_error=None
        except Exception as error:self.last_error=type(error).__name__;self.next_poll=time.monotonic()+3
