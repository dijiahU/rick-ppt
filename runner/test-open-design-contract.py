"""Offline artifact/host checks for open design with strict delivery invariants."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from lxml import etree as E

from decision_routing import check_decisions, pin_decision_contract, write_design_packet

spec=importlib.util.spec_from_file_location('historical_decision_fixtures',Path(__file__).with_name('test-decision-routing.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
POLICY=f.POLICY


def plan():
    return {'version':4,'task':{'operation':'create','viewing':'live','research':'supplied_only'},
        'template_preservation':['Preserve supplied institution logo and background; design the open body.'],
        'design_direction':'A scientific explanation with visible mechanisms and direct comparisons.',
        'references':[], 'pages':[
            {'id':'intro','behavior':'click_reveal','assets':[{'route':'none'}]},
            {'id':'space','behavior':'static','assets':[{'route':'source_grounded_native'}]}]}


def rewrite(data,edits):
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src,zipfile.ZipFile(out,'w') as dst:
        for name in src.namelist():dst.writestr(name,edits.get(name,src.read(name)))
        for name,body in edits.items():
            if name not in src.namelist():dst.writestr(name,body)
    return out.getvalue()


class OpenDesignTests(unittest.TestCase):
    def check(self,p,**kwargs):return POLICY.validate_plan(p,f.outline(),allow_legacy=False,**kwargs)

    def test_minimal_plan_needs_no_design_taxonomy(self):
        value=plan();before=copy.deepcopy(value)
        result=self.check(value)
        self.assertEqual(value,before)
        self.assertIsNone(result['distinct_form_layouts'])
        self.check(value,stage='authored',artifact=f.deck(clicks=True))

    def test_arbitrary_descriptions_combinations_and_consistent_layout_are_allowed(self):
        value=plan()
        for page in value['pages']:
            page.update(intent='Scientific mechanism',form='Editable cutaway plus typography',
                strategy='Trace a concrete state',composition='Asymmetric layered evidence field',
                support=['Dense local detail'],role='Understand the result',visual_action='Enlarge the changing object')
        self.check(value)
        self.check(value,stage='authored',artifact=f.deck(clicks=True))

    def test_template_protection_and_external_art_reference_are_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=plan();p['references']=[f.DecisionTests().reference(root)]
            self.check(p,root=root)
            self.assertEqual(POLICY.page_reference_ids(p,p['pages'][0]),['R1'])
            self.assertNotIn('reference_ids',p['pages'][0])
            artifact=f.DecisionTests().reference_deck(p)
            # Add the valid click structure, preserving generated reference notes.
            with zipfile.ZipFile(io.BytesIO(f.deck(clicks=True))) as z:
                slide=z.read('ppt/slides/slide9.xml')
            artifact=rewrite(artifact,{'ppt/slides/slide9.xml':slide})
            self.check(p,root=root,stage='authored',artifact=artifact)
            (root/'decision-plan.json').write_text(json.dumps(p));packet=root/'packet';packet.mkdir()
            write_design_packet({'plugin':str(f.PLUGIN)},root,packet,artifact)
            report=json.loads((packet/'design-references.json').read_text())
            self.assertEqual(report['pages'][0]['reference_ids'],['R1'])
            self.assertEqual(report['template_preservation'],p['template_preservation'])
            p['pages'][0]['reference_ids']=[]
            with self.assertRaisesRegex(ValueError,'agree'):self.check(p,root=root)

    def test_real_assets_still_need_ready_correct_bytes_on_correct_page(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'image.png').write_bytes(b'IMAGE');p=plan()
            p['pages'][0]['assets']=[{'route':'supplied','kind':'documentary','status':'ready','file':'image.png','origin':'Real fixture'}]
            self.check(p,root=root,stage='authored',artifact=f.deck(clicks=True))
            for artifact in (f.deck(used_page=2,clicks=True),f.deck(data=b'OTHER',clicks=True)):
                with self.assertRaisesRegex(ValueError,'bytes'):self.check(p,root=root,stage='authored',artifact=artifact)
            p['pages'][0]['assets'][0].update(status='planned',file=None)
            with self.assertRaisesRegex(ValueError,'unresolved'):self.check(p,root=root,stage='authored')

    def test_inherited_logo_is_an_asset_but_unreferenced_layout_media_is_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'image.png').write_bytes(b'IMAGE');p=plan()
            p['pages'][0]['assets']=[{'route':'supplied','kind':'documentary','status':'ready','file':'image.png','origin':'Template logo'}]
            data=f.deck(used_page=0,clicks=True)
            layout=f'<p:sldLayout xmlns:p="{f.P}" xmlns:a="{f.A}" xmlns:r="{f.R}"><p:cSld><p:spTree><p:pic><a:blip r:embed="logo"/></p:pic></p:spTree></p:cSld></p:sldLayout>'
            relations=f'<Relationships><Relationship Id="logo" Type="{f.R}/image" Target="../media/asset.png"/></Relationships>'
            page_rels=f'<Relationships><Relationship Id="layout" Type="{f.R}/slideLayout" Target="../slideLayouts/layout1.xml"/></Relationships>'
            data=rewrite(data,{'ppt/slides/_rels/slide9.xml.rels':page_rels,'ppt/slideLayouts/layout1.xml':layout,'ppt/slideLayouts/_rels/layout1.xml.rels':relations})
            self.check(p,root=root,stage='authored',artifact=data)
            data=rewrite(data,{'ppt/slideLayouts/layout1.xml':layout.replace('r:embed="logo"','')})
            with self.assertRaisesRegex(ValueError,'bytes'):self.check(p,root=root,stage='authored',artifact=data)

    def test_malformed_timing_cannot_satisfy_native_click_requirement(self):
        p=plan();data=f.deck()
        fake=f'<p:sld xmlns:p="{f.P}"><p:sp><p:nvSpPr><p:cNvPr id="2"/></p:nvSpPr></p:sp><p:timing><p:cond evt="onNext"/><p:cTn nodeType="clickEffect" presetClass="entr"><p:childTnLst><p:set><p:cBhvr><p:tgtEl><p:spTgt spid="2"/></p:tgtEl></p:cBhvr></p:set></p:childTnLst></p:cTn></p:timing></p:sld>'
        data=rewrite(data,{'ppt/slides/slide9.xml':fake})
        with self.assertRaisesRegex(ValueError,'native behavior'):self.check(p,stage='authored',artifact=data)
        self.check(p,stage='authored',artifact=f.deck(clicks=True))

    def test_invalid_appear_states_do_not_fall_back_to_success(self):
        data=f.deck(clicks=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            original=z.read('ppt/slides/slide9.xml')
        changes=[original.replace(b'val="visible"',b'val="hidden"'),
                 original.replace(b'presetID="1"',b'presetID="1"').replace(b'nodeType="clickEffect"',b'nodeType="clickEffect"').replace(b'<p:cond delay="0"/>',b'<p:cond delay="indefinite"/>')]
        for body in changes:
            with self.assertRaisesRegex(ValueError,'native behavior'):
                self.check(plan(),stage='authored',artifact=rewrite(data,{'ppt/slides/slide9.xml':body}))

    def test_art_record_cannot_replace_actual_notes_or_claim_unviewed_work(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=plan();entry=f.DecisionTests().reference(root);p['references']=[entry]
            with self.assertRaisesRegex(ValueError,'Final slide notes'):self.check(p,root=root,stage='authored',artifact=f.deck(clicks=True))
            entry.update(inspection='read_text',evidence='Only a description')
            with self.assertRaisesRegex(ValueError,'actual work'):self.check(p,root=root)

    def test_new_host_pins_v4_and_historical_record_cannot_bypass_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cfg={'plugin':str(f.PLUGIN)}
            self.assertEqual(pin_decision_contract(cfg,root,'new',False),4)
            job=root/'job';job.mkdir();(job/'decision-plan.json').write_text(json.dumps(f.plan()))
            with self.assertRaisesRegex(ValueError,'pinned'):check_decisions(cfg,job,f.outline(),stage='planning')
            check_decisions({**cfg,'_choice_min_version':3,'_native_reveal_required':False},job,f.outline(),stage='planning')
            (job/'decision-plan.json').write_text(json.dumps(plan()))
            check_decisions(cfg,job,f.outline(),stage='authored',artifact=f.deck(clicks=True))

    def test_historical_v1_reference_helper_preserves_without_needing_operation(self):
        import design_references
        value=f.legacy_plan();value['version']=1;value['task'].pop('operation');value['task'].update(scope='new_deck',inputs='complete')
        before=copy.deepcopy(value)
        with tempfile.TemporaryDirectory() as temp:
            result=design_references.apply(Path(temp)/'unused-workspace',value,f.outline(),root=Path(temp),allow_legacy=True)
        self.assertEqual(result['pages_updated'],[]);self.assertEqual(value,before)

    def test_technical_capabilities_scope_and_asset_path_limits_still_apply(self):
        p=plan();p['task']['operation']='edit'
        with self.assertRaisesRegex(ValueError,'Operation'):self.check(p)
        p=plan();p['task']['research']='topic_research'
        with self.assertRaisesRegex(ValueError,'Search'):self.check(p,search_enabled=False)
        p=plan();p['pages'][0]['assets']=[{'route':'generate','kind':'documentary','status':'planned','file':None,'origin':'Fake factual evidence'}]
        with self.assertRaisesRegex(ValueError,'Generation'):self.check(p)
        p['pages'][0]['assets'][0]['kind']='illustrative'
        with self.assertRaisesRegex(ValueError,'Generation'):self.check(p,generation_enabled=False)
        with tempfile.TemporaryDirectory() as temp:
            p['pages'][0]['assets'][0].update(route='supplied',status='ready',file='../outside.png')
            with self.assertRaisesRegex(ValueError,'inside'):self.check(p,root=Path(temp))

class HostPromptTests(unittest.TestCase):
    def test_real_entry_reaches_author_with_compact_v4_manifest(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from workflow import _run_workflow
        from progress import Reporter
        class StopAtAuthor(Exception):pass
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            outline={'title':'Paper explanation','purpose':'Understand the mechanism','slides':[
                {'id':'intro','title':'The question','summary':'Explain the actual question and required context.'},
                {'id':'space','title':'Mechanism','summary':'Trace the changing state and its qualified result.'}]}
            task={'id':'offline-v4','title':'Paper explanation','brief':'Explain the supplied paper in its institutional template.','pages':2,'style':'Designer choice','language':'en'}
            (root/'request.json').write_text(json.dumps({**task,'mode':'create'}))
            captured={}
            def phase(name,prompt,**kwargs):
                captured[name]=prompt
                if name=='author':raise StopAtAuthor()
                (root/'outline.json').write_text(json.dumps(outline))
                (root/'decision-plan.json').write_text(json.dumps(plan()))
                (root/'source-notes.md').write_text('Supplied fixture facts and permitted design direction.')
            run=SimpleNamespace(conversation=None,journal=None,reusable_author=lambda:False,
                reusable=lambda name:False,phase=phase,complete_phase=Mock(),author_thread=None)
            cfg={'plugin':str(f.PLUGIN),'python':__import__('sys').executable,'_choice_min_version':4}
            reporter=Reporter(cfg,task,root,lambda *args:None,explicit_previews=True)
            with self.assertRaises(StopAtAuthor):
                _run_workflow(run,SimpleNamespace(),cfg,task,root,{'mode':'create'},SimpleNamespace(check=lambda:None),reporter)
            manifest=json.loads((root/'tool-manifest.json').read_text())
            self.assertEqual(manifest['decision_contract']['version'],4)
            self.assertEqual(manifest['decision_contract']['page_fields'],['id','behavior','assets'])
            self.assertEqual(set(captured),{'research','author'})
            for prompt in captured.values():
                payload=json.loads(prompt[prompt.index('{"stage"'):])
                docs={Path(item['path']).name:item['content'] for item in payload['documents']}
                catalog=json.loads(docs['workflow-choices.json'])
                self.assertEqual(set(catalog['page']),{'behavior'})
                self.assertNotIn('eligible_forms',catalog)

if __name__=='__main__':unittest.main()
