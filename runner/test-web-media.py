"""Broker policy tests; --live also downloads, embeds and renders real media."""
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
from PIL import Image
import web_media as m

class Policy(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{},clear=True);self.env.start();self.addCleanup(self.env.stop)

    def test_only_host_loopback_proxy_is_accepted(self):
        self.assertIsNone(m.local_proxy({}))
        self.assertEqual(m.local_proxy({'HTTPS_PROXY':'http://localhost:7890'}),'http://127.0.0.1:7890')
        self.assertEqual(m.local_proxy({'https_proxy':'http://[::1]:7890'}),'http://[::1]:7890')
        for value in ('http://proxy.example:7890','http://127.0.0.1:7890/private','http://user:secret@127.0.0.1:7890','socks5://127.0.0.1:7890','http://127.0.0.1:0'):
            with self.subTest(value=value),self.assertRaises(m.MediaError) as raised:m.local_proxy({'HTTPS_PROXY':value})
            self.assertNotIn('secret',str(raised.exception))

    def proxy_fetch(self,command,**kwargs):
        self.assertEqual(command[command.index('--proxy')+1],'http://127.0.0.1:7890')
        self.assertEqual(kwargs['env'],{'PATH':'/usr/bin:/bin'})
        url=command[command.index('--url')+1]
        if url.startswith('https://dns.google/resolve?'):
            return subprocess.CompletedProcess(command,0,json.dumps({'Status':0,'Answer':[{'type':1,'data':'93.184.216.34'}]}).encode(),b'')
        self.assertEqual(command[command.index('--connect-to')+1],'example.com:443:93.184.216.34:443')
        self.assertEqual(url,'https://example.com/a.png')
        self.assertNotIn('--insecure',command);self.assertNotIn('-L',command)
        Path(command[command.index('--dump-header')+1]).write_bytes(b'HTTP/1.1 200 Connection established\r\n\r\nHTTP/2 200\r\nContent-Type: image/png\r\n\r\n')
        return subprocess.CompletedProcess(command,0,b'image-bytes',b'')

    def test_proxy_uses_public_doh_and_pins_connect_target(self):
        with patch.dict(os.environ,{'HTTPS_PROXY':'http://127.0.0.1:7890'}),patch.object(socket,'getaddrinfo',side_effect=AssertionError('local fake-IP DNS must not be used')),patch.object(subprocess,'run',side_effect=self.proxy_fetch) as run:
            self.assertEqual(m.download('https://example.com/a.png'),(b'image-bytes','https://example.com/a.png','image/png'))
            self.assertEqual(run.call_count,2)

    def test_proxy_cannot_fetch_private_dns_answer(self):
        answer=subprocess.CompletedProcess([],0,b'{"Answer":[{"type":1,"data":"10.0.0.7"}]}',b'')
        with patch.dict(os.environ,{'HTTPS_PROXY':'http://127.0.0.1:7890'}),patch.object(subprocess,'run',return_value=answer) as run,self.assertRaises(m.MediaError) as raised:m.download('https://example.com/a')
        self.assertEqual(raised.exception.code,'non_public_address');self.assertEqual(run.call_count,1)

    def test_proxy_redirect_is_revalidated(self):
        def fetch(command,**kwargs):
            if '--dump-header' not in command:return self.proxy_fetch(command,**kwargs)
            Path(command[command.index('--dump-header')+1]).write_bytes(b'HTTP/2 302\r\nLocation: https://127.0.0.1/private\r\n\r\n')
            return subprocess.CompletedProcess(command,0,b'',b'')
        with patch.dict(os.environ,{'HTTPS_PROXY':'http://127.0.0.1:7890'}),patch.object(subprocess,'run',side_effect=fetch) as run,self.assertRaises(ValueError):m.download('https://example.com/a.png')
        self.assertEqual(run.call_count,2)

    def test_transient_transport_has_one_retry_and_safe_diagnostics(self):
        failed=subprocess.CompletedProcess([],35,b'',b'sensitive query and host file path should not escape')
        with patch.object(socket,'getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]),patch.object(subprocess,'run',return_value=failed) as run,self.assertRaises(m.MediaError) as raised:m.download('https://example.com/a?token=secret')
        self.assertEqual(run.call_count,2);self.assertEqual(raised.exception.code,'tls_handshake')
        self.assertEqual(raised.exception.details,{'host':'example.com','route':'direct','curl_exit':35,'attempts':2})
        self.assertNotIn('secret',str(raised.exception))

    def test_partial_size_and_certificate_errors_are_not_retried(self):
        for code,body,expected in [(28,b'partial','download_timeout'),(60,b'','tls_certificate'),(63,b'','download_too_large')]:
            with self.subTest(code=code),patch.object(socket,'getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]),patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],code,body,b'')) as run,self.assertRaises(m.MediaError) as raised:m.download('https://example.com/a')
            self.assertEqual(run.call_count,1);self.assertEqual(raised.exception.code,expected)

    def test_http_status_is_reported_without_retry(self):
        def rejected(command,**kwargs):
            Path(command[command.index('--dump-header')+1]).write_bytes(b'HTTP/2 403\r\nContent-Type: text/html\r\n\r\n')
            return subprocess.CompletedProcess(command,0,b'denied',b'')
        with patch.object(socket,'getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]),patch.object(subprocess,'run',side_effect=rejected) as run,self.assertRaises(m.MediaError) as raised:m.download('https://example.com/a')
        self.assertEqual(run.call_count,1);self.assertEqual(raised.exception.details['http_status'],403)

    def test_shared_budget_prevents_unbounded_retry(self):
        with patch.object(time,'monotonic',side_effect=[0,0,0,0,66]),patch.object(socket,'getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]),patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],35,b'',b'')) as run,self.assertRaises(m.MediaError) as raised:m.download('https://example.com/a')
        self.assertEqual(run.call_count,1);self.assertEqual(raised.exception.code,'download_timeout')

    def test_broker_preserves_structured_error(self):
        with tempfile.TemporaryDirectory() as d,patch.object(m,'download',side_effect=m.MediaError('tls_handshake','Media TLS handshake failed',curl_exit=35,route='local_proxy')):
            broker=m.WebMediaBroker(Path(d));broker.fetch({'url':'https://example.com/a','purpose':'illustrate'})
        self.assertEqual(broker.result,{'ok':False,'error':'Media TLS handshake failed','error_code':'tls_handshake','details':{'curl_exit':35,'route':'local_proxy'}})

    def test_forbidden_urls(self):
        for url in ('file:///etc/passwd','http://example.com/a','https://user:pass@example.com/a','https://localhost/a','https://foo.internal/a','https://example.com:8443/a','https://example.com/\nfoo'):
            with self.subTest(url=url),self.assertRaises(ValueError):m.resolve_url(url)

    def test_public_dns_pinned(self):
        with patch.object(socket,'getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]):
            url,pin=m.resolve_url('https://example.com/a.png#x')
            self.assertEqual(url,'https://example.com/a.png');self.assertEqual(pin,'example.com:443:93.184.216.34')

    def test_private_dns_rejected(self):
        answer=subprocess.CompletedProcess([],0,json.dumps({'Answer':[{'type':1,'data':'127.0.0.1'}]}).encode(),b'')
        with patch.object(socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch.object(subprocess,'run',return_value=answer),self.assertRaises(ValueError):m.resolve_url('https://example.com/a')

    def test_redirect_revalidated(self):
        def fake(command,**kwargs):
            Path(command[command.index('--dump-header')+1]).write_bytes(b'HTTP/1.1 302 Found\r\nLocation: http://localhost/private\r\n\r\n')
            self.assertEqual(command[1],'-q');self.assertIn('--resolve',command);self.assertNotIn('-L',command)
            return subprocess.CompletedProcess(command,0,b'',b'')
        with patch.object(socket,'getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]),patch.object(subprocess,'run',side_effect=fake),self.assertRaises(ValueError):m.download('https://example.com/a')

    def test_symlink_queue_rejected(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
            root=Path(d);(root/'media-requests').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(OSError):m.WebMediaBroker(root).poll()

    def test_three_task_brokers_remain_separate(self):
        with tempfile.TemporaryDirectory() as d:
            brokers=[]
            for i in range(3):
                root=Path(d)/str(i);root.mkdir();(root/'assets').mkdir();(root/'media-requests').mkdir()
                (root/'assets/index.json').write_text('{"images":["generated-kept"]}')
                (root/'media-requests'/('a'*32+'.request.json')).write_text(json.dumps({'url':'https://example.com/media','purpose':str(i)}))
                brokers.append(m.WebMediaBroker(root))
            with patch.object(m,'download',return_value=(b'original','https://example.com/media','image/png')),patch.object(m,'normalize',return_value=({'kind':'image','file':'media.png'},{'media.png':b'normalized'})):
                for _ in range(30):
                    for broker in brokers:broker.poll()
                    if all(len(b.records)==1 for b in brokers):break
                    time.sleep(.01)
            for i,broker in enumerate(brokers):
                self.assertEqual(len(broker.records),1);self.assertEqual(broker.records[0]['purpose'],str(i))
                self.assertEqual(json.loads((broker.job/'assets/index.json').read_text())['images'],['generated-kept'])
                self.assertTrue(json.loads((broker.job/'media-requests'/('a'*32+'.reply.json')).read_text())['ok'])
                broker.poll();self.assertEqual(len(broker.records),1)

    def test_native_image_fit(self):
        from lxml import etree as E
        spec=importlib.util.spec_from_file_location('media_embed',Path(__file__).with_name('media-embed.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        blank=Path(__file__).resolve().parent.parent/'pptx-agent/skills/pptx/assets/blank.pptx'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with zipfile.ZipFile(blank) as archive:archive.extractall(root)
            source=root/'test.png';Image.new('RGB',(200,100),'blue').save(source)
            module.embed(root,1,source,None,(1,1,4,4))
            module.embed(root,1,source,None,(1,1,4,4),'cover')
            slide=E.parse(str(root/'ppt/slides/slide1.xml'))
            pictures=slide.findall('.//{'+module.P+'}pic');self.assertEqual(len(pictures),2)
            ext=pictures[0].find('.//{'+module.A+'}xfrm/{'+module.A+'}ext')
            self.assertEqual((int(ext.get('cx')),int(ext.get('cy'))),(3657600,1828800))
            crop=pictures[1].find('.//{'+module.A+'}srcRect')
            self.assertEqual(crop.attrib,{'l':'25000','r':'25000'})

def live():
    import runner
    cfg=runner.settings();job=runner.prepare(cfg)
    print('TEST JOB',job,flush=True)
    samples=[('png','https://www.megacrit.com/images/blade_dance.png'),('gif','https://www.megacrit.com/images/regent_gif.gif'),('video','https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4'),('audio','https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3')]
    records=[]
    broker=m.WebMediaBroker(job)
    for kind,url in samples:
        command=runner.sandbox(cfg,job,[cfg['python'],str(job/'web-media-proxy.py'),url,'--purpose','Engineering '+kind+' import verification','--source-page',url])
        out=runner.run_with_renderer(cfg,job,command,timeout=330,media_broker=broker)
        record=json.loads(out);assert record['ok'],record
        records.append(record);print('IMPORTED',kind,record['kind'],flush=True)
    assert len(broker.records)==4
    script=str(Path(cfg['plugin'])/'skills/pptx/scripts/pptx.py')
    def cli(*args):return json.loads(runner.run_with_renderer(cfg,job,runner.sandbox(cfg,job,[cfg['python'],script,*args]),timeout=180))
    unpack=cli('unpack',str(job/'blank.pptx'));workspace=unpack['workspace']
    cli('-w',workspace,'snapshot','--label','before-media-test')
    for i,record in enumerate(records):
        media=job/'assets'/record['file'];poster=job/'assets'/record.get('poster',records[0]['poster'])
        args=[cfg['python'],str(job/'media-embed.py'),workspace,'1',str(media),'--box',str(.4+(i%2)*6.3),str(.4+(i//2)*3.4),'5.7','3']
        if record['kind'] in ('video','audio'):args+=['--poster',str(poster)]
        print(runner.run_with_renderer(cfg,job,runner.sandbox(cfg,job,args)),flush=True)
    print(cli('-w',workspace,'validate','--level','3'),flush=True)
    print(cli('-w',workspace,'export',str(job/'media-test.pptx')),flush=True)
    with zipfile.ZipFile(job/'media-test.pptx') as z:
        media=[n for n in z.namelist() if n.startswith('ppt/media/')]
        for record in records:
            body=(job/'assets'/record['file']).read_bytes()
            assert any(z.read(n)==body for n in media),'Lost actual media bytes'
        xml=z.read('ppt/slides/slide1.xml')
        assert b'videoFile' in xml and b'audioFile' in xml and b'ppaction://media' in xml
        gif=next(n for n in media if n.endswith('.gif'));assert Image.open(io.BytesIO(z.read(gif))).n_frames>1
    (job/'verification.json').write_text(json.dumps({'records':records,'embeddedBytesVerified':True,'staticRenderValidated':True,'powerPointPlaybackVerified':False},indent=2))
    print('PASS: real public PNG/GIF/MP4/MP3 → sandbox proxy → native OOXML → validation/render/export',job,flush=True)

if __name__=='__main__':
    if '--live' in sys.argv:live()
    else:unittest.main()
