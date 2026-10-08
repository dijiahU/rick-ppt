"""Offline checks of real selection/embedding/repair branches, no queue admissions."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock
from PIL import Image

from decision_routing import choice_policy, check_decisions, needs_content_revision
from workflow import validate_report, _run_workflow

PLUGIN = Path(__file__).resolve().parents[1] / 'pptx-agent'
POLICY = choice_policy({'plugin': str(PLUGIN)})
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'


def plan():
    return {'version': 2, 'task': {'operation':'create', 'viewing': 'dual_use',
        'research': 'supplied_only', 'references': 'use_available', 'style': 'analytical',
        'palette': 'semantic', 'typography': 'installed_role_system'}, 'pages': [
        {'id': 'intro', 'intent': 'introduce', 'form': 'typography', 'support': [],
         'layout': 'focus', 'density': 'sparse', 'behavior': 'static',
         'assets': [{'route': 'none'}], 'role': 'Introduce the actual question.'},
        {'id': 'space', 'intent': 'show_space', 'form': 'diagram', 'support': ['typography'],
         'layout': 'spatial', 'density': 'balanced', 'behavior': 'static',
         'assets': [{'route': 'source_grounded_native'}], 'role': 'Show the shared route.'}]}


def outline():
    return {'slides': [{'id': 'intro'}, {'id': 'space'}]}


def deck(data=b'IMAGE', used_page=1, clicks=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        # Non-numeric ordering catches validators that assume slide filenames.
        archive.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst><p:sldId id="256" r:id="r1"/><p:sldId id="257" r:id="r2"/></p:sldIdLst></p:presentation>')
        archive.writestr('ppt/_rels/presentation.xml.rels', '<Relationships><Relationship Id="r1" Target="slides/slide9.xml"/><Relationship Id="r2" Target="/ppt/slides/slide4.xml"/></Relationships>')
        for page, number in ((1, 9), (2, 4)):
            image = '<a:blip r:embed="img"/>' if page == used_page else ''
            timing = '<p:timing><p:cond evt="onNext"/><p:spTgt spid="2"/></p:timing>' if clicks and page == 1 else ''
            archive.writestr(f'ppt/slides/slide{number}.xml', f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}">{image}{timing}</p:sld>')
            archive.writestr(f'ppt/slides/_rels/slide{number}.xml.rels', f'<Relationships><Relationship Id="img" Type="{R}/image" Target="../media/asset.png"/></Relationships>')
        archive.writestr('ppt/media/asset.png', data)
    return stream.getvalue()


class DecisionTests(unittest.TestCase):
    def check(self, value, **kwargs):
        return POLICY.validate_plan(value, outline(), **kwargs)

    def test_complete_choices_and_exact_coverage(self):
        result = self.check(plan())
        self.assertEqual(result['pages'], 2)
        self.assertEqual(result['distinct_form_layouts'], 2)
        for mutate in (lambda p: p['pages'].pop(), lambda p: p['pages'].reverse(),
                       lambda p: p['pages'][0].pop('form'), lambda p: p['task'].update(style='whatever')):
            value = plan(); mutate(value)
            with self.assertRaises(ValueError): self.check(value)

    def test_scaffold_has_exact_ids_and_no_preselected_task_or_page_choices(self):
        value = POLICY.plan_template(outline())
        self.assertEqual([page['id'] for page in value['pages']], ['intro', 'space'])
        self.assertTrue(all(choice is None for choice in value['task'].values()))
        self.assertTrue(all(page['form'] is None and page['assets'][0]['route'] is None for page in value['pages']))
        with self.assertRaises(ValueError): self.check(value)

    def test_eligibility_and_host_scope_cannot_be_evaded(self):
        value = plan(); value['pages'][0].update(intent='quantify', form='original_illustration')
        with self.assertRaises(ValueError): self.check(value)
        value = plan(); value['task']['operation'] = 'edit'
        with self.assertRaises(ValueError): self.check(value, mode='create')

    def test_normal_work_needs_no_input_state_classification(self):
        value = plan()
        self.assertNotIn('inputs', value['task'])
        self.check(value)
        value['pages'][0].update(form='documentary_image', assets=[
            {'route':'web_import','kind':'documentary','status':'planned','file':None,'origin':'Material still to acquire'}])
        self.check(value)  # Normal asset acquisition does not block planning.

    def test_legacy_records_migrate_without_modifying_original_bytes(self):
        value = plan(); value['version'] = 1
        value['task'].pop('operation'); value['task'].update(scope='new_deck', inputs='missing_essential')
        original = copy.deepcopy(value)
        self.assertEqual(self.check(value)['version'], 2)
        self.assertEqual(value, original)
        value['task']['scope'] = 'faithful_conversion'
        self.check(value, mode='edit', require_variation=False)

    def test_repetition_fails_new_deck_but_preserves_scoped_source(self):
        value = plan(); second = copy.deepcopy(value['pages'][0]); second['id'] = 'space'; value['pages'][1] = second
        with self.assertRaises(ValueError): self.check(value)
        value['task']['operation'] = 'edit'
        self.check(value, mode='edit')

    def test_unavailable_tools_and_documentary_generation_are_rejected(self):
        value = plan(); value['task']['research'] = 'topic_research'
        with self.assertRaises(ValueError): self.check(value, search_enabled=False)
        value = plan(); value['pages'][0].update(form='original_illustration', assets=[
            {'route': 'generate', 'kind': 'illustrative', 'status': 'planned', 'file': None, 'origin': 'New fictional interior'}])
        with self.assertRaises(ValueError): self.check(value, generation_enabled=False)
        value['pages'][0]['assets'][0]['kind'] = 'documentary'
        with self.assertRaises(ValueError): self.check(value)

    def test_asset_routes_are_explicit_and_compatible(self):
        for assets in ([], [{'route': 'invented'}], [{'route': 'none'}, {'route': 'source_grounded_native'}]):
            value = plan(); value['pages'][0]['assets'] = assets
            with self.assertRaises(ValueError): self.check(value)
        value = plan(); value['pages'][0]['form'] = 'documentary_image'
        with self.assertRaises(ValueError): self.check(value)

    def test_unresolved_asset_cannot_finish_authoring(self):
        value = plan(); value['pages'][0].update(form='documentary_image', assets=[
            {'route': 'web_import', 'kind': 'documentary', 'status': 'planned', 'file': None, 'origin': 'https://example.test/product'}])
        self.check(value)
        with self.assertRaises(ValueError): self.check(value, stage='authored')

    def test_selected_bytes_must_be_used_on_correct_presentation_page(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'image.png').write_bytes(b'IMAGE')
            value = plan(); value['pages'][0].update(form='documentary_image', assets=[
                {'route': 'supplied', 'kind': 'documentary', 'status': 'ready', 'file': 'image.png', 'origin': 'Authorized product image'}])
            result = self.check(value, stage='authored', root=root, artifact=deck())
            self.assertTrue(result['embedded_assets_checked'])
            for artifact in (deck(used_page=0), deck(used_page=2), deck(data=b'OTHER')):
                with self.assertRaises(ValueError): self.check(value, stage='authored', root=root, artifact=artifact)

    def test_assets_cannot_read_outside_task_or_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'image.png').write_bytes(b'IMAGE'); (root/'link.png').symlink_to(root/'image.png')
            for name in ('../image.png', str(root/'image.png'), 'link.png'):
                value = plan(); value['pages'][0]['assets'] = [{'route':'supplied','kind':'documentary','status':'ready','file':name,'origin':'Supplied'}]
                with self.assertRaises(ValueError): self.check(value, stage='authored', root=root)

    def test_selected_native_behavior_must_exist(self):
        value = plan(); value['pages'][0]['behavior'] = 'click_reveal'
        with self.assertRaises(ValueError): self.check(value, stage='authored', artifact=deck())
        self.check(value, stage='authored', artifact=deck(clicks=True))
        value['pages'][0]['behavior'] = 'internal_navigation'
        with self.assertRaises(ValueError): self.check(value, stage='authored', artifact=deck())

    def test_static_picture_cannot_claim_embedded_playback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'image.png').write_bytes(b'IMAGE')
            value = plan(); value['pages'][0].update(intent='demonstrate', form='embedded_media', behavior='embedded_playback', assets=[
                {'route':'supplied','kind':'media','status':'ready','file':'image.png','origin':'Test fixture'}])
            with self.assertRaises(ValueError): self.check(value, stage='authored', root=root, artifact=deck())

    def test_animated_gif_uses_native_image_relationship_without_playback_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); stream = io.BytesIO()
            Image.new('RGB',(8,8),'blue').save(stream,format='GIF',save_all=True,
                append_images=[Image.new('RGB',(8,8),'green')],duration=100,loop=0)
            body = stream.getvalue(); (root/'clip.gif').write_bytes(body)
            value = plan(); value['pages'][0].update(intent='demonstrate',form='embedded_media',behavior='embedded_playback',assets=[
                {'route':'supplied','kind':'media','status':'ready','file':'clip.gif','origin':'Synthetic animated fixture'}])
            self.check(value,stage='authored',root=root,artifact=deck(data=body))

    def test_host_requires_record_for_new_work_and_keeps_legacy_receipts(self):
        cfg = {'plugin': str(PLUGIN)}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertIsNone(check_decisions(cfg, root, outline(), stage='planning', required=False))
            with self.assertRaises(FileNotFoundError): check_decisions(cfg, root, outline(), stage='planning')
            (root/'decision-plan.json').write_text(json.dumps(plan()))
            receipt = check_decisions(cfg, root, outline(), stage='planning')
            self.assertEqual(len(receipt['decision_plan_sha256']), 64)

    def test_repair_route_tracks_work_not_reviewer_role(self):
        receipt = {'content': {'findings': [{'severity':'required','route':'native_repair'}]}, 'visual': {'findings': []}}
        self.assertFalse(needs_content_revision(receipt))
        receipt['visual']['findings'] = [{'severity':'required','route':'content_revision'}]
        self.assertTrue(needs_content_revision(receipt))
        receipt['visual']['findings'] = []; receipt['content']['findings'][0].pop('route')
        self.assertTrue(needs_content_revision(receipt))  # Historical reports retain their route.

    def test_review_route_validation_and_legacy_report_compatibility(self):
        finding = {'id':'f1','severity':'required','pages':[1],'observation':'Missing fact','impact':'Unclear','recommendation':'Correct it','route':'content_revision'}
        value = {'summary':'Checked','pages_reviewed':[1,2],'limitations':[],'findings':[finding]}
        validate_report(value, 2)
        finding['route'] = 'retain_suggestion'
        with self.assertRaises(ValueError): validate_report(value, 2)
        finding.pop('route'); validate_report(value, 2)

    def test_production_entry_rejects_missing_choices_before_authoring(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public = {'title':'A place','purpose':'Explain a spatial proposal','slides':[
                {'id':'intro','title':'The question','summary':'Introduce the actual project question.'},
                {'id':'space','title':'Shared route','summary':'Show the functions sharing the public route.'}]}
            def phase(name, prompt, **kwargs):
                (root/'outline.json').write_text(json.dumps(public))
                (root/'source-notes.md').write_text('Verified provided content')
            run = SimpleNamespace(conversation=None, journal=None, author_thread=None,
                reusable_author=lambda:False, reusable=lambda name:False,
                phase=Mock(side_effect=phase), complete_phase=Mock())
            task = {'id':'local-only','title':'A place','brief':'Explain the proposal','pages':2,'style':'Open','language':'en'}
            cfg = {'plugin':str(PLUGIN),'python':'python3'}
            with self.assertRaises(FileNotFoundError):
                _run_workflow(run, SimpleNamespace(), cfg, task, root, {'mode':'create'}, SimpleNamespace(), Mock())
            self.assertEqual([call.args[0] for call in run.phase.call_args_list], ['research'])
            run.complete_phase.assert_not_called()


if __name__ == '__main__':
    unittest.main()
