from __future__ import annotations

import argparse
import json
import sys
import zipfile

from lxml import etree

from .common import PptxError, local, now, parse, part_path
from .diff import diff
from .package import export, select, unpack
from .relationships import relationships, reverse_refs, slide_parts
from .renderer import render
from .snapshots import rollback, snapshot
from .validator import validate


def inspect(ws, number):
    slides = slide_parts(ws.root)
    if not 1 <= number <= len(slides):
        raise PptxError(f"Slide must be between 1 and {len(slides)}")
    part = slides[number - 1]
    tree = parse(ws.root / part)
    result = []
    for node in tree.iter():
        if local(node) not in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}:
            continue
        props = next((n for n in node.iter() if local(n) == "cNvPr"), None)
        xfrm = next((n for n in node.iter() if local(n) == "xfrm"), None)
        bounds = {local(n): dict(n.attrib) for n in xfrm} if xfrm is not None else {}
        result.append({"type": local(node), "id": props.get("id") if props is not None else None,
                       "name": props.get("name") if props is not None else None,
                       "text": "\n".join(n.text or "" for n in node.iter() if local(n) == "t"),
                       "transform": bounds})
    from .interactive_ooxml import discover_content_addins
    return {"slide": number, "part": part, "shapes": result, "relationships": relationships(ws.root, part),
            "interactive": [i for i in discover_content_addins(ws.root) if i["slide"] == number]}


def parser():
    p = argparse.ArgumentParser(description="Inspect, validate and export direct OOXML workspaces")
    p.add_argument("--workspace", "-w", help="Session directory or unpacked workspace directory")
    commands = p.add_subparsers(dest="command", required=True)
    u = commands.add_parser("unpack")
    u.add_argument("source")
    u.add_argument("--base", help="Parent directory for workspace sessions")
    u.add_argument("--render", action="store_true")
    li = commands.add_parser("list")
    li.add_argument("kind", choices=["slides", "media", "charts", "masters"])
    f = commands.add_parser("find")
    f.add_argument("text")
    i = commands.add_parser("inspect")
    i.add_argument("slide", type=int)
    r = commands.add_parser("refs")
    r.add_argument("target")
    r.add_argument("--from", dest="source")
    r.add_argument("--reverse", action="store_true")
    rr = commands.add_parser("render")
    rr.add_argument("slide", nargs="?", type=int)
    v = commands.add_parser("validate")
    v.add_argument("--level", type=int, choices=[1, 2, 3], default=2)
    d = commands.add_parser("diff")
    d.add_argument("--xml")
    s = commands.add_parser("snapshot")
    s.add_argument("--label", default="manual")
    rb = commands.add_parser("rollback")
    rb.add_argument("snapshot")
    e = commands.add_parser("export")
    e.add_argument("output", nargs="?")
    from .interactive import add_parser
    add_parser(commands)
    return p


def dispatch(args):
    if args.command == "interactive":
        from .interactive import dispatch as interactive_dispatch
        return interactive_dispatch(args), 0
    if args.command == "unpack":
        ws = unpack(args.source, args.base)
        if args.render:
            render(ws)
        return {"workspace": str(ws.root), "state": str(ws.state_path)}, 0
    ws = select(args.workspace)
    cmd = args.command
    if cmd == "list":
        if args.kind == "slides":
            return [{"slide": i, "part": p} for i, p in enumerate(slide_parts(ws.root), 1)], 0
        folder = {"media": "media", "charts": "charts", "masters": "slideMasters"}[args.kind]
        return [p.relative_to(ws.root).as_posix() for p in sorted((ws.root / "ppt" / folder).rglob("*")) if p.is_file()], 0
    if cmd == "find":
        found = []
        for path in sorted(ws.root.rglob("*.xml")):
            tree = parse(path)
            # Decoded text also finds &amp; and text split across runs.
            for node in tree.iter():
                if local(node) == "p":
                    text = "".join(n.text or "" for n in node.iter() if local(n) == "t")
                    if args.text in text:
                        found.append({"part": path.relative_to(ws.root).as_posix(),
                                      "line": node.sourceline, "text": text})
        return found, 0
    if cmd == "inspect":
        return inspect(ws, args.slide), 0
    if cmd == "refs":
        if args.reverse and args.source:
            raise PptxError("--reverse and --from cannot be combined")
        if args.reverse:
            part_path(ws.root, args.target)
            return reverse_refs(ws.root, args.target), 0
        if args.source:
            rels = [r for r in relationships(ws.root, args.source) if r["id"] == args.target]
            if not rels:
                raise PptxError(f"Relationship not found: {args.target}")
            return rels, 0
        return relationships(ws.root, args.target), 0
    if cmd == "validate":
        with ws.lock():
            ws.refresh()
            result = validate(ws.root, min(args.level, 2))
            if args.level >= 2:
                from .interactive_validate import validate_interactive
                result.errors.extend(validate_interactive(ws.root)["errors"])
            ws.state["last_validation"] = {"at": now(), **result.to_dict()}
            ws.save()
        value = result.to_dict()
        if result.ok and args.level == 3:
            value["render"] = render(ws)
        return value, 0 if result.ok else 1
    if cmd == "render":
        return render(ws, args.slide), 0
    if cmd == "diff":
        return diff(ws, args.xml), 0
    if cmd == "snapshot":
        with ws.lock():
            return {"snapshot": snapshot(ws, args.label)}, 0
    if cmd == "rollback":
        return rollback(ws, args.snapshot), 0
    if cmd == "export":
        return {"output": str(export(ws, args.output))}, 0
    raise PptxError(f"Unknown command: {cmd}")


def main(argv=None):
    try:
        value, status = dispatch(parser().parse_args(argv))
        print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
        return status
    except (PptxError, OSError, ValueError, zipfile.BadZipFile, etree.Error) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
