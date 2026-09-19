#!/usr/bin/env python3
"""Meaningful integrity-boundary tests; fixture receipts do not claim execution."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import shutil
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('case_inspector', Path(__file__).with_name('inspect-case-artifacts.py'))
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)
from lxml import etree
from PIL import Image
from pptx_core.common import NS, P, A, parse
from pptx_core.interactive_ooxml import attach_content_addin, discover_content_addins


def encoded(value):
    return json.dumps(value, indent=2).encode()


def png(color):
    output = io.BytesIO()
    Image.new('RGB', (160, 120), color).save(output, format='PNG')
    return output.getvalue()


def fixture(directory):
    """Create one native slide and consistent but explicitly synthetic receipts."""
    package = directory / 'package'
    package.mkdir()
    with zipfile.ZipFile(inspector.PLUGIN / 'skills/pptx/assets/blank.pptx') as archive:
        archive.extractall(package)  # A trusted repository fixture, never user input.
    tree = parse(package / 'ppt/slides/slide1.xml')
    shapes = tree.find('p:cSld/p:spTree', NS)
    last_id = max(int(node.get('id')) for node in tree.findall('.//p:cNvPr', NS))
    for index, (text, x, y, width, height) in enumerate([
        ('Synthetic native title', 300000, 200000, 11000000, 600000),
        ('Editable explanatory context remains outside the scene.', 7000000, 1500000, 4500000, 4000000),
    ], last_id + 1):
        shape = etree.SubElement(shapes, f'{{{P}}}sp')
        nv = etree.SubElement(shape, f'{{{P}}}nvSpPr')
        etree.SubElement(nv, f'{{{P}}}cNvPr', id=str(index), name=f'Native {index}')
        etree.SubElement(nv, f'{{{P}}}cNvSpPr')
        etree.SubElement(nv, f'{{{P}}}nvPr')
        props = etree.SubElement(shape, f'{{{P}}}spPr')
        transform = etree.SubElement(props, f'{{{A}}}xfrm')
        etree.SubElement(transform, f'{{{A}}}off', x=str(x), y=str(y))
        etree.SubElement(transform, f'{{{A}}}ext', cx=str(width), cy=str(height))
        body = etree.SubElement(shape, f'{{{P}}}txBody')
        etree.SubElement(body, f'{{{A}}}bodyPr')
        etree.SubElement(body, f'{{{A}}}lstStyle')
        paragraph = etree.SubElement(body, f'{{{A}}}p')
        run = etree.SubElement(paragraph, f'{{{A}}}r')
        etree.SubElement(run, f'{{{A}}}t').text = text
    (package / 'ppt/slides/slide1.xml').write_bytes(etree.tostring(tree, xml_declaration=True, encoding='UTF-8'))
    scene = {'schemaVersion': 1, 'id': 'fixture-scene', 'viewport': {'width': 160, 'height': 120},
             'requires': ['code'], 'initialState': {'x': 0}, 'nodes': [
                 {'id': 'editor', 'type': 'component', 'component': 'CodeEditor',
                  'props': {'x': 0, 'y': 0, 'width': 100, 'height': 80, 'language': 'javascript',
                            'code': 'throw new Error("This passive fixture must never execute");'}},
                 {'id': 'play', 'type': 'Button', 'props': {'text': 'Play', 'x': 0, 'y': 80, 'width': 60, 'height': 30}}],
             'timelines': [{'id': 'move', 'duration': 1000, 'tracks': [{'path': 'x', 'keyframes': [
                 {'time': 0, 'value': 0}, {'time': 1000, 'value': 100}]}]}],
             'interactions': [{'target': 'play', 'event': 'click', 'actions': [{'type': 'playTimeline', 'timeline': 'move'}]}],
             'testPlan': [{'name': 'quarter-way', 'actions': [{'type': 'seekTimeline', 'timeline': 'move', 'time': 250}],
                           'assertions': [{'type': 'state', 'path': 'x', 'equals': 25}], 'capture': True}]}
    source = encoded(scene)
    snapshot = directory / 'snapshot.png'
    snapshot.write_bytes(png('navy'))
    cfg = inspector.config()
    attach_content_addin(package, 1,
                         {'deckId': 'fixture-deck', 'sceneId': scene['id'], 'schemaVersion': 1,
                          'specHash': inspector.hash_bytes(source)},
                         {'x': 300000, 'y': 1500000, 'width': 6000000, 'height': 4000000}, snapshot)
    pptx = directory / 'delivered.pptx'
    with zipfile.ZipFile(pptx, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob('*')):
            if path.is_file(): archive.write(path, path.relative_to(package).as_posix())
    bundle = {'bundleVersion': 1, 'deckId': 'fixture-deck', 'pptxHash': inspector.hash_file(pptx),
              'runtimeVersion': cfg['runtimeVersion'], 'addinId': cfg['addinId'], 'schemaVersion': 1,
              'slides': discover_content_addins(package), 'scenes': {scene['id']: {'path': 'scenes/fixture-scene.json',
                'sha256': inspector.hash_bytes(source)}}, 'assets': {}, 'featurePacks': ['code'],
              'generatedAt': '2026-09-20T00:00:00+00:00'}
    members = {'presentation.pptx': pptx.read_bytes(), 'deck/bundle.json': encoded(bundle),
               'deck/scenes/fixture-scene.json': source, 'runtime/config.json': encoded(cfg),
               'runtime/dist/preview.html': b'<!doctype html><title>Passive fixture, no execution</title>',
               'runtime/dist/packs/code/code-runner.worker.js': b'// Passive test fixture, not a functioning runtime.\n'}
    runtime_files = {name[len('runtime/dist/'):]: inspector.hash_bytes(value) for name, value in members.items()
                     if name.startswith('runtime/dist/')}
    fingerprint = {'sha256': inspector.hash_bytes(json.dumps(runtime_files, sort_keys=True, separators=(',', ':')).encode()),
                   'files': len(runtime_files), 'configuration': inspector.hash_bytes(members['runtime/config.json'])}
    evidence = directory / 'interactive'
    (evidence / 'tests').mkdir(parents=True)
    renders = evidence / 'renders/fixture-scene-12345'
    renders.mkdir(parents=True)
    captures = inspector.capture_names(scene)
    for index, name in enumerate(captures): (renders / name).write_bytes(png(['navy', 'blue', 'navy'][index]))
    receipt = {'receiptVersion': 1, 'sceneId': scene['id'], 'specHash': inspector.hash_bytes(source),
               'runtime': fingerprint, 'errors': [], 'testCount': 1,
               'tests': [{'name': 'quarter-way', 'assertions': 1, 'ok': True}],
               'captures': captures, 'captureHashes': {name: inspector.hash_file(renders / name) for name in captures},
               'directory': str(renders), 'ok': True, 'runtime_verified': True,
               'powerpoint_playback_verified': True}  # Deliberately untrusted claims.
    write_receipt(evidence, renders, receipt)
    archive = directory / 'delivered.zip'
    write_bundle(archive, members)
    return {'pptx': pptx, 'zip': archive, 'evidence': evidence, 'renders': renders, 'receipt': receipt,
            'members': members, 'scene': scene, 'bundle': bundle}


def write_receipt(evidence, renders, receipt):
    (evidence / 'tests/fixture-scene.json').write_bytes(encoded(receipt))
    (renders / 'report.json').write_bytes(encoded(receipt))


def write_bundle(destination, members, *, omit=(), extra=None):
    checksums = {name: inspector.hash_bytes(value) for name, value in members.items() if name not in omit}
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items(): archive.writestr('delivery/' + name, value)
        archive.writestr('delivery/checksums.json', encoded(checksums))
        for name, value in (extra or {}).items(): archive.writestr(name, value)


class CaseInspection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='inspect-case-')
        self.root = Path(self.temp.name).resolve()
        self.data = fixture(self.root)
        self.count = 0

    def tearDown(self):
        self.temp.cleanup()

    def inspect(self, *, evidence=True, pptx=None):
        self.count += 1
        return inspector.inspect(pptx or self.data['pptx'], self.data['zip'], 1, self.root / f'proof-{self.count}',
                                 self.data['evidence'] if evidence else None)

    def test_matching_bytes_native_text_and_evidence_do_not_certify_execution(self):
        before = {key: inspector.hash_file(self.data[key]) for key in ('pptx', 'zip')}
        report = self.inspect()
        self.assertEqual(report['status'], 'ready-for-manual-review')
        self.assertTrue(report['structureChecksPassed'])
        self.assertTrue(report['evidenceConsistencyPassed'])
        for key in ('browserExecutionVerified', 'powerpointPlaybackVerified', 'contentReviewPassed', 'visualReviewPassed'):
            self.assertIs(report[key], False)
        self.assertEqual(report['scenes'][0]['testPlan'][0]['numericAssertions'][0]['equals'], 25)
        self.assertEqual(report['scenes'][0]['editors'][0]['language'], 'javascript')
        self.assertIn('Editable explanatory context', report['native']['slides'][0]['editableTextShapes'][1]['text'])
        self.assertTrue(report['scenes'][0]['receipt']['authorClaimsNotTrusted']['powerpoint_playback_verified'])
        self.assertEqual(before, {key: inspector.hash_file(self.data[key]) for key in ('pptx', 'zip')})

    def test_zip_without_receipts_is_valid_structure_but_evidence_incomplete(self):
        report = self.inspect(evidence=False)
        self.assertTrue(report['structureChecksPassed'])
        self.assertFalse(report['evidenceConsistencyPassed'])
        self.assertEqual(report['status'], 'incomplete-case-evidence')

    def test_missing_or_tampered_capture_cannot_be_replaced_by_success_flags(self):
        (self.data['renders'] / '01-quarter-way.png').write_bytes(png('red'))
        report = self.inspect()
        self.assertTrue(report['structureChecksPassed'])
        self.assertFalse(report['evidenceConsistencyPassed'])
        self.assertIn('Capture hash mismatch', report['evidenceErrors'][0])

    def test_receipt_runtime_must_match_the_distributed_build(self):
        receipt = copy.deepcopy(self.data['receipt'])
        receipt['runtime']['sha256'] = '0' * 64
        write_receipt(self.data['evidence'], self.data['renders'], receipt)
        report = self.inspect()
        self.assertFalse(report['evidenceConsistencyPassed'])
        self.assertIn('distributed runtime', report['evidenceErrors'][0])

    def test_receipt_path_cannot_read_outside_explicit_evidence_root(self):
        outside = self.root / 'outside'
        shutil.copytree(self.data['renders'], outside)
        receipt = copy.deepcopy(self.data['receipt'])
        receipt['directory'] = str(outside)
        (self.data['evidence'] / 'tests/fixture-scene.json').write_bytes(encoded(receipt))
        (outside / 'report.json').write_bytes(encoded(receipt))
        # The in-scope report differs, so the outside report must not be followed.
        report = self.inspect()
        self.assertFalse(report['evidenceConsistencyPassed'])
        self.assertIn('beneath the explicitly supplied renders', report['evidenceErrors'][0])

    def test_relocated_evidence_uses_report_match_not_stale_absolute_path(self):
        receipt = copy.deepcopy(self.data['receipt'])
        receipt['directory'] = '/a/previous/computer/interactive/renders/fixture-scene-12345'
        write_receipt(self.data['evidence'], self.data['renders'], receipt)
        self.assertTrue(self.inspect()['evidenceConsistencyPassed'])

    def test_symlink_evidence_does_not_invalidate_the_intact_bundle(self):
        self.data['renders'].rename(self.root / 'outside-render')
        self.data['renders'].symlink_to(self.root / 'outside-render', target_is_directory=True)
        report = self.inspect()
        self.assertTrue(report['structureChecksPassed'])
        self.assertFalse(report['evidenceConsistencyPassed'])
        self.assertIn('symlink', report['evidenceErrors'][0])

    def test_pptx_zip_comment_difference_fails_exact_bytes_even_with_same_slides(self):
        alternate = self.root / 'same-content-different-bytes.pptx'
        alternate.write_bytes(self.data['pptx'].read_bytes())
        with zipfile.ZipFile(alternate, 'a') as archive: archive.comment = b'different delivered generation'
        report = self.inspect(pptx=alternate)
        self.assertFalse(report['structureChecksPassed'])
        self.assertIn('bytes differ', report['errors'][0])

    def test_checksum_inventory_must_cover_extra_or_missing_files(self):
        write_bundle(self.data['zip'], self.data['members'], omit=('runtime/dist/preview.html',))
        report = self.inspect()
        self.assertFalse(report['structureChecksPassed'])
        self.assertIn('exact ZIP file inventory', report['errors'][0])

    def test_byte_tampering_is_caught_before_scene_metadata_can_claim_success(self):
        with zipfile.ZipFile(self.data['zip']) as archive:
            members = {item.filename: archive.read(item) for item in archive.infolist()}
        members['delivery/runtime/dist/preview.html'] = b'changed runtime'
        with zipfile.ZipFile(self.data['zip'], 'w') as archive:
            for name, value in members.items(): archive.writestr(name, value)
        report = self.inspect()
        self.assertFalse(report['structureChecksPassed'])
        self.assertIn('Checksum mismatch', report['errors'][0])

    def test_success_receipt_cannot_substitute_an_empty_or_unknown_assertion_plan(self):
        for plan in ([], [{'name': 'fake', 'actions': [], 'assertions': []}],
                     [{'name': 'fake', 'actions': [], 'assertions': [{'type': 'authorSaysOK'}]}]):
            with self.subTest(plan=plan):
                with self.assertRaises(inspector.InspectionError):
                    inspector.inspect_plan({'testPlan': plan})

    def test_boolean_receipt_assertion_count_is_not_integer_evidence(self):
        receipt = copy.deepcopy(self.data['receipt'])
        receipt['tests'][0]['assertions'] = True
        write_receipt(self.data['evidence'], self.data['renders'], receipt)
        self.assertFalse(self.inspect()['evidenceConsistencyPassed'])

    def test_existing_proof_is_preserved(self):
        proof = self.root / 'already-reviewed'
        proof.mkdir()
        sentinel = proof / 'keep.txt'
        sentinel.write_text('keep')
        with self.assertRaisesRegex(inspector.InspectionError, 'already exists'):
            inspector.inspect(self.data['pptx'], self.data['zip'], 1, proof)
        self.assertEqual(sentinel.read_text(), 'keep')
        self.assertEqual(list(proof.iterdir()), [sentinel])


class NamespaceBoundaries(unittest.TestCase):
    def test_zip_rejects_traversal_aliases_symlinks_and_file_directory_conflicts(self):
        variants = [('../escape',), ('/absolute',), ('a/../../escape',), ('a\\escape',),
                    ('C:/escape',), ('%2e%2e/escape',), ('a/./b',), ('a//b',),
                    ('a/CON.txt',), ('a/trailing.',), ('A/x', 'a/X'), ('a', 'a/b'),
                    ('caf\u00e9', 'cafe\u0301')]
        with tempfile.TemporaryDirectory(prefix='inspect-zip-') as temporary:
            root = Path(temporary).resolve()
            for index, names in enumerate(variants):
                with self.subTest(names=names):
                    path = root / f'{index}.zip'
                    with zipfile.ZipFile(path, 'x') as archive:
                        for name in names: archive.writestr(name, b'x')
                    with self.assertRaises(inspector.InspectionError): inspector.SafeArchive(path)
            path = root / 'symlink.zip'
            link = zipfile.ZipInfo('link')
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(path, 'x') as archive: archive.writestr(link, b'/outside')
            with self.assertRaisesRegex(inspector.InspectionError, 'symlink'): inspector.SafeArchive(path)

    def test_duplicate_json_and_nonfinite_numbers_are_not_accepted(self):
        for content in (b'{"ok":false,"ok":true}', b'{"n":NaN}', b'{"n":Infinity}'):
            with self.subTest(content=content):
                with self.assertRaises(inspector.InspectionError): inspector.json_data(content)


if __name__ == '__main__':
    unittest.main()
