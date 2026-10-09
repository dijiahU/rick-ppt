import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
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
    def test_transport_failure_is_an_explicit_tool_failure(self):
        with patch.object(a,'AppServer',side_effect=a.TransportError('private error contents')):result=self.aux.handle({'tool':'pptx_search_sources','arguments':{'request':'Evidence'}})
        self.assertFalse(result['success']);self.assertNotIn('private error',result['contentItems'][0]['text'])

if __name__=='__main__':unittest.main()
