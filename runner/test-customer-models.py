"""No upstream requests. Test task identity, secret isolation and fail-closed paths."""
import copy,json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import Mock,patch
from customer_models import customer_profile
from responses_proxy import ResponsesProxy
from auxiliary_tools import AuxiliaryTools
from model_backend import bind_task,profile_for_task

class CustomerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.task={'id':str(uuid.uuid4()),'lease':'LEASE','execution_backend':'api','funding_mode':'user_api'}
  self.binding={'version':1,'credentialId':str(uuid.uuid4()),'provider':'deepseek','model':'deepseek-flash'}
  self.key='customer-only-key-do-not-persist'
  self.send=Mock(return_value={'funding':self.binding,'apiKey':self.key})
 def tearDown(self):self.temp.cleanup()
 def test_fixed_endpoint_binding_no_secret_persistence_and_rotation(self):
  profile=customer_profile(self.root,self.task,self.send)
  self.assertEqual(profile['base_url'],'https://api.deepseek.com')
  self.assertFalse(profile['store']);self.assertTrue(profile['customer_funded'])
  self.send.assert_called_once_with('/api/worker/'+self.task['id']+'/model-profile',lease='LEASE')
  bind_task(self.root,self.task['id'],profile,False,execution_backend='api')
  self.send.return_value={'funding':self.binding,'apiKey':'rotated-key-same-customer-account'}
  rotated=customer_profile(self.root,self.task,self.send)
  self.assertEqual(profile_for_task(self.root,self.task['id'],rotated,True,execution_backend='api'),rotated)
  for p in self.root.rglob('*'):
   if p.is_file():self.assertNotIn(self.key,p.read_text())
  self.assertEqual((self.root/self.task['id']/'customer-account.json').stat().st_mode&0o777,0o600)
 def test_unfunded_legacy_task_never_fetches_key(self):
  self.task.pop('funding_mode');self.assertIsNone(customer_profile(self.root,self.task,self.send));self.send.assert_not_called()
 def test_bound_customer_cannot_downgrade_to_operator(self):
  customer_profile(self.root,self.task,self.send);self.task.pop('funding_mode')
  with self.assertRaises(ValueError):customer_profile(self.root,self.task,self.send)
 def test_recovery_cannot_change_customer_or_model(self):
  customer_profile(self.root,self.task,self.send)
  for mutation in [{'credentialId':str(uuid.uuid4())},{'provider':'openai','model':'gpt-6-astra'},{'base_url':'https://customer.invalid'}]:
   self.send.return_value={'funding':{**self.binding,**mutation},'apiKey':self.key}
   with self.assertRaises(ValueError):customer_profile(self.root,self.task,self.send)
 def test_missing_invalid_secret_and_invalid_binding_fail_closed(self):
  for result in [{},{'funding':None},{'funding':self.binding},{'funding':{**self.binding,'provider':'custom'},'apiKey':self.key},{'funding':self.binding,'apiKey':'bad\nkey'}]:
   self.send.return_value=result
   with self.assertRaises(ValueError):customer_profile(self.root,self.task,self.send)
 def test_store_false_explicit_history_and_no_mutation(self):
  profile=customer_profile(self.root,self.task,self.send);proxy=ResponsesProxy(profile)
  original={'model':'deepseek-flash','store':True,'input':[{'role':'user','content':'hello'}]};before=copy.deepcopy(original)
  result=proxy._request(original);self.assertFalse(result['store']);self.assertIn('reasoning.encrypted_content',result['include']);self.assertEqual(original,before)
  for extra in [{'previous_response_id':'resp_old'},{'conversation':'conv_old'}]:
   with self.assertRaises(ValueError):proxy._request({**original,**extra})
 def test_auxiliary_and_prefetch_cannot_charge_operator(self):
  helper=AuxiliaryTools({'_customer_funded':True},self.root)
  with patch('auxiliary_tools.AppServer') as server:
   for name in ['pptx_search_sources','pptx_generate_image']:
    result=helper.execute(name,'task request',[],[]);self.assertFalse(result['success'])
   server.assert_not_called()

if __name__=='__main__':unittest.main()
