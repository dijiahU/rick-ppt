import json
import subprocess
import sys
from pathlib import Path

import pytest

from pptx_core.hooks import handle
from pptx_core.package import Workspace

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "skills/pptx/scripts/pptx.py"


def event(ws, command, tool="Bash", **extra):
    return {"cwd": str(ws.home.parent.parent), "tool_name": tool, "tool_input": {"command": command},
            "session_id": "test", "tool_use_id": "test-call", **extra}


@pytest.mark.parametrize("command", ["rm {source}", "mv {source} other.pptx", "echo bad > {source}",
                                     "sed -i x {source}", "rm -rf {home}"])
def test_pre_protects_original(ws, command):
    import shlex
    cmd = command.format(source=shlex.quote(ws.state["source"]), home=shlex.quote(str(ws.home)))
    result = handle("PreToolUse", event(ws, cmd))
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pre_allows_read_original(ws):
    import shlex
    assert handle("PreToolUse", event(ws, "cat " + shlex.quote(ws.state["source"]))) is None


@pytest.mark.parametrize("command", ["ls -l {source}\nrg -n pattern .", "\npwd\nstat {source}\n", "cat {source}\nsha256sum {source}"])
def test_pre_allows_read_batches(ws, command):
    import shlex
    assert handle("PreToolUse", event(ws, command.format(source=shlex.quote(ws.state['source'])))) is None


@pytest.mark.parametrize("command", ["ls {source}\nrm {source}", "pwd\nmv {source} other.pptx", "cat {source} > {source}", "ls $(rm {source})", "ls {source}; rm {source}", "rg --pre=writer x {source}", "cat <(rm {source})"])
def test_read_batch_does_not_allow_writes(ws, command):
    import shlex
    result = handle("PreToolUse", event(ws, command.format(source=shlex.quote(ws.state['source']))))
    assert result['hookSpecificOutput']['permissionDecision'] == 'deny'


def test_high_risk_snapshot(ws):
    patch = f"*** Begin Patch\n*** Update File: {ws.root}/ppt/presentation.xml\n@@\n-x\n+y\n*** End Patch"
    assert handle("PreToolUse", event(ws, patch, "apply_patch")) is None
    assert len(list((ws.home / "snapshots").iterdir())) == 1


def test_post_error_and_self_repair(ws):
    p = ws.root / "ppt/slides/slide1.xml"
    original = p.read_text()
    e = event(ws, f"*** Begin Patch\n*** Update File: {p}\n*** End Patch", "apply_patch")
    assert handle("PreToolUse", e) is None
    p.write_text(original + "<")
    assert handle("PostToolUse", e)["decision"] == "block"
    assert p.read_text().endswith("<")  # no silent rollback
    assert Workspace(ws.home).state["dirty"]
    assert handle("PreToolUse", e) is None
    p.write_text(original.replace("Original title 1", "Repaired title"))
    assert handle("PostToolUse", e) is None
    assert Workspace(ws.home).state["last_validation"]["ok"]


def test_stop_bounded_failures(ws):
    p = ws.root / "ppt/slides/slide1.xml"
    p.write_text(p.read_text() + "<")
    for index in range(3):
        result = handle("Stop", event(ws, "", stop_hook_active=index > 0))
        if index < 2:
            assert result["decision"] == "block"
        else:
            assert "systemMessage" in result
    assert Workspace(ws.home).state["stop_failures"] == 3
    assert Workspace(ws.home).state["latest_output"] is None


def test_cli_navigation_and_hook_entrypoint(ws):
    for args in (["list", "slides"], ["list", "charts"], ["list", "masters"], ["list", "media"],
                 ["find", "Original title 2"], ["inspect", "2"], ["refs", "ppt/slides/slide1.xml"],
                 ["refs", "rId2", "--from", "ppt/slides/slide1.xml"],
                 ["refs", "ppt/media/image1.png", "--reverse"], ["validate"], ["diff"], ["snapshot"]):
        proc = subprocess.run([sys.executable, str(CLI), "-w", str(ws.home), *args], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        json.loads(proc.stdout)
    proc = subprocess.run([sys.executable, str(ROOT / "hooks/pre_tool.py")],
                          input=json.dumps(event(ws, f"rm '{ws.state['source']}'")), text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
