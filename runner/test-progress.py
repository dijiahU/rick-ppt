import io
import json
from pathlib import Path
import tempfile
import unittest
from progress import Reporter,read_scoped,public_url

class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pptx-progress-test-')
        self.root=Path(self.temp.name).resolve();self.calls=[]
        self.reporter=Reporter({}, {'id':'test','lease':'lease'},self.root,lambda *a:self.calls.append(a))
    def tearDown(self):self.temp.cleanup()
    def test_only_allowlisted_codes(self):
        for kind in ['reasoning','agent_message','mcp_tool_call']:
            self.reporter.consume({'type':'item.completed','item':{'type':kind,'text':'SECRET /Users/private token'}})
        self.reporter.consume({'type':'item.completed','item':{'type':'command_execution','exit_code':0,'command':'SECRET','aggregated_output':'SECRET'}})
        self.reporter.flush(force=True)
        raw=self.calls[-1][2].decode();self.assertNotIn('SECRET',raw);self.assertNotIn('/Users',raw)
        self.assertEqual([e['code'] for e in json.loads(raw)['events']],['started','working'])
    def test_preview_and_duplicate(self):
        png=b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+(100).to_bytes(4,'big')+(50).to_bytes(4,'big')
        page=self.root/'slide-1.png';page.write_bytes(png)
        event={'type':'item.completed','item':{'type':'command_execution','exit_code':0,'aggregated_output':json.dumps({'ok':True,'renderer':'LibreOffice','pages':[str(page)]})}}
        self.reporter.consume(event);self.reporter.flush(force=True)
        self.assertEqual(len([c for c in self.calls if 'action=preview' in c[1]]),1)
        self.reporter.consume(event);self.reporter.flush(force=True)
        self.assertEqual(len([c for c in self.calls if 'action=preview' in c[1]]),1)
    def test_private_state_renders_do_not_replace_explicit_deck_previews(self):
        reporter=Reporter({},self.reporter.task,self.root,lambda *a:self.calls.append(a),explicit_previews=True)
        png=b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+(100).to_bytes(4,'big')+(50).to_bytes(4,'big')
        pages=[]
        for n in (1,2,3):
            page=self.root/f'slide-{n}.png';page.write_bytes(png);pages.append(str(page))
        # A three-state review copy is still only a review of one real deck page.
        reporter.consume({'type':'item.completed','item':{'type':'command_execution','exit_code':0,'aggregated_output':json.dumps({'ok':True,'renderer':'LibreOffice','pages':pages})}})
        reporter.flush(force=True)
        self.assertFalse(reporter.previews);self.assertFalse(reporter.pending)
        self.journal([{'kind':'preview','slide':2,'render':{'ok':True,'renderer':'LibreOffice','pages':[pages[0]]}}])
        reporter.poll_public_journal();reporter.flush(force=True)
        self.assertEqual(json.loads(self.calls[-1][2])['previews'],[2])
        self.assertEqual([c[1] for c in self.calls if 'action=preview' in c[1]],['/api/worker/test?action=preview&slide=2'])
        # The host's final independent rendering is still allowed to replace it.
        reporter.pending[1]=(self.root,Path(pages[0]));reporter.flush(force=True)
        self.assertEqual(json.loads(self.calls[-1][2])['previews'],[1,2])
    def test_paths_and_symlinks(self):
        outside=self.root.parent/'not-in-task'
        (self.root/'escape').symlink_to(self.root.parent,target_is_directory=True)
        (self.root/'link').symlink_to('/etc/hosts')
        for path in [outside,Path('../outside'),Path('link'),Path('escape/file')]:
            with self.assertRaises((ValueError,OSError)):read_scoped(self.root,path,100)
    def test_partial_event(self):
        stream=io.BytesIO(b'{"type":"item.completed"')
        self.reporter.poll(stream);self.assertEqual(self.reporter.offset,0)
    def test_sync_failure_nonfatal(self):
        def fail(*args):raise RuntimeError('network')
        self.reporter.send=fail;self.reporter.flush(force=True);self.assertTrue(self.reporter.dirty)
    def test_bounded_events(self):
        for i in range(600):self.reporter.event('working' if i%2 else 'rendered')
        self.assertEqual(len(self.reporter.events),500)
    def test_search_states_and_safe_sources(self):
        item={'type':'web_search','action':{'query':'gradient descent example token=privatevalue /Users/rick/private','url':'https://example.com/paper?token=secret#private'}}
        for state in ['item.started','item.completed']:self.reporter.consume({'type':state,'item':item})
        self.reporter.flush(force=True)
        data=json.loads(self.calls[-1][2]);search=[e for e in data['events'] if e.get('category')=='search']
        self.assertEqual([e['state'] for e in search],['started','completed'])
        self.assertEqual(next(e for e in data['events'] if e.get('category')=='source')['url'],'https://example.com/paper')
        raw=json.dumps(data);self.assertNotIn('privatevalue',raw);self.assertNotIn('/Users',raw)
        for url in ['javascript:alert(1)','http://localhost/file','http://127.0.0.1/file','https://user:pass@example.com/']:
            self.assertIsNone(public_url(url))
    def test_only_explicit_public_note_and_revision(self):
        (self.root/'art-direction.txt').write_text('PRIVATE REASONING')
        note=self.root/'public-status.json'
        note.write_text(json.dumps({'revision':1,'phase':'design','summary':'Use a labeled process diagram.','reasoning':'PRIVATE REASONING'}))
        self.reporter.poll_public_status();self.reporter.poll_public_status()
        self.assertEqual(len(self.reporter.events),2)
        self.assertTrue(self.reporter.events[-1]['reported'])
        self.assertNotIn('PRIVATE',json.dumps(self.reporter.events))
    def test_job_notes_do_not_cross_tasks(self):
        with tempfile.TemporaryDirectory() as second:
            root=Path(second).resolve()
            other=Reporter({}, {'id':'other','lease':'other'},root,lambda *args:None)
            (self.root/'public-status.json').write_text(json.dumps({'revision':1,'phase':'review','summary':'Task one only'}))
            self.reporter.poll_public_status();other.poll_public_status()
            self.assertNotIn('Task one',json.dumps(other.events))
    def test_filename_only_and_nested_render(self):
        self.reporter.consume({'type':'item.completed','item':{'type':'file_change','status':'completed','changes':[{'path':'/Users/rick/private/slide-2.xml'}]}})
        self.assertEqual(self.reporter.events[-1]['detail'],'slide-2.xml')
        self.reporter.consume({'type':'item.completed','item':{'type':'command_execution','exit_code':0,'aggregated_output':json.dumps({'ok':True,'render':{'ok':True,'renderer':'LibreOffice','pages':[str(self.root/'slide-2.png')]}})}})
        self.assertIn(2,self.reporter.pending)
    def test_multiple_queries_and_source_links(self):
        self.reporter.consume({'type':'item.completed','item':{'type':'web_search','action':{'queries':['first topic','second topic'],'urls':['https://example.com/a','https://example.com/watch?v=abc&token=private']}}})
        events=self.reporter.events
        self.assertEqual(len([e for e in events if e.get('category')=='search']),2)
        self.assertEqual(len([e for e in events if e.get('category')=='source']),2)
        self.assertEqual(events[-1]['url'],'https://example.com/watch?v=abc')
    def test_failed_command_is_visible_without_raw_output(self):
        self.reporter.consume({'type':'item.completed','item':{'type':'command_execution','exit_code':1,'command':'python media-embed.py /Users/rick/private token=SECRET','aggregated_output':'PRIVATE STDOUT'}})
        event=self.reporter.events[-1]
        self.assertEqual(event['state'],'failed');self.assertEqual(event['detail'],'media-embed.py')
        self.assertNotIn('SECRET',json.dumps(event));self.assertNotIn('PRIVATE',json.dumps(event))
    def test_large_multilingual_payload_is_bounded(self):
        for i in range(500):self.reporter.event('working',str(i)+'测'*790,category='note')
        self.reporter.flush(force=True)
        self.assertLessEqual(len(self.calls[-1][2]),480000)
    def journal(self,records):
        with (self.root/'public-progress.jsonl').open('a') as stream:
            for record in records:stream.write(json.dumps(record)+'\n')
    def test_journal_retains_fast_notes_and_survives_tool_churn(self):
        self.journal([{'kind':'note','phase':'design','summary':'Use a comparison to explain the choice.','next':'Build the opening page.'},
          {'kind':'note','phase':'building','slide':1,'summary':'Create the first page.'}])
        self.reporter.poll_public_journal();self.reporter.poll_public_journal()
        self.assertEqual(len(self.reporter.notes),2)
        for n in range(520):self.reporter.event('working',str(n),category='command')
        self.reporter.flush(force=True)
        body=json.loads(self.calls[-1][2])
        self.assertEqual(len(body['events']),500)
        self.assertEqual(body['notes'][0]['phase'],'design')
        self.assertEqual(body['notes'][0]['next'],'Build the opening page.')
        self.assertEqual(body['notes'][1]['slide'],1)
    def test_partial_journal_retries_and_invalid_fields_are_ignored(self):
        p=self.root/'public-progress.jsonl';p.write_bytes(b'{"kind":"note"')
        self.reporter.poll_public_journal();self.assertEqual(self.reporter.journal_offset,0)
        with p.open('ab') as f:f.write(b',"phase":"design","summary":"Choose clear labels."}\n')
        self.journal([{'kind':'note','phase':'reasoning','summary':'PRIVATE'},
          {'kind':'note','phase':'building','slide':True,'summary':'PRIVATE'},
          {'kind':'note','phase':'building','slide':51,'summary':'PRIVATE'},
          {'kind':'note','phase':'building','slide':2,'summary':'Build two.','next':'token=PRIVATE /Users/private','reasoning':'PRIVATE'}])
        self.reporter.poll_public_journal()
        self.assertEqual(len(self.reporter.notes),2)
        self.assertNotIn('PRIVATE',json.dumps(self.reporter.notes))
        self.assertNotIn('/Users',json.dumps(self.reporter.notes))
    def test_logical_slide_mapping_and_preview_only_after_upload(self):
        png=b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+(100).to_bytes(4,'big')+(50).to_bytes(4,'big')
        page=self.root/'slide-1.png';page.write_bytes(png)
        self.journal([{'kind':'preview','slide':3,'render':{'ok':True,'renderer':'LibreOffice','pages':[str(page)]}}])
        self.reporter.poll_public_journal()
        send=self.reporter.send
        self.reporter.send=lambda *a:(_ for _ in ()).throw(RuntimeError('offline'))
        self.reporter.flush(force=True)
        self.assertFalse(self.reporter.previews)
        self.assertFalse(any(e['code']=='rendered' for e in self.reporter.events))
        self.reporter.send=send;self.reporter.flush(force=True)
        body=json.loads(self.calls[-1][2]);self.assertEqual(body['previews'],[3])
        self.assertEqual(body['events'][-1]['slide'],3)
        self.assertEqual(len(body['previewVersions']['3']),16)
        previous=body['previewVersions']['3']
        self.reporter.event('working','Another operation');self.reporter.flush(force=True)
        self.assertEqual(json.loads(self.calls[-1][2])['previewVersions']['3'],previous)
    def test_journal_and_preview_symlinks_stay_private(self):
        (self.root/'public-progress.jsonl').symlink_to('/etc/hosts')
        self.reporter.poll_public_journal();self.assertFalse(self.reporter.notes)
        self.reporter.pending[1]=(self.root,Path('/etc/hosts'))
        self.reporter.flush(force=True);self.assertFalse(self.reporter.previews)
    def test_notes_payload_remains_bounded(self):
        for n in range(100):self.reporter.event('working',str(n)+'测'*790,reported=True,phase='design',category='note',next_step='下'*400)
        self.reporter.flush(force=True)
        self.assertLessEqual(len(self.calls[-1][2]),480000)
        self.assertLessEqual(len(json.loads(self.calls[-1][2])['notes']),80)

if __name__=='__main__':unittest.main()
