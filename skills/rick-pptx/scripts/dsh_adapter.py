"""DSH SDK transport for the unchanged production presentation workflow.

No Codex process, provider proxy, global DSH-home discovery or API fallback.
Notifications are marshalled to the workflow owner thread before callbacks run.
"""
import base64
import copy
import fcntl
import json
import mimetypes
from pathlib import Path
import queue
import threading
import time
import uuid


def native_usage(raw):
    """DSH's inputTokens excludes cache reads/writes (verified SDK event shape)."""
    if 'inputTokens' in raw:
        names=('inputTokens','outputTokens','cacheReadTokens','cacheWriteTokens')
        values={k:raw.get(k,0) for k in names}
        if any(type(v) is not int or v<0 for v in values.values()):return None
        total=values['inputTokens']+values['cacheReadTokens']+values['cacheWriteTokens']
        if raw.get('totalTokens',total+values['outputTokens'])!=total+values['outputTokens']:return None
        return {'input_tokens':total,'cached_input_tokens':values['cacheReadTokens'],
                'output_tokens':values['outputTokens'],'reasoning_output_tokens':0}
    from usage_ledger import normalize_usage
    n=normalize_usage(raw)
    if n:return {'input_tokens':n['inputTokens'],'cached_input_tokens':n['cachedInputTokens'],
                 'output_tokens':n['outputTokens'],'reasoning_output_tokens':n['reasoningTokens']}


class DshServer:
    options = None
    harness_factory = None  # Deterministic offline transport fixtures.

    def __init__(self, *, cwd, config, env=None, on_event=None, on_public=None,
                 tick=None, on_usage=None, secrets=(), **kwargs):
        if not self.options:
            raise ValueError('Explicit DSH runtime options are required')
        self.cwd=Path(cwd).resolve(strict=True);self.config=config
        allowed=('PATH','LANG','LC_ALL','TMPDIR','TMPPREFIX','PPTX_SOFFICE','FONTCONFIG_FILE')
        self.tool_env={k:str(v) for k,v in (env or {}).items() if k in allowed}
        self.on_event=on_event;self.on_public=on_public;self.tick=tick;self.on_usage=on_usage
        self.secrets=tuple(secrets);self.active_turns={};self.completed_turns={};self.usage={}
        self.incoming=queue.Queue();self.harness=None;self.closed=False;self.threads={}
        self.workers={};self.results={};self.received={};self.interrupted=set();self.calls={}
        self.receipts=Path(self.options['records'])/'dsh-message-receipts.json'
        self.receipts.parent.mkdir(parents=True,exist_ok=True)
        try:self.deliveries=json.loads(self.receipts.read_text())
        except FileNotFoundError:self.deliveries={}

    def __enter__(self):
        self._start();return self

    def __exit__(self,*args):self.close()

    def _start(self):
        if self.harness is not None:return
        factory=self.harness_factory
        if factory is None:
            try:from deepseek_harness import DeepSeekHarness
            except ImportError as e:
                raise RuntimeError('Install requirements-dsh.txt in the selected Python environment before using --backend dsh') from e
            factory=DeepSeekHarness
        options={k:self.options[k] for k in ('dsh_home','profile','provider','model','reasoning_effort','max_tokens','dsh_bin','base_url','api_key','patches') if self.options.get(k) is not None}
        options.update(cwd=str(self.cwd),env={**self.tool_env,'PATH':str(Path(self.options['python']).parent)+':'+self.tool_env.get('PATH',__import__('os').environ.get('PATH',''))},
                       initialize_timeout_seconds=45,shutdown_timeout_seconds=5)
        self.harness=factory(**options);self.harness.start()

    def _emit(self,event):
        if self.on_event:
            raw=json.dumps(event,ensure_ascii=False)
            for secret in (*self.secrets,self.options.get('api_key')):
                if secret:raw=raw.replace(json.dumps(secret,ensure_ascii=False)[1:-1],'[redacted]')
            self.on_event(json.loads(raw))

    def _save_delivery(self,identifier,thread,turn,remote):
        if not identifier:return
        from pptx_core.common import atomic_json
        with self.receipts.with_suffix('.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            try:self.deliveries=json.loads(self.receipts.read_text())
            except FileNotFoundError:self.deliveries={}
            self.deliveries[identifier]={'thread_id':thread,'turn_id':turn,'remote_message_id':remote}
            atomic_json(self.receipts,self.deliveries)

    def start_thread(self, **kwargs):
        if kwargs.get('dynamic_tools'):
            raise ValueError('DSH tools come from its explicit SDK profile; Codex dynamic tools are not accepted')
        self._start();ident=str(uuid.uuid4());session=self.harness.start_session(ident)
        actual=session.get_working_directory()
        if Path(actual).resolve()!=self.cwd:raise RuntimeError('DSH did not accept the task working directory')
        self.threads[ident]=session;self._emit({'type':'thread.started','thread_id':ident})
        return {'thread':{'id':ident},'model':self.options['model'],'harness':'dsh'}

    def resume_thread(self,thread_id,**kwargs):
        from durable import RPCError
        self._start()
        try:
            session=self.harness.resume_session(thread_id)
            if Path(session.get_working_directory()).resolve()!=self.cwd:
                raise ValueError('Restored workspace differs from the DSH session permission origin; retain old session and use a fresh file-based context')
        except Exception as e:
            raise RPCError('thread/resume',{'code':-32000,'message':'DSH session restoration unavailable'}) from e
        self.threads[thread_id]=session
        return {'thread':{'id':thread_id},'model':self.options['model'],'harness':'dsh'}

    def start_turn(self,thread_id,text,*,client_message_id=None,output_schema=None,images=None,**kwargs):
        if thread_id in self.active_turns:raise RuntimeError('DSH session already has an owned run')
        turn=str(uuid.uuid4());key=(thread_id,turn);ready=threading.Event()
        if output_schema:
            text+='\nFINAL RESPONSE CONTRACT: return one bare JSON object matching this schema after tool work. '+json.dumps(output_schema,ensure_ascii=False)
        blocks=[{'type':'text','text':text}]
        from progress import read_scoped
        for value in images or ():
            path=Path(value);relative=path.relative_to(self.cwd) if path.is_absolute() else path
            data=read_scoped(self.cwd,relative,20*1024*1024)
            mime=mimetypes.guess_type(str(path))[0]
            if mime not in ('image/png','image/jpeg','image/webp'):raise ValueError('Unsupported DSH image input')
            blocks.append({'type':'image','mimeType':mime,'data':base64.b64encode(data).decode()})
        self.active_turns[thread_id]=turn;self.received[key]=ready
        def notify(notification):self.incoming.put(('notification',key,notification))
        def run():
            try:self.incoming.put(('result',key,self.threads[thread_id].run(blocks,on_notification=notify)))
            except BaseException as e:self.incoming.put(('error',key,e))
        worker=threading.Thread(target=run,name='pptx-dsh-'+turn,daemon=True);self.workers[key]=worker;worker.start()
        deadline=time.monotonic()+60
        while not ready.is_set():
            self.pump(.05)
            if key in self.completed_turns:
                if self.completed_turns[key]['status']!='completed':
                    raise RuntimeError('DSH run failed before accepting its input: '+str(self.completed_turns[key].get('reason','unknown native failure')))
                break
            if time.monotonic()>deadline:raise TimeoutError('No durable DSH inbox receipt; task preserved without acknowledgement')
        remote=self.results.get(('remote',key))
        if not remote:raise RuntimeError('DSH did not confirm input persistence')
        self._save_delivery(client_message_id,thread_id,turn,remote)
        return {'id':turn,'status':'completed' if key in self.completed_turns else 'inProgress','dsh_message_id':remote}

    def steer(self,thread_id,expected_turn_id,text,*,client_message_id=None,**kwargs):
        from durable import RPCError
        if self.active_turns.get(thread_id)!=expected_turn_id:
            raise RPCError('turn/steer',{'code':-32602,'message':'No active DSH run'})
        remote=self.harness.client.session_prompt(thread_id,[{'type':'text','text':text}])
        if not isinstance(remote,str) or not remote:raise RuntimeError('Missing durable DSH prompt receipt')
        self._save_delivery(client_message_id,thread_id,expected_turn_id,remote)
        return {'turnId':expected_turn_id,'dsh_message_id':remote}

    def interrupt(self,thread_id,turn_id):
        if self.active_turns.get(thread_id)!=turn_id:return {}
        # The SDK has runtime shutdown, not a per-session cancel RPC. This
        # adapter owns its process; closing it cancels only this phase runtime.
        key=(thread_id,turn_id);self.interrupted.add(key)
        harness=self.harness;self.harness=None
        if harness:harness.close()
        worker=self.workers.get(key)
        if worker:worker.join(timeout=6)
        if worker and worker.is_alive():raise RuntimeError('DSH shutdown has not confirmed cancellation')
        self._terminal(key,'interrupted')
        return {'cancelled_runtime':True}

    def _terminal(self,key,status,reason=None):
        if key in self.completed_turns:return
        thread,turn=key
        if self.active_turns.get(thread)==turn:self.active_turns.pop(thread,None)
        self.completed_turns[key]={'id':turn,'status':status,**({'reason':reason} if reason else {})}
        if self.received[key].is_set():
            self._emit({'type':'turn.completed' if status=='completed' else 'turn.'+status,
                        'thread_id':thread,'turn_id':turn,'status':status,'usage':self.usage.get(key)})
        elif status!='completed':
            self._emit({'type':'error','thread_id':thread,'message':'DSH input was not accepted','reason':reason})

    def _notification(self,key,n):
        thread,turn=key
        if n.method!='session.event' or n.payload.get('sessionId')!=thread:return
        event=n.payload.get('event') or {};kind=event.get('type');data=event.get('data') or {}
        if kind=='agent/inbox/spliced':
            inserted=data.get('inserted') or []
            if inserted and inserted[0].get('id'):
                if not self.received[key].is_set():
                    self.results[('remote',key)]=inserted[0]['id'];self.received[key].set()
                    self._emit({'type':'turn.started','thread_id':thread,'turn_id':turn})
        elif kind=='tool/call':
            ident=str(data.get('callId') or uuid.uuid4());self.calls[ident]=data
            self._emit({'type':'item.started','thread_id':thread,'turn_id':turn,
                        'item':{'id':ident,'type':'mcp_tool_call','server':'dsh','tool':data.get('name'),'arguments':data.get('arguments'),'status':'in_progress'}})
        elif kind=='tool/result':
            message=data.get('message') or {};ident=(message.get('source') or {}).get('callId')
            if ident:
                call=self.calls.pop(ident,{})
                self._emit({'type':'item.completed','thread_id':thread,'turn_id':turn,
                            'item':{'id':ident,'type':'mcp_tool_call','server':'dsh','tool':call.get('name'),
                                    'arguments':call.get('arguments'),'result':message.get('content'),'error':data.get('error'),'status':'completed'}})
        elif kind=='assistant/message':
            message=data.get('message') or data
            text=''.join(str(b.get('text','')) for b in message.get('content',[]) if b.get('type')=='text')
            for secret in (*self.secrets,self.options.get('api_key')):
                if secret:text=text.replace(secret,'[redacted]')
            if text and self.on_public:self.on_public({'type':'assistant.message','id':str(message.get('id') or uuid.uuid4()),'body':text,'complete':True})
            # Only explicitly reported native usage is counted; absent fields
            # stay unknown, never inferred from text or a default model price.
            raw=message.get('usage') or data.get('usage')
            if isinstance(raw,dict):
                normalized=native_usage(raw)
                if normalized:
                    self.usage[key]={k:self.usage.get(key,{}).get(k,0)+v for k,v in normalized.items()}
                if self.on_usage:self.on_usage({'thread_id':thread,'turn_id':turn,'usage':self.usage.get(key),
                    'raw_native_usage':raw,'reasoning_breakdown':'not separately reported' if 'inputTokens' in raw else 'provider fields',
                    'source':'dsh-native'})

        elif kind=='turn/end':
            reason=data.get('reason') or {};error=reason.get('error')
            if isinstance(error,dict):
                safe={k:error[k] for k in ('code','status','message') if k in error}
                raw=json.dumps(safe,ensure_ascii=False)
                for secret in (*self.secrets,self.options.get('api_key')):
                    if secret:raw=raw.replace(secret,'[redacted]')
                self.results[('failure',key)]=raw
                self._emit({'type':'error','thread_id':thread,'turn_id':turn,'message':'DSH native model/tool failure','error':json.loads(raw)})

    def pump(self,timeout=.1):
        if self.tick:self.tick()
        try:kind,key,value=self.incoming.get(timeout=timeout)
        except queue.Empty:return
        if kind=='notification':self._notification(key,value)
        elif kind=='result':
            if key in self.interrupted:return
            self.results[key]=value.final_response
            status='completed' if value.finish_reason=='completed' else 'failed'
            self._terminal(key,status,self.results.get(('failure',key),value.finish_reason))
        elif kind=='error':
            if key not in self.interrupted:self._terminal(key,'failed',type(value).__name__+': '+str(value))

    def wait_turn(self,thread_id,turn_id,*,timeout=1200):
        key=(thread_id,turn_id);deadline=time.monotonic()+timeout
        while key not in self.completed_turns:
            if time.monotonic()>deadline:raise TimeoutError('DSH run deadline exceeded')
            self.pump(.1)
        return copy.deepcopy(self.completed_turns[key])

    def result_text(self,thread_id,turn_id):return self.results.get((thread_id,turn_id),'')

    def find_client_message(self,thread_id,message_id,**kwargs):
        try:current=json.loads(self.receipts.read_text())
        except FileNotFoundError:current={}
        row=current.get(message_id)
        return row if row and row['thread_id']==thread_id else None

    def deliver(self,*args,**kwargs):
        from durable import AppServer
        return AppServer.deliver(self,*args,**kwargs)

    def reconcile_delivery(self,*args,**kwargs):
        from durable import AppServer
        return AppServer.reconcile_delivery(self,*args,**kwargs)

    def close(self):
        if self.closed:return
        self.closed=True
        for thread,turn in list(self.active_turns.items()):self.interrupt(thread,turn)
        if self.harness:self.harness.close();self.harness=None
