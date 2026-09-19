import copy,io,json,tempfile,unittest,urllib.error,urllib.request,zipfile
from pathlib import Path
from email.message import Message
from unittest.mock import patch
from review import ReviewClient,NoRedirect,CurlOpener,load_config,SITE,MAX_BUNDLE,DELIVERY_HEADER

class Response:
    def __init__(self,data,etag='"test"',headers=None):
        self.data=data;self.headers=Message();self.headers['ETag']=etag;self.reads=0
        for name,value in (headers or {}).items():self.headers[name]=value
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):self.reads+=1;return self.data[:n]
class Opener:
    def __init__(self,responses):self.responses=iter(responses);self.requests=[]
    def open(self,request,**kwargs):
        self.requests.append(request);response=next(self.responses)
        if isinstance(response,BaseException):raise response
        return response

class Tests(unittest.TestCase):
    def test_read_only_paths(self):
        client=ReviewClient(SITE,'a'*48)
        for path in ['/api/worker','https://other.example','/api/review/jobs/../../worker','/api/review/jobs-mutate','/api/review/jobs?token=secret','/api/review/jobs#fragment','/api/review/jobs/%2e%2e']:
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

TASK='11111111-1111-1111-1111-111111111111'
TOKEN='synthetic-review-credential-at-least-32-characters'
VERSION='ab'*32
def delivery():
    native=io.BytesIO()
    with zipfile.ZipFile(native,'w') as package:
        for name in ['[Content_Types].xml','ppt/presentation.xml','ppt/slides/slide1.xml']:package.writestr(name,'<test/>')
    zipped=io.BytesIO()
    with zipfile.ZipFile(zipped,'w') as package:
        package.writestr('distribution/presentation.pptx',native.getvalue())
        package.writestr('../../never-extract.txt','This untrusted path must not be extracted.')
        package.writestr('scripts/never-run.py','raise RuntimeError("Never execute downloaded archives")')
    meta={'schemaVersion':1,'readOnly':True,'job':{'id':TASK,'status':'complete','title':'../../remote-name','brief':'Original brief'},
          'artifact':{'available':True,'bytes':len(native.getvalue()),'etag':'"pptx"','deliveryVersion':VERSION},
          'bundle':{'available':True,'bytes':len(zipped.getvalue()),'etag':'"zip"','deliveryVersion':VERSION},'deliveryVersion':VERSION}
    return meta,native.getvalue(),zipped.getvalue()

def metadata(value):return Response(json.dumps(value).encode())
def native_response(data,version=VERSION):return Response(data,'"pptx"',{DELIVERY_HEADER:version,'Content-Disposition':'attachment; filename="../../unsafe.pptx"'})
def bundle_response(data,**headers):return Response(data,'"zip"',{'Content-Type':'application/zip',DELIVERY_HEADER:VERSION,'X-Review-PPTX-ETag':'"pptx"',**headers})

class BundleTests(unittest.TestCase):
    def test_default_fetch_still_downloads_only_original_pptx(self):
        meta,pptx,zipped=delivery();opener=Opener([metadata(meta),native_response(pptx)])
        with tempfile.TemporaryDirectory() as temp:
            result=ReviewClient(SITE,TOKEN,opener).fetch(TASK,Path(temp))
            self.assertNotIn('bundle',result)
            self.assertEqual(Path(result['directory'],'output.pptx').read_bytes(),pptx)
            self.assertFalse(Path(result['directory'],'interactive.zip').exists())
            self.assertEqual([r.full_url for r in opener.requests],[SITE+'/api/review/jobs/'+TASK,SITE+'/api/review/jobs/'+TASK+'/pptx'])

    def test_bundle_fetch_preserves_exact_bytes_private_files_and_no_archive_execution(self):
        meta,pptx,zipped=delivery();opener=Opener([metadata(meta),native_response(pptx),bundle_response(zipped),metadata(meta)])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=root/'keep.txt';original.write_text('preserve')
            result=ReviewClient(SITE,TOKEN,opener).fetch(TASK,root,bundle=True)
            self.assertTrue(result['bundle']['currentDeliveryConfirmed'])
            self.assertFalse(result['bundle']['archiveInspected'])
            folder=Path(result['directory'])
            self.assertEqual((folder/'interactive.zip').read_bytes(),zipped)
            self.assertEqual((folder/'output.pptx').read_bytes(),pptx)
            self.assertEqual(original.read_text(),'preserve')
            self.assertFalse((root/'never-extract.txt').exists())
            self.assertFalse((folder/'scripts').exists())
            for name in ['request.json','output.pptx','interactive.zip','manifest.json']:
                self.assertEqual((folder/name).stat().st_mode&0o077,0)
            self.assertNotIn(TOKEN,(folder/'manifest.json').read_text())
            self.assertTrue(opener.requests[0].full_url.endswith('?include=bundle'))
            for request in opener.requests:
                self.assertEqual(request.method,'GET')
                self.assertEqual(request.get_header('Authorization'),'Bearer '+TOKEN)
            for index in [1,2]:
                self.assertEqual({k.lower():v for k,v in opener.requests[index].header_items()}[DELIVERY_HEADER.lower()],VERSION)

    def test_absent_or_legacy_bundle_is_explicit_without_extra_download(self):
        for info,reason in [(None,'review_service_without_bundle_support'),({'available':False,'reason':'not_delivered'},'not_delivered')]:
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as temp:
                meta,pptx,_=delivery();meta.pop('bundle')
                if info is not None:meta['bundle']=info
                opener=Opener([metadata(meta),native_response(pptx)])
                result=ReviewClient(SITE,TOKEN,opener).fetch(TASK,Path(temp),bundle=True)
                self.assertFalse(result['bundle']['available']);self.assertEqual(result['bundle']['reason'],reason)
                self.assertEqual(len(opener.requests),2)

    def test_inconsistent_version_or_oversized_metadata_is_rejected_before_binary_download(self):
        for field,value in [('deliveryVersion','cd'*32),('bytes',MAX_BUNDLE+1),('bytes',True)]:
            with self.subTest(field=field,value=value),tempfile.TemporaryDirectory() as temp:
                meta,_,_=delivery();meta['bundle'][field]=value;opener=Opener([metadata(meta)])
                with self.assertRaises(ValueError):ReviewClient(SITE,TOKEN,opener).fetch(TASK,Path(temp),bundle=True)
                self.assertEqual(len(opener.requests),1)
                saved=json.loads(next(Path(temp).glob('*/manifest.json')).read_text())
                self.assertFalse(saved['bundle']['currentDeliveryConfirmed'])

    def test_stale_bundle_pair_does_not_become_verified_by_matching_zip_etag(self):
        meta,pptx,zipped=delivery()
        opener=Opener([metadata(meta),native_response(pptx),bundle_response(zipped,**{'X-Review-PPTX-ETag':'"different-pptx"'})])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'does not match'):ReviewClient(SITE,TOKEN,opener).fetch(TASK,Path(temp),bundle=True)
            folder=next(Path(temp).iterdir());self.assertEqual((folder/'output.pptx').read_bytes(),pptx)
            self.assertFalse((folder/'interactive.zip').exists())
            self.assertFalse(json.loads((folder/'manifest.json').read_text())['bundle']['currentDeliveryConfirmed'])

    def test_final_current_version_change_retains_both_originals_but_reports_failure(self):
        meta,pptx,zipped=delivery();changed=copy.deepcopy(meta);changed['deliveryVersion']='cd'*32
        opener=Opener([metadata(meta),native_response(pptx),bundle_response(zipped),metadata(changed)])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'originals retained'):ReviewClient(SITE,TOKEN,opener).fetch(TASK,Path(temp),bundle=True)
            folder=next(Path(temp).iterdir())
            self.assertEqual((folder/'output.pptx').read_bytes(),pptx);self.assertEqual((folder/'interactive.zip').read_bytes(),zipped)
            self.assertFalse(json.loads((folder/'manifest.json').read_text())['bundle']['currentDeliveryConfirmed'])

    def test_size_guards_cover_declared_and_actual_response_without_large_allocations(self):
        response=Response(b'x',headers={'Content-Length':str(MAX_BUNDLE+1)})
        client=ReviewClient(SITE,TOKEN,Opener([response]))
        with self.assertRaisesRegex(ValueError,'size limit'):client.get('/api/review/jobs/'+TASK+'/bundle',MAX_BUNDLE)
        self.assertEqual(response.reads,0)
        client=ReviewClient(SITE,TOKEN,Opener([Response(b'x'*11)]))
        with self.assertRaisesRegex(ValueError,'size limit'):client.get('/api/review/jobs/'+TASK+'/bundle',10)

    def test_http_auth_not_found_and_stale_errors_do_not_print_remote_bodies(self):
        for status in [401,404,412,413,428,503]:
            with self.subTest(status=status):
                error=urllib.error.HTTPError(SITE,status,'untrusted secret detail',{},io.BytesIO(b'PRIVATE_REMOTE_BODY'))
                with self.assertRaisesRegex(ValueError,'HTTP '+str(status)) as caught:
                    ReviewClient(SITE,TOKEN,Opener([error])).get('/api/review/jobs/'+TASK+'/bundle')
                self.assertNotIn('PRIVATE',str(caught.exception));self.assertNotIn('secret',str(caught.exception))

class CurlTests(unittest.TestCase):
    def fake_process(self,body,status=200):
        state={'input':None,'killed':False,'argv':None,'readLimit':None}
        class Input(io.BytesIO):
            def close(stream):state['input']=stream.getvalue();super().close()
        class Output(io.BytesIO):
            def read(stream,n):state['readLimit']=n;return super().read(n)
        class Process:
            def __init__(process,args,**kwargs):
                state['argv']=args;state['kwargs']=kwargs
                Path(args[args.index('--dump-header')+1]).write_text(f'HTTP/1.1 {status} Synthetic\nETag: "zip"\nLocation: https://attacker.example/\n\n')
                process.stdin=Input();process.stdout=Output(body);process.returncode=None
            def poll(process):return process.returncode
            def wait(process,**kwargs):process.returncode=0;return 0
            def kill(process):state['killed']=True;process.returncode=-9
        return state,Process

    def test_curl_credentials_only_use_stdin_and_redirects_are_refused(self):
        state,process=self.fake_process(b'redirect',302)
        with patch('review.subprocess.Popen',process):
            with self.assertRaisesRegex(ValueError,'HTTP 302'):
                ReviewClient(SITE,TOKEN,CurlOpener()).get('/api/review/jobs/'+TASK+'/bundle',MAX_BUNDLE)
        self.assertNotIn(TOKEN,' '.join(state['argv']))
        self.assertIn(TOKEN.encode(),state['input'])
        self.assertEqual(state['argv'][1],'--disable')
        self.assertNotIn('--location',state['argv']);self.assertNotIn('-L',state['argv'])
        self.assertEqual(state['argv'][state['argv'].index('--max-filesize')+1],str(MAX_BUNDLE))
        self.assertEqual(state['readLimit'],MAX_BUNDLE+1)
        self.assertNotIn('env',state['kwargs'])

    def test_curl_output_is_killed_at_actual_limit_even_without_content_length(self):
        state,process=self.fake_process(b'x'*11)
        with patch('review.subprocess.Popen',process):
            with self.assertRaisesRegex(ValueError,'size limit'):
                ReviewClient(SITE,TOKEN,CurlOpener()).get('/api/review/jobs/'+TASK+'/bundle',10)
        self.assertEqual(state['readLimit'],11);self.assertTrue(state['killed'])

if __name__=='__main__':unittest.main()
