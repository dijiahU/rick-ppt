"""Role handoff, single-pass feedback and exact native baseline recovery.

Offline fixtures only. No model, account, queue, aesthetic score or target playback.
"""
import copy,hashlib,json,tempfile,unittest,sys,importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from design_roles import role_contract,handoff_index,role_instruction
from design_feedback import mark_response,optional_response,host_authorized_response,capture_metadata,restore_baseline,save_baseline,load_baseline
from phase_context import prepared_phase_context,MAX_DOCUMENT
from workflow import _run_workflow,_rollback_designer_response
from progress import Reporter
from resilience import TaskPaused,HeartbeatLost,WorkerHTTPError
from conversation import RevisionPending
from durable import JournalError
from review_sessions import ReviewSessionError
from repair_recovery import _findings_valid

ROOT=Path(__file__).resolve().parents[1]

class RoleTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
  self.job=self.root/'job';self.job.mkdir();self.plugin=self.root/'plugin';self.skill=self.plugin/'skills/pptx'
  (self.skill/'scripts').mkdir(parents=True);(self.skill/'references').mkdir()
  (self.skill/'scripts/planning_commit.py').write_text('# admitted helper')
  (self.skill/'references/art-direction.md').write_text('HOST DESIGN METHOD')
  (self.skill/'references/art-direction-examples.md').write_text('OPTIONAL EXAMPLE BODY')
  (self.skill/'SKILL.md').write_text('HOST SKILL')
  self.cfg={'plugin':str(self.plugin),'token':'SYNTHETIC-HOST-SECRET','_model_profile':{'api_key':'SYNTHETIC-PROVIDER-SECRET'}}
  (self.job/'request.json').write_text(json.dumps({'mode':'create','title':'Mechanism','pages':2,'language':'en'}))
  (self.job/'outline.json').write_text(json.dumps({'slides':[{'id':'width','title':'Width','summary':'Share the evidence pool; no online score.'}]}))
  (self.job/'source-notes.md').write_text('k = 1 excludes the selector. 42 ± 2 score points; illustrative only. R_t stays fixed.')
  (self.job/'decision-plan.json').write_text(json.dumps({'version':4,'design_direction':'Inspect the changing state','template_preservation':['Keep logo only']}))
 def packet(self,stage):
  text=prepared_phase_context(self.cfg,self.job,stage)
  return json.loads(text[text.index('{"stage"'):])
 def test_roles_receive_exact_evidence_without_private_runtime_or_example_bloat(self):
  research=self.packet('research');author=self.packet('author')
  self.assertEqual(research['role_contract']['role'],'content_researcher_editor')
  self.assertEqual(author['role_contract']['role'],'continuing_deck_designer_author')
  self.assertFalse(any(Path(d['path']).name in ('source-notes.md','art-direction.md') for d in research['documents']))
  note=next(d for d in author['documents'] if Path(d['path']).name=='source-notes.md')
  self.assertEqual(note['content'],(self.job/'source-notes.md').read_text())
  self.assertEqual(author['handoff']['inputs']['source-notes.md']['sha256'],hashlib.sha256((self.job/'source-notes.md').read_bytes()).hexdigest())
  self.assertTrue(any(Path(d['path']).name=='art-direction.md' for d in author['documents']))
  for text in [json.dumps(research),json.dumps(author)]:
   for absent in ['SYNTHETIC-HOST-SECRET','SYNTHETIC-PROVIDER-SECRET']:self.assertNotIn(absent,text)
  self.assertNotIn('OPTIONAL EXAMPLE BODY',json.dumps(research))
  self.assertIn('OPTIONAL EXAMPLE BODY',json.dumps(author))
  self.assertNotIn('OPTIONAL EXAMPLE BODY',json.dumps(self.packet('repair')))
 def test_partial_and_oversized_evidence_stays_available_without_invented_summaries(self):
  original=b'{"version":4,"pages":[';(self.job/'decision-plan.json').write_bytes(original)
  value=self.packet('repair');self.assertEqual(value['handoff']['inputs']['decision-plan.json']['state'],'partial')
  self.assertEqual((self.job/'decision-plan.json').read_bytes(),original)
  (self.job/'source-notes.md').write_text('evidence '*MAX_DOCUMENT)
  value=self.packet('author');self.assertEqual(value['handoff']['inputs']['source-notes.md']['state'],'deferred')
  self.assertFalse(any(Path(d['path']).name=='source-notes.md' for d in value['documents']))
 def test_source_index_does_not_collide_with_prefetch_index(self):
  docs=[{'path':'/job/references/index.json','kind':'task_data','sha256':'actual-source','complete':True},
        {'path':'/job/material-prefetch/index.json','kind':'task_data','sha256':'material-status','complete':True}]
  self.assertEqual(handoff_index(docs,[],'research')['inputs']['references/index.json']['sha256'],'actual-source')
 def test_context_assembly_does_not_write_pages_or_invent_design_schema(self):
  before={p.relative_to(self.job).as_posix():p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
  for stage in ['research','author','repair']:self.packet(stage)
  self.assertEqual(before,{p.relative_to(self.job).as_posix():p.read_bytes() for p in self.job.rglob('*') if p.is_file()})
  self.assertEqual(json.loads((self.job/'decision-plan.json').read_text())['version'],4)
 def test_legacy_plugin_receives_no_role_requirement(self):
  (self.skill/'references/art-direction.md').unlink()
  self.assertIsNone(role_contract(self.cfg,'author'));self.assertNotIn('role_contract',self.packet('author'))
 def test_pinned_older_plugin_does_not_advertise_uninstalled_page_tools(self):
  for stage in ['research','author','repair']:
   self.assertNotIn('page_design',role_instruction(self.cfg,stage))
  (self.skill/'scripts/page_design.py').write_text('# actual installed capability')
  for stage in ['research','author','repair']:
   self.assertIn('page_design',role_instruction(self.cfg,stage))


def report():return {'summary':'Actual audience review','pages_reviewed':[1,2],'limitations':['Playback not tested'],'findings':[]}
def receipt(body,number=1):
 v={'artifact_sha256':hashlib.sha256(body).hexdigest(),'round':number,'input_revision':0,'plugin_version':'fixture-version','review_mode':'substantive','content_first_view':report(),'content':report(),'visual':report()}
 v['visual']['findings']=[{'id':'F1','severity':'suggestion','pages':[2],'observation':'Two relationships look the same.','impact':'They require prose reconstruction.','recommendation':'Differentiate the relationships; preserve source conditions and click grouping.','route':'retain_suggestion'}]
 return v

class FeedbackTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name).resolve();self.job=self.root/'job';self.job.mkdir()
  self.plugin=self.root/'plugin';guide=self.plugin/'skills/pptx/references/art-direction.md';guide.parent.mkdir(parents=True);guide.write_text('Fixture method')
  self.cfg={'plugin':str(self.plugin),'python':sys.executable,'single_file_pptx':True}
  self.task={'id':'designer-fixture','pages':2,'title':'Mechanism','brief':'Explain both mechanisms clearly','style':'Designer choice','language':'en'}
  self.outline={'title':'Mechanism','purpose':'Understand two changes','slides':[{'id':'first','title':'Question','summary':'Establish the question and shared context.'},{'id':'second','title':'Mechanisms','summary':'Show the difference without an online score.'}]}
  (self.job/'outline.json').write_text(json.dumps(self.outline));(self.job/'source-notes.md').write_text('Keep the qualified conditions.')
  (self.job/'original.pptx').write_bytes(b'PLUMBING FIXTURE: ORIGINAL; NO NATIVE CLAIM')
  (self.job/'delivery.json').write_text(json.dumps({'path':'original.pptx'}))
  self.records=self.root/'records';self.records.mkdir();self.frozen=self.root/'frozen';self.frozen.mkdir();self.pages=[]
  for n in [1,2]:p=self.frozen/f'page-{n}.png';p.write_bytes(b'PLUMBING PNG');self.pages.append(str(p))
  self.calls=[];self.action='noop'
  def delivery():return json.loads((self.job/'delivery.json').read_text())
  def current():return (self.job/delivery()['path']).read_bytes()
  def phase(name,prompt,**options):
   self.calls.append((name,options))
   self.assertEqual(options['thread'],'continuing-designer')
   if self.action=='fail':raise TimeoutError('Synthetic optional deadline')
   if self.action=='pause':raise TaskPaused('Owner stop')
   if self.action=='change':
    (self.job/'changed.pptx').write_bytes(b'PLUMBING FIXTURE: CHANGED')
    (self.job/'delivery.json').write_text(json.dumps({'path':'changed.pptx'}))
  def review(body,rendered,packet,payload,number):
   for kind in ('content','visual'):self.reporter.review_state(kind,'passed')
   return mark_response(self.cfg,receipt(body,number),scoped=False)
  self.run=SimpleNamespace(cfg=self.cfg,task=self.task,job=self.job,conversation=None,journal=None,author_thread='continuing-designer',
   reusable_author=lambda:True,reusable=lambda stage:False,review_tick=Mock(),freeze=Mock(side_effect=lambda:(current(),self.frozen,{'pages':self.pages},self.frozen/'packet')),
   review=Mock(side_effect=review),phase=phase,delivery=delivery,complete_phase=Mock(),records=self.records,images={},logs=[],interactive_verification=None)
  self.reporter=Reporter(self.cfg,self.task,self.job,lambda *args:None,explicit_previews=True)
 def execute(self):return _run_workflow(self.run,SimpleNamespace(),self.cfg,self.task,self.job,{'mode':'create'},SimpleNamespace(check=lambda:None),self.reporter)
 def fake_restore(self,run,body,review,metadata,**options):
  (run.job/'restored.pptx').write_bytes(body)
  for name,data in metadata.items():
   if data is None:(run.job/name).unlink(missing_ok=True)
   else:(run.job/name).write_bytes(data)
  (run.job/'delivery.json').write_text(json.dumps({'path':'restored.pptx'}))
  return ['restored.pptx','delivery.json']
 def test_host_marks_only_first_full_review_and_preserves_optional_severity(self):
  v=mark_response(self.cfg,receipt(b'x'),scoped=False);self.assertTrue(optional_response(v));self.assertTrue(_findings_valid(v,1,v['artifact_sha256']))
  self.assertEqual(v['visual']['findings'][0]['severity'],'suggestion')
  for number,scoped in [(2,False),(1,True)]:self.assertFalse(optional_response(mark_response(self.cfg,receipt(b'x',number),scoped=scoped)))
  v.pop('plugin_version');self.assertFalse(host_authorized_response(v))
 def test_noop_reuses_reviewed_bytes_and_does_not_repeat_review(self):
  result,_=self.execute();self.assertEqual(result['artifact'],(self.job/'original.pptx').read_bytes())
  self.assertEqual([n for n,_ in self.calls],['repair-1']);self.assertEqual(self.run.review.call_count,1)
  self.assertEqual(self.calls[0][1]['timeout'],360)
 def test_changed_file_is_reviewed_again_without_a_second_optional_pass(self):
  self.action='change';result,r=self.execute()
  self.assertEqual(self.run.review.call_count,2);self.assertEqual([n for n,_ in self.calls],['repair-1'])
  self.assertEqual(r['artifact_sha256'],hashlib.sha256(result['artifact']).hexdigest())
 def test_failed_optional_polish_delivers_exact_reviewed_baseline(self):
  self.action='fail'
  def restore(run,body,receipt,metadata,**options):
   self.assertEqual(metadata['source-notes.md'],b'Keep the qualified conditions.')
   (self.job/'restored.pptx').write_bytes(body);(self.job/'delivery.json').write_text(json.dumps({'path':'restored.pptx'}));return ['restored.pptx','delivery.json']
  with patch('design_feedback.restore_baseline',side_effect=restore) as fallback:result,_=self.execute()
  fallback.assert_called_once();self.assertEqual(result['artifact'],(self.job/'original.pptx').read_bytes());self.assertEqual(self.run.review.call_count,1)
 def test_user_stop_is_not_swallowed_by_optional_fallback(self):
  self.action='pause'
  with patch('design_feedback.restore_baseline') as fallback:
   with self.assertRaises(TaskPaused):self.execute()
   fallback.assert_not_called()
 def test_new_revision_cannot_fall_back_to_a_stale_review(self):
  def changed_input(*a,**k):
   self.task['input_revision']=1
   raise TimeoutError('Synthetic optional deadline')
  self.run.phase=changed_input
  with patch('design_feedback.restore_baseline') as fallback:
   with self.assertRaises(RevisionPending):self.execute()
   fallback.assert_not_called()
 def test_required_regression_after_optional_change_restores_accepted_bytes_and_review(self):
  self.action='change';original=self.run.review.side_effect
  def regress(*args):
   value=original(*args)
   if args[-1]==2:
    value['visual']['findings'][0]['severity']='required'
    self.reporter.review_state('visual','changes_requested')
    (self.job/'source-notes.md').write_text('Failed design attempt metadata')
   return value
  self.run.review.side_effect=regress
  with patch('design_feedback.restore_baseline',side_effect=self.fake_restore) as fallback:
   result,review=self.execute()
  fallback.assert_called_once()
  self.assertEqual([name for name,_ in self.calls],['repair-1'])
  self.assertEqual(self.run.review.call_count,2)
  self.assertEqual(result['artifact'],(self.job/'original.pptx').read_bytes())
  self.assertEqual(review['round'],1);self.assertEqual(self.reporter.reviews,{'content':'passed','visual':'passed'})
  self.assertEqual((self.job/'source-notes.md').read_text(),'Keep the qualified conditions.')
  self.assertTrue(load_baseline(self.run)['rolled_back'])
 def test_failed_recheck_after_optional_change_restores_accepted_bytes(self):
  self.action='change';original=self.run.review.side_effect
  def review(*args):
   if args[-1]==2:raise TimeoutError('Independent recheck transport expired')
   return original(*args)
  self.run.review.side_effect=review
  with patch('design_feedback.restore_baseline',side_effect=self.fake_restore):result,_=self.execute()
  self.assertEqual(result['artifact'],(self.job/'original.pptx').read_bytes())
  self.assertEqual(self.run.review.call_count,2)
 def test_control_and_integrity_errors_are_never_optional_fallbacks(self):
  for error in (TaskPaused('stop'),RevisionPending('new revision'),HeartbeatLost('lease expired'),
                WorkerHTTPError('heartbeat',status=409),JournalError('journal invalid'),ReviewSessionError('identity changed')):
   with self.subTest(error=type(error).__name__):
    self.run.phase=Mock(side_effect=error)
    with patch('design_feedback.restore_baseline') as fallback:
     with self.assertRaises(type(error)):self.execute()
     fallback.assert_not_called()
 def test_decision_validation_does_not_change_authoritative_review_envelope(self):
  self.action='change';original=self.run.review.side_effect;host=[]
  def review(*args):
   value=original(*args);host.append(copy.deepcopy(value));return value
  self.run.review.side_effect=review
  with patch('workflow.check_decisions',return_value={'decision_plan_sha256':'fixture-validation'}):result,review=self.execute()
  findings=json.loads(next(self.job.glob('review-findings-1-*.json')).read_text())
  self.assertEqual(findings,host[0]);self.assertNotIn('decision_validation',review)
  records=[json.loads(p.read_text()) for p in self.job.glob('decision-validation-*.json')]
  self.assertEqual(len(records),2)
  self.assertEqual(records[-1]['validation']['decision_plan_sha256'],'fixture-validation')
  self.assertIn(hashlib.sha256(result['artifact']).hexdigest(),[v['artifact_sha256'] for v in records])
 def test_revision_or_stop_arriving_during_restore_prevents_commit(self):
  for stop in (False,True):
   with self.subTest(stop=stop):
    self.task.pop('input_revision',None);self.action='fail'
    def restore(*args,**kwargs):
     result=self.fake_restore(*args,**kwargs)
     if stop:self.run.review_tick.side_effect=TaskPaused('Owner stopped during native restore')
     else:self.task['input_revision']=1
     return result
    with patch('design_feedback.restore_baseline',side_effect=restore):
     with self.assertRaises(TaskPaused if stop else RevisionPending):self.execute()
    self.run.complete_phase.assert_not_called()
    self.assertFalse(next(self.records.glob('*-designer-baseline-*')).joinpath('outcome.json').exists())
    self.run.review_tick.side_effect=None

class DurableOptionalTests(unittest.TestCase):
 def fixture(self,*,completed=False,persist=False):
  spec=importlib.util.spec_from_file_location('designer_durable_fixture',Path(__file__).with_name('test-repair-recovery.py'))
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  fixture=m.RepairRecoveryTests(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
  original=m.findings
  def optional(*a,**k):
   v=original(*a,**k);v['review_mode']='substantive';v['content']['findings'][0]['severity']='suggestion'
   v['visual']['findings']=[copy.deepcopy(v['content']['findings'][0])]
   v['designer_response']={'version':1,'max_passes':1};return v
  with patch.object(m,'findings',side_effect=optional):fixture.seed(phase='repair',completed=completed)
  if persist:
   guide=fixture.plugin/'skills/pptx/references/art-direction.md';guide.parent.mkdir(parents=True);guide.write_text('Fixture design method')
   pages=[]
   for n in (1,2):
    page=fixture.root/f'baseline-{n}.png';page.write_bytes(b'OFFLINE BASELINE PNG');pages.append(str(page))
   save_baseline(SimpleNamespace(records=fixture.records,job=fixture.job,task=fixture.task,journal=fixture.journal),
                 fixture.original,fixture.receipt,{'pages':pages},{'content':'passed','visual':'unverified'})
  return m,fixture
 def fake_restore(self,run,body,review,metadata,**options):
  return FeedbackTests.fake_restore(self,run,body,review,metadata,**options)
 def test_optional_repair_recovers_from_matching_host_receipt(self):
  m,f=self.fixture();run,bridge,reporter=f.restore()
  route=__import__('repair_recovery').recovery_route(f.journal,run.job,records=f.records,task_id=f.task['id'])
  self.assertEqual(route.repair_round,1);self.assertEqual(route.repair_thread,'interrupted-repair-thread')
 def test_task_only_suggestion_marker_is_not_recovery_authority(self):
  m,f=self.fixture();f.host_record.unlink();run,bridge,reporter=f.restore()
  route=__import__('repair_recovery').recovery_route(f.journal,run.job,records=f.records,task_id=f.task['id'])
  self.assertTrue(route.block_author);self.assertIsNone(route.repair_round)
 def test_resumed_optional_disconnect_delivers_exact_host_baseline(self):
  m,f=self.fixture(persist=True);run,bridge,reporter=f.restore()
  with patch('design_feedback.restore_baseline',side_effect=self.fake_restore) as fallback:
   result,review=f.execute(run,bridge,reporter,fail='repair-1')
  fallback.assert_called_once();self.assertEqual(result['artifact'],f.original)
  self.assertEqual(review,f.receipt);self.assertEqual(run.review.call_count,0)
  self.assertEqual([(x[0],x[1]) for x in f.calls],[('repair-1','interrupted-repair-thread')])
  self.assertTrue((run.job/'retained-failure.txt').is_file());self.assertTrue((run.job/'partial-work.txt').is_file())
  self.assertEqual(reporter.reviews,{'content':'passed','visual':'unverified'})
  self.assertTrue(load_baseline(run)['rolled_back'])
  details=[call.kwargs.get('detail') for call in run.trace.emit.call_args_list]
  self.assertTrue(any(isinstance(detail,dict) and detail.get('artifactSha256')==review['artifact_sha256'] for detail in details))
 def test_completed_optional_repair_resumes_at_recheck_and_rolls_back_new_required(self):
  m,f=self.fixture(completed=True,persist=True);run,bridge,reporter=f.restore()
  def review(body,rendered,packet,payload,number):
   self.assertEqual(number,2);value=copy.deepcopy(f.receipt)
   value['artifact_sha256']=hashlib.sha256(body).hexdigest();value['round']=number
   value['visual']['findings'][0]['severity']='required';reporter.review_state('visual','changes_requested')
   return value
  run.review.side_effect=review
  with patch('design_feedback.restore_baseline',side_effect=self.fake_restore):result,review=f.execute(run,bridge,reporter)
  self.assertEqual(result['artifact'],f.original);self.assertEqual(review,f.receipt)
  self.assertEqual(f.calls,[]);self.assertEqual(run.review.call_count,1)
  self.assertTrue((run.job/'repaired.pptx').is_file())
  # A further process loss reuses the committed, reviewed delivery itself.
  recovered,bridge,reporter=f.restore()
  # This fixture deliberately uses non-ZIP plumbing bytes. Native package
  # validation is independently exercised by NativeBaselineTests below.
  with patch('office_policy.validate_delivery'):result,review=f.execute(recovered,bridge,reporter)
  self.assertEqual(result['artifact'],f.original);self.assertTrue(result['reused_validated_delivery'])
  self.assertEqual(recovered.review.call_count,0)
 def test_resumed_optional_pause_keeps_recovery_pending(self):
  m,f=self.fixture(persist=True);run,bridge,reporter=f.restore()
  with patch('workflow._repair_candidate',side_effect=TaskPaused('Owner stop')),patch('design_feedback.restore_baseline') as fallback:
   with self.assertRaises(TaskPaused):f.execute(run,bridge,reporter)
  fallback.assert_not_called();self.assertFalse(load_baseline(run)['rolled_back'])

class NativeBaselineTests(unittest.TestCase):
 def test_workflow_rollback_uses_native_unpack_and_refreshes_actual_manifest(self):
  sys.path.insert(0,str(ROOT/'pptx-agent/skills/pptx/scripts'))
  from pptx_core.package import unpack
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary).resolve();job=root/'task';job.mkdir();records=root/'records';records.mkdir()
   cfg={'plugin':str(ROOT/'pptx-agent'),'python':sys.executable}
   task={'id':'native-designer-transaction','pages':1}
   plan={'title':'Native recovery','purpose':'Restore accepted native objects','slides':[{'id':'one','title':'Native state','summary':'Preserve the exact reviewed package and editable object tree.'}]}
   (job/'outline.json').write_text(json.dumps(plan));(job/'source-notes.md').write_text('Accepted source qualifiers')
   original=(ROOT/'pptx-agent/skills/pptx/assets/blank.pptx').read_bytes();review=mark_response(cfg,receipt(original),scoped=False)
   for key in ('content_first_view','content','visual'):review[key]['pages_reviewed']=[1]
   review['visual']['findings'][0]['pages']=[1]
   png=root/'page-1.png';png.write_bytes(b'OFFLINE PNG; NO VISUAL QUALITY CLAIM')
   ticks=[]
   def run_check(where,command,**options):
    options['tick']();ticks.append(command)
    return json.dumps({'workspace':str(unpack(Path(command[3]),Path(command[5])).root)})
   run=SimpleNamespace(cfg=cfg,task=task,job=job,records=records,journal=None,conversation=None,
                       author_thread='continuing-designer',review_tick=Mock(),run_check=run_check,complete_phase=Mock(),trace=Mock())
   baseline=save_baseline(run,original,review,{'pages':[str(png)]},{'content':'passed','visual':'unverified'})
   (job/'failed.pptx').write_bytes(b'Preserved failed native export')
   (job/'source-notes.md').write_bytes(b'Failed optional metadata'*150000)
   (job/'delivery.json').write_text(json.dumps({'path':'failed.pptx'}))
   reporter=Reporter(cfg,task,job,lambda *args:None,explicit_previews=True)
   result=_rollback_designer_response(run,SimpleNamespace(sandbox=lambda cfg,job,cmd:cmd),cfg,job,SimpleNamespace(check=lambda:None),reporter,baseline)
   delivery=json.loads((job/'delivery.json').read_text());manifest=json.loads((job/'tool-manifest.json').read_text())
   self.assertEqual(result[0],original);self.assertEqual(Path(delivery['path']).read_bytes(),original)
   self.assertEqual(manifest['parts_dir'],delivery['workspace']);self.assertEqual(len(ticks),1)
   self.assertEqual((job/'source-notes.md').read_text(),'Accepted source qualifiers')
   self.assertGreater(next(job.glob('designer-fallback-*/attempted-source-notes.md')).stat().st_size,2*1024*1024)
   self.assertEqual((job/'failed.pptx').read_bytes(),b'Preserved failed native export')
   self.assertEqual(reporter.reviews,{'content':'passed','visual':'unverified'})
 def test_failed_work_is_retained_and_actual_native_state_restored(self):
  sys.path.insert(0,str(ROOT/'pptx-agent/skills/pptx/scripts'))
  from pptx_core.package import unpack
  with tempfile.TemporaryDirectory() as temporary:
   job=Path(temporary).resolve();cfg={'plugin':str(ROOT/'pptx-agent'),'python':sys.executable}
   original=(ROOT/'pptx-agent/skills/pptx/assets/blank.pptx').read_bytes();v=receipt(original)
   (job/'outline.json').write_text('{"original":true}');(job/'source-notes.md').write_text('Verified 42 ± 2 score points')
   metadata=capture_metadata(job);(job/'source-notes.md').write_text('FAILED ATTEMPT NOTES');(job/'partial-native-edit.txt').write_text('Keep failed work')
   calls=[]
   def native(source,base):return {'workspace':str(unpack(source,base).root)}
   files=restore_baseline(SimpleNamespace(job=job,cfg=cfg,task={'id':'native-fixture'}),original,v,metadata,unpack=native,prepare=lambda *a,**k:calls.append(k))
   delivery=json.loads((job/'delivery.json').read_text());self.assertEqual(Path(delivery['path']).read_bytes(),original)
   self.assertEqual((job/'source-notes.md').read_bytes(),metadata['source-notes.md']);self.assertEqual((job/'partial-native-edit.txt').read_text(),'Keep failed work')
   self.assertEqual(calls[0]['workspace'],delivery['workspace']);self.assertTrue(Path(delivery['workspace']).is_dir())
   status=json.loads(next(job.glob('designer-fallback-*/designer-response.json')).read_text());self.assertEqual(status['status'],'not_applied')
   self.assertEqual(next(job.glob('designer-fallback-*/attempted-source-notes.md')).read_text(),'FAILED ATTEMPT NOTES')
   self.assertTrue(all((job/f).is_file() for f in files))
   with self.assertRaises(ValueError):restore_baseline(SimpleNamespace(job=job,cfg=cfg,task={'id':'native-fixture'}),original,{**v,'artifact_sha256':'0'*64},metadata,unpack=native)

if __name__=='__main__':unittest.main()
