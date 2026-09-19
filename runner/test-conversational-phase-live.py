"""Opt-in real Execution.phase smoke with a synthetic lease-fenced website.

Runs actual Codex, the Docker native renderer and the host Chromium scene broker.
No live queue is contacted, no host settings/credentials are read, and generated
files are retained. Invoke explicitly with --out pointing to a NEW proof file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import uuid

import runner as bridge_source
from admin_trace import AdminTrace
from durable import Journal
from progress import Reporter
from trajectory import Trajectory
from workflow import Execution


PLUGIN = Path(__file__).resolve().parents[1] / "pptx-agent"


class SyntheticSite:
    def __init__(self, task, job):
        self.task, self.job = task, job
        self.calls, self.assistant, self.acks, self.applied, self.checkpoints = [], {}, set(), set(), []
        self.revision_id, self.chat_id = str(uuid.uuid4()), str(uuid.uuid4())
        self.file_id = str(uuid.uuid4())
        self.attachment = b"Synthetic reference: the expected correction marker is PHASE_STEER_RECEIVED."
        self.rows = [
            {"seq": 1, "id": self.revision_id, "role": "user", "kind": "revision", "body":
             "Live correction: after phase_smoke.py finishes, create corrected.txt with exactly PHASE_STEER_RECEIVED. Preserve all existing files. This small change is the requested modification; complete the renderer smoke first.",
             "attachments": [{"id": self.file_id, "name": "reference.txt", "ext": "txt", "size": len(self.attachment), "sha256": hashlib.sha256(self.attachment).hexdigest()}]},
            {"seq": 2, "id": self.chat_id, "role": "user", "kind": "chat", "body":
             "What did the native and interactive rendering checks just verify? Briefly answer in the final reply, using PHASE_CHAT_ANSWERED as a marker.", "attachments": []},
        ]

    def send(self, cfg, path, body=b"{}", lease=None, raw=False):
        if lease != self.task["lease"] or not urlsplit(path).path.startswith(f'/api/worker/{self.task["id"]}'):
            raise AssertionError("Synthetic website rejected an unfenced request")
        query = parse_qs(urlsplit(path).query)
        action = query["action"][0]
        value = json.loads(body) if body and body[:1] in (b"{", b"[") else {}
        self.calls.append(action)
        if action == "poll":
            ready = (self.job / "ready-for-steering.txt").exists()
            return {"messages": self.rows if ready else [], "revision": 1 if ready else 0}
        if action == "attachment":
            if query.get("message") != [self.revision_id] or query.get("file") != [self.file_id] or not raw:
                raise AssertionError("Synthetic website rejected a foreign attachment")
            return self.attachment
        if action == "assistant":
            previous = self.assistant.setdefault(value["id"], value["body"])
            if previous != value["body"]: raise AssertionError("Assistant idempotency conflict")
        elif action == "ack": self.acks.update(value["ids"])
        elif action == "applied": self.applied.update(value["ids"])
        elif action == "checkpoint": self.checkpoints.append(value)
        return {"ok": True}


def run(out):
    out = Path(out).absolute()
    if out.exists(): raise FileExistsError("Proof destination exists")
    out.parent.mkdir(parents=True, exist_ok=True)
    host = Path(tempfile.mkdtemp(prefix="phase-smoke-host-", dir=out.parent)).resolve()
    (host / "records").mkdir()
    cfg = {"site": "https://synthetic-site.invalid", "token": "SYNTHETIC-NONSECRET-" + uuid.uuid4().hex,
           "plugin": str(PLUGIN), "python": str(PLUGIN / ".venv/bin/python"),
           "blank": str(PLUGIN / "skills/pptx/assets/blank.pptx"), "job_timeout_seconds": 1800}
    job = bridge_source.prepare(cfg)
    (job / "native-preview").mkdir()
    scene = {"schemaVersion": 1, "id": "phase-smoke", "viewport": {"width": 640, "height": 360},
             "initialState": {"count": 0}, "nodes": [
                 {"id": "counter", "type": "Button", "props": {"x": 20, "y": 20, "width": 160, "height": 50, "text": "Increment"}},
                 {"id": "value", "type": "Text", "props": {"x": 20, "y": 90, "width": 180, "height": 50}, "bind": {"text": {"expr": "state.count"}}}],
             "interactions": [{"target": "counter", "event": "click", "actions": [{"type": "increment", "path": "count"}]}],
             "testPlan": [{"name": "increment", "actions": [{"type": "click", "target": "counter"}], "assertions": [{"type": "state", "path": "count", "equals": 1}]}]}
    (job / "smoke.scene.json").write_text(json.dumps(scene))
    script = """import json,os,pathlib,subprocess,sys,time
root=pathlib.Path.cwd()
assert os.environ.get('PPTX_INTERACTIVE_PROXY')==str(root/'interactive-proxy.py')
assert os.environ.get('PPTX_SOFFICE')==str(root/'soffice-proxy.py')
(root/'ready-for-steering.txt').write_text('ready')
time.sleep(7)
native=subprocess.run([sys.executable,str(root/'soffice-proxy.py'),'--headless','--convert-to','pdf','--outdir',str(root/'native-preview'),str(root/'blank.pptx')],capture_output=True,text=True,timeout=110)
(root/'native-status.json').write_text(json.dumps({'returncode':native.returncode,'pdf_exists':(root/'native-preview/blank.pdf').is_file()}))
assert native.returncode==0,native.stderr
render=subprocess.run([sys.executable,RENDER,str(root/'smoke.scene.json'),'--out',str(root/'interactive-result')],capture_output=True,text=True,timeout=300)
(root/'interactive-status.json').write_text(json.dumps({'returncode':render.returncode,'stderr':render.stderr[-1000:]}))
assert render.returncode==0,render.stderr
report=json.loads(render.stdout)
assert report['runtime_verified'] and report['testCount']==1
print('PHASE_PROXIES_VERIFIED')
""".replace("RENDER", repr(str(PLUGIN / "skills/pptx/scripts/interactive_render.py")))
    (job / "phase_smoke.py").write_text(script)
    task = {"id": str(uuid.uuid4()), "lease": "SYNTHETIC-LEASE-" + uuid.uuid4().hex,
            "title": "Workflow transport and broker smoke", "brief": "Synthetic integration test", "pages": 1, "language": "en"}
    site = SyntheticSite(task, job)
    bridge = SimpleNamespace(ROOT=host, request=site.send, environment=bridge_source.environment,
                             render_requests=bridge_source.render_requests)
    checks = []
    lease = SimpleNamespace(check=lambda: checks.append(time.monotonic()))
    reporter = Reporter(cfg, task, job, site.send, explicit_previews=True)
    trace = AdminTrace(cfg, task, site.send, host / "records")
    trajectory = Trajectory(cfg, task, host / "trajectory", trace=trace)
    journal = Journal(host / "journal", task["id"], plugin_version="0.2.0", run_id=trajectory.run_id)
    proof = {"schema": "pptx-conversational-phase-smoke/v1", "passed": False,
             "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "cli_version": subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=10).stdout.strip()}
    result = None
    try:
        journal.checkpoint(job, reason="smoke_initial")
        execution = Execution(bridge, cfg, task, job, lease, reporter, trace=trace, trajectory=trajectory, journal=journal)
        prompt = ("This is an isolated integration smoke, not a presentation authoring request. Run exactly " +
                  cfg["python"] + " phase_smoke.py in the task directory. It exercises the task-local native and interactive render proxies while the host maintains their brokers. "
                  "Follow any live user revision/chat received during the command. Do not alter the test script, renderer inputs, existing artifacts or any source code. "
                  "Do not browse, generate images, make network requests or inspect other files. After the script and any live correction finish, reply concisely with PHASE_COMPLETE and answer the chat.")
        result, thread = execution.phase("transport-proxy-smoke", prompt, timeout=420)
        receipts = ["native-preview/blank.pdf", "native-status.json", "interactive-result/report.json", "corrected.txt"]
        proof["actual_phase_completed"] = bool(result)
        proof["live_revision_acknowledged_before_validation"] = journal.state["inbox"][site.revision_id]["state"] == "acknowledged"
        proof["chat_answered_after_completed_turn"] = journal.state["inbox"][site.chat_id]["state"] == "applied" and any("PHASE_CHAT_ANSWERED" in text for text in site.assistant.values())
        proof["correction_artifact"] = (job / "corrected.txt").read_text().strip() == "PHASE_STEER_RECEIVED"
        native = json.loads((job / "native-status.json").read_text())
        interactive = json.loads((job / "interactive-result/report.json").read_text())
        proof["native_proxy_rendered_pdf"] = native["returncode"] == 0 and native["pdf_exists"] and (job / "native-preview/blank.pdf").read_bytes().startswith(b"%PDF-")
        proof["interactive_proxy_verified_real_state_change"] = interactive["runtime_verified"] and interactive["testCount"] == 1
        proof["interactive_captures"] = len(interactive["captures"])
        proof["lease_checks_during_phase"] = len(checks)
        proof["trajectory_thread_receipt"] = trajectory.thread == thread
        proof["normalized_usage_receipt"] = execution.stages[-1]["usage"] is not None
        proof["public_reply_count"] = len(site.assistant)
        proof["attachment_transfer_verified"] = "attachment" in site.calls
        journal.complete_phase("transport-proxy-smoke", job, artifacts=receipts, next_phase="verification",
                               revision=journal.state["input_revision"], require_applied=False)
        execution.conversation.validated(receipts)
        execution.conversation.checkpoint(phase="verified", force=True)
        proof["revision_applied_only_after_verification"] = journal.state["inbox"][site.revision_id]["state"] == "applied" and site.revision_id in site.applied
        proof["checkpoint_published"] = bool(site.checkpoints)
        proof["phase_artifact_receipts_reusable"] = journal.can_reuse("transport-proxy-smoke", job)
        proof["public_credentials_excluded"] = all(cfg["token"] not in text and task["lease"] not in text for text in site.assistant.values())
        required = [value for key, value in proof.items() if type(value) is bool and key != "passed"]
        proof["passed"] = bool(required) and all(required)
    except Exception as error:
        proof["error_type"] = type(error).__name__
        proof["error"] = str(error).replace(cfg["token"], "[redacted]").replace(task["lease"], "[redacted]").replace(str(job), "$TASK")
    finally:
        trajectory.finish("complete" if proof["passed"] else "failed", job)
        trace.close()
        journal.close()
        proof["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with out.open("x") as stream: json.dump(proof, stream, indent=2)
        print(json.dumps(proof, indent=2))
        print("Retained synthetic task:", job)
        print("Retained host proof records:", host)
    return proof["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.out) else 1)
