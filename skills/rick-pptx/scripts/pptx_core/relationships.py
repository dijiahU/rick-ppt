from __future__ import annotations

import posixpath
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from .common import PptxError, P, STRICT_P, R, STRICT_R, local, parse, part_path


def rels_part(source):
    if not source:
        return "_rels/.rels"
    p = PurePosixPath(source)
    return str(p.parent / "_rels" / (p.name + ".rels"))


def source_part(rels):
    if rels == "_rels/.rels":
        return ""
    p = PurePosixPath(rels)
    if p.parent.name != "_rels" or not p.name.endswith(".rels"):
        raise PptxError(f"Invalid relationship part: {rels}")
    return str(p.parent.parent / p.name[:-5])


def resolve_target(source, target):
    uri = urlsplit(target)
    if uri.scheme or uri.netloc or uri.query:
        raise PptxError(f"Invalid internal relationship target: {target}")
    raw = unquote(uri.path)
    if "\\" in raw or "\x00" in raw:
        raise PptxError(f"Invalid internal relationship target: {target}")
    joined = posixpath.normpath(raw.lstrip("/") if raw.startswith("/") else
                                 posixpath.join(posixpath.dirname(source), raw))
    if joined in (".", "..") or joined.startswith("../"):
        raise PptxError(f"Relationship escapes package: {target}")
    return joined


def relationships(root, source):
    path = part_path(root, rels_part(source))
    if not path.exists():
        return []
    result = []
    for rel in parse(path):
        if local(rel) != "Relationship":
            continue
        external = rel.get("TargetMode") == "External"
        target = rel.get("Target", "")
        result.append({"id": rel.get("Id"), "type": rel.get("Type", ""),
                       "target": target, "external": external,
                       "resolved": None if external else resolve_target(source, target)})
    return result


def reverse_refs(root, target):
    result = []
    for path in sorted(root.rglob("*.rels")):
        source = source_part(path.relative_to(root).as_posix())
        for rel in relationships(root, source):
            if rel["resolved"] == target:
                result.append({"source": source, **rel})
    return result


def slide_parts(root):
    """Presentation order, never guessed from slideN filenames."""
    pres = parse(part_path(root, "ppt/presentation.xml"))
    rels = {r["id"]: r for r in relationships(root, "ppt/presentation.xml")}
    result = []
    namespace = pres.tag.split("}")[0].lstrip("{")
    if namespace not in {P, STRICT_P}:
        raise PptxError("Invalid presentation namespace")
    listing = pres.find(f"{{{namespace}}}sldIdLst")
    if listing is None:
        return []
    seen_ids = set()
    for node in listing:
        if node.tag != f"{{{namespace}}}sldId":
            continue
        ident = node.get("id")
        if ident is None or ident in seen_ids:
            raise PptxError(f"Duplicate or missing presentation slide ID: {ident}")
        seen_ids.add(ident)
        rid = node.get(f"{{{R}}}id") or node.get(f"{{{STRICT_R}}}id")
        rel = rels.get(rid)
        if not rel or rel["external"] or not rel["type"].endswith("/slide"):
            raise PptxError(f"Invalid presentation slide relationship: {rid}")
        result.append(rel["resolved"])
    return result
