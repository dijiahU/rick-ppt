from .common import PptxError, sha256


def manifest(root):
    if not root.is_dir() or root.is_symlink():
        raise PptxError(f"Workspace is missing or unsafe: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PptxError(f"Symlinks are not permitted in a package: {path}")
        if path.is_file():
            st = path.stat()
            result[path.relative_to(root).as_posix()] = {
                "mtime_ns": st.st_mtime_ns, "size": st.st_size, "hash": sha256(path)}
    return result


def changes(before, after):
    return {"added": sorted(after.keys() - before.keys()),
            "deleted": sorted(before.keys() - after.keys()),
            "modified": sorted(k for k in before.keys() & after.keys()
                               if before[k]["hash"] != after[k]["hash"])}


def changed_paths(before, after):
    return sorted(p for paths in changes(before, after).values() for p in paths)


def high_risk(part):
    return (part in {"ppt/presentation.xml", "[Content_Types].xml", "_rels/.rels"}
            or part.startswith(("ppt/theme/", "ppt/slideMasters/", "ppt/slideLayouts/",
                                "ppt/_rels/")))


def affected_slides(root, files):
    from .relationships import rels_part, slide_parts
    if not files:
        return []
    try:
        slides = slide_parts(root)
    except Exception:
        return "ALL"
    by_part = {p: n for n, p in enumerate(slides, 1)}
    by_part.update({rels_part(p): n for n, p in enumerate(slides, 1)})
    # Assets/charts/notes can be shared. Conservatively render all consumers.
    if any(p not in by_part for p in files):
        return "ALL"
    return sorted({by_part[p] for p in files})
