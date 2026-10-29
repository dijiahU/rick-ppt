import json,tempfile,unittest
import io
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from assets import AssetImporter
import auxiliary_tools as a

class FakeServer:
    instances=[]
    def __init__(self,**kwargs):self.kwargs=kwargs;self.usage={('thread','turn'):{'input_tokens':5}};self.instances.append(self)
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def start_thread(self):return {'thread':{'id':'thread'}}
    def start_turn(self,thread,prompt):self.prompt=prompt;return {'id':'turn'}
    def wait_turn(self,*args,**kwargs):return {'status':'completed'}
    def result_text(self,*args):return 'Inspected source https://example.test/teaching; actual factual note.'

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.job=Path(self.temp.name).resolve();(self.job/'assets').mkdir();FakeServer.instances=[]
        self.cfg={'_model_profile':{'api_key':'never-copy-private-key'},'default_model':'gpt-6.1-sol','default_reasoning_effort':'high'}
        self.aux=a.AuxiliaryTools(self.cfg,self.job)
    def test_only_known_bounded_tool_requests_are_allowed(self):
        for params in [{'tool':'shell','arguments':{'request':'pwd'}},{'tool':'pptx_search_sources','arguments':{'request':'x','path':'/private'}},{'tool':'pptx_search_sources','arguments':{'request':'x'*8001}},{'tool':'pptx_generate_image','arguments':{'request':'x','reference_files':['assets/../../private.png']}}]:
            self.assertFalse(self.aux.handle(params)['success'])
        self.assertFalse(FakeServer.instances)
    def test_search_retains_default_backend_without_external_key_and_records_sources(self):
        with patch.object(a,'AppServer',FakeServer):result=self.aux.handle({'tool':'pptx_search_sources','arguments':{'request':'Inspect the actual teaching page'}})
        self.assertTrue(result['success']);server=FakeServer.instances[-1]
        self.assertEqual(server.kwargs['config']['model'],'gpt-6.1-sol');self.assertEqual(server.kwargs['config']['web_search'],'live')
        self.assertFalse(server.kwargs['config']['features']['image_generation'])
        self.assertNotIn('never-copy-private-key',json.dumps(server.kwargs['config']))
        self.assertEqual(server.kwargs['config']['shell_environment_policy']['inherit'],'none')
        self.assertEqual(len(list((self.job/'retained-tool-evidence').glob('*.json'))),1)
        self.assertIn('https://example.test/teaching',result['contentItems'][0]['text'])
    def test_generation_without_an_actual_file_is_not_success(self):
        with patch.object(a,'AppServer',FakeServer):result=self.aux.handle({'tool':'pptx_generate_image','arguments':{'request':'Original concept'}})
        self.assertFalse(result['success']);self.assertTrue(FakeServer.instances[-1].kwargs['config']['features']['image_generation'])
        self.assertEqual(FakeServer.instances[-1].kwargs['config']['web_search'],'disabled')
        self.assertEqual(len(self.aux.calls),1)
        self.assertEqual(self.aux.calls[0]['turn_status'],'completed')

    def test_interrupted_search_keeps_observed_usage_and_tools_without_claiming_evidence(self):
        class Interrupted(FakeServer):
            def wait_turn(server,*args,**kwargs):
                server.kwargs['on_event']({'type':'item.completed','item':{'type':'web_search'}})
                raise a.TransportError('private failure details')
        with patch.object(a,'AppServer',Interrupted):
            result=self.aux.handle({'tool':'pptx_search_sources','arguments':{'request':'Find an authentic site image'}})
        self.assertFalse(result['success'])
        self.assertNotIn('private failure details',result['contentItems'][0]['text'])
        self.assertFalse((self.job/'retained-tool-evidence').exists())
        self.assertEqual(len(self.aux.calls),1)
        record=self.aux.calls[0]
        self.assertEqual(record['tool_events'],{'web_search':1})
        self.assertEqual(record['usage'],{'input_tokens':5})
        self.assertEqual(record['turn_status'],'unconfirmed')
        self.assertEqual(record['usage_receipt_scope'],'observed_so_far')
        self.assertEqual(record['error_type'],'TransportError')

    def test_material_cancellation_still_propagates_with_observed_call_record(self):
        from material_prefetch import PrefetchCancelled
        error=PrefetchCancelled('Cancelled by owner')
        class Cancelled(FakeServer):
            def wait_turn(server,*args,**kwargs):raise error
        with patch.object(a,'AppServer',Cancelled):
            with self.assertRaises(PrefetchCancelled) as caught:
                self.aux.handle({'tool':'pptx_search_sources','arguments':{'request':'Scoped source lookup'}})
        self.assertIs(caught.exception,error)
        self.assertEqual(self.aux.calls[0]['error_type'],'PrefetchCancelled')

    def test_timeout_returns_only_unverified_web_source_leads_and_no_acquired_file(self):
        from durable import transport_module
        class TimedOut(FakeServer):
            def wait_turn(server,*args,**kwargs):
                server.kwargs['on_event']({'type':'item.completed','item':{'type':'web_search','results':[
                    {'url':'https://example.test/original-work','title':'Public source page'}]}})
                raise transport_module.RPCTimeout('Synthetic observation deadline')
        with patch.object(a,'AppServer',TimedOut):
            response=self.aux.handle({'tool':'pptx_search_sources','arguments':{'request':'Find a useful actual source'}})
        self.assertFalse(response['success'])
        lead=json.loads(response['contentItems'][1]['text'])['partial_search_leads']
        self.assertEqual(lead,self.aux.calls[0]['partial_search_leads'])
        self.assertEqual(lead['items'],[{'url':'https://example.test/original-work','title':'Public source page'}])
        self.assertTrue(all(i['type']=='inputText' for i in response['contentItems']))
        self.assertFalse((self.job/'retained-tool-evidence').exists())
        self.assertEqual(list((self.job/'assets').iterdir()),[])
        with patch.object(a,'AppServer',side_effect=a.TransportError('New call failed before events')):
            later=self.aux.handle({'tool':'pptx_search_sources','arguments':{'request':'A different request'}})
        self.assertFalse(later['success']);self.assertEqual(len(later['contentItems']),1)

    def test_source_breadcrumbs_are_bounded_tool_results_without_assistant_invention(self):
        urls=[f'https://example.test/source-{n}' for n in range(9)]
        sources=[{'url':u,'title':'t'*300} for u in urls]+[
            {'url':urls[0],'title':'duplicate'}, {'url':'file:///private/data'},
            {'url':'data:image/png;base64,not-a-lead'}, {'url':'https://name:password@example.test/work'},
            {'url':'https://bad.test/line\nbreak'},None]
        events=[{'type':'item.started','item':{'type':'web_search','results':[{'url':'https://not-completed.test/'}]}},
                {'type':'item.completed','item':{'type':'agent_message','text':'https://invented.test/'}},
                {'type':'item.completed','item':{'type':'web_search','results':sources}}]
        leads=a.unfinished_search_leads(events)
        self.assertEqual(len(leads['items']),6);self.assertTrue(leads['truncated'])
        self.assertTrue({v['url'] for v in leads['items']}<=set(urls))
        self.assertTrue(all(len(v['title'])<=160 for v in leads['items']))
        self.assertIsNone(a.unfinished_search_leads(events[:2]))
    def test_transport_failure_is_an_explicit_tool_failure(self):
        with patch.object(a,'AppServer',side_effect=a.TransportError('private error contents')):result=self.aux.handle({'tool':'pptx_search_sources','arguments':{'request':'Evidence'}})
        self.assertFalse(result['success']);self.assertNotIn('private error',result['contentItems'][0]['text'])
    def test_sync_generation_keeps_shared_registry_and_actual_asset(self):
        generated=self.job/'generated/thread';generated.mkdir(parents=True)
        blob=io.BytesIO();Image.new('RGB',(8,8),'blue').save(blob,format='PNG')
        (generated/'exec-11111111-1111-1111-1111-111111111111.png').write_bytes(blob.getvalue())
        shared={};author=AssetImporter(self.job);author.imported=shared
        aux=a.AuxiliaryTools(self.cfg,self.job,importer=author)
        def importer(job,**kw):return AssetImporter(job,generated_root=generated.parent,**kw)
        with patch.object(a,'AppServer',FakeServer),patch.object(a,'AssetImporter',side_effect=importer):
            result=aux.handle({'tool':'pptx_generate_image','arguments':{'request':'Original concept'}})
        self.assertTrue(result['success']);self.assertIs(author.imported,shared)
        self.assertEqual(len(shared),1)
        index=json.loads((self.job/'assets/index.json').read_text())['images']
        self.assertEqual(index,list(shared.values()))
        self.assertEqual((self.job/'assets'/index[0]['file']).read_bytes(),blob.getvalue())

if __name__=='__main__':unittest.main()
