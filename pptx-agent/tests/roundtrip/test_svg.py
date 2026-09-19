import zipfile

import pytest

from pptx_core.package import export, pack, unpack
from pptx_core.validator import validate


@pytest.mark.render
def test_native_svg_and_bitmap_fallback_survive_title_edit(ws, tmp_path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect width="120" height="80" fill="#168aad"/></svg>'
    (ws.root / "ppt/media/vector.svg").write_bytes(svg)
    path = ws.root / "ppt/slides/slide1.xml"
    extension = '<a:extLst><a:ext uri="{96DAC541-7B7A-43D3-8B79-37D633B846F1}"><asvg:svgBlip xmlns:asvg="http://schemas.microsoft.com/office/drawing/2016/SVG/main" r:embed="rIdSvg"/></a:ext></a:extLst>'
    original = path.read_text()
    assert '<a:blip r:embed="rId2"/>' in original
    path.write_text(original.replace('<a:blip r:embed="rId2"/>', '<a:blip r:embed="rId2">' + extension + '</a:blip>'))
    rels = ws.root / "ppt/slides/_rels/slide1.xml.rels"
    rels.write_text(rels.read_text().replace("</Relationships>", '<Relationship Id="rIdSvg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/vector.svg"/></Relationships>'))
    ct = ws.root / "[Content_Types].xml"
    ct.write_text(ct.read_text().replace("</Types>", '<Default Extension="svg" ContentType="image/svg+xml"/></Types>'))
    source = tmp_path / "svg-input.pptx"
    pack(ws.root, source)
    edit_ws = unpack(source)
    slide = edit_ws.root / "ppt/slides/slide1.xml"
    slide.write_bytes(slide.read_bytes().replace(b"Original title 1", b"SVG preserved"))
    output = export(edit_ws)
    with zipfile.ZipFile(source) as a, zipfile.ZipFile(output) as b:
        assert b.read("ppt/media/vector.svg") == svg
        assert b.read("ppt/media/image1.png") == a.read("ppt/media/image1.png")
        assert extension.encode() in b.read("ppt/slides/slide1.xml")
        assert [n for n in a.namelist() if a.read(n) != b.read(n)] == ["ppt/slides/slide1.xml"]


def test_malformed_svg_is_rejected_even_if_a_bitmap_could_render(ws):
    (ws.root / "ppt/media/vector.svg").write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><broken>')
    content = ws.root / "[Content_Types].xml"
    content.write_text(content.read_text().replace("</Types>", '<Default Extension="svg" ContentType="image/svg+xml"/></Types>'))
    result = validate(ws.root)
    assert not result.ok
    assert any("vector.svg" in error for error in result.errors)
