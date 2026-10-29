import copy
import json
from pathlib import Path
import shutil
from unittest.mock import patch

from PIL import Image
import pytest

import page_design as design
from pptx_core.common import sha256
from pptx_core.manifest import content_fingerprint, manifest
from pptx_core.renderer import render


@pytest.fixture
def task(tmp_path, ws):
    (tmp_path/'outline.json').write_text(json.dumps({'title':'Mechanism','purpose':'Explain the relationship',
        'slides':[{'id':'mechanism','title':'Aggregation','summary':'Supported mechanism, with limits.'},
                  {'id':'evidence','title':'Evidence','summary':'Source observations.'},
                  {'id':'closing','title':'Closing','summary':'Retain the conditions.'}]}))
    (tmp_path/'source-notes.md').write_text('# Original evidence\n\nDo not change units or reported conditions.\n')
    return tmp_path, ws


def handoff(root, value):
    with (root/'source-notes.md').open('a') as stream:
        stream.write('\n```pptx-handoff\n'+json.dumps(value,ensure_ascii=False)+'\n```\n')


def fake_render(ws, number=1, color='white'):
    # The native render orchestration still validates, packs and binds the real
    # native input; only external LibreOffice execution is replaced in unit tests.
    def package(source, destination, slide, total):
        folder=Path(destination)/('generation-'+str(len(list(Path(destination).iterdir()))))
        folder.mkdir()
        numbers=[slide] if slide else list(range(1,total+1))
        pages=[]
        for page in numbers:
            image=folder/f'slide-{page}.png';Image.new('RGB',(96,54),color).save(image);pages.append(str(image))
        pdf=folder/'deck.pdf';pdf.write_bytes(b'%PDF-test-only')
        return {'pages':pages,'pdf':str(pdf),'source_hash':sha256(source),'at':'test-render','ok':True}
    with patch('pptx_core.renderer.render_package',side_effect=package):
        return render(ws,number)


def observation(root, **changes):
    value={'observation':'The relation was difficult to trace.',
           'actual_change':'Enlarged the relationship and kept source conditions.',
           'preserve':['Original evidence limits'],'outcome':'changed',**changes}
    path=root/'observation.json';path.write_text(json.dumps(value));return path


def test_plain_notes_remain_valid_and_read_only_without_optional_records(task):
    root, ws=task
    before={p: p.read_bytes() for p in [root/'outline.json',root/'source-notes.md',ws.state_path]}
    value=design.context(root,'mechanism',ws.root)
    assert value['page']['summary']=='Supported mechanism, with limits.'
    assert value['handoff']=={} and value['native']['preview']['status']=='not_recorded'
    assert design.handoff_index(root)['pages']==[]
    assert all(path.read_bytes()==data for path,data in before.items())


def test_native_object_index_reuses_actual_inspection_and_page_hash(task):
    root, ws = task
    from pptx_core.cli import inspect
    value = design.context(root, 'mechanism', ws.root)
    assert value['native']['objects'] == inspect(ws, 1)['shapes']
    assert value['native']['objects'][0]['text'] == 'Original title 1'
    assert value['native']['page_sha256'] == sha256(ws.root/value['native']['part'])


def test_large_object_index_defers_without_losing_native_preview_context(task):
    root, ws = task
    from lxml import etree
    part=ws.root/'ppt/slides/slide1.xml'
    tree=etree.parse(str(part));tree.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}t').text='X'*150000
    tree.write(str(part),encoding='UTF-8',xml_declaration=True)
    value=design.context(root,'mechanism',ws.root)
    assert value['native']['objects'] is None
    assert value['native']['object_count'] > 0
    assert value['native']['objects_status'].startswith('deferred')
    assert value['native']['preview']['status']=='not_recorded'


def test_page_handoff_preserves_qualifiers_and_checks_actual_material(task):
    root, ws=task
    image=root/'selected.png';Image.new('RGB',(42,24),'blue').save(image)
    evidence=root/'evidence.txt';evidence.write_text('Illustrative weights, not measurements.')
    value={'page_id':'mechanism','question':'What is aggregated?',
           'evidence':[{'source':'evidence.txt','locator':'Line 1','claim':'Illustrative weights, not measurements.'}],
           'materials':[{'file':'selected.png','role':'Inspected detail'}, {'file':'missing.png','role':'Pending detail'}],
           'preserve':['Reported units and labels'],'uncertainties':['Example weights unverified'],
           'visual_opportunity':'Make the aggregation inspectable'}
    handoff(root,value)
    result=design.context(root,'mechanism')
    assert result['handoff']=={k:v for k,v in value.items() if k!='page_id'}
    checks=[row['file_check'] for row in result['resources']]
    assert checks[0]['sha256']==sha256(evidence)
    assert checks[1]['pixels']==[42,24] and checks[1]['sha256']==sha256(image)
    assert checks[2]['availability']=='missing'
    assert design.context(root,'evidence')['handoff']=={}


def test_malformed_or_duplicate_optional_handoff_is_diagnosed_without_rewriting_notes(task):
    root,_=task
    handoff(root,{'page_id':'mechanism','question':'First possibility'})
    handoff(root,{'page_id':'mechanism','question':'Conflicting possibility'})
    with (root/'source-notes.md').open('a') as stream:
        stream.write('\n```pptx-handoff\n{partial\n```\n')
    before=(root/'source-notes.md').read_bytes()
    value=design.context(root,'mechanism')
    assert value['handoff']=={} and len(value['diagnostics'])==2
    assert (root/'source-notes.md').read_bytes()==before
    assert design.handoff_index(root)['diagnostics']


def test_private_handoff_does_not_enter_public_outline(task):
    root,_=task
    handoff(root,{'page_id':'mechanism','materials':[{'file':'selected.png','role':'PRIVATE-DESIGN-CONTEXT'}]})
    import sys
    from importlib.util import spec_from_file_location,module_from_spec
    path=Path(__file__).resolve().parents[3]/'runner/outline.py'
    spec=spec_from_file_location('public_outline_for_design_test',path)
    module=module_from_spec(spec);spec.loader.exec_module(module)
    public=module.validate_outline(json.loads((root/'outline.json').read_text()))
    assert 'PRIVATE-DESIGN-CONTEXT' not in json.dumps(public)
    assert 'selected.png' not in json.dumps(public)


def test_only_explicit_current_page_reference_applications_are_projected(task):
    root, ws = task
    Image.new('RGB', (37, 19), 'gold').save(root/'reference.png')
    common = {'kind':'design_work', 'creator':'Fixture designer', 'source':'https://example.test/work',
              'inspection':'local_image', 'evidence':'reference.png',
              'observed':'Unequal subject scale', 'borrowed':'Focus through scale'}
    plan = {'version':4, 'pages':[], 'references':[
        {**common, 'id':'shared', 'title':'Shared work', 'applications':[
            {'pages':['mechanism', 'closing'], 'action':'Enlarge the actual relationship'}]},
        {**common, 'id':'other', 'title':'Other work', 'applications':[
            {'pages':['evidence'], 'action':'Other page only'}]},
        {**common, 'id':'unapplied', 'title':'Not applied', 'applications':[]}]}
    path = root/'decision-plan.json'; path.write_text(json.dumps(plan))
    before = {p:p.read_bytes() for p in [path, root/'outline.json', root/'source-notes.md', ws.state_path]}
    result = design.context(root, 'mechanism')
    assert [r['id'] for r in result['references']] == ['shared']
    ref = result['references'][0]
    assert ref['observed'] == common['observed'] and ref['borrowed'] == common['borrowed']
    assert ref['applications'] == [{'pages':['mechanism'], 'action':'Enlarge the actual relationship'}]
    assert ref['file_check']['sha256'] == sha256(root/'reference.png')
    assert ref['file_check']['pixels'] == [37,19]
    assert design.context(root, 'closing')['references'][0]['file_check']['sha256'] == ref['file_check']['sha256']
    assert all(p.read_bytes() == body for p, body in before.items())


def test_missing_unavailable_and_hosted_references_are_not_promoted_to_viewed(task):
    root,_ = task
    records = []
    for ident, inspection, evidence in [('missing', 'local_image', 'missing.png'),
                                        ('unavailable', 'unavailable', None),
                                        ('hosted', 'hosted_visual', 'Hosted tool observation, not a local image')]:
        records.append({'id':ident, 'title':ident, 'inspection':inspection, 'evidence':evidence,
                        'applications':[{'pages':['mechanism'], 'action':'Declared application'}]})
    (root/'decision-plan.json').write_text(json.dumps({'references':records}))
    result = design.context(root,'mechanism')['references']
    assert [r['inspection'] for r in result] == ['local_image','unavailable','hosted_visual']
    assert result[0]['file_check']['availability'] == 'missing'
    assert all('sha256' not in r['file_check'] for r in result)
    assert result[1]['evidence'] is None


def test_no_reference_or_partial_plan_keeps_existing_context_available(task):
    root,_ = task
    assert design.context(root,'mechanism')['references'] == []
    (root/'decision-plan.json').write_text('{"references":[')
    result = design.context(root,'mechanism')
    assert result['references'] == [] and result['diagnostics']
    assert result['page']['summary'] == 'Supported mechanism, with limits.'


def test_local_resources_cannot_escape_task_through_path_or_symlink(task,tmp_path_factory):
    root,_=task
    outside=tmp_path_factory.mktemp('other')/'private.txt';outside.write_text('PRIVATE-SOURCE')
    (root/'shortcut').symlink_to(outside.parent,target_is_directory=True)
    for path in [str(outside),'../outside.txt','shortcut/private.txt']:
        value=design.resource(root,path)
        assert value['availability']=='unavailable' and 'sha256' not in value


def test_render_binds_preview_and_detects_native_or_image_changes(task):
    root,ws=task
    result=fake_render(ws)
    value=design.context(root,'mechanism',ws.root)['native']
    assert value['preview']['status']=='current'
    assert value['preview']['image_sha256']==sha256(result['pages'][0])
    part=ws.root/value['part'];before=part.read_bytes()
    part.write_bytes(before+b'\n')
    assert design.context(root,'mechanism',ws.root)['native']['preview']['status']=='stale'
    part.write_bytes(before)
    Path(result['pages'][0]).write_bytes(b'CHANGED-PREVIEW')
    assert design.context(root,'mechanism',ws.root)['native']['preview']['status']=='missing_or_changed'


def test_observation_preserves_original_notes_and_never_claims_review_pass(task):
    root,ws=task
    fake_render(ws);before=(root/'source-notes.md').read_bytes()
    result=design.record(root,'mechanism',ws.root,observation(root))
    assert (root/'source-notes.md').read_bytes().startswith(before)
    assert result['independent_review_pass'] is False
    assert result['native_changed_since_previous_observation'] is None
    value=design.context(root,'mechanism',ws.root)['observations'][-1]
    assert value['author_assessment']['preserve']==['Original evidence limits']
    assert value['native']['workspace_fingerprint']==content_fingerprint(manifest(ws.root))
    assert not Path(value['native']['preview']['image']).is_absolute()


def test_observation_can_retain_attempt_and_expose_unchanged_native_inputs(task):
    root,ws=task
    fake_render(ws)
    first=design.record(root,'mechanism',ws.root,observation(root))
    second=design.record(root,'mechanism',ws.root,observation(root,outcome='retained',actual_change='Retained the tested earlier composition.'))
    assert second['native_changed_since_previous_observation'] is False
    row=design.context(root,'mechanism',ws.root)['observations'][-1]
    assert row['previous_observation']==first['id']
    assert row['author_assessment']['outcome']=='retained'


def test_stale_observation_rejection_preserves_notes_and_native_parts(task):
    root,ws=task
    fake_render(ws)
    part=ws.root/'ppt/slides/slide1.xml';part.write_bytes(part.read_bytes()+b'\n')
    notes=(root/'source-notes.md').read_bytes();native=manifest(ws.root)
    with pytest.raises(ValueError,match='current existing render'):
        design.record(root,'mechanism',ws.root,observation(root))
    assert (root/'source-notes.md').read_bytes()==notes
    assert manifest(ws.root)==native


def test_preview_fingerprint_and_relative_paths_survive_relocated_workspace(task):
    root,ws=task
    fake_render(ws)
    copied=root/'restored-task';shutil.copytree(ws.home,copied/'native')
    for name in ['outline.json','source-notes.md']:
        shutil.copyfile(root/name,copied/name)
    state_path=copied/'native/state.json';state=json.loads(state_path.read_text())
    state['workspace']=str(copied/'native/workspace');state_path.write_text(json.dumps(state))
    assert design.context(copied,'mechanism',copied/'native/workspace')['native']['preview']['status']=='current'


def test_full_deck_render_retains_each_actual_page_preview(task):
    root,ws=task
    result=fake_render(ws,None)
    assert result['page_numbers']==[1,2,3]
    for ident in ['mechanism','evidence','closing']:
        assert design.context(root,ident,ws.root)['native']['preview']['status']=='current'
