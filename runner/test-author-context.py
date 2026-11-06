"""Offline admission and actual phase orchestration, without model/queue calls."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PIL import Image

import workflow
from author_context import enabled, new_task_mode, pin_mode, saved_thread
from browser_sources import capability
from design_inputs import TOOL
from durable import RPCError
from material_prefetch import MaterialPrefetchBroker
from runner import prefetch_capability

REPO = Path(__file__).resolve().parents[1]


class Admission(unittest.TestCase):
    def test_new_local_pins_but_legacy_and_other_harnesses_keep_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertEqual(pin_mode({},root,'new',False),'continuous')
            self.assertEqual(pin_mode({'author_context_mode':'split'},root,'new',True),'continuous')
            self.assertEqual(pin_mode({},root,'old',True),'split')
            self.assertFalse((root/'old/author-context.json').exists())
            self.assertEqual(pin_mode({'author_context_mode':'split'},root,'rollback',False),'split')
            for cfg in ({'_model_profile':{'model':'external'}},{'_harness_transport':'dsh-sdk'}):
                self.assertEqual(new_task_mode(cfg),'split')
                with self.assertRaises(ValueError):new_task_mode({**cfg,'author_context_mode':'continuous'})
                with self.assertRaises(ValueError):pin_mode(cfg,root,'new',True)
            with self.assertRaises(ValueError):new_task_mode({'author_context_mode':'typo'})

    def test_resume_uses_latest_author_milestone_not_review(self):
        journal=SimpleNamespace(state={'completed_stages':{
            'research':{'thread_id':'research','completed_at':1},
            'author':{'thread_id':'author','completed_at':2},
            'repair-1':{'thread_id':'repair','completed_at':3},
            'visual-1':{'thread_id':'review','completed_at':4}}})
        self.assertEqual(saved_thread(journal),'repair')
        journal.state['completed_stages']={'research':{'thread_id':'research','completed_at':1}}
        self.assertEqual(saved_thread(journal),'research')
        self.assertIsNone(saved_thread(None))

    def test_helpers_are_rejected_not_just_hidden_in_prompts(self):
        cfg={'_author_context_mode':'continuous','browser_research':{
            'enabled':True,'browser':'edge','site':'https://www.google.com'}}
        self.assertIsNone(capability(cfg))
        self.assertEqual(prefetch_capability(cfg)['mode'],'disabled')
        with tempfile.TemporaryDirectory() as directory:
            broker=MaterialPrefetchBroker(cfg,Path(directory))
            try:
                with self.assertRaisesRegex(ValueError,'model-backed prefetch is disabled'):broker.submit({})
                self.assertEqual(broker.pending,{})
            finally:broker.close()


class Phases(unittest.TestCase):
    def test_real_phase_reuses_thread_and_image_channel_but_keeps_review_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();job=root/'job';job.mkdir();review=root/'review';review.mkdir()
            for folder in (job,review):
                for name in ('media-requests','font-requests','render-requests','tmp'):(folder/name).mkdir()
            (job/'outline.json').write_text(json.dumps({'slides':[{'id':'one','title':'One','summary':'A real picture'}]}))
            (job/'source-notes.md').write_text('Retained source evidence')
            Image.new('RGB',(17,11),'blue').save(job/'subject.png')
            (job/'decision-plan.json').write_text(json.dumps({'version':4,'pages':[
                {'id':'one','assets':[{'file':'subject.png','status':'ready'}]}],'references':[]}))
            cfg={'plugin':str(REPO/'pptx-agent'),'python':sys.executable,'token':'fixture',
                 '_author_context_mode':'continuous'}
            bridge=SimpleNamespace(ROOT=root,environment=lambda r:{},request=lambda *a,**k:{'ok':True},render_requests=Mock())
            run=workflow.Execution(bridge,cfg,{'id':'fixture','lease':'fixture'},job,
                                   SimpleNamespace(check=lambda:None),Mock(last_sent=0),trace=Mock())
            observed=[];threads={};image_results=[];missing=set()

            class Server:
                def __init__(self,**kw):
                    self.kw=kw;self.active_turns={};self.completed_turns={};observed.append(self)
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def start_thread(self,**kw):
                    thread='thread-'+str(len(threads)+1);threads[thread]=kw.get('dynamic_tools',[])
                    self.started=thread;return {'thread':{'id':thread}}
                def resume_thread(self,thread):
                    if thread in missing:raise RPCError('thread/resume',{'code':-32602,'message':'missing fixture thread'})
                    assert thread in threads
                    self.resumed=thread;return {'thread':{'id':thread}}
                def start_turn(self,thread,prompt,**kw):
                    self.prompt=prompt;self.thread=thread;self.active_turns[thread]='turn'
                    if len(observed)==2:
                        assert TOOL in [t['name'] for t in threads[thread]]
                        params={'tool':TOOL,'arguments':{'page_id':'one'},'callId':'picture',
                                'threadId':thread,'turnId':'turn'}
                        response=self.kw['on_tool_call'](params)
                        self.kw['on_tool_result_sent'](params,response)
                        image_results.append(response)
                    return {'id':'turn'}
                def pump(self,*args):
                    self.kw['tick']()
                    self.active_turns.clear();self.completed_turns[(self.thread,'turn')]={'status':'completed'}
                def result_text(self,*args):return 'finished fixture'

            try:
                with patch.object(workflow,'AppServer',Server),patch.object(workflow,'record',wraps=workflow.record) as receipts:
                    research=run.phase('research','Investigate the source')[1]
                    author=run.phase('author','Use inspected source material')[1]
                    reviewer=run.phase('visual-1','Independent review',root=review,public=False)[1]
                    self.assertEqual(run.author_thread,author)
                    repaired=run.phase('repair-1','Apply the reviewer finding')[1]
                    self.assertEqual((research,author,repaired),(research,)*3)
                    self.assertNotEqual(reviewer,research)
                    self.assertFalse(threads[reviewer])
                    names=[t['name'] for t in threads[research]]
                    self.assertIn(TOOL,names)
                    self.assertNotIn('pptx_search_sources',names)
                    self.assertNotIn('pptx_browser_sources',names)
                    response=image_results[0]
                    self.assertTrue(response['success'])
                    self.assertTrue(any(i['type']=='inputImage' for i in response['contentItems']))
                    projected=json.loads(response['contentItems'][0]['text'])
                    self.assertIn(hashlib.sha256((job/'subject.png').read_bytes()).hexdigest(),json.dumps(projected))
                    missing.add(research)
                    recovered=run.phase('repair-2','Recover verified saved work')[1]
                    self.assertNotEqual(recovered,research)
                    self.assertEqual(run.author_thread,recovered)
                    self.assertTrue(any(c.args[2]=='host.author_context_rebuilt' for c in receipts.call_args_list if len(c.args)>2))
                    self.assertEqual((job/'source-notes.md').read_text(),'Retained source evidence')
            finally:run.prefetch.close()


if __name__=='__main__':unittest.main()
