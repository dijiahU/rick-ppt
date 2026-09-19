from __future__ import annotations

from dataclasses import asdict, dataclass, field
from lxml import etree

from .common import CT, P, PR, R, STRICT_P, STRICT_R, PptxError, local, parse, part_path
from .manifest import manifest
from .relationships import relationships, rels_part, slide_parts, source_part


def duplicate_shape_ids(tree):
    """OLE preview pictures have their own scope; MC branches are alternatives."""
    nodes = [n for n in tree.iter() if local(n) == "cNvPr" and
             not any(local(a) == "oleObj" for a in n.iterancestors())]
    seen = {}
    for node in nodes:
        ident = node.get("id")
        if ident is None:
            return True
        branches = {a.getparent(): a for a in node.iterancestors()
                    if local(a) in {"Choice", "Fallback"} and local(a.getparent()) == "AlternateContent"}
        for previous in seen.get(ident, []):
            if not any(key in previous and previous[key] is not branch for key, branch in branches.items()):
                return True
        seen.setdefault(ident, []).append(branches)
    return False


@dataclass
class Validation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors

    def to_dict(self):
        return {"ok": self.ok, **asdict(self)}

    def require(self):
        if not self.ok:
            raise PptxError("Validation failed:\n" + "\n".join(self.errors))


def validate(root, level=2):
    """Structural checks, not a full ECMA-376 schema implementation."""
    report = Validation()
    try:
        files = manifest(root)
    except PptxError as exc:
        report.errors.append(str(exc))
        return report
    trees = {}
    for required in ("[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml"):
        if required not in files:
            report.errors.append(f"Missing critical part: {required}")
    for name in files:
        if name.lower().endswith((".xml", ".rels", ".vml", ".svg")):
            try:
                trees[name] = parse(part_path(root, name))
            except (etree.Error, OSError, PptxError) as exc:
                report.errors.append(f"{name}: {exc}")
    expected = {"[Content_Types].xml": {f"{{{CT}}}Types"},
                "ppt/presentation.xml": {f"{{{P}}}presentation", f"{{{STRICT_P}}}presentation"}}
    for name, tree in trees.items():
        tags = {f"{{{PR}}}Relationships"} if name.endswith(".rels") else expected.get(name)
        for directory, element in (("ppt/slides/", "sld"), ("ppt/slideLayouts/", "sldLayout"),
                                   ("ppt/slideMasters/", "sldMaster")):
            if name.rsplit("/", 1)[0] + "/" == directory and name.endswith(".xml"):
                tags = {f"{{{P}}}{element}", f"{{{STRICT_P}}}{element}"}
        if tags and tree.tag not in tags:
            report.errors.append(f"{name}: invalid root namespace or element {tree.tag}")
        if name.rsplit("/", 1)[0] == "ppt/slides" and name.endswith(".xml"):
            if duplicate_shape_ids(tree):
                report.errors.append(f"{name}: duplicate or missing shape ID")
    if level == 1:
        return report
    all_rels = {}
    for name in files:
        if not name.endswith(".rels") or name not in trees:
            continue
        try:
            source = source_part(name)
            if source and source not in files:
                report.errors.append(f"{name}: relationship owner is missing: {source}")
            rels = relationships(root, source)
            all_rels[source] = rels
            ids = [r["id"] for r in rels]
            if len(ids) != len(set(ids)) or None in ids or "" in ids:
                report.errors.append(f"{name}: duplicate or empty relationship Id")
            for rel in rels:
                if not rel["target"] or not rel["type"]:
                    report.errors.append(f"{name}: missing Target/Type for {rel['id']}")
                if not rel["external"] and rel["resolved"] not in files:
                    report.errors.append(f"{name}: {rel['id']} missing target {rel['resolved']}")
                kind = rel["type"].rsplit("/", 1)[-1]
                target_root = trees.get(rel["resolved"])
                expected_local = {"slide": "sld", "slideLayout": "sldLayout", "slideMaster": "sldMaster",
                                  "officeDocument": "presentation"}.get(kind)
                if not rel["external"] and expected_local and target_root is not None and local(target_root) != expected_local:
                    report.errors.append(f"{name}: {rel['id']} targets {local(target_root)}, expected {expected_local}")
        except (PptxError, etree.Error, ValueError) as exc:
            report.errors.append(f"{name}: {exc}")
    for name, tree in trees.items():
        if name.endswith(".rels"):
            continue
        rels = {r["id"]: r for r in all_rels.get(name, [])}
        used = set()
        for node in tree.iter():
            for attr, value in node.attrib.items():
                if attr.startswith((f"{{{R}}}", f"{{{STRICT_R}}}")) or attr == "{urn:schemas-microsoft-com:office:office}relid":
                    used.add(value)
                    if value and value not in rels:
                        report.errors.append(f"{name}: missing relationship {value}")
        implicit = {"slideLayout", "slideMaster", "theme", "notesSlide", "notesMaster",
                    "handoutMaster", "presProps", "viewProps", "tableStyles"}
        for rid, rel in rels.items():
            if rid not in used and rel["type"].rsplit("/", 1)[-1] not in implicit:
                report.warnings.append(f"{name}: unused relationship {rid} (preserved)")
    ct = trees.get("[Content_Types].xml")
    if ct is not None:
        defaults, overrides = {}, {}
        for node in ct:
            key = node.get("Extension", "").lower() if local(node) == "Default" else node.get("PartName")
            dest = defaults if local(node) == "Default" else overrides
            if not key or not node.get("ContentType") or key in dest:
                report.errors.append("[Content_Types].xml: duplicate or invalid declaration")
            dest[key] = node.get("ContentType")
        for name in files:
            if name != "[Content_Types].xml" and "/" + name not in overrides and name.rsplit(".", 1)[-1].lower() not in defaults:
                report.errors.append(f"{name}: missing content type")
        for name in overrides:
            if name and name.lstrip("/") not in files:
                report.errors.append(f"[Content_Types].xml: override target missing: {name}")
    office = [r for r in all_rels.get("", []) if r["type"].endswith("/officeDocument")]
    if len(office) != 1 or office[0]["resolved"] != "ppt/presentation.xml":
        report.errors.append("_rels/.rels: expected one officeDocument -> ppt/presentation.xml")
    try:
        slides = slide_parts(root)
        if not slides:
            report.errors.append("Presentation contains no slides")
        if len(slides) != len(set(slides)):
            report.errors.append("Presentation references the same slide more than once")
        for slide in slides:
            layouts = [r for r in all_rels.get(slide, []) if r["type"].endswith("/slideLayout")]
            if len(layouts) != 1 or layouts[0]["external"]:
                report.errors.append(f"{slide}: expected one internal slideLayout relationship")
        for name in trees:
            if name.startswith("ppt/slideLayouts/") and name.endswith(".xml"):
                masters = [r for r in all_rels.get(name, []) if r["type"].endswith("/slideMaster")]
                if len(masters) != 1 or masters[0]["external"]:
                    report.errors.append(f"{name}: expected one internal slideMaster relationship")
    except (PptxError, etree.Error, OSError) as exc:
        report.errors.append(str(exc))
    from .interactive_ooxml import validate_ooxml
    report.errors.extend(validate_ooxml(root))
    return report
