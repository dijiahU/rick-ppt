"""Private synthetic draft-export synchronization; no website or live task."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
import zipfile

from draft_progress import DraftProgress,MAX_BYTES,validate_native
from progress import Reporter


BLANK=Path(__file__).resolve().parent.parent/'pptx-agent/skills/pptx/assets/blank.pptx'


def package(change=None,omit=()):
    with zipfile.ZipFile(BLANK) as source:
        values={name:source.read(name) for name in source.namelist() if name not in omit}
    if change:values.update(change)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as output:
        for name,data in values.items():output.writestr(name,data)
    return out.getvalue()


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pptx-draft-test-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.job=self.base/'task';self.job.mkdir()
        self.cfg={'state_directory':str(self.base/'host-state')};self.task={'id':'draft-test','lease':'synthetic','input_revision':2}
        self.calls=[];self.now=[0.0]
        def send(*args):self.calls.append(args);return {'ok':True}
        self.draft=DraftProgress(self.cfg,self.task,self.job,send,clock=lambda:self.now[0])
        self.body=BLANK.read_bytes();self.oldtime=time.time_ns()-10_000_000_000

    def export(self,name,body=None,offset=0):
        path=self.job/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(self.body if body is None else body)
        os.utime(path,ns=(self.oldtime+offset,self.oldtime+offset));return path

    def query(self,index=-1):return {k:v[0] for k,v in parse_qs(urlsplit(self.calls[index][1]).query).items()}

    def join(self):
        if self.draft.thread:self.draft.thread.join(3)

    def state(self,**extra):
        root=Path(self.cfg['state_directory'])/self.task['id'];root.mkdir(parents=True)
        value={'task_id':self.task['id'],'input_revision':7,'recoveries':{},**extra}
        (root/'state.json').write_text(json.dumps({'state':value}))

    def test_real_blank_passes_and_complete_native_count_is_uploaded(self):
        path=self.export('exports/v001.pptx')
        self.assertEqual(validate_native(self.body),1)
        self.draft.synchronize()
        self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0][2],self.body)
        self.assertEqual(self.query(),{'sha256':hashlib.sha256(self.body).hexdigest(),'pages':'1','revision':'2',
                                     'exportedAt':str(path.stat().st_mtime_ns//1_000_000)})
        self.assertEqual(self.calls[0][3],self.task['lease'])
        self.assertEqual(path.read_bytes(),self.body)

    def test_latest_corrupt_zip_falls_back_to_previous_valid_export(self):
        older=self.export('exports/v001.pptx');broken=self.export('exports/v002.pptx',b'PK broken',100)
        self.draft.synchronize();self.assertEqual(self.calls[0][2],self.body)
        self.assertEqual(older.read_bytes(),self.body);self.assertEqual(broken.read_bytes(),b'PK broken')

    def test_zip_missing_slide_or_native_presentation_is_rejected(self):
        for data in [package(omit=['ppt/slides/slide1.xml']),package(omit=['ppt/presentation.xml']),
                     package({'ppt/presentation.xml':b'<not-presentation/>'}),b'PK incomplete']:
            with self.subTest():
                with self.assertRaises(Exception):validate_native(data)

    def test_broken_relationship_and_external_escape_are_rejected(self):
        name='ppt/_rels/presentation.xml.rels'
        with zipfile.ZipFile(BLANK) as source:rels=source.read(name)
        self.assertIn(b'slides/slide1.xml',rels)
        for target in [b'../missing.xml',b'../../private.xml',b'%2e%2e/%2e%2e/private.xml']:
            with self.assertRaises(ValueError):validate_native(package({name:rels.replace(b'slides/slide1.xml',target)}))

    def test_active_office_content_and_xml_dtd_rejected(self):
        with self.assertRaises(ValueError):validate_native(package({'ppt/vbaProject.bin':b'active'}))
        with self.assertRaises(ValueError):validate_native(package({'ppt/presentation.xml':b'<!DOCTYPE test [<!ENTITY e "x">]><test>&e;</test>'}))

    def test_zero_and_out_of_range_page_ids_rejected(self):
        from lxml import etree
        with zipfile.ZipFile(BLANK) as source:tree=etree.fromstring(source.read('ppt/presentation.xml'))
        ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
        slide=tree.find('p:sldIdLst/p:sldId',ns);slide.set('id','0')
        with self.assertRaises(ValueError):validate_native(package({'ppt/presentation.xml':etree.tostring(tree)}))
        parent=tree.find('p:sldIdLst',ns);parent.remove(slide)
        with self.assertRaises(ValueError):validate_native(package({'ppt/presentation.xml':etree.tostring(tree)}))

    def test_oversized_file_and_absent_exports_create_no_upload(self):
        self.draft.synchronize();self.assertFalse(self.calls)
        path=self.export('exports/too-large.pptx',b'PK')
        with path.open('ab') as stream:stream.truncate(MAX_BYTES+1)
        self.draft.synchronize();self.assertFalse(self.calls)
        self.assertEqual(path.stat().st_size,MAX_BYTES+1)

    def test_symlink_files_directories_and_delivery_escape_are_not_read(self):
        outside=self.base/'outside.pptx';outside.write_bytes(self.body)
        (self.job/'exports').mkdir();(self.job/'exports/file.pptx').symlink_to(outside)
        (self.job/'exports/directory').symlink_to(self.base,target_is_directory=True)
        (self.job/'delivery.json').write_text(json.dumps({'path':str(outside)}))
        self.draft.synchronize();self.assertFalse(self.calls)
        (self.job/'delivery.json').write_text(json.dumps({'path':'../outside.pptx'}))
        self.draft.synchronize();self.assertFalse(self.calls)

    def test_nested_native_exports_and_delivery_relative_paths(self):
        self.export('.pptx-agent/native/exports/sub/v003.pptx')
        self.draft.synchronize();self.assertEqual(len(self.calls),1)
        other=package({'docProps/custom.xml':b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"/>'})
        # Use an existing XML part so content type coverage remains complete.
        other=package({'docProps/core.xml':b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"/>'})
        self.export('completed/custom.pptx',other,200)
        (self.job/'delivery.json').write_text(json.dumps({'path':'completed/custom.pptx'}))
        self.draft.synchronize();self.assertEqual(len(self.calls),2);self.assertEqual(self.calls[-1][2],other)

    def test_recovery_uses_host_alias_and_never_opens_old_workspace(self):
        old=self.base/'old-task';old.mkdir();(old/'custom').mkdir();(old/'custom/output.pptx').write_bytes(b'OLD DO NOT READ')
        self.export('custom/output.pptx')
        (self.job/'delivery.json').write_text(json.dumps({'path':str(old/'custom/output.pptx')}))
        self.state(recoveries={'one':{'previous_workspace':str(old),'workspace':str(self.job)}})
        self.draft.synchronize();self.assertEqual(self.calls[0][2],self.body);self.assertEqual(self.query()['revision'],'7')
        self.assertEqual((old/'custom/output.pptx').read_bytes(),b'OLD DO NOT READ')

    def test_forged_author_recovery_context_cannot_authorize_old_path(self):
        self.cfg['state_directory']=str(self.job/'state')
        self.state(recoveries={'one':{'previous_workspace':str(self.base),'workspace':str(self.job)}})
        self.export('exports/valid.pptx');self.draft.synchronize();self.assertFalse(self.calls)

    def test_no_upload_of_unpublished_candidate_or_arbitrary_source(self):
        self.export('exports/.pptx-export-partial/candidate.pptx')
        self.export('references/source.pptx');self.export('blank.pptx')
        self.draft.synchronize();self.assertFalse(self.calls)

    def test_success_hash_deduplicates_and_removed_latest_never_downgrades(self):
        older=self.export('exports/old.pptx')
        newer=package({'docProps/core.xml':b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"/>'})
        latest=self.export('exports/new.pptx',newer,100)
        self.draft.synchronize();self.draft.synchronize();self.assertEqual(len(self.calls),1)
        # Simulate candidate disappearance without deleting an existing fixture.
        with patch.object(self.draft,'candidates',return_value=['exports/old.pptx']):self.draft.synchronize()
        self.assertEqual(len(self.calls),1);self.assertEqual(latest.read_bytes(),newer);self.assertEqual(older.read_bytes(),self.body)

    def test_network_failure_and_nonack_response_retry_without_losing_candidate(self):
        self.export('exports/valid.pptx');original=self.draft.send
        self.draft.send=lambda *args:(_ for _ in ()).throw(OSError('network unavailable'))
        self.draft.synchronize();self.assertFalse(self.draft.uploaded)
        self.draft.send=lambda *args:{'ok':False};self.draft.synchronize();self.assertFalse(self.draft.uploaded)
        self.draft.send=original;self.draft.synchronize();self.assertEqual(len(self.calls),1);self.assertEqual(len(self.draft.uploaded),1)

    def test_poll_is_nonblocking_single_thread_throttled_and_finish_bounded(self):
        self.export('exports/valid.pptx');entered=threading.Event();release=threading.Event()
        def delayed(*args):entered.set();release.wait(5);return {'ok':True}
        self.draft.send=delayed
        try:
            started=time.monotonic();self.draft.poll();self.assertLess(time.monotonic()-started,.2)
            self.assertTrue(entered.wait(2));thread=self.draft.thread
            self.now[0]=30;self.draft.poll();self.assertIs(self.draft.thread,thread)
            started=time.monotonic();self.draft.finish(.01);self.assertLess(time.monotonic()-started,.2)
        finally:release.set();self.join()
        self.now[0]=31;self.draft.poll();self.join();thread=self.draft.thread
        self.now[0]=32;self.draft.poll();self.assertIs(self.draft.thread,thread)

    def test_reporter_flush_and_poll_sync_restored_exports_without_public_events(self):
        self.export('exports/restored.pptx')
        def send(*args):self.calls.append(args);return {'ok':True}
        reporter=Reporter(self.cfg,self.task,self.job,send,explicit_previews=True)
        reporter.dirty=False;reporter.last_sent=time.monotonic()
        reporter.flush();reporter.drafts.thread.join(3)
        drafts=[call for call in self.calls if '/draft?' in call[1]]
        self.assertEqual(len(drafts),1)
        reporter.poll(io.BytesIO(b''));reporter.finish_drafts(.1)
        self.assertEqual(len([call for call in self.calls if '/draft?' in call[1]]),1)


if __name__=='__main__':unittest.main()
