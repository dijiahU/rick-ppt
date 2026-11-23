"""Per-task Fast choice: admission pin, precedence, helpers, API profiles, receipts.
No model, website or worker calls."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from model_backend import (apply_service_tier,service_tier_for,task_service_tier,profile_with_task_tier,
                           overrides,public_identity,bind_task,profile_for_task)


class PinTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_new_fast_admission_is_pinned_and_reused_on_resume(self):
        self.assertEqual(task_service_tier(self.root,'t',False,'fast'),'fast')
        self.assertEqual(json.loads((self.root/'t/service-tier.json').read_text()),{'service_tier':'fast'})
        # Resume/repair rounds keep the pin even if a later claim omits the field.
        self.assertEqual(task_service_tier(self.root,'t',True,None),'fast')
        self.assertEqual(task_service_tier(self.root,'t',True,'fast'),'fast')

    def test_default_and_legacy_tasks_write_nothing(self):
        self.assertIsNone(task_service_tier(self.root,'plain',False,None))
        self.assertFalse((self.root/'plain/service-tier.json').exists())
        # A task already admitted without the choice cannot become Fast later.
        self.assertIsNone(task_service_tier(self.root,'legacy',True,'fast'))
        self.assertFalse((self.root/'legacy/service-tier.json').exists())

    def test_invalid_requests_are_rejected_before_writing(self):
        for value in ('priority','turbo','',True,1):
            with self.assertRaises(ValueError):task_service_tier(self.root,'bad',False,value)
        self.assertFalse((self.root/'bad/service-tier.json').exists())


class PrecedenceTests(unittest.TestCase):
    def test_task_choice_overrides_worker_default(self):
        cfg={'default_service_tier':'default','_task_service_tier':'fast'}
        config=apply_service_tier({'features':{'apps':False}},cfg)
        self.assertEqual(config['service_tier'],'fast')
        self.assertEqual(config['features'],{'apps':False,'fast_mode':True})

    def test_without_task_choice_worker_behavior_is_unchanged(self):
        self.assertEqual(apply_service_tier({'features':{}},{}),{'features':{}})
        self.assertEqual(apply_service_tier({},{'default_service_tier':'fast'})['service_tier'],'fast')
        with self.assertRaisesRegex(ValueError,'default_service_tier'):apply_service_tier({},{'default_service_tier':'turbo'})

    def test_task_only_helpers_ignore_worker_default(self):
        self.assertEqual(apply_service_tier({'features':{}},{'default_service_tier':'fast'},task_only=True),{'features':{}})
        self.assertEqual(apply_service_tier({'features':{}},{'_task_service_tier':'fast'},task_only=True)['service_tier'],'fast')
        self.assertIsNone(service_tier_for({'default_service_tier':'fast'},task_only=True))
        with self.assertRaises(ValueError):service_tier_for({'_task_service_tier':'turbo'})


class ProfileTests(unittest.TestCase):
    base={'wire_api':'responses','model':'gpt-6-astra','base_url':'https://api.openai.com/v1','api_key':'HOST-ONLY-SYNTHETIC'}

    def test_supported_provider_without_tier_uses_task_fast(self):
        profile,note=profile_with_task_tier(dict(self.base),'fast')
        self.assertEqual(profile['service_tier'],'fast');self.assertEqual(note['reason'],'task_choice')
        config=overrides(profile)
        self.assertEqual(config['service_tier'],'fast');self.assertTrue(config['features.fast_mode'])
        self.assertNotIn('service_tier',self.base,'worker profile must not be mutated')

    def test_explicit_profile_tier_wins(self):
        profile,note=profile_with_task_tier({**self.base,'service_tier':'default'},'fast')
        self.assertEqual(profile['service_tier'],'default')
        self.assertEqual(note,{'requested':'fast','applied':'default','reason':'profile_service_tier'})

    def test_unsupported_provider_ignores_and_records(self):
        for url,wire in (('https://api.deepseek.com','responses'),('https://api.siliconflow.cn/v1','chat_completions')):
            original={**self.base,'base_url':url,'wire_api':wire}
            profile,note=profile_with_task_tier(original,'fast')
            self.assertIs(profile,original);self.assertNotIn('service_tier',overrides(profile))
            self.assertEqual(note,{'requested':'fast','applied':None,'reason':'provider_unsupported'})

    def test_no_choice_leaves_profile_identical(self):
        self.assertEqual(profile_with_task_tier(self.base,None),(self.base,None))
        self.assertEqual(profile_with_task_tier(None,'fast'),(None,None))


class ReceiptTests(unittest.TestCase):
    def test_codex_usage_rows_record_configured_tier(self):
        from usage_ledger import UsageLedger
        with tempfile.TemporaryDirectory() as temp:
            ledger=UsageLedger.__new__(UsageLedger)
            ledger.records={};ledger.pending={};ledger.root=Path(temp);ledger.attempt='0'*16
            import threading;ledger.lock=threading.Lock()
            event={'thread_id':'thread-1','turn_id':'turn-1','status':'completed',
                   'usage':{'input_tokens':10,'output_tokens':5,'cached_input_tokens':0,'reasoning_output_tokens':0}}
            ledger.codex_sink('author','gpt-6.2-sol',service_tier='fast')(event)
            ledger.codex_sink('review','gpt-6.2-sol')({**event,'turn_id':'turn-2'})
            tiers=sorted((r['stage'],r['serviceTier']) for r in ledger.records.values())
            self.assertEqual(tiers,[('author','fast'),('review','default')])

    def test_execution_identity_shows_fast_only_for_fast_tasks(self):
        from execution_identity import execution_identity
        plain=execution_identity({'_task_default_model':'gpt-6.2-sol'})['model_selection']
        self.assertNotIn('service_tier',plain);self.assertNotIn('requested_service_tier',plain)
        fast=execution_identity({'_task_default_model':'gpt-6.2-sol','_task_service_tier':'fast'})['model_selection']
        self.assertEqual((fast['requested_service_tier'],fast['service_tier']),('fast','fast'))
        api=execution_identity({'_task_service_tier':'fast','_model_profile':{'model':'x','base_url':'https://api.deepseek.com'},
                                '_service_tier_note':{'requested':'fast','applied':None,'reason':'provider_unsupported'}})['model_selection']
        self.assertIsNone(api['service_tier']);self.assertEqual(api['service_tier_reason'],'provider_unsupported')


class HelperTests(unittest.TestCase):
    """Retained search/generation helpers follow the task choice only."""
    def run_search(self,cfg):
        import auxiliary_tools as a
        seen=[]
        class FakeServer:
            def __init__(self,**kwargs):seen.append(kwargs);self.usage={}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def start_thread(self):return {'thread':{'id':'thread'}}
            def start_turn(self,thread,prompt):return {'id':'turn'}
            def wait_turn(self,*args,**kwargs):return {'status':'completed'}
            def result_text(self,*args):return 'Inspected https://example.test/source.'
        with tempfile.TemporaryDirectory() as temp:
            job=Path(temp).resolve();(job/'assets').mkdir()
            with patch.object(a,'AppServer',FakeServer):
                a.AuxiliaryTools(cfg,job).handle({'tool':'pptx_search_sources','arguments':{'request':'Inspect the page'}})
        return seen[-1]['config']

    def test_fast_task_helpers_use_fast_and_default_helpers_are_unchanged(self):
        base={'default_model':'gpt-6.2-sol','default_reasoning_effort':'high'}
        fast=self.run_search({**base,'_task_service_tier':'fast'})
        self.assertEqual(fast['service_tier'],'fast');self.assertTrue(fast['features']['fast_mode'])
        plain=self.run_search({**base,'default_service_tier':'fast'})
        self.assertNotIn('service_tier',plain);self.assertNotIn('fast_mode',plain['features'])


class StartupTests(unittest.TestCase):
    """Real runner._run_job admission with the workspace/journal stage stubbed."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def start(self,cfg,task):
        import runner
        def prepare(selected):
            job=self.root/('job-'+uuid.uuid4().hex);job.mkdir();return job
        def execute(selected,task,lease,job,journal,plan):return dict(selected)
        with patch.object(runner,'prepare',side_effect=prepare), \
             patch.object(runner,'_installed_plugin_version',return_value='synthetic'), \
             patch.object(runner,'_run_job_locked',side_effect=execute), \
             patch('decision_routing.pin_decision_contract',return_value=0), \
             patch('decision_routing.admitted_click_requirement',return_value=False):
            return runner._run_job(cfg,task,None)

    def test_codex_task_fast_flows_into_phase_config(self):
        cfg={'state_directory':str(self.root/'state'),'token':'SYNTHETIC-HOST-TOKEN','plugin':str(self.root),'python':'python3'}
        task={'id':str(uuid.uuid4()),'lease':'SYNTHETIC-LEASE','execution_backend':'codex','service_tier':'fast'}
        selected=self.start(cfg,task)
        self.assertEqual(selected['_task_service_tier'],'fast')
        self.assertEqual(apply_service_tier({'features':{}},selected)['service_tier'],'fast')
        self.assertNotIn('_task_service_tier',cfg,'per-task choice must not leak into the worker config')
        # A resumed claim reuses the pinned choice.
        again=self.start(cfg,{**task,'service_tier':None})
        self.assertEqual(again['_task_service_tier'],'fast')

    def test_default_task_has_no_tier_and_no_receipt(self):
        cfg={'state_directory':str(self.root/'state'),'token':'SYNTHETIC-HOST-TOKEN','plugin':str(self.root),'python':'python3',
             'default_service_tier':'default'}
        task={'id':str(uuid.uuid4()),'lease':'SYNTHETIC-LEASE','execution_backend':'codex'}
        selected=self.start(cfg,task)
        self.assertNotIn('_task_service_tier',selected)
        self.assertFalse((self.root/'state'/task['id']/'service-tier.json').exists())
        self.assertEqual(apply_service_tier({'features':{}},selected)['service_tier'],'default')

    def test_api_profile_identity_is_pinned_without_injected_tier(self):
        profile={'wire_api':'responses','model':'gpt-6-astra','base_url':'https://api.openai.com/v1','api_key':'HOST-ONLY-SYNTHETIC'}
        state=self.root/'state'
        bind_task(state,'api',profile_for_task(state,'api',profile,False,execution_backend='api'),False,execution_backend='api')
        task_service_tier(state,'api',False,'fast')
        effective,_=profile_with_task_tier(profile,'fast')
        self.assertEqual(effective['service_tier'],'fast')
        # Resume compares the recorded identity against the unmodified worker profile.
        self.assertEqual(json.loads((state/'api/model-backend.json').read_text()),public_identity(profile))
        self.assertEqual(profile_for_task(state,'api',profile,True,execution_backend='api'),profile)


if __name__=='__main__':unittest.main()
