"""Offline: library browse filters, contact sheet, pick copies into the task."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import reference_library as rl


class Tests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        base = Path(t.name); lib = base / 'lib' / 'demo'; (lib / 'pages').mkdir(parents=True)
        pages = []
        for i, colour in enumerate(['white', 'black', 'white']):
            Image.new('RGB', (320, 180), colour).save(lib / 'pages' / f'{i + 1:04d}.jpg')
            pages.append({'id': f'{i + 1:04d}', 'file': f'pages/{i + 1:04d}.jpg', 'tone': 'light' if colour == 'white' else 'dark',
                          'colors': ['FFFFFF' if colour == 'white' else '000000'], 'deck': ['Huddle', 'Huddle', 'Slip'][i],
                          'page_type': ['traction', 'team', 'traction'][i], 'quality': [5, 4, 2][i],
                          'layout': ['big number + caption', 'team photo grid', 'line chart'][i],
                          'description': ['Growth from 3mo to 1day shown as huge numbers', 'Founders with photos', 'Revenue curve'][i]})
        (lib / 'index.json').write_text(json.dumps({'name': 'demo', 'source': 'test source', 'license': 'test', 'count': 3, 'pages': pages}))
        self.job = base / 'job'; self.job.mkdir()
        self.cfg = {'reference_library_root': str(base / 'lib')}
        self.tool = rl.ReferenceLibrary(self.cfg, self.job)

    def test_enabled_only_with_a_built_library(self):
        self.assertTrue(rl.enabled(self.cfg))
        self.assertFalse(rl.enabled({'reference_library_root': '/nonexistent'}))
        self.assertFalse(rl.enabled({**self.cfg, 'reference_library': False}))

    def test_browse_filters_by_tone_and_returns_a_sheet(self):
        reply = self.tool.handle({'arguments': {'action': 'browse', 'tone': 'light', 'count': 6}})
        value = json.loads(reply['contentItems'][0]['text'])
        self.assertEqual([s['id'] for s in value['slides']], ['0001', '0003'])
        self.assertTrue(reply['contentItems'][1]['imageUrl'].startswith('data:image/jpeg;base64,'))

    def test_search_ranks_by_meaning_and_filters_quality(self):
        reply = self.tool.handle({'arguments': {'action': 'search', 'query': 'big number traction'}})
        ids = [x['id'] for x in json.loads(reply['contentItems'][0]['text'])['slides']]
        self.assertEqual(ids[0], '0001')
        reply = self.tool.handle({'arguments': {'action': 'search', 'page_type': 'traction', 'min_quality': 4}})
        self.assertEqual([x['id'] for x in json.loads(reply['contentItems'][0]['text'])['slides']], ['0001'])

    def test_chinese_words_map_to_page_types_and_unknown_text_says_so(self):
        reply = self.tool.handle({'arguments': {'action': 'search', 'query': '团队介绍'}})
        self.assertEqual([x['id'] for x in json.loads(reply['contentItems'][0]['text'])['slides']], ['0002'])
        reply = self.tool.handle({'arguments': {'action': 'search', 'query': '随便看看'}})
        self.assertFalse(reply['success'])

    def test_named_page_type_outranks_incidental_words(self):
        reply = self.tool.handle({'arguments': {'action': 'search', 'query': 'team photo with revenue curve'}})
        self.assertEqual(json.loads(reply['contentItems'][0]['text'])['slides'][0]['id'], '0002')

    def test_deck_shows_all_pages_of_one_deck(self):
        reply = self.tool.handle({'arguments': {'action': 'deck', 'deck': 'huddle'}})
        self.assertEqual([x['id'] for x in json.loads(reply['contentItems'][0]['text'])['slides']], ['0001', '0002'])

    def test_pick_copies_into_task_references_with_source(self):
        reply = self.tool.handle({'arguments': {'action': 'pick', 'ids': ['0002']}})
        files = json.loads(reply['contentItems'][0]['text'])['files']
        self.assertEqual(files[0]['file'], 'references/library/demo-0002.jpg')
        self.assertEqual(files[0]['source'], 'test source')
        self.assertTrue((self.job / files[0]['file']).is_file())
        self.assertFalse(self.tool.handle({'arguments': {'action': 'pick', 'ids': ['9999']}})['success'])

    def test_inspire_keeps_distinct_decks_without_template_ids(self):
        reply = self.tool.handle({'arguments': {'action': 'inspire', 'query': 'traction', 'min_quality': 2}})
        pages = json.loads(reply['contentItems'][0]['text'])['pages']
        self.assertEqual([p['id'] for p in pages], ['0001', '0003'])
        self.assertIsNone(pages[0]['template']); self.assertIsNone(pages[0]['slide'])
        self.assertEqual(pages[0]['page_type'], 'traction')


class TemplateTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        base = Path(t.name); lib = base / 'lib' / 'templates'; (lib / 'pages').mkdir(parents=True); (lib / 'files').mkdir()
        (lib / 'files' / 'tabc12345.pptx').write_bytes(b'PK fake pptx')
        pages = []
        for i, (kind, desc) in enumerate([('cover', '克莱因蓝全幅封面，左侧大标题'), ('data', '左图右侧双栏数据卡片'), ('agenda', '杂志风目录')]):
            Image.new('RGB', (320, 180), 'white').save(lib / 'pages' / f'tabc12345-{i + 1:02d}.jpg')
            pages.append({'id': f'tabc12345-{i + 1:02d}', 'file': f'pages/tabc12345-{i + 1:02d}.jpg', 'tone': 'light', 'colors': ['FFFFFF'],
                          'deck': '克莱因蓝述职报告', 'template': 'tabc12345', 'category': '工作汇报', 'slide': i + 1,
                          'page_type': kind, 'description': desc, 'quality': 4})
        index = {'name': 'templates', 'kind': 'templates', 'source': 'WPS', 'license': 'own use', 'count': 3, 'pages': pages,
                 'templates': [{'id': 'tabc12345', 'name': '克莱因蓝述职报告', 'category': '工作汇报', 'file': 'files/tabc12345.pptx',
                                'slides': 3, 'visible_slides': 3, 'size': [13.33, 7.5]}]}
        (lib / 'index.json').write_text(json.dumps(index, ensure_ascii=False))
        self.job = base / 'job'; self.job.mkdir()
        self.tool = rl.ReferenceLibrary({'reference_library_root': str(base / 'lib')}, self.job)

    def value(self, reply):
        return json.loads(reply['contentItems'][0]['text'])

    def add_template(self, tid, kinds, *, category='工作汇报', description=''):
        index = self.tool.indexes['templates']
        index['templates'].append({'id': tid, 'name': tid, 'category': category, 'visible_slides': len(kinds)})
        for slide, (kind, quality, *desc) in enumerate(kinds, 1):
            index['pages'].append({'id': f'{tid}-{slide:02d}', 'file': 'pages/tabc12345-01.jpg', 'template': tid,
                                   'page_type': kind, 'quality': quality, 'slide': slide, 'description': desc[0] if desc else description})

    def templates(self, **args):
        return self.value(self.tool.handle({'arguments': {'action': 'templates', **args}}))

    def test_chinese_query_matches_chinese_tags_and_category(self):
        ids = [x['id'] for x in self.value(self.tool.handle({'arguments': {'action': 'search', 'query': '数据卡片'}}))['slides']]
        self.assertEqual(ids[0], 'tabc12345-02')
        ids = [x['id'] for x in self.value(self.tool.handle({'arguments': {'action': 'search', 'query': '目录', 'category': '工作汇报'}}))['slides']]
        self.assertEqual(ids[0], 'tabc12345-03')
        self.assertIn('工作汇报', self.tool.specs()[0]['description'])

    def test_deck_by_template_id_in_slide_order(self):
        ids = [x['id'] for x in self.value(self.tool.handle({'arguments': {'action': 'deck', 'deck': 'tabc12345'}}))['slides']]
        self.assertEqual(ids, ['tabc12345-01', 'tabc12345-02', 'tabc12345-03'])

    def test_templates_ranks_whole_templates_with_a_row_of_pages(self):
        reply = self.tool.handle({'arguments': {'action': 'templates', 'query': '工作汇报 数据', 'min_quality': 3}})
        value = self.value(reply)
        self.assertEqual(value['templates'][0]['template'], 'tabc12345')
        self.assertEqual(value['templates'][0]['average_quality'], 4)
        self.assertTrue(reply['contentItems'][1]['imageUrl'].startswith('data:image/jpeg'))
        self.assertFalse(self.tool.handle({'arguments': {'action': 'templates', 'min_quality': 5}})['success'])

    def test_templates_uses_best_page_per_role_and_requires_a_cover(self):
        roles = [('cover', 3), ('section', 4), ('image', 5), ('comparison', 4), ('timeline', 3), ('summary', 3)]
        self.add_template('broad', roles + [('image', 1)] * 3)
        self.add_template('sparse', [('cover', 5), ('image', 5)])
        self.add_template('weakcover', [('cover', 2)] + [(kind, 5) for kind, _ in roles[1:]])
        self.add_template('nocover', [(kind, 5) for kind, _ in roles[1:]])
        rows = self.templates()['templates']
        self.assertEqual([r['template'] for r in rows], ['broad'])
        self.assertEqual((rows[0]['coverage'], rows[0]['average_quality'], rows[0]['fit']), (3.67, 2.78, 1))
        self.assertEqual(rows[0]['roles_missing'], [])
        self.assertEqual(self.templates(min_quality=3.67)['status'], 'no_results')

    def test_templates_missing_role_counts_as_two_and_explicit_floor_uses_coverage(self):
        self.add_template('partial', [('cover', 3), ('agenda', 4), ('text', 5), ('comparison', 5), ('timeline', 1)])
        self.assertEqual(self.templates()['status'], 'no_results')
        row, = self.templates(min_quality=3.3)['templates']
        self.assertEqual((row['coverage'], row['roles_missing']), (3.33, ['closing']))
        self.assertEqual([p['page_type'] for p in row['shown_pages']], ['cover', 'text', 'comparison'])
        self.assertEqual(self.tool.specs()[0]['inputSchema']['properties']['min_quality']['type'], 'number')

    def test_templates_rank_by_weighted_fit_and_coverage(self):
        kinds = ['cover', 'agenda', 'text', 'data', 'process', 'closing']
        high = [(kind, 5) for kind in kinds]
        self.add_template('sixwords', list(zip(kinds, [3, 3, 4, 4, 3, 4])), description='alpha beta gamma delta epsilon zeta')
        self.add_template('fivewords', high, description='alpha beta gamma delta epsilon')
        self.add_template('fourwords', high, description='alpha beta gamma delta')
        rows = self.templates(query='alpha beta gamma delta epsilon zeta')['templates']
        self.assertEqual([r['template'] for r in rows], ['fivewords', 'sixwords', 'fourwords'])
        self.assertEqual([r['fit'] for r in rows], [0.83, 1, 0.67])

    def test_templates_preview_uses_two_distinct_matching_roles_between_cover_and_closing(self):
        self.add_template('preview', [('cover', 3), ('text', 4, 'alpha beta gamma'), ('image', 5, 'alpha beta'),
                                     ('section', 5), ('comparison', 3, 'alpha'), ('timeline', 5),
                                     ('summary', 4), ('closing', 3, 'alpha beta gamma'), ('cover', 5)])
        row, = self.templates(query='alpha beta gamma')['templates']
        self.assertEqual(row['shown_pages'], [{'id': f'preview-{slide:02d}', 'page_type': kind}
                                            for slide, kind in [(9, 'cover'), (2, 'text'), (5, 'comparison'), (7, 'summary')]])

    def test_templates_compares_report_categories_in_both_directions(self):
        kinds = ['cover', 'section', 'image', 'data', 'process', 'closing']
        for tid, category, quality in [('weekly', '周报月报', 4), ('work', '工作汇报', 5), ('lesson', '教学课件', 5)]:
            self.add_template(tid, [(kind, quality) for kind in kinds], category=category, description='alpha')
        for category in ('周报月报', '工作汇报'):
            with self.subTest(category=category):
                value = self.templates(category=category, query='alpha')
                self.assertEqual([r['template'] for r in value['templates']], ['work', 'weekly'])
                self.assertNotIn('note', value)
        self.assertEqual([r['template'] for r in self.templates(category='教学', query='alpha')['templates']], ['lesson'])

    def test_inspire_returns_only_high_rated_pages_one_per_template(self):
        value = self.value(self.tool.handle({'arguments': {'action': 'inspire', 'query': '目录 卡片 数据'}}))
        self.assertEqual(len(value['pages']), 1)  # three pages, one template
        self.assertTrue(all(p['quality'] >= 4 for p in value['pages']))

    def test_templates_widen_beyond_a_category_without_good_templates(self):
        value = self.templates(category='教学课件', min_quality=3)
        self.assertEqual(value['templates'][0]['template'], 'tabc12345')
        self.assertIn('No 教学课件 template', value['note'])
        self.tool.handle({'arguments': {'action': 'inspire', 'query': '目录 卡片 数据'}})
        log = [json.loads(l) for l in (self.job.parent / 'lib' / 'search-log.jsonl').read_text().splitlines()]
        self.assertEqual(log[0]['shown'], ['tabc12345']); self.assertIn('No 教学课件', log[0]['note'])
        self.assertEqual(len(log[1]['shown']), 1)  # recalled page ids are kept for later audit

    def test_template_copies_editable_file_into_task(self):
        value = self.value(self.tool.handle({'arguments': {'action': 'template', 'template': '克莱因蓝述职报告'}}))
        self.assertTrue(value['file'].startswith('references/templates/tabc12345-'))
        self.assertTrue((self.job / value['file']).is_file())
        self.assertEqual(len(value['pages']), 3)
        self.assertFalse(self.tool.handle({'arguments': {'action': 'template', 'template': 'nope'}})['success'])
        log = [json.loads(l) for l in (self.job.parent / 'lib' / 'search-log.jsonl').read_text().splitlines()]
        self.assertEqual([r['action'] for r in log], ['template', 'template'])
        self.assertTrue(log[0]['copied'].startswith('references/templates/')); self.assertFalse(log[1]['success'])


class RankingTests(unittest.TestCase):
    def test_one_template_cannot_fill_the_first_results_and_repeats_are_dropped(self):
        def page(i, deck, layout, quality=4):
            return ('t', {'id': f'{deck}-{i}', 'deck': deck, 'layout': layout, 'page_type': 'data', 'quality': quality,
                          'description': '数据 大数字'})
        items = [page(i, 'A', f'版式{i}') for i in range(5)] + [page(0, 'A', '版式0')] + [page(i, 'B', f'版式{i}') for i in range(2)]
        ranked = [it['id'] for _, it in rl.ReferenceLibrary._search(items, {'query': '数据 大数字'})]
        self.assertEqual(ranked[:4], ['A-0', 'A-1', 'B-0', 'B-1'])
        self.assertEqual(len(ranked), 7)  # the identical repeated A page is gone

    def test_rare_words_outweigh_common_ones(self):
        items = [('t', {'id': str(i), 'deck': f'D{i}', 'quality': 3, 'description': '工作汇报 数据' + (' 雪山' if i == 9 else '')})
                 for i in range(10)]
        ranked = [it['id'] for _, it in rl.ReferenceLibrary._search(items, {'query': '工作汇报 雪山'})]
        self.assertEqual(ranked[0], '9')


class InspireMatchTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        lib = Path(t.name) / 'lib' / 'templates'; (lib / 'pages').mkdir(parents=True)
        pages, templates = [], []
        rows = [('t1', '居中大字标语', 4), ('t2', '左文右路线地图', 3), ('t3', '满版照片居中大字标题', 5), ('t4', '平淡左文右图', 3)]
        for tid, desc, q in rows:
            Image.new('RGB', (320, 180), 'white').save(lib / 'pages' / f'{tid}-01.jpg')
            pages.append({'id': f'{tid}-01', 'file': f'pages/{tid}-01.jpg', 'tone': 'light', 'deck': tid, 'template': tid,
                          'category': '工作汇报', 'slide': 2, 'page_type': 'image', 'layout': desc, 'quality': q})
            templates.append({'id': tid, 'name': tid, 'category': '工作汇报'})
        (lib / 'index.json').write_text(json.dumps({'name': 'templates', 'kind': 'templates', 'pages': pages, 'templates': templates},
                                                   ensure_ascii=False))
        job = Path(t.name) / 'job'; job.mkdir()
        self.tool = rl.ReferenceLibrary({'reference_library_root': str(Path(t.name) / 'lib')}, job)

    def pages(self, query):
        return json.loads(self.tool.handle({'arguments': {'action': 'inspire', 'query': query}})['contentItems'][0]['text'])

    def test_three_rated_exact_match_competes(self):
        ids = [p['id'] for p in self.pages('路线地图 大字')['pages']]
        self.assertIn('t2-01', ids)            # rated 3 but the only map
        self.assertNotIn('t4-01', ids)         # rated 3 and matches nothing specific

    def test_each_page_reports_its_match(self):
        value = self.pages('路线地图')
        self.assertEqual(value['pages'][0]['id'], 't2-01'); self.assertGreater(value['pages'][0]['match'], 0.5)

    def test_inspire_sorts_before_deduplicating_templates_and_layouts(self):
        pages = self.tool.indexes['templates']['pages']
        pages.append({**pages[0], 'id': 't1-02', 'slide': 3, 'page_type': 'section', 'description': 'atlas'})
        items = list(self.tool._items())
        search = rl.ReferenceLibrary._search(items, {'query': 'image atlas', 'min_quality': 4})
        self.assertEqual([p['id'] for _, p in search if p['template'] == 't1'], ['t1-01'])
        for floor in (3, 4):
            with self.subTest(floor=floor):
                args = {'action': 'inspire', 'query': 'image atlas', 'min_quality': floor, 'count': 1}
                page, = json.loads(self.tool.handle({'arguments': args})['contentItems'][0]['text'])['pages']
                self.assertEqual((page['id'], page['template'], page['slide'], page['page_type']), ('t1-02', 't1', 3, 'section'))


if __name__ == '__main__': unittest.main()
