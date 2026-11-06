"""Offline contract tests, not model/aesthetic evaluation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from design_completion import (CRAFT_DIMENSIONS, CRAFT_MARKER, VISUAL_COVERAGE_MARKER,
                               coverage_enabled, coverage_inventory, response_needed, schema)
from workflow import VISUAL_REPORT_SCHEMA, validate_report


def report(kind='native_schematic'):
    return {'summary': 'Two actual pages reviewed.', 'pages_reviewed': [1, 2], 'limitations': [], 'findings': [],
        'design_assessment': {
            'audience_fit': 'Teach the supported operation to a new audience.',
            'sequence': 'A title is followed by the concrete demonstration.',
            'reference_transfer': 'No external reference is required in this fixture.',
            'readiness': 'ready', 'primary_findings': [], 'image_requirement_exemption': None,
            'visual_craft': {k: {'score': 8, 'pages': [1, 2], 'evidence': 'Visible subjects and labels have a deliberate hierarchy.',
                                  'finding_ids': []} for k in CRAFT_DIMENSIONS},
            'visual_coverage': [
                {'page': 1, 'kind': 'text_only', 'subject': 'Opening question', 'status': 'text_appropriate',
                 'evidence': 'The opening introduces the operation demonstrated on the next page.', 'finding_ids': []},
                {'page': 2, 'kind': kind, 'subject': 'Operated-on object and changing state', 'status': 'sufficient',
                 'evidence': 'The audience can inspect the actual object and its changed state.', 'finding_ids': []}]}}


def missing(value):
    a = value['design_assessment']
    value['findings'] = [{'id': 'V1', 'severity': 'required', 'pages': [2],
        'observation': 'Only data bars and prose are visible; the pictured operation is absent.',
        'impact': 'The requested illustrated example is missing.',
        'recommendation': 'Show the actual subject and its before/after state at useful scale; preserve values and labels.',
        'route': 'native_repair'}]
    a.update(readiness='needs_revision', primary_findings=['V1'])
    a['visual_coverage'][1].update(status='missing', finding_ids=['V1'])
    a['visual_craft']['visual_expression'].update(score=7, finding_ids=['V1'], pages=[2])
    return value


class VisualCoverageTests(unittest.TestCase):
    def check(self, value, counts=None, request=None):
        return validate_report(value, 2, require_design=True, completion=True, craft=True,
                               coverage=True, picture_counts=counts, request_text=request)

    def test_chart_only_or_document_only_cannot_pass_the_pictorial_minimum(self):
        for kind in ('native_chart', 'document_example'):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Charts/document'):
                self.check(report(kind), {1: 0, 2: 0})
        value=missing(report('native_chart'))
        self.check(value, {1: 0, 2: 0})
        self.assertTrue(response_needed({'visual': value}))

    def test_real_embedded_image_and_native_pictures_have_separate_evidence(self):
        self.check(report('embedded_image'), {1: 0, 2: 1})
        for kind in ('native_schematic', 'native_illustration'):
            self.check(report(kind), {1: 0, 2: 0})  # Native editability never needs rasterization.
        with self.assertRaisesRegex(ValueError, 'No image object'):
            self.check(report('embedded_image'), {1: 0, 2: 0})

    def test_each_page_must_be_accounted_for_not_replaced_by_another_pages_chart(self):
        for rows in ([], [report()['design_assessment']['visual_coverage'][1]],
                     [report()['design_assessment']['visual_coverage'][0]] * 2):
            value=report();value['design_assessment']['visual_coverage']=rows
            with self.assertRaisesRegex(ValueError, 'every page'):self.check(value)

    def test_gap_cannot_coexist_with_ready_high_score_or_unlocated_advice(self):
        for mutation in ('ready', 'high', 'wrong_page', 'retained', 'unlinked', 'optional'):
            value=missing(report('native_chart'));a=value['design_assessment']
            if mutation=='ready':a.update(readiness='ready',primary_findings=[])
            if mutation=='high':a['visual_craft']['visual_expression']['score']=8
            if mutation=='wrong_page':value['findings'][0]['pages']=[1]
            if mutation=='retained':value['findings'][0].update(route='retain_suggestion',severity='suggestion')
            if mutation=='unlinked':a['visual_coverage'][1]['finding_ids']=[]
            if mutation=='optional':value['findings'][0]['severity']='suggestion'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.check(value)

    def test_presence_is_not_sufficiency_and_uncertainty_cannot_be_ready(self):
        value=missing(report('embedded_image'));self.check(value,{1:0,2:1})
        value=report();value['design_assessment']['visual_coverage'][1]['status']='uncertain'
        with self.assertRaisesRegex(ValueError,'Uncertain'):self.check(value)
        value['design_assessment']['readiness']='uncertain';self.check(value)

    def test_cover_picture_cannot_clear_a_known_body_demonstration_gap(self):
        value=missing(report('text_only'));a=value['design_assessment']
        a['visual_coverage'][0].update(kind='embedded_image',status='sufficient',subject='Cover illustration')
        self.check(value,{1:1,2:0})
        a.update(readiness='ready',primary_findings=[])
        with self.assertRaises(ValueError):self.check(value,{1:1,2:0})

    def test_explicit_text_only_exception_needs_original_user_quote(self):
        value=report('text_only');a=value['design_assessment']
        a['visual_coverage'][1]['status']='text_appropriate'
        a['image_requirement_exemption']='请只用文字，不要放图片或示意图'
        with self.assertRaisesRegex(ValueError,'actual user'):self.check(value)
        self.check(value,request='请只用文字，不要放图片或示意图，保持原文。')
        a['image_requirement_exemption']=None
        with self.assertRaisesRegex(ValueError,'Charts/document'):self.check(value)

    def test_frozen_slide_counts_do_not_include_reference_images(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'design-reference-images').mkdir();(root/'design-reference-images/ref.png').write_bytes(b'fixture')
            (root/'review-index.json').write_text(json.dumps({'schema':'native-review-index/v1',
                'slides':[{'page':1,'object_counts':{'sp':20}},{'page':2,'object_counts':{'pic':1,'sp':6}}]}))
            self.assertEqual(coverage_inventory(root,2),{1:0,2:1})
            with self.assertRaises(ValueError):coverage_inventory(root,3)

    def test_old_and_scoped_reports_keep_existing_contract(self):
        old=copy.deepcopy(VISUAL_REPORT_SCHEMA)
        self.assertNotIn('visual_coverage',schema(old,craft=True)['properties']['design_assessment']['properties'])
        self.assertIn('visual_coverage',schema(old,craft=True,coverage=True)['properties']['design_assessment']['required'])
        self.assertEqual(old,VISUAL_REPORT_SCHEMA)
        value=report('native_chart');a=value['design_assessment']
        a.pop('visual_coverage');a.pop('image_requirement_exemption')
        validate_report(value,2,require_design=True,completion=True,craft=True)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'skills/pptx';(root/'references').mkdir(parents=True);(root/'assets').mkdir()
            (root/'assets/workflow-choices.json').write_text('{"version":4}')
            guide=root/'references/design-completion.md';guide.write_text(CRAFT_MARKER)
            self.assertFalse(coverage_enabled({'plugin':folder}))
            guide.write_text(CRAFT_MARKER+'\n'+VISUAL_COVERAGE_MARKER)
            self.assertTrue(coverage_enabled({'plugin':folder}))


if __name__=='__main__':unittest.main()
