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

    def test_source_pass_uses_sealed_blind_reading_and_all_page_claims(self):
        prompt, images = prepare_review_materials(self.root, 'content-evidence')
        self.assertEqual(images, ['contact-1.jpg'])
        self.assertIn('ACTUAL PAGE 1', prompt)
        self.assertIn('ACTUAL PAGE 2', prompt)
        self.assertIn('first-view.json', prompt)
        self.assertIn('Open actual page/state images', prompt)
        _, images = prepare_review_materials(self.root, 'content-evidence', scoped=True)
        self.assertIn('reading-page-2.png', images)

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
        self.assertEqual(prepare_review_materials(self.root, 'visual'), ('', []))


if __name__ == '__main__':
    unittest.main()
