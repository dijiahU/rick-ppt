"""Authenticated loopback Responses adapter; upstream key stays in host memory."""
import contextlib,json,math,secrets,subprocess,threading,time,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from model_backend import overrides,KEY_ENV

MAX_BODY=16*1024*1024
class ChatProxy:
 def __init__(self,profile):
  self.profile=profile;self.token=secrets.token_urlsafe(32);self.calls=[];self.server=None;self.thread=None
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
    except UpstreamError as error:self.answer(error.status,{'error':{'message':str(error),'type':'upstream_error'}})
    except (ValueError,KeyError,TypeError) as error:
     outer.calls.append({'ok':False,'error':type(error).__name__,'detail':str(error)[:300]})
     self.answer(400,{'error':{'message':'Unsupported request: '+str(error)[:300],'type':'invalid_request_error'}})
    except (BrokenPipeError,ConnectionResetError):pass
    except Exception as error:
     outer.calls.append({'ok':False,'error':type(error).__name__})
     self.answer(502,{'error':{'message':'Local adapter failed','type':'adapter_error'}})
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.url=f'http://127.0.0.1:{self.server.server_port}/v1'
  return self
 def __exit__(self,*args):
  self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
 def complete(self,body):
  from chat_protocol import responses_to_chat,chat_to_response
  if body.get('model')!=self.profile['model']:raise ValueError('Model does not match selected profile')
  request,mapping=responses_to_chat(body)
  request['model']=self.profile['model'];request['stream']=False
  request['enable_thinking']=False
  request['max_tokens']=min(int(request.get('max_tokens',8192)),16384)
  config='header = '+json.dumps('Authorization: Bearer '+self.profile['api_key'])+'\nheader = "Content-Type: application/json"\n'+ 'data = '+json.dumps(json.dumps(request))+'\n'
  started=time.monotonic()
  for attempt in range(1,4):
   process=subprocess.run(['curl','--disable','--config','-','--silent','--show-error','--max-time','180','--max-filesize',str(MAX_BODY),'--write-out','\n%{http_code}',self.profile['base_url']+'/chat/completions'],input=config,text=True,capture_output=True,timeout=190)
   if process.returncode:
    self.calls.append({'ok':False,'attempt':attempt,'transport_code':process.returncode})
    raise UpstreamError(502,'Upstream transport failed (curl '+str(process.returncode)+')')
   raw,status=process.stdout.rsplit('\n',1);status=int(status)
   if status==200:break
   delay=(30 if attempt==1 else 60) if status==429 and attempt<3 else 0
   self.calls.append({'ok':False,'attempt':attempt,'upstream_status':status,'retry_delay_seconds':delay})
   if not delay:raise UpstreamError(status if 400<=status<600 else 502,'Provider rejected request (HTTP '+str(status)+')')
   time.sleep(delay)
  reply=json.loads(raw);response=chat_to_response(reply,mapping,model=self.profile['model'])
  self.calls.append({'ok':True,'attempts':attempt,'upstream_status':status,'seconds':round(time.monotonic()-started,3),'usage':reply.get('usage'),
   'tools':len(request.get('tools',[])),'output_types':[x.get('type') for x in response.get('output',[])]})
  return response

def safe_api_calls(calls):
 """Allowlisted metadata snapshot: never persist upstream text or credentials."""
 result=[]
 def number(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
 token_keys=('prompt_tokens','completion_tokens','total_tokens','input_tokens','output_tokens')
 for call in calls:
  if not isinstance(call,dict):continue
  clean={}
  if type(call.get('ok')) is bool:clean['ok']=call['ok']
  for key in ('attempt','attempts','upstream_status','transport_code','retry_delay_seconds','seconds','tools'):
   if number(call.get(key)):clean[key]=call[key]
  if isinstance(call.get('output_types'),list):
   clean['output_types']=[kind for kind in call['output_types'] if kind in ('message','function_call','custom_tool_call','reasoning')]
  usage=call.get('usage')
  if isinstance(usage,dict):
   clean['usage']={key:usage[key] for key in token_keys if number(usage.get(key))}
   for key in ('prompt_tokens_details','completion_tokens_details','input_tokens_details','output_tokens_details'):
    if isinstance(usage.get(key),dict):
     clean['usage'][key]={k:usage[key][k] for k in ('cached_tokens','reasoning_tokens','audio_tokens','accepted_prediction_tokens','rejected_prediction_tokens') if number(usage[key].get(k))}
  if clean:result.append(clean)
 return result

class UpstreamError(RuntimeError):
 def __init__(self,status,message):super().__init__(message);self.status=status

@contextlib.contextmanager
def provider_session(profile):
 if profile and profile.get('wire_api')=='chat_completions':
  with ChatProxy(profile) as proxy:
   local={**profile,'base_url':proxy.url,'wire_api':'responses','api_key':proxy.token}
   yield overrides(local),{KEY_ENV:proxy.token},proxy.calls
 else:yield overrides(profile),({KEY_ENV:profile['api_key']} if profile else None),[]
