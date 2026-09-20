import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from model_backend import load_profile,overrides,bind_task,public_identity,KEY_ENV
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
