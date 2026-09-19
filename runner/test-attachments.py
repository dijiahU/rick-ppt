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
            self.assertEqual(calls[1],(f'/api/worker/{task["id"]}?action=attachment&file={self.item["id"]}','private-lease',True))
    def test_filename_not_path(self):
        with tempfile.TemporaryDirectory() as root:
            task={'id':str(uuid.uuid4()),'lease':'l','attachments':[{**self.item,'name':'../../outside.txt'}]}
            result=receive({},task,Path(root),lambda *a,**k:self.data if k.get('raw') else {})
            self.assertEqual(Path(result[0]['path']).name,self.item['id']+'.txt')
    def test_hash_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):receive({}, {'id':str(uuid.uuid4()),'lease':'l','attachments':[self.item]},Path(root),lambda *a,**k:b'bad' if k.get('raw') else {})
    def test_limits_and_ids(self):
        for change in [{'id':'../../x'},{'ext':'exe'},{'size':11*1024*1024},{'sha256':'bad'},{'size':True}]:
            with self.assertRaises((ValueError,TypeError)):metadata([{**self.item,**change}])
        with self.assertRaises(ValueError):metadata([self.item]*4)
        with self.assertRaises(ValueError):metadata([self.item]*2)
        self.assertEqual(metadata(None),[])
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
