"""Task-route isolation and immutable recovery; no model or website calls."""
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from model_backend import available_backends,bind_task,profile_for_task,public_identity,load_profile
from language import presentation_request


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.profile={'wire_api':'responses','model':'example-model','base_url':'https://provider.example/v1',
                      'api_key':'HOST-ONLY-SYNTHETIC','reasoning_effort':'high'}

    def tearDown(self):self.temp.cleanup()

    def test_both_routes_remain_available_when_api_configured(self):
        self.assertEqual(available_backends({'_model_profile':self.profile}),['api','codex'])
        self.assertEqual(available_backends({}),['codex'])

    def test_explicit_local_choice_ignores_global_api(self):
        chosen=profile_for_task(self.root,'local',self.profile,False,execution_backend='codex')
        self.assertIsNone(chosen)
        bind_task(self.root,'local',chosen,False,execution_backend='codex')
        self.assertEqual(json.loads((self.root/'local/model-backend.json').read_text()),{'backend':'codex-default'})
        self.assertNotIn(self.profile['api_key'],(self.root/'local/execution-choice.json').read_text())

    def test_explicit_api_choice_requires_api_and_never_falls_back(self):
        with self.assertRaisesRegex(ValueError,'not configured'):
            profile_for_task(self.root,'missing',None,False,execution_backend='api')
        chosen=profile_for_task(self.root,'api',self.profile,False,execution_backend='api')
        self.assertIs(chosen,self.profile)
        bind_task(self.root,'api',chosen,False,execution_backend='api')
        with self.assertRaises(ValueError):profile_for_task(self.root,'api',None,True,execution_backend='api')

    def test_existing_task_cannot_change_route(self):
        for route,profile in [('api',self.profile),('codex',None)]:
            bind_task(self.root,route,profile,False,execution_backend=route)
            other='codex' if route=='api' else 'api'
            with self.assertRaisesRegex(ValueError,'change execution'):
                profile_for_task(self.root,route,self.profile,True,execution_backend=other)
            self.assertEqual(profile_for_task(self.root,route,self.profile,True,execution_backend=route),profile)

    def test_legacy_receipts_keep_original_route(self):
        bind_task(self.root,'legacy-local',None,False)
        bind_task(self.root,'legacy-api',self.profile,False)
        self.assertIsNone(profile_for_task(self.root,'legacy-local',self.profile,True))
        self.assertEqual(profile_for_task(self.root,'legacy-api',self.profile,True),self.profile)
        with self.assertRaises(ValueError):profile_for_task(self.root,'legacy-api',self.profile,True,execution_backend='codex')

    def test_unknown_choice_is_rejected_before_provider_binding(self):
        for choice in ('auto','',True):
            with self.assertRaises(ValueError):profile_for_task(self.root,'invalid',self.profile,False,execution_backend=choice)
        self.assertFalse((self.root/'invalid/model-backend.json').exists())

    def test_identity_keeps_old_profile_compatible_and_explicit_transport_pinned(self):
        self.assertNotIn('responses_transport',public_identity(self.profile))
        bind_task(self.root,'explicit',{**self.profile,'responses_transport':'buffered'},False,execution_backend='api')
        with self.assertRaises(ValueError):
            profile_for_task(self.root,'explicit',{**self.profile,'responses_transport':'streaming'},True,execution_backend='api')
        path=self.root/'profile.json';path.write_text(json.dumps({**self.profile,'responses_transport':'buffered'}));path.chmod(0o600)
        self.assertEqual(load_profile(path)['responses_transport'],'buffered')
        path.write_text(json.dumps({**self.profile,'responses_transport':'invented'}))
        with self.assertRaisesRegex(ValueError,'responses_transport'):load_profile(path)

    def test_execution_selection_saved_without_exposing_host_config(self):
        request=presentation_request({'title':'Title','brief':'Description','pages':1,'style':'clear',
                                      'language':'zh-CN','execution_backend':'api'})
        self.assertEqual(request['execution_backend'],'api')
        self.assertNotIn(self.profile['api_key'],json.dumps(request))

    def test_real_job_startup_uses_task_choice_with_same_global_api_config(self):
        import runner
        cfg={'state_directory':str(self.root/'state'),'token':'SYNTHETIC-HOST-TOKEN',
             '_model_profile':self.profile,'plugin':str(self.root),'python':'python3'}
        def prepare(selected):
            job=self.root/('job-'+uuid.uuid4().hex);job.mkdir()
            return job
        def execute(selected,task,lease,job,journal,plan):
            return selected.get('_model_profile'),selected.get('_task_default_model')
        with patch.object(runner,'prepare',side_effect=prepare), \
             patch.object(runner,'_installed_plugin_version',return_value='synthetic'), \
             patch.object(runner,'_run_job_locked',side_effect=execute), \
             patch('decision_routing.pin_decision_contract',return_value=0), \
             patch('decision_routing.admitted_click_requirement',return_value=False):
            for route in ('api','codex'):
                task={'id':str(uuid.uuid4()),'lease':'SYNTHETIC-LEASE','execution_backend':route}
                selected,default=runner._run_job(cfg,task,None)
                self.assertEqual(selected,self.profile if route=='api' else None)
                self.assertEqual(default,None if route=='api' else 'gpt-6.1-sol')
                self.assertEqual(json.loads((self.root/'state'/task['id']/'execution-choice.json').read_text()),
                                 {'execution_backend':route})
        self.assertIs(cfg['_model_profile'],self.profile,'per-task selection must not mutate the worker config')


if __name__=='__main__':unittest.main()
