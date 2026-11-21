"""Offline decision/transport tests; no model quality or human acceptance claim."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from design_completion import CONTRACT, PRESENTATION, PRESENTATION_MARKER, CRAFT, CRAFT_MARKER, CRAFT_DIMENSIONS, craft_enabled, schema, selection, notice, presentation_schema, presentation_enabled, response_findings
from design_completion import READING_ORDER, READING_ORDER_MARKER, normalize_derived, readiness
from design_feedback import mark_response, optional_response, introduced_required, load_baseline
from workflow import validate_report, VISUAL_REPORT_SCHEMA, REPORT_SCHEMA, DESIGN_RESPONSE_SECONDS


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


def craft_report(value, score=6):
    value['visual_craft'] = dict(CRAFT)
    if score is not None and score < 8:value['visual']['findings'][0]['route']='native_repair'
    value['visual']['design_assessment']['visual_craft'] = {
        key: {'score': score if key == 'composition' else 8, 'pages': [1, 2],
              'evidence': 'The central example is small amid unstructured space on pages 1–2.' if key == 'composition'
                          else 'Deliberate type hierarchy and field correspondence carry the quiet document-led subject.',
              'finding_ids': ['F1'] if key == 'composition' and score is not None and score < 8 else []}
        for key in CRAFT_DIMENSIONS}
    return value


class CraftTests(unittest.TestCase):
    def check(self, value):
        return validate_report(value['visual'], 2, require_design=True, completion=True, craft=True)

    def test_new_contract_is_opt_in_and_keeps_historical_reports(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'skills/pptx';(root/'references').mkdir(parents=True);(root/'assets').mkdir()
            (root/'assets/workflow-choices.json').write_text('{"version":4}')
            guide=root/'references/design-completion.md';guide.write_text('Historical policy')
            self.assertFalse(craft_enabled({'plugin':directory}))
            guide.write_text(CRAFT_MARKER);self.assertTrue(craft_enabled({'plugin':directory}))
        self.assertNotIn('visual_craft',schema(VISUAL_REPORT_SCHEMA)['properties']['design_assessment']['properties'])
        self.assertIn('visual_craft',schema(VISUAL_REPORT_SCHEMA,craft=True)['properties']['design_assessment']['required'])
        validate_report(current()['visual'],2,require_design=True,completion=True)

    def test_clear_but_unfinished_cannot_be_ready_or_hidden_by_other_high_scores(self):
        value=craft_report(current(state='ready'))
        for key in CRAFT_DIMENSIONS[1:]:value['visual']['design_assessment']['visual_craft'][key]['score']=10
        with self.assertRaisesRegex(ValueError,'needs_revision'):self.check(value)
        value['visual']['design_assessment'].update(readiness='needs_revision',primary_findings=['F1'])
        self.check(value)

    def test_low_score_requires_real_located_action_not_a_cosmetic_retained_suggestion(self):
        for mutation in ('missing','invented','different_page','retain'):
            value=craft_report(current());row=value['visual']['design_assessment']['visual_craft']['composition']
            if mutation=='missing':row['finding_ids']=[]
            if mutation=='invented':row['finding_ids']=['imagined']
            if mutation=='different_page':
                row['pages']=[2];value['visual']['findings'][0]['pages']=[1]
            if mutation=='retain':value['visual']['findings'][0]['route']='retain_suggestion'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.check(value)
        for field in ('observation','impact','recommendation'):
            value=craft_report(current());value['visual']['findings'][0][field]=' '
            with self.subTest(missing=field),self.assertRaisesRegex(ValueError,'Empty review evidence'):self.check(value)
        value=craft_report(current());value['visual']['design_assessment']['visual_craft']['composition']['evidence']=' '
        with self.assertRaisesRegex(ValueError,'page/region evidence'):self.check(value)

    def test_retained_suggestion_on_low_score_is_format_correctable_by_exact_message(self):
        # workflow.review_pass grants one format-only correction to this exact
        # error on every backend; keep the two strings in step.
        value=craft_report(current());value['visual']['findings'][0]['route']='retain_suggestion'
        with self.assertRaises(ValueError) as caught:self.check(value)
        source=(Path(__file__).parent/'workflow.py').read_text()
        self.assertIn("craft_error=str(error) in ('"+str(caught.exception)+"'",source)

    def test_quiet_finished_work_can_pass_without_images_or_new_findings(self):
        value=craft_report(current(state='ready'),8);value['visual']['findings']=[]
        self.check(value)
        value['output_language']='zh-CN'
        self.assertIn('构图焦点 8',notice(value))
        self.assertIn('模型评分',notice(value))

    def test_supported_tone_gap_uses_existing_bounded_repair_without_factual_error(self):
        value=craft_report(current(),8)
        finding=value['visual']['findings'][0]
        finding.update(observation='Page 1 uses a toy-like prop scene for the explicitly sober briefing.',
                       impact='The main treatment conflicts with the requested presentation tone; the example is correct.',
                       recommendation='Rework the prop treatment and color distribution; keep the worked example, focal scale and click groups.',
                       route='native_repair')
        value['visual']['design_assessment']['visual_craft']['visual_expression'].update(
            score=6,evidence=finding['observation'],finding_ids=['F1'])
        self.check(value)
        with patch('design_feedback.enabled',return_value=True):mark_response({},value,scoped=False)
        self.assertTrue(optional_response(value))
        self.assertEqual(value['designer_response']['max_passes'],1)
        self.assertEqual(response_findings(value)[0]['recommendation'],finding['recommendation'])
        self.assertFalse(any(f['severity']=='required' for kind in ('content','visual') for f in value[kind]['findings']))
        value['visual']['design_assessment'].update(readiness='ready',primary_findings=[])
        with self.assertRaises(ValueError):self.check(value)

    def test_unavailable_or_invalid_score_cannot_be_promoted(self):
        value=craft_report(current(state='ready'),None)
        with self.assertRaisesRegex(ValueError,'Uncertain'):self.check(value)
        value['visual']['design_assessment']['readiness']='uncertain';self.check(value)
        for score in (True,0,11,'8',7.5):
            value['visual']['design_assessment']['visual_craft']['composition']['score']=score
            with self.subTest(score=score),self.assertRaises(ValueError):self.check(value)


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
        # No optional design response; with finishing polish switched off nothing runs.
        # (Polish on: PolishTests.)
        for state in ('ready', 'uncertain'):
            value = mark_response(self.cfg, current(state=state), scoped=False)
            self.assertFalse(optional_response(value))
        self.cfg['polish_pass'] = False
        self.run.review.side_effect = lambda body,*a:mark_response(self.cfg,current(body,state='ready'),scoped=False)
        self.execute()
        self.assertEqual(self.calls, [])

    def test_main_gap_triggers_only_one_response_and_keeps_improved_unfinished_candidate(self):
        self.cfg['polish_pass'] = False  # designer-response behaviour alone; polish after it: PolishTests
        self.configure(); self.action = 'change'
        result, receipt = self.execute()
        self.assertEqual(result['artifact'], (self.job/'changed.pptx').read_bytes())
        self.assertEqual([n for n,_ in self.calls], ['repair-1'])
        self.assertEqual(self.calls[0][1]["timeout"], DESIGN_RESPONSE_SECONDS)
        self.assertEqual(self.run.review.call_count, 2)
        self.assertIn('still needed', notice(receipt))
        decision = json.loads(next(self.records.glob('*-design-selection-*')).read_text())
        self.assertEqual(decision['selected'], 'candidate')
        self.assertEqual(decision['candidate_sha256'], hashlib.sha256(result['artifact']).hexdigest())

    def test_low_picture_craft_uses_existing_single_response_and_real_version_selection(self):
        self.cfg['polish_pass'] = False  # designer-response behaviour alone; polish after it: PolishTests
        baseline=craft_report(current((self.job/'original.pptx').read_bytes()))
        def review(body,rendered,packet,payload,number):
            value=craft_report(current(body,number,'ready' if number>1 else 'needs_revision'),8 if number>1 else 7)
            validate_report(value['visual'],2,require_design=True,completion=True,craft=True)
            if number>1:compared(baseline,value,resolution='resolved')
            return mark_response(self.cfg,value,scoped=False)
        self.run.review.side_effect=review;self.action='change'
        result,receipt=self.execute()
        self.assertEqual([n for n,_ in self.calls],['repair-1'])
        self.assertEqual(self.run.review.call_count,2)
        self.assertEqual(result['artifact'],(self.job/'changed.pptx').read_bytes())
        self.assertIn('composition 8',notice(receipt))

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
        self.assertEqual(self.calls[0][1]["timeout"], DESIGN_RESPONSE_SECONDS)
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


def content_suggestion(value, severity='suggestion', pages=(1,)):
    value['content']['findings'] = [{'id': 'C1', 'severity': severity, 'pages': list(pages),
        'observation': 'Sample dates fall in an earlier month than the stated reporting period.',
        'impact': 'Deadlines read as already past for the intended audience.',
        'recommendation': 'Re-anchor sample dates to the reporting period; keep durations and ordering.',
        'route': 'content_revision'}]
    return value


class RequiredOriginTests(unittest.TestCase):
    def setUp(self):
        self.base = content_suggestion(current(b'baseline'))
        self.next = compared(self.base, content_suggestion(current(b'candidate', 2), 'required'))

    def test_linked_severity_drift_is_not_introduced(self):
        self.next['content']['carried_findings'] = [{'id': 'C1', 'prior_id': 'C1'}]
        introduced, carried = introduced_required(self.base, self.next)
        self.assertEqual(introduced, [])
        self.assertEqual(carried[0]['evidence'], 'reviewer_link')
        self.assertEqual(selection(self.base, self.next, introduced=introduced)['selected'], 'candidate')
        self.assertEqual(selection(self.base, self.next)['reason'], 'required_regression')

    def test_unlinked_or_moved_required_finding_is_introduced(self):
        self.assertEqual(len(introduced_required(self.base, self.next)[0]), 1)
        self.next['content']['carried_findings'] = [{'id': 'C1', 'prior_id': 'C1'}]
        self.next['content']['findings'][0]['pages'] = [2]
        self.assertEqual(len(introduced_required(self.base, self.next)[0]), 1)

    def test_untouched_pages_prove_pre_existing_without_a_link(self):
        introduced, carried = introduced_required(self.base, self.next, unchanged={1})
        self.assertEqual((introduced, carried[0]['evidence']), ([], 'pages_unchanged'))

    def test_visual_regression_overrides_reviewer_link(self):
        self.next['content']['findings'] = []
        self.next['visual']['findings'][0]['severity'] = 'required'
        self.next['visual']['carried_findings'] = [{'id': 'F1', 'prior_id': 'F1'}]
        self.assertEqual(introduced_required(self.base, self.next)[0], [])
        self.next['visual']['design_comparison']['regression_findings'] = ['F1']
        self.assertEqual(len(introduced_required(self.base, self.next)[0]), 1)
        self.next['visual']['design_comparison']['regression_findings'] = []
        self.next['visual']['design_comparison']['resolutions'][0]['status'] = 'regressed'
        self.assertEqual(len(introduced_required(self.base, self.next)[0]), 1)

    def test_carried_links_are_validated_against_actual_ids(self):
        report = self.next['content']
        with self.assertRaisesRegex(ValueError, 'carried_findings'):
            validate_report(report, 2, prior_ids=['C1'])
        for rows in ([{'id': 'C9', 'prior_id': 'C1'}], [{'id': 'C1', 'prior_id': 'X'}],
                     [{'id': 'C1', 'prior_id': 'C1'}, {'id': 'C1', 'prior_id': 'C1'}]):
            report['carried_findings'] = rows
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_report(report, 2, prior_ids=['C1'])
        report['carried_findings'] = [{'id': 'C1', 'prior_id': 'C1'}]
        validate_report(report, 2, prior_ids=['C1'])
        with self.assertRaises(ValueError):validate_report(report, 2)


class RequiredOriginWorkflowTests(unittest.TestCase):
    setUp = fixture.FeedbackTests.setUp
    execute = fixture.FeedbackTests.execute
    fake_restore = fixture.FeedbackTests.fake_restore

    def configure(self, link):
        baseline = content_suggestion(current((self.job/'original.pptx').read_bytes()))
        def review(body, rendered, packet, payload, number):
            if number == 1:
                value = content_suggestion(current(body))
            elif number == 2:
                value = compared(baseline, content_suggestion(current(body, 2), 'required'))
                if link:value['content']['carried_findings'] = [{'id': 'C1', 'prior_id': 'C1'}]
            else:
                value = current(body, number, 'ready')
            return mark_response(self.cfg, value, scoped=False)
        self.run.review.side_effect = review
        self.action = 'change'
        author_phase = self.run.phase
        def phase(name, prompt, **options):
            if 'thread' not in options:  # content-revision research step of a required repair
                self.calls.append((name, options)); return
            return author_phase(name, prompt, **options)
        self.run.phase = phase

    def test_escalated_existing_issue_keeps_improvement_and_repairs_it(self):
        self.configure(link=True)
        with patch('design_feedback.restore_baseline', side_effect=self.fake_restore) as fallback:
            result, receipt = self.execute()
        fallback.assert_not_called()
        self.assertEqual([n for n, _ in self.calls if n.startswith('repair-')][:2], ['repair-1', 'repair-2'])
        self.assertEqual(self.run.review.call_count, 3)
        self.assertEqual(result['artifact'], (self.job/'changed.pptx').read_bytes())
        self.assertEqual(receipt['round'], 3)
        self.assertIsNone(load_baseline(self.run))
        decision = json.loads(next(self.records.glob('*-design-selection-*')).read_text())
        self.assertEqual(decision['selected'], 'candidate')

    def test_unlinked_required_finding_still_restores_baseline(self):
        self.configure(link=False)
        with patch('design_feedback.restore_baseline', side_effect=self.fake_restore) as fallback:
            result, receipt = self.execute()
        fallback.assert_called_once()
        self.assertEqual(result['artifact'], (self.job/'original.pptx').read_bytes())
        self.assertEqual(receipt['round'], 1)


class GeneratedLookTests(unittest.TestCase):
    def setUp(self):
        self.value = current(state='ready')['visual']
        self.value['design_assessment'].update(generated_look='some_tells', generated_tells=[{
            'pages': [2], 'region': 'Top KPI strip across the page',
            'resembles': 'Default four-tile KPI strip with matching pictograms',
            'why_unjustified': 'The quarter has two meaningful figures; the other tiles restate the title.',
            'direction': 'Lead with the two figures at the scale of their consequence; drop the filler tiles.',
            'scope': 'page', 'finding_ids': ['F1']}])

    def check(self, value=None):
        return validate_report(value or self.value, 2, require_design=True, completion=True, generated_look=True)

    def test_schema_offers_fields_only_when_enabled(self):
        enabled = schema(VISUAL_REPORT_SCHEMA, generated_look=True)['properties']['design_assessment']
        self.assertIn('generated_tells', enabled['required'])
        self.assertEqual(enabled['properties']['generated_look']['enum'], ['clear', 'some_tells', 'pronounced'])
        self.assertNotIn('generated_look', schema(VISUAL_REPORT_SCHEMA)['properties']['design_assessment']['properties'])
        with self.assertRaises(ValueError):
            validate_report(self.value, 2, require_design=True, completion=True)

    def test_page_tells_stay_optional_but_deck_or_pronounced_tells_need_revision(self):
        self.check()  # page-local tells can remain suggestions on a ready deck
        for key, value in (('generated_look', 'pronounced'), ('scope', 'deck')):
            changed = copy.deepcopy(self.value)
            if key == 'scope':changed['design_assessment']['generated_tells'][0]['scope'] = value
            else:changed['design_assessment'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Deck-wide generated look'):self.check(changed)
            assessment = changed['design_assessment']
            assessment.update(readiness='needs_revision', primary_findings=['F1'])
            finding = next(f for f in changed['findings'] if f['id'] == 'F1'); finding['route'] = 'native_repair'
            self.check(changed)

    def test_any_number_of_tells_but_level_must_match(self):
        self.value['design_assessment'].update(generated_look='clear', generated_tells=[])
        self.check()
        self.value['design_assessment']['generated_look'] = 'some_tells'
        with self.assertRaisesRegex(ValueError, 'level'):self.check()

    def test_each_tell_is_located_and_carried_by_a_real_finding(self):
        tell = self.value['design_assessment']['generated_tells'][0]
        for key, bad in (('pages', [3]), ('finding_ids', []), ('finding_ids', ['missing']),
                         ('pages', [1]), ('resembles', ' '), ('scope', 'site')):
            original = copy.deepcopy(tell); tell[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):self.check()
            tell.clear(); tell.update(original)
        self.check()


class ReadingOrderTests(unittest.TestCase):
    def setUp(self):
        self.value = current(state='ready')['visual']
        self.assessment = self.value['design_assessment']
        self.row = {'page': 2, 'seen': ['Large portrait', 'Blue banner', 'Chart labels'],
                    'takeaway': 'The chart compares two quarters.', 'matches_point': False}
        self.assessment['reading_order'] = [self.row]

    def check(self):
        return validate_report(self.value, 2, require_design=True, completion=True, reading_order=True)

    def test_pinned_marker_gates_review_schema_notes_and_receipt(self):
        spec = importlib.util.spec_from_file_location('review_fixture', Path(__file__).with_name('test-review-sessions.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        fixture = module.ReviewRecoveryTests()
        self.addCleanup(fixture.doCleanups); fixture.setUp()
        skill = fixture.plugin/'skills/pptx'; (skill/'assets').mkdir()
        (skill/'assets/workflow-choices.json').write_text('{"version":4}')
        (skill/'references/design-completion.md').write_text('Substantive design review')
        guide = skill/'references/visual-review.md'
        glance_rule = 'Take a three-second glance at each content page.'
        note = '阅读顺序：① Turnover ② Blue banner ③ Chart labels'
        (fixture.packet/'audience-notes.json').write_text(json.dumps({'pages': [
            {'number': 1, 'text': 'Unrelated speaker notes'},
            {'number': 2, 'text': 'Author intro '+note+' [PPTX-DESIGN-REFERENCES-BEGIN] Reference record'}]}))
        phase = fixture.run.phase

        def inspect(name, prompt, **options):
            report, thread = phase(name, prompt, **options)
            self.assertNotIn('Unrelated speaker notes', prompt)
            self.assertNotIn('Reference record', prompt)
            self.assertEqual(note in prompt, active and name.startswith('visual'))
            self.assertEqual(glance_rule in prompt, active and name.startswith('visual'))
            if name.startswith('visual'):
                assessment = options['schema']['properties']['design_assessment']
                self.assertEqual('reading_order' in assessment['properties'], active)
                self.assertEqual('reading_order' in assessment['required'], active)
                report = copy.deepcopy(self.value)
                if not active:report['design_assessment'].pop('reading_order')
                if scoped:
                    for key in ('readiness', 'primary_findings'):report['design_assessment'].pop(key)
            return report, thread

        fixture.run.phase = inspect
        for marked, scoped in ((False, False), (True, False), (True, True)):
            with self.subTest(marked=marked, scoped=scoped):
                active = marked and not scoped
                guide.write_text(READING_ORDER_MARKER+'\n'+glance_rule if marked else 'Historical policy')
                if scoped:
                    fixture.payload['mode'] = 'edit'
                    fixture.expected_review_payload = fixture.payload
                receipt = fixture.review()
                self.assertEqual(receipt.get('reading_order'), READING_ORDER if active else None)

    def test_rejects_bad_reading_order_shape(self):
        for field, bad in (('page', 0), ('page', 3), ('page', True), ('seen', []),
                           ('seen', ['One', 'Two', 'Three', 'Four']), ('seen', [' ']),
                           ('seen', [1]), ('takeaway', ' '), ('matches_point', 0)):
            with self.subTest(field=field, bad=bad):
                self.assessment['reading_order'] = [dict(self.row, **{field: bad})]
                with self.assertRaisesRegex(ValueError, 'reading_order'):self.check()
        for bad in (None, {}, [{}], [dict(self.row, extra=True)]):
            with self.subTest(bad=bad):
                self.assessment['reading_order'] = bad
                with self.assertRaisesRegex(ValueError, 'reading_order'):self.check()

    def test_valid_evidence_is_optional_and_leaves_readiness_unchanged(self):
        for size in (1, 2, 3):
            self.assessment['reading_order'] = [dict(self.row, seen=self.row['seen'][:size])]
            self.assertEqual(self.check(), self.value)
            self.assertEqual(normalize_derived(self.value), self.value)
            self.assertEqual(readiness(self.value), 'ready')
        with self.assertRaises(ValueError):
            validate_report(self.value, 2, require_design=True, completion=True)
        self.assessment.pop('reading_order')
        self.check()


class StrictSchemaTests(unittest.TestCase):
    """Every schema the host sends to a model must satisfy strict structured output:
    each object has additionalProperties false and lists every property as required."""
    def violations(self, node, path=''):
        found = []
        if isinstance(node, dict):
            if node.get('type') == 'object' or 'properties' in node:
                props = set(node.get('properties', {}))
                if node.get('additionalProperties') is not False or props != set(node.get('required', [])):
                    found.append((path, sorted(props - set(node.get('required', [])))))
            for key, child in node.items():found += self.violations(child, path + '/' + key)
        elif isinstance(node, list):
            for i, child in enumerate(node):found += self.violations(child, f'{path}[{i}]')
        return found

    def test_all_visual_review_schema_variants_are_strict(self):
        import itertools
        from workflow import VISUAL_REPORT_SCHEMA, LEGACY_VISUAL_REPORT_SCHEMA
        self.assertEqual(self.violations(LEGACY_VISUAL_REPORT_SCHEMA), [])
        for craft, coverage, look, order in itertools.product((False, True), repeat=4):
            if coverage and not craft:continue
            value = schema(VISUAL_REPORT_SCHEMA, None, craft=craft, coverage=coverage, generated_look=look, reading_order=order)
            with self.subTest(craft=craft, coverage=coverage, generated_look=look, reading_order=order):
                self.assertEqual(self.violations(value), [])
                self.assertEqual('reading_order' in value['properties']['design_assessment']['properties'], order)


class NormalizeTests(unittest.TestCase):
    def test_low_scores_with_actionable_links_become_primary_and_revision(self):
        from design_completion import normalize_derived
        report={'findings':[{'id':'F1','route':'native_repair','severity':'suggestion'},
                            {'id':'F2','route':'retain_suggestion','severity':'suggestion'}],
                'design_assessment':{'readiness':'ready','primary_findings':[],
                    'visual_craft':{'composition':{'score':6,'finding_ids':['F1','F2']},'typography':{'score':8,'finding_ids':[]},
                                    'visual_expression':{'score':6,'finding_ids':[]}},
                    'visual_coverage':[{'page':1,'status':'missing','finding_ids':['F1']}]}}
        out=normalize_derived(report)
        a=out['design_assessment']
        self.assertEqual(a['readiness'],'needs_revision');self.assertEqual(a['primary_findings'],['F1'])
        self.assertEqual(a['visual_craft']['visual_expression']['finding_ids'],['F1'])
        self.assertEqual(report['design_assessment']['readiness'],'ready')  # input not mutated

    def test_scores_at_seven_or_above_change_nothing(self):
        from design_completion import normalize_derived
        report={'findings':[{'id':'F1','route':'native_repair','severity':'suggestion'}],
                'design_assessment':{'readiness':'ready','primary_findings':[],
                    'visual_craft':{'composition':{'score':7,'finding_ids':['F1']}}}}
        self.assertEqual(normalize_derived(report),report)


    def test_linked_finding_on_other_pages_extends_entry_pages(self):
        from design_completion import normalize_derived
        report={'findings':[{'id':'F1','route':'native_repair','severity':'suggestion','pages':[4]},
                            {'id':'F2','route':'native_repair','severity':'suggestion','pages':[2,3]}],
                'design_assessment':{'readiness':'needs_revision','primary_findings':['F1'],
                    'visual_craft':{'sequence':{'score':7,'pages':[1,2],'finding_ids':['F1','F2']}}}}
        row=normalize_derived(report)['design_assessment']['visual_craft']['sequence']
        self.assertEqual(row['pages'],[1,2,4])  # F2 already shares page 2; F1 adds page 4


class PolishTests(unittest.TestCase):
    """Finishing polish: a passed review applies its directly fixable suggestions once."""
    execute = fixture.FeedbackTests.execute
    fake_restore = fixture.FeedbackTests.fake_restore

    def setUp(self):
        fixture.FeedbackTests.setUp(self)
        self.prompts = []; inner = self.run.phase
        def phase(name, prompt, **options):
            self.prompts.append(prompt); return inner(name, prompt, **options)
        self.run.phase = phase

    def passed(self, body, number, route='native_repair', required=False):
        value = current(body, number, 'ready')
        value['visual']['findings'][0]['route'] = route
        if required:
            value['visual']['findings'] = [dict(value['visual']['findings'][0], id='F9', severity='required',
                                                 observation='A label now overlaps the chart.')]
        return mark_response(self.cfg, value, scoped=False)

    def test_marker_needs_fixable_suggestion_full_review_and_rounds_left(self):
        from design_feedback import polish_response
        for number, route, scoped, expected in [(2, 'native_repair', False, True), (2, 'retain_suggestion', False, True),
                                                 (2, 'content_revision', False, False),
                                                 (2, 'native_repair', True, False), (3, 'native_repair', False, False)]:
            value = fixture.receipt(b'x', number); value['visual']['findings'][0]['route'] = route
            self.assertEqual(polish_response(mark_response(self.cfg, value, scoped=scoped)), expected, (number, route, scoped))
        value = fixture.receipt(b'x', 2); value['visual']['findings'][0]['route'] = 'native_repair'
        self.assertFalse(polish_response(mark_response(dict(self.cfg, polish_pass=False), value, scoped=False)))
        content_only = fixture.receipt(b'x', 2)
        content_only['content']['findings'] = [dict(content_only['visual']['findings'][0], route='retain_suggestion')]
        content_only['visual']['findings'] = []
        self.assertFalse(polish_response(mark_response(self.cfg, content_only, scoped=False)))
        self.assertFalse(polish_response(value | {'polish_response': {'version': 1, 'max_passes': 1},
                                                  'visual': dict(value['visual'], findings=[dict(value['visual']['findings'][0], severity='required')])}))

    def test_polish_change_is_reviewed_once_and_delivered(self):
        first = {}
        def review(body, rendered, packet, payload, number):
            value = self.passed(body, number)
            if number == 1: first.update(value)
            else: compared(first, value, 'better', resolution='resolved')
            return value
        self.run.review.side_effect = review
        self.action = 'change'
        result, receipt = self.execute()
        self.assertEqual([n for n, _ in self.calls], ['repair-1'])
        self.assertIn('FINISHING POLISH', self.prompts[0])
        self.assertEqual(self.run.review.call_count, 2)
        self.assertEqual(result['artifact'], (self.job/'changed.pptx').read_bytes())

    def test_new_required_after_polish_restores_the_passed_version(self):
        def review(body, rendered, packet, payload, number):
            return self.passed(body, number, required=number > 1)
        self.run.review.side_effect = review; self.action = 'change'
        with patch('design_feedback.restore_baseline', side_effect=self.fake_restore):
            result, receipt = self.execute()
        self.assertEqual(result['artifact'], (self.job/'original.pptx').read_bytes())
        self.assertEqual(receipt['round'], 1)
        self.assertEqual([n for n, _ in self.calls], ['repair-1'])

    def test_equivalent_polish_with_a_resolved_suggestion_is_kept(self):
        first = {}
        def review(body, rendered, packet, payload, number):
            value = self.passed(body, number)
            if number == 1: first.update(value)
            else: compared(first, value, 'equivalent', resolution='resolved')
            return value
        self.run.review.side_effect = review; self.action = 'change'
        result, _ = self.execute()
        self.assertEqual(result['artifact'], (self.job/'changed.pptx').read_bytes())
        self.assertEqual(json.loads(next(self.records.glob('*-design-selection-*')).read_text())['reason'], 'polish_resolved')

    def test_accepted_designer_response_still_gets_one_polish(self):
        first = {}
        def review(body, rendered, packet, payload, number):
            if number == 1:
                value = mark_response(self.cfg, current(body, 1, 'needs_revision'), scoped=False)
                first.update(value); return value
            value = self.passed(body, number)
            if number == 2: compared(first, value, 'better', resolution='resolved')
            else: value['visual']['design_comparison'] = None; value['visual'].pop('design_comparison')
            return value
        self.run.review.side_effect = review; self.action = 'change'
        self.execute()
        self.assertEqual([n for n, _ in self.calls], ['repair-1', 'repair-2'])
        self.assertIn('FINISHING POLISH', self.prompts[1])
        self.assertLessEqual(self.run.review.call_count, 3)

    def test_noop_polish_delivers_reviewed_bytes_without_rereview(self):
        self.run.review.side_effect = lambda body, rendered, packet, payload, number: self.passed(body, number)
        result, _ = self.execute()
        self.assertEqual(self.run.review.call_count, 1)
        self.assertEqual(result['artifact'], (self.job/'original.pptx').read_bytes())


class FinalRoundTests(unittest.TestCase):
    def test_final_round_delivers_latest_version_with_open_issues_by_default(self):
        from workflow import final_round_outcome
        self.assertEqual(final_round_outcome([],{}),'deliver')
        self.assertEqual(final_round_outcome([{'id':'F1'}],{}),'deliver_open')
        self.assertEqual(final_round_outcome([{'id':'F1'}],{'deliver_with_open_issues':False}),'fail')
        self.assertEqual(final_round_outcome([{'id':'F1'}],{'deliver_with_open_issues':True}),'deliver_open')


if __name__ == '__main__': unittest.main()
