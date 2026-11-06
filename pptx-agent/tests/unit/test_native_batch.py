import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest import mock
import uuid
import zipfile

import pytest
from PIL import Image

import native_batch as batch
from pptx_core.package import unpack


SCRIPTS = Path(batch.__file__).parent
FONT = next((path for path in [Path('/System/Library/Fonts/Supplemental/Songti.ttc'),
                              Path('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'),
                              Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
                              Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
             if path.is_file()), None)


@pytest.fixture
def fixture(tmp_path):
    source = tmp_path / 'source.pptx'
    shutil.copyfile(SCRIPTS.parent / 'assets/blank.pptx', source)
    ws = unpack(source, tmp_path / 'projects')
    Image.new('RGB', (48, 32), '#123456').save(tmp_path / 'asset.png')
    return tmp_path, ws


def parts(ws):
    return {str(p.relative_to(ws.root)): p.read_bytes() for p in ws.root.rglob('*') if p.is_file()}


def document(*operations, batch_id='test'):
    return {'version': 1, 'batch_id': batch_id, 'operations': list(operations)}


def freeform(**options):
    return {'op': 'path', 'id': 'curve', 'slide': 1, 'box': [1, 1, 4, 2],
            'path_size': [100, 100], 'commands': [['M', 0, 50], ['C', 20, 0, 80, 100, 100, 50]],
            'fill': None, 'stroke': '557799', 'line_width': 2, 'name': 'Feedback loop', **options}


def test_pixel_frame_writes_actual_geometry_preserving_native_groups_timing_and_point_sizes(fixture):
    root, ws = fixture
    doc = document(shape('node', box=[0, 0, 48, 32]),
                   freeform(box=[0, 0, 48, 32], end_arrow='triangle', dash='dash'),
                   {'op': 'group', 'id': 'module', 'slide': 1, 'members': ['node', 'curve'], 'name': 'Module'},
                   {'op': 'reveal', 'slide': 1, 'steps': [['module']]})
    doc['source_frame'] = {'image': 'asset.png', 'box': [1, 1, 6, 6]}
    receipt = batch.run_batch(ws.root, root, doc)
    ns = {'p': batch.canvas.P, 'a': batch.canvas.A}
    tree = batch.canvas.page(ws.root, 1)[2]
    curve = tree.find('.//p:cNvPr[@name="Feedback loop"]', ns).getparent().getparent()
    xf = curve.find('p:spPr/a:xfrm', ns)
    assert {k: int(v) for k, v in xf.find('a:off', ns).attrib.items()} == {'x': 914400, 'y': 1828800}
    assert {k: int(v) for k, v in xf.find('a:ext', ns).attrib.items()} == {'cx': 5486400, 'cy': 3657600}
    assert curve.find('p:spPr/a:ln', ns).get('w') == '25400'  # points, not source pixels
    assert curve.find('.//a:cubicBezTo/a:pt', ns).attrib == {'x': '20000', 'y': '0'}
    assert curve.find('.//a:tailEnd', ns).get('type') == 'triangle'
    assert curve.find('.//a:prstDash', ns).get('val') == 'dash'
    assert tree.find('.//p:spTgt', ns).get('spid') == str(receipt['handles']['module']['shape_id'])
    assert not tree.findall('.//p:pic', ns)  # coordinate source is not embedded
    assert receipt['source_frame']['mapped_box_inches'] == [1, 2, 6, 4]
    assert not receipt['source_frame']['inspection_claimed']
    assert str(root / 'asset.png') in receipt['dependencies']


def test_pixel_frame_keeps_font_points_and_measures_pixel_padding(fixture):
    root, ws = fixture
    doc = document(text(text='Native', x=0, y=0, width=48, max_height=32, size=20, padding=1))
    doc['source_frame'] = {'image': 'asset.png', 'box': [0, 0, 6, 4]}
    receipt = batch.run_batch(ws.root, root, doc)
    value = receipt['text_measurements'][0]
    assert value['size'] == 20 and value['width'] == 6 and value['padding'] == .125
    assert value['requested_height'] == 4
    assert {n.get('sz') for n in batch.canvas.page(ws.root, 1)[2].iter('{'+batch.canvas.A+'}rPr')} == {'2000'}


def test_source_frame_bytes_bind_idempotent_receipt(fixture):
    root, ws = fixture
    doc = document(shape())
    doc['source_frame'] = {'image': 'asset.png', 'box': [0, 0, 6, 4]}
    batch.run_batch(ws.root, root, doc)
    old = parts(ws)
    Image.new('RGB', (48, 32), 'red').save(root / 'asset.png')
    with pytest.raises(ValueError, match='different input or assets'):
        batch.run_batch(ws.root, root, doc)
    assert old == parts(ws)


@pytest.mark.parametrize('options', [
    {'commands': [['L', 0, 0], ['L', 5, 5]]},
    {'commands': [['M', 0, 0], ['Z']]},
    {'commands': [['M', 0, 0], ['Q', 2, 3]]},
    {'commands': [['M', 0, 0], ['L', float('inf'), 5]]},
    {'path_size': [.0001, 100]}, {'dash': 'zigzag'}, {'stroke': None, 'end_arrow': 'triangle'},
])
def test_invalid_freeform_rolls_back_whole_batch(fixture, options):
    root, ws = fixture
    old = parts(ws)
    with pytest.raises((ValueError, batch.BatchError)):
        batch.run_batch(ws.root, root, document(shape(), freeform(**options)))
    assert old == parts(ws)


def test_freeform_polygon_quadratic_and_multiple_subpaths_stay_native(fixture):
    root, ws = fixture
    doc = document(freeform(fill='AABBCC', dash='dot', commands=[['M', 20, 0], ['L', 80, 0],
                    ['L', 100, 100], ['L', 0, 100], ['Z'], ['M', 0, 50], ['Q', 50, 0, 100, 50]]))
    batch.run_batch(ws.root, root, doc)
    ns = {'a': batch.canvas.A, 'p': batch.canvas.P}
    tree = batch.canvas.page(ws.root, 1)[2]
    path = tree.find('.//a:custGeom/a:pathLst/a:path', ns)
    assert path.get('fill') == 'norm'
    assert tree.find('.//a:prstDash', ns).get('val') == 'sysDot'
    assert [node.tag.split('}')[1] for node in path] == ['moveTo', 'lnTo', 'lnTo', 'lnTo', 'close', 'moveTo', 'quadBezTo']
    assert not tree.findall('.//p:pic', ns)


def text(ident='title', **options):
    assert FONT is not None, 'A real system font is required for native text tests'
    return {'op': 'text', 'id': ident, 'slide': 1, 'text': '原生文字 → test',
            'font_file': str(FONT), 'size': 20, 'ink': '112233',
            'x': .4, 'y': .4, 'width': 5, 'max_height': 'auto', **options}


def shape(ident='a', **options):
    return {'op': 'shape', 'id': ident, 'slide': 1, 'box': [1, 2, 2, 1],
            'geometry': 'ellipse', 'fill': 'AABBCC', 'stroke': None,
            'line_width': 1, 'name': ident, **options}


def full_document():
    return document(text(), shape('first'), shape('second', box=[4, 2, 2, 1]),
                    {'op': 'group', 'id': 'pair', 'slide': 1, 'members': ['first', 'second'], 'name': 'Semantic pair'},
                    {'op': 'image', 'id': 'image', 'slide': 1, 'source': 'asset.png',
                     'box': [8, 2, 1, 1], 'fit': 'cover', 'layer': 'front'},
                    {'op': 'connector', 'id': 'link', 'slide': 1, 'start': 'second', 'end': 'image',
                     'points': [6, 2.5, 8, 2.5], 'start_site': 6, 'end_site': 1,
                     'ink': '445566', 'line_width': 1.5, 'arrow': 'triangle', 'name': 'Meaningful connection'},
                    {'op': 'bars', 'id': 'data', 'slide': 1, 'labels': ['前', '后'],
                     'values': [40, 63], 'unit': '示例次数', 'colors': ['557799', 'AA7744'],
                     'box': [1, 4, 5, 2], 'font_family': 'Arial', 'font_size': 18},
                    {'op': 'reveal', 'slide': 1, 'steps': [['pair', 'image', 'link'], ['data']]})


def test_full_batch_preserves_native_group_connections_reveals_and_editable_chart(fixture):
    root, ws = fixture
    old = parts(ws)
    # An existing native notes part must survive the transaction byte for byte.
    note = ws.root / 'ppt/notesSlides/notesSlide99.xml'
    note.parent.mkdir(exist_ok=True)
    note.write_text('<existing-source-notes>保留</existing-source-notes>')
    saved_note = note.read_bytes()
    receipt = batch.run_batch(ws.home, root, full_document())
    handles = receipt['handles']
    tree = batch.canvas.page(ws.root, 1)[2]
    ns = {'p': batch.canvas.P, 'a': batch.canvas.A}
    ids = [node.get('id') for node in tree.findall('.//p:cNvPr', ns)]
    assert len(ids) == len(set(ids))
    pair = tree.find(f'.//p:grpSp/p:nvGrpSpPr/p:cNvPr[@id="{handles["pair"]["shape_id"]}"]', ns).getparent().getparent()
    assert {node.get('id') for node in pair.findall('p:sp/p:nvSpPr/p:cNvPr', ns)} == {
        str(handles['first']['shape_id']), str(handles['second']['shape_id'])}
    assert tree.find('.//a:stCxn', ns).get('id') == str(handles['second']['shape_id'])
    assert tree.find('.//a:endCxn', ns).get('id') == str(handles['image']['shape_id'])
    assert {node.get('spid') for node in tree.findall('.//p:spTgt', ns)} == {
        str(handles[key]['shape_id']) for key in ('pair', 'image', 'link', 'data')}
    assert (ws.root / handles['data']['workbook']).is_file()
    chart = (ws.root / handles['data']['chart']).read_text()
    assert '<c:v>63</c:v>' in chart and '示例次数' in chart
    assert note.read_bytes() == saved_note
    for name, data in old.items():
        if name not in ('ppt/slides/slide1.xml', 'ppt/slides/_rels/slide1.xml.rels', '[Content_Types].xml'):
            assert (ws.root / name).read_bytes() == data
    assert all(handle['workspace'] == str(ws.root) for handle in handles.values())
    assert receipt['render_required'] and not receipt['playback_verified']


def test_all_text_height_errors_are_reported_before_any_mutation(fixture):
    root, ws = fixture
    before, state = parts(ws), ws.state_path.read_bytes()
    with pytest.raises(batch.BatchError) as failure:
        batch.run_batch(ws.root, root, document(shape(), text('one', max_height=.01), text('two', max_height=.02)))
    errors = failure.value.errors
    assert [(error['id'], error['code']) for error in errors] == [('one', 'text_height'), ('two', 'text_height')]
    assert all(error['needs_height'] > error['available_height'] for error in errors)
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    assert not (ws.home / 'native-batches').exists()


@pytest.mark.parametrize('points', [[[3, 2.5], [4, 2.5]], [3, 2.5, 4],
                                   [3, 2.5, 4, float('inf')], [True, 2.5, 4, 2.5]])
def test_bad_connector_points_give_actionable_preflight_without_execution(fixture, points):
    root, ws = fixture
    before, state = parts(ws), ws.state_path.read_bytes()
    edge = {'op': 'connector', 'id': 'edge', 'slide': 1, 'start': 'a', 'end': 'b',
            'points': points, 'start_site': 6, 'end_site': 2, 'ink': '112233',
            'line_width': 1, 'arrow': 'triangle', 'name': 'Connection'}
    with mock.patch.object(batch, '_execute') as execute:
        with pytest.raises(batch.BatchError) as failure:
            batch.run_batch(ws.root, root, document(shape(), shape('b', box=[4, 2, 2, 1]), edge))
        execute.assert_not_called()
    error = failure.value.errors[0]
    assert error['id'] == 'edge' and 'flat [x1, y1, x2, y2]' in error['message']
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    assert not (ws.home / 'native-batches').exists()


@pytest.mark.parametrize('members', [[], ['a'], ['a', 'a']])
def test_degenerate_group_explains_direct_reveal_without_execution(fixture, members):
    root, ws = fixture
    before, state = parts(ws), ws.state_path.read_bytes()
    group = {'op': 'group', 'id': 'unit', 'slide': 1, 'members': members, 'name': 'Unit'}
    with mock.patch.object(batch, '_execute') as execute:
        with pytest.raises(batch.BatchError) as failure:
            batch.run_batch(ws.root, root, document(shape(), group))
        execute.assert_not_called()
    error = failure.value.errors[0]
    assert error['id'] == 'unit' and 'directly in reveal.steps' in error['message']
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    assert not (ws.home / 'native-batches').exists()


def test_auto_height_is_explicit_actual_font_measurement_without_shrinking(fixture):
    root, ws = fixture
    operation = text(text='中文宽度\n第二行', size=24)
    measured = batch.canvas.text_measure(operation['text'], FONT, 24, 5)
    receipt = batch.run_batch(ws.root, root, document(operation))
    assert receipt['text_measurements'][0]['requested_height'] == 'auto'
    assert receipt['handles']['title']['height'] == measured['height']
    tree = batch.canvas.page(ws.root, 1)[2]
    assert {node.get('sz') for node in tree.iter('{'+batch.canvas.A+'}rPr')} == {'2400'}


def test_operation_failure_rolls_back_all_earlier_stage_changes_and_retry_is_clean(fixture):
    root, ws = fixture
    before, state = parts(ws), ws.state_path.read_bytes()
    wrong = document(shape('one'), shape('interloper'), shape('two'),
                     {'op': 'group', 'id': 'group', 'slide': 1, 'members': ['one', 'two'], 'name': 'Not adjacent'})
    with pytest.raises(batch.BatchError, match='adjacent'):
        batch.run_batch(ws.root, root, wrong)
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    correct = document(shape('one'), shape('two'),
                       {'op': 'group', 'id': 'group', 'slide': 1, 'members': ['one', 'two'], 'name': 'Adjacent'})
    receipt = batch.run_batch(ws.root, root, correct)
    assert len({item['shape_id'] for item in receipt['handles'].values()}) == 3


def test_commit_receipt_failure_restores_parts_and_workspace_state(fixture):
    root, ws = fixture
    before, state = parts(ws), ws.state_path.read_bytes()
    with mock.patch.object(batch, '_json_write', side_effect=OSError('simulated receipt disk failure')):
        with pytest.raises(OSError, match='receipt disk failure'):
            batch.run_batch(ws.root, root, full_document())
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    assert not (ws.home / 'native-batches/test.json').exists()


def test_successful_repeat_does_not_append_and_changed_input_is_rejected(fixture):
    root, ws = fixture
    original = document(shape())
    applied = batch.run_batch(ws.root, root, original)
    before = parts(ws)
    again = batch.run_batch(ws.home, root, original)
    assert again['status'] == 'already_applied' and again['handles'] == applied['handles']
    assert parts(ws) == before
    with pytest.raises(ValueError, match='different input'):
        batch.run_batch(ws.root, root, document(shape(fill='112233')))
    assert parts(ws) == before


def test_intervening_parts_change_cannot_reuse_old_success(fixture):
    root, ws = fixture
    original = document(shape())
    batch.run_batch(ws.root, root, original)
    path = ws.root / 'ppt/slides/slide1.xml'
    path.write_bytes(path.read_bytes() + b'\n')
    before = parts(ws)
    with pytest.raises(ValueError, match='native parts changed'):
        batch.run_batch(ws.root, root, original)
    assert parts(ws) == before


def test_check_only_rehearses_every_operation_without_committing_or_receipt(fixture):
    root, ws = fixture
    before, state = parts(ws), ws.state_path.read_bytes()
    receipt = batch.run_batch(ws.root, root, full_document(), check_only=True)
    assert receipt['status'] == 'checked' and len(receipt['results']) == 8
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    assert not (ws.home / 'native-batches').exists()


@pytest.mark.parametrize('operations', [
    lambda: [shape('same'), shape('same')],
    lambda: [shape('one'), {'op': 'group', 'id': 'g', 'slide': 1, 'members': ['one', 'missing'], 'name': 'G'}],
    lambda: [shape('one'), {'op': 'reveal', 'slide': 1, 'steps': [['one'], ['one']]}],
])
def test_bad_or_duplicate_handles_and_repeated_reveal_targets_do_not_change_parts(fixture, operations):
    root, ws = fixture
    before = parts(ws)
    with pytest.raises(batch.BatchError):
        batch.run_batch(ws.root, root, document(*operations()))
    assert parts(ws) == before


def test_multiple_pages_are_rejected_even_if_both_exist(fixture):
    root, ws = fixture
    # Clone the real blank page's OOXML and presentation relationship, without
    # relying on a higher-level PowerPoint authoring library for the fixture.
    canvas = batch.canvas
    presentation = canvas.parse(ws.root / 'ppt/presentation.xml')
    slides = presentation.find('{'+canvas.P+'}sldIdLst')
    second = copy.deepcopy(slides[0])
    second.set('id', str(int(second.get('id')) + 1))
    second.set('{'+canvas.R+'}id', 'rIdSecondPageTest')
    slides.append(second)
    canvas.write(ws.root / 'ppt/presentation.xml', presentation)
    rels = canvas.parse(ws.root / 'ppt/_rels/presentation.xml.rels')
    canvas.node(rels.getroot(), canvas.PKG, 'Relationship', Id='rIdSecondPageTest',
                Type=canvas.R+'/slide', Target='slides/slide2.xml')
    canvas.write(ws.root / 'ppt/_rels/presentation.xml.rels', rels)
    shutil.copyfile(ws.root / 'ppt/slides/slide1.xml', ws.root / 'ppt/slides/slide2.xml')
    before = parts(ws)
    with pytest.raises(batch.BatchError) as error:
        batch.run_batch(ws.root, root, document(shape('a'), shape('b', slide=2)))
    assert any(item['code'] == 'multiple_pages' for item in error.value.errors)
    assert parts(ws) == before


def test_existing_timing_is_preserved_and_failed_new_reveal_does_not_add_text(fixture):
    root, ws = fixture
    batch.run_batch(ws.root, root, document(shape(), {'op': 'reveal', 'slide': 1, 'steps': [['a']]}, batch_id='first'))
    before = parts(ws)
    with pytest.raises(batch.BatchError, match='Existing timing preserved'):
        batch.run_batch(ws.root, root, document(text(), {'op': 'reveal', 'slide': 1, 'steps': [['title']]}, batch_id='second'))
    assert parts(ws) == before


def test_private_font_and_external_or_symlink_image_cannot_escape_scope(fixture, tmp_path_factory):
    root, ws = fixture
    external = tmp_path_factory.mktemp('private')
    shutil.copyfile(FONT, external / 'private.ttf')
    Image.new('RGB', (10, 10)).save(external / 'private.png')
    (root / 'font-link.ttf').symlink_to(external / 'private.ttf')
    (root / 'asset-link.png').symlink_to(external / 'private.png')
    before = parts(ws)
    for file in (str(external / 'private.ttf'), 'font-link.ttf'):
        with pytest.raises(batch.BatchError, match='Fonts must be'):
            batch.run_batch(ws.root, root, document(text(font_file=file)))
    for file in (str(external / 'private.png'), 'asset-link.png'):
        with pytest.raises(batch.BatchError):
            batch.run_batch(ws.root, root, document({'op': 'image', 'id': 'img', 'slide': 1,
                            'source': file, 'box': [1, 1, 2, 2], 'fit': 'contain', 'layer': 'front'}))
    assert parts(ws) == before


def test_task_font_copy_is_allowed_and_dependency_changes_reject_success_reuse(fixture):
    root, ws = fixture
    (root / 'fonts').mkdir()
    shutil.copyfile(FONT, root / 'fonts/selected.ttf')
    source = document(text(font_file='fonts/selected.ttf'))
    batch.run_batch(ws.root, root, source)
    path = root / 'fonts/selected.ttf'
    path.write_bytes(path.read_bytes() + b'\0')
    with pytest.raises(ValueError, match='different input or assets'):
        batch.run_batch(ws.root, root, source)


def test_cli_returns_aggregate_safe_json_and_leaves_original_unchanged(fixture):
    root, ws = fixture
    payload = root / 'batch.json'
    payload.write_text(json.dumps(document(text('one', max_height=.01), text('two', max_height=.01)), ensure_ascii=False))
    before = parts(ws)
    result = subprocess.run([sys.executable, str(SCRIPTS / 'native_batch.py'), '--task-root', str(root),
                             '--workspace', str(ws.root), '--input', str(payload)], capture_output=True, text=True)
    assert result.returncode == 2
    receipt = json.loads(result.stdout)
    assert receipt['status'] == 'rejected' and len(receipt['errors']) == 2
    assert parts(ws) == before


def test_zero_line_width_feedback_preserves_explicit_style_and_parts(fixture):
    root, ws = fixture
    before = parts(ws)
    with pytest.raises(batch.BatchError, match='even with stroke=null'):
        batch.run_batch(ws.root, root, document(shape(stroke=None, line_width=0)))
    assert parts(ws) == before


def test_existing_integer_targets_are_real_same_page_objects(fixture):
    root, ws = fixture
    initial = batch.run_batch(ws.root, root, document(shape(), batch_id='initial'))
    ident = initial['handles']['a']['shape_id']
    result = batch.run_batch(ws.root, root, document({'op': 'reveal', 'slide': 1, 'steps': [[ident]]}, batch_id='timing'))
    assert result['results'][0]['steps'] == [[ident]]
    before = parts(ws)
    with pytest.raises(batch.BatchError, match='exactly one native object'):
        batch.run_batch(ws.root, root, document({'op': 'reveal', 'slide': 1, 'steps': [[999999]]}, batch_id='bad'))
    assert parts(ws) == before


def test_task_font_directory_symlink_cannot_read_private_font(fixture, tmp_path_factory):
    root, ws = fixture
    external = tmp_path_factory.mktemp('private-fonts')
    shutil.copyfile(FONT, external / 'font.ttf')
    (root / 'fonts').symlink_to(external, target_is_directory=True)
    before = parts(ws)
    with pytest.raises(batch.BatchError, match='symlinks'):
        batch.run_batch(ws.root, root, document(text(font_file='fonts/font.ttf')))
    assert parts(ws) == before


def test_string_false_does_not_accidentally_authorize_replacing_existing_timing(fixture):
    root, ws = fixture
    initial = document(shape(), {'op': 'reveal', 'slide': 1, 'steps': [['a']]}, batch_id='initial')
    result = batch.run_batch(ws.root, root, initial)
    before = parts(ws)
    with pytest.raises(batch.BatchError, match='explicit JSON boolean'):
        batch.run_batch(ws.root, root, document({'op': 'reveal', 'slide': 1,
                        'steps': [[result['handles']['a']['shape_id']]], 'replace': 'false'}, batch_id='replace'))
    assert parts(ws) == before


def test_compact_defaults_produce_identical_native_parts_and_preserve_input(fixture):
    root, expanded_ws = fixture
    compact_ws = unpack(root / 'source.pptx', root / 'comparison')
    expanded = full_document()
    compact = copy.deepcopy(expanded)
    compact['defaults'] = {
        'text': {key: expanded['operations'][0][key] for key in ('font_file', 'size', 'ink')},
        'shape': {'fill': 'AABBCC', 'stroke': '112233', 'line_width': 1},
        'connector': {'ink': '445566', 'line_width': 1.5},
        'bars': {'font_family': 'Arial', 'font_size': 18},
    }
    for op in compact['operations']:
        for key, value in compact['defaults'].get(op['op'], {}).items():
            if op.get(key) == value:
                del op[key]
    # Explicit null stroke overrides the reusable color. All coordinates,
    # groups, connector endpoints, editable chart data and reveal targets stay.
    original = copy.deepcopy(compact)
    # Control only generated media/relationship identities. XLSX container
    # timestamps may differ; its actual embedded members must still match.
    def run(ws, doc):
        with mock.patch.object(batch.canvas.uuid, 'uuid4', side_effect=[uuid.UUID(int=n) for n in range(1, 200)]):
            return batch.run_batch(ws.root, root, doc)
    expected = run(expanded_ws, expanded)
    actual = run(compact_ws, compact)
    def content(ws):
        result = parts(ws)
        for name, data in result.items():
            if name.endswith('.xlsx'):
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    result[name] = {key: archive.read(key) for key in archive.namelist()}
        return result
    assert content(compact_ws) == content(expanded_ws)
    assert actual['text_measurements'] == expected['text_measurements']
    assert compact == original
    assert batch.run_batch(compact_ws.root, root, compact)['status'] == 'already_applied'
    changed = copy.deepcopy(compact)
    changed['defaults']['text']['ink'] = '667788'
    with pytest.raises(ValueError, match='different input'):
        batch.run_batch(compact_ws.root, root, changed)


@pytest.mark.parametrize('defaults', [
    None, [], {'text': []}, {'text': {'x': 1}}, {'text': {'max_height': 'auto'}},
    {'text': {'text': 'implicit copy'}}, {'shape': {'geometry': 'rect'}},
    {'image': {'source': 'asset.png'}}, {'reveal': {'replace': True}},
])
def test_defaults_cannot_hide_content_geometry_assets_or_timing(fixture, defaults):
    root, ws = fixture
    before = parts(ws)
    doc = document(shape())
    doc['defaults'] = defaults
    with pytest.raises(batch.BatchError):
        batch.run_batch(ws.root, root, doc)
    assert parts(ws) == before


def test_inherited_font_scope_and_text_height_are_still_checked(fixture, tmp_path_factory):
    root, ws = fixture
    private = tmp_path_factory.mktemp('private-default-font') / 'font.ttf'
    shutil.copyfile(FONT, private)
    operation = text(max_height=.01)
    del operation['font_file']
    doc = document(operation)
    doc['defaults'] = {'text': {'font_file': str(private)}}
    before = parts(ws)
    with pytest.raises(batch.BatchError, match='Fonts must be'):
        batch.run_batch(ws.root, root, doc)
    doc['defaults']['text']['font_file'] = str(FONT)
    with pytest.raises(batch.BatchError, match='Text exceeds'):
        batch.run_batch(ws.root, root, doc)
    assert parts(ws) == before


def test_default_font_dependency_changes_invalidate_success_receipt(fixture):
    root, ws = fixture
    (root / 'fonts').mkdir()
    font = root / 'fonts/selected.ttf'
    shutil.copyfile(FONT, font)
    operation = text()
    del operation['font_file']
    doc = document(operation)
    doc['defaults'] = {'text': {'font_file': 'fonts/selected.ttf'}}
    batch.run_batch(ws.root, root, doc)
    font.write_bytes(font.read_bytes() + b'\0')
    with pytest.raises(ValueError, match='different input or assets'):
        batch.run_batch(ws.root, root, doc)
