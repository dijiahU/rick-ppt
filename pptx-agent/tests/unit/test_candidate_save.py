"""Real native packages; only the external renderer is replaced in unit tests."""
import json
from pathlib import Path
import re
from unittest import mock
import zipfile

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
import pytest

import candidate_save as tool
from deck_style import QUIET_EXAMPLE
from pptx_core.common import sha256
from pptx_core.package import unpack
from speaker_notes import set_notes

ENGLISH_SPEECH = ('Today we will look at why the process changed and how the team used the results '
                  'to make a better decision for the next round.')
CHINESE_SPEECH = ('今天我们先来看看这个变化如何影响整个团队，然后一起分析目前观察到的几个结果。'
                  '最后我会解释为什么我们决定调整原来的做法，以及下一次怎样判断调整有没有奏效。')
STYLE = {'register': 'restrained', 'colors': {'background': 'FFFFFF'}, 'quiet_system': QUIET_EXAMPLE}


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


@pytest.fixture
def create_task(task):
    root, ws = task
    (root / 'request.json').write_text(json.dumps({'mode': 'create', 'pages': 3}))
    (root / 'deck-style.json').write_text(json.dumps(STYLE))
    path = root / 'decision-plan.json'
    plan = json.loads(path.read_text())
    plan['task']['operation'] = 'create'
    path.write_text(json.dumps(plan))
    return task


def test_create_requires_quiet_system_before_export(create_task):
    root, _ = create_task
    (root / 'deck-style.json').unlink()
    with mock.patch.object(tool, 'export') as export, pytest.raises(ValueError, match='quiet_system'):
        save(create_task)
    export.assert_not_called()
    assert not (root / 'delivery.json').exists()


@pytest.mark.parametrize('plain,mode,legacy,warning', [
    ([2, 3], 'create', False, [2, 3]),           # consecutive, exactly one quarter
    ([2, 4, 6], 'create', False, [2, 4, 6]),     # over one quarter, no consecutive pages
    ([1, 2, 4, 8], 'create', False, None),       # exact quarter, ignoring both endpoints
    ([2, 3], 'edit', False, None),
    ([2, 3], 'create', True, None),
])
def test_plain_page_warning_on_new_decks_only(tmp_path, plain, mode, legacy, warning):
    pres = Presentation()
    for number in range(1, 9):
        slide = pres.slides.add_slide(pres.slide_layouts[6])
        box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(2))
        run = box.text_frame.paragraphs[0].add_run()
        run.text = f'Page {number}'
        run.font.size = Pt(24 if number in plain else 60)
    source = tmp_path / 'source.pptx'
    pres.save(source)
    ws = unpack(source, base=tmp_path / 'projects')
    (tmp_path / 'request.json').write_text(json.dumps({'mode': mode, 'pages': 8}))
    if mode == 'create':
        for number in range(1, 9):
            set_notes(ws.root, number, ENGLISH_SPEECH)
        if not legacy:
            (tmp_path / 'deck-style.json').write_text(json.dumps(STYLE))
    result = tool.save_candidate(tmp_path, ws.root, 'exports/chosen.pptx', allow_legacy=legacy)
    assert result['ok']
    assert json.loads((tmp_path / 'delivery.json').read_text()) == result['candidate']
    if warning:
        assert result['plain_pages_warning'] == {'pages': warning, 'meaning':
            '这些页只有白底和小字。用 deck-style.json 的 quiet_system 给每页加上第二个面、展示字或标记中的至少一样。'}
    else:
        assert 'plain_pages_warning' not in result


def test_create_reports_every_missing_or_short_script(create_task):
    root, ws = create_task
    set_notes(ws.root, 2, '   ')
    set_notes(ws.root, 3, ENGLISH_SPEECH.rsplit(' ', 1)[0] + '.')
    with pytest.raises(ValueError) as failure:
        save(create_task)
    message = str(failure.value)
    assert '第 1 页（缺少讲稿备注）' in message
    assert '第 2 页（缺少讲稿备注）' in message
    assert '第 3 页（讲稿过短' in message
    assert '备注只写讲者要说的话' in message
    assert '页面上的图注或参考文献页' in message
    assert 'decision-plan.json 或 page-plans.json' in message
    assert not (root / 'delivery.json').exists()


@pytest.mark.parametrize('label', ['来源', '出处', 'Source', 'Sources', 'Credit', 'Photo', '图片来源',
                               '设计参考', 'Design reference', '阅读顺序', 'Reading order', '点击',
                               'Click', '备注', 'Note:', 'TODO'])
def test_create_rejects_non_speech_line_prefixes(create_task, label):
    _, ws = create_task
    set_notes(ws.root, 2, ENGLISH_SPEECH + '\n  ' + label + '：internal text')
    with pytest.raises(ValueError, match=f'第 2 页（含非讲稿行首标签「{label.rstrip(":")}」'):
        save(create_task)


@pytest.mark.parametrize('extra,reason', [
    ('http://example.test/work', '含 HTTP/HTTPS 链接'),
    ('HTTPS://example.test/work', '含 HTTP/HTTPS 链接'),
    ('[PPTX-DESIGN-REFERENCES-BEGIN]', '含 [PPTX- 标记'),
    ('CC BY-SA 4.0', '含许可说明或图库名'), ('CC0', '含许可说明或图库名'),
    ('维基图库Wikimedia提供', '含许可说明或图库名'),
    ('unsplash', '含许可说明或图库名'), ('Pexels', '含许可说明或图库名'),
])
def test_create_rejects_non_speech_inside_a_line(create_task, extra, reason):
    _, ws = create_task
    set_notes(ws.root, 2, ENGLISH_SPEECH + ' ' + extra)
    with pytest.raises(ValueError, match=re.escape(f'第 2 页（{reason}')):
        save(create_task)


def test_create_rejects_embedded_hyperlink_and_label_after_soft_break(create_task):
    from pptx_core.common import NS
    from pptx_core.relationships import rels_part

    _, ws = create_task
    note = set_notes(ws.root, 2, ENGLISH_SPEECH)['notes_part']
    path = ws.root / note
    tree = etree.parse(path)
    run = tree.find('.//a:r', NS)
    etree.SubElement(run.find('a:rPr', NS), '{%s}hlinkClick' % NS['a'], {'{%s}id' % NS['r']: 'rIdLink'})
    run.addnext(etree.Element('{%s}br' % NS['a']))
    label = etree.SubElement(run.getparent(), '{%s}r' % NS['a'])
    etree.SubElement(label, '{%s}t' % NS['a']).text = '来源：附录'
    tree.write(path, encoding='UTF-8')
    path = ws.root / rels_part(note)
    tree = etree.parse(path)
    etree.SubElement(tree.getroot(), '{%s}Relationship' % NS['pr'], Id='rIdLink',
                     Type=NS['r'] + '/hyperlink', Target='https://example.test/work', TargetMode='External')
    tree.write(path, encoding='UTF-8')
    with pytest.raises(ValueError, match='第 2 页（含非讲稿行首标签「来源」、含 HTTP/HTTPS 链接'):
        save(create_task)


def test_create_accepts_chinese_and_english_speech(create_task):
    from native_canvas import add_shape, reveal

    root, ws = create_task
    for number, script in enumerate((ENGLISH_SPEECH, CHINESE_SPEECH, ENGLISH_SPEECH), 1):
        set_notes(ws.root, number, script)
    shape = add_shape(ws.root, 2, (1, 1, 2, 1), geometry='ellipse', fill=None,
                      stroke='202020', line_width=1, name='Result')
    reveal(ws.root, 2, [[shape]])
    path = root / 'decision-plan.json'
    plan = json.loads(path.read_text())
    plan['pages'][1]['behavior'] = 'click_reveal'
    path.write_text(json.dumps(plan))
    result = save(create_task)
    assert result['ok']
    assert json.loads((root / 'delivery.json').read_text()) == result['candidate']


def test_edit_keeps_inherited_notes_and_allows_missing_notes(task):
    _, ws = task
    note = set_notes(ws.root, 2, '来源：https://example.test/work\n[PPTX-OLD]')['notes_part']
    with zipfile.ZipFile(save(task)['candidate']['path']) as archive:
        assert archive.read(note) == (ws.root / note).read_bytes()


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


def test_unshipped_text_fonts_are_listed_and_fallback_rows_ignored(tmp_path):
    path = tmp_path / 'fonts.pptx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('ppt/slides/slide1.xml', '<p:sld xmlns:a="a" xmlns:p="p"><a:rPr><a:latin typeface="思源黑体 CN Heavy"/>'
                         '<a:ea typeface="思源黑体 CN Heavy"/></a:rPr><a:rPr><a:latin typeface="Arial"/><a:ea typeface="+mn-ea"/>'
                         '</a:rPr></p:sld>')
        archive.writestr('ppt/theme/theme1.xml', '<a:theme xmlns:a="a"><a:latin typeface="微软雅黑"/>'
                         '<a:font script="Thai" typeface="Angsana New"/></a:theme>')
    assert tool.unshipped_fonts(path) == {'思源黑体 CN Heavy': 2}


def test_blank_fields_finds_fill_in_lines_but_not_ordinary_text(tmp_path):
    prs = Presentation()
    for body in ('袋价 ______ 元 ÷ 净重 ______ 克', '示例：一袋 180 元、1000 克，单杯 18 克', '姓名（      ）'):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame.text = body
    path = tmp_path / 'blanks.pptx'
    prs.save(path)
    assert tool.blank_fields(path) == [1, 3]
