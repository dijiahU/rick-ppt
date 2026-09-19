"""Opt-in complete workflow smoke using actual Codex and renderers.

Only the leased website transport is synthetic. Research, authoring, native and
scene validation, three independent reviewer contexts, and portable packaging use
the production workflow. No live queue or runner settings are read. All generated
task folders, earlier candidates, and private host records are retained.

Run with the plugin Python and --out pointing to a NEW proof file. --gate-only
exercises the real runner's HTTP 412 completion retry without model calls.
"""
import argparse
from collections import Counter
import copy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import time
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, urlsplit
import uuid
import xml.etree.ElementTree as ET
import zipfile

import runner as bridge_source
import workflow as workflow_source
from admin_trace import AdminTrace
from conversation import Conversation, RevisionPending
from durable import Journal
from language import presentation_request
from interactive_host import verify_frozen, bundle_frozen
from progress import Reporter
from resilience import WorkerHTTPError
from trajectory import Trajectory


PLUGIN = Path(__file__).resolve().parents[1] / "pptx-agent"
BRIEF = """Create exactly two slides in English for a beginner learning a state
transition. Topic: one click adds one. Use only the supplied elementary example:
start with count 0; Increment adds exactly 1; two clicks produce 2; Reset returns
the count to 0. No external sources, images, video, internet research or invented
data are needed. Slide 1 is a native editable context page: explain the rule
count_next = count + 1 and the complete worked example 0 -> 1 -> 2, including what
Reset does. This simultaneous comparison should be visible on entry. Slide 2 is
the practice/closing page: retain an editable native title and useful instructions
outside a large shared-runtime interactive region. That region has a visible
number, an Increment button and a Reset button. Ask the learner to predict the
value after two clicks, then try it. Include meaningful browser tests that click
the actual controls and numerically assert count 1, count 2 and Reset count 0.
The static fallback must convey the rule and initial value without a runtime.
Use clear large text, restrained dark blue/white/teal styling, no decorative
imagery, and no separate cover or thank-you page. Use the normal native CLI and
declarative scene authoring path, actual renders and sidecar export. Keep all
original inputs and earlier exports. This is a small teaching deck, not a report
about software tests; do not put smoke-test or implementation jargon on slides.
"""


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def config():
    return {"site": "https://synthetic-site.invalid",
            "token": "SYNTHETIC-NONSECRET-" + uuid.uuid4().hex,
            "plugin": str(PLUGIN), "python": str(PLUGIN / ".venv/bin/python"),
            "blank": str(PLUGIN / "skills/pptx/assets/blank.pptx"),
            "job_timeout_seconds": 7200}


def task():
    return {"id": str(uuid.uuid4()), "lease": "SYNTHETIC-LEASE-" + uuid.uuid4().hex,
            "title": "One click adds one", "brief": BRIEF, "pages": 2,
            "style": "Clear dark blue, white and teal teaching slides",
            "language": "en", "mode": "create", "attachments": []}


class SyntheticLease:
    def __init__(self):
        self.checks, self.finished = 0, False
        self.last_notice = time.monotonic()
        self.started = self.last_notice

    def check(self):
        if self.finished:
            raise AssertionError("An already finished synthetic lease was reused")
        self.checks += 1
        if time.monotonic() - self.last_notice >= 45:
            self.last_notice = time.monotonic()
            print(json.dumps({"heartbeat": "full-workflow-smoke", "seconds": round(self.last_notice - self.started),
                              "lease_checks": self.checks}), flush=True)

    def finish(self):
        self.finished = True


class SyntheticSite:
    def __init__(self, task, host):
        self.task, self.host = task, host
        self.calls = Counter()
        self.rows, self.checkpoints, self.progress = [], [], []
        self.assistant, self.previews = {}, {}
        self.acks, self.applied = set(), set()
        self.completed, self.uploads = [], []
        self.completion_hook = None

    @property
    def revision(self):
        return max((row["seq"] for row in self.rows if row["kind"] == "revision"), default=0)

    def send(self, cfg, path, body=b"{}", lease=None, raw=False):
        route, query = urlsplit(path), parse_qs(urlsplit(path).query)
        action = query["action"][0]
        if (cfg["site"] != "https://synthetic-site.invalid" or lease != self.task["lease"] or
                route.path not in (f'/api/worker/{self.task["id"]}',
                                   f'/api/worker/{self.task["id"]}/conversation',
                                   f'/api/worker/{self.task["id"]}/bundle')):
            raise AssertionError("Synthetic API rejected a foreign route or lease")
        self.calls[action] += 1
        value = json.loads(body) if body and body[:1] in (b"{", b"[") else {}
        if action == "poll":
            return {"messages": copy.deepcopy(self.rows), "revision": self.revision}
        if action == "assistant":
            previous = self.assistant.setdefault(value["id"], value["body"])
            if previous != value["body"]:
                raise AssertionError("Assistant outbox reused an ID with different text")
        elif action == "ack":
            self.acks.update(value["ids"])
        elif action == "applied":
            self.applied.update(value["ids"])
        elif action == "checkpoint":
            self.checkpoints.append(value)
        elif action == "preview":
            assert body.startswith(b"\x89PNG\r\n\x1a\n")
            slide = int(query["slide"][0])
            self.previews[slide] = digest(body)
            folder = self.host / "website-previews"
            folder.mkdir(exist_ok=True)
            destination = folder / f"page-{slide}-{digest(body)[:16]}.png"
            if not destination.exists():
                destination.write_bytes(body)
        elif action == "progress":
            self.progress.append(value)
        elif action == "bundle":
            assert body.startswith(b"PK")
            self.uploads.append(digest(body))
        elif action == "complete":
            revision = int(query["revision"][0])
            if self.completion_hook:
                self.completion_hook(revision, body)
            if revision != self.revision or any(row["id"] not in self.applied for row in self.rows):
                raise WorkerHTTPError("complete", status=412, reason="New user input arrived before completion")
            self.completed.append({"revision": revision, "sha256": digest(body)})
        elif action not in ("trace", "heartbeat", "version"):
            raise AssertionError("Unexpected synthetic API action: " + action)
        return {"ok": True}


class MilestoneTrace(AdminTrace):
    def begin(self, stage, root):
        print(json.dumps({"phase": stage, "at": now()}), flush=True)
        super().begin(stage, root)

    def emit(self, kind, label, **kwargs):
        if kind in ("phase", "error") and kwargs.get("state") in ("completed", "failed"):
            print(json.dumps({"phase_event": label, "state": kwargs["state"], "at": now()}), flush=True)
        return super().emit(kind, label, **kwargs)


def delivery_window_gate(cfg, parent):
    """Actual final-upload runner loop; only model output and remote API are fake."""
    host = Path(tempfile.mkdtemp(prefix="delivery-window-gate-", dir=parent)).resolve()
    (host / "records").mkdir()
    job = bridge_source.prepare(cfg)
    item, lease = task(), SyntheticLease()
    site = SyntheticSite(item, host)
    row = {"seq": 1, "id": str(uuid.uuid4()), "role": "user", "kind": "revision",
           "body": "Change the practice prompt before delivery", "attachments": []}
    attempts, prior_retained = [], []
    with Journal(host / "journal", item["id"], plugin_version="0.2.0") as journal:
        def reject_first(revision, body):
            assert not lease.finished
            if not site.rows:
                site.rows.append(copy.deepcopy(row))
                assert revision == 0

        def synthetic_workflow(bridge, cfg, item, workspace, payload, current_lease, reporter, **kwargs):
            conversation = Conversation(cfg, item, workspace, journal, site.send, reporter=reporter)
            conversation.poll(force=True)
            attempts.append(conversation.server_revision)
            version = workspace / ("gate-candidate-" + str(len(attempts)) + ".pptx")
            version.write_bytes(b"PK-synthetic-candidate-" + str(len(attempts)).encode())
            if len(attempts) == 2:
                assert journal.state["inbox"][row["id"]]["state"] == "accepted"
                request_id = str(uuid.uuid4())
                journal.begin_delivery(row["id"], request_id, "synthetic-thread", "synthetic-turn")
                journal.acknowledge_message(row["id"], request_id=request_id, turn_id="synthetic-turn")
                conversation.validated([version.name])
                prior_retained.append((workspace / "gate-candidate-1.pptx").is_file())
            return {"artifact": version.read_bytes(), "revision": conversation.server_revision, "bundle": None}

        site.completion_hook = reject_first
        # This test does not archive the installed plugin, launch a child model,
        # or mutate actual source roots. The production upload/retry code is used.
        with mock.patch.object(bridge_source, "ROOT", host), mock.patch.object(bridge_source, "request", site.send), \
                mock.patch.object(workflow_source, "run_workflow", synthetic_workflow), \
                mock.patch.object(Trajectory, "runtime", lambda self: None):
            bridge_source._run_job_locked(cfg, item, lease, job, journal, None)
        return {"actual_runner_upload_loop": True, "old_revision_rejected": attempts == [0, 1],
                "only_current_revision_delivered": len(site.completed) == 1 and site.completed[0]["revision"] == 1,
                "late_revision_applied_before_finish": row["id"] in site.applied and lease.finished,
                "previous_candidate_preserved": prior_retained == [True],
                "complete_attempts": site.calls["complete"]}


def check_bundle(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        prefixes = {PurePosixPath(name).parts[0] for name in names}
        assert len(prefixes) == 1, "Portable bundle needs a single root"
        prefix = prefixes.pop() + "/"
        files = {name[len(prefix):]: name for name in names if not name.endswith("/")}
        for name in files:
            relative = PurePosixPath(name)
            assert not relative.is_absolute() and ".." not in relative.parts and "\\" not in name
        inventory = json.loads(archive.read(files["checksums.json"]))
        assert set(inventory) == set(files) - {"checksums.json"}
        for name, sha in inventory.items():
            assert digest(archive.read(files[name])) == sha, "Bundle checksum differs: " + name
        bundle = json.loads(archive.read(files["deck/bundle.json"]))
        verification = json.loads(archive.read(files["verification.json"]))
        assert digest(archive.read(files["presentation.pptx"])) == bundle["pptxHash"]
        assert verification["ok"] and verification["runtime_verified"]
        assert verification["powerpoint_playback_verified"] is False
        assert all(name in files for name in ("runtime/dist/preview.html", "scripts/start.command",
                                              "scripts/stop.command", "scripts/start.ps1", "scripts/stop.ps1"))
        assert all((archive.getinfo(files[name]).external_attr >> 16) & 0o100
                   for name in ("scripts/start.command", "scripts/stop.command"))
        scenes = [json.loads(archive.read(files["deck/" + entry["path"]])) for entry in bundle["scenes"].values()]
        assertions = [assertion for scene in scenes for test in scene.get("testPlan", [])
                      for assertion in test.get("assertions", [])]
        actions = [action for scene in scenes for test in scene.get("testPlan", [])
                   for action in test.get("actions", [])]
        expected = {assertion["equals"] for assertion in assertions
                    if assertion.get("type") == "state" and type(assertion.get("equals")) in (int, float)}
        meaningful = {0, 1, 2}.issubset(expected) and sum(action.get("type") == "click" for action in actions) >= 3
        return {"checksum_inventory_valid": True, "runtime_verified": True,
                "click_and_numeric_assertions_0_1_2": meaningful,
                "desktop_powerpoint_playback_verified": False, "files": len(files),
                "scene_count": len(bundle["scenes"]), "pptx_sha256": bundle["pptxHash"],
                "zip_sha256": digest(path.read_bytes()), "zip_bytes": path.stat().st_size}


def run(out, gate_only=False):
    out = Path(out).absolute()
    if out.exists():
        raise FileExistsError("Proof destination exists; select a fresh path")
    out.parent.mkdir(parents=True, exist_ok=True)
    host = Path(tempfile.mkdtemp(prefix="workflow-smoke-host-", dir=out.parent)).resolve()
    (host / "records").mkdir()
    cfg, item = config(), task()
    proof = {"schema": "pptx-full-workflow-smoke/v1", "passed": False, "started_at": now(),
             "mode": "delivery-gate-only" if gate_only else "actual-full-workflow",
             "cli_version": subprocess.run(["codex", "--version"], capture_output=True, text=True,
                                            timeout=10, check=True).stdout.strip(),
             "checks": {}, "host_records": str(host)}
    trace = trajectory = journal = None
    job = None
    try:
        gate = delivery_window_gate(cfg, host)
        proof["delivery_window_gate"] = gate
        proof["checks"]["final_upload_new_input_fence"] = all(v for v in gate.values() if type(v) is bool)
        if not gate_only:
            job = bridge_source.prepare(cfg)
            proof["task_workspace"] = str(job)
            site, lease = SyntheticSite(item, host), SyntheticLease()
            payload = presentation_request(item)
            payload["attachments"] = []
            (job / "request.json").write_text(json.dumps(payload, indent=2))
            bridge = SimpleNamespace(ROOT=host, request=site.send, environment=bridge_source.environment,
                                     prepare=bridge_source.prepare, sandbox=bridge_source.sandbox,
                                     render_requests=bridge_source.render_requests,
                                     run_with_renderer=bridge_source.run_with_renderer)
            reporter = Reporter(cfg, item, job, site.send, explicit_previews=True)
            trace = MilestoneTrace(cfg, item, site.send, host / "records")
            trajectory = Trajectory(cfg, item, host / "trajectory", trace=trace)
            journal = Journal(host / "journal", item["id"], plugin_version="0.2.0", run_id=trajectory.run_id)
            journal.checkpoint(job, reason="synthetic_inputs_ready")
            result = workflow_source.run_workflow(bridge, cfg, item, job, payload, lease, reporter,
                                                  trace=trace, trajectory=trajectory, journal=journal)
            reporter.flush(force=True, tick=lease.check)
            audit = json.loads(Path(result["workflow_audit"]).read_bytes())
            receipt = audit["final_review"]
            stages = audit["budget"]["stages"]
            proof["stages"] = [{key: stage[key] for key in ("name", "seconds", "transport", "resumed") if key in stage}
                               for stage in stages]
            proof["review_round"] = receipt["round"]
            checks = proof["checks"]
            checks["actual_research_and_author_completed"] = {"research", "author"}.issubset({s["name"] for s in stages})
            checks["all_model_stages_have_native_usage_receipts"] = all(s.get("usage") for s in stages)
            checks["three_independent_review_contexts"] = all(
                len({s["thread"] for s in stages if s["name"] in names}) == 3
                and result["thread"] not in {s["thread"] for s in stages if s["name"] in names}
                for names in [{f'content-first-{receipt["round"]}', f'content-evidence-{receipt["round"]}', f'visual-{receipt["round"]}'}])
            checks["every_final_reviewer_covers_both_pages"] = all(receipt[k]["pages_reviewed"] == [1, 2]
                                                                         for k in ("content_first_view", "content", "visual"))
            checks["no_required_final_review_findings"] = not any(
                f["severity"] == "required" for k in ("content", "visual") for f in receipt[k]["findings"])
            checks["delivered_bytes_match_independent_review"] = digest(result["artifact"]) == receipt["artifact_sha256"]
            with zipfile.ZipFile(io.BytesIO(result["artifact"])) as archive:
                slides = sorted(name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
                checks["exactly_two_native_slides"] = len(slides) == 2
                native = ET.fromstring(archive.read(slides[0]))
                ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
                      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
                text = " ".join(el.text or "" for el in native.findall(".//a:t", ns))
                checks["editable_native_context_retained"] = len(text) >= 60 and len(native.findall(".//p:sp", ns)) >= 3
                checks["content_addin_in_exported_ooxml"] = any(name.startswith("ppt/slides/udata/") for name in archive.namelist())
            assert result["bundle"], "Interactive full-workflow smoke did not return its portable bundle"
            bundle = check_bundle(Path(result["bundle"]))
            proof["portable_bundle"] = bundle
            checks["portable_bundle_verified_and_complete"] = bundle["checksum_inventory_valid"] and bundle["runtime_verified"] and bundle["scene_count"] >= 1
            checks["bundle_contains_exact_reviewed_pptx_bytes"] = bundle["pptx_sha256"] == digest(result["artifact"])
            checks["real_controls_have_numeric_increment_and_reset_tests"] = bundle["click_and_numeric_assertions_0_1_2"]
            packets = [root / "review-packet/inventory.json" for root in trajectory.roots if (root / "review-packet/inventory.json").is_file()]
            inventories = [json.loads(path.read_bytes()) for path in packets]
            instances = [entry for inventory in inventories for entry in inventory.get("interactive", {}).get("instances", [])]
            proof["interactive_review_capture_count"] = sum(len(entry.get("captures", [])) for entry in instances)
            proof["interactive_runtime_test_count"] = sum(len(entry.get("runtime_tests", [])) for entry in instances)
            checks["host_captures_reach_independent_reviewers"] = bool(instances) and all(entry.get("captures") and entry.get("runtime_tests") for entry in instances)
            checks["native_previews_published"] = set(site.previews) == {1, 2}
            checks["delivery_ready_artifacts_reusable"] = journal.can_reuse("delivery-ready", job)
            checks["delivery_ready_checkpoint_published"] = any(c["phase"] == "delivery-ready" for c in site.checkpoints)
            checks["scoped_host_lease_checked"] = lease.checks >= 10
            checks["public_assistant_messages_exclude_credentials"] = bool(site.assistant) and all(
                cfg["token"] not in text and item["lease"] not in text for text in site.assistant.values())
            proof["lease_checks"] = lease.checks
            proof["fake_api_call_counts"] = dict(site.calls)
            proof["artifact_sha256"] = digest(result["artifact"])
            proof["artifact_bytes"] = len(result["artifact"])
            proof["delivery_bundle"] = result["bundle"]
            proof["review_summary"] = result["review_summary"]
            proof["workflow_audit"] = result["workflow_audit"]
            # Once frozen, a new message must invalidate reuse and interrupt an
            # isolated review/bundle tick. This uses the real conversation code.
            late = {"seq": 1, "id": str(uuid.uuid4()), "role": "user", "kind": "revision",
                    "body": "Change the exercise instruction before delivery", "attachments": []}
            site.rows.append(late)
            conversation = Conversation(cfg, item, job, journal, site.send, reporter=reporter)
            blocked = False
            try:
                conversation.poll(allow_steer=False, force=True)
            except RevisionPending:
                blocked = True
            checks["late_input_invalidates_frozen_delivery"] = blocked and not journal.can_reuse("delivery-ready", job)
            checks["late_input_preserves_existing_delivery"] = Path(result["bundle"]).is_file()
        proof["passed"] = bool(proof["checks"]) and all(proof["checks"].values())
    except Exception as error:
        proof["error_type"] = type(error).__name__
        proof["error"] = str(error).replace(cfg["token"], "[redacted]").replace(item["lease"], "[redacted]")
    finally:
        if trajectory:
            trajectory.finish("complete" if proof["passed"] else "failed", job)
        if trace:
            trace.close()
        if journal:
            journal.close()
        proof["finished_at"] = now()
        with out.open("x") as stream:
            json.dump(proof, stream, indent=2)
        print(json.dumps(proof, indent=2), flush=True)
    return proof["passed"]


def reverify_reviewed(source, out):
    """Fresh host/browser/native verification of a preserved reviewed candidate.

    Used after changes confined to bundling/host gates. It makes no model calls
    and does not imply that the original author/reviewer phases were repeated.
    """
    source, out = Path(source).absolute(), Path(out).absolute()
    if out.exists():
        raise FileExistsError('Proof destination exists; choose a fresh path')
    source_bytes = source.read_bytes()
    previous = json.loads(source_bytes)
    if previous.get('passed') is not True or previous.get('mode') != 'actual-full-workflow':
        raise ValueError('A passed actual full-workflow proof is required')
    cfg = config()
    author = Path(previous['task_workspace'])
    old_bundle = Path(previous['delivery_bundle'])
    old_presentation = old_bundle.parent / 'presentation.pptx'
    reviewed = old_presentation.read_bytes()
    if digest(reviewed) != previous['artifact_sha256']:
        raise ValueError('Preserved reviewed artifact changed')
    delivery = json.loads((author / 'delivery.json').read_bytes())
    out.parent.mkdir(parents=True, exist_ok=True)
    frozen, lease = bridge_source.prepare(cfg), SyntheticLease()
    proof = {'schema': 'pptx-reviewed-bundle-followup/v1', 'passed': False, 'started_at': now(),
             'mode': 'fresh-host-verification-of-preserved-reviewed-artifact', 'model_calls': 0,
             'source_full_workflow_proof': str(source), 'source_proof_sha256': digest(source_bytes),
             'frozen_workspace': str(frozen), 'checks': {}}
    try:
        (frozen / 'result.pptx').write_bytes(reviewed)
        cli = str(PLUGIN / 'skills/pptx/scripts/pptx.py')
        unpacked = json.loads(bridge_source.run_with_renderer(cfg, frozen,
            bridge_source.sandbox(cfg, frozen, [cfg['python'], cli, 'unpack', str(frozen / 'result.pptx')]), tick=lease.check))
        workspace = unpacked['workspace']
        verification = verify_frozen(cfg, author, delivery, frozen, workspace, tick=lease.check)
        validation = json.loads(bridge_source.run_with_renderer(cfg, frozen,
            bridge_source.sandbox(cfg, frozen, [cfg['python'], cli, '-w', workspace, 'validate', '--level', '3']), tick=lease.check))
        result = bundle_frozen(cfg, frozen, workspace, verification, 'reviewed-delivery', tick=lease.check,
                               native_service=lambda: bridge_source.render_requests(frozen))
        bundle = check_bundle(Path(result['zip']))
        checks = proof['checks']
        checks['reviewed_native_bytes_unchanged'] = digest(reviewed) == verification['reviewed_pptx_sha256']
        checks['fresh_native_render_has_two_pages'] = len(validation['render']['pages']) == 2
        checks['fresh_host_scene_tests_pass'] = verification['runtime_verified'] and all(
            report['ok'] and report['testCount'] > 0 and all(t['assertions'] > 0 for t in report['tests'])
            for report in verification['reports'].values())
        checks['host_published_exact_reviewed_identity'] = result['exact_reviewed_pptx'] and result['pptx_sha256'] == previous['artifact_sha256']
        checks['portable_zip_has_exact_reviewed_pptx_bytes'] = bundle['pptx_sha256'] == previous['artifact_sha256'] and Path(result['pptx']).read_bytes() == reviewed
        checks['portable_checksums_and_numeric_tests_verified'] = bundle['checksum_inventory_valid'] and bundle['click_and_numeric_assertions_0_1_2']
        checks['previous_full_proof_preserved'] = source.read_bytes() == source_bytes
        checks['previous_native_and_bundle_preserved'] = old_presentation.read_bytes() == reviewed and digest(old_bundle.read_bytes()) == previous['portable_bundle']['zip_sha256']
        proof['portable_bundle'] = bundle
        proof['delivery_bundle'] = result['zip']
        proof['reviewed_artifact_sha256'] = previous['artifact_sha256']
        proof['fresh_native_previews'] = validation['render']['pages']
        proof['scene_reports'] = [{key: report[key] for key in ('directory', 'captures', 'testCount', 'specHash')}
                                  for report in verification['reports'].values()]
        proof['lease_checks'] = lease.checks
        proof['passed'] = all(checks.values())
    except Exception as error:
        proof['error_type'], proof['error'] = type(error).__name__, str(error)
    finally:
        proof['finished_at'] = now()
        with out.open('x') as stream:
            json.dump(proof, stream, indent=2)
        print(json.dumps(proof, indent=2), flush=True)
    return proof['passed']


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--gate-only", action="store_true")
    parser.add_argument("--reverify-reviewed", type=Path,
                        help="New host verification/bundle proof for an existing passed full-workflow candidate; no model calls")
    args = parser.parse_args()
    if args.gate_only and args.reverify_reviewed:
        parser.error('--gate-only and --reverify-reviewed are mutually exclusive')
    passed = reverify_reviewed(args.reverify_reviewed, args.out) if args.reverify_reviewed else run(args.out, args.gate_only)
    raise SystemExit(0 if passed else 1)
