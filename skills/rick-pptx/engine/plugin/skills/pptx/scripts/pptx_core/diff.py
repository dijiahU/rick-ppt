import difflib
import zipfile

from .manifest import changes, manifest
from .common import PptxError, part_path


def diff(ws, xml=None):
    if xml is None:
        return changes(ws.state["original_manifest"], manifest(ws.root))
    part = xml if "/" in xml else f"ppt/slides/{xml.removesuffix('.xml')}.xml"
    path = part_path(ws.root, part)
    with zipfile.ZipFile(ws.home / "original.pptx") as archive:
        before = archive.read(part).decode("utf-8") if part in archive.namelist() else ""
    after = path.read_text() if path.exists() else ""
    return "".join(difflib.unified_diff(before.splitlines(keepends=True),
                                      after.splitlines(keepends=True),
                                      fromfile="original/" + part, tofile="workspace/" + part))
