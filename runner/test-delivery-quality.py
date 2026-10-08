import hashlib,io,json,tempfile,unittest,uuid,zipfile
from pathlib import Path
from types import SimpleNamespace
from delivery import deliver
from durable import Journal
from resilience import WorkerHTTPError
from workflow import reviewed_delivery,Execution


class DeliveryTests(unittest.TestCase):
    def test_lost_response_is_confirmed_only_for_same_bytes_and_revision(self):
        data=b'PKfrozen';digest=hashlib.sha256(data).hexdigest();task={'id':str(uuid.uuid4()),'lease':'synthetic'}
        for receipt,success in [({'status':'complete','sha256':digest,'revision':4},True),
                                ({'status':'complete','sha256':'0'*64,'revision':4},False),
                                ({'status':'complete','sha256':digest,'revision':3},False),
                                ({'status':'running','sha256':digest,'revision':4},False)]:
            calls=[]
            def send(cfg,path,*args,**kwargs):
                calls.append(path)
                if 'action=complete&' in path:raise WorkerHTTPError('complete',curl=28,retryable=True)
                if 'action=delivery-status' in path:return receipt
                return {'ok':True}
            if success:self.assertTrue(deliver({},task,data,4,send)['confirmed_after_timeout'])
            else:
                with self.assertRaises(WorkerHTTPError):deliver({},task,data,4,send)
            self.assertEqual(len(calls),3)

    def test_revision_rejection_returns_to_author_without_confirming(self):
        calls=[]
        def send(cfg,path,*args,**kwargs):
            calls.append(path);raise WorkerHTTPError('delivery-ready',status=412)
        with self.assertRaises(WorkerHTTPError):deliver({}, {'id':str(uuid.uuid4()),'lease':'synthetic'},b'PK',0,send)
        self.assertEqual(len(calls),1)

    def test_host_receipted_delivery_survives_upgrade_but_rejects_revision_and_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);job=root/'job';job.mkdir();version=job/'delivery-versions/v1';version.mkdir(parents=True)
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as archive:archive.writestr('ppt/slides/slide1.xml','<x/>')
            data=out.getvalue();(version/'presentation.pptx').write_bytes(data)
            (version/'review.json').write_text(json.dumps({'artifact_sha256':hashlib.sha256(data).hexdigest(),'content':{'findings':[]},'visual':{'findings':[]}}))
            (version/'review.md').write_text('Passed')
            saved={'artifact':'delivery-versions/v1/presentation.pptx','review':'delivery-versions/v1/review.json','review_summary':'delivery-versions/v1/review.md','revision':0}
            (version/'delivery.json').write_text(json.dumps(saved))
            ident=str(uuid.uuid4())
            with Journal(root/'state',ident,plugin_version='old-native') as journal:
                journal.begin_phase('delivery-ready',job)
                journal.complete_phase('delivery-ready',job,artifacts=[str(p.relative_to(job)) for p in version.iterdir()])
                restored=root/'restored';journal.recover(restored,plugin_version='new-native',allow_plugin_upgrade=True)
                run=SimpleNamespace(journal=journal,conversation=SimpleNamespace(server_revision=0),cfg={'single_file_pptx':True})
                self.assertFalse(journal.can_reuse('delivery-ready',restored))
                self.assertEqual(reviewed_delivery(run,restored)[2],data)
                run.conversation.server_revision=1;self.assertIsNone(reviewed_delivery(run,restored))
                run.conversation.server_revision=0;(restored/saved['artifact']).write_bytes(b'PKchanged')
                self.assertIsNone(reviewed_delivery(run,restored))

    def test_deferred_chat_uses_separate_workspace_and_never_marks_fake_answer(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);job=root/'author';job.mkdir();(job/'presentation.pptx').write_bytes(b'PKfrozen');(job/'outline.json').write_text('{}')
            ident=str(uuid.uuid4())
            with Journal(root/'state',ident,plugin_version='native') as journal:
                mid=str(uuid.uuid4());journal.accept_message(mid,'How is progress?',cursor=1,changes_input=False)
                run=object.__new__(Execution);run.journal=journal;run.conversation=object();run.job=job;run.cfg={}
                def prepare(cfg):
                    chat=root/'isolated-chat';chat.mkdir();return chat
                run.bridge=SimpleNamespace(ROOT=root,prepare=prepare)
                run.task={'id':ident,'title':'Synthetic'};run.stages=[];calls=[]
                run.trace=SimpleNamespace(emit=lambda *a,**k:None)
                def phase(name,prompt,**kwargs):
                    calls.append(kwargs)
                    self.assertFalse(kwargs['root'].is_relative_to(job));self.assertFalse(job.is_relative_to(kwargs['root']))
                    self.assertFalse((kwargs['root']/'presentation.pptx').exists())
                    self.assertIn('chat-only',(kwargs['root']/'AGENTS.md').read_text())
                    raise TimeoutError('Synthetic chat timeout')
                run.phase=phase;run.respond_chats()
                self.assertEqual((job/'presentation.pptx').read_bytes(),b'PKfrozen')
                self.assertEqual(journal.state['inbox'][mid]['state'],'accepted')
                self.assertFalse(calls[0]['public']);self.assertEqual(calls[0]['chat_ids'],[mid])

if __name__=='__main__':unittest.main()
