import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.render
def test_real_process_inspect_error_repair_render_stop_export(ws):
    def command(*args):
        result = subprocess.run([sys.executable, str(ROOT / "skills/pptx/scripts/pptx.py"),
                                 "-w", str(ws.home), *args], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    path = ws.root / "ppt/slides/slide1.xml"
    event = {"cwd": str(ws.home.parent.parent), "session_id": "e2e", "tool_use_id": "edit",
             "tool_name": "apply_patch", "tool_input": {"command": f"*** Begin Patch\n*** Update File: {path}\n*** End Patch"}}

    def hook(name):
        result = subprocess.run([sys.executable, str(ROOT / "hooks" / (name + ".py"))],
                                input=json.dumps(event), capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout) if result.stdout.strip() else None

    assert "Original title 1" in command("inspect", "1")["shapes"][0]["text"]
    raw = path.read_bytes()
    assert hook("pre_tool") is None
    path.write_bytes(raw + b"<broken>")
    assert hook("post_tool")["decision"] == "block"
    assert path.read_bytes().endswith(b"<broken>")
    event["tool_use_id"] = "repair"
    assert hook("pre_tool") is None
    path.write_bytes(raw.replace(b"Original title 1", b"Verified end-to-end"))
    assert hook("post_tool") is None
    assert command("validate")["ok"]
    preview = command("render", "1")
    assert Path(preview["pages"][0]).is_file()
    final = hook("stop")
    assert "exported" in final["systemMessage"]
    state = json.loads(ws.state_path.read_text())
    assert Path(state["latest_output"]).is_file()
    assert not state["dirty"]
