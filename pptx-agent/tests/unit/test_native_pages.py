import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest import mock

from lxml import etree as E
import pytest

import native_pages as pages
from pptx_core.package import unpack
from pptx_core.relationships import relationships, slide_parts


SCRIPTS = Path(pages.__file__).parent


@pytest.fixture
def fixture(tmp_path):
    source = tmp_path / 'source.pptx'
    shutil.copyfile(SCRIPTS.parent / 'assets/blank.pptx', source)
    return tmp_path, unpack(source, tmp_path / 'projects')


def parts(ws):
    return {str(p.relative_to(ws.root)): p.read_bytes() for p in ws.root.rglob('*') if p.is_file()}


def ensure(root, ws, **options):
    return pages.ensure_page(ws.root, root, **{'page': 2, 'key': 'page-2', 'mode': 'blank_from_layout',
                                             'source_slide': 1, **options})


def test_append_preserves_original_layout_master_theme_and_existing_parts(fixture):
    root, ws = fixture
    before, original = parts(ws), (root / 'source.pptx').read_bytes()
    receipt = ensure(root, ws)
    assert receipt['status'] == 'appended' and receipt['page'] == 2
    assert len(slide_parts(ws.root)) == 2
    assert pages._page_layout(ws.root, receipt['identity']['part']) == pages._page_layout(ws.root, 'ppt/slides/slide1.xml')
    for name, data in before.items():
        if name not in ('ppt/presentation.xml', 'ppt/_rels/presentation.xml.rels', '[Content_Types].xml'):
            assert (ws.root / name).read_bytes() == data
    assert (root / 'source.pptx').read_bytes() == original == (ws.home / 'original.pptx').read_bytes()
    assert receipt['render_required'] and not receipt['playback_verified']
    assert not pages.validate(ws.root).errors


def test_repeat_after_authored_content_and_later_page_returns_same_identity(fixture):
    root, ws = fixture
    first = ensure(root, ws)
    part = ws.root / first['identity']['part']
    tree = pages.parse(part)
    tree.set('showMasterSp', '0')
    pages._write(part, tree)
    third = ensure(root, ws, page=3, key='page-3')
    assert third['page'] == 3
    before = parts(ws)
    repeated = ensure(root, ws)
    assert repeated['status'] == 'already_applied' and repeated['identity'] == first['identity']
    assert len(slide_parts(ws.root)) == 3 and parts(ws) == before


def test_existing_page_is_reused_without_clearing_template_content(fixture):
    root, ws = fixture
    tree = pages.parse(ws.root / 'ppt/slides/slide1.xml')
    tree.set('showMasterSp', '0')
    pages._write(ws.root / 'ppt/slides/slide1.xml', tree)
    before, state = parts(ws), ws.state_path.read_bytes()
    receipt = ensure(root, ws, page=1, key='page-1')
    assert receipt['status'] == 'existing' and receipt['identity']['part'] == 'ppt/slides/slide1.xml'
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    assert ensure(root, ws, page=1, key='page-1')['status'] == 'already_applied'


def test_explicit_layout_path_uses_existing_chain(fixture):
    root, ws = fixture
    layout = pages._page_layout(ws.root, 'ppt/slides/slide1.xml')
    receipt = ensure(root, ws, source_slide=None, layout=layout)
    assert receipt['layout'] == layout
    assert relationships(ws.root, receipt['identity']['part'])[0]['resolved'] == layout


def test_source_content_notes_and_timing_are_never_copied(fixture):
    root, ws = fixture
    source = ws.root / 'ppt/slides/slide1.xml'
    tree = pages.parse(source)
    E.SubElement(tree, '{' + pages.P + '}timing')
    common = tree.find('{' + pages.P + '}cSld')
    common.set('name', 'Original page content')
    E.SubElement(common.find('{' + pages.P + '}spTree'), '{' + pages.P + '}sp')
    # Keep this synthetic content test isolated from schema validation; shape
    # completeness is irrelevant to proving the append never copies its tree.
    pages._write(source, tree)
    with mock.patch.object(pages, 'validate') as validate:
        receipt = ensure(root, ws)
    new = pages.parse(ws.root / receipt['identity']['part'])
    assert new.find('{' + pages.P + '}timing') is None
    assert new.find('{' + pages.P + '}cSld').get('name') is None
    assert len(new.find('{' + pages.P + '}cSld/{' + pages.P + '}spTree')) == 2
    assert len(relationships(ws.root, receipt['identity']['part'])) == 1


@pytest.mark.parametrize('options,match', [
    ({'page': 4}, 'next sequential'),
    ({'source_slide': 2}, 'already exist'),
    ({'source_slide': None, 'layout': '../private.xml'}, 'inside'),
    ({'mode': 'clone'}, 'not supported'),
    ({'key': '../escape'}, 'filename-safe'),
    ({'source_slide': None, 'layout': 'ppt/theme/theme1.xml'}, 'slideLayout'),
])
def test_invalid_requests_leave_parts_and_state_untouched(fixture, options, match):
    root, ws = fixture
    before, state = parts(ws), ws.state_path.read_bytes()
    with pytest.raises(ValueError, match=match):
        ensure(root, ws, **options)
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    assert not (ws.home / 'native-pages/page-2.json').exists()


def test_key_collision_and_disappeared_page_never_append_again(fixture):
    root, ws = fixture
    ensure(root, ws)
    before = parts(ws)
    with pytest.raises(ValueError, match='different page request'):
        ensure(root, ws, page=3)
    assert parts(ws) == before
    path = ws.root / 'ppt/presentation.xml'
    pres = pages.parse(path)
    listing = pres.find('{' + pages.P + '}sldIdLst')
    listing.remove(listing[-1])
    pages._write(path, pres)
    before = parts(ws)
    with pytest.raises(ValueError, match='disappeared'):
        ensure(root, ws)
    assert parts(ws) == before and len(slide_parts(ws.root)) == 1


def test_append_allocates_unused_parts_relationships_and_ids(fixture):
    root, ws = fixture
    # Orphan filename is preserved, never overwritten by append.
    (ws.root / 'ppt/slides/slide2.xml').write_bytes((ws.root / 'ppt/slides/slide1.xml').read_bytes())
    # Validation accepts unused parts; reserved file must remain byte-identical.
    before = (ws.root / 'ppt/slides/slide2.xml').read_bytes()
    receipt = ensure(root, ws)
    assert receipt['identity']['part'] == 'ppt/slides/slide3.xml'
    assert (ws.root / 'ppt/slides/slide2.xml').read_bytes() == before
    identities = pages._identities(ws.root)
    assert len({i['slide_id'] for i in identities}) == len(identities)
    assert len({i['relationship_id'] for i in identities}) == len(identities)


@pytest.mark.parametrize('failure_point', ['_append', 'validation', 'refresh', 'receipt'])
def test_failure_rolls_back_parts_state_and_receipt(fixture, failure_point):
    root, ws = fixture
    before, state = parts(ws), ws.state_path.read_bytes()
    if failure_point == 'validation':
        patch = mock.patch.object(pages, 'validate', side_effect=OSError('simulated validation failure'))
    elif failure_point == 'refresh':
        patch = mock.patch('pptx_core.package.Workspace.refresh', side_effect=OSError('simulated refresh failure'))
    else:
        patch = mock.patch.object(pages, '_append' if failure_point == '_append' else '_json_write', side_effect=OSError('simulated failure'))
    with patch, pytest.raises(OSError, match='simulated'):
        ensure(root, ws)
    assert parts(ws) == before and ws.state_path.read_bytes() == state
    assert not (ws.home / 'native-pages/page-2.json').exists()
    assert ensure(root, ws)['status'] == 'appended'


def test_template_layout_cannot_be_changed_on_existing_page(fixture):
    root, ws = fixture
    current = pages._page_layout(ws.root, 'ppt/slides/slide1.xml')
    other = next(p.relative_to(ws.root).as_posix() for p in (ws.root / 'ppt/slideLayouts').glob('*.xml')
                 if p.relative_to(ws.root).as_posix() != current)
    before = parts(ws)
    with pytest.raises(ValueError, match='another layout'):
        ensure(root, ws, page=1, source_slide=None, layout=other)
    assert parts(ws) == before


def test_task_paths_and_layout_symlinks_are_rejected(fixture, tmp_path_factory):
    root, ws = fixture
    elsewhere = tmp_path_factory.mktemp('outside')
    with pytest.raises(ValueError, match='inside the task root'):
        pages.ensure_page(ws.root, elsewhere, page=2, key='x', mode='blank_from_layout', source_slide=1)
    layout = pages._page_layout(ws.root, 'ppt/slides/slide1.xml')
    path = ws.root / layout
    original = path.read_bytes()
    path.unlink()
    (elsewhere / 'layout.xml').write_bytes(original)
    path.symlink_to(elsewhere / 'layout.xml')
    with pytest.raises(ValueError, match='symlink'):
        ensure(root, ws)


def test_cli_returns_receipt_with_current_interpreter(fixture):
    root, ws = fixture
    result = subprocess.run([sys.executable, str(SCRIPTS / 'native_pages.py'), '--task-root', str(root),
                             '--workspace', str(ws.root), '--page', '2', '--source-slide', '1',
                             '--key', 'page-2', '--mode', 'blank_from_layout'], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['status'] == 'appended'
