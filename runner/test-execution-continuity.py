"""Offline file/transport tests: continuity never certifies design or delivery."""
import hashlib
import json
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import workflow
from durable import Journal, RPCError
from execution_continuity import (OutputProgress, ProgressStalled, compact_resume,
                                  fresh_prompt, same_phase_recovery, inbox_clear,declared_output)
from phase_context import prepared_phase_context
from progress import Reporter
from resilience import TaskPaused

REPO = Path(__file__).resolve().parents[1]
PYTHON = '/Users/rick/Desktop/ppt/pptx-agent/.venv/bin/python'


class Files(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.job = self.root/'job'; self.job.mkdir()
        self.records = self.root/'records'; self.records.mkdir()

    def guard(self, name='author'):
        return OutputProgress(self.job,self.records,'task',name,0,window=4)

    def actions(self, guard, count=4, start=0):
        for n in range(start,start+count):
            guard.observe({'type':'item.completed','thread_id':'t','turn_id':'u',
                           'item':{'id':str(n),'type':'image_view'}})
        return guard.action()

    def test_waits_and_inspection_do_not_prove_outputs(self):
        g=self.guard()
        for _ in range(50):self.assertIsNone(g.action())
        (self.job/'tmp').mkdir();(self.job/'tmp/crop.png').write_bytes(b'crop')
        self.assertEqual(self.actions(g),'nudge');g.applied('nudge')
        self.assertEqual(self.actions(g,start=4),'rebuild');g.applied('rebuild')
        g=self.guard()
        self.assertEqual(self.actions(g,start=8),'stalled')

    def test_native_changes_and_research_notes_reset_counter_without_mutation(self):
        for role,path in [('author','parts/ppt/slides/slide1.xml'),('research','source-notes.md')]:
            g=self.guard(role);self.assertEqual(self.actions(g),'nudge');g.applied('nudge')
            p=self.job/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'actual saved content')
            before=p.read_bytes();self.assertIsNone(self.actions(g,start=4))
            self.assertEqual(g.state['quiet_actions'],0);self.assertEqual(p.read_bytes(),before)

    def test_active_and_yielded_shell_wait_for_real_terminal_receipt(self):
        g=self.guard();event={'thread_id':'t','turn_id':'u','item':{'id':'shell','type':'command_execution','exit_code':None}}
        g.observe({**event,'type':'item.started'})
        self.assertIsNone(self.actions(g))
        g.observe({**event,'type':'item.completed'})
        self.assertIsNone(g.action(missing_outputs=True))
        g.observe({**event,'type':'item.completed','item':{**event['item'],'exit_code':0}})
        self.assertEqual(g.action(),'nudge')

    def test_duplicate_completed_events_count_once(self):
        g=self.guard()
        for _ in range(30):self.actions(g,count=1)
        self.assertEqual(g.state['quiet_actions'],1)

    def test_unstable_zip_defers_without_erasing_evidence(self):
        p=self.job/'candidate.pptx';p.write_bytes(b'partial ZIP')
        g=self.guard();self.assertIsNone(self.actions(g))
        self.assertEqual(p.read_bytes(),b'partial ZIP')

    def test_resume_is_short_revision_bound_and_current_files_are_unchanged(self):
        (self.job/'source-notes.md').write_text('evidence '*5000)
        before=(self.job/'source-notes.md').read_bytes()
        text=compact_resume(self.job,'author')
        self.assertLess(len(text),2500);self.assertNotIn('evidence evidence',text)
        self.assertIn(hashlib.sha256(before).hexdigest(),text)
        self.assertEqual((self.job/'source-notes.md').read_bytes(),before)
        state={'input_revision':2,'phase':{'name':'author','thread_id':'old','status':'interrupted','input_revision':2}}
        self.assertTrue(same_phase_recovery(state,'author','old'))
        self.assertFalse(same_phase_recovery(state,'repair-1','old'))
        state['input_revision']=3;self.assertFalse(same_phase_recovery(state,'author','old'))

    def test_fresh_prompt_refreshes_saved_documents_and_preserves_requirements(self):
        cfg={'plugin':str(REPO/'pptx-agent')}
        (self.job/'source-notes.md').write_text('OLD_FINDING')
        original='EXPLICIT PRESERVED REQUIREMENT'+prepared_phase_context(cfg,self.job,'author')
        (self.job/'source-notes.md').write_text('CURRENT_FINDING')
        fresh=fresh_prompt(cfg,self.job,'author',original,'conversation-inputs/current.json')
        self.assertIn('EXPLICIT PRESERVED REQUIREMENT',fresh);self.assertIn('CURRENT_FINDING',fresh)
        self.assertNotIn('OLD_FINDING',fresh);self.assertIn('conversation-inputs/current.json',fresh)

    def test_declared_handoff_uses_only_trusted_recovery_alias_and_restored_bytes(self):
        old=self.root/'old';old.mkdir();(old/'candidate.pptx').write_bytes(b'never read this historical file')
        current=self.job/'candidate.pptx'
        with zipfile.ZipFile(current,'w') as z:
            z.writestr('[Content_Types].xml','<Types/>');z.writestr('ppt/presentation.xml','<presentation/>')
        (self.job/'delivery.json').write_text(json.dumps({'path':str(old/'candidate.pptx')}))
        self.assertIsNone(declared_output(self.job))
        found=declared_output(self.job,[{'previous_workspace':str(old),'workspace':str(self.job)}])
        self.assertEqual(found['sha256'],hashlib.sha256(current.read_bytes()).hexdigest())
        self.assertEqual((old/'candidate.pptx').read_bytes(),b'never read this historical file')


class Phase(unittest.TestCase):
    def run_phase(self, mode='rebuild', resume=False, missing_thread=False, name='research', pause=False,
                  revision_at_reset=False, bad_receipt=False, reject_steer=False,allow_handoff=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);job=root/'job';job.mkdir()
        for name_ in ('media-requests','font-requests','render-requests','tmp'):(job/name_).mkdir()
        task={'id':str(uuid.uuid4()),'lease':'fake-lease'}
        cfg={'token':'fake-token','plugin':str(REPO/'pptx-agent'),'python':PYTHON,
             'progress_action_window':4}
        if allow_handoff:cfg['_allow_declared_author_handoff']=True
        bridge=SimpleNamespace(ROOT=root,environment=lambda root:{},request=lambda *a,**k:{'ok':True},render_requests=Mock())
        reporter=Reporter(cfg,task,job,bridge.request,explicit_previews=True)
        journal=Journal(root/'state',task['id'],plugin_version='test');self.addCleanup(journal.close)
        if resume:
            journal.begin_phase(name,job,thread_id='old');journal.interrupt()
        run=workflow.Execution(bridge,cfg,task,job,SimpleNamespace(check=lambda:None),reporter,journal=journal)
        self.addCleanup(run.trace.close)
        conversation=Mock();conversation.context.return_value=None;run.conversation=conversation
        if pause:conversation.poll.side_effect=TaskPaused('Owner stopped')
        run.prefetch=Mock()
        observed=[]
        class Server:
            def __init__(self,**kw):
                self.kw=kw;self.active_turns={};self.completed_turns={};self.threads=[];self.prompts=[]
                self.steps=0;self.turns=0;self.steers=0;self.interrupts=0;observed.append(self)
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def start_thread(self,**kwargs):
                thread='new-'+str(len(self.threads));self.threads.append(thread)
                return {'thread':{'id':thread}}
            def resume_thread(self,thread):
                if missing_thread:raise RPCError('thread/resume',{'code':-32602,'message':'missing'})
                self.threads.append(thread);return {'thread':{'id':thread}}
            def start_turn(self,thread,prompt,**kw):
                self.turns+=1;turn='turn-'+str(self.turns);self.active_turns[thread]=turn
                self.prompts.append(prompt);return {'id':turn}
            def steer(self,*args,**kw):
                self.steers+=1
                if reject_steer and self.steers==1:raise RPCError('turn/steer',{'code':-32000,'message':'compacting'})
                return {'turnId':'receipt'}
            def interrupt(self,thread,turn):self.interrupts+=1;return {'ok':True}
            def wait_turn(self,thread,turn,**kw):
                self.kw['tick']()
                self.active_turns.pop(thread,None);receipt={'status':'failed' if bad_receipt else 'interrupted'}
                self.completed_turns[(thread,turn)]=receipt;return receipt
            def pump(self,timeout):
                self.kw['tick']();self.steps+=1
                if self.steps>50:raise AssertionError('Fake model exceeded bounded execution')
                if mode=='handoff' and self.steps==1:
                    artifact=job/'declared.pptx'
                    with zipfile.ZipFile(artifact,'w') as z:
                        z.writestr('[Content_Types].xml','<Types/>')
                        z.writestr('ppt/presentation.xml','<presentation/>')
                        z.writestr('ppt/slides/slide1.xml','<slide/>')
                    (job/'delivery.json').write_text(json.dumps({'path':str(artifact)}))
                thread,turn=next(iter(self.active_turns.items()))
                if mode=='missing' and self.turns==1:
                    self.finish(thread,turn);return
                if mode=='complete' or mode=='missing' and self.turns>1 or mode=='rebuild' and len(self.threads)>1:
                    for n in ('outline.json','source-notes.md','decision-plan.json'):(job/n).write_text('retained output')
                    self.finish(thread,turn);return
                self.kw['on_event']({'type':'item.completed','thread_id':thread,'turn_id':turn,
                                     'item':{'id':'image-'+str(self.steps),'type':'image_view'}})
            def finish(self,thread,turn):
                self.active_turns.pop(thread);self.completed_turns[(thread,turn)]={'status':'completed'}
            def result_text(self,*args):return 'finished'
        prompt='PRESERVED_REQUIREMENT'+prepared_phase_context(cfg,job,'research')
        error=None;result=None
        if revision_at_reset:
            def poll(**kw):
                if observed and observed[0].interrupts:
                    journal.accept_message('new-revision','Preserve new requirement',cursor=1,changes_input=True)
            conversation.poll.side_effect=poll
        with patch.object(workflow,'AppServer',Server):
            try:result=run.phase(name,prompt,thread='old' if resume else None)
            except Exception as e:error=e
        return observed[0],result,error,journal,job

    def test_actual_orchestration_nudges_then_rebuilds_once_and_keeps_files(self):
        s,result,error,journal,job=self.run_phase()
        self.assertIsNone(error);self.assertEqual(result[0],'finished')
        self.assertEqual((s.steers,s.interrupts,len(s.threads)),(1,1,2))
        self.assertIn('PRESERVED_REQUIREMENT',s.prompts[-1]);self.assertTrue((job/'outline.json').is_file())
        self.assertEqual(journal.state['phase']['thread_id'],s.threads[-1])

    def test_permanent_nonproduction_stops_after_one_reset(self):
        s,_,error,_,_=self.run_phase(mode='stalled')
        self.assertIsInstance(error,ProgressStalled);self.assertEqual(len(s.threads),2)

    def test_completed_valid_handoff_does_not_get_extra_turn(self):
        s,_,error,_,_=self.run_phase(mode='complete')
        self.assertIsNone(error);self.assertEqual(s.turns,1);self.assertEqual(s.steers,0)

    def test_terminal_missing_handoff_requests_one_continuation(self):
        s,_,error,_,_=self.run_phase(mode='missing')
        self.assertIsNone(error);self.assertEqual(s.turns,2);self.assertEqual(len(s.threads),1)

    def test_recovery_compact_but_missing_thread_fallback_has_full_requirements(self):
        s,_,error,_,_=self.run_phase(mode='complete',resume=True)
        self.assertIsNone(error);self.assertTrue(s.prompts[0].startswith('HOST PHASE CONTINUATION'))
        s,_,error,_,_=self.run_phase(mode='complete',resume=True,missing_thread=True)
        self.assertIsNone(error);self.assertIn('PRESERVED_REQUIREMENT',s.prompts[0])
        self.assertIn('HOST-PREPARED CURRENT PHASE DOCUMENTS',s.prompts[0])

    def test_owner_stop_takes_precedence_without_context_rebuild(self):
        s,_,error,_,_=self.run_phase(pause=True)
        self.assertIsInstance(error,TaskPaused);self.assertEqual(len(s.threads),1)
        self.assertEqual(s.interrupts,0)

    def test_reviews_are_not_subject_to_output_guard(self):
        s,_,error,_,_=self.run_phase(mode='missing',name='visual-1')
        self.assertIsNone(error);self.assertEqual(s.turns,1)

    def test_acknowledged_or_uncertain_user_delivery_blocks_reset(self):
        for state in ('accepted','delivering','uncertain','acknowledged'):
            self.assertFalse(inbox_clear(SimpleNamespace(state={'inbox':{'m':{'state':state}}})))
        self.assertTrue(inbox_clear(SimpleNamespace(state={'inbox':{'m':{'state':'applied'}}})))

    def test_user_revision_arriving_at_interrupt_is_preserved_without_new_context(self):
        from conversation import RevisionPending
        s,_,error,journal,_=self.run_phase(revision_at_reset=True)
        self.assertIsInstance(error,RevisionPending);self.assertEqual(len(s.threads),1)
        self.assertEqual(journal.state['inbox']['new-revision']['state'],'accepted')

    def test_reset_requires_actual_successful_terminal_receipt(self):
        s,_,error,_,_=self.run_phase(bad_receipt=True)
        self.assertIsInstance(error,RuntimeError);self.assertEqual(len(s.threads),1)

    def test_rejected_steer_does_not_consume_reminder_budget(self):
        s,_,error,_,_=self.run_phase(reject_steer=True)
        self.assertIsNone(error);self.assertEqual(s.steers,2);self.assertEqual(len(s.threads),2)

    def test_declared_candidate_can_end_author_loop_without_faking_model_completion(self):
        s,result,error,_,job=self.run_phase(mode='handoff',name='author',allow_handoff=True)
        self.assertIsNone(error);self.assertIn('author-phase handoff',result[0])
        self.assertEqual(len(s.threads),1);self.assertEqual(s.interrupts,1)
        self.assertEqual(next(iter(s.completed_turns.values()))['status'],'interrupted')
        self.assertTrue((job/'declared.pptx').is_file())

    def test_user_revision_prevents_declared_candidate_handoff(self):
        from conversation import RevisionPending
        _,_,error,journal,_=self.run_phase(mode='handoff',name='author',allow_handoff=True,revision_at_reset=True)
        self.assertIsInstance(error,RevisionPending)
        self.assertEqual(journal.state['inbox']['new-revision']['state'],'accepted')


if __name__=='__main__':unittest.main()
