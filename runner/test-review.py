import io,json,tempfile,unittest,urllib.error,zipfile
from pathlib import Path
from email.message import Message
from review import ReviewClient,NoRedirect,load_config,SITE

class Response:
    def __init__(self,data,etag='"test"'):
        self.data=data;self.headers=Message();self.headers['ETag']=etag
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.data[:n]
class Opener:
    def __init__(self,responses):self.responses=iter(responses);self.requests=[]
    def open(self,request,**kwargs):self.requests.append(request);return next(self.responses)

class Tests(unittest.TestCase):
    def test_read_only_paths(self):
        client=ReviewClient(SITE,'a'*48)
        for path in ['/api/worker','https://other.example','/api/review/jobs/../../worker']:
            with self.assertRaises(ValueError):client.get(path)
    def test_no_redirect(self):self.assertIsNone(NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_response_limit(self):
        with self.assertRaises(ValueError):ReviewClient(SITE,'a'*48,Opener([Response(b'x'*20)])).get('/api/review/jobs',10)
    def test_config_origin_and_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'settings.json';path.write_text(json.dumps({'site':'https://attacker.example','token':'a'*48}));path.chmod(0o600)
            with self.assertRaises(ValueError):load_config(path)
            path.write_text(json.dumps({'site':SITE,'token':'a'*48}));path.chmod(0o644)
            with self.assertRaises(ValueError):load_config(path)
            path.chmod(0o600);self.assertEqual(load_config(path)['site'],SITE)
    def test_mismatch_and_path_traversal(self):
        client=ReviewClient(SITE,'a'*48,Opener([Response(json.dumps({'job':{'id':'other'}}).encode())]))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):client.fetch('../../bad',Path(temp))
            with self.assertRaises(ValueError):client.fetch('11111111-1111-1111-1111-111111111111',Path(temp))

if __name__=='__main__':unittest.main()
