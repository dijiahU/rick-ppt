"""Host-owned, crash-recoverable PPTX workflow state; Python 3.11 standard library.

The journal directory MUST be outside every model-writable task workspace. Hold
the Journal context for the lifetime of the worker/recovery attempt. This module
never contacts the queue or Codex, executes archived commands, or deletes an old
attempt. Immutable, hash-chained event files are the write-ahead log; state.json
is an atomically replaced projection and may lag after a process crash.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
from typing import Any, Iterator
import uuid


VERSION = 1
SCHEMA = "pptx-workflow-journal/v1"
ZERO_HASH = "0" * 64
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
EXCLUDED_DIRECTORIES = frozenset({".git", ".venv", "node_modules", "__pycache__", "font-cache"})
MESSAGE_STATES = frozenset({"accepted", "delivering", "acknowledged", "applied", "uncertain"})


class JournalError(RuntimeError):
    """Base class for an actionable host-side recovery failure."""


class CorruptJournal(JournalError):
    """A durable record or a referenced file did not verify."""


class JournalBusy(JournalError):
    """Another process already owns this task's journal."""


class VersionMismatch(JournalError):
    """The caller supplied a different runtime/plugin version."""


class AlreadyRecovered(JournalError):
    """An idempotent recovery request was already committed."""


@dataclass(frozen=True)
class Limits:
    file_bytes: int = 128 * 1024 * 1024
    total_bytes: int = 1024 * 1024 * 1024
    files: int = 25000
    record_bytes: int = 32 * 1024 * 1024
    message_bytes: int = 64 * 1024
    messages: int = 5000
    events: int = 100000

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in vars(self).values()):
            raise ValueError("Journal limits must be positive integers")


def _encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _id(value: str, label: str = "identifier") -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid " + label)
    return value


def _revision(value: int) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Invalid input revision")
    return value


def safe_relative(value: str) -> PurePosixPath:
    """A portable, bounded path whose components can safely be opened by dir_fd."""
    if (not isinstance(value, str) or not value or len(value) > 2048 or
            any(c in value for c in ("\\", "\x00", ":"))):
        raise ValueError("Unsafe checkpoint path")
    parts = value.split("/")
    if len(parts) > 64 or any(p in ("", ".", "..") or len(p.encode("utf-8")) > 255 for p in parts):
        raise ValueError("Unsafe checkpoint path")
    return PurePosixPath(value)


def _signature(info: os.stat_result) -> tuple:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _new_file(path: Path, data: bytes) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(path.parent)


def _publish_new(path: Path, data: bytes) -> None:
    """Atomically publish without replacing a prior immutable event/snapshot."""
    temporary = path.parent / (".pending-" + str(uuid.uuid4()))
    try:
        _new_file(temporary, data)
        os.link(temporary, path, follow_symlinks=False)
        _fsync_directory(path.parent)
    finally:
        # Only this operation's newly created temporary file is removed.
        temporary.unlink(missing_ok=True)


def _atomic_projection(path: Path, data: bytes) -> None:
    temporary = path.parent / (".pending-state-" + str(uuid.uuid4()))
    try:
        _new_file(temporary, data)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CorruptJournal("Duplicate JSON key")
        result[key] = value
    return result


def _read_json(path: Path, limit: int) -> Any:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise CorruptJournal("Journal record is not a bounded regular file")
            data = stream.read(limit + 1)
            if len(data) > limit or _signature(before) != _signature(os.fstat(stream.fileno())):
                raise CorruptJournal("Journal record changed during read")
        return json.loads(data, object_pairs_hook=_unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(CorruptJournal("Non-finite JSON number")))
    except (ValueError, OSError, RecursionError) as exc:
        raise CorruptJournal("Cannot read a valid journal record") from exc


def _directory(path: Path, *, create: bool = False) -> Path:
    path = Path(path).absolute()
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("Expected a real directory, not a symlink")
    return path.resolve(strict=True)


@contextmanager
def _root_fd(root: Path) -> Iterator[int]:
    root = _directory(root)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield fd
    finally:
        os.close(fd)


def _open_relative(root_fd: int, value: str) -> int:
    parts = safe_relative(value).parts
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)


def _hash_fd(fd: int, limit: int) -> dict:
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise CorruptJournal("Expected a bounded regular artifact")
        digest, count = hashlib.sha256(), 0
        while block := stream.read(min(1024 * 1024, limit + 1 - count)):
            count += len(block)
            if count > limit:
                raise CorruptJournal("Artifact byte limit exceeded")
            digest.update(block)
        if _signature(before) != _signature(os.fstat(stream.fileno())) or count != before.st_size:
            raise CorruptJournal("Artifact changed during capture")
        return {"sha256": digest.hexdigest(), "bytes": count,
                "mode": stat.S_IMODE(before.st_mode) & 0o777,
                "mtime_ns": before.st_mtime_ns}


class Journal:
    """Exclusive per-task journal. Open through a with-statement; never share threads."""

    def __init__(self, directory: Path | str, task_id: str, *, plugin_version: str | None = None,
                 run_id: str | None = None, input_revision: int = 0, limits: Limits | None = None,
                 secrets: tuple[str, ...] = ()):
        self.task_id = _id(task_id, "task ID")
        self.limits = limits or Limits()
        self.secrets = tuple(secret for secret in secrets if secret)
        self.directory = _directory(Path(directory), create=True)
        self.root = _directory(self.directory / self.task_id, create=True)
        mode = self.root.stat()
        if mode.st_uid != os.getuid() or stat.S_IMODE(mode.st_mode) & 0o022:
            raise ValueError("Task journal must be host-owned and not writable by other users")
        self._lock = os.open(self.root / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        self._closed = False
        try:
            if not stat.S_ISREG(os.fstat(self._lock).st_mode):
                raise ValueError("Invalid journal lock")
            try:
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise JournalBusy("Another worker owns this task journal") from exc
            for name in ("events", "snapshots", "blobs"):
                _directory(self.root / name, create=True)
            self._state, self._head = self._load()
            if self._state is None:
                if plugin_version is None:
                    raise ValueError("plugin_version is required for a new journal")
                self._state = {
                    "version": VERSION, "task_id": self.task_id,
                    "run_id": _id(run_id or str(uuid.uuid4()), "run ID"),
                    "plugin_version": _id(plugin_version, "plugin version"),
                    "input_revision": _revision(input_revision), "message_cursor": 0,
                    "applied_message_cursor": 0, "status": "ready", "phase": None,
                    "next_phase": None, "workspace": None, "snapshot_id": None,
                    "completed_stages": {}, "inbox": {}, "recoveries": {},
                    "created_at": time.time_ns(), "updated_at": time.time_ns(), "sequence": 0,
                }
                self._event("created", {})
            elif plugin_version is not None and self._state["plugin_version"] != plugin_version:
                raise VersionMismatch("Plugin version differs; open without a version and explicitly migrate recovery")
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> Journal:
        self._check_open()
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            fcntl.flock(self._lock, fcntl.LOCK_UN)
            os.close(self._lock)

    def _check_open(self) -> None:
        if self._closed:
            raise JournalError("Journal lock is no longer held")

    @property
    def state(self) -> dict:
        """Private host state. Do not send this projection to the browser/model."""
        self._check_open()
        return copy.deepcopy(self._state)

    def _load(self) -> tuple[dict | None, str]:
        entries = []
        for path in (self.root / "events").iterdir():
            if path.name.startswith(".pending-"):
                continue
            if not re.fullmatch(r"[0-9]{20}\.json", path.name):
                raise CorruptJournal("Unexpected journal event filename")
            entries.append(path)
        if len(entries) > self.limits.events:
            raise CorruptJournal("Journal event limit exceeded")
        head, state, envelopes = ZERO_HASH, None, {}
        for seq, path in enumerate(sorted(entries), 1):
            if path.name != f"{seq:020}.json":
                raise CorruptJournal("Journal event sequence has a gap")
            event = _read_json(path, self.limits.record_bytes)
            if not isinstance(event, dict) or set(event) != {"schema", "sequence", "previous", "kind", "at", "data", "state", "sha256"}:
                raise CorruptJournal("Malformed journal event")
            digest = event.pop("sha256")
            if event["schema"] != SCHEMA or event["sequence"] != seq or event["previous"] != head or digest != _sha(_encoded(event)):
                raise CorruptJournal("Journal event hash chain does not verify")
            state = event["state"]
            self._validate_state(state, seq)
            head = digest
            envelopes[seq] = (head, _sha(_encoded(state)))
        projection = self.root / "state.json"
        if projection.exists() or projection.is_symlink():
            saved = _read_json(projection, self.limits.record_bytes)
            if not isinstance(saved, dict) or set(saved) != {"head", "state"}:
                raise CorruptJournal("Malformed state projection")
            projected_state = saved["state"]
            seq = projected_state.get("sequence") if isinstance(projected_state, dict) else None
            if type(seq) is not int or envelopes.get(seq) != (saved["head"], _sha(_encoded(projected_state))):
                raise CorruptJournal("State projection is not a committed journal state")
        if state is not None:
            # Recover from an event committed before the projection replacement.
            _atomic_projection(projection, _encoded({"head": head, "state": state}))
        return state, head

    def _validate_state(self, state: Any, seq: int) -> None:
        if (not isinstance(state, dict) or state.get("version") != VERSION or
                state.get("task_id") != self.task_id or state.get("sequence") != seq or
                not isinstance(state.get("inbox"), dict) or not isinstance(state.get("completed_stages"), dict)):
            raise CorruptJournal("Journal state identity/schema mismatch")
        try:
            _revision(state["input_revision"])
            _id(state["run_id"])
            _id(state["plugin_version"])
            if len(state["inbox"]) > self.limits.messages:
                raise CorruptJournal("Journal inbox limit exceeded")
            for identifier, message in state["inbox"].items():
                if message["id"] != identifier or message["state"] not in MESSAGE_STATES:
                    raise CorruptJournal("Invalid durable inbox state")
        except (KeyError, TypeError, ValueError) as exc:
            raise CorruptJournal("Invalid journal state fields") from exc

    def _event(self, kind: str, data: dict, new_state: dict | None = None) -> None:
        self._check_open()
        state = copy.deepcopy(self._state if new_state is None else new_state)
        state["sequence"] = self._state["sequence"] + 1
        state["updated_at"] = time.time_ns()
        if state["sequence"] > self.limits.events:
            raise JournalError("Journal event limit reached")
        self._validate_state(state, state["sequence"])
        event = {"schema": SCHEMA, "sequence": state["sequence"], "previous": self._head,
                 "kind": _id(kind), "at": state["updated_at"], "data": data, "state": state}
        head = _sha(_encoded(event))
        encoded = _encoded({**event, "sha256": head})
        if len(encoded) > self.limits.record_bytes:
            raise JournalError("Journal record limit reached")
        _publish_new(self.root / "events" / f"{state['sequence']:020}.json", encoded)
        # Once the immutable event exists, it is committed even if projection IO fails.
        self._state, self._head = state, head
        _atomic_projection(self.root / "state.json", _encoded({"head": head, "state": state}))

    def begin_phase(self, name: str, workspace: Path | str, *, thread_id: str | None = None) -> dict:
        name = _id(name, "phase name")
        root = _directory(Path(workspace))
        if root == self.root or self.root.is_relative_to(root):
            raise ValueError("The journal must not be inside the task workspace")
        state = self.state
        state["workspace"] = str(root)
        state["phase"] = {"id": str(uuid.uuid4()), "name": name, "status": "running",
                          "input_revision": state["input_revision"], "thread_id": _id(thread_id) if thread_id else None,
                          "turn_id": None, "started_at": time.time_ns()}
        state["status"], state["next_phase"] = "running", name
        self._event("phase.started", {"name": name}, state)
        return copy.deepcopy(state["phase"])

    def bind_session(self, thread_id: str, turn_id: str | None = None) -> None:
        state = self.state
        if not state["phase"] or state["phase"]["status"] != "running":
            raise JournalError("No running phase to bind")
        state["phase"].update(thread_id=_id(thread_id, "thread ID"),
                              turn_id=_id(turn_id, "turn ID") if turn_id else None)
        self._event("phase.session", {}, state)

    def interrupt(self, *, reason: str = "worker_interrupted") -> None:
        state = self.state
        state["status"] = "interrupted"
        if state["phase"] and state["phase"]["status"] == "running":
            state["phase"]["status"] = "interrupted"
        self._event("phase.interrupted", {"reason": _id(reason)}, state)

    def _store_file(self, fd: int) -> dict:
        temporary = self.root / "blobs" / (".pending-" + str(uuid.uuid4()))
        try:
            with os.fdopen(fd, "rb") as source:
                before = os.fstat(source.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_size > self.limits.file_bytes:
                    raise CorruptJournal("Snapshot contains an oversized or non-regular file")
                digest, size = hashlib.sha256(), 0
                with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as target:
                    while block := source.read(min(1024 * 1024, self.limits.file_bytes + 1 - size)):
                        size += len(block)
                        if size > self.limits.file_bytes:
                            raise CorruptJournal("Snapshot file limit exceeded")
                        digest.update(block)
                        target.write(block)
                    target.flush()
                    os.fsync(target.fileno())
                if _signature(before) != _signature(os.fstat(source.fileno())) or size != before.st_size:
                    raise CorruptJournal("Snapshot file changed during capture")
            receipt = {"sha256": digest.hexdigest(), "bytes": size,
                       "mode": stat.S_IMODE(before.st_mode) & 0o777, "mtime_ns": before.st_mtime_ns}
            destination = self.root / "blobs" / receipt["sha256"]
            try:
                os.link(temporary, destination, follow_symlinks=False)
                _fsync_directory(destination.parent)
            except FileExistsError:
                self._verify_blob(receipt)
            return receipt
        finally:
            temporary.unlink(missing_ok=True)

    def checkpoint(self, workspace: Path | str, *, reason: str = "stable_snapshot",
                   exclude_directories: frozenset[str] = EXCLUDED_DIRECTORIES) -> dict:
        self._check_open()
        root = _directory(Path(workspace))
        if root == self.root or self.root.is_relative_to(root):
            raise ValueError("The journal must not be inside the task workspace")
        files, directories, excluded, total = {}, [], [], 0
        def fail_walk(error):
            raise error

        for parent, dirs, names, fd in os.fwalk(root, follow_symlinks=False, onerror=fail_walk):
            relative_parent = Path(parent).relative_to(root)
            for name in sorted(dirs):
                relative = (relative_parent / name).as_posix()
                safe_relative(relative)
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    raise CorruptJournal("Snapshot contains a symlink directory")
                (excluded if name in exclude_directories else directories).append(relative)
                if len(directories) + len(excluded) > self.limits.files:
                    raise CorruptJournal("Snapshot directory count limit exceeded")
            dirs[:] = sorted(name for name in dirs if name not in exclude_directories)
            for name in sorted(names):
                relative = (relative_parent / name).as_posix()
                safe_relative(relative)
                if len(files) >= self.limits.files:
                    raise CorruptJournal("Snapshot file count limit exceeded")
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                receipt = self._store_file(child)
                total += receipt["bytes"]
                if total > self.limits.total_bytes:
                    raise CorruptJournal("Snapshot total byte limit exceeded")
                files[relative] = receipt
        snapshot_id = str(uuid.uuid4())
        snapshot = {"schema": SCHEMA, "id": snapshot_id, "task_id": self.task_id,
                    "run_id": self._state["run_id"], "plugin_version": self._state["plugin_version"],
                    "input_revision": self._state["input_revision"], "after_event_sequence": self._state["sequence"],
                    "reason": _id(reason), "snapshot_atomic": False, "files": files,
                    "directories": sorted(directories), "excluded_directories": sorted(excluded), "bytes": total}
        body = _encoded(snapshot)
        if len(body) > self.limits.record_bytes:
            raise JournalError("Snapshot record limit exceeded")
        self._validate_snapshot(snapshot)
        _publish_new(self.root / "snapshots" / (snapshot_id + ".json"), body)
        state = self.state
        state.update(snapshot_id=snapshot_id, snapshot_sha256=_sha(body), workspace=str(root))
        self._event("workspace.checkpoint", {"snapshot_id": snapshot_id}, state)
        return copy.deepcopy(snapshot)

    def artifacts(self, workspace: Path | str, paths: list[str] | tuple[str, ...]) -> dict:
        """Return verified relative-path receipts; never dereference symlinks."""
        self._check_open()
        if len(paths) > self.limits.files or len(set(paths)) != len(paths):
            raise ValueError("Invalid artifact path list")
        result, total = {}, 0
        with _root_fd(Path(workspace)) as fd:
            for path in paths:
                receipt = _hash_fd(_open_relative(fd, path), self.limits.file_bytes)
                total += receipt["bytes"]
                if total > self.limits.total_bytes:
                    raise ValueError("Artifact total byte limit exceeded")
                result[path] = {"sha256": receipt["sha256"], "bytes": receipt["bytes"]}
        return result

    def complete_phase(self, name: str, workspace: Path | str, *, artifacts: list[str],
                       next_phase: str | None = None, revision: int | None = None,
                       require_applied: bool = True) -> dict:
        state = self.state
        phase = state["phase"]
        if not phase or phase["name"] != name or phase["status"] != "running":
            raise JournalError("The requested phase is not running")
        revision = phase["input_revision"] if revision is None else _revision(revision)
        if revision != state["input_revision"]:
            raise JournalError("Phase result is stale after a user revision")
        if type(require_applied) is not bool:
            raise ValueError("require_applied must be boolean")
        # Research/authoring boundaries certify phase artifacts. Final delivery
        # keeps the strict default: only validated requested edits are complete.
        pending_states = {"accepted", "delivering", "uncertain"}
        if any(m["changes_input"] and m["revision"] <= revision and
               (m["state"] != "applied" if require_applied else m["state"] in pending_states)
               for m in state["inbox"].values()):
            raise JournalError("A requested correction has not been applied")
        receipts = self.artifacts(workspace, artifacts)
        if not receipts:
            raise ValueError("Completed stages require at least one durable artifact")
        snapshot = self.checkpoint(workspace, reason="phase_completed")
        if any({k: snapshot["files"].get(path, {}).get(k) for k in ("sha256", "bytes")} != receipt
               for path, receipt in receipts.items()):
            raise JournalError("Phase artifact changed before its checkpoint; retry after validation")
        state = self.state
        receipt = {"name": _id(name), "input_revision": revision,
                   "plugin_version": state["plugin_version"], "artifacts": receipts,
                   "snapshot_id": snapshot["id"], "thread_id": phase["thread_id"], "completed_at": time.time_ns()}
        state["completed_stages"][name] = receipt
        state["phase"].update(status="completed", turn_id=None, input_revision=revision)
        state["next_phase"] = _id(next_phase) if next_phase is not None else None
        state["status"] = "ready" if next_phase else "completed"
        self._event("phase.completed", {"name": name}, state)
        return copy.deepcopy(receipt)

    def can_reuse(self, name: str, workspace: Path | str, *, revision: int | None = None) -> bool:
        self._check_open()
        receipt = self._state["completed_stages"].get(name)
        revision = self._state["input_revision"] if revision is None else _revision(revision)
        if (not receipt or revision != self._state["input_revision"] or
                receipt["input_revision"] != revision or receipt["plugin_version"] != self._state["plugin_version"]):
            return False
        try:
            actual = self.artifacts(workspace, list(receipt["artifacts"]))
        except (JournalError, ValueError, OSError):
            return False
        return bool(actual) and actual == receipt["artifacts"]

    def _validate_snapshot(self, snapshot: Any) -> None:
        if (not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA or
                snapshot.get("task_id") != self.task_id or not isinstance(snapshot.get("files"), dict) or
                not isinstance(snapshot.get("directories"), list)):
            raise CorruptJournal("Snapshot schema/task mismatch")
        files, dirs = snapshot["files"], snapshot["directories"]
        if len(files) > self.limits.files or len(dirs) > self.limits.files:
            raise CorruptJournal("Snapshot entry count limit exceeded")
        folded, total = set(), 0
        try:
            for path in [*files, *dirs]:
                safe_relative(path)
                if path.casefold() in folded:
                    raise CorruptJournal("Checkpoint paths collide")
                folded.add(path.casefold())
                if any(str(parent) in files for parent in PurePosixPath(path).parents if str(parent) != "."):
                    raise CorruptJournal("Checkpoint parent is a file")
            for receipt in files.values():
                if (not isinstance(receipt, dict) or not SHA256.fullmatch(receipt.get("sha256", "")) or
                        type(receipt.get("bytes")) is not int or not 0 <= receipt["bytes"] <= self.limits.file_bytes or
                        type(receipt.get("mode")) is not int or not 0 <= receipt["mode"] <= 0o777 or
                        type(receipt.get("mtime_ns")) is not int):
                    raise CorruptJournal("Invalid snapshot artifact receipt")
                total += receipt["bytes"]
            if total > self.limits.total_bytes or total != snapshot.get("bytes"):
                raise CorruptJournal("Snapshot byte total mismatch")
        except (ValueError, TypeError, KeyError) as exc:
            raise CorruptJournal("Unsafe checkpoint manifest") from exc

    def _verify_blob(self, receipt: dict) -> None:
        try:
            fd = os.open(self.root / "blobs" / receipt["sha256"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            actual = _hash_fd(fd, self.limits.file_bytes)
        except OSError as exc:
            raise CorruptJournal("Checkpoint blob missing or unsafe") from exc
        if actual["sha256"] != receipt["sha256"] or actual["bytes"] != receipt["bytes"]:
            raise CorruptJournal("Checkpoint blob checksum mismatch")

    def recover(self, out: Path | str, *, plugin_version: str, recovery_id: str | None = None,
                allow_plugin_upgrade: bool = False) -> dict:
        """Restore a new attempt. Caller validates it and resumes or starts Codex.

        No message is resent here. Uncertain messages are returned separately and
        require thread/event reconciliation before they can be delivered again.
        The task lock remains held after this method returns.
        """
        state = self.state
        recovery_id = _id(recovery_id or str(uuid.uuid4()), "recovery ID")
        if recovery_id in state["recoveries"]:
            raise AlreadyRecovered("This recovery request has already produced a new attempt")
        upgraded = state["plugin_version"] != _id(plugin_version, "plugin version")
        if upgraded and not allow_plugin_upgrade:
            raise VersionMismatch("Recovery requires the recorded plugin version")
        if not state["snapshot_id"]:
            raise JournalError("No durable checkpoint is available")
        snapshot = _read_json(self.root / "snapshots" / (state["snapshot_id"] + ".json"), self.limits.record_bytes)
        if _sha(_encoded(snapshot)) != state.get("snapshot_sha256"):
            raise CorruptJournal("Checkpoint manifest checksum mismatch")
        self._validate_snapshot(snapshot)
        for receipt in snapshot["files"].values():
            self._verify_blob(receipt)
        out = Path(out).absolute()
        parent = _directory(out.parent)
        out = parent / out.name
        if out == self.root or out.is_relative_to(self.root):
            raise ValueError("Recovery output must be outside the host journal")
        out.mkdir(mode=0o700, exist_ok=False)
        for relative in sorted(snapshot["directories"], key=lambda p: (len(PurePosixPath(p).parts), p)):
            out.joinpath(*safe_relative(relative).parts).mkdir(mode=0o700, parents=True, exist_ok=True)
        for relative, receipt in sorted(snapshot["files"].items()):
            destination = out.joinpath(*safe_relative(relative).parts)
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(self.root / "blobs" / receipt["sha256"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as source:
                digest, size = hashlib.sha256(), 0
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise CorruptJournal("Checkpoint blob is no longer regular")
                with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as target:
                    while block := source.read(min(1024 * 1024, self.limits.file_bytes + 1 - size)):
                        size += len(block)
                        if size > self.limits.file_bytes:
                            raise CorruptJournal("Checkpoint blob grew during recovery")
                        digest.update(block)
                        target.write(block)
                    target.flush()
                    os.fsync(target.fileno())
                if digest.hexdigest() != receipt["sha256"] or size != receipt["bytes"]:
                    raise CorruptJournal("Checkpoint blob changed during recovery; retain but do not use this attempt")
            # Recovered files must remain owner writable and never acquire setuid bits.
            os.chmod(destination, (receipt["mode"] & 0o700) | 0o600)
            os.utime(destination, ns=(receipt["mtime_ns"], receipt["mtime_ns"]))
        for parent_path, _, _ in os.walk(out, topdown=False):
            _fsync_directory(Path(parent_path))
        _fsync_directory(out.parent)
        previous_run = state["run_id"]
        previous_workspace = state["workspace"]
        state.update(run_id=str(uuid.uuid4()), workspace=str(out), status="recovered")
        if upgraded:
            state["plugin_version"] = plugin_version
            state["input_revision"] += 1
        needs_reapplication = []
        for message in state["inbox"].values():
            if message["state"] == "delivering":
                message["state"] = "uncertain"
            if message["state"] == "applied" and any(
                    {k: snapshot["files"].get(path, {}).get(k) for k in ("sha256", "bytes")} != receipt
                    for path, receipt in message["artifacts"].items()):
                message.update(state="acknowledged", applied_revision=None, applied_checkpoint_missing=True)
                needs_reapplication.append(message["id"])
        state["applied_message_cursor"] = 0
        for message in sorted(state["inbox"].values(), key=lambda m: m["cursor"]):
            if message["state"] != "applied":
                break
            state["applied_message_cursor"] = message["cursor"]
        phase = state["phase"]
        thread_id = phase.get("thread_id") if phase and phase["status"] in ("running", "interrupted") and not upgraded else None
        next_phase = phase["name"] if phase and phase["status"] in ("running", "interrupted") else state["next_phase"]
        if phase and phase["status"] in ("running", "interrupted"):
            phase["status"] = "interrupted"
        plan = {
            "recovery_id": recovery_id, "task_id": self.task_id, "run_id": state["run_id"],
            "previous_run_id": previous_run, "previous_workspace": previous_workspace,
            "workspace": str(out), "snapshot_id": snapshot["id"],
            "workspace_revision": snapshot["input_revision"], "input_revision": state["input_revision"],
            "next_phase": next_phase, "preferred_thread_id": thread_id,
            "context_rebuild_required": upgraded or not bool(thread_id),
            "file_bytes_verified": True, "snapshot_atomic": False, "validation_required": True,
            "message_cursor": state["message_cursor"],
            "pending_message_ids": [m["id"] for m in state["inbox"].values() if m["state"] == "accepted"],
            "uncertain_message_ids": [m["id"] for m in state["inbox"].values() if m["state"] == "uncertain"],
            "acknowledged_message_ids": [m["id"] for m in state["inbox"].values() if m["state"] == "acknowledged"],
            "requires_reapplication_message_ids": needs_reapplication,
        }
        state["recoveries"][recovery_id] = plan
        self._event("attempt.recovered", {"recovery_id": recovery_id, "previous_run_id": previous_run}, state)
        return copy.deepcopy(plan)

    def accept_message(self, identifier: str, text: str, *, attachments: list[dict] | None = None,
                       cursor: int | None = None, changes_input: bool = True) -> dict:
        """Durably deduplicate a website message before any transport write."""
        identifier = _id(identifier, "message ID")
        if not isinstance(text, str) or len(text.encode("utf-8")) > self.limits.message_bytes:
            raise ValueError("Message exceeds its byte limit")
        if type(changes_input) is not bool:
            raise ValueError("changes_input must be boolean")
        attachments = copy.deepcopy(attachments or [])
        if len(attachments) > 3 or not text.strip() and not attachments:
            raise ValueError("Empty message or too many attachments")
        seen = set()
        for item in attachments:
            if not isinstance(item, dict) or not {"id", "path", "sha256", "bytes"}.issubset(item) or set(item) - {"id", "path", "sha256", "bytes", "name", "media_type"}:
                raise ValueError("Invalid message attachment descriptor")
            _id(item["id"], "attachment ID")
            safe_relative(item["path"])
            if item["id"] in seen or not SHA256.fullmatch(item["sha256"]) or type(item["bytes"]) is not int or not 0 <= item["bytes"] <= self.limits.file_bytes:
                raise ValueError("Invalid attachment identity/hash/size")
            seen.add(item["id"])
            if any(not isinstance(item.get(key, ""), str) or len(item.get(key, "")) > 512 for key in ("name", "media_type")):
                raise ValueError("Attachment label exceeds its limit")
        state = self.state
        payload = {"text": text, "attachments": attachments, "changes_input": changes_input}
        fingerprint = _sha(_encoded(payload))
        previous = state["inbox"].get(identifier)
        if previous:
            if previous["fingerprint"] != fingerprint or cursor is not None and previous["cursor"] != cursor:
                raise JournalError("Message ID was reused with different content")
            return copy.deepcopy(previous)
        if len(state["inbox"]) >= self.limits.messages:
            raise JournalError("Inbox message limit reached")
        cursor = state["message_cursor"] + 1 if cursor is None else cursor
        if type(cursor) is not int or cursor <= state["message_cursor"]:
            raise JournalError("New message cursor must advance monotonically")
        state["message_cursor"] = cursor
        if changes_input:
            state["input_revision"] += 1
        message = {"id": identifier, **payload, "fingerprint": fingerprint, "cursor": cursor,
                   "revision": state["input_revision"], "state": "accepted", "delivery": None,
                   "accepted_at": time.time_ns(), "applied_revision": None, "artifacts": {}}
        state["inbox"][identifier] = message
        self._event("message.accepted", {"id": identifier, "cursor": cursor}, state)
        return copy.deepcopy(message)

    def pending_messages(self) -> list[dict]:
        """Only never-sent or positively reconciled-not-received messages."""
        return sorted((m for m in self.state["inbox"].values() if m["state"] == "accepted"), key=lambda m: m["cursor"])

    def begin_delivery(self, identifier: str, request_id: str, thread_id: str, turn_id: str | None = None) -> dict:
        state = self.state
        message = state["inbox"].get(identifier)
        if not message or message["state"] != "accepted":
            raise JournalError("Message is not pending; reconcile any uncertain delivery first")
        delivery = {"request_id": _id(request_id, "request ID"), "thread_id": _id(thread_id, "thread ID"),
                    "turn_id": _id(turn_id, "turn ID") if turn_id else None, "started_at": time.time_ns()}
        message.update(state="delivering", delivery=delivery)
        self._event("message.delivery_started", {"id": identifier}, state)
        return copy.deepcopy(message)

    def acknowledge_message(self, identifier: str, *, request_id: str | None = None,
                            turn_id: str | None = None) -> dict:
        state = self.state
        message = state["inbox"].get(identifier)
        if not message or message["state"] not in ("delivering", "uncertain", "acknowledged", "applied"):
            raise JournalError("Message has no delivery to acknowledge")
        if request_id is not None and message["delivery"]["request_id"] != request_id:
            raise JournalError("Acknowledgement belongs to a different delivery request")
        if message["state"] in ("acknowledged", "applied"):
            return copy.deepcopy(message)
        message.update(state="acknowledged", acknowledged_at=time.time_ns())
        if turn_id is not None:
            message["delivery"]["turn_id"] = _id(turn_id, "turn ID")
        self._event("message.acknowledged", {"id": identifier}, state)
        return copy.deepcopy(message)

    def reconcile_message(self, identifier: str, *, outcome: str, evidence: str) -> dict:
        """Host protocol hook; only positive absence evidence permits another send."""
        if outcome not in ("accepted", "not_received", "unknown") or not isinstance(evidence, str) or not evidence.strip() or len(evidence.encode()) > 4096:
            raise ValueError("A bounded explicit reconciliation outcome and evidence are required")
        state = self.state
        message = state["inbox"].get(identifier)
        if not message or message["state"] not in ("delivering", "uncertain"):
            raise JournalError("Message does not have an ambiguous delivery")
        message["reconciliation"] = {"outcome": outcome, "evidence": evidence, "at": time.time_ns()}
        message["state"] = {"accepted": "acknowledged", "not_received": "accepted", "unknown": "uncertain"}[outcome]
        if outcome == "accepted":
            message["acknowledged_at"] = time.time_ns()
        elif outcome == "not_received":
            # The old receipt remains in the immutable event log.
            message["delivery"] = None
        self._event("message.reconciled", {"id": identifier, "outcome": outcome}, state)
        return copy.deepcopy(message)

    def mark_applied(self, identifiers: list[str], workspace: Path | str, *, artifacts: list[str],
                     revision: int | None = None) -> None:
        state = self.state
        revision = state["input_revision"] if revision is None else _revision(revision)
        if revision != state["input_revision"] or not identifiers or len(set(identifiers)) != len(identifiers):
            raise JournalError("Applied message receipt requires the current revision and unique IDs")
        messages = []
        for identifier in identifiers:
            message = state["inbox"].get(identifier)
            if not message or message["state"] not in ("acknowledged", "applied"):
                raise JournalError("Message was not acknowledged by the runtime")
            messages.append(message)
        receipts = self.artifacts(workspace, artifacts)
        if any(message["changes_input"] for message in messages) and not receipts:
            raise JournalError("Applied corrections require validated artifact receipts")
        for message in messages:
            message.update(state="applied", applied_revision=revision, artifacts=receipts, applied_at=time.time_ns())
        # Cursors may have gaps in the server's global sequence. Never advance
        # past an accepted earlier message which has not actually been applied.
        for message in sorted(state["inbox"].values(), key=lambda m: m["cursor"]):
            if message["state"] != "applied":
                break
            state["applied_message_cursor"] = max(state["applied_message_cursor"], message["cursor"])
        self._event("message.applied", {"ids": identifiers, "revision": revision}, state)

    def public_status(self) -> dict:
        """Allowlisted telemetry; excludes text, paths, threads, leases and reasoning."""
        state = self.state

        def public_id(value: str | None) -> str | None:
            if value is None:
                return None
            if (any(secret in value for secret in self.secrets) or
                    re.search(r"(?:sk-|gh[pousr]_|github_pat_)", value, re.I)):
                return "[redacted]"
            return value if IDENTIFIER.fullmatch(value) else "[redacted]"

        return {
            "version": VERSION, "task_id": public_id(state["task_id"]), "run_id": public_id(state["run_id"]),
            "status": state["status"], "input_revision": state["input_revision"],
            "phase": public_id(state["phase"]["name"]) if state["phase"] else None,
            "next_phase": public_id(state["next_phase"]), "checkpoint_available": bool(state["snapshot_id"]),
            "message_cursor": state["message_cursor"], "applied_message_cursor": state["applied_message_cursor"],
            "messages": [{"id": public_id(m["id"]), "state": m["state"], "cursor": m["cursor"],
                          "revision": m["revision"], "applied_revision": m["applied_revision"]}
                         for m in sorted(state["inbox"].values(), key=lambda m: m["cursor"])],
            "recovery_count": len(state["recoveries"]),
        }
