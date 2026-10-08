import hashlib
import tempfile
import unittest
import uuid
from pathlib import Path

from runner import receive_progress_draft


ROOT=Path(__file__).resolve().parent
BLANK=ROOT/'runtime/0.1.0+codex.20260919234350/pptx-agent/skills/pptx/assets/blank.pptx'


class ProgressContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.job=Path(self.temp.name).resolve();self.task={'id':str(uuid.uuid4()),'lease':'synthetic-lease'}

    def test_explicit_draft_continuation_fetches_valid_native_source(self):
        data=BLANK.read_bytes();self.task['summary']='resume_from_draft';calls=[]
        def send(cfg,path,body=b'{}',lease=None,raw=False):
            calls.append((path,lease,raw));return data
        item=receive_progress_draft({},self.task,self.job,send)
        self.assertEqual(calls,[(f'/api/worker/{self.task["id"]}?action=draft-source','synthetic-lease',True)])
        self.assertEqual(item['sha256'],hashlib.sha256(data).hexdigest());self.assertEqual(item['ext'],'pptx')
        self.assertEqual((self.job/item['path']).read_bytes(),data)

    def test_normal_attempt_never_fetches_a_progress_copy(self):
        def send(*args,**kwargs):raise AssertionError('unexpected fetch')
        self.assertIsNone(receive_progress_draft({},self.task,self.job,send))

    def test_invalid_progress_copy_is_rejected_before_publication(self):
        self.task['summary']='resume_from_draft'
        with self.assertRaises(Exception):receive_progress_draft({},self.task,self.job,lambda *a,**k:b'PK broken')
        self.assertFalse((self.job/'references').exists())


if __name__=='__main__':unittest.main()
