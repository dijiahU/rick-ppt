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
import design_inputs
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
        library = self.root/'library'
        templates = library/'templates'; templates.mkdir(parents=True)
        (templates/'index.json').write_text(json.dumps({'pages':[{'id':'t4d1de641-03'}]}))
        self.cfg = {'python':sys.executable, 'plugin':str(ROOT/'pptx-agent'), 'reference_library_root':str(library)}
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

    def key_plan(self, **overrides):
        return {'page_id':'first', 'action':'page_plan', 'kind':'key', 'reference':'t4d1de641-03',
                'takeaway':'注册转化率升至 4.6%', 'relationship':'比较缩减前后的注册流程', 'steps':'先看结果，再看原因',
                'hero':'4.6% 占画面约 40%', 'reading_order':['4.6%', '缩短的流程', '省掉的步骤'], 'cut':'删掉注册术语',
                'visual_idea':'让缩短的注册流程直接指向 4.6% 的终点数字',
                'rejected':'用表格排列步骤会让读者来回寻找被删掉的步骤', 'anchor':'示例：注册由 4 步减到 2 步，转化 3.1% 到 4.6%', 'form':'手机注册页截图的步骤条', 'average':'标题加两列上线前后对照表', **overrides}

    def deck_plan(self, **overrides):
        return {'action':'deck_plan', 'occasion':'婚宴开场，宴会厅大屏', 'audience':'来赴宴的亲友',
                'feeling':'喜庆、甜、被感动', 'expectations':['新人本人的照片或插画', '红金色彩和热闹的现场'],
                'subject':'两位新人', 'wrong_looks':['大面积留白的编辑设计'], **overrides}

    def submit(self, args, *, wire=False):
        params = {**self.params(), 'arguments':args}
        response = self.wire(params) if wire else self.inputs.handle(params)
        return response['success'], json.loads(response['contentItems'][0]['text'])

    def test_deck_plan_crosses_wire_without_page_id_and_is_saved(self):
        schema = self.inputs.specs()[0]['inputSchema']
        self.assertIn('deck_plan', schema['properties']['action']['enum'])
        self.assertNotIn('page_id', schema.get('required', []))
        args = self.deck_plan(references=['  婚礼开场示例  '])
        self.assertLessEqual(set(args), set(schema['properties']))
        ok, result = self.submit(args, wire=True)
        self.assertTrue(ok); self.assertEqual(result['status'], 'accepted')
        self.assertIn('主角和视觉想法都要服务于 feeling 和 expectations', result['instruction'])
        path = self.job/'deck-plan.json'
        self.assertEqual(json.loads(path.read_text()),
                         {**{k:v for k,v in args.items() if k != 'action'}, 'references':['婚礼开场示例']})
        self.assertTrue(self.submit(self.deck_plan())[0])
        self.assertEqual(json.loads(path.read_text())['references'], [])

    def test_deck_plan_lists_all_missing_and_malformed_fields(self):
        ok, result = self.submit({'action':'deck_plan'})
        self.assertFalse(ok); self.assertEqual(result['status'], 'invalid')
        self.assertEqual({issue.split()[0] for issue in result['issues']},
                         {'occasion', 'audience', 'feeling', 'subject', 'expectations', 'wrong_looks'})
        ok, result = self.submit(self.deck_plan(occasion=' ', audience=[], subject=None,
                                               expectations=['新人合影', '红金', '', '场景配色清晰', '灯光照亮舞台', '宾客上台致辞'],
                                               wrong_looks=['商务风'] * 5 + [' '], references=['示例'] * 4, page_id='first'))
        self.assertFalse(ok); self.assertEqual(result['status'], 'invalid')
        for issue in ('occasion 必须', 'audience 必须', 'subject 必须', 'expectations 必须', 'expectations 第 1 条',
                      'expectations 第 2 条', 'expectations 第 3 条', 'wrong_looks 必须', 'wrong_looks 第 6 条',
                      'references 必须', '未知设计单字段：page_id'):
            self.assertTrue(any(v.startswith(issue) for v in result['issues']), result)
        self.assertFalse((self.job/'deck-plan.json').exists())

    def test_deck_plan_feeling_requires_a_specific_mood_after_stripping_style(self):
        for feeling in ('高级、简洁、克制、专业、现代', '整体优雅与很有专业感', 'modern and clean', '，123。'):
            with self.subTest(feeling=feeling):
                ok, result = self.submit(self.deck_plan(occasion='课堂投影', feeling=feeling))
                self.assertFalse(ok); self.assertEqual(result['status'], 'invalid')
                self.assertTrue(any(issue.startswith('feeling ') for issue in result['issues']))
        self.assertTrue(self.submit(self.deck_plan(occasion='课堂投影', feeling='克制、好奇'))[0])

    def test_social_deck_plan_checks_feeling_and_people(self):
        for changes in (
                {'occasion':'婚宴开场', 'feeling':'喜悦、克制'},
                {'audience':'等着招新的同学', 'feeling':'冷静、好奇'},
                {'feeling':'喜庆、低调'},
                {'occasion':'颁奖晚会', 'feeling':'激动、极简'},
                {'occasion':'婚宴开场', 'expectations':['红金色彩装点宴会厅', '拍摄舞台灯光与花墙', '无人机拍摄的宴会厅照片']}):
            with self.subTest(changes=changes):
                ok, result = self.submit(self.deck_plan(**{'occasion':'礼堂大屏', **changes}))
                self.assertFalse(ok); self.assertEqual(result['status'], 'invalid')
                self.assertIn('这是庆典或社交场合，观众期待热闹和看到人', result['issues'])
        self.assertFalse((self.job/'deck-plan.json').exists())
        self.assertTrue(self.submit(self.deck_plan(occasion='社团招新，礼堂投影', audience='有意入社的同学',
                                                   feeling='好奇、想加入', expectations=['社员正在动手搭天线', '试用设备的真实场景'],
                                                   subject='无线电社的社员'))[0])

    def test_failed_deck_plan_update_preserves_saved_plan(self):
        self.assertTrue(self.submit(self.deck_plan())[0])
        path = self.job/'deck-plan.json'
        before = path.read_bytes()
        for args in (self.deck_plan(feeling='高级、简洁'), self.deck_plan(subject='新人' * 10000)):
            ok, result = self.submit(args)
            self.assertFalse(ok); self.assertEqual(result['status'], 'invalid')
        with patch.object(Path, 'replace', side_effect=OSError('synthetic write failure')):
            ok, result = self.submit(self.deck_plan(feeling='开心、激动'))
        self.assertFalse(ok); self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.job.glob('.deck-plan-*')), [])

    def test_key_plan_requires_deck_plan_but_ordinary_plan_does_not(self):
        ok, result = self.submit(self.key_plan(), wire=True)
        self.assertFalse(ok); self.assertEqual(result['status'], 'invalid')
        self.assertIn('先用 action=deck_plan 提交整套场合与观众单', result['issues'])
        self.assertFalse((self.job/'page-plans.json').exists())
        ok, result = self.submit(self.key_plan(kind='ordinary', device='左侧铺灰色带'))
        self.assertTrue(ok); self.assertEqual(result['status'], 'accepted')
        self.assertNotIn('deck_plan', result)

    def test_key_plan_crosses_wire_and_updates_saved_page(self):
        deck = self.deck_plan()
        self.assertTrue(self.submit(deck)[0])
        args = self.key_plan()
        ok, result = self.submit(args, wire=True)
        self.assertTrue(ok); self.assertEqual(result['status'], 'accepted')
        self.assertNotIn('reading_order_note', result)
        self.assertEqual(result['instruction'], '阅读顺序已保存在设计单里，备注只写演讲稿。')
        self.assertEqual(result['deck_plan'], {k:deck[k] for k in ('feeling', 'expectations')})
        path = self.job/'page-plans.json'
        self.assertEqual(json.loads(path.read_text()),
                         {'first':{k:v for k,v in args.items() if k not in ('action', 'page_id')}})
        self.assertEqual(self.submit(self.key_plan(page_id='later', kind='ordinary', device='左侧铺灰色带'))[1]['deck_plan'], result['deck_plan'])
        self.assertTrue(self.submit(self.key_plan(page_id='later'))[0])
        self.assertTrue(self.submit(self.key_plan(cut='删去重复标签'))[0])
        saved = json.loads(path.read_text())
        self.assertEqual(set(saved), {'first', 'later'})
        self.assertEqual(saved['first']['cut'], '删去重复标签')
        self.assertEqual(saved['later']['cut'], args['cut'])

    def test_failed_plan_update_preserves_existing_file(self):
        self.assertTrue(self.submit(self.deck_plan())[0])
        self.assertTrue(self.submit(self.key_plan())[0])
        path = self.job/'page-plans.json'
        before = path.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('synthetic write failure')):
            ok, result = self.submit(self.key_plan(cut='删去重复标签'))
        self.assertFalse(ok); self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.job.glob('.page-plans-*')), [])

    def test_key_plan_reports_each_failed_requirement(self):
        self.assertTrue(self.submit(self.deck_plan())[0])
        for changes, field in [
                ({'hero':'转化率数字最大'}, 'hero'),
                ({'takeaway':'采用简洁高级风格', 'visual_idea':'采用简洁高级留白大字低饱和强烈对比'}, 'visual_idea'),
                ({'visual_idea':'把北方商路画成一连串接力的驿站'}, 'visual_idea'),
                ({'visual_idea':'4.6% 终点'}, 'visual_idea'),
                ({'rejected':'表格难读'}, 'rejected'),
                ({'rejected':'改成橙色卡片并放在画面中间'}, 'rejected'),
                ({'rejected':'：因为读者找不到自己要看的内容'}, 'rejected'),
                ({'reading_order':['结果', '流程', '细节', '脚注']}, 'reading_order'),
                ({'page_id':'unknown'}, 'page_id')]:
            with self.subTest(field=field, changes=changes):
                ok, result = self.submit(self.key_plan(**changes))
                self.assertFalse(ok); self.assertEqual(result['status'], 'invalid')
                self.assertTrue(any(issue.startswith(field) for issue in result['issues']), result)
        args = self.key_plan(steps='  ', cut='')
        del args['takeaway'], args['reading_order']
        ok, result = self.submit(args)
        self.assertFalse(ok)
        self.assertEqual({issue.split()[0] for issue in result['issues']}, {'takeaway', 'steps', 'cut', 'reading_order'})
        self.assertFalse((self.job/'page-plans.json').exists())

    def test_key_plan_matches_english_words_and_numeric_content(self):
        self.assertTrue(self.submit(self.deck_plan())[0])
        args = self.key_plan(takeaway='Enrollment is accelerating', hero='The enrollment curve takes 40% of the slide',
                             visual_idea='Draw a single ENROLLMENT curve as a diverging path',
                             rejected='Use four cards because they hide the inflection')
        self.assertTrue(self.submit(args)[0])
        self.assertFalse(self.submit({**args, 'visual_idea':'Draw enrollments along a winding path'})[0])
        self.assertTrue(self.submit(self.key_plan(takeaway='课程注册', hero='40% 画幅给最大的数字 4.6%',
                                                 visual_idea='最后只点亮 4.6% 让终点数字从灰色路径中跳出来'))[0])

    def test_ordinary_plan_requires_and_saves_a_quiet_system_device(self):
        args = {'page_id':'first', 'action':'page_plan', 'kind':'ordinary', 'reference':'craft-3',
                'takeaway':'注册变快', 'relationship':'对照', 'reading_order':['注册结果'], 'anchor':'示例：注册由 4 步减到 2 步，转化 3.1% 到 4.6%', 'form':'手机注册页截图的步骤条', 'average':'标题加两列上线前后对照表'}
        for invalid in (args, {**args, 'device':'  红点。 '}, {**args, 'device':1234}):
            with self.subTest(device=invalid.get('device')):
                ok, result = self.submit(invalid, wire=True)
                self.assertFalse(ok)
                self.assertEqual(result['issues'], ['普通页也要写本页的设计手段（来自 quiet_system 的第二个面、展示字或标记）'])
        self.assertFalse((self.job/'page-plans.json').exists())
        self.assertIn('device', self.inputs.specs()[0]['inputSchema']['properties'])
        args['device'] = '  页码左边加红点  '
        ok, result = self.submit(args, wire=True)
        self.assertTrue(ok)
        self.assertEqual(result, {'status': 'accepted', 'instruction': '阅读顺序已保存在设计单里，备注只写演讲稿。'})
        saved = json.loads((self.job/'page-plans.json').read_text())['first']
        self.assertEqual(saved['reading_order'], ['注册结果'])
        self.assertEqual(saved['device'], '页码左边加红点')
        self.assertEqual(saved['reference'], 'craft-3')
        self.assertTrue(self.submit({**args, 'hero':'流程', 'visual_idea':'留白', 'rejected':'不用'})[0])
        ok, result = self.submit({**args, 'takeaway':' ', 'relationship':'', 'reading_order':[' ']})
        self.assertFalse(ok)
        self.assertEqual({issue.split()[0] for issue in result['issues']}, {'takeaway', 'relationship', 'reading_order'})

    def test_both_page_plan_kinds_require_a_real_page_id_or_craft_move(self):
        self.assertTrue(self.submit(self.deck_plan())[0])
        self.assertIn('reference', self.inputs.specs()[0]['inputSchema']['properties'])
        path = self.job/'page-plans.json'
        message = '每页设计前先参考：用 pptx_reference_library action=inspire / search 找一张模板页（填它的 id），或用 action=craft 看工艺示例（填 craft-N）'
        for plan in (self.key_plan(), self.key_plan(kind='ordinary', device='左侧铺灰色带')):
            for reference in ('t4d1de641-03', 'craft-5'):
                with self.subTest(kind=plan['kind'], reference=reference):
                    self.assertTrue(self.submit({**plan, 'reference':reference})[0])
                    self.assertEqual(json.loads(path.read_text())['first']['reference'], reference)
            before = path.read_bytes()
            del plan['reference']
            for invalid in (plan, {**plan, 'reference':'t4d1de641-99'}, {**plan, 'reference':'craft-7'}):
                with self.subTest(kind=plan['kind'], reference=invalid.get('reference')):
                    ok, result = self.submit(invalid)
                    self.assertFalse(ok)
                    self.assertEqual(result['issues'], [message])
                    self.assertEqual(path.read_bytes(), before)

    def test_repeated_craft_reference_gets_a_note_without_rejection(self):
        ids = ['p1','p2','p3','p4']
        (self.job/'outline.json').write_text(json.dumps({'slides':[{'id':i,'title':i,'summary':i} for i in ids]}))
        plan = {'action':'page_plan', 'kind':'ordinary', 'takeaway':'注册变快', 'relationship':'对照',
                'reading_order':['注册结果'], 'device':'左侧铺灰色带', 'reference':'craft-4', 'anchor':'示例：注册由 4 步减到 2 步，转化 3.1% 到 4.6%', 'form':'手机注册页截图的步骤条', 'average':'标题加两列上线前后对照表'}
        notes = []
        for i in ids[:3]:
            ok, result = self.submit({**plan, 'page_id':i}, wire=True)
            self.assertTrue(ok); notes.append(result.get('reference_note'))
        self.assertEqual(notes[:2], [None, None])
        self.assertIn('已有 3 页参考同一个 craft-4', notes[2])
        self.assertIn('craft-2', notes[2])
        ok, result = self.submit({**plan, 'page_id':'p4', 'reference':'craft-2'}, wire=True)
        self.assertTrue(ok); self.assertNotIn('reference_note', result)

    def test_both_kinds_require_anchor_form_and_average(self):
        self.assertTrue(self.submit(self.deck_plan())[0])
        for kind in ('key', 'ordinary'):
            plan = self.key_plan(kind=kind, **({'device':'左侧铺灰色带'} if kind == 'ordinary' else {}))
            for field in ('anchor', 'form', 'average'):
                with self.subTest(kind=kind, field=field):
                    ok, result = self.submit({**plan, field:'短'})
                    self.assertFalse(ok)
                    self.assertTrue(any(issue.startswith(field) for issue in result['issues']))
            self.assertTrue(self.submit({**plan, 'form':'无：这页是纯引语'})[0])
            saved = json.loads((self.job/'page-plans.json').read_text())['first']
            self.assertEqual((saved['form'], saved['average']), ('无：这页是纯引语', '标题加两列上线前后对照表'))

    def test_page_plan_skips_reference_check_without_library(self):
        self.cfg['reference_library_root'] = str(self.root/'missing-library')
        self.assertTrue(self.submit(self.deck_plan())[0])
        plan = self.key_plan()
        del plan['reference']
        self.assertTrue(self.submit(plan)[0])
        self.assertNotIn('reference', json.loads((self.job/'page-plans.json').read_text())['first'])
        self.assertTrue(self.submit({**plan, 'reference':'unavailable-on-server'})[0])

    def test_render_returns_missing_warning_first_then_saved_plan_alongside_pixels(self):
        ws = self.native(); self.rendered(ws)
        params = {**self.params(), 'arguments':{'page_id':'first', 'workspace':str(ws.root)}}
        self.assertNotIn('plan_missing', json.loads(self.wire(self.params())['contentItems'][0]['text']))
        response = self.wire(params)
        missing = json.loads(response['contentItems'][0]['text'])
        self.assertTrue(response['success'])
        self.assertEqual(next(iter(missing)), 'plan_missing')
        self.assertEqual(missing['plan_missing'],
                         '这页是封面、收尾或关键页，先提交 page_plan，再判断渲染是否达到设计单，不合格就按设计单重做')
        self.assertEqual(next(v['state'] for v in missing['visual_inputs'] if v['role']=='page_preview'), 'attached')
        self.assertTrue(self.submit(self.key_plan(kind='ordinary', device='左侧铺灰色带'))[0])
        self.assertIn('plan_missing', json.loads(self.wire(params)['contentItems'][0]['text']))
        self.assertTrue(self.submit(self.deck_plan())[0])
        args = self.key_plan()
        self.assertTrue(self.submit(args)[0])
        context = json.loads(self.wire(params)['contentItems'][0]['text'])
        self.assertNotIn('plan_missing', context)
        self.assertEqual(context['plan'], {k:args[k] for k in ('takeaway', 'hero', 'reading_order', 'visual_idea', 'anchor', 'form', 'average')})
        self.assertIn('不要改写设计单去迁就现状', context['plan_check'])

    def test_closing_page_and_author_marked_key_pages_use_workspace_outline(self):
        path = self.job/'outline.json'
        pages = json.loads(path.read_text())['slides']
        pages[1:1] = [{'id':'middle'}, {'id':'marked', 'kind':'key'}]
        path.write_text(json.dumps({'slides':pages}))
        def preview(page, number, **flags):
            params = {**self.params(page), 'arguments':{'page_id':page, 'workspace':'local', **flags}}
            with patch.object(self.inputs, 'context', return_value={'page':{'id':page}, 'page_number':number}):
                return json.loads(self.inputs.handle(params)['contentItems'][0]['text'])
        key, ordinary = design_inputs.PLAN_MISSING, design_inputs.ORDINARY_PLAN_MISSING
        self.assertEqual(preview('later', 4)['plan_missing'], key)
        self.assertEqual(preview('marked', 3)['plan_missing'], key)
        self.assertEqual(preview('middle', 2)['plan_missing'], ordinary)
        self.assertEqual(preview('middle', 2, kind='key')['plan_missing'], key)
        path.unlink()
        self.assertEqual(preview('later', 4)['plan_missing'], ordinary)
        self.assertEqual(preview('first', 1)['plan_missing'], key)

    def test_author_is_told_to_submit_before_building(self):
        from design_roles import role_instruction
        prompt = role_instruction(self.cfg, 'author')
        self.assertIn('expects to see and how they should feel, then submit page_plan', prompt)
        self.assertLess(prompt.index('use deck_plan'), prompt.index('submit page_plan'))
        self.assertIn('submit the design sheet with page_plan before building', prompt)
        fallback = role_instruction({**self.cfg, '_harness_transport':'dsh-sdk'}, 'author')
        self.assertNotIn('page_plan', fallback); self.assertNotIn('deck_plan', fallback)

    def test_composition_method_crosses_actual_tool_wire_without_creating_a_page(self):
        before={p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        with patch('design_inputs.record') as capture:
            result=self.wire(self.params())
        ctx=json.loads(result['contentItems'][0]['text'])
        self.assertEqual(ctx['author_design_prompt_stage'],'composition')
        self.assertEqual(result['contentItems'][-1],{'type':'inputText','text':ctx['author_design_prompt']})
        self.assertTrue(any(x['type']=='inputImage' for x in result['contentItems']))
        sent=next(c.args[3] for c in capture.call_args_list if c.args[2]=='design.author_cue_sent')
        self.assertEqual(sent['sha256'],hashlib.sha256(result['contentItems'][-1]['text'].encode()).hexdigest())
        self.assertEqual(before,{p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()})

    def test_current_deck_direction_reaches_wire_with_page_and_scoped_reference_pixels(self):
        from design_roles import composition_instruction, rendered_page_instruction
        self.plan['design_direction']='Provisional: preserve supplied textured background; emphasis belongs to the specimen.'
        self.save()
        before={p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        entry=self.wire(self.params())
        ctx=json.loads(entry['contentItems'][0]['text'])
        self.assertEqual(ctx['design_direction'],self.plan['design_direction'])
        self.assertEqual(entry['contentItems'][-1]['text'],composition_instruction(self.cfg))
        self.assertEqual(before,{p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()})
        ws=self.native();preview=self.rendered(ws)
        self.plan['design_direction']='Revised provisional relationship after inspecting the actual page.'
        self.save()
        before={p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        result=self.wire({**self.params(),'callId':'render-check',
                          'arguments':{'page_id':'first','workspace':str(ws.root)}})
        ctx=json.loads(result['contentItems'][0]['text'])
        self.assertEqual(ctx['design_direction'],self.plan['design_direction'])
        self.assertEqual(result['contentItems'][-1]['text'],rendered_page_instruction(self.cfg))
        for role,path in [('page_preview',Path(preview['pages'][0])),('reference:work',self.job/'reference.png')]:
            row=next(v for v in ctx['visual_inputs'] if v['role']==role)
            self.assertEqual(row['state'],'attached')
            self.assertEqual(base64.b64decode(result['contentItems'][row['content_index']]['imageUrl'].split(',',1)[1]),path.read_bytes())
        self.assertEqual(before,{p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()})
        later=json.loads(self.wire(self.params('later'))['contentItems'][0]['text'])
        self.assertEqual(later['design_direction'],self.plan['design_direction'])
        self.assertEqual(later['references'],[])  # Shared direction is not shared image permission/application.

    def test_missing_direction_does_not_invent_a_palette_or_require_a_record(self):
        for value in (None, {'palette':'unvalidated record'}):
            if value is None:self.plan.pop('design_direction',None)
            else:self.plan['design_direction']=value
            self.save()
            result=self.wire(self.params())
            self.assertTrue(result['success'])
            self.assertNotIn('design_direction',json.loads(result['contentItems'][0]['text']))

    def test_actual_formula_objects_reach_author_wire_and_frozen_review_input(self):
        from lxml import etree
        from pptx_core.common import NS
        from review_packet import collect
        from review_materials import prepare_review_materials
        ws=self.native();part=ws.root/'ppt/slides/slide1.xml'
        tree=etree.parse(str(part))
        shape=etree.fromstring(f'''<p:sp xmlns:p="{NS['p']}" xmlns:a="{NS['a']}">
          <p:nvSpPr><p:cNvPr id="2" name="Routing equation"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
          <p:spPr><a:xfrm><a:off x="914400" y="914400"/><a:ext cx="5486400" cy="914400"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
          <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>p_R = q_E^2</a:t></a:r></a:p></p:txBody></p:sp>''')
        tree.find('.//p:spTree',NS).append(shape);tree.write(str(part),encoding='UTF-8',xml_declaration=True)
        rendered=self.rendered(ws)
        before={p:p.read_bytes() for p in ws.root.rglob('*') if p.is_file()}
        params={**self.params(),'arguments':{'page_id':'first','workspace':str(ws.root)}}
        result=self.wire(params)
        ctx=json.loads(result['contentItems'][0]['text'])
        facts=ctx['native']['formula_inventory']
        self.assertEqual(facts['warnings'][0]['object_id'],'2')
        self.assertEqual(facts['warnings'][0]['object_name'],'Routing equation')
        guide=(ROOT/'pptx-agent/skills/pptx/references/technical/formula-fidelity.md').read_text()
        self.assertIn(guide,result['contentItems'][-1]['text'])
        raw=base64.b64decode(result['contentItems'][1]['imageUrl'].split(',',1)[1])
        self.assertEqual(raw,Path(rendered['pages'][0]).read_bytes())
        packet=self.job/'review'
        with patch('review_packet.state_previews',return_value={'frames':[]}):
            inventory=collect(ws.root,rendered,packet)
        self.assertEqual(inventory['slides'][0]['formula_inventory'],facts)
        for role in ('visual','content-first'):
            prompt,images=prepare_review_materials(packet,role)
            self.assertIn('possible-plain-math-script',prompt)
            self.assertIn('Routing equation',prompt)
            self.assertIn('Literal code may intentionally use underscores',prompt)
            self.assertIn('reading-page-1.png',images)
            self.assertNotIn('Actual source notes',prompt)
        self.assertEqual(before,{p:p.read_bytes() for p in ws.root.rglob('*') if p.is_file()})

    def test_formula_guide_stays_conditional_and_missing_guide_preserves_images(self):
        result=self.wire(self.params())
        self.assertNotIn('# Formula fidelity',result['contentItems'][-1]['text'])
        context=self.inputs.context('first')
        context['native']={'formula_inventory':{'warnings':[{'kind':'possible-plain-math-script'}]}}
        with patch.object(self.inputs,'context',return_value=context):
            # A historical plugin lacking the optional guide must still deliver
            # actual material bytes. Read failures never authorize other paths.
            real_read=__import__('design_inputs').read_scoped
            def missing(root,path,limit):
                if str(path).endswith('formula-fidelity.md'):raise FileNotFoundError(path)
                return real_read(root,path,limit)
            with patch('design_inputs.read_scoped',side_effect=missing):
                result=self.inputs.handle({**self.params(),'arguments':{'page_id':'first','repeat_images':True}})
        self.assertTrue(result['success'])
        self.assertTrue(any(x['type']=='inputImage' for x in result['contentItems']))
        self.assertNotIn('# Formula fidelity',result['contentItems'][-1]['text'])

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
            self.assertEqual(ctx['author_design_prompt_stage'],'composition')
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
        self.assertEqual(context['author_design_prompt_stage'],'composition')
        self.assertEqual(sum(x['type']=='inputImage' for x in result['contentItems']),2)
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
        self.assertTrue(result['success']); self.assertFalse(any(x['type']=='inputImage' for x in result['contentItems']))
        self.assertEqual(json.loads(result['contentItems'][0]['text'])['author_design_prompt_stage'],'composition')
        with patch('design_inputs.record') as record:
            self.inputs.sent(self.params(),result)
        self.assertEqual([c.args[2] for c in record.call_args_list],['design.author_cue_sent'])

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
        self.assertTrue(result['success']); self.assertFalse(any(x['type']=='inputImage' for x in result['contentItems']))
        self.assertEqual(context['references'][0]['inspection'],'unavailable')
        self.assertEqual([r['file'] for r in context['visual_inputs']],['missing.png','animation.gif'])
        self.assertTrue(all(r['state']=='not_attached' for r in context['visual_inputs']))
        self.assertEqual(before,{p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()})

    def test_duplicate_file_is_delivered_once_and_later_page_does_not_get_first_page_reference(self):
        (self.job/'source-notes.md').write_text('```pptx-handoff\n'+json.dumps({
            'page_id':'first','materials':[{'file':'main.png','role':'Main subject'}]})+'\n```\n')
        result=self.inputs.handle(self.params()); context=json.loads(result['contentItems'][0]['text'])
        self.assertEqual(sum(x['type']=='inputImage' for x in result['contentItems']),2)
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
        self.assertEqual(sum(x['type']=='inputImage' for x in later['contentItems']),1)  # Later material only; reference already sent.
        self.assertEqual(context['references'][0]['applications'][0]['pages'],['later'])
        self.assertEqual(context['visual_inputs'][-1]['state'],'previously_supplied')
        self.assertEqual(context['visual_inputs'][-1]['prior_call_id'],'call-1')
        fresh=self.inputs.handle({**self.params('later'),'threadId':'new-thread'})
        self.assertEqual(sum(x['type']=='inputImage' for x in fresh['contentItems']),2)
        repeat=self.inputs.handle({**self.params(),'arguments':{'page_id':'first','repeat_images':True}})
        self.assertEqual(sum(x['type']=='inputImage' for x in repeat['contentItems']),2)

    def test_escape_changed_file_and_message_limit_do_not_claim_delivery(self):
        (self.root/'private.png').write_bytes((self.job/'main.png').read_bytes())
        (self.job/'link.png').symlink_to(self.root/'private.png')
        self.plan['pages'][0]['assets']=[{'status':'ready','file':'link.png'}]; self.plan['references']=[]; self.save()
        result=self.inputs.handle(self.params())
        self.assertFalse(any(x['type']=='inputImage' for x in result['contentItems']))
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


class FestiveFeelingTests(unittest.TestCase):
    def test_wedding_needs_a_celebration_feeling(self):
        from design_inputs import deck_plan_issues
        plan = dict(occasion='婚宴开场，宴会厅大屏', audience='新人的亲友', feeling='温暖、亲切、会心',
                    expectations=['看见两位新人相识的小事', '新人本人的照片或插画'], subject='两位新人',
                    wrong_looks=['商务风'], references=[])
        self.assertTrue(any('庆典场合' in issue for issue in deck_plan_issues(plan)))
        self.assertEqual(deck_plan_issues(dict(plan, feeling='喜庆、温馨、甜蜜')), [])
