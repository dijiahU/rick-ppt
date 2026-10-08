"""Exercise the real job startup/exception/checkpoint flow without a live queue."""
import hashlib,json,tempfile,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
import runner,workflow
from durable import Journal
from resilience import TaskPaused
from trajectory import Trajectory


class StartupRecoveryTests(unittest.TestCase):
    def run_case(self,paused):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);job=root/'task';job.mkdir()
            (job/'references').mkdir();(job/'capabilities.json').write_text('{}')
            data=b'%PDF-1.4\nsynthetic reference';file=str(uuid.uuid4())
            item={'id':file,'name':'source.pdf','ext':'pdf','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            task={'id':str(uuid.uuid4()),'lease':'synthetic-lease','title':'Recovery','brief':'Use the supplied PDF','pages':1,'style':'Clear','language':'en','attachments':[item]}
            cfg={'token':'synthetic-secret','plugin':str(root),'python':'python3'};calls=[];stopped=False;finished=False
            def check():
                if stopped:raise TaskPaused('Synthetic owner stop')
            def finish():
                nonlocal finished
                finished=True
            lease=SimpleNamespace(check=check,finish=finish)
            def send(cfg,path,body=b'{}',lease=None,raw=False):
                action=parse_qs(urlsplit(path).query)['action'][0]
                calls.append((action,body))
                if action=='attachment':return data
                return {'ok':True}
            def work(bridge,cfg,task,job,payload,*args,**kwargs):
                nonlocal stopped
                self.assertEqual((job/payload['attachments'][0]['path']).read_bytes(),data)
                self.assertEqual(json.loads((job/'request.json').read_text())['attachments'],payload['attachments'])
                if paused:
                    stopped=True
                    raise RuntimeError('Renderer exited while stopping')
                return {'artifact':b'PKreviewed','revision':0,'bundle':None}
            with Journal(root/'state',task['id'],plugin_version='native') as journal:
                journal.checkpoint(job,reason='before_original_download')
                with patch.object(runner,'ROOT',root),patch.object(runner,'request',send),patch.object(workflow,'run_workflow',work),patch.object(Trajectory,'runtime',lambda self:None):
                    if paused:
                        with self.assertRaises(TaskPaused):runner._run_job_locked(cfg,task,lease,job,journal,{'next_phase':'research'})
                    else:runner._run_job_locked(cfg,task,lease,job,journal,{'next_phase':'research'})
                checkpoints=[json.loads(body) for action,body in calls if action=='checkpoint']
                if paused:
                    self.assertFalse(finished);self.assertEqual(checkpoints[-1]['phase'],'paused')
                    self.assertFalse(any(action=='complete' for action,_ in calls))
                else:
                    self.assertTrue(finished);self.assertEqual(sum(action=='attachment' for action,_ in calls),1)
                    self.assertEqual(sum(action=='complete' for action,_ in calls),1)
                self.assertFalse(any(action=='fail' for action,_ in calls))

    def test_restore_before_request_json_and_original_pdf_exist(self):self.run_case(False)
    def test_render_exit_after_owner_stop_is_checkpointed_as_paused(self):self.run_case(True)

if __name__=='__main__':unittest.main()
