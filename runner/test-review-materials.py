import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from review_materials import prepare_review_materials
from review_sessions import ReviewSessionError


class ReviewMaterialsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        def image(name, **fields):
            body = name.encode()
            (self.root / name).write_bytes(body)
            return {'path': name, 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body), **fields}
        self.index = {'schema': 'native-review-index/v1',
                      'reading_pages': [image(f'reading-page-{n}.png', page=n) for n in (1, 2)],
                      'state_contacts': [image('native-state-contact-1.jpg')],
                      'page_contacts': [image('contact-1.jpg')],
                      'slides': [{'page': n, 'text': f'ACTUAL PAGE {n}', 'native_reveal': {'support': 'simple_appear'}}
                                 for n in (1, 2)]}
        self.save()
        (self.root / 'source-notes.md').write_text('PRIVATE AUTHOR REASONING')
        (self.root / 'design-references.json').write_text('{"private":"AUTHOR DESIGN"}')

    def save(self):
        (self.root / 'review-index.json').write_text(json.dumps(self.index))

    def test_blind_and_visual_receive_all_reading_pages_and_state_overview(self):
        for role in ('content-first', 'visual'):
            prompt, images = prepare_review_materials(self.root, role)
            self.assertEqual(images, ['reading-page-1.png', 'reading-page-2.png', 'native-state-contact-1.jpg'])
            self.assertIn('ACTUAL PAGE 2', prompt)
            self.assertNotIn('PRIVATE AUTHOR REASONING', prompt)
            self.assertNotIn('AUTHOR DESIGN', prompt)

    def test_original_comparison_images_cross_only_source_and_visual_inputs(self):
        folder=self.root/'edit-comparison';folder.mkdir()
        body=b'EXACT ORIGINAL PREVIEW';(folder/'before.png').write_bytes(body)
        entry={'schema':'native-edit-comparison/v1','status':'prepared','pages':[{'page':1,
            'before':{'path':'edit-comparison/before.png','bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}}]}
        (folder/'index.json').write_text(json.dumps(entry))
        for role in ('content-first','content-evidence','visual'):
            prompt,images=prepare_review_materials(self.root,role,scoped=True,include_role_documents=True)
            if role=='content-first':
                self.assertNotIn('edit-comparison/before.png',images)
                self.assertNotIn('EXACT ORIGINAL PREVIEW',prompt)
            else:self.assertEqual(images[-1],'edit-comparison/before.png')
        (folder/'before.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ReviewSessionError,'checksum changed'):
            prepare_review_materials(self.root,'visual',scoped=True)

    def test_source_pass_uses_sealed_blind_reading_and_all_page_claims(self):
        prompt, images = prepare_review_materials(self.root, 'content-evidence')
        self.assertEqual(images, ['contact-1.jpg'])
        self.assertIn('ACTUAL PAGE 1', prompt)
        self.assertIn('ACTUAL PAGE 2', prompt)
        self.assertIn('first-view.json', prompt)
        self.assertIn('Open actual page/state images', prompt)
        _, images = prepare_review_materials(self.root, 'content-evidence', scoped=True)
        self.assertIn('reading-page-2.png', images)

    def test_refinement_before_images_and_feedback_are_visual_only(self):
        folder = self.root / 'refinement-comparison'; folder.mkdir()
        body = b'PRIOR ACTUAL PREVIEW'; (folder / 'before.png').write_bytes(body)
        entry = {'schema': 'native-edit-comparison/v1', 'kind': 'reviewed_refinement_baseline',
                 'status': 'prepared', 'findings': [{'observation': 'PRIOR VISUAL GAP'}],
                 'pages': [{'page': 2, 'before': {'path': 'refinement-comparison/before.png',
                    'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}}]}
        (folder / 'index.json').write_text(json.dumps(entry))
        for role in ('content-first', 'content-evidence', 'visual'):
            prompt, images = prepare_review_materials(self.root, role, include_role_documents=True)
            if role == 'visual':
                self.assertEqual(images[-1], 'refinement-comparison/before.png')
                self.assertIn('PRIOR VISUAL GAP', prompt)
                self.assertIn('REFINEMENT RECHECK', prompt)
            else:
                self.assertNotIn('refinement-comparison/before.png', images)
                self.assertNotIn('PRIOR VISUAL GAP', prompt)
        (folder / 'before.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ReviewSessionError, 'checksum changed'):
            prepare_review_materials(self.root, 'visual')
        entry['status'] = 'page_count_differs; correspondence_unverified'
        (folder / 'index.json').write_text(json.dumps(entry))
        prompt, images = prepare_review_materials(self.root, 'visual')
        self.assertNotIn('refinement-comparison/before.png', images)
        self.assertIn('No before images were attached from that comparison', prompt)

    def test_missing_coverage_changed_bytes_and_escape_are_rejected(self):
        self.index['reading_pages'].reverse()
        self.save()
        with self.assertRaisesRegex(ReviewSessionError, 'cover every page'):
            prepare_review_materials(self.root, 'visual')
        self.index['reading_pages'].reverse()
        self.save()
        (self.root / 'reading-page-1.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ReviewSessionError, 'checksum changed'):
            prepare_review_materials(self.root, 'visual')

    def test_old_immutable_packet_keeps_existing_review_path(self):
        (self.root / 'review-index.json').unlink()
        # Historical packets must neither read new evidence nor change prompts,
        # including when supplemental data is malformed or inaccessible.
        (self.root / 'request.json').write_text('{bad JSON')
        (self.root / 'audience-notes.json').symlink_to('/unavailable/private-notes')
        self.assertEqual(prepare_review_materials(self.root, 'visual'), ('', []))

    def test_role_documents_preserve_blind_isolation_and_source_role_boundaries(self):
        documents = {
            'request.json': {'title': 'VISIBLE REQUIREMENT', 'brief': 'SOURCE BRIEF',
                             'api_key': 'PRIVATE HOST VALUE',
                             'attachments': [{'path': 'references/source.md', 'name': 'ACTUAL SOURCE',
                                              'private_transport': 'PRIVATE TRANSPORT VALUE'}]},
            'first-view.json': {'summary': 'SEALED BLIND JUDGMENT', 'pages_reviewed': [1, 2]},
            'audience-notes.json': {'slides': [{'text': 'EXPORTED NOTES'}]},
            'references/index.json': [{'path': 'references/source.md', 'title': 'SOURCE REGISTER'}],
        }
        (self.root / 'references').mkdir()
        for name, value in documents.items():
            (self.root / name).write_text(json.dumps(value))
        (self.root / 'references/source.md').write_text('ACTUAL SOURCE BODY NOT AUTOMATICALLY INLINED')
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        blind, _ = prepare_review_materials(self.root, 'content-first')
        evidence, _ = prepare_review_materials(self.root, 'content-evidence',include_role_documents=True)
        visual, _ = prepare_review_materials(self.root, 'visual',include_role_documents=True)
        for marker in ('VISIBLE REQUIREMENT', 'SOURCE BRIEF', 'SEALED BLIND JUDGMENT',
                       'EXPORTED NOTES', 'SOURCE REGISTER', 'AUTHOR DESIGN', 'ACTUAL SOURCE'):
            self.assertNotIn(marker, blind)
        for marker in ('VISIBLE REQUIREMENT', 'SOURCE BRIEF', 'SEALED BLIND JUDGMENT',
                       'EXPORTED NOTES', 'SOURCE REGISTER'):
            self.assertIn(marker, evidence)
        self.assertNotIn('AUTHOR DESIGN', evidence)
        self.assertNotIn('AUTHOR DESIGN', visual)
        self.assertNotIn('EXPORTED NOTES', visual)
        self.assertIn('Inspect the actual audience canvas/sequence first', visual)
        self.assertIn('After that assessment, read the existing', visual)
        self.assertNotIn('SEALED BLIND JUDGMENT', visual)
        for prompt in (blind, evidence, visual):
            self.assertNotIn('PRIVATE AUTHOR REASONING', prompt)
            self.assertNotIn('PRIVATE HOST VALUE', prompt)
            self.assertNotIn('PRIVATE TRANSPORT VALUE', prompt)
            self.assertNotIn('ACTUAL SOURCE BODY NOT AUTOMATICALLY INLINED', prompt)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_oversize_evidence_has_exact_receipt_and_explicit_read_fallback(self):
        body = json.dumps({'slides': [{'text': 'NONTRUNCATED' * 4000}]}).encode()
        (self.root / 'audience-notes.json').write_bytes(body)
        prompt, _ = prepare_review_materials(self.root, 'content-evidence',include_role_documents=True)
        self.assertIn(hashlib.sha256(body).hexdigest(), prompt)
        self.assertIn('read this exact file before judging its contents', prompt)
        self.assertNotIn('NONTRUNCATED', prompt)

    def test_malformed_supplement_falls_back_to_original_without_inventing_content(self):
        (self.root / 'first-view.json').write_text('{unfinished')
        prompt, _ = prepare_review_materials(self.root, 'content-evidence',include_role_documents=True)
        self.assertIn('JSON could not be prepared; inspect the original file directly', prompt)
        self.assertNotIn('{unfinished', prompt)

    def test_blind_never_opens_disallowed_symlinks_but_visible_symlinks_are_rejected(self):
        (self.root / 'request.json').symlink_to('/unavailable/private-request')
        prepare_review_materials(self.root, 'content-first')
        with self.assertRaises(OSError):
            prepare_review_materials(self.root, 'visual',include_role_documents=True)

    def test_historical_index_does_not_opt_into_new_role_prompt(self):
        (self.root/'request.json').write_text('{"brief":"MUST NOT CHANGE HISTORICAL PROMPT"}')
        (self.root/'first-view.json').write_text('{"summary":"HISTORICAL SEALED PASS"}')
        for role in ('content-first','content-evidence','visual'):
            prompt,_=prepare_review_materials(self.root,role)
            self.assertNotIn('ROLE-SCOPED SUPPLEMENTAL EVIDENCE',prompt)
            self.assertNotIn('MUST NOT CHANGE HISTORICAL PROMPT',prompt)
            self.assertNotIn('HISTORICAL SEALED PASS',prompt)

    def test_unknown_prepared_role_fails_closed(self):
        with self.assertRaisesRegex(ReviewSessionError, 'Unknown prepared reviewer role'):
            prepare_review_materials(self.root, 'author')


if __name__ == '__main__':
    unittest.main()
