from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

import fcntl

from .common import PptxError, atomic_json, now, sha256
from .manifest import affected_slides, changed_paths, manifest

MAX_FILES = 50000
MAX_UNCOMPRESSED = 2 * 1024**3


def safe_extract(source, target):
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES or sum(i.file_size for i in entries) > MAX_UNCOMPRESSED:
            raise PptxError("Package exceeds extraction limits (50k entries / 2 GiB)")
        seen = set()
        for entry in entries:
            name = entry.filename
            p = PurePosixPath(name)
            mode = entry.external_attr >> 16
            if (not name or p.is_absolute() or ".." in p.parts or "\\" in name or
                    ":" in name or "\x00" in name or str(p).casefold() in seen or
                    stat.S_ISLNK(mode)):
                raise PptxError(f"Unsafe or duplicate ZIP member: {name}")
            seen.add(str(p).casefold())
        for entry in entries:
            dest = target / entry.filename
            if entry.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as src, dest.open("xb") as dst:
                    shutil.copyfileobj(src, dst)


def pack(root, output):
    files = manifest(root)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(root / name, name)
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad or "[Content_Types].xml" not in archive.namelist():
            raise PptxError(f"ZIP verification failed: {bad}")


class Workspace:
    def __init__(self, home):
        self.home = Path(home).resolve()
        self.root = self.home / "workspace"
        self.state_path = self.home / "state.json"
        self.state = json.loads(self.state_path.read_text())
        if self.state.get("version") != 1 or self.state.get("workspace") != str(self.root):
            raise PptxError(f"Invalid workspace state: {self.state_path}")

    def save(self):
        atomic_json(self.state_path, self.state)

    @contextmanager
    def lock(self):
        with (self.home / ".lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            self.state = json.loads(self.state_path.read_text())
            try:
                yield self
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def refresh(self):
        current = manifest(self.root)
        files = changed_paths(self.state["baseline"], current)
        self.state.update(dirty=bool(files), changed_files=files,
                          changed_slides=affected_slides(self.root, files))
        self.save()
        return current

    def check_original(self):
        for p in (Path(self.state["source"]), self.home / "original.pptx"):
            if not p.is_file() or sha256(p) != self.state["source_hash"]:
                raise PptxError(f"Protected original changed or missing: {p}")


def discover(cwd):
    cwd = Path(cwd).resolve()
    for parent in [cwd, *cwd.parents]:
        if (parent / "state.json").is_file() and (parent / "workspace").is_dir():
            return [Workspace(parent)]
        found = sorted((parent / ".pptx-agent").glob("*/state.json"))
        if found:
            return [w for p in found if (w := Workspace(p.parent)).state.get("active")]
    return []


def select(path=None):
    if path:
        p = Path(path).resolve()
        return Workspace(p.parent if p.name in {"workspace", "state.json"} else p)
    found = discover(Path.cwd())
    if len(found) != 1:
        raise PptxError("Choose an active workspace with --workspace PATH" if found else
                        "No active workspace. Run pptx unpack FILE.pptx first.")
    return found[0]


def unpack(source, base=None):
    from .validator import validate
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() != ".pptx" or not zipfile.is_zipfile(source):
        raise PptxError("Input must be a ZIP-based .pptx file")
    parent = Path(base).resolve() if base else source.parent / ".pptx-agent"
    parent.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w.-]+", "-", source.stem, flags=re.UNICODE).strip(".-")[:80] or "deck"
    home = parent / slug
    index = 2
    while home.exists():
        home = parent / f"{slug}-{index}"
        index += 1
    with tempfile.TemporaryDirectory(prefix=".unpack-", dir=parent) as temporary:
        stage = Path(temporary)
        root = stage / "workspace"
        root.mkdir()
        safe_extract(source, root)
        result = validate(root)
        result.require()
        shutil.copyfile(source, stage / "original.pptx")
        (stage / "original.pptx").chmod(0o444)
        for name in ("renders", "snapshots", "output"):
            (stage / name).mkdir()
        initial = manifest(root)
        atomic_json(stage / "state.json", {
            "version": 1, "source": str(source), "source_hash": sha256(source),
            "workspace": str(home / "workspace"), "active": True, "dirty": False,
            "changed_files": [], "changed_slides": [], "baseline": initial,
            "original_manifest": initial, "last_validation": {"at": now(), **result.to_dict()},
            "last_render": None, "latest_output": None, "stop_failures": 0})
        # Reserve destination without replacing an existing workspace.
        home.mkdir()
        for child in stage.iterdir():
            shutil.move(str(child), home / child.name)
    return Workspace(home)


def export(ws, output=None):
    from .renderer import render_package
    from .relationships import slide_parts
    from .validator import validate
    with ws.lock():
        ws.check_original()
        before = ws.refresh()
        result = validate(ws.root)
        ws.state["last_validation"] = {"at": now(), **result.to_dict()}
        ws.save()
        result.require()
        source = Path(ws.state["source"])
        wanted = Path(output).absolute() if output else source.with_name(source.stem + "-edited.pptx")
        resolved = wanted.resolve()
        if (resolved == source or resolved == ws.home / "original.pptx" or
                resolved.is_relative_to(ws.root) or resolved.suffix.lower() != ".pptx"):
            raise PptxError("Export must target a new .pptx outside the workspace and original")
        wanted.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".pptx-export-", dir=wanted.parent) as temp:
            candidate = Path(temp) / "candidate.pptx"
            pack(ws.root, candidate)
            rendered = render_package(candidate, ws.home / "renders", expected_pages=len(slide_parts(ws.root)))
            ws.check_original()
            if changed_paths(before, manifest(ws.root)):
                raise PptxError("Workspace changed during export; retry after edits finish")
            # link() is atomic and refuses existing files, including racing writers.
            dest = wanted
            suffix = 2
            while True:
                try:
                    os.link(candidate, dest)
                    break
                except FileExistsError:
                    dest = wanted.with_name(f"{wanted.stem}-{suffix}.pptx")
                    suffix += 1
            ws.state.update(baseline=before, dirty=False, changed_files=[], changed_slides=[],
                            last_render=rendered, latest_output=str(dest), stop_failures=0)
            ws.save()
        return dest
