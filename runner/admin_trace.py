"""Administrator-only operational records; never publish private reasoning events."""
import hashlib
import json
import os
from pathlib import Path
import re
import time

KINDS={'phase','command','tool','search','file','media','note','review','error'}
MAX_EVENTS=20000
MAX_BYTES=64*1024*1024


class AdminTrace:
    def __init__(self,cfg,task,send,records):
        self.cfg,self.task,self.send=cfg,task,send
        self.seq=0;self.chunk=1;self.pending=[];self.inflight=None;self.last_send=0
        self.total_bytes=0;self.limited=False;self.stage='setup';self.offset=0
        self.roots={};self.seen={}
        self.path=Path(records)/(task['id']+'-admin-trace-'+str(int(time.time()*1000))+'.jsonl')
        self.fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)

    def clean(self,value,limit):
        if not isinstance(value,str):value=json.dumps(value,ensure_ascii=False)
        # Known bridge credentials never enter the stored or transmitted record.
        secret=self.cfg.get('token')
        if secret:value=value.replace(secret,'[redacted]')
        value=re.sub(r'(?is)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----','[private key redacted]',value)
        value=re.sub(r'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/_.=:-]+','[authorization redacted]',value)
        value=re.sub(r'(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret|authorization)\b["\x27]?\s*[:=]\s*)(?:"[^"\n]*"|\x27[^\x27\n]*\x27|[^\s,;}]+)',r'\1[redacted]',value)
        value=re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{15,}|github_pat_[A-Za-z0-9_]{15,})','[credential redacted]',value)
        for path,label in sorted(self.roots.items(),key=lambda p:-len(p[0])):value=value.replace(path,label)
        value=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',value)
        value=''.join(ch for ch in value if ch in '\n\r\t' or ord(ch)>=32)
        # The receiving JavaScript API bounds UTF-16 code units, not Python
        # code points. Never let astral symbols make an otherwise valid batch
        # retry forever, and never split a surrogate pair at the boundary.
        encoded=value.encode('utf-16-le',errors='replace')
        truncated=len(encoded)>limit*2
        return encoded[:limit*2].decode('utf-16-le',errors='ignore'),truncated

    def emit(self,kind,label,*,state='completed',command=None,output=None,detail=None,item_id=None,exit_code=None):
        if self.limited or kind not in KINDS:return
        if self.seq>=MAX_EVENTS or self.total_bytes>=MAX_BYTES:
            kind,label,state='error','Record limit reached','failed'
            command=output=None;detail='Further details remain in the local execution log; this online record is incomplete.'
            self.limited=True
        self.seq+=1
        event={'seq':self.seq,'at':int(time.time()*1000),'stage':self.stage,'kind':kind,'label':self.clean(label,240)[0],'state':state}
        truncated=False
        for key,value,limit in [('command',command,32000),('output',output,100000),('detail',detail,16000),('itemId',item_id,100)]:
            if value is not None:
                event[key],cut=self.clean(value,limit);truncated|=cut
        if type(exit_code) is int:event['exitCode']=exit_code
        if truncated:event['truncated']=True
        line=(json.dumps(event,ensure_ascii=False)+'\n').encode()
        os.write(self.fd,line);self.total_bytes+=len(line);self.pending.append(event)

    def begin(self,stage,root):
        self.stage=stage;self.offset=0;self.roots[str(root)]='$WORKSPACE'
        self.emit('phase',stage,state='started')

    def consume(self,event):
        if not isinstance(event,dict):return
        event_type=event.get('type')
        if event_type in ('error','turn.failed'):
            error=event.get('error') or event.get('message') or 'Execution failed'
            self.emit('error','Execution error',state='failed',detail=error);return
        if event_type not in ('item.started','item.updated','item.completed'):return
        item=event.get('item')
        if not isinstance(item,dict):return
        kind=item.get('type')
        # Allowlist: reasoning, encrypted content and unknown event types never leave the host.
        if kind not in ('command_execution','web_search','file_change','agent_message','mcp_tool_call','image_generation','image_generation_call'):return
        state='completed' if event_type=='item.completed' else 'started'
        if item.get('status')=='failed' or item.get('exit_code') not in (None,0):state='failed'
        ident=str(item.get('id',''))[:100]
        fingerprint=hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()
        key=(self.stage,ident,event_type)
        if self.seen.get(key)==fingerprint:return
        self.seen[key]=fingerprint
        if kind=='command_execution':
            self.emit('command','Shell command',state=state,command=item.get('command'),output=item.get('aggregated_output'),item_id=ident,exit_code=item.get('exit_code'))
        elif kind=='agent_message':
            if state=='completed':self.emit('note','Assistant update',detail=item.get('text',''),item_id=ident)
        elif kind=='web_search':
            action=item.get('action') or {}
            detail={key:action[key] for key in ('type','query','queries','url','urls','pattern') if key in action} if isinstance(action,dict) else {}
            self.emit('search','Web search / source',state=state,detail=detail,item_id=ident)
        elif kind=='file_change':
            changes=[{k:c[k] for k in ('path','kind','diff') if k in c} for c in item.get('changes',[]) if isinstance(c,dict)]
            self.emit('file','File changes',state=state,detail=changes,item_id=ident)
        elif kind=='mcp_tool_call':
            result=item.get('result') or {}
            text=[c.get('text','') for c in result.get('content',[]) if isinstance(c,dict) and c.get('type')=='text'] if isinstance(result,dict) else []
            self.emit('tool',str(item.get('server',''))+'/'+str(item.get('tool','')),state=state,detail=item.get('arguments'),output='\n'.join(text),item_id=ident)
        else:self.emit('media','Image generation',state=state,item_id=ident)

    def poll(self,stream):
        stream.seek(self.offset)
        for _ in range(100):
            start=stream.tell();line=stream.readline(2*1024*1024)
            if not line:break
            if not line.endswith(b'\n'):
                if len(line)<2*1024*1024:break
                while line and not line.endswith(b'\n'):line=stream.readline(2*1024*1024)
                self.offset=stream.tell();self.emit('error','Oversized event omitted',detail='A local event exceeded the capture limit.');continue
            self.offset=stream.tell()
            try:self.consume(json.loads(line))
            except (ValueError,TypeError,AttributeError):continue
        self.flush()

    def flush(self,force=False):
        if not force and time.monotonic()-self.last_send<3:return
        self.last_send=time.monotonic()
        for _ in range(8 if force else 1):
            if not self.inflight:
                if not self.pending:return
                batch=[];size=0
                for event in self.pending[:50]:
                    length=len(json.dumps(event,ensure_ascii=False).encode())
                    if batch and size+length>700000:break
                    batch.append(event);size+=length
                self.inflight={'version':1,'chunk':self.chunk,'events':batch}
            try:
                result=self.send(self.cfg,f'/api/worker/{self.task["id"]}?action=trace',json.dumps(self.inflight,ensure_ascii=False).encode(),self.task['lease'])
                if result.get('ok') is not True:return
            except Exception:return  # Trace transport must not fail presentation generation.
            del self.pending[:len(self.inflight['events'])];self.chunk+=1;self.inflight=None

    def close(self):
        try:self.flush(force=True)
        finally:os.close(self.fd)
