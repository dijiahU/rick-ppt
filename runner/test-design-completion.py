"""Offline decision/transport tests; no model quality or human acceptance claim."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from design_completion import CONTRACT, PRESENTATION, PRESENTATION_MARKER, schema, selection, notice, presentation_schema, presentation_enabled, response_findings
from design_feedback import mark_response, optional_response
from workflow import validate_report, VISUAL_REPORT_SCHEMA, REPORT_SCHEMA


spec = importlib.util.spec_from_file_location('feedback_fixture', Path(__file__).with_name('test-design-author.py'))
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def current(body=b'candidate', number=1, state='needs_revision'):
    value = fixture.receipt(body, number)
    value.update(design_completion=dict(CONTRACT), output_language='en')
    value['visual']['design_assessment'] = {
        'audience_fit': 'The main relationship still requires prose reconstruction.',
        'sequence': 'Page two follows the same mechanism question.',
        'reference_transfer': 'No external artwork is used in this fixture.',
        'readiness': state, 'primary_findings': ['F1'] if state == 'needs_revision' else []}
    return value


def compared(baseline, candidate, verdict='better', resolution='partial'):
    candidate['visual']['design_comparison'] = {
        'baseline_sha256': baseline['artifact_sha256'],
        'candidate_sha256': candidate['artifact_sha256'],
        'verdict': verdict, 'reason': 'The subject is larger and directly tied to the corresponding explanation.',
        'regression_findings': [], 'resolutions': [
            {'id': 'F1', 'status': resolution, 'evidence': 'The main mapping is visible; some small annotations still compete.'}]}
    return candidate


def content_priority(value, nominated=True):
    value['content_presentation'] = dict(PRESENTATION)
    value['content']['findings'] = [dict(value['visual']['findings'][0], pages=[1],
        observation='An essential comparison qualification is buried in the credit line.',
        impact='The visible values can be interpreted without their necessary condition.',
        recommendation='Move the existing condition beside the comparison at reading scale; preserve values and native groups.')]
    value['content']['presentation_findings'] = ['F1'] if nominated else []
    return value


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.base = current(b'baseline')
        self.next = compared(self.base, current(b'candidate', 2))
        self.binding = {'baseline_sha256': self.base['artifact_sha256'],
            'candidate_sha256': self.next['artifact_sha256'], 'visual_input_complete': True,
            'finding_ids': ['F1']}

    def check(self, value=None, binding=None):
        return validate_report(value or self.next['visual'], 2, require_design=True,
                               completion=True, comparison=binding or self.binding)

    def test_schema_is_scoped_and_does_not_change_legacy_contract(self):
        old = copy.deepcopy(VISUAL_REPORT_SCHEMA)
        value = schema(VISUAL_REPORT_SCHEMA, self.binding)
        self.assertIn('readiness', value['properties']['design_assessment']['required'])
        self.assertIn('design_comparison', value['required'])
        self.assertEqual(VISUAL_REPORT_SCHEMA, old)
        validate_report(fixture.receipt(b'old')['visual'], 2)
        self.check()

    def test_readiness_requires_actual_actionable_findings(self):
        for state, ids in [('needs_revision', []), ('needs_revision', ['invented']),
                           ('ready', ['F1']), ('uncertain', ['F1'])]:
            with self.subTest(state=state, ids=ids):
                value = copy.deepcopy(self.next['visual'])
                value['design_assessment'].update(readiness=state, primary_findings=ids)
                with self.assertRaises(ValueError): self.check(value)

    def test_identity_and_original_problem_coverage_are_enforced(self):
        mutations = [('baseline_sha256', 'f'*64), ('candidate_sha256', 'e'*64),
                     ('regression_findings', ['made-up']), ('resolutions', [])]
        for key, replacement in mutations:
            with self.subTest(key=key):
                value = copy.deepcopy(self.next['visual'])
                value['design_comparison'][key] = replacement
                with self.assertRaises(ValueError): self.check(value)

    def test_missing_visual_input_cannot_claim_comparison_success(self):
        binding = {**self.binding, 'visual_input_complete': False}
        with self.assertRaisesRegex(ValueError, 'uncertain'): self.check(binding=binding)
        self.next['visual']['design_comparison']['verdict'] = 'uncertain'
        self.check(binding=binding)

    def test_missing_host_baseline_cannot_accept_model_invented_comparison(self):
        with self.assertRaises(ValueError):
            validate_report(self.next['visual'], 2, require_design=True, completion=True)

    def test_only_better_without_regression_replaces_baseline(self):
        for verdict in ('better', 'equivalent', 'worse', 'uncertain'):
            self.next['visual']['design_comparison']['verdict'] = verdict
            choice = selection(self.base, self.next)
            self.assertEqual(choice['selected'], 'candidate' if verdict == 'better' else 'baseline')
        self.next['visual']['design_comparison']['verdict'] = 'better'
        self.next['visual']['design_comparison']['regression_findings'] = ['F1']
        self.assertEqual(selection(self.base, self.next)['reason'], 'design_regression')

    def test_partial_progress_keeps_truthful_unfinished_state(self):
        self.assertEqual(selection(self.base, self.next)['selected'], 'candidate')
        self.assertIn('still needed', notice(self.next))
        self.next['output_language'] = 'zh-CN'
        self.assertIn('仍需实质设计修改', notice(self.next))
        self.assertEqual(notice(fixture.receipt(b'legacy')), '')

    def test_hard_regression_and_legacy_selection_keep_existing_boundaries(self):
        self.next['content']['findings'] = [dict(self.next['visual']['findings'][0], severity='required')]
        self.assertEqual(selection(self.base, self.next)['reason'], 'required_regression')
        self.assertIsNone(selection(fixture.receipt(b'legacy'), self.next))
        self.next['visual']['design_comparison']['candidate_sha256'] = 'd'*64
        with self.assertRaises(ValueError): selection(self.base, self.next)

    def test_source_checked_priority_uses_existing_findings_and_separate_ids(self):
        value=content_priority(current(state='ready'))
        original=copy.deepcopy(value)
        self.assertIn('presentation_findings',presentation_schema(REPORT_SCHEMA)['required'])
        validate_report(value['content'],2,presentation=True)
        rows=response_findings(value)
        self.assertEqual([f['id'] for f in rows],['content:F1','visual:F1'])
        self.assertEqual(rows[0]['source_id'],'F1')
        self.assertEqual(rows[0]['pages'],[1])
        self.assertEqual(value,original)
        for ids in (None,['unknown'],['F1','F1']):
            value['content']['presentation_findings']=ids
            with self.assertRaises(ValueError):validate_report(value['content'],2,presentation=True)
        value['content']['presentation_findings']=['F1']
        value['content']['findings'][0]['route']='content_revision'
        with self.assertRaises(ValueError):validate_report(value['content'],2,presentation=True)

    def test_source_priority_does_not_become_finished_due_to_visual_ready(self):
        value=content_priority(current(state='ready'))
        self.assertIn('still needed',notice(value))
        value['content']['presentation_findings']=[]
        self.assertIn('ready for the stated use',notice(value))

    def test_pinned_older_guide_keeps_content_report_contract(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);skill=root/'skills/pptx'
            (skill/'assets').mkdir(parents=True);(skill/'references').mkdir()
            (skill/'assets/workflow-choices.json').write_text('{"version":4}')
            guide=skill/'references/design-completion.md'
            guide.write_text('Historical visual-only completion policy')
            self.assertFalse(presentation_enabled({'plugin':str(root)}))
            guide.write_text(guide.read_text()+'\n'+PRESENTATION_MARKER)
            self.assertTrue(presentation_enabled({'plugin':str(root)}))

    def test_missing_source_reassessment_and_new_presentation_regression_keep_baseline(self):
        content_priority(self.base,False)
        self.assertEqual(selection(self.base,self.next)['reason'],'presentation_assessment_unavailable')
        content_priority(self.next)
        self.assertEqual(selection(self.base,self.next)['reason'],'presentation_regression')
        content_priority(self.base)
        self.assertEqual(selection(self.base,self.next)['selected'],'candidate')


class WorkflowTests(unittest.TestCase):
    setUp = fixture.FeedbackTests.setUp
    execute = fixture.FeedbackTests.execute
    fake_restore = fixture.FeedbackTests.fake_restore

    def configure(self, verdict='better', state='needs_revision', regression=False):
        baseline = current((self.job/'original.pptx').read_bytes())
        def review(body, rendered, packet, payload, number):
            value = current(body, number, state if number > 1 else 'needs_revision')
            if number > 1:
                compared(baseline, value, verdict)
                if regression: value['visual']['design_comparison']['regression_findings'] = ['F1']
            return mark_response(self.cfg, value, scoped=False)
        self.run.review.side_effect = review

    def test_ready_or_uncertain_with_suggestions_does_not_start_cosmetic_work(self):
        for state in ('ready', 'uncertain'):
            value = mark_response(self.cfg, current(state=state), scoped=False)
            self.assertFalse(optional_response(value))
        self.run.review.side_effect = lambda body,*a:mark_response(self.cfg,current(body,state='ready'),scoped=False)
        self.execute()
        self.assertEqual(self.calls, [])

    def test_main_gap_triggers_only_one_response_and_keeps_improved_unfinished_candidate(self):
        self.configure(); self.action = 'change'
        result, receipt = self.execute()
        self.assertEqual(result['artifact'], (self.job/'changed.pptx').read_bytes())
        self.assertEqual([n for n,_ in self.calls], ['repair-1'])
        self.assertEqual(self.calls[0][1]['timeout'], 360)
        self.assertEqual(self.run.review.call_count, 2)
        self.assertIn('still needed', notice(receipt))
        decision = json.loads(next(self.records.glob('*-design-selection-*')).read_text())
        self.assertEqual(decision['selected'], 'candidate')
        self.assertEqual(decision['candidate_sha256'], hashlib.sha256(result['artifact']).hexdigest())

    def test_visually_worse_repair_delivers_exact_baseline_not_latest_export(self):
        self.configure('worse'); self.action = 'change'
        with patch('design_feedback.restore_baseline', side_effect=self.fake_restore):
            result, receipt = self.execute()
        self.assertEqual(result['artifact'], (self.job/'original.pptx').read_bytes())
        self.assertEqual(receipt['round'], 1)
        self.assertIn('still needed', notice(receipt))
        self.assertEqual(json.loads(next(self.records.glob('*-design-selection-*')).read_text())['reason'], 'comparison_worse')

    def test_equivalent_and_uncertain_keep_baseline(self):
        for verdict in ('equivalent', 'uncertain'):
            with self.subTest(verdict=verdict):
                self.configure(verdict); self.action = 'change'
                with patch('design_feedback.restore_baseline', side_effect=self.fake_restore):
                    result, _ = self.execute()
                self.assertEqual(result['artifact'], (self.job/'original.pptx').read_bytes())

    def test_claimed_improvement_with_regression_is_rejected(self):
        self.configure(regression=True); self.action = 'change'
        with patch('design_feedback.restore_baseline', side_effect=self.fake_restore):
            result, _ = self.execute()
        self.assertEqual(result['artifact'], (self.job/'original.pptx').read_bytes())

    def test_ready_improvement_and_noop_are_distinct(self):
        self.configure(state='ready'); self.action = 'change'
        _, receipt = self.execute()
        self.assertIn('ready for the stated use', notice(receipt))

    def test_noop_keeps_unfinished_status_and_does_not_claim_repair_success(self):
        self.configure(); self.action = 'noop'
        result, receipt = self.execute()
        self.assertEqual(result['artifact'], (self.job/'original.pptx').read_bytes())
        self.assertIn('still needed', notice(receipt))
        self.assertFalse(list(self.records.glob('*-design-selection-*')))

    def test_visual_ready_content_priority_gets_one_response_and_comparison(self):
        baseline=content_priority(current((self.job/'original.pptx').read_bytes(),state='ready'))
        baseline['visual']['findings']=[]
        def review(body,*args):
            number=args[-1]
            value=content_priority(current(body,number,state='ready'),nominated=number==1)
            value['visual']['findings']=[]
            if number>1:
                compared(baseline,value)
                value['visual']['design_comparison']['resolutions']=[
                    {'id':f['id'],'status':'resolved','evidence':'The qualification is visible beside the evidence.'}
                    for f in response_findings(baseline)]
            return mark_response(self.cfg,value,scoped=False)
        self.run.review.side_effect=review;self.action='change'
        result,receipt=self.execute()
        self.assertEqual([n for n,_ in self.calls],['repair-1'])
        self.assertEqual(self.calls[0][1]['timeout'],360)
        self.assertEqual(result['artifact'],(self.job/'changed.pptx').read_bytes())
        self.assertEqual(self.run.review.call_count,2)
        self.assertEqual(receipt['visual']['design_assessment']['readiness'],'ready')
        self.assertIn('ready for the stated use',notice(receipt))

    def test_unnominated_content_suggestion_and_scoped_edit_do_not_start_response(self):
        value=content_priority(current(state='ready'),False)
        self.assertFalse(optional_response(mark_response(self.cfg,value,scoped=False)))
        value=content_priority(current(state='ready'))
        self.assertFalse(optional_response(mark_response(self.cfg,value,scoped=True)))
        value=content_priority(current(state='ready'))
        value['content']['findings'][0]['severity']='required'
        self.assertFalse(optional_response(mark_response(self.cfg,value,scoped=False)))


if __name__ == '__main__': unittest.main()
