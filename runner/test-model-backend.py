import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from model_backend import load_profile,overrides,bind_task,public_identity,KEY_ENV,task_default_model,task_default_reasoning_effort,profile_for_task,retained_tools
from durable import AppServer,task_configuration
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'provider.local.json';self.data={'model':'sample-model','base_url':'https://example.test/v1','api_key':'synthetic-private-key'}
 def tearDown(self):self.tmp.cleanup()
 def profile(self,**changes):
  self.path.write_text(json.dumps({**self.data,**changes}));self.path.chmod(0o600);return load_profile(self.path)
 def test_key_stays_out_of_config_and_tools(self):
  p=self.profile();config=task_configuration(self.root,config_paths=[],web_search='disabled');config.update(overrides(p))
  server=AppServer(cwd=self.root,config=config,provider_env={KEY_ENV:p['api_key']})
  self.assertEqual(server.env[KEY_ENV],p['api_key']);self.assertNotIn(p['api_key'],json.dumps(config));self.assertNotIn(KEY_ENV,config['shell_environment_policy']['set']);self.assertEqual(config['shell_environment_policy']['inherit'],'none');self.assertIn(p['api_key'],server.secrets)
 def test_default_unchanged(self):self.assertEqual(overrides(None),{});self.assertEqual(public_identity(None),{'backend':'codex-default'})
 def test_retained_tools_are_explicit_and_recorded_without_changing_wire_protocol(self):
  p=self.profile(wire_api='chat_completions',auxiliary_tools='existing_backend')
  self.assertTrue(retained_tools(p));self.assertEqual(public_identity(p)['auxiliary_tools'],'existing_backend')
  self.assertEqual(overrides(p)['web_search'],'disabled')
  with self.assertRaises(ValueError):self.profile(auxiliary_tools='invented')
 def test_old_default_admission_keeps_provider_after_global_api_switch(self):
  p=self.profile();bind_task(self.root,'old',None,False)
  self.assertIsNone(profile_for_task(self.root,'old',p,True))
  self.assertIsNone(profile_for_task(self.root,'old',p,False))
  self.assertIsNone(profile_for_task(self.root,'legacy',p,True))
  self.assertEqual(profile_for_task(self.root,'new',p,False),p)
  bind_task(self.root,'external',p,False)
  self.assertEqual(profile_for_task(self.root,'external',p,True),p)
  with self.assertRaises(ValueError):profile_for_task(self.root,'external',None,True)
 def test_new_default_is_61_high_and_persists_on_resume(self):
  self.assertEqual(task_default_model(self.root,'new',False),'gpt-6.1-sol')
  self.assertEqual(task_default_reasoning_effort(self.root,'new'),'high')
  self.assertEqual(task_default_model(self.root,'new',True,'gpt-6-astra','low'),'gpt-6.1-sol')
  self.assertEqual(task_default_reasoning_effort(self.root,'new'),'high')
 def test_model_only_legacy_receipt_keeps_model_and_implicit_effort(self):
  path=self.root/'legacy/default-model.json';path.parent.mkdir();original=b'{"model":"gpt-6-sol"}\n';path.write_bytes(original)
  self.assertEqual(task_default_model(self.root,'legacy',True),'gpt-6-sol')
  self.assertIsNone(task_default_reasoning_effort(self.root,'legacy'))
  self.assertEqual(path.read_bytes(),original)
 def test_invalid_default_effort_does_not_publish_receipt(self):
  with self.assertRaises(ValueError):task_default_model(self.root,'invalid',False,reasoning_effort='unsupported')
  self.assertFalse((self.root/'invalid/default-model.json').exists())
 def test_legacy_task_keeps_its_original_default(self):
  self.assertIsNone(task_default_model(self.root,'legacy',True))
  self.assertFalse((self.root/'legacy/default-model.json').exists())
  self.assertIsNone(task_default_reasoning_effort(self.root,'legacy'))
 def test_environment_key(self):
  self.data.pop('api_key')
  with patch.dict(os.environ,{KEY_ENV:'from-environment'}):self.assertEqual(self.profile()['api_key'],'from-environment')
 def test_missing_key(self):
  self.data.pop('api_key')
  with patch.dict(os.environ,{},clear=True),self.assertRaises(ValueError):self.profile()
 def test_reject_insecure_or_credential_url(self):
  for url in ['http://example.test/v1','https://key@example.test/v1','https://example.test/v1?key=bad','https://example.test/v1/responses']:
   with self.subTest(url=url),self.assertRaises(ValueError):self.profile(base_url=url)
 def test_local_provider(self):self.assertEqual(self.profile(base_url='http://127.0.0.1:8000/v1')['model'],'sample-model')
 def test_reject_protocol(self):
  with self.assertRaisesRegex(ValueError,'wire_api'):self.profile(wire_api='chat')
 def test_private_profile_permissions(self):
  self.profile();self.path.chmod(0o644)
  with self.assertRaises(ValueError):load_profile(self.path)
 def test_provider_cannot_inject_arbitrary_env(self):
  with self.assertRaises(ValueError):AppServer(cwd=self.root,config={},provider_env={'HOME':'bad'})
  with self.assertRaises(ValueError):AppServer(cwd=self.root,config={},provider_env={KEY_ENV:'key'})
 def test_resume_identity_and_key_rotation(self):
  p=self.profile();bind_task(self.root,'task',p,False);p['api_key']='rotated';bind_task(self.root,'task',p,True)
  self.assertNotIn('synthetic-private-key',(self.root/'task/model-backend.json').read_text())
  with self.assertRaises(ValueError):bind_task(self.root,'task',{**p,'model':'another'},True)
  with self.assertRaises(ValueError):bind_task(self.root,'task',None,True)
 def test_legacy_default_task(self):
  with self.assertRaises(ValueError):bind_task(self.root,'legacy',self.profile(),True)
  bind_task(self.root,'legacy',None,True)
if __name__=='__main__':unittest.main()
