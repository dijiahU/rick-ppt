import copy
import hashlib
import json
import unittest

from outline import MAX_BOUND_EMU, page_version, validate_outline


def base():
    return {'title': 'Convolution', 'purpose': 'Explain shared filters', 'slides': [
        {'id': 'patch', 'title': 'One patch', 'summary': 'Multiply and add four cells'}]}


def interactive():
    value = base()
    value['slides'][0].update(presentationMode='hybrid', interaction={
        'scene': 'cnn-patch', 'purpose': 'Move the kernel and inspect the sum',
        'bounds': {'x': 457200, 'y': 1371600, 'width': 10058400, 'height': 4114800}})
    return value


class Tests(unittest.TestCase):
    def test_legacy_hash_and_shape_are_unchanged(self):
        value = base()
        expected = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
        self.assertEqual(validate_outline(value), {**value, 'revision': expected})

    def test_public_fields_survive_and_change_page_revision(self):
        value = interactive()
        value['slides'][0]['interaction']['internal'] = '/private/not-public'
        value['slides'][0]['interaction']['bounds']['internal'] = 'discard'
        normalized = validate_outline(value, 1)
        self.assertEqual(normalized['slides'][0], interactive()['slides'][0])
        self.assertEqual(validate_outline(normalized), normalized)
        before = page_version(normalized, 1)
        for field, changed in [('presentationMode', 'interactive'), ('interaction', {
                **normalized['slides'][0]['interaction'], 'scene': 'cnn-patch-next'})]:
            other = copy.deepcopy(normalized)
            other['slides'][0][field] = changed
            self.assertNotEqual(page_version(validate_outline(other), 1), before)
        other = copy.deepcopy(normalized)
        other['slides'][0]['interaction']['bounds']['width'] += 1
        self.assertNotEqual(page_version(validate_outline(other), 1), before)

    def test_optional_mode_and_bounds_remain_optional(self):
        for mode in ('native', 'interactive', 'hybrid'):
            value = base(); value['slides'][0]['presentationMode'] = mode
            self.assertEqual(validate_outline(value)['slides'][0]['presentationMode'], mode)
        value = interactive(); del value['slides'][0]['presentationMode']
        del value['slides'][0]['interaction']['bounds']
        self.assertNotIn('bounds', validate_outline(value)['slides'][0]['interaction'])

    def test_rejects_paths_secrets_and_malformed_metadata(self):
        for mode in ('script', None, [], 1):
            value = base(); value['slides'][0]['presentationMode'] = mode
            with self.subTest(mode=mode), self.assertRaises(ValueError): validate_outline(value)
        invalid = [None, [], {}, {'scene': '../scene.json', 'purpose': 'Slide'},
                   {'scene': 'https://example.org/scene', 'purpose': 'Slide'},
                   {'scene': 'good', 'purpose': '/Users/rick/local.txt'},
                   {'scene': 'good', 'purpose': 'api_key=private-value'}]
        for interaction in invalid:
            value = base(); value['slides'][0]['interaction'] = interaction
            with self.subTest(interaction=interaction), self.assertRaises(ValueError): validate_outline(value)

    def test_bounds_reject_incomplete_noninteger_and_overflow(self):
        invalid = [{}, [], {'x': 0, 'y': 0, 'width': 1},
                   {'x': 0, 'y': 0, 'width': 0, 'height': 1},
                   {'x': -1, 'y': 0, 'width': 1, 'height': 1},
                   {'x': 0, 'y': 0, 'width': True, 'height': 1},
                   {'x': 0, 'y': 0, 'width': float('inf'), 'height': 1},
                   {'x': 0, 'y': 0, 'width': 1.5, 'height': 1},
                   {'x': MAX_BOUND_EMU, 'y': 0, 'width': 1, 'height': 1}]
        for bounds in invalid:
            value = interactive(); value['slides'][0]['interaction']['bounds'] = bounds
            with self.subTest(bounds=bounds), self.assertRaises(ValueError): validate_outline(value)


if __name__ == '__main__': unittest.main()
