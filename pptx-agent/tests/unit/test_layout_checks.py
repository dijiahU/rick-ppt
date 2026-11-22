import sys
from pathlib import Path
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'skills/pptx/scripts'))
import layout_checks as lc

NS = ('xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"')


def sp(name, x, y, cx, cy, text, sz=2400):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="1" name="{name}"/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/>'
            f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:rPr sz="{sz}"/><a:t>{text}</a:t>'
            '</a:r></a:p></p:txBody></p:sp>')


def slide(*shapes):
    return etree.fromstring(f'<p:sld {NS}><p:cSld><p:spTree>{"".join(shapes)}</p:spTree></p:cSld></p:sld>')


SIZE = (12192000, 6858000)


def kinds(*shapes, band=False):
    # Most fixtures are small fragments placed near the top; the empty-band clue has its own test.
    return sorted({i['kind'] for i in lc.check(slide(*shapes), SIZE)
                   if band or i['kind'] not in ('empty_band', 'near_alignment')})


def test_content_stacked_at_the_top_reports_an_empty_band():
    top = [sp('Title', 500000, 400000, 8000000, 900000, '支付失败类工单仍在排查'),
           sp('Body', 500000, 1500000, 8000000, 2000000, '较上周增加 23 单')]
    assert kinds(*top, band=True) == ['empty_band']
    footer = sp('Footer', 500000, 6500000, 3000000, 150000, '小程序产品周报 03/05', sz=900)
    assert kinds(*top, footer, band=True) == ['empty_band', 'small_text']
    assert kinds(*top, sp('Chart', 500000, 3700000, 8000000, 2600000, '工单总量 612 → 502'), band=True) == []


def test_clean_page_has_no_clues():
    assert kinds(sp('Title', 500000, 400000, 8000000, 900000, '丝绸之路'),
                 sp('Body', 500000, 1600000, 8000000, 2000000, '张骞两次出使西域')) == []


def test_off_slide_overlap_small_and_crammed_text_are_reported():
    assert kinds(sp('Wide', 11000000, 400000, 3000000, 900000, '超出右边界的标题')) == ['off_slide']
    assert kinds(sp('A', 500000, 500000, 4000000, 1000000, '第一段文字'),
                 sp('B', 600000, 600000, 4000000, 1000000, '第二段文字')) == ['text_overlap']
    assert kinds(sp('Note', 500000, 500000, 4000000, 1000000, '很小的说明文字', sz=800)) == ['small_text']
    assert kinds(sp('Tight', 500000, 500000, 1000000, 300000, '这是一段很长的正文放在很小的文本框里面' * 3)) == ['text_may_overflow']


def test_cream_background_is_flagged_but_white_and_tints_are_not():
    assert all(lc.is_cream(c) for c in ('F5F3ED', 'FAF7EF', 'FFFFF0', 'F5F5DC'))
    assert not any(lc.is_cream(c) for c in ('FFFFFF', 'F2F2F2', 'DCE4D7', '2B2118', None))
    bg = ('<p:bg><p:bgPr><a:solidFill><a:srgbClr val="F5F3ED"/></a:solidFill></p:bgPr></p:bg>')
    tree = etree.fromstring(f'<p:sld {NS}><p:cSld>{bg}<p:spTree/></p:cSld></p:sld>')
    assert lc.background(tree, SIZE) == 'F5F3ED'
    assert [i['kind'] for i in lc.check(tree, SIZE)] == ['cream_background']


def rect(name, x, y, cx, cy, fill='DCE4D7'):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="9" name="{name}"/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/>'
            f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></p:spPr></p:sp>')


def line(name, x, y, cx):
    return (f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="8" name="{name}"/></p:nvCxnSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/>'
            f'<a:ext cx="{cx}" cy="1"/></a:xfrm><a:prstGeom prst="line"><a:avLst/></a:prstGeom></p:spPr></p:cxnSp>')


def test_plain_page_allows_a_full_background_thin_line_and_small_text():
    rule = rect('Diagonal line', 0, 0, SIZE[0], SIZE[1]).replace('prst="rect"', 'prst="line"')
    assert lc.plain_page(slide(rect('Ground', 0, 0, *SIZE, 'FFFFFF'), rule,
                               sp('Title', 0, 0, 7000000, 700000, '小字标题', sz=5999)), SIZE, 'FFFFFF')


def test_plain_page_uses_six_percent_of_visible_area_and_any_solid_fill_color():
    width, height = SIZE
    block_width = width * 6 // 100
    assert lc.plain_page(slide(rect('Small', 0, 0, block_width - 1, height)), SIZE, 'FFFFFF')
    for fill in ('FFFFFF', '102030'):
        assert not lc.plain_page(slide(rect('Second surface', 0, 0, block_width, height, fill)), SIZE, 'FFFFFF')
    assert not lc.plain_page(slide(rect('Theme color', 0, 0, block_width, height).replace(
        '<a:srgbClr val="DCE4D7"/>', '<a:schemeClr val="accent1"/>')), SIZE, 'FFFFFF')


def test_plain_page_rejects_picture_objects_and_picture_fills():
    fill = '<a:blipFill><a:blip/></a:blipFill>'
    assert not lc.plain_page(slide('<p:pic/>'), SIZE, 'FFFFFF')
    assert not lc.plain_page(slide(f'<p:sp><p:spPr>{fill}</p:spPr></p:sp>'), SIZE, 'FFFFFF')
    assert not lc.plain_page(slide(f'<p:bg><p:bgPr>{fill}</p:bgPr></p:bg>'), SIZE, None)


def test_plain_page_requires_visible_text_at_display_size():
    text = sp('Number', 0, 0, 3000000, 900000, '23', sz=6000)
    assert not lc.plain_page(slide(text), SIZE, 'FFFFFF')
    default = '<a:pPr><a:defRPr sz="6100"/></a:pPr>'
    inherited = text.replace('<a:p>', '<a:p>' + default).replace('<a:rPr sz="6000"/>', '')
    assert not lc.plain_page(slide(inherited), SIZE, 'FFFFFF')
    smaller = text.replace('<a:p>', '<a:p>' + default).replace('sz="6000"', 'sz="2400"')
    assert lc.plain_page(slide(smaller), SIZE, 'FFFFFF')


def test_line_through_text_and_text_across_a_surface_edge():
    label = sp('地名', 2000000, 1000000, 2000000, 800000, '喀什绿洲')
    assert 'line_crosses_text' in kinds(label, line('路线', 0, 1400000, 6000000))
    assert kinds(label, line('路线', 0, 3000000, 6000000)) == []  # clear of the text
    upper, lower = rect('上半', 1000000, 0, 4000000, 1600000), rect('下半', 1000000, 1600000, 4000000, 1600000, '205B4D')
    assert 'text_straddles_edge' in kinds(upper, lower, label)
    assert 'text_straddles_edge' not in kinds(rect('底', 0, 0, 9000000, 5000000), label)  # fully on one surface


def test_groups_are_checked_and_short_units_may_tuck_against_numbers():
    group = (f'<p:grpSp><p:nvGrpSpPr><p:cNvPr id="7" name="组"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>'
             f'<a:off x="0" y="0"/><a:ext cx="6000000" cy="3000000"/><a:chOff x="0" y="0"/><a:chExt cx="6000000" cy="3000000"/>'
             f'</a:xfrm></p:grpSpPr>{sp("地名", 2000000, 1000000, 2000000, 800000, "喀什绿洲")}{line("路线", 0, 1400000, 6000000)}</p:grpSp>')
    assert 'line_crosses_text' in kinds(group)
    assert kinds(sp('数', 500000, 500000, 2000000, 1000000, '+23'), sp('单位', 1500000, 600000, 800000, 800000, '单')) == []


def test_left_edges_that_almost_align_are_reported():
    page = [sp('Fill', 500000, 4000000, 8000000, 2500000, '背景对比 612 → 502')]
    assert kinds(*page, sp('Title', 500000, 400000, 8000000, 900000, '支付失败类工单'),
                 sp('Body', 560000, 1600000, 8000000, 900000, '较上周增加 23 单'), band=True) == ['near_alignment']
    assert kinds(*page, sp('Title', 500000, 400000, 8000000, 900000, '支付失败类工单'),
                 sp('Body', 500000, 1600000, 8000000, 900000, '较上周增加 23 单'), band=True) == []
    # A big number nudged left against its small label is optical alignment, not a slip.
    assert kinds(*page, sp('Big', 450000, 400000, 4000000, 1800000, '+23', sz=13000),
                 sp('Label', 500000, 2300000, 4000000, 600000, '支付失败类工单', sz=1800), band=True) == []


def test_unit_printed_over_a_large_number_is_reported():
    # 126 pt "+23" inks about 3.15 in from its left edge; "单" at 2.98 in sits on the "3".
    number = sp('数', 0, 914400, 3063240, 1197864, '+23', sz=12600)
    over = sp('单位', 2724912, 1500000, 530352, 548640, '单', sz=3100)
    assert 'unit_over_number' in kinds(number, over)
    clear = sp('单位', 3200000, 1500000, 530352, 548640, '单', sz=3100)
    assert 'unit_over_number' not in kinds(number, clear)
    label = sp('标签', 0, 914400, 530352, 548640, '最高', sz=2400)
    assert 'unit_over_number' not in kinds(number, label)


def test_bold_digits_are_wider_and_still_caught():
    # 103 pt bold "+23" (opt9 weekly): "单" at 2.6 in from the box left edge sat on the "3".
    number = sp('数', 0, 914400, 2761488, 1636776, '+23', sz=10300).replace('<a:rPr sz="10300"/>', '<a:rPr sz="10300" b="1"/>')
    unit = sp('单位', 2377440, 1847088, 548640, 512064, '单', sz=3300)
    assert 'unit_over_number' in kinds(number, unit)
    assert 'unit_over_number' not in kinds(number.replace(' b="1"', ''), unit)


def test_paper_and_beige_tones_count_as_cream():
    for colour in ('FAF5EA', 'FFF9EF', 'F1E2CF', 'E9DCC5'):
        assert lc.is_cream(colour), colour
    for colour in ('FFFFFF', 'F4F6F8', 'EEF2F5', 'F0F0F0', '1F2A30'):
        assert not lc.is_cream(colour), colour


def test_candidate_save_cream_exemption_only_from_template_grounds(tmp_path):
    import zipfile
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'skills/pptx/scripts'))
    import candidate_save as cs
    def deck(path, colour):
        rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('ppt/presentation.xml', f'<p:presentation {NS} xmlns:r="{rel}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/></p:presentation>')
            z.writestr('ppt/_rels/presentation.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="x/slide" Target="slides/slide1.xml"/></Relationships>')
            z.writestr('ppt/slides/slide1.xml', f'<p:sld {NS}><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{colour}"/></a:solidFill></p:bgPr></p:bg><p:spTree/></p:cSld></p:sld>')
        return path
    out = deck(tmp_path / 'out.pptx', 'FAF5EA')
    assert [c for _, c in cs.cream_slides(out)] == ['FAF5EA']
    assert cs.template_grounds(tmp_path) == set()
    (tmp_path / 'references/templates').mkdir(parents=True)
    deck(tmp_path / 'references/templates/t1.pptx', 'FAF5EA')
    assert 'FAF5EA' in cs.template_grounds(tmp_path)


def test_surface_audit_finds_cream_panels_tinted_cards_and_muted_palette(tmp_path):
    import zipfile as _zip
    from pptx import Presentation as _P
    from pptx.dml.color import RGBColor
    from pptx.util import Inches as _I
    from layout_checks import surface_audit
    prs = _P()
    for fills in (['FFFCF5'], ['E4EBE1', 'E4EBE1', 'E4EBE1'], ['A8B9A8'], ['C0392B']):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        for i, fill in enumerate(fills):
            box = slide.shapes.add_shape(1, _I(0.5 + i * 3), _I(1), _I(2.8), _I(3))
            box.fill.solid(); box.fill.fore_color.rgb = RGBColor.from_string(fill)
            box.text_frame.text = 'card text'
    path = tmp_path / 'deck.pptx'
    prs.save(path)
    with _zip.ZipFile(path) as archive:
        audit = surface_audit(archive)
    assert [(n, c) for n, c, _ in audit['cream_surfaces']] == [(1, 'FFFCF5')]
    assert audit['card_pages'] == {1: 1, 2: 3}
    assert audit['muted_colours'][:2] == ['E4EBE1', 'A8B9A8']
    assert 0.5 < audit['muted_cool_share'] < 1
