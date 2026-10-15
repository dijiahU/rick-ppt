import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import zipfile
from PIL import Image,UnidentifiedImageError
from attachments import metadata,receive,validate_content
from resilience import LeaseKeeper,WorkerHTTPError,HeartbeatLost,TaskPaused

class AttachmentsTests(unittest.TestCase):
    def setUp(self):
        self.data='Reference: Café team'.encode()
        self.item={'id':str(uuid.uuid4()),'name':'notes.txt','ext':'txt','size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()}
    def test_scoped_transfer(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            def request(cfg,path,lease=None,raw=False):
                calls.append((path,lease,raw));return self.data if raw else {}
            task={'id':str(uuid.uuid4()),'lease':'private-lease','attachments':json.dumps([self.item])}
            result=receive({},task,Path(root),request)
            self.assertEqual((Path(root)/result[0]['path']).read_bytes(),self.data)
            self.assertEqual(calls,[(f'/api/worker/{task["id"]}?action=attachment&file={self.item["id"]}','private-lease',True)])
    def test_filename_not_path(self):
        with tempfile.TemporaryDirectory() as root:
            task={'id':str(uuid.uuid4()),'lease':'l','attachments':[{**self.item,'name':'../../outside.txt'}]}
            result=receive({},task,Path(root),lambda *a,**k:self.data if k.get('raw') else {})
            self.assertEqual(Path(result[0]['path']).name,self.item['id']+'.txt')
    def test_hash_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):receive({}, {'id':str(uuid.uuid4()),'lease':'l','attachments':[self.item]},Path(root),lambda *a,**k:b'bad' if k.get('raw') else {})
    def test_recovery_downloads_missing_original_and_reuses_verified_file(self):
        with tempfile.TemporaryDirectory() as root:
            task={'id':str(uuid.uuid4()),'lease':'new-lease','attachments':[self.item]};calls=[]
            def request(*args,**kwargs):calls.append((args,kwargs));return self.data if kwargs.get('raw') else {}
            (Path(root)/'references').mkdir()
            restored=receive({},task,Path(root),request,recover=True)
            self.assertEqual(len(calls),1)
            calls.clear();again=receive({},task,Path(root),request,recover=True)
            self.assertEqual(restored,again);self.assertEqual(calls,[])
    def test_rejected_or_paused_lease_prevents_original_download(self):
        for response in ({'ok':True,'stop':True},WorkerHTTPError('heartbeat',status=401),WorkerHTTPError('heartbeat',status=403),WorkerHTTPError('heartbeat',status=409)):
            with self.subTest(response=response),tempfile.TemporaryDirectory() as root:
                def pulse():
                    if isinstance(response,Exception):raise response
                    return response
                keeper=LeaseKeeper(pulse,log=lambda _:None);keeper.pulse()
                task={'id':str(uuid.uuid4()),'lease':'l','attachments':[self.item]}
                with self.assertRaises((TaskPaused,WorkerHTTPError)):
                    receive({},task,Path(root),lambda *a,**k:self.fail('Must not download on a rejected or paused lease'),check=keeper.check)
                self.assertEqual(list(Path(root).iterdir()),[])
    def test_stop_or_silence_limit_during_download_prevents_publication(self):
        for stopped in (False,True):
            with self.subTest(stopped=stopped),tempfile.TemporaryDirectory() as root:
                now=[0.0]
                keeper=LeaseKeeper(lambda:{'ok':True,'stop':stopped},clock=lambda:now[0],log=lambda _:None)
                task={'id':str(uuid.uuid4()),'lease':'l','attachments':[self.item]}
                def download(*a,**kw):
                    if stopped:keeper.pulse()
                    else:now[0]=keeper.max_silence
                    return self.data
                with self.assertRaises(TaskPaused if stopped else HeartbeatLost):
                    receive({},task,Path(root),download,check=keeper.check)
                self.assertEqual(list(Path(root).iterdir()),[])
    def test_recovered_verified_file_still_checks_current_pause(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'references';folder.mkdir();file=folder/(self.item['id']+'.txt');file.write_bytes(self.data)
            task={'id':str(uuid.uuid4()),'lease':'l','attachments':[self.item]}
            def stop():raise TaskPaused('Owner stopped')
            with self.assertRaises(TaskPaused):
                receive({},task,Path(root),lambda *a,**k:self.fail('No request expected'),recover=True,check=stop)
            self.assertEqual(file.read_bytes(),self.data);self.assertFalse((folder/'index.json').exists())
    def test_recovery_does_not_replace_corrupt_or_symlinked_inputs(self):
        for symlink in (False,True):
            with tempfile.TemporaryDirectory() as root:
                path=Path(root)/'references';path.mkdir();file=path/(self.item['id']+'.txt')
                if symlink:file.symlink_to(Path(root)/'outside.txt');(Path(root)/'outside.txt').write_bytes(self.data)
                else:file.write_bytes(b'corrupt')
                with self.assertRaises((OSError,ValueError)):
                    receive({}, {'id':str(uuid.uuid4()),'lease':'l','attachments':[self.item]},Path(root),lambda *a,**k:self.fail('Must not overwrite a bad existing input'),recover=True)
    def test_limits_and_ids(self):
        for change in [{'id':'../../x'},{'ext':'exe'},{'size':20*1024*1024+1},{'sha256':'bad'},{'size':True}]:
            with self.assertRaises((ValueError,TypeError)):metadata([{**self.item,**change}])
        with self.assertRaises(ValueError):metadata([{**self.item,'id':str(uuid.uuid4())} for _ in range(11)])
        with self.assertRaises(ValueError):metadata([self.item]*2)
        self.assertEqual(metadata(None),[])
    def test_ten_attachments_and_twenty_mb_boundary(self):
        items=[{**self.item,'id':str(uuid.uuid4()),'size':2*1024*1024} for _ in range(10)]
        self.assertEqual(len(metadata(items)),10)
        self.assertEqual(metadata([{**self.item,'size':20*1024*1024}])[0]['size'],20*1024*1024)
        with self.assertRaises(ValueError):metadata(items+[{**self.item,'id':str(uuid.uuid4())}])
        with self.assertRaises(ValueError):metadata([{**item,'size':item['size']+(1 if i==0 else 0)} for i,item in enumerate(items)])
    def test_receive_ten_images(self):
        image=Image.new('RGB',(10,10));out=io.BytesIO();image.save(out,format='PNG');data=out.getvalue()
        items=[{**self.item,'id':str(uuid.uuid4()),'name':f'image-{i}.png','ext':'png','size':len(data),'sha256':hashlib.sha256(data).hexdigest()} for i in range(10)]
        with tempfile.TemporaryDirectory() as root:
            result=receive({}, {'id':str(uuid.uuid4()),'lease':'l','attachments':items},Path(root),lambda *a,**k:data)
            self.assertEqual(len(result),10)
            self.assertTrue(all((Path(root)/item['path']).read_bytes()==data for item in result))
    def archive(self,extra):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            z.writestr('[Content_Types].xml','test');z.writestr('word/document.xml','test')
            for name,data in extra:z.writestr(name,data)
        return out.getvalue()
    def test_office_validation(self):
        validate_content(self.archive([]),'docx')
        for extra in [[('../escape',b'x')],[('word/vbaProject.bin',b'x')],[('word/embeddings/ole.bin',b'x')]]:
            with self.assertRaises(ValueError):validate_content(self.archive(extra),'docx')
        with self.assertRaises(ValueError):validate_content(self.archive([]),'pptx')
    def test_signatures(self):
        for ext in ['pdf','png','jpg','docx']:
            with self.assertRaises((ValueError,zipfile.BadZipFile,UnidentifiedImageError)):validate_content(b'fake',ext)
        with self.assertRaises(ValueError):validate_content(b'bad\0text','txt')
    def test_image_dimensions(self):
        image=Image.new('RGB',(9000,1));out=io.BytesIO();image.save(out,format='PNG')
        with self.assertRaises(ValueError):validate_content(out.getvalue(),'png')
        image=Image.new('RGB',(10,10));out=io.BytesIO();image.save(out,format='PNG')
        validate_content(out.getvalue(),'png')

if __name__=='__main__':unittest.main()
