import json
import shutil
import uuid
from pathlib import Path

from .common import PptxError, atomic_json, now
from .manifest import manifest, changed_paths


def snapshot(ws, label="manual"):
    ident = now().replace(":", "-") + "-" + uuid.uuid4().hex[:8]
    dest = ws.home / "snapshots" / ident
    manifest(ws.root)
    shutil.copytree(ws.root, dest / "workspace")
    sidecar = ws.home / "interactive"
    sidecar_hashes = manifest(sidecar) if sidecar.exists() else {}
    if sidecar.exists():
        shutil.copytree(sidecar, dest / "interactive")
    atomic_json(dest / "snapshot.json", {"id": ident, "label": label, "at": now(),
                                        "manifest": manifest(dest / "workspace"),
                                        "interactive_manifest": sidecar_hashes,
                                        "interactive_state": {k: v for k, v in ws.state.items()
                                            if k.startswith("interactive") or k in
                                            ("bundle_manifest", "runtime_version", "latest_interactive_render")}})
    return ident


def rollback(ws, ident):
    if Path(ident).name != ident or ident in {".", ".."}:
        raise PptxError("Snapshot ID must be a single directory name")
    source = ws.home / "snapshots" / ident / "workspace"
    if not source.is_dir() or source.is_symlink():
        raise PptxError(f"Snapshot not found: {ident}")
    receipt = json.loads((source.parent / "snapshot.json").read_text())
    if changed_paths(receipt["manifest"], manifest(source)):
        raise PptxError("Snapshot package hashes do not match")
    sidecar = source.parent / "interactive"
    if changed_paths(receipt.get("interactive_manifest", {}), manifest(sidecar) if sidecar.exists() else {}):
        raise PptxError("Snapshot scene hashes do not match")
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
        # Keep replaced files as well as the named recovery snapshot.
        current_sidecar = ws.home / "interactive"
        if current_sidecar.exists():
            current_sidecar.rename(ws.home / (".replaced-interactive-" + uuid.uuid4().hex))
        if sidecar.exists():
            shutil.copytree(sidecar, current_sidecar)
        ws.state.update(receipt.get("interactive_state", {}))
        if not sidecar.exists():
            ws.state.update(interactive=False, interactive_baseline={})
        ws.state.update(last_validation=None, last_render=None, stop_failures=0)
        ws.refresh()
    return {"restored": ident, "recovery_snapshot": backup}
