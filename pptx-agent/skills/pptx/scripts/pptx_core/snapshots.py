import shutil
import uuid
from pathlib import Path

from .common import PptxError, atomic_json, now
from .manifest import manifest


def snapshot(ws, label="manual"):
    ident = now().replace(":", "-") + "-" + uuid.uuid4().hex[:8]
    dest = ws.home / "snapshots" / ident
    manifest(ws.root)
    shutil.copytree(ws.root, dest / "workspace")
    atomic_json(dest / "snapshot.json", {"id": ident, "label": label, "at": now(),
                                        "manifest": manifest(dest / "workspace")})
    return ident


def rollback(ws, ident):
    if Path(ident).name != ident or ident in {".", ".."}:
        raise PptxError("Snapshot ID must be a single directory name")
    source = ws.home / "snapshots" / ident / "workspace"
    if not source.is_dir() or source.is_symlink():
        raise PptxError(f"Snapshot not found: {ident}")
    manifest(source)
    with ws.lock():
        backup = snapshot(ws, "before-rollback")
        stage = ws.home / (".rollback-" + uuid.uuid4().hex)
        shutil.copytree(source, stage)
        old = ws.home / (".replaced-" + uuid.uuid4().hex)
        ws.root.rename(old)
        try:
            stage.rename(ws.root)
        except Exception:
            old.rename(ws.root)
            raise
        shutil.rmtree(old)  # Exact generated path; recoverable from backup snapshot.
        ws.state.update(last_validation=None, last_render=None, stop_failures=0)
        ws.refresh()
    return {"restored": ident, "recovery_snapshot": backup}
