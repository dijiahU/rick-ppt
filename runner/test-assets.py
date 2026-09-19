import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from assets import AssetImporter

PNG=b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+(100).to_bytes(4,'big')+(50).to_bytes(4,'big')+b'\x00\x00\x00\x00IEND\xaeB`\x82'

class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='asset-import-test-');self.root=Path(self.temp.name).resolve()
        self.job=self.root/'job';self.job.mkdir();(self.job/'assets').mkdir()
        self.generated=self.root/'generated';self.generated.mkdir()
        self.thread=str(uuid.uuid4());self.source=self.generated/self.thread;self.source.mkdir()
        self.name='exec-'+str(uuid.uuid4())+'.png'
        self.importer=AssetImporter(self.job,self.generated)
    def tearDown(self):self.temp.cleanup()
    def start(self):self.importer.poll(io.BytesIO((json.dumps({'type':'thread.started','thread_id':self.thread})+'\n').encode()))
    def test_only_current_thread(self):
        other=self.generated/str(uuid.uuid4());other.mkdir();(other/self.name).write_bytes(PNG)
        self.start();self.assertFalse(list((self.job/'assets').iterdir()))
        (self.source/self.name).write_bytes(PNG);self.importer.import_images()
        self.assertEqual((self.job/'assets'/('generated-'+self.name)).read_bytes(),PNG)
        index=json.loads((self.job/'assets/index.json').read_text());self.assertEqual(len(index['images']),1)
        self.importer.import_images();self.assertEqual(len(self.importer.imported),1)
    def test_source_symlink_denied(self):
        outside=self.root/'outside.png';outside.write_bytes(PNG);(self.source/self.name).symlink_to(outside)
        self.start();self.assertFalse(self.importer.imported)
    def test_destination_symlink_denied(self):
        (self.job/'assets').rmdir();outside=self.root/'outside';outside.mkdir();(self.job/'assets').symlink_to(outside,target_is_directory=True)
        (self.source/self.name).write_bytes(PNG);self.start();self.assertFalse(list(outside.iterdir()))
    def test_incomplete_png_retried(self):
        (self.source/self.name).write_bytes(PNG[:-12]);self.start();self.assertFalse(self.importer.imported)
        (self.source/self.name).write_bytes(PNG);self.importer.import_images();self.assertTrue(self.importer.imported)
    def test_nested_spoof_ignored(self):
        self.importer.consume({'type':'item.completed','item':{'aggregated_output':json.dumps({'type':'thread.started','thread_id':self.thread})}})
        self.assertIsNone(self.importer.thread)
    def test_invalid_thread_and_pinned_identity(self):
        self.importer.consume({'type':'thread.started','thread_id':'../other'});self.assertIsNone(self.importer.thread)
        self.start();self.importer.consume({'type':'thread.started','thread_id':str(uuid.uuid4())});self.assertEqual(self.importer.thread,self.thread)

if __name__=='__main__':unittest.main()
