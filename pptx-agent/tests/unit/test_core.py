import json
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from pptx_core.common import PptxError, sha256
from pptx_core.diff import diff
from pptx_core.manifest import affected_slides, manifest
from pptx_core.package import Workspace, pack, safe_extract, unpack
from pptx_core.relationships import relationships, resolve_target, reverse_refs, slide_parts
from pptx_core.snapshots import rollback, snapshot
from pptx_core.validator import validate


def test_unpack_native_parts_and_bytes(ws, deck):
    assert validate(ws.root).ok
    assert sha256(deck) == sha256(ws.home / "original.pptx")
    with zipfile.ZipFile(deck) as source:
        for name in source.namelist():
            assert source.read(name) == (ws.root / name).read_bytes()
    assert (ws.home / "original.pptx").stat().st_mode & 0o222 == 0
    assert not ws.state["dirty"]


@pytest.mark.parametrize("target,expected", [("../media/a%20b.png", "ppt/media/a b.png"),
                                            ("/ppt/media/a.png", "ppt/media/a.png"),
                                            ("../media/a.png#x", "ppt/media/a.png")])
def test_target_resolution(target, expected):
    assert resolve_target("ppt/slides/slide1.xml", target) == expected


@pytest.mark.parametrize("target", ["../../../outside", "https://example.com/a", "..\\bad", "//host/a"])
def test_unsafe_relationship(target):
    with pytest.raises(PptxError):
        resolve_target("ppt/slides/slide1.xml", target)


@pytest.mark.parametrize("member", ["../escape", "/absolute", "ppt/../../escape", "ppt\\escape", "C:/x"])
def test_zip_slip(tmp_path, member):
    source = tmp_path / "bad.pptx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(member, b"bad")
    target = tmp_path / "extract"
    target.mkdir()
    with pytest.raises(PptxError):
        safe_extract(source, target)
    assert not list(target.iterdir())


def test_duplicate_zip_and_symlink(tmp_path):
    for variant in ("duplicate", "symlink"):
        path = tmp_path / (variant + ".pptx")
        with zipfile.ZipFile(path, "w") as z:
            if variant == "duplicate":
                z.writestr("ppt/A.xml", "a")
                z.writestr("ppt/a.xml", "b")
            else:
                info = zipfile.ZipInfo("link")
                info.external_attr = 0o120777 << 16
                z.writestr(info, "../secret")
        with pytest.raises(PptxError):
            unpack(path)


def test_reordered_slides(ws):
    p = ws.root / "ppt/presentation.xml"
    tree = etree.fromstring(p.read_bytes())
    ids = tree.find("{*}sldIdLst")
    ids.insert(0, ids[-1])
    p.write_bytes(etree.tostring(tree))
    assert slide_parts(ws.root)[0] == "ppt/slides/slide3.xml"
    assert affected_slides(ws.root, ["ppt/slides/slide3.xml"]) == [1]
    assert affected_slides(ws.root, ["ppt/theme/theme1.xml"]) == "ALL"


@pytest.mark.parametrize("kind", ["xml", "relationship", "shape", "content-type", "namespace", "target", "doctype"])
def test_validation_rejects_corruption(ws, kind):
    p = ws.root / "ppt/slides/slide1.xml"
    text = p.read_text()
    if kind == "xml":
        p.write_text(text + "<")
    elif kind == "relationship":
        p.write_text(text.replace('r:embed="rId2"', 'r:embed="rId999"'))
    elif kind == "shape":
        p.write_text(text.replace('id="3"', 'id="2"', 1))
    elif kind == "content-type":
        (ws.root / "ppt/media/new.unknown").write_bytes(b"x")
    elif kind == "namespace":
        p = ws.root / "ppt/presentation.xml"
        p.write_text(p.read_text().replace("presentationml/2006/main", "invalid"))
    elif kind == "target":
        (ws.root / "ppt/media/image1.png").unlink()
    else:
        p.write_text('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>')
    assert not validate(ws.root).ok


def test_unused_media_and_rels_are_permitted(ws):
    (ws.root / "ppt/media/orphan.png").write_bytes((ws.root / "ppt/media/image1.png").read_bytes())
    assert validate(ws.root).ok


def test_reverse_refs_shared_image(ws):
    refs = reverse_refs(ws.root, "ppt/media/image1.png")
    assert len(refs) == 3
    assert all(r["id"] == "rId2" for r in refs)


def test_snapshot_rollback_preserves_recovery(ws):
    original = manifest(ws.root)
    ident = snapshot(ws)
    p = ws.root / "ppt/slides/slide1.xml"
    p.write_text(p.read_text().replace("Original title 1", "Edited title"))
    result = rollback(ws, ident)
    assert not diff(ws)["modified"]
    assert (ws.home / "snapshots" / result["recovery_snapshot"] / "workspace" / "ppt/slides/slide1.xml").read_text().find("Edited title") >= 0
    assert manifest(ws.root).keys() == original.keys()
    with pytest.raises(PptxError):
        rollback(ws, "../outside")


def test_modified_bytes_tracking_and_diff(ws):
    path = ws.root / "ppt/slides/slide1.xml"
    path.write_text(path.read_text().replace("Original title 1", "Original title X"))
    ws.refresh()
    assert ws.state["changed_slides"] == [1]
    assert diff(ws)["modified"] == ["ppt/slides/slide1.xml"]
    assert "Original title X" in diff(ws, "slide1")


def test_symlink_workspace_rejected(ws, tmp_path):
    (ws.root / "leak").symlink_to(tmp_path)
    assert not validate(ws.root).ok


def test_unpack_name_collision_does_not_overwrite(ws, deck):
    other = unpack(deck)
    assert other.home != ws.home
    assert other.home.name.endswith("-2")
