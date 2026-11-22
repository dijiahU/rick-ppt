import json
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'skills/pptx/scripts'
sys.path.insert(0, str(SCRIPTS))
import deck_style
import native_edit
import native_canvas as canvas


def make_task(tmp_path, style=None):
    (tmp_path / 'request.json').write_text('{}')
    if style is not None:
        (tmp_path / 'deck-style.json').write_text(json.dumps(style))
    ws = tmp_path / 'projects/ws'
    with zipfile.ZipFile(SCRIPTS.parent / 'assets/blank.pptx') as z:
        z.extractall(ws)
    return ws


STYLE = {'register': 'restrained', 'colors': {'background': 'FFFFFF', 'text': '1F2329', 'primary': '1f5fbf'},
         'devices': {'red square': 'starts the key figure', 'hairline': 'separates groups'},
         'type': {'display': 120, 'title': 36, 'body': 20, 'label': 14}}
QUIET = {'ground': '左侧铺一列深蓝色窄栏', 'display': '浅灰章节数字贴着页面右边', 'mark': '页码左边放一个实心蓝点'}


def test_tokens_resolve_from_the_task_root(tmp_path):
    ws = make_task(tmp_path, STYLE)
    style = deck_style.load(ws)
    assert deck_style.resolve('@primary', style) == '1F5FBF'
    assert deck_style.resolve(['@text', 'ABCDEF'], style) == ['1F2329', 'ABCDEF']
    with pytest.raises(ValueError, match='not in deck-style'):
        deck_style.resolve('@accent', style)
    assert deck_style.palette(style) == {'FFFFFF', '1F2329', '1F5FBF'}


def test_invalid_style_and_missing_file(tmp_path):
    ws = make_task(tmp_path)
    assert deck_style.load(ws) is None
    with pytest.raises(ValueError, match='quiet_system.*完整示例'):
        deck_style.load(ws, require_quiet=True)
    with pytest.raises(ValueError, match='needs deck-style.json'):
        deck_style.resolve('@primary', None)
    (tmp_path / 'deck-style.json').write_text(json.dumps({'register': 'loud', 'colors': {'a': 'FFFFFF'}}))
    with pytest.raises(ValueError, match='register'):
        deck_style.load(ws)


@pytest.mark.parametrize('quiet', [None, {}, *[{**QUIET, key: '  短  '} for key in QUIET], {**QUIET, 'mark': 12345678}])
def test_new_style_requires_three_quiet_system_descriptions(tmp_path, quiet):
    style = STYLE if quiet is None else {**STYLE, 'quiet_system': quiet}
    ws = make_task(tmp_path, style)
    assert deck_style.load(ws) == style
    with pytest.raises(ValueError, match='quiet_system') as failure:
        deck_style.load(ws, require_quiet=True)
    example = json.loads(str(failure.value).split('完整示例：', 1)[1])
    assert set(example['quiet_system']) == set(QUIET)
    assert all(len(value) >= 8 for value in example['quiet_system'].values())


@pytest.mark.parametrize('register', ['restrained', 'celebratory'])
def test_new_style_accepts_complete_quiet_system(tmp_path, register):
    ws = make_task(tmp_path, {**STYLE, 'register': register, 'quiet_system': QUIET})
    assert deck_style.load(ws, require_quiet=True)['quiet_system'] == QUIET


def test_edit_accepts_tokens(tmp_path):
    ws = make_task(tmp_path, STYLE)
    canvas.add_shape(ws, 1, [0, 0, 2, 1], geometry='rect', fill='EEEEEE', stroke=None, line_width=1, name='块')
    native_edit.apply(ws, {'slide': 1, 'target': '块', 'fill': '@primary'})
    assert '1F5FBF' in (ws / 'ppt/slides/slide1.xml').read_text()


def test_devices_and_type_scale_are_optional_but_well_formed(tmp_path):
    # 2026-11-21: required counts produced perfunctory entries, so only the shape is checked.
    make_task(tmp_path, {**STYLE, 'type': {'title': 36, 'body': 20, 'figure': 54}})
    assert deck_style.load(tmp_path)['type']['figure'] == 54
    make_task(tmp_path, {k: v for k, v in STYLE.items() if k != 'devices'})
    assert 'devices' not in deck_style.load(tmp_path)
    make_task(tmp_path, {**STYLE, 'devices': ['not', 'a', 'map']})
    with pytest.raises(ValueError, match='devices'):
        deck_style.load(tmp_path)
