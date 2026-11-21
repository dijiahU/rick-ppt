"""Offline: critique tool validation, prompt/images handed to a fresh thread, call limit."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import design_critique as dc


class FakeServer:
    seen = {}
    def __init__(self, cwd, config, **kwargs): self.cwd = cwd; FakeServer.seen['config'] = config
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def start_thread(self): return {'thread': {'id': 't'}}
    def start_turn(self, thread, prompt, images=None):
        FakeServer.seen.update(prompt=prompt, images=[Path(i).name for i in images]); return {'id': 'u'}
    def wait_turn(self, *a, **k): return {'status': 'completed'}
    def result_text(self, *a): return 'DECK DIRECTION: use the mural palette.\nPage 1: 6/10\n1. Enlarge the mural to full bleed.'


class Tests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.job = Path(t.name).resolve()
        (self.job / 'request.json').write_text(json.dumps({'title': '丝绸之路', 'brief': '初二历史课件', 'language': 'zh-CN', 'pages': 5}))
        (self.job / 'r').mkdir()
        for n in (1, 2): (self.job / f'r/page-{n}.png').write_bytes(b'\x89PNG')
        self.tool = dc.DesignCritique({}, self.job)

    def call(self, **args):
        args.setdefault('wait', True)
        with patch.object(dc, 'AppServer', FakeServer):
            return self.tool.handle({'tool': dc.TOOL, 'arguments': args})

    def test_returns_instructions_and_records_them(self):
        reply = self.call(images=['r/page-1.png', 'r/page-2.png'], pages=[1, 2])
        self.assertTrue(reply['success']); self.assertIn('Enlarge the mural', reply['contentItems'][0]['text'])
        self.assertIn('初二历史课件', FakeServer.seen['prompt']); self.assertIn('Simplified Chinese', FakeServer.seen['prompt'])
        self.assertIn('SimSun for Chinese', FakeServer.seen['prompt']); self.assertIn('DengXian', FakeServer.seen['prompt']); self.assertIn('declared background', FakeServer.seen['prompt'])
        self.assertIn('restrained genres', FakeServer.seen['prompt'])
        self.assertNotIn('occasion and audience sheet (deck-plan.json)', FakeServer.seen['prompt'])
        self.assertIn('Start with "DECK DIRECTION": is the register right', FakeServer.seen['prompt'])
        self.assertEqual(FakeServer.seen['images'], ['00.png', '01.png'])
        self.assertEqual(FakeServer.seen['config']['tools']['web_search'] if 'tools' in FakeServer.seen['config'] else 'disabled', 'disabled')
        self.assertEqual(len(list((self.job / 'design-critique').glob('*.json'))), 1)

    def test_background_critique_returns_at_once_and_is_delivered_later(self):
        import time
        with patch.object(dc, 'AppServer', FakeServer):
            reply = self.tool.handle({'tool': dc.TOOL, 'arguments': {'images': ['r/page-1.png'], 'pages': [1]}})
            self.assertTrue(reply['success']); self.assertIn('started in the background', reply['contentItems'][0]['text'])
            for _ in range(100):
                text = self.tool.deliver()
                if text:break
                time.sleep(0.02)
        self.assertIn('Enlarge the mural', text); self.assertIn('[pages 1]', text)
        self.assertEqual(self.tool.deliver(), '')  # delivered once

    def test_spec_matches_the_shape_app_server_accepts(self):
        import asset_libraries
        reference = asset_libraries.AssetLibraries({}, self.job).specs()[0]
        spec = self.tool.specs()[0]
        self.assertEqual(set(spec), set(reference))
        self.assertEqual(spec['type'], 'function')

    def test_registered_reference_works_are_attached_automatically(self):
        (self.job / 'references').mkdir(); (self.job / 'references/ref.png').write_bytes(b'\x89PNG')
        (self.job / 'decision-plan.json').write_text(json.dumps({'references': [
            {'id': 'R1', 'inspection': 'local_image', 'evidence': 'references/ref.png'},
            {'id': 'R2', 'inspection': 'read_text', 'evidence': 'references/notes.md'}]}))
        self.assertTrue(self.call(images=['r/page-1.png'])['success'])
        self.assertEqual(FakeServer.seen['images'], ['00.png', '01.png'])
        self.assertIn('real reference examples', FakeServer.seen['prompt'])

    def test_deck_style_reaches_the_critic(self):
        (self.job / 'deck-style.json').write_text(json.dumps({'register': 'restrained', 'colors': {'primary': '1F5FBF'}}))
        self.call(images=['r/page-1.png'])
        self.assertIn('register restrained', FakeServer.seen['prompt']); self.assertIn('1F5FBF', FakeServer.seen['prompt'])

    def test_deck_plan_reaches_the_critic_with_an_image_only_audience_check(self):
        plan = {'occasion': '初二历史课，教室投影', 'audience': '跟随老师读图的初二学生', 'feeling': '好奇、惊叹',
                'expectations': ['历史商队穿过绿洲的情景', '地图上清楚的驿站路线'], 'wrong_looks': ['商务汇报风']}
        (self.job / 'deck-plan.json').write_text(json.dumps({**plan, 'subject': '真实的丝路商队', 'references': []}))
        reply = self.call(images=['r/page-1.png'])
        self.assertTrue(reply['success']); self.assertIn('DECK DIRECTION: use the mural palette.', reply['contentItems'][0]['text'])
        prompt = FakeServer.seen['prompt']
        self.assertIn(json.dumps(plan, ensure_ascii=False), prompt)
        self.assertIn('any design sheet below states intent, not proof', prompt)
        self.assertIn('In the first sentence of "DECK DIRECTION", answer based only on the attached rendered pages', prompt)
        self.assertIn('makes this audience feel the intended feeling, shows what is in expectations, and falls into any of wrong_looks', prompt)
        self.assertIn('With three or more pages add "RHYTHM"', prompt)

    def test_submitted_page_design_sheet_reaches_the_critic(self):
        (self.job / 'outline.json').write_text(json.dumps({'slides': [{'id': 'intro'}, {'id': 'trade-routes'}]}))
        plan = {'kind': 'key', 'takeaway': '丝绸在绿洲接力', 'relationship': '地图', 'steps': '先路线后驿站',
                'hero': '路线占 70%', 'reading_order': ['路线', '驿站'], 'cut': '古国年表',
                'visual_idea': '让路线在每个绿洲驿站换色表示商帮接力', 'rejected': '改用时间线会让读者看不出路线'}
        (self.job / 'page-plans.json').write_text(json.dumps({'intro': {'takeaway': '未提交点评的封面'}, 'trade-routes': plan}))
        reply = self.call(images=['r/page-2.png'], pages=[2])
        self.assertTrue(reply['success'])
        prompt = FakeServer.seen['prompt']
        self.assertIn(json.dumps({2: plan}, ensure_ascii=False), prompt)
        self.assertIn('answer whether visual_idea is actually visible in the image', prompt)
        self.assertNotIn('未提交点评的封面', prompt)

    def test_rejects_files_outside_task_and_enforces_limit(self):
        self.assertFalse(self.call(images=['../../etc/hosts'])['success'])
        self.assertFalse(self.call(images=[])['success'])
        for _ in range(dc.MAX_CALLS): self.assertTrue(self.call(images=['r/page-1.png'])['success'])
        self.assertIn('limit', self.call(images=['r/page-1.png'])['contentItems'][0]['text'])


if __name__ == '__main__': unittest.main()
