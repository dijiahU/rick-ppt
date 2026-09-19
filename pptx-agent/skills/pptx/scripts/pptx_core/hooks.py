"""Best-effort lifecycle guardrails; export independently verifies every artifact."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from pathlib import Path

from .common import PptxError, atomic_json, now
from .manifest import changed_paths, high_risk, manifest
from .package import discover, export
from .snapshots import snapshot
from .validator import validate


def event_text(event):
    data = event.get("tool_input", {})
    return data if isinstance(data, str) else str(data.get("command", data.get("cmd", json.dumps(data))))


def is_patch(event):
    return event.get("tool_name") in {"apply_patch", "Edit", "Write"} or "*** Begin Patch" in event_text(event)


def mutation_paths(event):
    text = event_text(event)
    if is_patch(event):
        data = event.get("tool_input", {})
        paths = re.findall(r"^\*\*\* (?:Update File|Add File|Delete File|Move to): (.+)$", text, re.M)
        if isinstance(data, dict):
            paths += [str(data[k]) for k in ("file_path", "path") if k in data]
        return paths
    return []


def read_only(event):
    if is_patch(event):
        return False
    text = event_text(event)
    # A batch of independent reads is still read-only. Do not generalize this
    # to shell operators, substitutions, continuations or arbitrary programs.
    if re.search(r"[<>;|&`$\\]", text):
        return False
    commands = []
    for line in text.splitlines():
        try:
            tokens = shlex.split(line)
        except ValueError:
            return False
        if not tokens:
            continue
        if Path(tokens[0]).name not in {"cat", "head", "tail", "ls", "rg", "grep", "pwd", "stat", "file", "wc", "sha256sum", "shasum"}:
            return False
        if any(t.startswith("--pre") for t in tokens[1:]):
            return False
        commands.append(tokens)
    return bool(commands)


def denied(ws, event):
    cwd = Path(event.get("cwd", ".")).resolve()
    protected = [Path(ws.state["source"]), ws.home / "original.pptx"]
    paths = mutation_paths(event)
    for value in paths:
        target = (cwd / value).resolve()
        if any(target == p or p.is_relative_to(target) for p in protected):
            return "Do not modify the source PPTX or original.pptx; edit workspace OOXML."
    if is_patch(event) or read_only(event):
        return None
    text = event_text(event)
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = []
    # Shell is arbitrary code. Protect explicit paths and obvious destructive ancestor targets.
    destructive = bool(re.search(r"\b(rm|rmdir|mv|unlink|truncate|rmtree)\b", text))
    for token in tokens:
        if not token or token.startswith("-") or token in {";", "&&", "|", ">", ">>"}:
            continue
        target = (cwd / token).resolve()
        for p in protected:
            if target == p or (destructive and p.is_relative_to(target)):
                # Reading an original via unpack is a normal tool operation.
                if "unpack" in tokens and not destructive and not re.search(r"[>;|&`\n]", text):
                    continue
                return "Command may modify a protected PPTX. Use the unpacked workspace."
        if destructive and (target == ws.root or ws.root.is_relative_to(target)):
            return "Deleting or moving the active workspace is blocked; use snapshot/rollback."
    if any(str(p) in text or p.name in text for p in protected) and re.search(r"write|unlink|remove|rename|truncate|rmtree|[>]", text):
        return "Command may overwrite a protected original PPTX."
    return None


def record_path(ws, event):
    ident = json.dumps([event.get("session_id", ""), event.get("tool_use_id", ""), str(ws.home)])
    digest = hashlib.sha256(ident.encode()).hexdigest()
    base = Path(os.environ.get("PLUGIN_DATA", str(ws.home / "hook-data")))
    return base / "pre_tool" / (digest + ".json")


def pre(ws, event):
    reason = denied(ws, event)
    if reason:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}
    with ws.lock():
        ws.check_original()
        before = manifest(ws.root)
        paths = mutation_paths(event)
        # Opaque shell writers can touch any part. Checkpoint conservatively.
        risky = not read_only(event) and not is_patch(event)
        cwd = Path(event.get("cwd", ".")).resolve()
        for value in paths:
            p = (cwd / value).resolve()
            if p.is_relative_to(ws.root) and high_risk(p.relative_to(ws.root).as_posix()):
                risky = True
            if p.is_relative_to(ws.home / "interactive"):
                risky = True
        if risky:
            snapshot(ws, "pre-tool-high-risk-or-opaque-write")
        atomic_json(record_path(ws, event), {"manifest": before, "interactive_manifest": ws.sidecar_manifest(), "at": now()})
    return None


def post(ws, event):
    with ws.lock():
        record = record_path(ws, event)
        previous = json.loads(record.read_text()) if record.exists() else {"manifest": ws.state["baseline"]}
        before = previous["manifest"]
        after = ws.refresh()
        ws.check_original()
        changed = changed_paths(before, after)
        sidecar_changes = changed_paths(previous.get("interactive_manifest", ws.state["interactive_baseline"]), ws.sidecar_manifest())
        if not changed and not sidecar_changes:
            return None
        report = validate(ws.root)
        from .interactive_validate import validate_interactive
        report.errors.extend(validate_interactive(ws.root)["errors"])
        ws.state["last_validation"] = {"at": now(), "changed": changed, **report.to_dict()}
        ws.save()
        if not report.ok:
            return {"decision": "block", "reason": "PPTX validation failed:\n" + "\n".join(report.errors),
                    "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
                                           "Repair the reported OOXML issue. Broken state was retained."}}
    return None


def stop(ws, event):
    with ws.lock():
        ws.check_original()
        ws.refresh()
        if not ws.state["dirty"]:
            return None
        # Reset retries for a new user turn; continuing Stop calls share the budget.
        if not event.get("stop_hook_active"):
            ws.state["stop_failures"] = 0
            ws.save()
    try:
        from .interactive_ooxml import discover_content_addins
        from .interactive_validate import config
        if any(i.get("addinId") == config()["addinId"] for i in discover_content_addins(ws.root)):
            import uuid
            from .interactive_bundle import assemble_bundle
            bundle = assemble_bundle(ws, ws.home / "output" / ("interactive-" + uuid.uuid4().hex[:12]))
            return {"systemMessage": f"Interactive PPTX validated, tested and bundled: {bundle['bundle']}"}
        path = export(ws)
        return {"systemMessage": f"PPTX validated, rendered and exported: {path}"}
    except Exception as exc:
        with ws.lock():
            ws.state["stop_failures"] = ws.state.get("stop_failures", 0) + 1
            failures = ws.state["stop_failures"]
            ws.state["last_stop_error"] = str(exc)
            ws.save()
        reason = f"PPTX finalization failed ({failures}/3): {exc}"
        if failures < 3:
            return {"decision": "block", "reason": reason}
        return {"systemMessage": reason + f". No new output published. Recoverable workspace and snapshots: {ws.home}"}


def handle(kind, event):
    outputs = []
    for ws in discover(event.get("cwd", ".")):
        try:
            result = {"PreToolUse": pre, "PostToolUse": post, "Stop": stop}[kind](ws, event)
        except Exception as exc:
            reason = f"PPTX guardrail failed: {exc}"
            if kind == "PreToolUse":
                result = {"hookSpecificOutput": {"hookEventName": kind, "permissionDecision": "deny",
                                                "permissionDecisionReason": reason}}
            elif kind == "Stop":
                # Missing workspace/source errors must share the bounded retry policy.
                with ws.lock():
                    failures = ws.state.get("stop_failures", 0) + 1 if event.get("stop_hook_active") else 1
                    ws.state["stop_failures"] = failures
                    ws.save()
                result = {"decision": "block", "reason": reason} if failures < 3 else {"systemMessage": reason}
            else:
                result = {"decision": "block", "reason": reason}
        if result:
            outputs.append(result)
    if not outputs:
        return None
    denials = [o for o in outputs if o.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"]
    if denials:
        return denials[0]
    blocked = [o["reason"] for o in outputs if o.get("decision") == "block"]
    if blocked:
        return {"decision": "block", "reason": "\n".join(blocked)}
    return {"systemMessage": "\n".join(o.get("systemMessage", "") for o in outputs)}
