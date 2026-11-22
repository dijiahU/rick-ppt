"""Reference provenance stays in the decision plan when cleaning old decks."""
import json

import pytest

import design_references as tool
from pptx_core.package import pack, unpack
from speaker_notes import set_notes
from workflow_decisions import validate_plan


@pytest.fixture
def reference_task(tmp_path, deck):
    ws = unpack(deck, base=tmp_path / 'projects')
    ids = ['opening', 'result', 'closing']
    outline = {'slides': [{'id': ident} for ident in ids]}
    plan = {'version': 4, 'task': {'operation': 'create', 'viewing': 'live', 'research': 'supplied_only'},
            'template_preservation': [], 'design_direction': 'Explain the method and result in order.',
            'references': [{'id': 'R1', 'kind': 'artwork', 'title': 'Study in contrast', 'creator': 'Fixture artist',
                            'source': 'https://museum.example/study', 'inspection': 'hosted_visual',
                            'evidence': 'Inspected the work on the museum page.',
                            'observed': 'One strong focal object.', 'borrowed': 'Contrast in scale.',
                            'applications': [{'pages': ['opening', 'result'], 'action': 'Scale up the focal object.'}]}],
            'pages': [{'id': ident, 'behavior': 'static', 'assets': [{'route': 'none'}]} for ident in ids]}
    (tmp_path / 'decision-plan.json').write_text(json.dumps(plan))
    return ws, plan, outline


def test_authored_decisions_accept_reference_register_without_notes(reference_task, tmp_path):
    ws, plan, outline = reference_task
    artifact = tmp_path / 'authored.pptx'
    pack(ws.root, artifact)
    options = dict(stage='authored', root=tmp_path, artifact=artifact, require_click_reveal=False)
    assert validate_plan(plan, outline, **options)['references_recorded'] == 1
    plan['references'][0]['inspection'] = 'read_text'
    with pytest.raises(ValueError, match='Inspect the actual work'):
        validate_plan(plan, outline, **options)


def test_cleanup_removes_old_blocks_without_adding_reference_notes(reference_task, tmp_path):
    ws, plan, outline = reference_task
    block = f'{tool.BEGIN}\nDesign reference [R1] Study in contrast\n{tool.END}'
    speech = 'Here is the example.\nLet us look at how the result changes.'
    old = speech.replace('\n', f'\n{block}\n') + '\n' + block
    first = ws.root / set_notes(ws.root, 1, old)['notes_part']
    third = ws.root / set_notes(ws.root, 3, block)['notes_part']
    plan_file = tmp_path / 'decision-plan.json'
    registered = plan_file.read_bytes()
    paths = {p for p in ws.root.rglob('*') if p.is_file()}
    untouched = {p: p.read_bytes() for p in paths - {first, third}}

    assert tool.apply(ws.root, plan, outline, root=tmp_path)['pages_updated'] == [1, 3]
    assert {p for p in ws.root.rglob('*') if p.is_file()} == paths
    assert all(p.read_bytes() == body for p, body in untouched.items())
    text = lambda path: '\n'.join(tool.parse(path).xpath('//a:t/text()', namespaces={'a': tool.A}))
    assert text(first) == speech
    assert text(third) == ''
    assert plan_file.read_bytes() == registered
    before = first.read_bytes(), third.read_bytes()
    assert tool.apply(ws.root, plan, outline, root=tmp_path)['pages_updated'] == []
    assert (first.read_bytes(), third.read_bytes()) == before
