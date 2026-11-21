import sys
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

import native_canvas as canvas
import native_edit
import template_fill
from pptx_core.package import unpack


def template(tmp_path):
    """Three-slide template: titled pages, slide 2 with a picture frame."""
    picture = tmp_path / 'sample.png'
    Image.new('RGB', (400, 300), 'red').save(picture)
    prs = Presentation()
    for n in range(3):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = f'模板标题 {n + 1}'
        if n == 1:
            slide.shapes.add_picture(str(picture), Inches(1), Inches(2), Inches(3), Inches(3))
    prs.slides[0].notes_slide.notes_text_frame.text = 'template notes'
    path = tmp_path / 'template.pptx'
    prs.save(path)
    return unpack(path, tmp_path / 'projects').root


def titles(ws):
    return [next(o['text'] for o in s['objects'] if o.get('text')) for s in template_fill.map_slides(ws)]


def test_map_lists_text_and_picture_slots(tmp_path):
    ws = template(tmp_path)
    pages = template_fill.map_slides(ws)
    assert [p['slide'] for p in pages] == [1, 2, 3]
    pictures = [o for o in pages[1]['objects'] if o.get('picture')]
    assert pictures and pictures[0]['pixels'] == [400, 300] and pictures[0]['box'] == [1.0, 2.0, 3.0, 3.0]


def test_select_keeps_order_repeats_layout_and_prunes_parts(tmp_path):
    ws = template(tmp_path)
    result = template_fill.select(ws, [3, 2, 2])
    assert result['slides'] == 3
    assert titles(ws) == ['模板标题 3', '模板标题 2', '模板标题 2']
    # The repeated page is an independent copy.
    native_edit.apply(ws, {'slide': 3, 'target': next(o['id'] for o in template_fill.map_slides(ws)[2]['objects']
                                                        if o.get('text')), 'text': '新内容'})
    assert titles(ws) == ['模板标题 3', '模板标题 2', '新内容']
    # Slide 1 and its notes left the package and its content types.
    live = template_fill._referenced(Path(ws))
    slides = {p for p in live if p.startswith('ppt/slides/slide')}
    assert len(slides) == 3 and not any(p.startswith('ppt/notesSlides') for p in live)
    types = (Path(ws) / '[Content_Types].xml').read_text()
    assert 'notesSlide1.xml' not in types


def picture_crops(ws):
    _, _, tree, _ = canvas.page(ws, 2)
    return [dict(rect.attrib) for rect in tree.iter('{%s}srcRect' % canvas.A)]


@pytest.mark.parametrize('options, expected', [
    ({}, {'l': '33333', 'r': '33333'}),
    ({'focus': [0.5, 0.5]}, {'l': '33333', 'r': '33333'}),
    ({'focus': [0.6, 0.8]}, {'l': '43333', 'r': '23333'}),
    ({'focus': [0, 1]}, {'l': '0', 'r': '66667'}),
])
def test_image_swaps_picture_inside_the_same_frame(tmp_path, options, expected):
    ws = template(tmp_path)
    wide = tmp_path / 'wide.jpg'
    Image.new('RGB', (900, 300), 'blue').save(wide)
    pic = next(o for o in template_fill.map_slides(ws)[1]['objects'] if o.get('picture'))
    result = template_fill.image(ws, 2, pic['id'], wide, **options)
    assert result['box'] == [1.0, 2.0, 3.0, 3.0]
    after = next(o for o in template_fill.map_slides(ws)[1]['objects'] if o.get('picture'))
    assert after['pixels'] == [900, 300]
    assert picture_crops(ws) == [expected]


def test_image_cli_accepts_focus(tmp_path, monkeypatch):
    ws = template(tmp_path)
    tall = tmp_path / 'tall.png'
    Image.new('RGB', (300, 900), 'blue').save(tall)
    pic = next(o for o in template_fill.map_slides(ws)[1]['objects'] if o.get('picture'))
    monkeypatch.setattr(sys, 'argv', ['template_fill.py', 'image', '--workspace', str(ws), '--slide', '2',
                                     '--target', str(pic['id']), '--source', str(tall), '--focus', '0.1', '0.95'])
    template_fill.main()
    assert picture_crops(ws) == [{'t': '66667', 'b': '0'}]


@pytest.mark.parametrize('focus', [[0.5], [0.5, 1.1], [float('nan'), 0], [True, 0]])
def test_invalid_image_focus_leaves_package_untouched(tmp_path, focus):
    ws = template(tmp_path)
    pic = next(o for o in template_fill.map_slides(ws)[1]['objects'] if o.get('picture'))
    before = {p: p.read_bytes() for p in ws.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='coordinates between 0 and 1'):
        template_fill.image(ws, 2, pic['id'], tmp_path / 'sample.png', focus=focus)
    assert {p: p.read_bytes() for p in ws.rglob('*') if p.is_file()} == before
