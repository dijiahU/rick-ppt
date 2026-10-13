"""Atomic native Responses transport, retry boundaries and credential isolation."""
import copy, io, json, unittest, threading,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock, patch

from chat_proxy import KEY_ENV, UpstreamError, provider_session, safe_api_calls
from responses_proxy import ResponsesProxy
from chat_protocol import response_sse_events

PROFILE={'model':'test-model','base_url':'https://provider.invalid/v1','api_key':'host-secret-placeholder',
         'wire_api':'responses','reasoning_effort':'high','service_tier':'fast'}

def response(**changes):
    result={'id':'resp_1','object':'response','created_at':1,'model':'test-model','status':'completed',
            'error':None,'output':[{'id':'msg_1','type':'message','role':'assistant','status':'completed',
              'content':[{'type':'output_text','text':'done','annotations':[]}]}],
            'service_tier':'default','usage':{'input_tokens':10,'output_tokens':2,'total_tokens':12}}
    result.update(changes);return result

def upstream(reply,status=200,streaming=True):
    raw=('event: response.'+reply['status']+'\ndata: '+json.dumps({'type':'response.'+reply['status'],'response':reply})+'\n\n') if streaming else json.dumps(reply)
    return SimpleNamespace(returncode=0,stdout=raw+'\n'+str(status)+'\nreq-123\n',stderr='')

class ResponsesTests(unittest.TestCase):
    def test_real_curl_utf8_and_nested_tool_json_round_trip(self):
        """Parse with actual curl, not json.loads(config), which hides this bug."""
        observed=[]
        class Echo(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                observed.append(body)
                arguments=json.dumps({'正文':body['input'][0]['content'],'nested':body['input'][1]['output']},ensure_ascii=False)
                result=response(output=[{'id':'fc_utf8','type':'function_call','status':'completed','name':'capture',
                                       'call_id':'call_utf8','arguments':arguments}])
                raw=(''.join('event: '+e['type']+'\ndata: '+json.dumps(e,ensure_ascii=False)+'\n\n' for e in response_sse_events(result))) if body['stream'] else json.dumps(result,ensure_ascii=False)
                encoded=raw.encode('utf-8')
                self.send_response(200);self.send_header('Content-Type','text/event-stream' if body['stream'] else 'application/json; charset=utf-8')
                self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)
        server=ThreadingHTTPServer(('127.0.0.1',0),Echo);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            text='原始标题 → API链路测试 😀\n换行 "双引号" 与反斜杠 \\ 文件路径 C:\\资料\\测试.txt'
            nested={'中文键':'图表 ✅','quoted':'"你好"','path':'C:\\资料\\file.txt','lines':'甲\n乙','literal_escape':'\\u4e2d'}
            body={'model':'test-model','stream':True,'input':[{'role':'user','content':text},
                  {'type':'function_call_output','call_id':'prior_call','output':json.dumps(nested,ensure_ascii=False)}]}
            proxy=ResponsesProxy({**PROFILE,'base_url':f'http://127.0.0.1:{server.server_port}/v1'})
            actual=proxy._upstream
            def local_curl(command,**kwargs):
                # This fixture alone bypasses developer machine proxy env.
                return actual(command[:1]+['--noproxy','*']+command[1:],**kwargs)
            with patch.object(proxy,'_upstream',side_effect=local_curl) as call:
                result=proxy.complete(body)
                self.assertEqual(call.call_count,1)
            self.assertEqual(observed[0]['input'],body['input'])
            self.assertTrue(observed[0]['stream'])
            parsed=json.loads(result['output'][0]['arguments'])
            self.assertEqual(parsed['正文'],text);self.assertEqual(json.loads(parsed['nested']),nested)
            self.assertEqual(proxy._digest(body),proxy._digest(copy.deepcopy(body)))
            proxy.abort_delivery(body)
            with patch.object(proxy,'_upstream') as call:
                with self.assertRaises(UpstreamError):proxy.complete(copy.deepcopy(body))
                call.assert_not_called()
        finally:server.shutdown();server.server_close();thread.join(timeout=2)

    def test_native_history_images_reasoning_schema_and_length_are_preserved(self):
        body={'model':'test-model','stream':True,'previous_response_id':'resp_old','max_output_tokens':48000,
              'reasoning':{'effort':'low','summary':'auto'},'input':[{'type':'reasoning','encrypted_content':'encrypted-state'},
              {'role':'user','content':[{'type':'input_image','image_url':'data:image/png;base64,example'}]}],
              'tools':[{'type':'namespace','name':'functions','description':'tools','tools':[{'type':'custom','name':'exec',
                       'format':{'type':'grammar','syntax':'lark','definition':'start: /.+/'}}]}],
              'text':{'format':{'type':'json_schema','name':'result','schema':{'type':'object'}}}}
        original=copy.deepcopy(body);proxy=ResponsesProxy({**PROFILE,'responses_transport':'buffered'})
        with patch.object(proxy,'_upstream',return_value=upstream(response(),streaming=False)) as call:
            self.assertEqual(proxy.complete(body)['status'],'completed')
        config=call.call_args.kwargs['input'];line=next(x for x in config.splitlines() if x.startswith('data = '))
        sent=json.loads(json.loads(line[7:]));self.assertFalse(sent['stream'])
        for key in ('previous_response_id','max_output_tokens','input','tools','text'):self.assertEqual(sent[key],body[key])
        self.assertEqual(sent['reasoning'],{'effort':'high','summary':'auto'})
        self.assertEqual(sent['service_tier'],'priority');self.assertEqual(body,original)
        self.assertNotIn(PROFILE['api_key'],repr(call.call_args.args));self.assertNotIn('encrypted-state',repr(call.call_args.args))
        receipt=safe_api_calls(proxy.calls)[0];self.assertEqual(receipt['request_id'],'req-123')
        self.assertEqual(receipt['requested_service_tier'],'priority');self.assertEqual(receipt['actual_service_tier'],'default')

    def test_http200_failed_is_bounded_and_same_request_is_not_replayed(self):
        failed=response(status='failed',output=[],error={'type':'server_error','code':'upstream_timeout','message':'private upstream details'})
        proxy=ResponsesProxy(PROFILE);proxy.stopping.wait=Mock(return_value=False)
        with patch.object(proxy,'_upstream',return_value=upstream(failed)) as call:
            with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
            with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
        self.assertEqual(call.call_count,2);self.assertTrue(proxy.calls[-1]['cache_hit'])
        self.assertTrue(proxy.calls[0]['http_ok']);self.assertFalse(proxy.calls[0]['ok'])
        safe=safe_api_calls(proxy.calls);self.assertEqual(safe[0]['response_error_type'],'server_error')
        self.assertNotIn('private upstream details',json.dumps(proxy.calls))

    def test_partial_tool_result_never_retries_or_escapes_as_success(self):
        call_item={'id':'fc_1','type':'function_call','call_id':'call_1','name':'write','arguments':'partial','status':'incomplete'}
        proxy=ResponsesProxy(PROFILE)
        with patch.object(proxy,'_upstream',return_value=upstream(response(status='failed',output=[call_item],error={'type':'server_error'}))) as call:
            with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
        self.assertEqual(call.call_count,1);self.assertFalse(proxy.calls[0]['ok'])

    def test_top_completed_with_incomplete_tool_is_rejected(self):
        item={'id':'fc_1','type':'function_call','call_id':'call_1','name':'write','arguments':'partial','status':'incomplete'}
        proxy=ResponsesProxy(PROFILE)
        with patch.object(proxy,'_upstream',return_value=upstream(response(output=[item]))):
            with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
        self.assertFalse(proxy.calls[-1]['ok'])

    def test_malformed_tool_status_or_argument_type_is_not_executable(self):
        base={'id':'fc_1','type':'function_call','call_id':'call_1','name':'write','arguments':'{}','status':'completed'}
        for changes in ({'status':'unknown'},{'status':42},{'arguments':{'command':'bad'}},{'arguments':'{"partial":'},{'call_id':''}):
            proxy=ResponsesProxy(PROFILE)
            with patch.object(proxy,'_upstream',return_value=upstream(response(output=[{**base,**changes}]))):
                with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
            self.assertFalse(proxy.calls[-1]['ok'])

    def test_uncertain_local_delivery_is_not_regenerated(self):
        proxy=ResponsesProxy(PROFILE);body={'model':'test-model','input':'hello','stream':True}
        with patch.object(proxy,'_upstream',return_value=upstream(response())) as call:
            proxy.complete(body);proxy.abort_delivery(body)
            with self.assertRaises(UpstreamError):proxy.complete(body)
        self.assertEqual(call.call_count,1)

    def test_incomplete_and_model_mismatch_are_terminal(self):
        for reply in (response(status='incomplete',incomplete_details={'reason':'max_output_tokens'}),response(model='other-model')):
            proxy=ResponsesProxy(PROFILE)
            with patch.object(proxy,'_upstream',return_value=upstream(reply)) as call:
                with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
            self.assertEqual(call.call_count,1);self.assertFalse(proxy.calls[0]['ok'])

    def test_buffered_sse_replay_keeps_reasoning_namespaces_custom_and_long_input(self):
        long='中文script\n'*5000
        items=[{'id':'rs_1','type':'reasoning','encrypted_content':'state','summary':[{'type':'summary_text','text':'brief'}]},
               {'id':'ct_1','type':'custom_tool_call','status':'completed','call_id':'call_1','namespace':'functions','name':'exec','input':long},
               {'id':'opaque_1','type':'web_search_call','status':'completed','action':{'type':'search','query':'fixture'}}]
        result=response(output=items);events=response_sse_events(result)
        delta=''.join(e['delta'] for e in events if e['type']=='response.custom_tool_call_input.delta')
        self.assertEqual(delta,long);self.assertGreater(sum(e['type']=='response.custom_tool_call_input.delta' for e in events),1)
        self.assertEqual(events[-1]['response'],result)
        done=[e['item'] for e in events if e['type']=='response.output_item.done'];self.assertEqual(done,items)
        self.assertNotIn('arguments',done[0]);self.assertNotIn('arguments',done[2])

    def test_streaming_mode_requires_terminal_frame(self):
        proxy=ResponsesProxy({**PROFILE,'responses_transport':'streaming'})
        raw='event: response.created\ndata: '+json.dumps({'type':'response.created','response':response(status='in_progress')})+'\n\n'
        process=SimpleNamespace(returncode=0,stdout=raw+'\n200\nreq-123\n',stderr='')
        with patch.object(proxy,'_upstream',return_value=process):
            with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
        self.assertEqual(proxy.calls[0]['response_error_type'],'stream_incomplete')

    def test_default_and_explicit_upstream_modes(self):
        for selected,expected in (({},True),({'responses_transport':'streaming'},True),({'responses_transport':'buffered'},False)):
            proxy=ResponsesProxy({**PROFILE,**selected})
            with patch.object(proxy,'_upstream',return_value=upstream(response(),streaming=expected)) as call:
                proxy.complete({'model':'test-model','input':'中文 😀','stream':True})
            line=next(x for x in call.call_args.kwargs['input'].splitlines() if x.startswith('data = '))
            self.assertIs(json.loads(json.loads(line[7:]))['stream'],expected)

    def test_524_retries_once_with_cancellable_documented_backoff(self):
        timeout=SimpleNamespace(returncode=0,stdout='Gateway timeout\n524\nreq-timeout\n',stderr='')
        proxy=ResponsesProxy(PROFILE)
        with patch.object(proxy.stopping,'wait',return_value=False) as wait,patch.object(proxy,'_upstream',side_effect=[timeout,upstream(response())]) as call:
            self.assertEqual(proxy.complete({'model':'test-model','input':'hello'})['status'],'completed')
        self.assertEqual(call.call_count,2);wait.assert_called_once_with(120)
        self.assertEqual(proxy.calls[0]['upstream_status'],524);self.assertEqual(proxy.calls[0]['retry_delay_seconds'],120)

    def test_524_exhaustion_returns_fatal_sdk_400_and_deduplicates(self):
        timeout=SimpleNamespace(returncode=0,stdout='Gateway timeout\n524\nreq-timeout\n',stderr='')
        with ResponsesProxy(PROFILE) as proxy:
            with patch.object(proxy.stopping,'wait',return_value=False),patch.object(proxy,'_upstream',return_value=timeout) as call:
                request={'model':'test-model','input':'hello','stream':True}
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(2):
                    req=urllib.request.Request(proxy.url+'/responses',data=json.dumps(request).encode(),headers={'Authorization':'Bearer '+proxy.token,'Content-Type':'application/json'})
                    with self.assertRaises(urllib.error.HTTPError) as caught:opener.open(req,timeout=5)
                    self.assertEqual(caught.exception.code,400)
                    self.assertEqual(json.loads(caught.exception.read())['error']['code'],'pptx_upstream_failure')
                self.assertEqual(call.call_count,2);self.assertTrue(proxy.calls[-1]['cache_hit'])

    def test_failed_stream_with_partial_or_without_terminal_never_retries(self):
        partial={'type':'response.output_item.added','item':{'id':'fc_1','type':'function_call','arguments':'','name':'write','call_id':'call_1','status':'in_progress'},'output_index':0}
        failed=response(status='failed',output=[],error={'type':'server_error'})
        terminal={'type':'response.failed','response':failed}
        error={'type':'error','error':{'type':'server_error'}}
        for events in ([partial,terminal],[error],[partial,error]):
            raw=''.join('data: '+json.dumps(e)+'\n\n' for e in events)
            process=SimpleNamespace(returncode=0,stdout=raw+'\n200\nreq-123\n',stderr='')
            proxy=ResponsesProxy(PROFILE)
            with patch.object(proxy,'_upstream',return_value=process) as call:
                with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
            self.assertEqual(call.call_count,1)

    def test_524_partial_then_malformed_sse_is_terminal_sdk_error(self):
        partial={'type':'response.output_item.added','item':{'id':'fc_1','type':'function_call','arguments':'','name':'write','call_id':'call_1','status':'in_progress'},'output_index':0}
        raw='event: response.output_item.added\ndata: '+json.dumps(partial)+'\n\ndata: {malformed\n\n'
        process=SimpleNamespace(returncode=0,stdout=raw+'\n524\nreq-524\n',stderr='')
        with ResponsesProxy(PROFILE) as proxy:
            with patch.object(proxy.stopping,'wait',return_value=False) as wait,patch.object(proxy,'_upstream',return_value=process) as call:
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                req=urllib.request.Request(proxy.url+'/responses',data=json.dumps({'model':'test-model','input':'hello','stream':True}).encode(),headers={'Authorization':'Bearer '+proxy.token,'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as caught:opener.open(req,timeout=5)
                self.assertEqual(caught.exception.code,400)
                body=caught.exception.read();self.assertNotIn(b'output_item',body)
                self.assertEqual(json.loads(body)['error']['code'],'pptx_upstream_failure')
                call.assert_called_once();wait.assert_not_called()

    def test_auth_key_and_private_error_codes_cannot_enter_receipts(self):
        proxy=ResponsesProxy(PROFILE);failed=response(status='failed',output=[],error={'type':PROFILE['api_key'],'code':PROFILE['api_key']})
        with patch.object(proxy,'_upstream',return_value=upstream(failed)):
            with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'hello'})
        self.assertNotIn(PROFILE['api_key'],json.dumps(safe_api_calls(proxy.calls)))

    def test_request_id_cannot_embed_provider_or_loopback_credentials(self):
        for secret_source in ('provider','loopback'):
            proxy=ResponsesProxy(PROFILE);secret=PROFILE['api_key'] if secret_source=='provider' else proxy.token
            reply=upstream(response());reply.stdout=reply.stdout.replace('req-123','req-'+secret)
            with patch.object(proxy,'_upstream',return_value=reply):proxy.complete({'model':'test-model','input':'hello'})
            self.assertNotIn('request_id',safe_api_calls(proxy.calls)[0]);self.assertNotIn(secret,json.dumps(proxy.calls))
        self.assertEqual(safe_api_calls([{'request_id':'req-host-secret-placeholder'}],secrets=(PROFILE['api_key'],)),[])

    def test_native_provider_uses_only_ephemeral_loopback_key(self):
        fake=SimpleNamespace(url='http://127.0.0.1:32123/v1',token='local-token',calls=[])
        cm=Mock();cm.__enter__=Mock(return_value=fake);cm.__exit__=Mock(return_value=False)
        with patch('responses_proxy.ResponsesProxy',return_value=cm):
            with provider_session(PROFILE) as (config,env,calls):
                self.assertEqual(env,{KEY_ENV:fake.token});self.assertEqual(calls,[])
                self.assertNotIn(PROFILE['api_key'],json.dumps([config,env,calls]))

if __name__=='__main__':unittest.main()
