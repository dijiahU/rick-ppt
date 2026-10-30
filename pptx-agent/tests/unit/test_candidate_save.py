"""Real native packages; only the external renderer is replaced in unit tests."""
import json
from pathlib import Path
from unittest import mock
import zipfile

from lxml import etree
from PIL import Image
import pytest

import candidate_save as tool
from pptx_core.common import sha256
from pptx_core.package import unpack


@pytest.fixture
def task(tmp_path, deck):
    root = tmp_path.resolve()
    ws = unpack(deck, base=root / 'projects')
    slides = [{'id': f'p{n}', 'title': f'Page {n}', 'summary': 'Preserve the source.'} for n in range(1, 4)]
    (root / 'request.json').write_text(json.dumps({'mode': 'edit', 'pages': 3}))
    (root / 'outline.json').write_text(json.dumps({'title': 'Native source', 'purpose': 'Scoped edit', 'slides': slides}))
    (root / 'decision-plan.json').write_text(json.dumps({
        'version': 4, 'task': {'operation': 'edit', 'viewing': 'live', 'research': 'supplied_only'},
        'template_preservation': ['Preserve source parts and native objects.'],
        'design_direction': 'Preserve source.', 'references': [],
        'pages': [{'id': x['id'], 'behavior': 'static', 'assets': [{'route': 'none'}]} for x in slides]}))
    return root, ws


@pytest.fixture(autouse=True)
def conversion(monkeypatch):
    def render(source, directory, **kwargs):
        directory = Path(directory) / ('offline-' + sha256(source)[:12])
        directory.mkdir(parents=True, exist_ok=True)
        pages = []
        for n in range(1, kwargs.get('expected_pages', 3) + 1):
            path = directory / f'page-{n}.png'
            Image.new('RGB', (96, 54), 'white').save(path)
            pages.append(str(path))
        return {'ok': True, 'pages': pages, 'source_hash': sha256(source)}
    monkeypatch.setattr('pptx_core.renderer.render_package', render)


def save(task):
    root, ws = task
    return tool.save_candidate(root, ws.root, 'exports/chosen.pptx')


def test_completed_native_edit_refreshes_declaration_and_keeps_old_export(task):
    root, ws = task
    original = (ws.home / 'original.pptx').read_bytes()
    first = save(task)
    old = Path(first['candidate']['path']).read_bytes()
    part = ws.root / 'ppt/slides/slide3.xml'
    tree = etree.fromstring(part.read_bytes())
    tree.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}t').text = 'A finished scoped correction'
    part.write_bytes(etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True))
    second = save(task)
    assert second['candidate']['path'] != first['candidate']['path']
    assert second['sha256'] != first['sha256']
    assert Path(first['candidate']['path']).read_bytes() == old
    assert json.loads((root / 'delivery.json').read_text()) == second['candidate']
    assert second['authored']['stage'] == 'authored'
    assert second['native_render']['source_hash'] == second['sha256']
    assert (ws.home / 'original.pptx').read_bytes() == original
    with zipfile.ZipFile(first['candidate']['path']) as before, zipfile.ZipFile(second['candidate']['path']) as after:
        assert before.read('ppt/slides/slide1.xml') == after.read('ppt/slides/slide1.xml')
        assert before.read('ppt/slides/slide2.xml') == after.read('ppt/slides/slide2.xml')
        assert before.read('ppt/slides/slide3.xml') != after.read('ppt/slides/slide3.xml')


@pytest.mark.parametrize('failure', ['render', 'authored', 'declaration', 'page_count'])
def test_failed_save_keeps_prior_declared_bytes_and_immutable_candidate(task, failure):
    root, ws = task
    first = save(task)
    declaration = (root / 'delivery.json').read_bytes()
    original = Path(first['candidate']['path']).read_bytes()
    if failure == 'authored':
        plan = json.loads((root / 'decision-plan.json').read_text())
        plan['pages'][0]['behavior'] = 'not_a_real_behavior'
        (root / 'decision-plan.json').write_text(json.dumps(plan))
    if failure == 'page_count':
        (root / 'request.json').write_text(json.dumps({'mode': 'edit', 'pages': 2}))
    patch = (mock.patch('pptx_core.renderer.render_package', side_effect=RuntimeError('conversion failed'))
             if failure == 'render' else mock.patch.object(tool, '_declare', side_effect=OSError('disk failed'))
             if failure == 'declaration' else mock.patch.object(tool, 'sha256', wraps=tool.sha256))
    with patch, pytest.raises((ValueError, RuntimeError, OSError)):
        save(task)
    assert (root / 'delivery.json').read_bytes() == declaration
    assert Path(first['candidate']['path']).read_bytes() == original
    assert not list(root.glob('.delivery-*.json'))


@pytest.mark.parametrize('where', ['output', 'workspace', 'declaration'])
def test_task_paths_cannot_follow_symlinks_or_escape(task, where):
    root, ws = task
    first = save(task)
    old = Path(first['candidate']['path']).read_bytes()
    output, workspace = 'exports/next.pptx', ws.root
    if where == 'output':
        (root / 'escape').symlink_to(root.parent, target_is_directory=True)
        output = 'escape/outside.pptx'
    elif where == 'workspace':
        (root / 'alias').symlink_to(ws.root, target_is_directory=True)
        workspace = root / 'alias'
    else:
        (root / 'delivery.json').unlink()
        (root / 'delivery.json').symlink_to(Path(first['candidate']['path']))
    with pytest.raises(ValueError, match='symlink'):
        tool.save_candidate(root, workspace, output)
    assert Path(first['candidate']['path']).read_bytes() == old


def test_concurrent_declaration_change_is_preserved(task):
    root, ws = task
    save(task)
    original_export = tool.export
    other = b'{"path":"other-author-declared.pptx"}\n'
    def changed(*args):
        result = original_export(*args)
        (root / 'delivery.json').write_bytes(other)
        return result
    with mock.patch.object(tool, 'export', side_effect=changed), pytest.raises(ValueError, match='changed while'):
        save(task)
    assert (root / 'delivery.json').read_bytes() == other
