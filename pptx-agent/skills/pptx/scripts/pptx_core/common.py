from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
STRICT_P = "http://purl.oclc.org/ooxml/presentationml/main"
STRICT_R = "http://purl.oclc.org/ooxml/officeDocument/relationships"
NS = {"p": P, "a": A, "r": R, "pr": PR, "ct": CT}


class PptxError(Exception):
    """An actionable user-facing error."""


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def parse(path):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    if Path(path).suffix.lower() == ".vml":
        # Office's legacy VML can contain downlevel-revealed conditional markers,
        # which are not XML tokens. Remove only the wrappers in the read-only view;
        # validate all branch contents and preserve the actual package bytes.
        raw = Path(path).read_bytes()
        pattern = rb"<!\[(if [^\]<>\r\n]+|endif)\]>"
        depth = 0
        for marker in re.finditer(pattern, raw):
            depth += -1 if marker.group(1) == b"endif" else 1
            if depth < 0:
                raise PptxError(f"Unbalanced VML conditional marker: {path}")
        if depth:
            raise PptxError(f"Unbalanced VML conditional marker: {path}")
        tree = etree.parse(BytesIO(re.sub(pattern, b"", raw)), parser)
    else:
        tree = etree.parse(str(path), parser)
    if tree.docinfo.doctype:
        raise PptxError(f"DTD is not permitted in an OOXML part: {path}")
    return tree.getroot()


def local(element):
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


def part_path(root, part):
    root = Path(root).resolve()
    path = root / part
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise PptxError(f"Unsafe package path: {part}")
    return path
