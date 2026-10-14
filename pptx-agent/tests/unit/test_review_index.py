import json
from pathlib import Path

import pytest
from PIL import Image

from pptx_core.common import PptxError, sha256
from review_index import write_review_index


def evidence(tmp_path, *, steps=None, frames=None):
    packet = tmp_path / 'packet'; packet.mkdir()
    final = tmp_path / 'original-render.png'
    Image.new('RGB', (1280, 720), '#336699').save(final)
    Image.new('RGB', (900, 506), '#336699').save(packet / 'reading-page-1.png')
    Image.new('RGB', (1260, 260), 'white').save(packet / 'contact-1.jpg')
    shapes = [
        {'id': '10', 'name': 'Native group', 'kind': 'grpSp', 'group_id': None,
         'text': '示例（非通用收益）', 'explicit_font_points': [24], 'connections': []},
        {'id': '11', 'name': 'Grouped child', 'kind': 'sp', 'group_id': '10',
         'text': 'A → B', 'explicit_font_points': [18], 'connections': [],
         'bounds_in_parent_emu': [0, 0, 914400, 914400]},
        {'id': '12', 'name': 'Second reveal', 'kind': 'sp', 'group_id': None,
         'text': '10 ms\n单位与范围', 'explicit_font_points': [18], 'connections': []},
        {'id': '13', 'name': 'Persistent connector', 'kind': 'cxnSp', 'group_id': None,
         'text': '', 'explicit_font_points': [],
         'connections': [{'end': 'stCxn', 'id': '11', 'idx': '0'},
                         {'end': 'endCxn', 'id': '12', 'idx': '1'}]},
    ]
    for frame in frames or []:
        Image.new('RGB', (1280, 720), '#abcdef').save(packet / frame['file'])
    inventory = {'slides': [{'page': 1, 'part': 'ppt/slides/slide1.xml',
        'text': '示例（非通用收益）\nA → B\n10 ms\n单位与范围', 'shapes': shapes,
        'effect_nodes': [{'nodeType': 'clickEffect'}], 'timing_targets': ['10', '12'],
        'reading_preview': {'file': 'reading-page-1.png'}}],
        'contact_sheets': ['contact-1.jpg'],
        'static_states': {'frames': frames or [], 'unsupported_pages': [1] if steps is None else []},
        'design_references': {'rationale': 'PRIVATE_AUTHOR_RECORD'},
        'audience_notes': 'PRIVATE_AUTHOR_NOTES'}
    (packet / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False))
    return packet, final, inventory


def test_exact_reading_receipts_native_groups_and_no_author_leak(tmp_path):
    frames = [{'page': 1, 'after_clicks': n, 'total_clicks': 2,
               'file': f'state-page-1-after-{n}.png'} for n in (0, 1)]
    packet, final, inventory = evidence(tmp_path, steps=[['10'], ['12']], frames=frames)
    raw = (packet / 'inventory.json').read_bytes(); before = final.read_bytes()
    index = write_review_index(inventory, {'pages': [str(final)]}, packet, [[['10'], ['12']]])
    assert index['reading_pages'][0]['width'] == 900
    assert index['reading_pages'][0]['sha256'] == sha256(packet / 'reading-page-1.png')
    assert index['full_pages'][0]['location'] == 'reviewer_root'
    assert index['full_pages'][0]['sha256'] == sha256(final)
    assert index['slides'][0]['native_reveal']['initially_visible_ids'] == ['13']
    assert index['slides'][0]['native_reveal']['click_groups'][1] == {'after_clicks': 2, 'target_ids': ['12']}
    assert len(index['state_contacts']) == 1
    assert [p['kind'] for p in index['state_contacts'][0]['panels']] == ['static_simulation', 'static_simulation', 'final']
    assert index['slides'][0]['text'] == inventory['slides'][0]['text']
    objects = json.loads((packet / 'review-objects.json').read_text())
    assert objects['slides'][0]['objects'][1]['bounds_in_parent_emu'] == [0, 0, 914400, 914400]
    assert objects['slides'][0]['objects'][3]['connections'][1]['id'] == '12'
    assert 'PRIVATE_AUTHOR' not in json.dumps(index) + json.dumps(objects)
    assert not index['powerpoint_playback_verified']
    assert (packet / 'inventory.json').read_bytes() == raw and final.read_bytes() == before


def test_unknown_timing_has_no_fabricated_click_states(tmp_path):
    packet, final, inventory = evidence(tmp_path)
    index = write_review_index(inventory, {'pages': [str(final)]}, packet, [None])
    reveal = index['slides'][0]['native_reveal']
    assert reveal['support'] == 'unsupported'
    assert reveal['initially_visible_ids'] is None and reveal['click_groups'] is None
    assert index['state_frames'] == []
    assert index['state_contacts'][0]['panels'][0]['kind'] == 'final'
    assert index['static_state_limitations']['unsupported_pages'] == [1]


def test_static_deck_and_failed_state_render_remain_factual(tmp_path):
    packet, final, inventory = evidence(tmp_path, steps=[])
    inventory['static_states']['error'] = 'RenderFailure'
    index = write_review_index(inventory, {'pages': [str(final)]}, packet, [[]])
    assert index['slides'][0]['native_reveal']['support'] == 'static'
    assert index['slides'][0]['native_reveal']['state_render_error'] == 'RenderFailure'
    assert index['state_frames'] == index['state_contacts'] == []


def test_state_evidence_must_match_actual_native_steps(tmp_path):
    frames = [{'page': 1, 'after_clicks': 3, 'total_clicks': 3, 'file': 'state.png'}]
    packet, final, inventory = evidence(tmp_path, steps=[['10']], frames=frames)
    with pytest.raises(PptxError, match='does not match'):
        write_review_index(inventory, {'pages': [str(final)]}, packet, [[['10']]])


@pytest.mark.parametrize('escape', ['../original-render.png', '/tmp/outside.png'])
def test_packet_paths_cannot_escape(tmp_path, escape):
    packet, final, inventory = evidence(tmp_path, steps=[])
    inventory['slides'][0]['reading_preview']['file'] = escape
    with pytest.raises(PptxError, match='stay inside'):
        write_review_index(inventory, {'pages': [str(final)]}, packet, [[]])


def test_collect_creates_900px_portrait_index_without_mutating_source(tmp_path, monkeypatch):
    import review_packet
    from pptx_core.package import unpack
    from native_canvas import add_shape, reveal
    ws = unpack(Path(__file__).resolve().parents[2] / 'skills/pptx/assets/blank.pptx', tmp_path / 'workspaces')
    handles = [add_shape(ws.root, 1, (x, 1, 1, 1), geometry='ellipse', fill=None,
                         stroke='202020', line_width=1, name=f'Group{x}') for x in (1, 3)]
    reveal(ws.root, 1, [[handles[0]], [handles[1]]])
    source = {str(p.relative_to(ws.root)): p.read_bytes() for p in ws.root.rglob('*') if p.is_file()}
    final = tmp_path / 'portrait.png'; Image.new('RGB', (720, 1280), 'white').save(final)
    def fake_render(package, destination, expected_pages):
        directory = Path(destination); directory.mkdir(parents=True)
        png = directory / 'state.png'; Image.new('RGB', (720, 1280), '#336699').save(png)
        return {'pages': [str(png)]}
    monkeypatch.setattr(review_packet, 'render_package', fake_render)
    packet = tmp_path / 'packet'
    result = review_packet.collect(ws.root, {'pages': [str(final)]}, packet)
    assert len(result['slides']) == 1 and 'shapes' in result['slides'][0]
    index = json.loads((packet / 'review-index.json').read_text())
    assert (index['reading_pages'][0]['width'], index['reading_pages'][0]['height']) == (900, 1600)
    assert len(index['state_frames']) == 2 and len(index['state_contacts']) == 1
    assert source == {str(p.relative_to(ws.root)): p.read_bytes() for p in ws.root.rglob('*') if p.is_file()}
