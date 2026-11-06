"""Public-source mediation tests with synthetic pixels; no live browser calls."""
import base64
import copy
import fcntl
import hashlib
import io
import json
from pathlib import Path
import random
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from PIL import Image

import browser_sources as b


class Tests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.job=self.root/'job';self.job.mkdir()
        self.cfg={'state_directory':str(self.root/'state'),
            'browser_research':{'enabled':True,'browser':'edge','site':b.SITE,'model':'test-model'}}
        self.source=b.BrowserSources(self.cfg,self.job)
        self.params={'tool':b.TOOL,'arguments':{'query':'商业汇报 PPT 设计','purpose':'Inspect useful type and evidence hierarchy'}}
        self.paths={'chrome_plugin':self.root/'chrome'}
        p=self.paths['chrome_plugin']/'skills/control-chrome/SKILL.md';p.parent.mkdir(parents=True);p.write_text('Fixture browser instructions')
        blob=io.BytesIO();Image.new('RGB',(12,10),'navy').save(blob,format='PNG');self.png=blob.getvalue()
        self.report={'status':'results','summary':'Observed a rendered source','limitations':'Search results are thumbnails',
            'sources':[{'url':b.SITE+'/explore/123?xsec_token=private-signed-query',
                        'title':'Reference','observed':'Large subject with aligned annotations','screenshot':'reference-1.png'}]}
        self.servers=[];outer=self
        class Server:
            usage={('t','u'):{'input_tokens':10}}
            def __init__(self,**kw):self.kw=kw;outer.servers.append(self)
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def start_thread(self):return {'thread':{'id':'t'}}
            def start_turn(self,t,prompt,**kw):self.prompt=prompt;return {'id':'u'}
            def wait_turn(self,*a,**kw):
                (self.kw['cwd']/'reference-1.png').write_bytes(outer.png)
                self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call','tool':'js','status':'completed'}})
                return {'status':'completed'}
            def result_text(self,*a):return json.dumps(outer.report)
        self.Server=Server
        for name,value in [('installed_runtime',lambda:self.paths),('browser_configuration',lambda *a:{'features':{}}),('AppServer',Server)]:
            patcher=patch.object(b,name,value);patcher.start();self.addCleanup(patcher.stop)

    def test_disabled_customer_funded_and_dsh_never_use_operator_browser(self):
        configs=[{}, {**self.cfg,'_customer_funded':True}, {**self.cfg,'_model_profile':{'customer_funded':True}},
                 {**self.cfg,'_harness_transport':'dsh-sdk'},
                 {**self.cfg,'browser_research':{'enabled':True,'browser':'chrome','site':b.SITE}}]
        for cfg in configs:
            tool=b.BrowserSources(cfg,self.job)
            self.assertEqual(tool.specs(),[]);self.assertIsNone(b.capability(cfg))
            self.assertFalse(tool.handle(self.params)['success'])
        self.assertEqual(self.servers,[])

    def test_bounded_arguments_cannot_override_site_browser_or_credentials(self):
        for changes in ({'url':'https://private.invalid'}, {'query':''}, {'query':'x'*201}, {'purpose':'x'*2001}, {'api_key':'private'}):
            params=copy.deepcopy(self.params);params['arguments'].update(changes)
            self.assertFalse(self.source.handle(params)['success'])
        self.assertEqual(self.servers,[])

    def test_sites_are_explicit_and_legacy_settings_keep_the_original_site(self):
        self.assertEqual(b.configured_sites(self.cfg),[b.SITE])
        self.assertFalse(self.source.handle({**self.params,'arguments':{**self.params['arguments'],'site':b.X}})['success'])
        for sites in ([],['https://unapproved.invalid'],[None],b.X):
            cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':sites}}
            self.assertFalse(b.enabled(cfg))
        cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':[b.SITE,b.X,b.X]}}
        self.assertEqual(b.capability(cfg)['sites'],[b.SITE,b.X])

    def test_selected_enabled_site_returns_actual_image_and_scoped_source(self):
        for site,url in ((b.X,b.X+'/designer/status/123?tracking=private'),
                         (b.PINTEREST,'https://jp.pinterest.com/pin/123/?tracking=private')):
            with self.subTest(site=site):
                cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':[b.SITE,site]}}
                self.report['sources'][0]['url']=url
                response=b.BrowserSources(cfg,self.job).handle({**self.params,'arguments':{**self.params['arguments'],'site':site}})
                data=json.loads(response['contentItems'][0]['text'])
                self.assertTrue(response['success']);self.assertEqual(data['site'],site)
                self.assertEqual(len(response['contentItems']),2)
                self.assertNotIn('tracking',data['sources'][0]['url'])
                self.assertIn(site,self.servers[-1].prompt)
                self.assertNotIn('search_result_ai?',self.servers[-1].prompt)
        for url in ('https://jp.pinterest.com/private/board/',b.X+'/messages',b.X+'/designer',
                    'https://x.com.evil.test/search?q=test','https://other.pinterest.com/pin/123/'):
            self.assertIsNone(b.source_url(url,b.PINTEREST))
            self.assertIsNone(b.source_url(url,b.X))
        self.assertIsNone(b.source_url(b.X+'/designer/status/123',b.SITE))

    def test_one_denied_site_does_not_disable_another_explicitly_enabled_site(self):
        cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':[b.SITE,b.X]}}
        tool=b.BrowserSources(cfg,self.job)
        class Denied(self.Server):
            def wait_turn(self,*a,**kw):
                self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call','tool':'js','status':'failed',
                    'error':{'message':'Browser security policy: user denied permission'}}})
        with patch.object(b,'AppServer',Denied):self.assertFalse(tool.handle(self.params)['success'])
        self.report['sources'][0]['url']=b.X+'/designer/status/123'
        response=tool.handle({**self.params,'arguments':{**self.params['arguments'],'site':b.X}})
        self.assertTrue(response['success'])
        self.assertFalse(tool.handle(self.params)['success'])
        self.assertEqual(len(self.servers),2)

    def test_actual_png_reaches_author_image_input_with_exact_hash_and_source(self):
        response=self.source.handle(self.params);self.assertTrue(response['success'])
        result=json.loads(response['contentItems'][0]['text']);file=result['files'][0]
        self.assertEqual(file['sha256'],hashlib.sha256(self.png).hexdigest())
        self.assertEqual((self.job/file['file']).read_bytes(),self.png)
        self.assertEqual(base64.b64decode(response['contentItems'][1]['imageUrl'].split(',',1)[1]),self.png)
        self.assertEqual(result['sources'][0]['screenshot'],file['file'])
        self.assertNotIn('private-signed-query',json.dumps(response))
        self.assertEqual(self.servers[0].kw['enabled_mcp_servers'],('node_repl',))
        self.assertIn('No raw CDP',self.servers[0].prompt)
        self.assertIn('search_result_ai?keyword=%25',self.servers[0].prompt)
        self.assertIs(self.source.handle(self.params),response);self.assertEqual(len(self.servers),1)
        with patch.object(b,'record') as log:
            self.source.sent({**self.params,'threadId':'author','callId':'call'},response)
        data=log.call_args.args[-1]
        self.assertEqual(data['files'][0]['sha256'],file['sha256'])
        self.assertEqual(data['channel'],'tool-result inputImage')

    def test_text_only_results_do_not_invent_visual_inputs(self):
        self.report['sources'][0]['screenshot']=None
        result=self.source.handle(self.params)
        self.assertTrue(result['success']);self.assertEqual(len(result['contentItems']),1)
        self.assertEqual(json.loads(result['contentItems'][0]['text'])['files'],[])

    def test_only_declared_corrected_capture_is_forwarded(self):
        outer=self
        class Corrected(self.Server):
            def wait_turn(self,*a,**kw):
                result=super().wait_turn(*a,**kw)
                (self.kw['cwd']/'reference-2.png').write_bytes(outer.png)
                return result
        self.report['sources'][0]['screenshot']='reference-2.png'
        with patch.object(b,'AppServer',Corrected):response=self.source.handle(self.params)
        result=json.loads(response['contentItems'][0]['text'])
        self.assertEqual(len(result['files']),1)
        self.assertTrue(result['files'][0]['file'].endswith('reference-2.png'))
        self.assertEqual(len(response['contentItems']),2)
        self.assertNotIn('reference-1',json.dumps(result))

    def test_jpeg_screenshot_named_png_retains_exact_bytes_and_correct_mime(self):
        blob=io.BytesIO();Image.new('RGB',(12,10),'navy').save(blob,format='JPEG');self.png=blob.getvalue()
        response=self.source.handle(self.params)
        data=json.loads(response['contentItems'][0]['text']);file=data['files'][0]
        self.assertTrue(file['file'].endswith('.jpg'))
        self.assertEqual((self.job/file['file']).read_bytes(),self.png)
        image=response['contentItems'][1]['imageUrl']
        self.assertTrue(image.startswith('data:image/jpeg;base64,'))
        self.assertEqual(base64.b64decode(image.split(',',1)[1]),self.png)
        self.assertEqual(file['sha256'],hashlib.sha256(self.png).hexdigest())

    def test_missing_or_symlinked_capture_is_not_imported(self):
        outer=self
        class BadCapture(self.Server):
            def wait_turn(self,*a,**kw):
                target=outer.root/'outside.png';target.write_bytes(outer.png)
                (self.kw['cwd']/'reference-1.png').symlink_to(target)
                self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call','tool':'js','status':'completed'}})
                return {'status':'completed'}
        with patch.object(b,'AppServer',BadCapture):response=self.source.handle(self.params)
        data=json.loads(response['contentItems'][0]['text'])
        self.assertEqual(data['files'],[]);self.assertEqual(len(response['contentItems']),1)
        self.assertIsNone(data['sources'][0]['screenshot'])
        self.assertEqual(data['sources'][0]['capture_status'],'unavailable')

    def test_policy_denial_stops_request_and_future_attempts_in_this_context(self):
        class Denied(self.Server):
            def wait_turn(self,*a,**kw):
                self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call','tool':'js','status':'failed',
                    'error':{'message':'Browser security policy: user denied permission. private-error-detail'}}})
                raise AssertionError('Must stop before another browser action')
        with patch.object(b,'AppServer',Denied):
            result=self.source.handle(self.params)
            later=self.source.handle({**self.params,'arguments':{'query':'different','purpose':'research'}})
        self.assertFalse(result['success']);self.assertFalse(later['success'])
        self.assertEqual(json.loads(result['contentItems'][0]['text'])['status'],'blocked')
        self.assertNotIn('private-error-detail',json.dumps(result))
        self.assertEqual(len(self.servers),1)

    def test_terminal_browser_errors_in_result_text_stop_without_waiting_or_requerying(self):
        # Real AppServer failures can have error=null and the browser's message
        # in result.content. Do not lose that cause behind the four-minute cap.
        for message,reason in (
            ('Browser reported: net::ERR_INTERNET_DISCONNECTED','network_disconnected'),
            ('Browser is not available: edge','browser_unavailable'),
            ('Cannot find module /private/runtime.js','browser_runtime_unavailable'),
            ('Browser reported: net::ERR_CONNECTION_RESET','network_failure'),
            ('Browser security policy: user denied permission','permission_denied'),
        ):
            with self.subTest(reason=reason):
                class Failed(self.Server):
                    def wait_turn(self,*a,**kw):
                        self.kw['on_event']({'type':'item.completed','item':{
                            'type':'mcp_tool_call','tool':'js','status':'failed','error':None,
                            'result':{'content':[{'type':'text','text':message+' private-detail'}]}}})
                        raise AssertionError('Must stop on this event, before waiting or acting again')
                tool=b.BrowserSources(self.cfg,self.job);count=len(self.servers)
                with patch.object(b,'AppServer',Failed):
                    response=tool.handle(self.params)
                    later=tool.handle({**self.params,'arguments':{'query':'another','purpose':'research'}})
                self.assertFalse(response['success']);self.assertFalse(later['success'])
                self.assertEqual(json.loads(response['contentItems'][0]['text'])['reason'],reason)
                self.assertNotIn('private-detail',json.dumps(response))
                self.assertEqual(len(self.servers),count+1)

    def test_successful_page_prose_and_correctable_js_errors_are_not_connection_failures(self):
        self.assertIsNone(b.failure_reason({'status':'completed','result':{'content':[
            {'type':'text','text':'Article about net::ERR_INTERNET_DISCONNECTED'}]}}))
        self.assertIsNone(b.failure_reason({'status':'failed','error':{'message':'ReferenceError: tab is not defined'}}))

    def test_outer_timeout_does_not_repeat_same_site_in_this_phase(self):
        from durable import transport_module
        class TimedOut(self.Server):
            def wait_turn(self,*a,**kw):raise transport_module.RPCTimeout('private transport detail')
        with patch.object(b,'AppServer',TimedOut):
            response=self.source.handle(self.params)
            later=self.source.handle({**self.params,'arguments':{'query':'another','purpose':'research'}})
        self.assertFalse(response['success']);self.assertFalse(later['success'])
        self.assertEqual(json.loads(response['contentItems'][0]['text'])['reason'],'request_timeout')
        self.assertNotIn('private transport detail',json.dumps(response))
        self.assertEqual(len(self.servers),1)

    def test_one_site_timeout_does_not_disable_other_authorized_sites(self):
        from durable import transport_module
        cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':[b.SITE,b.PINTEREST,b.X]}}
        tool=b.BrowserSources(cfg,self.job)
        class TimedOut(self.Server):
            def wait_turn(self,*a,**kw):raise transport_module.RPCTimeout('private timeout detail')
        with patch.object(b,'AppServer',TimedOut):first=tool.handle(self.params)
        self.assertEqual(json.loads(first['contentItems'][0]['text'])['failure_scope'],'site')
        for site,url in ((b.PINTEREST,'https://jp.pinterest.com/pin/123/'),(b.X,b.X+'/designer/status/123')):
            self.report['sources'][0]['url']=url
            result=tool.handle({**self.params,'arguments':{**self.params['arguments'],'site':site}})
            self.assertTrue(result['success'])
            self.assertEqual(len(result['contentItems']),2)
        self.assertEqual(len(self.servers),3)
        self.assertIsNone(tool.unavailable_reason)

    def test_site_network_failure_isolated_but_missing_shared_runtime_is_global(self):
        cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':[b.SITE,b.X]}}
        for message,other_available in [('net::ERR_PROXY_CONNECTION_FAILED',True),
                                        ('net::ERR_INTERNET_DISCONNECTED',True),
                                        ('Browser is not available: edge',False),
                                        ('Cannot find module /private/runtime.js',False)]:
            with self.subTest(message=message):
                class Failed(self.Server):
                    def wait_turn(self,*a,**kw):
                        self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call','tool':'js',
                            'status':'failed','error':{'message':message}}})
                        raise AssertionError('Recognized failure must stop this request')
                tool=b.BrowserSources(cfg,self.job)
                with patch.object(b,'AppServer',Failed):result=tool.handle(self.params)
                self.assertFalse(result['success'])
                self.report['sources'][0]['url']=b.X+'/designer/status/123'
                following=tool.handle({**self.params,'arguments':{**self.params['arguments'],'site':b.X}})
                self.assertEqual(following['success'],other_available)

    def test_busy_browser_does_not_start_or_wait_for_model(self):
        state=Path(self.cfg['state_directory']);state.mkdir()
        with (state/'browser-research.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            response=self.source.handle(self.params)
        self.assertEqual(json.loads(response['contentItems'][0]['text'])['status'],'busy')
        self.assertEqual(self.servers,[])

    def test_untrusted_results_outside_source_site_cannot_be_published_as_sources(self):
        self.report['sources'][0]['url']='https://other.test/private'
        response=self.source.handle(self.params)
        self.assertFalse(response['success'])
        self.assertEqual(json.loads(response['contentItems'][0]['text'])['sources'],[])
        for url in ('https://www.xiaohongshu.com@evil.test/explore/abc','file:///private/a',
                    b.SITE+'/user/profile/me',b.SITE+'/api/account',b.SITE+'/explore/abc\n'):
            self.assertIsNone(b.source_url(url))
        self.assertNotIn('signed-value',b.safe_text(b.SITE+'/explore/abc?xsec_token=signed-value',1000))
        self.assertNotIn('private.invalid',b.safe_text('Look https://private.invalid/account',1000))

    def test_incomplete_model_turn_does_not_turn_existing_capture_into_success(self):
        class Incomplete(self.Server):
            def wait_turn(self,*a,**kw):
                super().wait_turn(*a,**kw);return {'status':'failed'}
        with patch.object(b,'AppServer',Incomplete):response=self.source.handle(self.params)
        self.assertFalse(response['success']);self.assertEqual(len(response['contentItems']),1)
        self.assertFalse((self.job/'assets').exists())

    def batch_setup(self, *, tick=None):
        cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],
            'sites':[b.SITE,b.PINTEREST,b.X]}}
        tool=b.BrowserSources(cfg,self.job,tick=tick)
        params={'tool':b.TOOL,'arguments':{'requests':[
            {'site':site,'query':'Office examples','purpose':'Inspect task-relevant public material'}
            for site in (b.SITE,b.PINTEREST,b.X)]}}
        return tool,params

    def batch_server(self, *, barrier=None, failures=None, pixels=None):
        """Independent deterministic sources, exercising actual import/assembly."""
        outer=self
        urls={b.SITE:b.SITE+'/explore/123',
              b.PINTEREST:'https://jp.pinterest.com/pin/456/',b.X:b.X+'/designer/status/789',
              b.GOOGLE:'https://example.org/public-guide'}
        images={}
        for site,color in zip(urls,('navy','red','green','purple')):
            blob=io.BytesIO();Image.new('RGB',(12,10),color).save(blob,format='PNG')
            images[site]=pixels or blob.getvalue()
        class MultiServer(self.Server):
            gate=barrier
            def start_turn(self,t,prompt,**kw):
                result=super().start_turn(t,prompt,**kw)
                self.args=json.loads(prompt.split('Research request:\n',1)[1].split('\n\nBrowser instructions:',1)[0])
                return result
            def wait_turn(self,*a,**kw):
                if self.gate:self.gate.wait(timeout=3)
                failure=(failures or {}).get(self.args['site'])
                if failure=='timeout':
                    from durable import transport_module
                    raise transport_module.RPCTimeout('private timeout detail')
                if failure=='denied':
                    self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call',
                        'tool':'js','status':'failed','error':{'message':'Browser security policy: user denied permission private detail'}}})
                    raise AssertionError('Permission denial must stop this site')
                (self.kw['cwd']/'reference-1.png').write_bytes(images[self.args['site']])
                self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call','tool':'js','status':'completed'}})
                return {'status':'completed'}
            def result_text(self,*a):
                return json.dumps({'status':'results','summary':'Observed public example',
                    'limitations':'Thumbnail, not the original asset','sources':[{
                    'url':urls[self.args['site']],'title':self.args['site'],
                    'observed':'Concrete input/output example','screenshot':'reference-1.png'}]})
        return MultiServer,images

    def test_batch_overlaps_three_sites_and_preserves_exact_source_pixels(self):
        tool,params=self.batch_setup()
        Server,pixels=self.batch_server(barrier=threading.Barrier(3))
        with patch.object(b,'AppServer',Server):response=tool.handle(params)
        self.assertTrue(response['success'])
        results=json.loads(response['contentItems'][0]['text'])['results']
        self.assertEqual([r['site'] for r in results],[b.SITE,b.PINTEREST,b.X])
        self.assertEqual(len(self.servers),3)
        self.assertEqual(len({s.kw['cwd'] for s in self.servers}),3)
        for result,image in zip(results,response['contentItems'][1:]):
            file=result['files'][0];expected=pixels[result['site']]
            self.assertEqual(base64.b64decode(image['imageUrl'].split(',',1)[1]),expected)
            self.assertEqual((self.job/file['file']).read_bytes(),expected)
            self.assertEqual(file['sha256'],hashlib.sha256(expected).hexdigest())
            self.assertEqual(result['sources'][0]['screenshot'],file['file'])
            self.assertIn('close only the tab you created',self.servers[0].prompt)
        with patch.object(b,'record') as record:
            tool.sent({**params,'threadId':'author','callId':'batch-call'},response)
        receipts=[c.args[-1] for c in record.call_args_list]
        self.assertEqual(len(receipts),3)
        self.assertEqual({r['files'][0]['sha256'] for r in receipts},
                         {hashlib.sha256(pixels[s]).hexdigest() for s in (b.SITE,b.PINTEREST,b.X)})

    def test_batch_site_timeout_or_denial_does_not_cancel_other_sites(self):
        for failure in ('timeout','denied'):
            with self.subTest(failure=failure):
                tool,params=self.batch_setup();before=len(self.servers)
                Server,_=self.batch_server(barrier=threading.Barrier(3),failures={b.SITE:failure})
                with patch.object(b,'AppServer',Server):response=tool.handle(params)
                results=json.loads(response['contentItems'][0]['text'])['results']
                self.assertTrue(response['success'])
                self.assertEqual([r['status'] for r in results],
                                 ['unavailable' if failure=='timeout' else 'blocked','results','results'])
                self.assertEqual(len(response['contentItems']),3)
                self.assertIsNone(tool.unavailable_reason)
                self.assertNotIn('private',json.dumps(response))
                self.assertFalse(tool.handle({'tool':b.TOOL,'arguments':{
                    **params['arguments']['requests'][0],'query':'Do not retry this site'}})['success'])
                self.assertEqual(len(self.servers),before+3)
                Server.gate=None
                with patch.object(b,'AppServer',Server):
                    next_response=tool.handle({'tool':b.TOOL,'arguments':{
                        **params['arguments']['requests'][1],'query':'Independent follow-up'}})
                self.assertTrue(next_response['success'])

    def test_batch_rejects_invalid_or_unauthorized_entries_before_starting_any_model(self):
        tool,params=self.batch_setup();valid=params['arguments']['requests']
        bad_args=[{'requests':[]},{'requests':valid+[valid[0]]},{'requests':'invalid'},
                  {'requests':[valid[0],valid[0]]},
                  {'requests':[valid[0],{**valid[0],'query':' '+valid[0]['query']+' '}]},
                  {'requests':[valid[0],{**valid[1],'site':'https://unauthorized.invalid'}]},
                  {'requests':[valid[0],{**valid[1],'query':' '}]},
                  {'requests':[valid[0],{**valid[1],'purpose':'x'*2001}]},
                  {'requests':[valid[0],{**valid[1],'url':'https://private.invalid'}]},
                  {'requests':[valid[0],None]},
                  {'requests':valid,'query':'Mixed request','purpose':'Not permitted'}]
        for args in bad_args:
            with self.subTest(args=args):self.assertFalse(tool.handle({'tool':b.TOOL,'arguments':args})['success'])
        for changes in ({'tool':'other'},{'namespace':'not-allowed'}):
            self.assertFalse(tool.handle({**params,**changes})['success'])
        for cfg in ({}, {**tool.cfg,'_customer_funded':True},{**tool.cfg,'_harness_transport':'dsh-sdk'}):
            self.assertFalse(b.BrowserSources(cfg,self.job).handle(params)['success'])
        self.assertEqual(self.servers,[])

    def test_busy_batch_does_not_start_models(self):
        tool,params=self.batch_setup();state=Path(self.cfg['state_directory']);state.mkdir()
        with (state/'browser-research.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            response=tool.handle(params)
        self.assertEqual(json.loads(response['contentItems'][0]['text'])['status'],'busy')
        self.assertEqual(self.servers,[])

    def test_batch_lock_oserror_degrades_without_starting_models(self):
        tool,params=self.batch_setup()
        with patch.object(tool,'browser_guard',side_effect=OSError('private lock path')):
            response=tool.handle(params)
        self.assertFalse(response['success'])
        self.assertEqual(json.loads(response['contentItems'][0]['text'])['status'],'unavailable')
        self.assertNotIn('private lock path',json.dumps(response))
        self.assertEqual(self.servers,[])

    def test_google_is_explicit_opt_in_and_uses_google_search_not_default_engine(self):
        params={**self.params,'arguments':{**self.params['arguments'],'site':b.GOOGLE}}
        self.assertFalse(self.source.handle(params)['success']);self.assertEqual(self.servers,[])
        cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':[b.GOOGLE,b.SITE,b.PINTEREST,b.X]}}
        tool=b.BrowserSources(cfg,self.job)
        self.report['sources'][0]['url']='https://support.microsoft.com/en-us/office/public-article?utm_source=google'
        response=tool.handle(params);self.assertTrue(response['success'])
        data=json.loads(response['contentItems'][0]['text'])
        self.assertEqual(data['site'],b.GOOGLE)
        self.assertEqual(data['sources'][0]['url'],'https://support.microsoft.com/en-us/office/public-article')
        self.assertIn('external source verification is not established',data['assessment_scope'])
        self.assertEqual(len(response['contentItems']),2)
        prompt=self.servers[-1].prompt
        self.assertIn('https://www.google.com/search?q=',prompt)
        self.assertIn('never type the query into the address bar',prompt)
        self.assertIn('use default Bing',prompt)
        self.assertIn('Do not navigate to other regional Google hosts',prompt)
        self.assertIn('www.google.com.hk redirect',prompt)
        self.assertIn('HTTP 403/access denial',prompt)
        self.assertIn('Google snippets and thumbnails are discovery evidence',prompt)
        self.assertNotIn('search_result_ai?',prompt)
        self.assertEqual(b.capability(cfg)['batch_max_requests'],3)

    def test_google_sources_clean_public_external_identity_without_widening_other_sites(self):
        external='https://example.org/articles/diagram?id=42&utm_source=search#tracking'
        self.assertEqual(b.source_url(external,b.GOOGLE),'https://example.org/articles/diagram?id=42')
        for site in (b.SITE,b.PINTEREST,b.X):self.assertIsNone(b.source_url(external,site))
        self.assertEqual(b.source_url(b.GOOGLE+'/search?q=office+AI&udm=2&start=10&ved=tracking',b.GOOGLE),
                         b.GOOGLE+'/search?q=office+AI&udm=2&start=10')
        self.assertEqual(b.source_url('https://www.google.com.hk/search?q=office&ved=tracking',b.GOOGLE),
                         'https://www.google.com.hk/search?q=office')
        for url in (
            'https://localhost/a','https://localhost.localdomain/a','https://127.0.0.1/a',
            'https://192.168.1.5/a','https://10.0.0.1/a','https://[::1]/a',
            'https://intranet.internal/a','https://user:password@example.org/a',
            'https://example.org/account','https://example.org/accounts/me',
            'https://example.org/%61ccount/me','https://example.org/signin',
            'https://example.org/oauth/callback','https://accounts.example.org/a',
            'https://example.org/a?access_token=secret','https://example.org/a?signature=secret',
            'https://example.org/a?X-Amz-Signature=secret','https://example.org/a?session=secret',
            'https://accounts.google.com/signin','https://consent.google.com/m',
            'https://www.google.co.jp/search?q=office','https://google.com/search?q=office',
            b.GOOGLE+'/url?q=https://example.org/a',b.GOOGLE+'/account',
            'file:///private/a','https://example.org/a\n',
        ):
            with self.subTest(url=url):self.assertIsNone(b.source_url(url,b.GOOGLE))

    def test_google_barrier_remains_blocked_and_is_not_retried_or_fallback(self):
        cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':[b.GOOGLE,b.X]}}
        tool=b.BrowserSources(cfg,self.job)
        params={**self.params,'arguments':{**self.params['arguments'],'site':b.GOOGLE}}
        self.report.update(status='blocked',summary='Google showed a CAPTCHA/access denial',sources=[],limitations='No results inspected')
        response=tool.handle(params)
        self.assertFalse(response['success'])
        self.assertEqual(json.loads(response['contentItems'][0]['text'])['status'],'blocked')
        self.assertEqual(len(response['contentItems']),1)
        self.assertFalse(tool.handle({**params,'arguments':{**params['arguments'],'query':'Another query'}})['success'])
        self.assertEqual(len(self.servers),1)
        self.assertIn(b.GOOGLE,tool.blocked_sites)
        self.assertIsNone(tool.unavailable_reason)

    def test_google_failed_403_or_captcha_tool_stops_without_fallback(self):
        cfg={**self.cfg,'browser_research':{**self.cfg['browser_research'],'sites':[b.GOOGLE]}}
        params={**self.params,'arguments':{**self.params['arguments'],'site':b.GOOGLE}}
        for message in ('HTTP 403 Forbidden','HTTP status: 403','Status code 403','CAPTCHA required'):
            with self.subTest(message=message):
                tool=b.BrowserSources(cfg,self.job);before=len(self.servers)
                class Denied(self.Server):
                    def wait_turn(self,*a,**kw):
                        self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call',
                            'tool':'js','status':'failed','error':None,
                            'result':{'content':[{'type':'text','text':message}]}}})
                        raise AssertionError('Access denial must stop before another action')
                with patch.object(b,'AppServer',Denied):response=tool.handle(params)
                self.assertFalse(response['success'])
                self.assertEqual(json.loads(response['contentItems'][0]['text'])['status'],'blocked')
                self.assertFalse(tool.handle(params)['success'])
                self.assertEqual(len(self.servers),before+1)
        self.assertFalse(b.google_access_blocked({'status':'completed','result':{'content':[
            {'type':'text','text':'Article about HTTP 403 and CAPTCHA required'}]}}))
        self.assertFalse(b.google_access_blocked({'status':'failed','error':{
            'message':'ReferenceError: captcha is not defined'}}))

    def test_google_and_legacy_sites_overlap_in_the_same_three_request_batch(self):
        tool,params=self.batch_setup()
        tool.cfg['browser_research']['sites'].append(b.GOOGLE)
        params['arguments']['requests'][0]['site']=b.GOOGLE
        Server,_=self.batch_server(barrier=threading.Barrier(3))
        class GoogleServer(Server):
            def result_text(self,*a):
                if self.args['site']!=b.GOOGLE:return super().result_text(*a)
                return json.dumps({'status':'results','summary':'Google results','limitations':'Snippets only',
                    'sources':[{'url':'https://example.org/public-guide','title':'Public guide',
                    'observed':'Search snippet','screenshot':'reference-1.png'}]})
            def wait_turn(self,*a,**kw):
                if self.args['site']!=b.GOOGLE:return super().wait_turn(*a,**kw)
                self.gate.wait(timeout=3)
                (self.kw['cwd']/'reference-1.png').write_bytes(outer.png)
                self.kw['on_event']({'type':'item.completed','item':{'type':'mcp_tool_call','tool':'js','status':'completed'}})
                return {'status':'completed'}
        outer=self
        with patch.object(b,'AppServer',GoogleServer):response=tool.handle(params)
        self.assertTrue(response['success'])
        results=json.loads(response['contentItems'][0]['text'])['results']
        self.assertEqual([r['site'] for r in results],[b.GOOGLE,b.PINTEREST,b.X])
        self.assertEqual([r['status'] for r in results],['results']*3)
        self.assertEqual(len(response['contentItems']),4)

    def test_google_parallel_questions_on_same_site_are_distinct_and_normalized(self):
        tool,params=self.batch_setup()
        tool.cfg['browser_research']['sites'].append(b.GOOGLE)
        params['arguments']['requests']=[
            {'site':' '+b.GOOGLE+' ','query':' '+query+' ','purpose':' Research public examples '}
            for query in ('Official office AI instructions','Real office AI workflows','Workplace presentation design')]
        original=copy.deepcopy(params)
        Server,_=self.batch_server(barrier=threading.Barrier(3))
        with patch.object(b,'AppServer',Server):response=tool.handle(params)
        self.assertTrue(response['success'])
        self.assertEqual(params,original)
        results=json.loads(response['contentItems'][0]['text'])['results']
        self.assertEqual([r['site'] for r in results],[b.GOOGLE]*3)
        self.assertEqual([r['status'] for r in results],['results']*3)
        self.assertEqual(len({r['request_id'] for r in results}),3)
        self.assertEqual([r['query'] for r in results],
                         [q['query'].strip() for q in params['arguments']['requests']])
        self.assertEqual({s.args['query'] for s in self.servers},
                         {q['query'].strip() for q in params['arguments']['requests']})
        self.assertTrue(all(s.args['purpose']=='Research public examples' for s in self.servers))
        self.assertEqual(len(response['contentItems']),4)

    def test_batch_owner_tick_runs_only_on_owner_and_stop_joins_helpers(self):
        owner=threading.get_ident();ticks=[];exited=[];cancelled=[]
        ready=threading.Event();gate=threading.Barrier(3,action=ready.set)
        class StopTask(RuntimeError):pass
        def tick():
            ticks.append(threading.get_ident())
            self.assertTrue(ready.wait(timeout=3))
            raise StopTask('User stopped task')
        tool,params=self.batch_setup(tick=tick)
        class Waiting(self.Server):
            def __exit__(self,*a):exited.append(threading.get_ident())
            def wait_turn(self,*a,**kw):
                gate.wait(timeout=3)
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    try:self.kw['tick']()
                    except b.TransportError:
                        cancelled.append(threading.get_ident());raise
                    time.sleep(.005)
                raise AssertionError('Child did not observe batch cancellation')
        with patch.object(b,'AppServer',Waiting):
            with self.assertRaises(StopTask):tool.handle(params)
        self.assertEqual(set(ticks),{owner})
        self.assertEqual(len(exited),3);self.assertEqual(len(cancelled),3)
        self.assertNotIn(owner,exited)
        self.assertEqual(tool.cache,{})
        with tool.browser_guard() as acquired:self.assertTrue(acquired)

    def test_batch_budget_omission_is_not_visual_delivery_or_cache_mutation(self):
        tool,params=self.batch_setup()
        blob=io.BytesIO()
        Image.frombytes('RGB',(1024,1024),random.Random(23).randbytes(1024*1024*3)).save(blob,format='PNG')
        Server,_=self.batch_server(pixels=blob.getvalue())
        with patch.object(b,'AppServer',Server):response=tool.handle(params)
        results=json.loads(response['contentItems'][0]['text'])['results']
        self.assertEqual([r['files'][0]['input_image'] for r in results],[True,False,False])
        self.assertEqual(len(response['contentItems']),2)
        for result in results:self.assertTrue((self.job/result['files'][0]['file']).is_file())
        with patch.object(b,'record') as record:tool.sent(params,response)
        self.assertEqual(record.call_count,1)
        self.assertEqual(record.call_args.args[-1]['request_id'],results[0]['request_id'])
        count=len(self.servers)
        standalone=tool.handle({'tool':b.TOOL,'arguments':params['arguments']['requests'][1]})
        self.assertEqual(len(self.servers),count)
        self.assertTrue(json.loads(standalone['contentItems'][0]['text'])['files'][0]['input_image'])
        self.assertEqual(len(standalone['contentItems']),2)


if __name__=='__main__':unittest.main()
