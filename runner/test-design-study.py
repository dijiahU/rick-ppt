import base64, io, json, sys, tempfile, unittest
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_study


class DesignStudyTest(unittest.TestCase):
    def setUp(self):
        self.job = Path(tempfile.mkdtemp())
        im = Image.new('RGB', (1200, 675), (240, 236, 228))
        d = ImageDraw.Draw(im)
        for k in range(0, 360, 12):  # a busy subject on the right
            d.line([(760 + k, 120), (1180, 120 + k)], fill=(30, 40, 50), width=4)
        d.rectangle([80, 520, 200, 560], fill=(200, 40, 30))  # small red accent
        (self.job / 'references').mkdir()
        im.save(self.job / 'references' / 'r.png')
        self.tool = design_study.DesignStudy({}, self.job)

    def test_measures_focal_quiet_space_and_accent(self):
        reply = self.tool.handle({'arguments': {'file': 'references/r.png'}})
        self.assertTrue(reply['success'])
        value = json.loads(reply['contentItems'][0]['text'])
        self.assertGreater(value['focal_point']['centre'][0], .6)
        self.assertEqual(value['quiet_space']['mostly'], 'left')
        self.assertEqual(value['palette'][0]['role'], 'dominant'); self.assertEqual(len(value['suggested']['light_ground']), 2)
        self.assertTrue(any(c.get('role') == 'accent' and c['hex'].startswith(('C', 'D', 'B')) for c in value['palette']))
        self.assertEqual(reply['contentItems'][1]['type'], 'inputImage')

    def test_compare_sets_reference_beside_page(self):
        Image.new('RGB', (1333, 750), 'white').save(self.job / 'page.png')
        reply = self.tool.handle({'arguments': {'file': 'references/r.png', 'compare': 'page.png'}})
        self.assertTrue(reply['success'])
        self.assertEqual(json.loads(reply['contentItems'][0]['text'])['page'], 'page.png')
        self.assertEqual(reply['contentItems'][1]['type'], 'inputImage')

    def study(self, im, name='x.png'):
        im.save(self.job / name)
        reply = self.tool.handle({'arguments': {'file': name}})
        self.assertTrue(reply['success'])
        return json.loads(reply['contentItems'][0]['text']), reply

    def test_transparent_png_reads_as_white_page(self):
        im = Image.new('RGBA', (800, 600), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([500, 150, 750, 400], fill=(20, 60, 160, 255))
        value, _ = self.study(im)
        self.assertEqual(value['palette'][0]['hex'], 'FFFFFF')
        self.assertGreater(value['value_masses']['light'], .8)

    def test_flat_picture_has_no_busy_border_or_false_focus(self):
        # PIL edge filters copy the raw outer pixels; that used to make every border cell 'busy'.
        value, _ = self.study(Image.new('RGB', (1000, 600), (30, 90, 160)))
        self.assertEqual(value['quiet_space']['share'], 1.0)
        self.assertEqual(value['focal_point']['box'], [0.0, 0.0, 1.0, 1.0])

    def test_frame_or_mount_does_not_become_the_focus(self):
        im = Image.new('RGB', (600, 900), (225, 210, 180))  # light mount
        d = ImageDraw.Draw(im)
        d.rectangle([60, 0, 540, 899], fill=(120, 95, 60))  # painting
        d.rectangle([0, 0, 8, 899], fill=(10, 10, 10)); d.rectangle([591, 0, 599, 899], fill=(10, 10, 10))
        for k in range(0, 160, 10):  # a dark tree cluster low in the picture
            d.line([(250 + k, 520), (330 - k, 760)], fill=(20, 18, 15), width=5)
        value, _ = self.study(im)
        x, y, w, h = value['focal_point']['box']
        self.assertTrue(.2 < x + w / 2 < .8 and y + h / 2 > .5, value['focal_point'])
        cx, cy = value['focal_point']['centre']
        self.assertTrue(x <= cx <= x + w and y <= cy <= y + h)

    def test_mass_study_separates_low_key_values_and_slide_text(self):
        # A low-key picture: fixed 85/170 cuts would show two values only.
        im = Image.new('L', (420, 300), 40)
        ImageDraw.Draw(im).rectangle([0, 0, 420, 120], fill=110)
        ImageDraw.Draw(im).ellipse([180, 60, 260, 140], fill=160)
        self.assertEqual(len(design_study.notan(im, im.size).getcolors()), 3)
        # A white slide: a paragraph of thin text should read as a grey block, not vanish into the page.
        page = Image.new('L', (420, 236), 255)
        d = ImageDraw.Draw(page)
        for y in range(60, 120, 8):
            for x in range(30, 220, 6):
                d.line([(x, y), (x + 3, y)], fill=60)
        d.rectangle([260, 160, 380, 175], fill=40)
        masses = design_study.notan(page, page.size).convert('L')
        self.assertLess(masses.getpixel((120, 90)), 200)
        self.assertEqual(masses.getpixel((380, 30)), 235)

    def test_dark_red_accent_on_dark_olive_and_ink_on_dark_slide(self):
        im = Image.new('RGB', (900, 600), (67, 70, 60))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 900, 200], fill=(120, 120, 106))
        d.rectangle([600, 420, 760, 520], fill=(111, 41, 35))  # dark red tablecloth, 58 RGB from the olive
        palette, _ = self.study(im)
        self.assertTrue(any(c['hex'] == '6F2923' and c['role'] == 'accent' for c in palette['palette']), palette)
        slide = Image.new('RGB', (1280, 720), 'black')
        d = ImageDraw.Draw(slide)
        for y in range(200, 420, 40):
            d.rectangle([100, y, 700, y + 4], fill="white")  # thin lines of white type
        value, _ = self.study(slide, 'dark.png')
        self.assertTrue(any(c.get('role') == 'ink' and c['lightness'] > .8 for c in value['palette']), value)

    def test_odd_formats_and_extreme_sizes(self):
        Image.open(self.job / 'references' / 'r.png').convert('CMYK').save(self.job / 'c.jpg')
        Image.open(self.job / 'references' / 'r.png').convert('P').save(self.job / 'p.gif')
        Image.new('LA', (40, 30), (90, 255)).save(self.job / 'tiny.png')
        for name in ('c.jpg', 'p.gif', 'tiny.png'):
            self.assertTrue(self.tool.handle({'arguments': {'file': name}})['success'], name)
        _, reply = self.study(Image.new('RGB', (300, 3000), 'white'), 'tall.png')
        sheet = Image.open(io.BytesIO(base64.b64decode(reply['contentItems'][1]['imageUrl'].split(',', 1)[1])))
        self.assertLessEqual(sheet.height, 700)  # a scroll or long poster stays a readable sheet

    def test_sequence_shows_the_deck_as_a_strip(self):
        for n in (1, 2):
            Image.new('RGB', (1333, 750), (255, 255, 255) if n == 1 else (20, 20, 20)).save(self.job / f'p{n}.png')
        reply = self.tool.handle({'arguments': {'sequence': ['p1.png', 'p2.png']}})
        self.assertTrue(reply['success'])
        self.assertEqual(json.loads(reply['contentItems'][0]['text'])['pages'], 2)

    def test_sketch_and_fresh_eyes(self):
        reply = self.tool.handle({'arguments': {'sketch': [
            {'name': 'big number left', 'blocks': [[0.6, 0.5, 7, 1.2, 'dark', 'title'], [0.6, 2.5, 5, 3, 'accent', '+23']]},
            {'name': 'statement', 'ground': 'dark', 'blocks': [[1, 3, 11, 1.5, 'light']]}]}})
        self.assertTrue(reply['success'])
        value = json.loads(reply['contentItems'][0]['text'])
        self.assertEqual(value['sketches'], 2)
        self.assertNotIn('try_first', value); self.assertNotIn('fallback_order', value)
        self.assertFalse(self.tool.handle({'arguments': {'sketch': [{'name': 'x'}]}})['success'])
        reply = self.tool.handle({'arguments': {'fresh_eyes': 'references/r.png'}})
        self.assertTrue(reply['success']); self.assertEqual(reply['contentItems'][1]['type'], 'inputImage')

    def test_crop_candidates_follow_the_focus(self):
        reply = self.tool.handle({'arguments': {'crops': 'references/r.png'}})
        self.assertTrue(reply['success'])
        candidates = json.loads(reply['contentItems'][0]['text'])['candidates']
        self.assertEqual(candidates[0]['crop'], [0, 0, 0, 0])
        tight = candidates[1]['crop']  # the busy subject is on the right, so the left side is trimmed more
        self.assertGreater(tight[0], tight[2])

    def test_three_options_must_be_anchored_and_rated(self):
        plain = [{'name': n, 'blocks': [[1, 1, 5, 1, 'dark']]} for n in 'ABC']
        reply = self.tool.handle({'arguments': {'sketch': plain}})
        self.assertFalse(reply['success']); self.assertIn('anchor', reply['contentItems'][0]['text'])
        good = [{'name': 'A', 'anchor': 'references/r.png', 'typicality': .3, 'blocks': [[8, 1, 4, 5, 'dark']]},
                {'name': 'B', 'concept': '+23 is the one figure going against the trend', 'typicality': .1, 'blocks': [[1, 2, 6, 3, 'accent']]},
                {'name': 'C', 'concept': 'title bar over cards', 'typicality': .8, 'blocks': [[1, 1, 11, 1, 'dark']]}]
        reply = self.tool.handle({'arguments': {'sketch': good}})
        self.assertTrue(reply['success'])
        value = json.loads(reply['contentItems'][0]['text'])
        self.assertEqual(value['by_typicality'], ['B', 'A', 'C'])
        for instruction in ('build try_first', 'available assets', 'fallback_order', 'your notes'):
            self.assertIn(instruction, value['meaning'])

    def sketch_options(self, scores=(.9, .4, .1, .4, .2, .7, .4, .8, .1)):
        options = [{'name': n, 'concept': 'a single focal point', 'typicality': t, 'blocks': [[1, 1, 5, 1, 'dark']]}
                   for n, t in zip('ABCDEFGHI', scores)]
        options[0]['anchor'] = 'references/r.png'
        return options

    def sketch_result(self, options, tool=None):
        reply = (tool or self.tool).handle({'arguments': {'sketch': options}})
        self.assertTrue(reply['success'], reply['contentItems'][0]['text'])
        return json.loads(reply['contentItems'][0]['text'])

    def test_sketch_draw_replays_with_the_same_names(self):
        options = self.sketch_options()
        first = self.sketch_result(options)
        self.assertEqual(self.sketch_result(options[::-1], design_study.DesignStudy({}, self.job)), first)
        rescored = [{**item, 'typicality': 1} if item['name'] == first['try_first'] else item for item in options]
        replay = self.sketch_result(rescored)
        self.assertEqual(replay['try_first'], first['try_first'])
        self.assertEqual(replay['fallback_order'], first['fallback_order'])
        self.assertEqual(replay['by_typicality'][-1], first['try_first'])

    def test_sketch_draw_varies_across_task_directories(self):
        options = self.sketch_options()
        picks = set()
        for n in range(8):
            job = self.job / f'job-{n}'
            (job / 'references').mkdir(parents=True)
            (job / 'references/r.png').write_bytes((self.job / 'references/r.png').read_bytes())
            picks.add(self.sketch_result(options, design_study.DesignStudy({}, job))['try_first'])
        self.assertGreater(len(picks), 1)

    def test_sketch_draw_and_fallback_follow_the_median_cutoff(self):
        cases = [((.9, .4, .1, .3, .2, .7, .6, .8), 'BCDE', 'GFHA'),
                 ((.9, .4, .1, .4, .2, .7, .4, .8, .1), 'BCDEGI', 'FHA')]
        for scores, candidates, tail in cases:
            with self.subTest(scores=scores):
                options = self.sketch_options(scores)
                value = self.sketch_result(options)
                first, fallback = value['try_first'], value['fallback_order']
                self.assertIn(first, candidates)
                self.assertCountEqual(fallback, [item['name'] for item in options if item['name'] != first])
                self.assertCountEqual(fallback[:len(candidates) - 1], [n for n in candidates if n != first])
                self.assertEqual(fallback[len(candidates) - 1:], list(tail))

    def test_sketch_draw_requires_unique_non_empty_names(self):
        for name in (None, ' ', 7, 'B'):
            with self.subTest(name=name):
                options = self.sketch_options()
                options[0]['name'] = name
                reply = self.tool.handle({'arguments': {'sketch': options}})
                self.assertFalse(reply['success'])
                self.assertIn('unique non-empty name', reply['contentItems'][0]['text'])

    def test_rejects_paths_outside_the_task(self):
        reply = self.tool.handle({'arguments': {'file': '../../etc/hosts'}})
        self.assertFalse(reply['success'])

    def audience_first_tool(self):
        plugin = self.job / 'plugin'
        guide = plugin / 'skills/pptx/references/art-direction.md'
        guide.parent.mkdir(parents=True)
        guide.write_text('<!-- audience-first-reference/v1 -->')
        return design_study.DesignStudy({'plugin': str(plugin)}, self.job)

    def test_audience_fit_beats_novelty_and_allows_direct_layout(self):
        tool = self.audience_first_tool()
        items = self.sketch_options((.9, .1, .2))
        items[0].pop('anchor')
        items[1]['anchor'] = 'references/r.png'
        for item, fit, evidence in zip(items, [5, 2, 3],
                                       ['common scale', 'equal columns hide differences', 'read values individually']):
            item.update(task_fit=fit, fit_evidence=evidence)
        reply = tool.handle({'arguments': {'sketch': items, 'audience_task': 'Compare the step durations'}})
        self.assertTrue(reply['success'])
        value = json.loads(reply['contentItems'][0]['text'])
        self.assertEqual(value['best_fit'], ['A'])
        self.assertEqual([x['name'] for x in value['by_task_fit']], ['A', 'C', 'B'])
        self.assertNotIn('try_first', value)

    def test_audience_first_sketches_are_viewable_before_scoring(self):
        tool = self.audience_first_tool()
        items = [{'name': n, 'blocks': [[1, 1, 5, 1, 'dark']]} for n in 'AB']
        value = self.sketch_result(items, tool)
        self.assertEqual(value['sketches'], 2)
        self.assertNotIn('best_fit', value)
        self.assertNotIn('try_first', value)

    def test_asset_check_displays_the_actual_crop_at_the_intended_width(self):
        tool = self.audience_first_tool()
        request = {'file': 'references/r.png', 'detail': 'the thin dark lines', 'crop': [.5, 0, 0, 0], 'width': 320}
        reply = tool.handle({'arguments': {'asset_check': request}})
        self.assertTrue(reply['success'])
        value = json.loads(reply['contentItems'][0]['text'])
        self.assertEqual(value['source_pixels'], [600, 675])
        self.assertEqual(value['preview_pixels'], [320, 360])
        preview = reply['contentItems'][1]['imageUrl'].split(',', 1)[1]
        with Image.open(io.BytesIO(base64.b64decode(preview))) as image:
            self.assertEqual(image.size, (320, 360))
        for invalid in ({'file': '../../etc/hosts'}, {'crop': [.5, 0, .5, 0]}):
            self.assertFalse(tool.handle({'arguments': {'asset_check': {**request, **invalid}}})['success'])


if __name__ == '__main__':
    unittest.main()
