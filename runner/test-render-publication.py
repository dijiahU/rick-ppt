"""Exercise host replies while a distinct task uid is already waiting."""
import json
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import weakref
from types import SimpleNamespace
from unittest.mock import patch

import runner


@unittest.skipUnless(sys.platform=='linux' and os.geteuid()==0,'Linux host/task uid boundary')
class RenderPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='pptx-reply-test-')
        self.job=Path(self.temporary.name);self.uid=712345678
        os.chown(self.job,self.uid,self.uid)
        self.queue=self.job/'render-requests';self.queue.mkdir(mode=0o700);os.chown(self.queue,self.uid,self.uid)
        self.qfd=os.open(self.queue,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        self.addCleanup(os.close,self.qfd)
        self.addCleanup(self.temporary.cleanup)

    def read_as_task(self,path):
        # No new sandbox invocation or recursive chown after host publication.
        # Such a chown previously hid this bug between successive commands.
        script='import json,os,sys;os.setgroups([]);os.setgid('+str(self.uid)+');os.setuid('+str(self.uid)+');print(open(sys.argv[1]).read())'
        child=subprocess.run([sys.executable,'-c',script,str(path)],capture_output=True,text=True,timeout=15)
        self.assertEqual(child.returncode,0,child.stderr)
        return json.loads(child.stdout)

    def test_success_and_error_replies_are_private_but_task_readable(self):
        previous=os.umask(0o077)
        try:
            for index,result in enumerate(({'returncode':0,'stdout':'ready'},{'returncode':1,'stderr':'render failed'})):
                name=str(index)*32+'.reply.json'
                runner._publish_render_reply(self.qfd,name,result)
                path=self.queue/name
                self.assertEqual(self.read_as_task(path),result)
                self.assertEqual(path.stat().st_uid,self.uid)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertFalse(list(self.queue.glob('*.host-pending')))
        finally:os.umask(previous)

    def test_publication_replaces_a_leaf_symlink_without_touching_its_target(self):
        private=self.job/'private';private.write_text('keep')
        name='a'*32+'.reply.json';(self.queue/name).symlink_to(private)
        runner._publish_render_reply(self.qfd,name,{'returncode':0})
        self.assertEqual(private.read_text(),'keep')
        self.assertFalse((self.queue/name).is_symlink())
        self.assertEqual(self.read_as_task(self.queue/name),{'returncode':0})

    def test_invalid_request_also_returns_a_readable_error(self):
        name='b'*32
        (self.queue/(name+'.request.json')).write_text(json.dumps({'args':[]}))
        runner.render_requests(self.job)
        result=self.read_as_task(self.queue/(name+'.reply.json'))
        self.assertEqual(result['returncode'],1)
        self.assertIn('ValueError',result['stderr'])

    def test_linux_success_branch_publishes_pdf_and_reply_to_task_uid(self):
        source=self.job/'draft.pptx';source.write_bytes((runner.ROOT.parent/'pptx-agent/skills/pptx/assets/blank.pptx').read_bytes())
        destination=self.job/'output';destination.mkdir(mode=0o700);os.chown(destination,self.uid,self.uid)
        name='c'*32
        (self.queue/(name+'.request.json')).write_text(json.dumps({'args':['--convert-to','pdf','--outdir',str(destination),str(source)]}))
        def render(job,input_dir,output_dir,font_dir,name,metadata,**options):
            (output_dir/'draft.pdf').write_bytes(b'%PDF-task-readable-fixture')
            return SimpleNamespace(returncode=0,stdout='rendered',stderr='')
        with patch('linux_render.render',side_effect=render),patch('linux_render.renderer_version',return_value='LibreOffice test'):
            runner.render_requests(self.job)
        result=self.read_as_task(self.queue/(name+'.reply.json'))
        self.assertEqual(result['returncode'],0)
        self.assertEqual(result['environment']['renderer_image'],'linux-landlock-libreoffice')
        child=subprocess.run([sys.executable,'-c','import os,sys;os.setgroups([]);os.setgid('+str(self.uid)+');os.setuid('+str(self.uid)+');assert open(sys.argv[1],"rb").read().startswith(b"%PDF-")',str(destination/'draft.pdf')],capture_output=True,text=True,timeout=15)
        self.assertEqual(child.returncode,0,child.stderr)

    def test_selected_page_reaches_renderer_and_keeps_timing_out_of_identity(self):
        from render_options import pdf_filter
        source=self.job/'draft.pptx';source.write_bytes((runner.ROOT.parent/'pptx-agent/skills/pptx/assets/blank.pptx').read_bytes())
        destination=self.job/'output';destination.mkdir(mode=0o700);os.chown(destination,self.uid,self.uid)
        identifier='d'*32
        (self.queue/(identifier+'.request.json')).write_text(json.dumps({'args':['--convert-to',pdf_filter(1),'--outdir',str(destination),str(source)]}))
        def render(*args,**options):
            self.assertEqual(options['page'],1)
            self.assertEqual(args[-1]['exported_pages'],[1])
            (args[2]/'draft.pdf').write_bytes(b'%PDF-selected-page')
            return SimpleNamespace(returncode=0,stdout='',stderr='',timings={'office_process_seconds':.5})
        with patch('linux_render.render',side_effect=render),patch('linux_render.renderer_version',return_value='LibreOffice test'):
            runner.render_requests(self.job)
        result=self.read_as_task(self.queue/(identifier+'.reply.json'))
        self.assertEqual(result['returncode'],0)
        self.assertEqual(result['environment']['exported_pages'],[1])
        self.assertEqual(result['timings'],{'office_process_seconds':.5})
        self.assertNotIn('timings',result['environment'])

    def test_page_outside_full_source_is_rejected_before_rendering(self):
        from render_options import pdf_filter
        source=self.job/'draft.pptx';source.write_bytes((runner.ROOT.parent/'pptx-agent/skills/pptx/assets/blank.pptx').read_bytes())
        identifier='e'*32
        (self.queue/(identifier+'.request.json')).write_text(json.dumps({'args':['--convert-to',pdf_filter(2),'--outdir',str(self.job),str(source)]}))
        with patch('linux_render.render') as convert:runner.render_requests(self.job)
        convert.assert_not_called()
        self.assertEqual(self.read_as_task(self.queue/(identifier+'.reply.json'))['returncode'],1)


class FontStagingTests(unittest.TestCase):
    def test_verified_source_buffers_are_released_before_office_starts(self):
        class TrackedFiles(dict):pass
        refs=[];body=b'verified-font-fixture';digest=hashlib.sha256(body).hexdigest()
        def source(job):
            files=TrackedFiles({'fonts/face.ttf':body,'fonts/provenance.json':b'checked by broker'})
            refs.append(weakref.ref(files));return files
        metadata={'family':'Fixture','style':'Regular','weight':400,'sha256':digest}
        with tempfile.TemporaryDirectory() as directory:
            font_dir=Path(directory)
            with patch('font_assets.verified_files',side_effect=source),patch('font_assets.inspect',return_value=metadata):
                records=runner._stage_render_fonts(Path('/unused'),font_dir)
            self.assertIsNone(refs[0]())
            self.assertEqual((font_dir/'face.ttf').read_bytes(),body)
            self.assertFalse((font_dir/'provenance.json').exists())
            self.assertEqual(records,[{'id':'face',**metadata}])


class RenderEnvironmentTests(unittest.TestCase):
    def test_host_enables_single_page_only_after_capability_verification(self):
        if sys.platform!='linux':self.skipTest('Linux renderer capability')
        with patch('linux_render.supports_page_range',return_value=True):
            self.assertEqual(runner.environment(Path('/tmp/pptx-test'))['PPTX_RENDER_PAGE_RANGE'],'1')
        with patch('linux_render.supports_page_range',return_value=False):
            self.assertNotIn('PPTX_RENDER_PAGE_RANGE',runner.environment(Path('/tmp/pptx-test')))

    def test_legacy_codex_command_keeps_render_flags_without_worker_credentials(self):
        cfg={'plugin':'/trusted/plugin','python':'/trusted/python/bin/python'}
        with patch.object(runner,'environment',return_value={'PPTX_RENDER_PAGE_RANGE':'1','PPTX_RENDER_TIMEOUT_SECONDS':'210','WORKER_TOKEN':'private-fixture'}):
            command=runner.codex_command(cfg,Path('/tmp/pptx-test'))
        setting=next(x for x in command if x.startswith('shell_environment_policy.set='))
        self.assertIn('"PPTX_RENDER_PAGE_RANGE"="1"',setting)
        self.assertIn('"PPTX_RENDER_TIMEOUT_SECONDS"="210"',setting)
        self.assertNotIn('WORKER_TOKEN',setting)

if __name__=='__main__':unittest.main()
