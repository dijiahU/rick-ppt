"""Real phase orchestration and Journal receipts with a deterministic model fake."""
import json,tempfile,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
import runner,workflow
from durable import Journal
from workflow import Execution
from progress import Reporter


class ChatPhaseTests(unittest.TestCase):
    def test_review_chat_bootstraps_isolated_runtime_and_completes_real_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);author=root/'author';author.mkdir();(author/'presentation.pptx').write_bytes(b'PKfrozen')
            (author/'outline.json').write_text('{}');task={'id':str(uuid.uuid4()),'lease':'synthetic-lease','title':'Test'}
            rows=[{'id':str(uuid.uuid4()),'seq':1,'kind':'chat','body':'How is progress?','attachments':[]}]
            answers=[];applied=[]
            def send(cfg,path,body=b'{}',lease=None,raw=False):
                action=parse_qs(urlsplit(path).query)['action'][0];value=json.loads(body)
                if action=='poll':return {'messages':rows,'revision':0}
                if action=='assistant':answers.append(value)
                if action=='applied':applied.extend(value['ids'])
                return {'ok':True}
            cfg={'token':'synthetic-secret','plugin':str(Path(__file__).resolve().parents[1]/'pptx-agent'),
                 'python':'/Users/rick/Desktop/ppt/pptx-agent/.venv/bin/python','single_file_pptx':True}
            bridge=SimpleNamespace(ROOT=root,request=send,prepare=runner.prepare,environment=runner.environment,render_requests=runner.render_requests)
            observed=[]
            class Server:
                def __init__(self,**kwargs):
                    self.root=kwargs['cwd'];self.tick=kwargs['tick'];self.public=kwargs['on_public'];self.event=kwargs['on_event']
                    self.active_turns={};self.completed_turns={}
                    self.configuration=kwargs['config'];observed.append(self)
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def start_thread(self):return {'thread':{'id':'chat-thread'}}
                def deliver(self,journal,identifier,thread,active):
                    journal.begin_delivery(identifier,'chat-rpc',thread,'chat-turn')
                    journal.acknowledge_message(identifier,request_id='chat-rpc',turn_id='chat-turn')
                    self.active_turns[thread]='chat-turn'
                    return {'turn_id':'chat-turn'}
                def pump(self,timeout):
                    self.tick()  # Real queues, temp directory, polling and flushing.
                    self.public({'type':'assistant.message','complete':True,'id':'answer-1','body':'The reviews finished; delivery is next.'})
                    self.active_turns.clear();self.completed_turns[('chat-thread','chat-turn')]={'status':'completed'}
                    self.event({'type':'turn.completed','thread_id':'chat-thread','turn_id':'chat-turn','status':'completed'})
                def result_text(self,*args):return 'The reviews finished; delivery is next.'
            with Journal(root/'state',task['id'],plugin_version='native') as journal:
                journal.begin_phase('author',author)
                reporter=Reporter(cfg,task,author,send,explicit_previews=True)
                run=Execution(bridge,cfg,task,author,SimpleNamespace(check=lambda:None),reporter,journal=journal)
                try:
                    run.conversation.poll(allow_steer=False,force=True)
                    self.assertEqual(reporter.reviews,{'content':'pending','visual':'pending'})
                    with patch.object(workflow,'AppServer',Server):run.respond_chats(artifact=b'PKfrozen',review={'content':{'findings':[]},'visual':{'findings':[]}})
                    self.assertEqual(journal.state['inbox'][rows[0]['id']]['state'],'applied')
                    self.assertEqual(applied,[rows[0]['id']]);self.assertEqual(len(answers),1)
                    self.assertEqual(journal.state['phase']['name'],'author')
                    self.assertEqual((author/'presentation.pptx').read_bytes(),b'PKfrozen')
                    isolated=observed[0].root
                    self.assertTrue((isolated/'render-requests').is_dir());self.assertTrue((isolated/'tmp').is_dir())
                    self.assertEqual((isolated/'reviewed-presentation.pptx').read_bytes(),b'PKfrozen')
                    self.assertNotIn(str(author),json.dumps(observed[0].configuration))
                    self.assertFalse(isolated.is_relative_to(author))
                finally:run.trace.close()

if __name__=='__main__':unittest.main()
