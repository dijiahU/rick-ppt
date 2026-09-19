"""Exercise direct XML mutations, not a PowerPoint API mutation layer."""
import re
import zipfile
from io import BytesIO

import pytest
from lxml import etree
from PIL import Image

from pptx_core.common import P, R, CT, PR, parse
from pptx_core.package import export
from pptx_core.relationships import slide_parts
from pptx_core.validator import validate


@pytest.mark.render
def test_layout_alignment_and_native_objects(ws):
    path = ws.root / "ppt/slides/slide1.xml"
    before = parse(path)
    before_ids = before.xpath("//@id")
    text = path.read_text()
    positions = [914400, 3200400, 5486400]
    matches = list(re.finditer(r'<a:off x="(\d+)" y="1828800"/>', text))
    assert len(matches) == 3
    for match, x in reversed(list(zip(matches, positions))):
        text = text[:match.start(1)] + str(x) + text[match.end(1):]
    path.write_text(text)
    assert parse(path).xpath("//@id") == before_ids
    assert validate(ws.root).ok
    output = export(ws)
    with zipfile.ZipFile(output) as archive:
        node = etree.fromstring(archive.read("ppt/slides/slide1.xml"))
        values = [int(n.get("x")) for n in node.iter() if n.tag.endswith("}off") and n.get("y") == "1828800"]
        assert values == positions


@pytest.mark.render
def test_picture_replace_and_delete_reference(ws):
    media = ws.root / "ppt/media/image1.png"
    image = Image.new("RGB", (120, 80), "#e85d04")
    image.save(media)
    path = ws.root / "ppt/slides/slide1.xml"
    text = path.read_text()
    text, count = re.subn(r"<p:pic>.*?</p:pic>", "", text, count=1)
    assert count == 1
    path.write_text(text)
    relpath = ws.root / "ppt/slides/_rels/slide1.xml.rels"
    relpath.write_text(re.sub(r'<Relationship\b[^>]*\bId="rId2"[^>]*/>', "", relpath.read_text()))
    assert validate(ws.root).ok
    output = export(ws)
    with zipfile.ZipFile(output) as archive:
        assert archive.read("ppt/media/image1.png") == media.read_bytes()
        assert b"<p:pic>" not in archive.read("ppt/slides/slide1.xml")
        assert b"<p:pic>" in archive.read("ppt/slides/slide2.xml")


@pytest.mark.render
def test_unknown_extension_and_animation_preserved(ws):
    path = ws.root / "ppt/slides/slide1.xml"
    extension = '<p:extLst><p:ext uri="urn:pptx-agent:preservation"><custom:data xmlns:custom="urn:unknown-vendor" value="keep-exactly"/></p:ext></p:extLst>'
    animation = '<p:transition spd="slow"><p:fade/></p:transition>'
    path.write_text(path.read_text().replace("</p:sld>", animation + extension + "</p:sld>"))
    path.write_text(path.read_text().replace("Original title 1", "Extension preserved"))
    output = export(ws)
    with zipfile.ZipFile(output) as archive:
        text = archive.read("ppt/slides/slide1.xml").decode()
        assert extension in text
        assert animation in text


@pytest.mark.render
def test_duplicate_then_delete_slide(ws):
    # Direct package edits; byte-copy the slide and preserve shared image relationships.
    root = ws.root
    (root / "ppt/slides/slide4.xml").write_bytes((root / "ppt/slides/slide1.xml").read_bytes())
    (root / "ppt/slides/_rels/slide4.xml.rels").write_bytes((root / "ppt/slides/_rels/slide1.xml.rels").read_bytes())
    pres = root / "ppt/presentation.xml"
    rels = root / "ppt/_rels/presentation.xml.rels"
    content = root / "[Content_Types].xml"
    pres.write_text(pres.read_text().replace("</p:sldIdLst>", '<p:sldId id="999" r:id="rId999"/></p:sldIdLst>'))
    rels.write_text(rels.read_text().replace("</Relationships>", f'<Relationship Id="rId999" Type="{R}/slide" Target="slides/slide4.xml"/></Relationships>'))
    content.write_text(content.read_text().replace("</Types>", '<Override PartName="/ppt/slides/slide4.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>'))
    assert len(slide_parts(root)) == 4
    assert validate(root).ok
    output = export(ws)
    assert len(ws.state["last_render"]["pages"]) == 4
    # Remove the duplicated slide plus all package declarations.
    pres.write_text(pres.read_text().replace('<p:sldId id="999" r:id="rId999"/>', ""))
    rels.write_text(re.sub(r'<Relationship Id="rId999"[^>]*/>', "", rels.read_text()))
    content.write_text(re.sub(r'<Override PartName="/ppt/slides/slide4.xml"[^>]*/>', "", content.read_text()))
    (root / "ppt/slides/slide4.xml").unlink()
    (root / "ppt/slides/_rels/slide4.xml.rels").unlink()
    assert validate(root).ok
    export(ws)
    assert len(ws.state["last_render"]["pages"]) == 3


@pytest.mark.render
def test_hidden_slide_numbering(ws):
    path = ws.root / "ppt/slides/slide2.xml"
    path.write_text(path.read_text().replace("<p:sld ", '<p:sld show="0" ', 1))
    export(ws)
    assert len(ws.state["last_render"]["pages"]) == 3
