from lxml import etree

from pptx_core.common import P, PptxError, parse
import pytest
from pptx_core.relationships import slide_parts
from pptx_core.validator import duplicate_shape_ids, validate


def test_sections_do_not_create_phantom_slides(ws):
    path = ws.root / "ppt/presentation.xml"
    path.write_text(path.read_text().replace("</p:presentation>", '<p:extLst><p:ext uri="section"><p14:sectionLst xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main"><p14:section><p14:sldIdLst><p14:sldId id="256"/></p14:sldIdLst></p14:section></p14:sectionLst></p:ext></p:extLst></p:presentation>'))
    assert len(slide_parts(ws.root)) == 3
    assert validate(ws.root).ok


def test_uppercase_media_extension(ws):
    root = ws.root
    (root / "ppt/media/image1.png").rename(root / "ppt/media/image1.PNG")
    for path in root.rglob("*.rels"):
        path.write_text(path.read_text().replace("image1.png", "image1.PNG"))
    assert validate(root).ok


def test_ole_preview_ids_and_mutually_exclusive_fallback():
    tree = etree.fromstring(f'<p:sld xmlns:p="{P}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"><p:spTree><p:sp><p:cNvPr id="1"/></p:sp><p:oleObj><p:pic><p:cNvPr id="0"/></p:pic></p:oleObj><p:oleObj><p:pic><p:cNvPr id="0"/></p:pic></p:oleObj><mc:AlternateContent><mc:Choice Requires="p"><p:pic><p:cNvPr id="2"/></p:pic></mc:Choice><mc:Fallback><p:pic><p:cNvPr id="2"/></p:pic></mc:Fallback></mc:AlternateContent></p:spTree></p:sld>')
    assert not duplicate_shape_ids(tree)
    etree.SubElement(tree, f"{{{P}}}cNvPr", id="1")
    assert duplicate_shape_ids(tree)


def test_slide_must_have_slide_root(ws):
    (ws.root / "ppt/slides/slide1.xml").write_text("<not-a-slide/>")
    report = validate(ws.root)
    assert not report.ok
    assert any("root namespace" in error for error in report.errors)


def test_layout_relationship_cannot_point_to_another_slide(ws):
    path = ws.root / "ppt/slides/_rels/slide1.xml.rels"
    path.write_text(path.read_text().replace("../slideLayouts/slideLayout6.xml", "slide2.xml"))
    report = validate(ws.root)
    assert not report.ok
    assert any("expected sldLayout" in error for error in report.errors)


def test_legacy_vml_conditionals_are_read_only(tmp_path):
    path = tmp_path / "drawing.vml"
    raw = b'<xml xmlns:v="urn:schemas-microsoft-com:vml"><![if gte mso 9]><v:shape id="one"/><![endif]></xml>'
    path.write_bytes(raw)
    assert len(parse(path)) == 1
    assert path.read_bytes() == raw
    path.write_bytes(raw.replace(b"<![endif]>", b""))
    with pytest.raises(PptxError):
        parse(path)
