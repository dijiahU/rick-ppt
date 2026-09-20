"""Offline regressions for providers that wrap schema output in Markdown."""
import json
import unittest

from structured_output import parse_structured_output
from workflow import validate_report


class StructuredOutputTests(unittest.TestCase):
    def setUp(self):
        self.report = {'summary': '已检查实际页面。', 'pages_reviewed': [1, 2],
                       'limitations': ['Playback was not tested.'], 'findings': [{
                           'id': 'layout', 'severity': 'required', 'pages': [2],
                           'observation': 'A label overlaps the chart.',
                           'impact': 'The label cannot be read.',
                           'recommendation': 'Move the label above the chart.'}]}
        self.payload = json.dumps(self.report, ensure_ascii=False)
        self.fenced = '```json\n' + self.payload + '\n```'

    def test_bare_and_wrapped_reports_preserve_all_content(self):
        for text in (self.payload, ' \n' + self.payload + '\n ', self.fenced,
                     'I completed the review.\n\n' + self.fenced + '\nReview complete.',
                     '以下为审阅报告：\n' + self.fenced,
                     self.fenced.replace('\n', '\r\n').replace('```json', '  ```JSON  ')):
            with self.subTest(text=text):
                value = parse_structured_output(text)
                self.assertEqual(value, self.report)
                self.assertEqual(validate_report(value, 2), self.report)

    def test_strings_containing_json_and_fence_text_are_preserved(self):
        value = {**self.report, 'summary': 'Example: {} [] ```json and escaped "quotes".'}
        payload = json.dumps(value)
        for text in (payload, '```json\n' + payload + '\n```'):
            self.assertEqual(parse_structured_output(text), value)

    def test_multiple_fences_are_never_selected_or_merged(self):
        for extra in (self.fenced, '```text\nNotes\n```', '~~~json\n{}\n~~~'):
            for text in (extra + '\n' + self.fenced, self.fenced + '\n' + extra):
                with self.subTest(text=text), self.assertRaises(ValueError):
                    parse_structured_output(text)

    def test_extra_json_or_partial_containers_outside_fence_are_rejected(self):
        for extra in ('{}', '[]', '{"extra":', '[', 'true', 'false', 'null', '42',
                      '-1.5e2', '"another answer"', 'NaN', 'Infinity', 'Extra: {}'):
            for text in (extra + '\n' + self.fenced, self.fenced + '\n' + extra):
                with self.subTest(extra=extra, text=text), self.assertRaises(ValueError):
                    parse_structured_output(text)

    def test_malformed_payloads_and_unsupported_envelopes_are_not_repaired(self):
        for text in ('', 'No report.', 'Here is ' + self.payload,
                     self.payload + self.payload, self.payload + '\nDone.',
                     '```\n' + self.payload + '\n```', '```json\n' + self.payload,
                     '```json\n' + self.payload + ',\n```',
                     '```json\n' + self.payload + '\n{}\n```',
                     '```json\n{"summary": "unfinished}\n```',
                     '```json\n{\'summary\': \'python\'}\n```'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_structured_output(text)

    def test_non_objects_duplicate_keys_and_constants_are_rejected(self):
        for payload in ('[]', 'null', '42', '"report"', '{"a":1,"a":2}',
                        '{"a":{"b":1,"b":2}}', '{"a":NaN}', '{"a":Infinity}'):
            for text in (payload, '```json\n' + payload + '\n```'):
                with self.subTest(text=text), self.assertRaises(ValueError):
                    parse_structured_output(text)

    def test_decoding_does_not_bypass_report_validation(self):
        bad_reports = [
            {**self.report, 'pages_reviewed': [1]},
            {**self.report, 'extra': 'not in schema'},
            {**self.report, 'limitations': 'wrong type'},
            {**self.report, 'findings': [{**self.report['findings'][0], 'pages': [3]}]},
            {**self.report, 'findings': [{**self.report['findings'][0], 'severity': 'passed'}]},
            {**self.report, 'findings': [{**self.report['findings'][0], 'impact': ''}]},
        ]
        for report in bad_reports:
            text = 'Completed review.\n```json\n' + json.dumps(report) + '\n```'
            decoded = parse_structured_output(text)
            self.assertEqual(decoded, report)
            with self.subTest(report=report), self.assertRaises(ValueError):
                validate_report(decoded, 2)


if __name__ == '__main__':
    unittest.main()
