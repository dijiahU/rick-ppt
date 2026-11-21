import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from lxml import etree

SCRIPTS = Path(__file__).resolve().parents[2] / 'skills/pptx/scripts'
sys.path.insert(0, str(SCRIPTS))
import native_canvas as canvas
import native_edit

P, A = canvas.P, canvas.A


@pytest.fixture()
def workspace(tmp_path):
    ws = tmp_path / 'ws'
    with zipfile.ZipFile(SCRIPTS.parent / 'assets/blank.pptx') as z:
        z.extractall(ws)
    canvas.add_shape(ws, 1, [0, 0, 13.333, 7.5], geometry='rect', fill='29231F', stroke=None, line_width=1, name='底')
    fonts = sorted(Path('/System/Library/Fonts').glob('*.tt[fc]')) + sorted(Path('/Library/Fonts').glob('*.tt[fc]'))
    font = next((f for f in fonts if f.name.startswith(('Times', 'Arial.', 'Helvetica'))), fonts[0])
    canvas.add_text(ws, 1, 'Title', str(font), 40, 'FFFFFF', x=1, y=1, width=6, max_height=2, name='标题')
    return ws


def slide(ws):
    return etree.parse(str(ws / 'ppt/slides/slide1.xml'))


def test_edits_change_only_named_properties(workspace):
    native_edit.apply(workspace, {'slide': 1, 'target': '标题', 'box': [2, 1.5, 7, 2], 'size': 54, 'ink': 'F0BE72', 'text': '丝绸之路\n第二行'})
    native_edit.apply(workspace, {'slide': 1, 'target': '底', 'fill': 'F3F5F6'})
    tree = slide(workspace)
    title = next(sp for sp in tree.iter('{%s}sp' % P) if sp.find('.//{%s}cNvPr' % P).get('name') == '标题')
    off = title.find('.//{%s}off' % A)
    assert (off.get('x'), off.get('y')) == (str(2 * canvas.EMU), str(round(1.5 * canvas.EMU)))
    assert [t.text for t in title.iter('{%s}t' % A)] == ['丝绸之路', '第二行']
    assert {r.get('sz') for r in title.iter('{%s}rPr' % A)} == {'5400'}
    assert {c.get('val') for c in title.iter('{%s}srgbClr' % A)} == {'F0BE72'}
    back = next(sp for sp in tree.iter('{%s}sp' % P) if sp.find('.//{%s}cNvPr' % P).get('name') == '底')
    assert back.find('{%s}spPr/{%s}solidFill/{%s}srgbClr' % (P, A, A)).get('val') == 'F3F5F6'


@pytest.fixture()
def styled_text(workspace):
    path = workspace / 'ppt/slides/slide1.xml'
    tree = slide(workspace)
    body = next(tree.iter('{%s}txBody' % P))
    for p in list(body.iterchildren('{%s}p' % A)):
        body.remove(p)
    for align, size, weights in (('ctr', 4000, (1, 0)), ('l', 1800, (0,))):
        p = canvas.node(body, A, 'p')
        canvas.node(p, A, 'pPr', algn=align)
        for bold in weights:
            r = canvas.node(p, A, 'r')
            canvas.node(r, A, 'rPr', sz=size, b=bold)
            canvas.node(r, A, 't').text = '样例'
    canvas.write(path, tree)
    return workspace


@pytest.mark.parametrize('text, expected', [
    ('标题', [('ctr', [('标题', '4000', '1')])]),
    ('标题\n副题', [('ctr', [('标题', '4000', '1')]), ('l', [('副题', '1800', '0')])]),
    ('标题\n副题\n注释', [('ctr', [('标题', '4000', '1')]), ('l', [('副题', '1800', '0')]),
                          ('l', [('注释', '1800', '0')])]),
    ([['4.6', '%', ' YoY'], ['注册转化率']], [('ctr', [('4.6', '4000', '1'), ('%', '4000', '0'), (' YoY', '4000', '0')]),
                                         ('l', [('注册转化率', '1800', '0')])]),
    ([[], ['副题']], [('ctr', []), ('l', [('副题', '1800', '0')])]),
])
def test_text_preserves_paragraph_and_run_styles(styled_text, text, expected):
    native_edit.apply(styled_text, {'slide': 1, 'target': '标题', 'text': text})
    body = next(slide(styled_text).iter('{%s}txBody' % P))
    actual = []
    for p in body.findall('{%s}p' % A):
        runs = []
        for r in p.findall('{%s}r' % A):
            rpr = r.find('{%s}rPr' % A)
            runs.append((r.find('{%s}t' % A).text, rpr.get('sz'), rpr.get('b')))
        actual.append((p.find('{%s}pPr' % A).get('algn'), runs))
    assert actual == expected


def test_text_into_empty_spacer_paragraph_borrows_nearest_style(styled_text):
    path = styled_text / 'ppt/slides/slide1.xml'
    tree = slide(styled_text)
    body = next(tree.iter('{%s}txBody' % P))
    spacer = canvas.E.Element('{%s}p' % A)
    canvas.node(spacer, A, 'pPr', algn='r')
    body.insert(list(body).index(body.findall('{%s}p' % A)[1]), spacer)
    canvas.write(path, tree)
    native_edit.apply(styled_text, {'slide': 1, 'target': '标题', 'text': '标题\n空行\n副题'})
    ps = next(slide(styled_text).iter('{%s}txBody' % P)).findall('{%s}p' % A)
    rpr = ps[1].find('{%s}r/{%s}rPr' % (A, A))
    assert ps[1].find('{%s}pPr' % A).get('algn') == 'r' and rpr is not None and rpr.get('sz') == '4000'


@pytest.mark.parametrize('text', [[], ['标题'], [[4.6]]])
def test_invalid_nested_text_leaves_text_untouched(styled_text, text):
    path = styled_text / 'ppt/slides/slide1.xml'
    before = path.read_bytes()
    with pytest.raises(ValueError, match='string runs'):
        native_edit.apply(styled_text, {'slide': 1, 'target': '标题', 'text': text})
    assert path.read_bytes() == before


def test_delete_and_clear_errors(workspace):
    native_edit.apply(workspace, {'slide': 1, 'target': '底', 'delete': True})
    assert '底' not in [n.get('name') for n in slide(workspace).iter('{%s}cNvPr' % P)]
    with pytest.raises(ValueError, match='No object named'):
        native_edit.apply(workspace, {'slide': 1, 'target': '不存在', 'size': 20})
    with pytest.raises(ValueError, match='slide and target'):
        native_edit.apply(workspace, {'slide': 1, 'target': '标题', 'colour': 'FFFFFF'})


def test_poster_properties(workspace, tmp_path):
    from PIL import Image
    Image.new('RGB', (400, 300), 'red').save(tmp_path / 'p.png')
    pic = canvas.add_image(workspace, 1, str(tmp_path / 'p.png'), [8, 1, 4, 3], fit='cover', layer='front', task_root=tmp_path)
    native_edit.apply(workspace, {'slide': 1, 'target': '标题', 'rotate': -90, 'vertical': True, 'tracking': -2, 'leading': 0.9})
    native_edit.apply(workspace, {'slide': 1, 'target': pic['shape_id'], 'shape': 'ellipse', 'opacity': 0.5})
    native_edit.apply(workspace, {'slide': 1, 'target': '底', 'gradient': {'from': '000000', 'to': '000000',
                                                                         'from_opacity': 0.8, 'to_opacity': 0, 'angle': 0}})
    tree = slide(workspace)
    title = next(sp for sp in tree.iter('{%s}sp' % P) if sp.find('.//{%s}cNvPr' % P).get('name') == '标题')
    assert title.find('.//{%s}xfrm' % A).get('rot') == str(270 * 60000)
    assert title.find('.//{%s}bodyPr' % A).get('vert') == 'eaVert'
    assert {r.get('spc') for r in title.iter('{%s}rPr' % A)} == {'-200'}
    assert title.find('.//{%s}lnSpc/{%s}spcPct' % (A, A)).get('val') == '90000'
    picture = next(tree.iter('{%s}pic' % P))
    assert picture.find('.//{%s}prstGeom' % A).get('prst') == 'ellipse'
    assert picture.find('.//{%s}alphaModFix' % A).get('amt') == '50000'
    back = next(sp for sp in tree.iter('{%s}sp' % P) if sp.find('.//{%s}cNvPr' % P).get('name') == '底')
    stops = back.findall('.//{%s}gs/{%s}srgbClr/{%s}alpha' % (A, A, A))
    assert [s.get('val') for s in stops] == ['80000', '0']
    assert back.find('{%s}spPr/{%s}solidFill' % (P, A)) is None
    with pytest.raises(ValueError, match='shape applies to pictures'):
        native_edit.apply(workspace, {'slide': 1, 'target': '底', 'shape': 'ellipse'})


def children(el):
    return [c.tag.split('}')[-1] for c in el]


def test_fills_and_effects_follow_schema_order(workspace, tmp_path):
    """Template objects carry ln/effectLst/extLst; new children must keep ECMA-376 order."""
    from PIL import Image
    Image.new('RGB', (40, 30), 'red').save(tmp_path / 'p.png')
    pic = canvas.add_image(workspace, 1, str(tmp_path / 'p.png'), [8, 1, 4, 3], fit='cover', layer='front', task_root=tmp_path)
    path = workspace / 'ppt/slides/slide1.xml'
    tree = canvas.parse(path)
    back = next(sp for sp in tree.iter('{%s}sp' % P) if sp.find('.//{%s}cNvPr' % P).get('name') == '底')
    sppr = back.find('{%s}spPr' % P)
    sppr.remove(sppr.find('{%s}ln' % A))
    canvas.node(sppr, A, 'effectLst')
    canvas.node(next(tree.iter('{%s}blip' % A)), A, 'extLst')
    for rpr in native_edit._runs(tree.getroot()):
        rpr.insert(0, etree.Element('{%s}ln' % A))
    canvas.write(path, tree)

    native_edit.apply(workspace, {'slide': 1, 'target': '底', 'fill': '112233'})
    assert children(slide(workspace).find('.//{%s}sp/{%s}spPr' % (P, P)))[-2:] == ['solidFill', 'effectLst']
    native_edit.apply(workspace, {'slide': 1, 'target': '底', 'gradient': {'from': '000000', 'to': 'FFFFFF'}})
    native_edit.apply(workspace, {'slide': 1, 'target': '标题', 'ink': 'F0BE72'})
    native_edit.apply(workspace, {'slide': 1, 'target': pic['shape_id'], 'opacity': 0.5})
    native_edit.apply(workspace, {'slide': 1, 'target': pic['shape_id'], 'opacity': 0.4})
    tree = slide(workspace)
    assert children(tree.find('.//{%s}sp/{%s}spPr' % (P, P)))[-2:] == ['gradFill', 'effectLst']
    for rpr in native_edit._runs(tree.getroot()):
        assert children(rpr)[:2] == ['ln', 'solidFill'] and children(rpr).index('solidFill') < children(rpr).index('latin')
    assert children(next(tree.iter('{%s}blip' % A))) == ['alphaModFix', 'extLst']


def test_cjk_wrapping_keeps_numbers_whole_and_no_xml_space(workspace):
    cache = Path(__file__).resolve().parents[3] / 'runner/font-cache.local/fonts'
    font = next(iter(sorted(cache.glob('simsun-regular-*.ttf'))), Path('missing'))
    if not Path(font).is_file():
        pytest.skip('SimSun cache not present')
    lines = canvas.text_measure('公元前2024年出使西域12.5%', font, 24, 1.3)['lines']
    assert '2024年' in lines and all('202' not in l or '2024' in l for l in lines)
    canvas.add_text(workspace, 1, ' 前后有空格 ', font, 20, '000000', x=1, y=4, width=4, max_height=1, name='空格')
    assert 'xml:space' not in (workspace / 'ppt/slides/slide1.xml').read_text()


def test_crop_trims_a_picture(workspace, tmp_path):
    from PIL import Image
    Image.new('RGB', (400, 300), 'red').save(tmp_path / 'c.png')
    pic = canvas.add_image(workspace, 1, str(tmp_path / 'c.png'), [1, 1, 4, 3], fit='contain', layer='front', task_root=tmp_path)
    native_edit.apply(workspace, {'slide': 1, 'target': pic['shape_id'], 'crop': [0.1, 0.2, 0.3, 0]})
    rect = next(slide(workspace).iter('{%s}pic' % P)).find('.//{%s}srcRect' % A)
    assert (rect.get('l'), rect.get('t'), rect.get('r'), rect.get('b')) == ('10000', '20000', '30000', None)
    with pytest.raises(ValueError, match='crop applies to pictures'):
        native_edit.apply(workspace, {'slide': 1, 'target': pic['shape_id'], 'crop': [0.6, 0, 0.5, 0]})


@pytest.mark.parametrize('props, expected', [
    ({'focus': [0.6, 0.8]}, {'l': '43333', 'r': '23333'}),
    ({'box': [1, 1, 6, 3], 'focus': [0.6, 0.8]}, {'l': '26667', 'r': '6667'}),
    ({'box': [1, 1, 6, 3]}, {'l': '16667', 'r': '16667'}),
])
def test_edit_picture_cover_focus(workspace, tmp_path, props, expected):
    from PIL import Image
    path = tmp_path / 'wide.png'
    Image.new('RGB', (900, 300), 'red').save(path)
    pic = canvas.add_image(workspace, 1, str(path), [1, 1, 3, 3], fit='cover', layer='front', task_root=tmp_path)
    result = native_edit.apply(workspace, {'slide': 1, 'target': pic['shape_id'], **props})
    assert result['changed'] == list(props)
    rects = next(slide(workspace).iter('{%s}pic' % P)).findall('.//{%s}srcRect' % A)
    assert len(rects) == 1 and rects[0].attrib == expected


def test_focus_requires_picture(workspace):
    with pytest.raises(ValueError, match='focus applies to pictures'):
        native_edit.apply(workspace, {'slide': 1, 'target': '标题', 'focus': [0.5, 0.5]})
