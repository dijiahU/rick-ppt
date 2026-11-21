"""Icon conversion, library tools and native icon placement without network or models."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PLUGIN = HERE.parent / 'pptx-agent'
sys.path.insert(0, str(PLUGIN / 'skills/pptx/scripts'))
import icon_geometry as geometry
import asset_libraries as libraries
import native_canvas as canvas
import native_batch

USER = '<path fill="currentColor" d="M12 4a4 4 0 1 1 0 8a4 4 0 0 1 0-8m0 10c4.42 0 8 1.79 8 4v2H4v-2c0-2.21 3.58-4 8-4"/>'
LINE = ('<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="2">'
        '<path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0-8 0"/><path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/></g>')
DUO = '<path fill="currentColor" d="M0 0h10v10H0z" opacity=".3"/><path fill="currentColor" d="M2 2h4v4H2z"/>'


class GeometryTests(unittest.TestCase):

    def test_image_sheet_leaves_the_process_wide_pixel_limit_alone(self):
        from PIL import Image
        before = Image.MAX_IMAGE_PIXELS
        try:
            libraries.AssetLibraries.image_sheet(object.__new__(libraries.AssetLibraries), [{"title": "x"}])
        except Exception:
            pass
        self.assertEqual(Image.MAX_IMAGE_PIXELS, before)

    def test_relative_shorthand_and_arc_commands_become_absolute_native_segments(self):
        commands = geometry.parse_path('M1 1h4v4H1zm10 0q2 0 2 2t2 2s1 1 2 2a2 2 0 01 2 2')
        kinds = [c[0] for c in commands]
        self.assertEqual(kinds[:5], ['M', 'L', 'L', 'L', 'Z'])
        self.assertEqual(commands[1][1:], (5.0, 1.0))
        self.assertEqual(commands[5], ('M', 11.0, 1.0))
        self.assertTrue(all(k in 'MLCZ' for k in kinds))
        end = commands[-1]
        self.assertAlmostEqual(end[-2], 19.0); self.assertAlmostEqual(end[-1], 9.0)

    def test_filled_and_stroked_icons_convert_with_paint_and_stroke_width(self):
        filled = geometry.convert(USER, 24, 24)
        self.assertEqual([(l['fill'], l['stroke']) for l in filled['layers']], [(True, False)])
        line = geometry.convert(LINE, 24, 24)
        self.assertEqual(len(line['layers']), 1)  # same paint merges
        self.assertEqual((line['layers'][0]['fill'], line['layers'][0]['stroke'], line['layers'][0]['stroke_width']), (False, True, 2.0))
        shapes = geometry.convert('<circle cx="5" cy="5" r="4"/><rect x="1" y="1" width="8" height="4" rx="1"/>', 10, 10)
        self.assertEqual(shapes['layers'][0]['commands'][0][0], 'M')
        image = geometry.render(filled, 64)
        self.assertLess(min(image.convert('L').getdata()), 50)

    def test_unsupported_svg_features_are_rejected_not_approximated(self):
        for body in ('<path transform="rotate(4)" d="M0 0L1 1"/>', DUO, '<image href="https://x/y.png"/>',
                     '<path fill="url(#g)" d="M0 0L1 1L0 1z"/>', '<use href="#a"/>', '<text>Hi</text>',
                     '<path d="M0 0L1"/>', '<!DOCTYPE x [<!ENTITY e "x">]><path d="&e;"/>'):
            with self.subTest(body=body), self.assertRaises(geometry.IconError):
                geometry.convert(body, 24, 24)


class FakeFetch:
    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if 'api.iconify.design/search?' in url:
            return {'icons': ['tabler:headset', 'gpl:headset'] if 'query=headset' in url else []}
        if '/collections?' in url:
            return {'tabler': {'name': 'Tabler Icons', 'license': {'spdx': 'MIT', 'title': 'MIT', 'url': 'https://github.com/tabler/LICENSE'},
                               'author': {'name': 'Tabler'}},
                    'gpl': {'name': 'Copyleft', 'license': {'spdx': 'GPL-3.0'}, 'author': {'name': 'X'}}}
        if 'api.iconify.design/tabler.json' in url:
            return {'width': 24, 'height': 24, 'icons': {'headset': {'body': LINE}, 'user': {'body': USER}, 'bad': {'body': DUO}}}
        if 'commons.wikimedia.org' in url:
            return {'query': {'pages': {'1': {'index': 1, 'title': 'File:Map.jpg', 'imageinfo': [{
                'mime': 'image/jpeg', 'width': 3000, 'height': 2000,
                'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Map.jpg?utm_source=x',
                'thumburl': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Map.jpg/1920px-Map.jpg?utm_source=x',
                'extmetadata': {'LicenseShortName': {'value': 'CC BY-SA 4.0'}, 'Artist': {'value': '<a href="x">Jane</a>'},
                                'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by-sa/4.0'}}}]},
                '2': {'index': 2, 'title': 'File:NoLicense.jpg', 'imageinfo': [{'mime': 'image/jpeg', 'url': 'https://upload.wikimedia.org/wikipedia/commons/b/bc/N.jpg', 'extmetadata': {}}]},
                '3': {'index': 3, 'title': 'File:Elsewhere.jpg', 'imageinfo': [{'mime': 'image/jpeg', 'url': 'https://evil.example/x.jpg', 'extmetadata': {'LicenseShortName': {'value': 'CC0'}}}]}}}}
        if 'api.openverse.org/v1/images/?' in url:
            assert 'license=by%2Cby-sa' in url and 'nd' not in url.split('license=')[1].split('&')[0].replace('%2C', ',').split(',')
            return {'results': [{'title': 'Mogao', 'creator': 'Ann', 'license': 'by', 'license_version': '2.0',
                                 'license_url': 'https://creativecommons.org/licenses/by/2.0/', 'url': 'https://live.staticflickr.com/1/a_b.jpg',
                                 'thumbnail': 'https://api.openverse.org/v1/images/x/thumb/', 'foreign_landing_url': 'https://www.flickr.com/photos/1/1',
                                 'width': 800, 'height': 600, 'source': 'flickr'},
                                {'title': 'No licence', 'url': 'https://live.staticflickr.com/2/b.jpg'}]}
        if 'v1.1/search' in url:
            return {'objectIDs': [1, 2]}
        if '/objects/1' in url:
            return {'isPublicDomain': True, 'primaryImageSmall': 'https://images.metmuseum.org/CRDImages/a/web-large/1.jpg',
                    'title': 'Pipa', 'objectURL': 'https://www.metmuseum.org/art/collection/search/1'}
        if '/objects/2' in url:
            return {'isPublicDomain': False, 'primaryImageSmall': 'https://images.metmuseum.org/CRDImages/a/web-large/2.jpg', 'title': 'Restricted'}
        raise OSError('unexpected ' + url)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.job = Path(self.temp.name).resolve(); self.fetch = FakeFetch()
        self.tool = libraries.AssetLibraries({}, self.job, fetch=self.fetch)
        self.tool.image_sheet = lambda candidates: None

    def call(self, name, **args):
        response = self.tool.handle({'tool': name, 'arguments': args})
        return response, json.loads(response['contentItems'][0]['text'])

    def test_phrase_search_falls_back_to_words_and_drops_non_permissive_sets(self):
        response, value = self.call('pptx_icons', action='search', query='headset support', limit=4)
        self.assertEqual(value['status'], 'results')
        self.assertEqual([c['id'] for c in value['candidates']], ['tabler:headset'])
        self.assertEqual(value['candidates'][0]['style'], 'line')
        self.assertTrue(response['contentItems'][1]['imageUrl'].startswith('data:image/png;base64,'))
        self.assertTrue(any('query=headset&' in u for u in self.fetch.urls))

    def test_fetch_writes_native_icon_files_and_reports_unconvertible_icons(self):
        _, value = self.call('pptx_icons', action='fetch', icons=['tabler:user', 'tabler:bad', 'tabler:missing'])
        self.assertEqual([f['id'] for f in value['files']], ['tabler:user'])
        self.assertEqual({f['id'] for f in value['failures']}, {'tabler:bad', 'tabler:missing'})
        document = json.loads((self.job / 'assets/icons/tabler--user.json').read_text())
        self.assertEqual((document['schema'], document['license']), ('native-icon/v1', 'MIT'))
        self.assertTrue((self.job / 'assets/icons/tabler--user.png').is_file())
        _, invalid = self.call('pptx_icons', action='fetch', icons=['../etc:passwd'])
        self.assertEqual(invalid['status'], 'invalid')

    def test_symlinked_asset_folder_is_refused(self):
        outside = self.job.parent / (self.job.name + '-outside'); outside.mkdir()
        self.addCleanup(lambda: outside.rmdir() if outside.exists() and not any(outside.iterdir()) else None)
        (self.job / 'assets').symlink_to(outside)
        _, value = self.call('pptx_icons', action='fetch', icons=['tabler:user'])
        self.assertEqual(value['status'], 'unavailable')
        self.assertEqual(list(outside.iterdir()), [])

    def test_open_image_candidates_keep_licence_source_and_permitted_media_only(self):
        _, value = self.call('pptx_open_images', query='silk road map', source='wikimedia', limit=3)
        self.assertEqual(len(value['candidates']), 1)
        item = value['candidates'][0]
        self.assertEqual((item['license'], item['creator']), ('CC BY-SA 4.0', 'Jane'))
        self.assertEqual(item['media_url'], 'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Map.jpg/1920px-Map.jpg')
        self.assertEqual(item['source_page'], 'https://commons.wikimedia.org/wiki/File:Map.jpg')
        self.assertNotIn('thumb', item)
        self.assertIs(item['low_resolution'], False)  # 3000x2000 fixture
        _, met = self.call('pptx_open_images', query='pipa', source='met', limit=3)
        self.assertEqual([c['title'] for c in met['candidates']], ['Pipa'])

    def test_openverse_candidates_carry_licence_size_and_exclude_no_derivatives(self):
        _, value = self.call('pptx_open_images', query='mogao', source='openverse', limit=4)
        self.assertEqual([c['title'] for c in value['candidates']], ['Mogao'])
        item = value['candidates'][0]
        self.assertEqual((item['license'], item['size'], item['low_resolution']), ('CC BY 2.0', [800, 600], True))
        self.assertEqual(item['source_page'], 'https://www.flickr.com/photos/1/1')

    def test_requests_only_reach_fixed_https_hosts(self):
        for url in ('http://api.iconify.design/x', 'https://evil.example/x', 'https://user@api.iconify.design/x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                libraries.http_get(url)
        self.assertEqual(libraries.AssetLibraries({'asset_libraries': False}, self.job).specs(), [])
        self.assertEqual(libraries.AssetLibraries({'_customer_funded': True}, self.job).specs(), [])


class PromptTests(unittest.TestCase):
    def test_stage_prompts_carry_icon_and_generation_rules_only_when_libraries_are_enabled(self):
        import design_roles
        cfg = {'plugin': str(PLUGIN)}
        author = design_roles.visual_presence_instruction(cfg, 'author')
        self.assertIn('pptx_icons', author); self.assertIn('Do not assemble pictograms', author)
        self.assertIn('built-in generation', author)
        self.assertIn('generated illustrations', design_roles.visual_presence_instruction(cfg, 'research'))
        self.assertIn('assembled from primitive shapes', design_roles.visual_presence_instruction(cfg, 'render'))
        self.assertNotIn('pptx_icons', design_roles.visual_presence_instruction({**cfg, 'asset_libraries': False}, 'author'))


class NativeIconTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.parts = self.root / 'parts'; self.parts.mkdir()
        with zipfile.ZipFile(PLUGIN / 'skills/pptx/assets/blank.pptx') as archive:
            archive.extractall(self.parts)
        (self.root / 'assets/icons').mkdir(parents=True)
        for name, body in (('user', USER), ('two', LINE + '<path fill="currentColor" d="M2 2h4v4H2z"/>')):
            icon = geometry.convert(body, 24, 24)
            (self.root / f'assets/icons/{name}.json').write_text(json.dumps({'schema': 'native-icon/v1', 'id': 'tabler:' + name, **icon}))

    def test_icon_is_native_recoloured_path_centred_in_box(self):
        handle = canvas.add_icon(self.parts, 1, self.root / 'assets/icons/user.json', (1, 1, 2, 1), ink='336699', name='User', task_root=self.root)
        tree = canvas.parse(self.parts / 'ppt/slides/slide1.xml')
        shape = next(s for s in tree.iter('{' + canvas.P + '}sp') if s.find('.//{' + canvas.P + '}cNvPr').get('id') == str(handle['shape_id']))
        self.assertIsNotNone(shape.find('.//{' + canvas.A + '}custGeom'))
        self.assertEqual(shape.find('.//{' + canvas.A + '}solidFill/{' + canvas.A + '}srgbClr').get('val'), '336699')
        off = shape.find('.//{' + canvas.A + '}off'); ext = shape.find('.//{' + canvas.A + '}ext')
        self.assertEqual((int(ext.get('cx')), int(ext.get('cy'))), (914400, 914400))
        self.assertEqual(int(off.get('x')), round(1.5 * 914400))

    def test_multi_layer_icon_is_one_group_and_scope_is_enforced(self):
        handle = canvas.add_icon(self.parts, 1, self.root / 'assets/icons/two.json', (1, 1, 1, 1), ink='202020', name='Two', task_root=self.root)
        tree = canvas.parse(self.parts / 'ppt/slides/slide1.xml')
        self.assertTrue(any(g.find('.//{' + canvas.P + '}cNvPr').get('id') == str(handle['shape_id']) for g in tree.iter('{' + canvas.P + '}grpSp')))
        outside = Path(tempfile.mkdtemp()); self.addCleanup(lambda: (outside / 'x.json').unlink(missing_ok=True) or outside.rmdir())
        (outside / 'x.json').write_text((self.root / 'assets/icons/user.json').read_text())
        with self.assertRaisesRegex(ValueError, 'task-scoped'):
            canvas.add_icon(self.parts, 1, outside / 'x.json', (1, 1, 1, 1), ink='202020', name='X', task_root=self.root)

    def test_batch_icon_operation_binds_task_root(self):
        from pptx_core.package import unpack
        import shutil
        shutil.copyfile(PLUGIN / 'skills/pptx/assets/blank.pptx', self.root / 'source.pptx')
        workspace = unpack(self.root / 'source.pptx', self.root / 'projects').root
        document = {'version': 1, 'batch_id': 'icons', 'defaults': {'icon': {'ink': '884422'}},
                    'operations': [{'op': 'icon', 'id': 'u', 'slide': 1, 'icon': 'assets/icons/user.json', 'box': [1, 1, 1, 1], 'name': 'User'}]}
        native_batch.run_batch(workspace, self.root, document)
        slide = next(workspace.rglob('slide1.xml'))
        self.assertIn('884422', slide.read_text())
        document['operations'][0]['task_root'] = '/'
        with self.assertRaises(native_batch.BatchError):
            native_batch.run_batch(workspace, self.root, {**document, 'batch_id': 'icons2'})


if __name__ == '__main__':
    unittest.main()
