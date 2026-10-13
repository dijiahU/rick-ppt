"""Authenticated loopback Responses adapter; upstream key stays in host memory."""
import contextlib,hashlib,json,math,re,secrets,subprocess,threading,time,urllib.parse
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from model_backend import overrides,KEY_ENV

MAX_BODY=16*1024*1024
def curl_reply(output):
 """Parse host curl status/allowlisted ID trailers; legacy mocks lack IDs."""
 try:
  raw,status,request_id,alternative_id=output.rsplit('\n',3)
  return raw,int(status),request_id or alternative_id
 except (ValueError,TypeError):
  raw,status=output.rsplit('\n',1)
  return raw,int(status),None

class ChatProxy:
 def __init__(self,profile):
  self.profile=profile;self.token=secrets.token_urlsafe(32);self.calls=[];self.server=None;self.thread=None
  self.stopping=threading.Event();self.active=set();self.active_lock=threading.Lock()
  self.failed_requests=OrderedDict();self.request_lock=threading.RLock()
 def _marker(self,value,limit=200):
  return value if (isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,'+str(limit)+r'}',value)
                  and self.profile['api_key'] not in value and self.token not in value) else None
 def _remember_failure(self,digest,status,message):
  self.failed_requests[digest]=(status,message);self.failed_requests.move_to_end(digest)
  while len(self.failed_requests)>128:self.failed_requests.popitem(last=False)
 def _digest(self,body):return hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 def abort_delivery(self,body):
  # A broken local connection after generation leaves tool delivery uncertain.
  # Refuse repeats rather than generate/replay executable calls again.
  with self.request_lock:self._remember_failure(self._digest(body),502,'Configured API result delivery was interrupted; recover the task before retrying')
 def __enter__(self):
  outer=self
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def answer(self,status,value):
    body=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   def do_POST(self):
    if self.path!='/v1/responses':return self.answer(404,{'error':{'message':'Unsupported adapter route','type':'invalid_request_error'}})
    if not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+outer.token):return self.answer(401,{'error':{'message':'Invalid local adapter token','type':'authentication_error'}})
    try:
     length=int(self.headers.get('Content-Length','0'))
     if not 0<length<=MAX_BODY:raise ValueError('Request body size limit')
     if self.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Compressed requests are unsupported')
     body=json.loads(self.rfile.read(length));result=outer.complete(body)
     if body.get('stream'):
      from chat_protocol import response_sse_events
      events=response_sse_events(result)
      encoded=''.join('event: '+e['type']+'\ndata: '+json.dumps(e,ensure_ascii=False)+'\n\n' for e in events).encode()
      self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-cache');self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)
     else:self.answer(200,result)
    except UpstreamError as error:
     # The host owns bounded retries. Returning a transient 5xx here causes an
     # app-server client to repeat the whole request outside that budget.
     self.answer(400 if error.terminal else error.status,{'error':{'message':str(error),'type':'invalid_request_error' if error.terminal else 'upstream_error','code':'pptx_upstream_failure'}})
    except (ValueError,KeyError,TypeError) as error:
     outer.calls.append({'ok':False,'error':type(error).__name__,'detail':str(error)[:300]})
     self.answer(400,{'error':{'message':'Unsupported request: '+str(error)[:300],'type':'invalid_request_error'}})
    except (BrokenPipeError,ConnectionResetError):
     if isinstance(locals().get('body'),dict):outer.abort_delivery(body)
    except Exception as error:
     outer.calls.append({'ok':False,'error':type(error).__name__})
     self.answer(400,{'error':{'message':'Local adapter failed','type':'invalid_request_error','code':'pptx_adapter_failure'}})
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.url=f'http://127.0.0.1:{self.server.server_port}/v1'
  return self
 def __exit__(self,*args):
  self.stopping.set()
  with self.active_lock:processes=list(self.active)
  for process in processes:
   if process.poll() is None:process.kill()
  self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
 def _upstream(self,command,*,input,text,capture_output,timeout):
  process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  with self.active_lock:
   self.active.add(process)
   if self.stopping.is_set():process.kill()
  try:
   try:
    stdout,stderr=process.communicate(input=input,timeout=timeout)
    return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
   except subprocess.TimeoutExpired:
    process.kill();stdout,stderr=process.communicate()
    return subprocess.CompletedProcess(command,28,stdout,stderr)
  finally:
   with self.active_lock:self.active.discard(process)
 def complete(self,body):
  if body.get('model')!=self.profile['model']:raise ValueError('Model does not match selected profile')
  digest=self._digest(body)
  with self.request_lock:
   if digest in self.failed_requests:
    status,message=self.failed_requests[digest];self.calls.append({'ok':False,'cache_hit':True,'terminal':True,'protocol':'chat_completions'})
    raise UpstreamError(status,message)
   try:return self._complete(body)
   except UpstreamError as error:
    self._remember_failure(digest,error.status,str(error));raise
 def _complete(self,body):
  from chat_protocol import responses_to_chat,chat_to_response
  if body.get('model')!=self.profile['model']:raise ValueError('Model does not match selected profile')
  request,mapping=responses_to_chat(body)
  request['model']=self.profile['model'];request['stream']=False
  request['enable_thinking']=bool(self.profile.get('reasoning_effort'))
  if self.profile.get('reasoning_effort'):request['reasoning_effort']=self.profile['reasoning_effort']
  if self.profile.get('service_tier') is not None:request['service_tier']='priority' if self.profile['service_tier']=='fast' else self.profile['service_tier']
  request.setdefault('max_tokens',8192)
  if type(request['max_tokens']) is not int or request['max_tokens']<=0:raise ValueError('Invalid output token limit')
  config='header = '+json.dumps('Authorization: Bearer '+self.profile['api_key'])+'\nheader = "Content-Type: application/json"\n'+ 'data = '+json.dumps(json.dumps(request))+'\n'
  started=time.monotonic()
  request_timeout=600 if self.profile.get('reasoning_effort') else 180
  transport_retries=0;upstream_requests=0
  for attempt in range(1,4):
   deadline=time.monotonic()+request_timeout
   while True:
    if self.stopping.is_set():raise UpstreamError(499,'Model request interrupted')
    remaining=max(1,math.ceil(deadline-time.monotonic()))
    upstream_requests+=1
    process=self._upstream(['curl','--disable','--config','-','--silent','--show-error','--max-time',str(remaining),'--max-filesize',str(MAX_BODY),'--write-out','\n%{http_code}\n%header{x-request-id}\n%header{request-id}',self.profile['base_url']+'/chat/completions'],input=config,text=True,capture_output=True,timeout=remaining+10)
    if upstream_requests<3 and transport_retries==0 and process.returncode in (7,28,35,52,55,56) and process.stdout.strip() in ('','000') and time.monotonic()<deadline and not self.stopping.is_set():
     transport_retries+=1;self.calls.append({'ok':False,'attempt':attempt,'transport_code':process.returncode,'retry_delay_seconds':0});continue
    break
   if process.returncode:
    self.calls.append({'ok':False,'attempt':attempt,'transport_code':process.returncode})
    raise UpstreamError(502,'Upstream transport failed (curl '+str(process.returncode)+')')
   raw,status,request_id=curl_reply(process.stdout)
   if status==200:break
   delay=(30 if attempt==1 else 60) if status==429 and attempt<3 and upstream_requests<3 else 0
   self.calls.append({'ok':False,'attempt':attempt,'upstream_status':status,'retry_delay_seconds':delay})
   if not delay:raise UpstreamError(status if 400<=status<600 else 502,'Provider rejected request (HTTP '+str(status)+')')
   if self.stopping.wait(delay):raise UpstreamError(499,'Configured API request interrupted')
  reply=json.loads(raw)
  receipt={'ok':False,'http_ok':True,'protocol':'chat_completions','endpoint':'/chat/completions','attempts':attempt,
           'upstream_status':status,'seconds':round(time.monotonic()-started,3),'tools':len(request.get('tools',[])),
           'requested_model':self.profile['model'],'response_bytes':len(raw.encode())}
  self.calls.append(receipt)
  for key,value in (('request_id',request_id),('response_model',reply.get('model')),
                    ('response_error_type',(reply.get('error') or {}).get('type')),
                    ('response_error_code',(reply.get('error') or {}).get('code')),
                    ('finish_reason',(reply.get('choices') or [{}])[0].get('finish_reason'))):
   if self._marker(value) is not None:receipt[key]=value
  if isinstance(reply.get('usage'),dict):receipt['usage']=safe_api_calls([{'usage':reply['usage']}])[0]['usage']
  if self.profile.get('service_tier') is not None:receipt['requested_service_tier']=request['service_tier']
  if reply.get('service_tier') in ('auto','default','fast','priority'):receipt['actual_service_tier']=reply['service_tier']
  if reply.get('model')!=self.profile['model'] or reply.get('error'):
   raise UpstreamError(502,'Configured API returned an invalid completion')
  if self.profile['api_key'] in json.dumps(reply,ensure_ascii=False) or self.token in json.dumps(reply,ensure_ascii=False):
   raise UpstreamError(502,'Configured API returned protected credential material')
  response=chat_to_response(reply,mapping,model=self.profile['model']);receipt['response_status']=response['status']
  receipt['output_types']=[x.get('type') for x in response.get('output',[])]
  if response['status']!='completed':raise UpstreamError(502,'Configured API returned an incomplete completion')
  receipt['ok']=True
  return response

def safe_api_calls(calls,*,secrets=()):
 """Allowlisted metadata snapshot: never persist upstream text or credentials."""
 result=[]
 def number(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
 token_keys=('prompt_tokens','completion_tokens','total_tokens','input_tokens','output_tokens')
 for call in calls:
  if not isinstance(call,dict):continue
  hidden=tuple(value for value in (*secrets,call.get('api_key'),call.get('token'),call.get('authorization')) if isinstance(value,str) and value)
  clean={}
  for key in ('ok','http_ok','stream','cache_hit','terminal'):
   if type(call.get(key)) is bool:clean[key]=call[key]
  for key in ('attempt','attempts','upstream_status','transport_code','retry_delay_seconds','seconds','tools','response_bytes'):
   if number(call.get(key)):clean[key]=call[key]
  for key in ('protocol','endpoint','requested_model','response_model','response_status','response_error_code','response_error_type','incomplete_reason','request_id','finish_reason'):
   value=call.get(key)
   if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,200}',value) and not any(secret in value for secret in hidden):clean[key]=value
  if isinstance(call.get('output_types'),list):
   clean['output_types']=[kind for kind in call['output_types'] if kind in ('message','function_call','custom_tool_call','reasoning')]
  for key in ('requested_service_tier','actual_service_tier'):
   if call.get(key) in ('auto','default','fast','priority'):clean[key]=call[key]
  usage=call.get('usage')
  if isinstance(usage,dict):
   clean['usage']={key:usage[key] for key in token_keys if number(usage.get(key))}
   for key in ('prompt_tokens_details','completion_tokens_details','input_tokens_details','output_tokens_details'):
    if isinstance(usage.get(key),dict):
     clean['usage'][key]={k:usage[key][k] for k in ('cached_tokens','reasoning_tokens','audio_tokens','accepted_prediction_tokens','rejected_prediction_tokens') if number(usage[key].get(k))}
  if clean:result.append(clean)
 return result

class UpstreamError(RuntimeError):
 def __init__(self,status,message,*,terminal=True):super().__init__(message);self.status=status;self.terminal=terminal

@contextlib.contextmanager
def provider_session(profile):
 if profile:
  if profile.get('wire_api','responses')=='chat_completions':factory=ChatProxy
  else:
   from responses_proxy import ResponsesProxy
   factory=ResponsesProxy
  with factory(profile) as proxy:
   local={**profile,'base_url':proxy.url,'wire_api':'responses','api_key':proxy.token}
   yield overrides(local),{KEY_ENV:proxy.token},proxy.calls
 else:yield overrides(profile),None,[]
