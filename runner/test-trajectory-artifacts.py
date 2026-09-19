import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image

from trajectory import Trajectory,digest
from trajectory_replay import restore_snapshot,copy_original,list_artifacts
from assets import AssetImporter
from web_media import WebMediaBroker


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.job=self.root/'job';self.job.mkdir()
        self.run=Trajectory({'token':'synthetic-host-secret'},{'id':str(uuid.uuid4()),'lease':'synthetic-lease'},self.root/'trajectory')
        self.run.register(self.job,'task')

    def tearDown(self):
        for stream in (self.run.events,self.run.steps,self.run.catalog):
            if not stream.closed:stream.close()
        self.temp.cleanup()

    def test_exact_file_versions_restore_original_not_normalized_view(self):
        original=('File: '+str(self.job/'input.txt')+'\n你好 😀').encode()
        (self.job/'input.txt').write_bytes(original)
        (self.job/'tmp').mkdir();(self.job/'tmp'/'intermediate.pptx').write_bytes(b'PKintermediate-v1')
        first=self.run.snapshot(self.job,'before')
        (self.job/'input.txt').write_text('changed');(self.job/'tmp'/'intermediate.pptx').unlink()
        second=self.run.snapshot(self.job,'after')
        restore_snapshot(self.run.root,first,self.root/'restore-1');restore_snapshot(self.run.root,second,self.root/'restore-2')
        self.assertEqual((self.root/'restore-1/input.txt').read_bytes(),original)
        self.assertEqual((self.root/'restore-1/tmp/intermediate.pptx').read_bytes(),b'PKintermediate-v1')
        self.assertEqual((self.root/'restore-2/input.txt').read_text(),'changed')
        self.assertFalse((self.root/'restore-2/tmp/intermediate.pptx').exists())
        with self.assertRaises(FileExistsError):restore_snapshot(self.run.root,first,self.root/'restore-1')

    def test_original_download_and_conversion_both_survive(self):
        broker=WebMediaBroker(self.job,trajectory=self.run);broker.current='a'*32
        with patch('web_media.download',return_value=(b'original-jpeg','https://example.com/a.jpg','image/jpeg')),patch('web_media.normalize',return_value=({'kind':'image','file':'media.png'},{'media.png':b'converted-png'})):
            broker.fetch({'url':'https://example.com/start','source_page':'https://example.com/article','purpose':'Explain the product'})
        artifacts=list_artifacts(self.run.root)
        self.assertEqual({a['role'] for a in artifacts},{'download-originals','download-converted'})
        for content in (b'original-jpeg',b'converted-png'):self.assertEqual((self.run.root/'raw-blobs'/digest(content)).read_bytes(),content)
        self.assertTrue(all(a['source']['request_id']=='a'*32 for a in artifacts))

    def test_all_generated_images_archived_beyond_import_quota(self):
        (self.job/'assets').mkdir();generated=self.root/'generated';generated.mkdir();thread=str(uuid.uuid4());source=generated/thread;source.mkdir()
        for i in range(14):Image.new('RGB',(5,5),(i,0,0)).save(source/('exec-'+str(uuid.uuid4())+'.png'))
        importer=AssetImporter(self.job,generated,trajectory=self.run)
        importer.consume({'type':'thread.started','thread_id':thread});importer.import_images()
        self.assertEqual(len(importer.imported),12)
        images=[a for a in list_artifacts(self.run.root) if a['role']=='generated-images']
        self.assertEqual(len(images),14)
        self.assertTrue(all(a['source']['producer_thread_id']==thread for a in images))
        importer.import_images();self.assertEqual(len(list_artifacts(self.run.root)),14)

    def test_render_inputs_and_pdf_archived_before_reply(self):
        import runner
        queue=self.job/'render-requests';queue.mkdir();dest=self.job/'temporary';dest.mkdir();pptx=self.job/'draft.pptx';pptx.write_bytes(b'PKdraft')
        request={'args':['--headless','--convert-to','pdf','--outdir',str(dest),str(pptx)]}
        (queue/('b'*32+'.request.json')).write_text(json.dumps(request))
        def convert(*args,**kwargs):
            (dest/'draft.pdf').write_bytes(b'%PDF-captured')
            return SimpleNamespace(returncode=0,stdout='render output',stderr='')
        with patch.object(runner.subprocess,'run',side_effect=convert):runner.render_requests(self.job,trajectory=self.run)
        (dest/'draft.pdf').unlink();pptx.unlink()
        roles={a['role'] for a in list_artifacts(self.run.root)}
        self.assertIn('render-input',roles);self.assertIn('render-output',roles)
        self.assertEqual((self.run.root/'raw-blobs'/digest(b'%PDF-captured')).read_bytes(),b'%PDF-captured')
        self.assertTrue((queue/('b'*32+'.reply.json')).exists())

    def test_large_original_streamed_without_old_64mb_limit(self):
        path=self.job/'large.bin'
        with path.open('wb') as f:f.seek(65*1024*1024);f.write(b'last-byte')
        artifact=self.run.artifact_path(self.job,path,'media')
        self.assertEqual(artifact['original']['raw_bytes'],path.stat().st_size)
        self.assertFalse(artifact['original']['view_available'])
        out=self.root/'restored.bin';copy_original(self.run.root,artifact['original'],out)
        self.assertEqual(out.stat().st_size,path.stat().st_size)
        self.assertEqual(digest(out.read_bytes()),digest(path.read_bytes()))

    def test_original_host_credentials_withheld_and_corruption_rejected(self):
        ref=self.run.blob(b'\xffsynthetic-host-secret')
        self.assertIsNone(ref['raw_sha256'])
        self.assertNotIn(b'synthetic-host-secret',(self.run.root/'blobs'/ref['sha256']).read_bytes())
        with self.assertRaises(ValueError):copy_original(self.run.root,ref,self.root/'secret.bin')
        artifact=self.run.artifact(b'good','final.pptx','delivered',final=True)
        original=self.run.root/'raw-blobs'/artifact['original']['raw_sha256'];os.chmod(original,0o600);original.write_bytes(b'bad!')
        with self.assertRaises(ValueError):copy_original(self.run.root,artifact['original'],self.root/'corrupt.pptx')

    def test_restore_rejects_archive_path_traversal(self):
        sid=str(uuid.uuid4());(self.run.root/'snapshots'/(sid+'.json')).write_text(json.dumps({'scope':'task','files':{'../escape':{}},'unavailable':[]}))
        with self.assertRaises(ValueError):restore_snapshot(self.run.root,sid,self.root/'restore')
        self.assertFalse((self.root/'restore').exists())

if __name__=='__main__':unittest.main()
