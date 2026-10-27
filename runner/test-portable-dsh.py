"""Offline DSH receipts/lifecycle and local transport; no model or Codex calls."""
import json,sys,tempfile,threading,time,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

OVERLAY=Path(__file__).resolve().parents[1]/'tools/skill-packaging/rick-pptx/scripts'
sys.path.insert(0,str(OVERLAY))
from dsh_adapter import DshServer,native_usage
from portable_transport import LocalTransport


class FakeSession:
    def __init__(self,harness,ident):self.harness=harness;self.id=ident;self.cwd=harness.kw['cwd']
    def get_working_directory(self):return self.cwd
    def set_working_directory(self,path):self.cwd=path;return path
    def run(self,blocks,on_notification):
        self.blocks=blocks
        def emit(kind,data,session=None):
            on_notification(SimpleNamespace(method='session.event',payload={'sessionId':session or self.id,'event':{'type':kind,'data':data}}))
        emit('agent/inbox/spliced',{'inserted':[{'id':'remote-'+self.id}]})
        emit('tool/call',{'callId':'tool-1','name':'bash','arguments':{'command':'true'}})
        emit('tool/result',{'message':{'source':{'callId':'tool-1'},'content':[{'type':'text','text':'actual tool result'}]}})
        if self.harness.wait:
            self.harness.release.wait(3)
            if self.harness.closed:raise RuntimeError('owned runtime closed')
        emit('assistant/message',{'message':{'id':'answer','content':[{'type':'text','text':'SYNTHETIC-SECRET'}],
            'usage':{'input_tokens':100,'output_tokens':20}}})
        return SimpleNamespace(final_response='{"ok":true}',finish_reason=self.harness.reason)


class FakeHarness:
    created=[];saved={};wait=False;reason='completed'
    def __init__(self,**kwargs):
        self.kw=kwargs;self.closed=False;self.release=threading.Event();self.client=self;self.prompts=[]
        self.created.append(self)
    def start(self):pass
    def close(self):self.closed=True;self.release.set()
    def start_session(self,ident):
        session=FakeSession(self,ident);self.saved[ident]=session;return session
    def resume_session(self,ident):
        if ident not in self.saved:raise ValueError('missing persisted session')
        session=FakeSession(self,ident);self.saved[ident]=session;return session
    def session_prompt(self,ident,blocks):self.prompts.append((ident,blocks));return 'durable-steer-receipt'


class AdapterTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.job=self.root/'job';self.job.mkdir()
        DshServer.options={'records':str(self.root/'records'),'dsh_home':str(self.root/'dsh-home'),
                           'model':'same-model','provider':'same-provider','profile':'sdk','python':sys.executable,
                           'api_key':'SYNTHETIC-SECRET'}
        FakeHarness.created=[];FakeHarness.saved={};FakeHarness.wait=False;FakeHarness.reason='completed'
        self.patch=patch.object(DshServer,'harness_factory',FakeHarness);self.patch.start();self.addCleanup(self.patch.stop)
        self.events=[];self.public=[];self.usage=[]
    def server(self,**kwargs):
        s=DshServer(cwd=self.job,config={},on_event=self.events.append,on_public=self.public.append,on_usage=self.usage.append,**kwargs)
        self.addCleanup(s.close);s.__enter__();return s
    def test_model_identity_real_inbox_receipt_and_final_completion(self):
        s=self.server();thread=s.start_thread()['thread']['id'];turn=s.start_turn(thread,'actual request',client_message_id='client-id')['id']
        done=s.wait_turn(thread,turn,timeout=1)
        self.assertEqual(done['status'],'completed');self.assertEqual(s.result_text(thread,turn),'\u007b"ok":true}')
        self.assertEqual(s.find_client_message(thread,'client-id')['remote_message_id'],'remote-'+thread)
        self.assertEqual(FakeHarness.created[0].kw['model'],'same-model');self.assertEqual(FakeHarness.created[0].kw['profile'],'sdk')
        self.assertEqual(self.usage[0]['usage']['input_tokens'],100)
        self.assertNotIn('SYNTHETIC-SECRET',json.dumps(self.events+self.public))
    def test_schema_and_local_image_are_sent_without_global_context(self):
        s=self.server();thread=s.start_thread()['thread']['id']
        (self.job/'tiny.png').write_bytes(b'image fixture')
        turn=s.start_turn(thread,'original brief',output_schema={'type':'object'},images=['tiny.png'])['id'];s.wait_turn(thread,turn,timeout=1)
        blocks=FakeHarness.saved[thread].blocks
        self.assertIn('original brief',blocks[0]['text']);self.assertIn('FINAL RESPONSE CONTRACT',blocks[0]['text'])
        self.assertEqual(blocks[1]['type'],'image');self.assertEqual(blocks[1]['mimeType'],'image/png')
    def test_pre_admission_failure_preserves_error_without_unbound_terminal(self):
        s=self.server();thread=s.start_thread()['thread']['id']
        with patch.object(FakeSession,'run',side_effect=ValueError('native input validation failed')):
            with self.assertRaisesRegex(RuntimeError,'native input validation failed'):
                s.start_turn(thread,'request')
        self.assertFalse(any(e['type'] in ('turn.started','turn.failed','turn.interrupted') for e in self.events))
    def test_image_outside_task_is_rejected(self):
        (self.root/'private.png').write_bytes(b'image fixture');s=self.server();thread=s.start_thread()['thread']['id']
        with self.assertRaises(ValueError):s.start_turn(thread,'request',images=[self.root/'private.png'])
    def test_steering_has_native_queued_receipt_and_no_duplicate_turn(self):
        FakeHarness.wait=True;s=self.server();thread=s.start_thread()['thread']['id'];turn=s.start_turn(thread,'request')['id']
        receipt=s.steer(thread,turn,'new requirement',client_message_id='revision')
        self.assertEqual(receipt['dsh_message_id'],'durable-steer-receipt');self.assertEqual(s.active_turns[thread],turn)
        self.assertEqual(s.find_client_message(thread,'revision')['turn_id'],turn)
        s.harness.release.set();s.wait_turn(thread,turn,timeout=1)
    def test_interrupt_reaps_owned_runtime_then_new_context_can_start(self):
        FakeHarness.wait=True;s=self.server();a=s.start_thread()['thread']['id'];t=s.start_turn(a,'request')['id'];first=s.harness
        s.interrupt(a,t);self.assertTrue(first.closed);self.assertEqual(s.wait_turn(a,t)['status'],'interrupted')
        b=s.start_thread()['thread']['id'];self.assertNotEqual(a,b);self.assertEqual(len(FakeHarness.created),2)
    def test_output_limit_or_runtime_error_is_not_success(self):
        FakeHarness.reason='max-tokens';s=self.server();thread=s.start_thread()['thread']['id'];turn=s.start_turn(thread,'request')['id']
        self.assertEqual(s.wait_turn(thread,turn)['status'],'failed')
    def test_fresh_review_sessions_are_distinct_and_resume_is_explicit(self):
        s=self.server();a=s.start_thread()['thread']['id'];b=s.start_thread()['thread']['id'];self.assertNotEqual(a,b)
        s2=self.server();s2.resume_thread(a);self.assertEqual(s2.threads[a].id,a)
        from durable import RPCError
        with self.assertRaises(RPCError):s2.resume_thread('not-a-saved-session')
    def test_receipts_from_parallel_phase_instances_do_not_overwrite_each_other(self):
        a=self.server();b=self.server();a._save_delivery('one','a','t1','native1');b._save_delivery('two','b','t2','native2')
        self.assertIsNotNone(a.find_client_message('b','two'));self.assertIsNotNone(b.find_client_message('a','one'))
    def test_codex_dynamic_tools_are_rejected_instead_of_fake_registration(self):
        s=self.server()
        with self.assertRaises(ValueError):s.start_thread(dynamic_tools=[{'name':'codex-tool'}])
    def test_render_proxy_and_font_environment_reach_dsh_without_worker_secrets(self):
        self.server(env={'PATH':'/task/bin:/usr/bin','PPTX_SOFFICE':'/task/soffice-proxy.py','FONTCONFIG_FILE':'/task/fonts.conf','WORKER_TOKEN':'DO-NOT-INHERIT'})
        value=FakeHarness.created[0].kw['env']
        self.assertIn('/task/bin',value['PATH']);self.assertEqual(value['PPTX_SOFFICE'],'/task/soffice-proxy.py')
        self.assertNotIn('WORKER_TOKEN',value)
    def test_native_cache_counts_are_not_lost_or_double_counted(self):
        value=native_usage({'inputTokens':187,'outputTokens':67,'cacheReadTokens':5760,'cacheWriteTokens':0,'totalTokens':6014})
        self.assertEqual(value['input_tokens'],5947);self.assertEqual(value['cached_input_tokens'],5760)
        self.assertEqual(value['output_tokens'],67)
        self.assertIsNone(native_usage({'inputTokens':187,'outputTokens':67,'totalTokens':1}))


class TransportTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.task={'id':str(uuid.uuid4()),'lease':'local-lease'}
        self.transport=LocalTransport(self.root,self.task,{})
    def send(self,action,body=b'{}',**options):
        return self.transport({},'/api/worker/'+self.task['id']+'?action='+action,body,self.task['lease'],**options)
    def test_no_website_claim_or_unknown_route_is_possible(self):
        with self.assertRaises(RuntimeError):self.send('claim')
        with self.assertRaises(ValueError):self.transport({},'https://outside.test/api/worker',b'{}',self.task['lease'])
    def test_hash_bound_delivery_preserves_old_bytes_for_revision(self):
        import hashlib
        for rev,body in [(0,b'first-native-pptx'),(1,b'revised-native-pptx')]:
            if rev:
                folder=self.root/'messages';folder.mkdir(exist_ok=True)
                (folder/'00000001.json').write_text(json.dumps({'seq':1,'kind':'revision'}))
            digest=hashlib.sha256(body).hexdigest();suffix='&sha256='+digest+'&revision='+str(rev)
            self.send('delivery-ready'+suffix);self.send('complete'+suffix,body)
        self.assertEqual((self.root/'presentation.pptx').read_bytes(),b'revised-native-pptx')
        self.assertEqual(next((self.root/'versions').glob('*.pptx')).read_bytes(),b'first-native-pptx')
    def test_conversation_revisions_and_owner_stop_are_local(self):
        folder=self.root/'messages';folder.mkdir();(folder/'00000001.json').write_text(json.dumps({'id':str(uuid.uuid4()),'seq':1,'kind':'revision','body':'actual revision','attachments':[]}))
        (self.root/'STOP').touch()
        value=self.transport({},'/api/worker/'+self.task['id']+'/conversation?action=poll',b'{}',self.task['lease'])
        self.assertEqual(value['revision'],1);self.assertTrue(value['stop']);self.assertEqual(value['messages'][0]['body'],'actual revision')
    def test_new_revision_and_stop_prevent_stale_delivery(self):
        import hashlib
        from resilience import TaskPaused,WorkerHTTPError
        body=b'original frozen bytes';digest=hashlib.sha256(body).hexdigest();suffix='&sha256='+digest+'&revision=0'
        self.send('delivery-ready'+suffix)
        messages=self.root/'messages';messages.mkdir();(messages/'00000001.json').write_text(json.dumps({'seq':1,'kind':'revision'}))
        with self.assertRaises(WorkerHTTPError):self.send('complete'+suffix,body)
        self.assertFalse((self.root/'presentation.pptx').exists())
        (self.root/'STOP').touch()
        with self.assertRaises(TaskPaused):self.send('complete'+suffix,body)


class ConfigTests(unittest.TestCase):
    def test_explicit_output_limit_change_is_auditable_but_model_switch_is_rejected(self):
        from portable_workflow import check_resume_identity
        old={'model':'same','max_tokens':8192,'profile':'sdk'}
        new={**old,'max_tokens':32768}
        self.assertEqual(check_resume_identity(old,new),{'max_tokens':{'previous':8192,'current':32768}})
        with self.assertRaises(ValueError):check_resume_identity(old,{**new,'model':'different'})
    def test_reuse_private_api_file_without_embedding_key_in_config_or_package(self):
        from portable_workflow import make_options
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);keyfile=root/'credential.json';keyfile.write_text('{"api_key":"SYNTHETIC-ACCOUNT-KEY"}');keyfile.chmod(0o600)
            config=root/'config.json';config.write_text(json.dumps({'model':'actual-model','api_key_file':str(keyfile)}))
            args=SimpleNamespace(config=str(config))
            options=make_options(args,root)
            self.assertEqual(options['model'],'actual-model');self.assertEqual(options['api_key'],'SYNTHETIC-ACCOUNT-KEY')
            self.assertNotIn('SYNTHETIC-ACCOUNT-KEY',config.read_text())
            keyfile.chmod(0o644)
            with self.assertRaises(ValueError):make_options(args,root)
    def test_no_default_model_or_minimal_profile_silently_replaces_complete_workflow(self):
        from portable_workflow import make_options
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);config=root/'config.json';config.write_text('{}');args=SimpleNamespace(config=str(config))
            with self.assertRaises(ValueError):make_options(args,root)
            config.write_text('{"model":"actual-model","profile":"sdk-minimal"}')
            with self.assertRaises(ValueError):make_options(args,root)


class ExecutionReceiptTests(unittest.TestCase):
    def test_package_verification_detects_mixed_entrypoint_and_engine(self):
        import hashlib,importlib.util
        spec=importlib.util.spec_from_file_location('portable_doctor_test',OVERLAY/'doctor.py')
        doctor=importlib.util.module_from_spec(spec);spec.loader.exec_module(doctor)
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'assets').mkdir();(root/'engine').mkdir()
            (root/'SKILL.md').write_text('Current entrypoint')
            (root/'engine/workflow.py').write_text('Current engine')
            files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in root.rglob('*') if p.is_file()}
            ident=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            (root/'assets/package-manifest.json').write_text(json.dumps({'package_id':ident,'files':files}))
            self.assertTrue(doctor.package_integrity(root)['verified'])
            (root/'engine/workflow.py').write_text('Old or modified engine')
            result=doctor.package_integrity(root)
            self.assertFalse(result['verified']);self.assertEqual(result['mismatches'],['engine/workflow.py'])
            (root/'assets/package-manifest.json').write_text('{"source_files":{}}')
            self.assertFalse(doctor.package_integrity(root)['verified'])

    def test_status_receipt_includes_observed_parallel_review_phases(self):
        from portable_workflow import write_status
        from trajectory import Trajectory
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);job=root/'job';job.mkdir();(root/'host').mkdir()
            task={'id':str(uuid.uuid4()),'lease':'private-lease'}
            parent=Trajectory({},task,root/'trajectory')
            child=Trajectory({},task,root/'trajectory')
            try:
                parent.begin('author',job,'Actual author input',['harness']);parent.end('Candidate')
                parent.emit('review.child',{'run_id':child.run_id,'role':'visual'})
                child.begin('visual-1',job,'Independent input',['harness']);child.end('Review result')
                child.finish('complete')
                write_status(root,{'state':'failed'},parent)
                receipt=json.loads((root/'host/execution.json').read_text())
                self.assertEqual(receipt['state'],'failed')
                self.assertEqual(receipt['phases'][0]['name'],'author')
                self.assertEqual(receipt['review_runs'][0]['status'],'complete')
                self.assertEqual(receipt['review_runs'][0]['phases'][0]['name'],'visual-1')
                self.assertNotIn('private-lease',json.dumps(receipt))
                self.assertEqual(json.loads((root/'status.json').read_text())['execution_receipt'],str(root/'host/execution.json'))
            finally:
                for run in (parent,child):
                    if not run.events.closed:run.finish('failed')


if __name__=='__main__':unittest.main()
