"""Real task files and offline app-server frames; no model/account/queue calls."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from design_inputs import PageDesignInputs, TOOL
from durable import AppServer, TransportError

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT/'workflow'))
sys.path.insert(0, str(ROOT/'pptx-agent/skills/pptx/scripts'))
from pptx_core.package import unpack
from pptx_core.renderer import render
from pptx_core.common import sha256
spec = importlib.util.spec_from_file_location('design_input_protocol_fixture', ROOT/'workflow/test_app_server.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve(); self.job = self.root/'task'; self.job.mkdir()
        self.cfg = {'python':sys.executable, 'plugin':str(ROOT/'pptx-agent')}
        self.inputs = PageDesignInputs(self.cfg, self.job)
        (self.job/'outline.json').write_text(json.dumps({'slides':[
            {'id':'first','title':'Actual image','summary':'Keep the actual evidence and qualification.'},
            {'id':'later','title':'Later page','summary':'Different material.'}]}))
        (self.job/'source-notes.md').write_text('Actual source notes.\n')
        Image.new('RGB',(43,29),'blue').save(self.job/'main.png')
        Image.new('RGB',(17,13),'gold').save(self.job/'reference.png')
        Image.new('RGB',(11,7),'green').save(self.job/'later.png')
        self.plan = {'version':4, 'pages':[
            {'id':'first','assets':[{'status':'ready','file':'main.png'}]},
            {'id':'later','assets':[{'status':'ready','file':'later.png'}]}],
            'references':[{'id':'work','inspection':'local_image','evidence':'reference.png',
                           'observed':'Large subject with a quiet surround','borrowed':'Subject prominence',
                           'applications':[{'pages':['first'],'action':'Enlarge the actual subject'}]}]}
        self.save()

    def save(self):
        (self.job/'decision-plan.json').write_text(json.dumps(self.plan))

    def params(self, page='first'):
        return {'tool':TOOL,'arguments':{'page_id':page},'callId':'call-1','threadId':'thread-1','turnId':'turn-1'}

    def native(self):
        return unpack(ROOT/'pptx-agent/skills/pptx/assets/blank.pptx', base=self.job/'projects')

    def rendered(self, ws, color='white'):
        # Validate/pack/fingerprint real OOXML; replace only external conversion.
        def package(source, destination, slide, total):
            folder=Path(tempfile.mkdtemp(prefix='render-test-',dir=destination))
            image=folder/f'slide-{slide}.png'; Image.new('RGB',(96,54),color).save(image)
            return {'pages':[str(image)],'source_hash':sha256(source),'at':'offline-test','ok':True}
        with patch('pptx_core.renderer.render_package',side_effect=package):
            return render(ws,1)

    def wire(self, params):
        with AppServer(cwd=self.job, config={}, command=[sys.executable,'-u','-c',fixture.FAKE_SERVER],
                       on_tool_call=self.inputs.handle, on_tool_result_sent=self.inputs.sent) as server:
            server.start_thread(dynamic_tools=self.inputs.specs())
            return server.request('test/approval',{'method':'item/tool/call','params':params})

    def test_page_preview_crosses_wire_before_and_after_native_edit_with_real_version_receipts(self):
        ws=self.native(); first=self.rendered(ws,'white')
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        files={p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        with patch('design_inputs.record') as capture:
            result=self.wire(params)
            ctx=json.loads(result['contentItems'][0]['text'])
            self.assertEqual(ctx['native']['preview']['status'],'current')
            self.assertEqual(ctx['visual_inputs'][0]['role'],'page_preview')
            self.assertEqual(ctx['visual_inputs'][0]['content_index'],1)
            raw=base64.b64decode(result['contentItems'][1]['imageUrl'].split(',',1)[1])
            self.assertEqual(raw,Path(first['pages'][0]).read_bytes())
            self.assertEqual(files,{p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()})
            receipt=capture.call_args.args[3]
            self.assertEqual(capture.call_args.args[2],'design.page_preview_sent')
            self.assertEqual(receipt['native']['workspace_fingerprint'],first['workspace_fingerprint'])
            self.assertIsNone(receipt['previous_input'])
            original=Path(first['pages'][0]).read_bytes()
            part=ws.root/ctx['native']['part'];part.write_bytes(part.read_bytes()+b'\n')
            changed=self.rendered(ws,'blue')
            result=self.wire({**params,'callId':'call-2'})
        ctx=json.loads(result['contentItems'][0]['text'])
        raw=base64.b64decode(result['contentItems'][1]['imageUrl'].split(',',1)[1])
        self.assertEqual(raw,Path(changed['pages'][0]).read_bytes())
        self.assertNotEqual(raw,original)
        self.assertEqual(Path(first['pages'][0]).read_bytes(),original)
        self.assertEqual(ctx['previous_preview_input']['call_id'],'call-1')
        self.assertEqual(ctx['native']['workspace_fingerprint'],changed['workspace_fingerprint'])
        self.assertNotEqual(ctx['native']['workspace_fingerprint'],first['workspace_fingerprint'])
        self.assertEqual(capture.call_args.args[3]['previous_input']['call_id'],'call-1')

    def test_identical_preview_pixels_are_resupplied_for_changed_native_version(self):
        ws=self.native();first=self.rendered(ws)
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        self.wire(params)
        part=ws.root/'ppt/slides/slide1.xml';part.write_bytes(part.read_bytes()+b'\n')
        second=self.rendered(ws)
        self.assertEqual(sha256(first['pages'][0]),sha256(second['pages'][0]))
        result=self.wire({**params,'callId':'call-2'})
        ctx=json.loads(result['contentItems'][0]['text'])
        self.assertEqual(ctx['visual_inputs'][0]['state'],'attached')
        self.assertEqual(ctx['native']['preview']['workspace_fingerprint'],second['workspace_fingerprint'])

    def test_first_preview_resupplies_applicable_reference_pixels_then_reuses_delivery(self):
        # The model received the reference before drawing, as in the real run.
        self.wire(self.params())
        ws=self.native();preview=self.rendered(ws)
        params={**self.params(),'callId':'first-preview',
                'arguments':{'page_id':'first','workspace':str(ws.root)}}
        before={p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        with patch('design_inputs.record') as capture:result=self.wire(params)
        ctx=json.loads(result['contentItems'][0]['text'])
        attached=[v for v in ctx['visual_inputs'] if v['state']=='attached']
        self.assertEqual([v['role'] for v in attached],['page_preview','reference:work'])
        for row,file in zip(attached,[Path(preview['pages'][0]),self.job/'reference.png']):
            raw=base64.b64decode(result['contentItems'][row['content_index']]['imageUrl'].split(',',1)[1])
            self.assertEqual(raw,file.read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        self.assertNotIn('later.png',json.dumps(ctx))
        self.assertEqual(before,{p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()})
        sent=next(c.args[3] for c in capture.call_args_list if c.args[2]=='design.visual_input_sent')
        self.assertEqual(sent['files'],attached)
        # A later preview still gets fresh current pixels, not endless references.
        later=self.wire({**params,'callId':'next-preview'})
        ctx=json.loads(later['contentItems'][0]['text'])
        ref=next(v for v in ctx['visual_inputs'] if v['role']=='reference:work')
        self.assertEqual(ref['state'],'previously_supplied')
        self.assertEqual(ref['prior_call_id'],'first-preview')
        self.assertEqual(sum(v['type']=='inputImage' for v in later['contentItems']),1)

    def test_unavailable_or_failed_first_preview_does_not_consume_reference_comparison(self):
        self.wire(self.params())
        ws=self.native()
        params={**self.params(),'callId':'missing-preview',
                'arguments':{'page_id':'first','workspace':str(ws.root)}}
        result=self.wire(params);ctx=json.loads(result['contentItems'][0]['text'])
        ref=next(v for v in ctx['visual_inputs'] if v['role']=='reference:work')
        self.assertEqual(ref['state'],'previously_supplied')
        self.assertEqual(self.inputs.previews,{})
        self.rendered(ws)
        # Handler preparation is not a successful image-input write.
        with AppServer(cwd=self.job, config={}, command=[sys.executable,'-u','-c',fixture.FAKE_SERVER],
                       on_tool_call=self.inputs.handle,on_tool_result_sent=self.inputs.sent) as server:
            original=server._write
            def broken(value):
                if value.get('id')=='host-request':raise TransportError('Synthetic first-comparison write failure')
                original(value)
            server._write=broken
            with self.assertRaises(TransportError):
                server.request('test/approval',{'method':'item/tool/call','params':params})
        self.assertEqual(self.inputs.previews,{})
        self.assertEqual(self.inputs.delivered[('thread-1',sha256(self.job/'reference.png'))],'call-1')
        result=self.wire({**params,'callId':'successful-preview'})
        ctx=json.loads(result['contentItems'][0]['text'])
        self.assertEqual(next(v for v in ctx['visual_inputs'] if v['role']=='reference:work')['state'],'attached')

    def test_render_judgment_cue_accompanies_actual_current_pixels_without_task_mutation(self):
        ws=self.native();preview=self.rendered(ws)
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        before={p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        with patch('design_inputs.record') as capture:result=self.wire(params)
        ctx=json.loads(result['contentItems'][0]['text'])
        self.assertIsInstance(ctx['author_design_prompt'],str)
        self.assertTrue(ctx['author_design_prompt'])
        self.assertEqual(result['contentItems'][-1],{'type':'inputText','text':ctx['author_design_prompt']})
        self.assertTrue(all(item['type']=='inputImage' for item in result['contentItems'][1:-1]))
        sent=next(c.args[3] for c in capture.call_args_list if c.args[2]=='design.visual_input_sent')
        self.assertEqual(sent['author_design_prompt_sha256'],hashlib.sha256(ctx['author_design_prompt'].encode()).hexdigest())
        self.assertEqual(sent['author_design_prompt_channel'],'tool-result inputText after images')
        row=next(v for v in ctx['visual_inputs'] if v['role']=='page_preview')
        self.assertEqual(row['state'],'attached')
        self.assertEqual(base64.b64decode(result['contentItems'][row['content_index']]['imageUrl'].split(',',1)[1]),Path(preview['pages'][0]).read_bytes())
        self.assertEqual(before,{p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()})

    def test_plain_cue_receipt_requires_that_block_in_the_written_result(self):
        ws=self.native();self.rendered(ws)
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        with patch('design_inputs.record') as capture:result=self.wire(params)
        # Emulate an older transport retaining JSON/pixels but omitting the new
        # standalone text. The receipt must not invent that delivery channel.
        result['contentItems'].pop()
        with patch('design_inputs.record') as capture:self.inputs.sent(params,result)
        sent=next(c.args[3] for c in capture.call_args_list if c.args[2]=='design.visual_input_sent')
        self.assertIn('author_design_prompt_sha256',sent)
        self.assertNotIn('author_design_prompt_channel',sent)

    def test_near_frame_limit_keeps_actual_images_and_omits_only_optional_cue(self):
        ws=self.native();self.rendered(ws)
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        result=self.inputs.handle(params);ctx=json.loads(result['contentItems'][0]['text'])
        ctx.pop('author_design_prompt')
        images=[item for item in result['contentItems'][1:] if item['type']=='inputImage']
        without_cue=self.inputs.reply(True,ctx,images)
        limit=len(json.dumps(without_cue).encode())+16
        with patch('design_inputs.MAX_RESPONSE',limit):bounded=self.wire(params)
        self.assertEqual(bounded['contentItems'][1:],images)
        self.assertNotIn('author_design_prompt',json.loads(bounded['contentItems'][0]['text']))
        self.assertLessEqual(len(json.dumps(bounded).encode()),limit)

    def test_requested_previous_preview_crosses_wire_as_historical_exact_bytes(self):
        ws=self.native();first=self.rendered(ws,'white')
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        self.wire(params)
        part=ws.root/'ppt/slides/slide1.xml';part.write_bytes(part.read_bytes()+b'\n')
        second=self.rendered(ws,'blue')
        result=self.wire({**params,'callId':'call-2','arguments':{**params['arguments'],'compare_previous':True}})
        ctx=json.loads(result['contentItems'][0]['text'])
        rows=ctx['visual_inputs'][:2]
        self.assertEqual([r['role'] for r in rows],['page_preview','previous_page_preview'])
        self.assertEqual(ctx['comparison']['previous_call_id'],'call-1')
        self.assertEqual(ctx['comparison']['native']['workspace_fingerprint'],first['workspace_fingerprint'])
        for row,path in zip(rows,[second['pages'][0],first['pages'][0]]):
            self.assertEqual(row['state'],'attached')
            self.assertEqual(base64.b64decode(result['contentItems'][row['content_index']]['imageUrl'].split(',',1)[1]),Path(path).read_bytes())

    def test_comparison_does_not_cross_threads_or_send_changed_historical_bytes(self):
        ws=self.native();first=self.rendered(ws)
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        self.wire(params)
        part=ws.root/'ppt/slides/slide1.xml';part.write_bytes(part.read_bytes()+b'\n')
        self.rendered(ws,'blue')
        compare={**params,'arguments':{**params['arguments'],'compare_previous':True}}
        result=self.wire({**compare,'threadId':'different-thread','callId':'other'})
        ctx=json.loads(result['contentItems'][0]['text'])
        self.assertEqual(ctx['comparison']['status'],'no_previous_input')
        Path(first['pages'][0]).write_bytes(b'changed historical preview')
        result=self.wire({**compare,'callId':'call-2'})
        ctx=json.loads(result['contentItems'][0]['text'])
        self.assertEqual(ctx['visual_inputs'][1]['state'],'not_attached')
        self.assertEqual(ctx['visual_inputs'][1]['reason'],'changed_since_context')

    def test_missing_stale_or_changed_preview_never_claims_current_visual_delivery(self):
        ws=self.native()
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        def check(reason):
            with patch('design_inputs.record') as capture:
                result=self.wire(params)
            ctx=json.loads(result['contentItems'][0]['text']); row=ctx['visual_inputs'][0]
            self.assertTrue(result['success']);self.assertEqual(row['role'],'page_preview')
            self.assertEqual(row['state'],'not_attached');self.assertEqual(row['reason'],reason)
            self.assertNotIn('author_design_prompt',ctx)
            self.assertNotIn('design.page_preview_sent',[call.args[2] for call in capture.call_args_list])
        check('not_recorded')
        self.rendered(ws)
        part=ws.root/'ppt/slides/slide1.xml';part.write_bytes(part.read_bytes()+b'\n')
        check('stale')
        current=self.rendered(ws);Path(current['pages'][0]).write_bytes(b'changed-preview')
        check('missing_or_changed')

    def test_preview_transport_failure_keeps_prior_receipt_and_workspace_scope(self):
        ws=self.native();self.rendered(ws)
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        with patch('design_inputs.record') as capture:
            with AppServer(cwd=self.job, config={}, command=[sys.executable,'-u','-c',fixture.FAKE_SERVER],
                           on_tool_call=self.inputs.handle, on_tool_result_sent=self.inputs.sent) as server:
                original=server._write
                def broken(value):
                    if value.get('id')=='host-request':raise TransportError('Synthetic write failure')
                    original(value)
                server._write=broken
                with self.assertRaises(TransportError):
                    server.request('test/approval',{'method':'item/tool/call','params':params})
        capture.assert_not_called();self.assertEqual(self.inputs.previews,{})
        escaped={**params,'arguments':{'page_id':'first','workspace':str(self.root)}}
        result=self.inputs.handle(escaped);self.assertFalse(result['success'])

    def test_images_cross_the_actual_tool_result_frame_and_match_registered_bytes(self):
        sent = []; frames = []
        def receipt(params, response):
            # The actual wire write happened first, not just handler preparation.
            self.assertEqual(frames[-1]['result'], response)
            sent.append((params,response))
        with AppServer(cwd=self.job, config={}, command=[sys.executable,'-u','-c',fixture.FAKE_SERVER],
                       on_tool_call=self.inputs.handle, on_tool_result_sent=receipt) as server:
            original = server._write
            def write(value):
                original(value); frames.append(value)
            server._write = write
            registered = server.start_thread(dynamic_tools=self.inputs.specs())
            self.assertEqual(registered['dynamicTools'][0]['name'],TOOL)
            result = server.request('test/approval',{'method':'item/tool/call','params':self.params()})
        self.assertEqual(len(sent),1)
        context = json.loads(result['contentItems'][0]['text'])
        self.assertEqual(context['page']['id'],'first')
        self.assertEqual(context['page']['summary'],'Keep the actual evidence and qualification.')
        self.assertNotIn('author_design_prompt',context)
        self.assertEqual(len(result['contentItems']),3)
        for row in context['visual_inputs']:
            block = result['contentItems'][row['content_index']]
            self.assertEqual(block['type'],'inputImage')
            raw = base64.b64decode(block['imageUrl'].split(',',1)[1])
            self.assertEqual(raw,(self.job/row['file']).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        self.assertNotIn('later.png',json.dumps(context['resources']))
        with patch('design_inputs.record') as record:
            self.inputs.sent(self.params(),result)
        receipt = record.call_args.args[3]
        self.assertEqual(receipt['call_id'],'call-1')
        self.assertEqual(receipt['files'],context['visual_inputs'])
        self.assertNotIn('understood',receipt)

    def test_search_ready_text_and_file_existence_are_not_visual_delivery(self):
        self.plan['pages'][0]['assets'] = []
        self.plan['references'] = []; self.save()
        folder=self.job/'material-prefetch'; folder.mkdir()
        (folder/'index.json').write_text(json.dumps({'requests':[{'state':'ready','kind':'search','text':'Search evidence only'}]}))
        (self.job/'source-notes.md').write_text('```pptx-handoff\n'+json.dumps({
            'page_id':'first','evidence':[{'source':'https://example.test/image.png','claim':'Text only'}]})+'\n```\n')
        result=self.inputs.handle(self.params())
        self.assertTrue(result['success']); self.assertEqual(len(result['contentItems']),1)
        self.assertNotIn('author_design_prompt',json.loads(result['contentItems'][0]['text']))
        with patch('design_inputs.record') as record:
            self.inputs.sent(self.params(),result)
        record.assert_not_called()

    def test_failed_transport_write_does_not_emit_a_delivery_receipt(self):
        with patch('design_inputs.record') as record:
            with AppServer(cwd=self.job, config={}, command=[sys.executable,'-u','-c',fixture.FAKE_SERVER],
                           on_tool_call=self.inputs.handle, on_tool_result_sent=self.inputs.sent) as server:
                original=server._write
                def broken(value):
                    if value.get('id')=='host-request':
                        raise TransportError('Synthetic interrupted response write')
                    original(value)
                server._write=broken
                with self.assertRaises(TransportError):
                    server.request('test/approval',{'method':'item/tool/call','params':self.params()})
        record.assert_not_called()

    def test_missing_unavailable_pending_and_unsupported_files_degrade_without_acquisition(self):
        Image.new('RGB',(4,4),'red').save(self.job/'animation.gif')
        self.plan['pages'][0]['assets']=[{'status':'pending','file':'main.png'},
                                       {'status':'ready','file':'missing.png'},
                                       {'status':'ready','file':'animation.gif'}]
        self.plan['references'][0].update(inspection='unavailable',evidence=None)
        self.save(); before={p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        result=self.inputs.handle(self.params()); context=json.loads(result['contentItems'][0]['text'])
        self.assertTrue(result['success']); self.assertEqual(len(result['contentItems']),1)
        self.assertEqual(context['references'][0]['inspection'],'unavailable')
        self.assertEqual([r['file'] for r in context['visual_inputs']],['missing.png','animation.gif'])
        self.assertTrue(all(r['state']=='not_attached' for r in context['visual_inputs']))
        self.assertEqual(before,{p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()})

    def test_duplicate_file_is_delivered_once_and_later_page_does_not_get_first_page_reference(self):
        (self.job/'source-notes.md').write_text('```pptx-handoff\n'+json.dumps({
            'page_id':'first','materials':[{'file':'main.png','role':'Main subject'}]})+'\n```\n')
        result=self.inputs.handle(self.params()); context=json.loads(result['contentItems'][0]['text'])
        self.assertEqual(len(result['contentItems']),3)
        self.assertEqual(context['visual_inputs'][0]['content_index'],context['visual_inputs'][1]['content_index'])
        later=self.inputs.handle(self.params('later')); context=json.loads(later['contentItems'][0]['text'])
        self.assertEqual(context['references'],[])
        self.assertEqual([r['file'] for r in context['visual_inputs']],['later.png'])

    def test_shared_reference_reuses_only_real_same_thread_receipts_and_can_be_resupplied(self):
        self.plan['references'][0]['applications'][0]['pages'].append('later'); self.save()
        first=self.inputs.handle(self.params())
        with patch('design_inputs.record'):
            self.inputs.sent(self.params(),first)
        later=self.inputs.handle({**self.params('later'),'callId':'call-2'})
        context=json.loads(later['contentItems'][0]['text'])
        self.assertEqual(len(later['contentItems']),2)  # Later material only; reference already sent.
        self.assertEqual(context['references'][0]['applications'][0]['pages'],['later'])
        self.assertEqual(context['visual_inputs'][-1]['state'],'previously_supplied')
        self.assertEqual(context['visual_inputs'][-1]['prior_call_id'],'call-1')
        fresh=self.inputs.handle({**self.params('later'),'threadId':'new-thread'})
        self.assertEqual(len(fresh['contentItems']),3)
        repeat=self.inputs.handle({**self.params(),'arguments':{'page_id':'first','repeat_images':True}})
        self.assertEqual(len(repeat['contentItems']),3)

    def test_escape_changed_file_and_message_limit_do_not_claim_delivery(self):
        (self.root/'private.png').write_bytes((self.job/'main.png').read_bytes())
        (self.job/'link.png').symlink_to(self.root/'private.png')
        self.plan['pages'][0]['assets']=[{'status':'ready','file':'link.png'}]; self.plan['references']=[]; self.save()
        result=self.inputs.handle(self.params())
        self.assertEqual(len(result['contentItems']),1)
        self.plan['pages'][0]['assets']=[{'status':'ready','file':'main.png'}]; self.save()
        context=self.inputs.context('first')
        Image.new('RGB',(43,29),'red').save(self.job/'main.png')
        with patch.object(self.inputs,'context',return_value=context):
            result=self.inputs.handle(self.params())
        self.assertEqual(json.loads(result['contentItems'][0]['text'])['visual_inputs'][0]['reason'],'changed_since_context')
        with patch('design_inputs.MAX_RESPONSE',10):
            result=self.inputs.handle(self.params())
        self.assertEqual(len(result['contentItems']),1)
        self.assertEqual(json.loads(result['contentItems'][0]['text'])['visual_inputs'][0]['state'],'not_attached')

    def test_dsh_and_older_plugins_keep_the_existing_cli_viewer_fallback(self):
        cfg={**self.cfg,'_harness_transport':'dsh-sdk'}
        inputs=PageDesignInputs(cfg,self.job)
        self.assertEqual(inputs.specs(),[])
        self.assertEqual(inputs.context('first')['references'][0]['id'],'work')
        self.assertEqual(PageDesignInputs({**self.cfg,'plugin':str(self.root/'old')},self.job).specs(),[])


if __name__=='__main__': unittest.main()
