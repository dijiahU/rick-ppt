import io,json,tempfile,threading,time,unittest,uuid,zipfile
from pathlib import Path
from types import SimpleNamespace
from workflow import Execution,fidelity_task,_repair_candidate
from progress import Reporter
from resilience import LeaseKeeper,TaskPaused
from office_policy import validate_delivery
from conversation import Conversation


def deck(files):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        for k,v in files.items():z.writestr(k,v)
    return data.getvalue()

def report():return {'summary':'Independent check','pages_reviewed':[1],'findings':[],'limitations':['No real PowerPoint player']}

class PolicyTests(unittest.TestCase):
    def test_pause_heartbeat_stops_without_becoming_failure(self):
        keeper=LeaseKeeper(lambda:{'ok':True,'stop':True})
        self.assertFalse(keeper.pulse())
        with self.assertRaises(TaskPaused):keeper.check()

    def test_pause_inbox_stops_before_processing_or_steering(self):
        c=object.__new__(Conversation);c.clock=lambda:1;c.next_poll=0
        c.journal=SimpleNamespace(state={'inbox':{}});c.api=lambda *a:{'messages':[],'stop':True}
        c._network=lambda f:f()
        with self.assertRaises(TaskPaused):c.poll()

    def test_one_pptx_rejects_addins_and_external_media_but_keeps_native_navigation(self):
        for files in [{'ppt/webextensions/webextension1.xml':'<x/>'},
                      {'ppt/slides/_rels/slide1.xml.rels':'<Relationships><Relationship Type="x/video" TargetMode="External" Target="https://example.test/a.mp4"/></Relationships>'},
                      {'ppt/slides/_rels/slide1.xml.rels':'<Relationships><Relationship Type="x/hyperlink" TargetMode="External" Target="https://example.test/lesson"/></Relationships>'}]:
            with self.assertRaises(ValueError):validate_delivery(deck(files),single_file=True)
        validate_delivery(deck({'ppt/slides/_rels/slide1.xml.rels':'<Relationships><Relationship Type="x/slide" Target="slide2.xml"/></Relationships>','ppt/media/clip.mp4':b'embedded'}),single_file=True)

    def test_fidelity_routing_excludes_substantive_rewrites(self):
        self.assertTrue(fidelity_task({'title':'将图片内容转化为可编辑ppt'}))
        self.assertTrue(fidelity_task({'mode':'edit','brief':'放大字体'}))
        self.assertFalse(fidelity_task({'mode':'edit','brief':'重写整个内容'}))
        self.assertFalse(fidelity_task({'brief':'Explain neural networks from scratch'}))

    def test_pause_cancels_both_independent_review_workers(self):
        from admin_trace import AdminTrace
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=object.__new__(Execution)
            run.cfg={};run.task={'id':str(uuid.uuid4())};run.records=root;run.job=root
            run.lease=SimpleNamespace(check=lambda:None);run.trajectory=None
            run.stages=[];run.logs=[];run.threads=[]
            run.trace=AdminTrace({},run.task,lambda *a,**k:{'ok':True},root)
            started=threading.Event();lock=threading.Lock();active=[];stopped=[]
            def check():
                if started.is_set():raise TaskPaused('Synthetic owner pause')
            run.review_tick=check
            def work(child):
                with lock:
                    active.append(child.review_role)
                    if len(active)==2:started.set()
                try:
                    while True:child.lease.check();time.sleep(.01)
                finally:
                    with lock:stopped.append(child.review_role)
            try:
                with self.assertRaises(TaskPaused):run._parallel_review({'content':work,'visual':work},1)
                self.assertEqual(set(stopped),{'content','visual'})
            finally:run.trace.close()

    def test_source_and_visual_review_overlap_and_keep_separate_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);job=base/'author';job.mkdir();(job/'references').mkdir();(job/'references/source.txt').write_text('SOURCE')
            (job/'source-notes.md').write_text('AUTHOR SECRET');(job/'outline.json').write_text('AUTHOR OUTLINE')
            plugin=base/'plugin'
            for name in ['pptx.py','native_builds.py','review_packet.py']:
                p=plugin/'skills/pptx/scripts'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# fixture')
            for name in ['content-review.md','visual-review.md']:
                p=plugin/'skills/pptx/references'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('review rules')
            (plugin/'.codex-plugin').mkdir();(plugin/'.codex-plugin/plugin.json').write_text('{"version":"native-test"}')
            image=base/'page.png';image.write_bytes(b'PNG');packet=base/'packet';packet.mkdir();(packet/'inventory.json').write_text('{}')
            def prepare(cfg):return Path(tempfile.mkdtemp(dir=base))
            task={'id':str(uuid.uuid4()),'lease':'test'};cfg={'plugin':str(plugin),'python':'python3','single_file_pptx':True,'parallel_reviews':True}
            reporter=Reporter({},task,job,lambda *a:{'ok':True},explicit_previews=True)
            exe=Execution(SimpleNamespace(ROOT=base,prepare=prepare),cfg,task,job,SimpleNamespace(check=lambda:None),reporter)
            barrier=threading.Barrier(2,timeout=2);calls=[];lock=threading.Lock()
            def phase(name,prompt,**kw):
                root=kw['root']
                with lock:calls.append((name,root,prompt))
                self.assertFalse((root/'source-notes.md').exists());self.assertFalse((root/'outline.json').exists())
                if name.startswith('content-evidence'):
                    self.assertEqual((root/'references/source.txt').read_text(),'SOURCE')
                else:self.assertFalse((root/'references/source.txt').exists())
                barrier.wait()  # Would time out if the passes were still serial.
                attempt=kw['review_attempt'];attempt.bind(name,'turn')
                attempt.observe({'type':'turn.completed','thread_id':name,'turn_id':'turn','status':'completed'})
                return report(),name
            exe.phase=phase
            try:
                receipt=exe.review(b'FROZEN',{'pages':[str(image)]},packet,{'title':'将图片内容转化为可编辑ppt','attachments':[{'path':'references/source.txt'}]},1)
                self.assertEqual(len(calls),2);self.assertEqual(len(set(c[1] for c in calls)),2)
                self.assertIsNone(receipt['content_first_view']);self.assertEqual(receipt['review_mode'],'source-fidelity')
                self.assertEqual(reporter.reviews,{'content':'passed','visual':'passed'})
            finally:exe.trace.close()

if __name__=='__main__':unittest.main()
