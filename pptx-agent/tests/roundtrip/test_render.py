import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from pptx_core.common import PptxError, sha256
from pptx_core.hooks import handle
from pptx_core.package import Workspace, export
from pptx_core.renderer import render_package, render

pytestmark = pytest.mark.render


def assert_pixels_equal(left, right):
    with Image.open(left) as a, Image.open(right) as b:
        assert a.size == b.size
        assert ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is None


def test_zero_edit_roundtrip(ws, deck, tmp_path):
    baseline = render_package(deck, tmp_path / "baseline", expected_pages=3)
    output = export(ws)
    assert output.is_file()
    with zipfile.ZipFile(deck) as a, zipfile.ZipFile(output) as b:
        assert a.namelist() != []
        assert set(a.namelist()) == set(b.namelist())
        assert all(a.read(n) == b.read(n) for n in a.namelist())
    for a, b in zip(baseline["pages"], ws.state["last_render"]["pages"]):
        assert_pixels_equal(a, b)


def test_minimal_edit_render_and_no_overwrite(ws, deck, tmp_path):
    baseline = render_package(deck, tmp_path / "baseline", expected_pages=3)
    p = ws.root / "ppt/slides/slide1.xml"
    p.write_text(p.read_text().replace("Original title 1", "Edited native title"))
    existing = tmp_path / "chosen.pptx"
    existing.write_bytes(b"do not overwrite")
    output = export(ws, existing)
    assert output.name == "chosen-2.pptx"
    assert existing.read_bytes() == b"do not overwrite"
    with zipfile.ZipFile(deck) as a, zipfile.ZipFile(output) as b:
        changed = [n for n in a.namelist() if a.read(n) != b.read(n)]
        assert changed == ["ppt/slides/slide1.xml"]
        assert b"Edited native title" in b.read(changed[0])
    for i in (1, 2):
        assert_pixels_equal(baseline["pages"][i], ws.state["last_render"]["pages"][i])
    assert sha256(deck) == ws.state["source_hash"]


def test_export_fails_closed_without_renderer(ws, tmp_path, monkeypatch):
    monkeypatch.setenv("PPTX_SOFFICE", "/does-not-exist/soffice")
    destination = tmp_path / "must-not-exist.pptx"
    with pytest.raises(PptxError):
        export(ws, destination)
    assert not destination.exists()
    assert ws.state["latest_output"] is None


def test_stop_full_closed_loop(ws):
    p = ws.root / "ppt/slides/slide1.xml"
    p.write_text(p.read_text().replace("Original title 1", "Stop finalized title"))
    result = handle("Stop", {"cwd": str(ws.home.parent.parent), "stop_hook_active": False})
    assert "exported" in result.get("systemMessage", ""), result
    state = Workspace(ws.home).state
    assert not state["dirty"]
    assert Path(state["latest_output"]).is_file()
    assert state["last_render"]["ok"]


def test_single_slide_render(ws):
    result = render(ws, 2)
    assert len(result["pages"]) == 1
    assert Path(result["pages"][0]).name == "slide-2.png"
