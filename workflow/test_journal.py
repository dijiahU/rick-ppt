"""Run: python3.11 -m unittest discover -s workflow -p 'test_journal.py' -v."""
import copy
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from journal import (AlreadyRecovered, CorruptJournal, Journal, JournalBusy,
                     JournalError, Limits, VersionMismatch, safe_relative)


HERE = Path(__file__).resolve().parent


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pptx-journal-test-")
        self.base = Path(self.temporary.name)
        self.host = self.base / "private-host"
        self.job = self.base / "attempt-original"
        self.job.mkdir()
        (self.job / "deck.json").write_text('{"slides": []}')
        self.journal = None

    def tearDown(self):
        if self.journal:
            self.journal.close()
        self.temporary.cleanup()

    def open(self, **kwargs):
        self.journal = Journal(self.host, "task-123", plugin_version="0.2.0", **kwargs)
        return self.journal

    def start(self, **kwargs):
        journal = self.open(**kwargs)
        journal.begin_phase("author", self.job)
        journal.bind_session("thread-1", "turn-1")
        return journal

    def acknowledge(self, identifier="message-1", *, cursor=None, changes_input=True):
        j = self.journal
        j.accept_message(identifier, "Please clarify the diagram.", cursor=cursor, changes_input=changes_input)
        j.begin_delivery(identifier, "request-" + identifier, "thread-1", "turn-1")
        j.acknowledge_message(identifier, request_id="request-" + identifier)

    def test_completed_stage_restores_to_new_attempt_and_preserves_original(self):
        j = self.start()
        (self.job / "empty").mkdir()
        original = (self.job / "deck.json").read_bytes()
        receipt = j.complete_phase("author", self.job, artifacts=["deck.json"], next_phase="review")
        self.assertTrue(j.can_reuse("author", self.job))
        out = self.base / "recovered"
        plan = j.recover(out, plugin_version="0.2.0")
        self.assertEqual((out / "deck.json").read_bytes(), original)
        self.assertEqual((self.job / "deck.json").read_bytes(), original)
        self.assertTrue((out / "empty").is_dir())
        self.assertEqual(plan["next_phase"], "review")
        self.assertIsNone(plan["preferred_thread_id"], "A fresh review must not inherit the author thread")
        self.assertTrue(plan["validation_required"])
        self.assertFalse(plan["snapshot_atomic"])
        self.assertTrue(j.can_reuse("author", out))
        self.assertEqual(receipt["input_revision"], 0)

    def test_duplicate_lock_excludes_another_worker(self):
        self.open()
        with self.assertRaises(JournalBusy):
            Journal(self.host, "task-123", plugin_version="0.2.0")
        self.journal.close()
        with Journal(self.host, "task-123", plugin_version="0.2.0") as other:
            self.assertEqual(other.state["status"], "ready")

    def test_real_killed_worker_can_resume_thread_and_preserves_ambiguous_delivery(self):
        script = """
import sys, time
sys.path.insert(0, sys.argv[1])
from journal import Journal
j = Journal(sys.argv[2], 'task-123', plugin_version='0.2.0')
j.begin_phase('author', sys.argv[3])
j.bind_session('thread-before-kill', 'turn-before-kill')
j.checkpoint(sys.argv[3])
j.accept_message('message-1', 'Make the kernel visible')
j.begin_delivery('message-1', 'rpc-before-kill', 'thread-before-kill', 'turn-before-kill')
print('READY', flush=True)
time.sleep(60)
"""
        process = subprocess.Popen([sys.executable, "-c", script, str(HERE), str(self.host), str(self.job)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([process.stdout], [], [], 10)
            self.assertTrue(ready, "Subprocess did not reach durable checkpoint")
            self.assertEqual(process.stdout.readline().strip(), "READY")
            with self.assertRaises(JournalBusy):
                Journal(self.host, "task-123", plugin_version="0.2.0")
            process.send_signal(signal.SIGKILL)
            process.wait(timeout=10)
            self.assertEqual(process.returncode, -signal.SIGKILL)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdout.close()
            process.stderr.close()
        j = self.open()
        plan = j.recover(self.base / "after-kill", plugin_version="0.2.0")
        self.assertEqual(plan["preferred_thread_id"], "thread-before-kill")
        self.assertEqual(plan["next_phase"], "author")
        self.assertEqual(plan["uncertain_message_ids"], ["message-1"])
        self.assertEqual(j.pending_messages(), [])
        self.assertTrue((self.job / "deck.json").exists())

    def test_process_exit_between_event_commit_and_state_projection_is_replayed(self):
        j = self.start()
        j.close()
        script = """
import os, sys
sys.path.insert(0, sys.argv[1])
import journal
j = journal.Journal(sys.argv[2], 'task-123', plugin_version='0.2.0')
journal._atomic_projection = lambda *a: os._exit(91)
j.bind_session('thread-committed', 'turn-committed')
"""
        result = subprocess.run([sys.executable, "-c", script, str(HERE), str(self.host)], timeout=10)
        self.assertEqual(result.returncode, 91)
        j = self.open()
        self.assertEqual(j.state["phase"]["thread_id"], "thread-committed")
        self.assertEqual(json.loads((j.root / "state.json").read_text())["state"], j.state)

    def test_artifact_mutation_prevents_stage_reuse(self):
        j = self.start()
        j.complete_phase("author", self.job, artifacts=["deck.json"], next_phase="review")
        (self.job / "deck.json").write_text("different")
        self.assertFalse(j.can_reuse("author", self.job))

    def test_user_revision_invalidates_completed_stage(self):
        j = self.start()
        j.complete_phase("author", self.job, artifacts=["deck.json"], next_phase="review")
        j.accept_message("message-1", "Make the kernel visible")
        self.assertFalse(j.can_reuse("author", self.job))
        self.assertFalse(j.can_reuse("author", self.job, revision=0))
        self.assertEqual(j.state["input_revision"], 1)

    def test_phase_completion_rejects_unapplied_or_stale_revision(self):
        j = self.start()
        self.acknowledge()
        with self.assertRaises(JournalError):
            j.complete_phase("author", self.job, artifacts=["deck.json"])
        with self.assertRaises(JournalError):
            j.complete_phase("author", self.job, artifacts=["deck.json"], revision=1)
        j.mark_applied(["message-1"], self.job, artifacts=["deck.json"])
        j.complete_phase("author", self.job, artifacts=["deck.json"], revision=1)
        self.assertTrue(j.can_reuse("author", self.job))

    def test_duplicate_message_does_not_advance_revision_or_append_event(self):
        j = self.open()
        first = j.accept_message("message-1", "Hello", cursor=7)
        sequence = j.state["sequence"]
        self.assertEqual(j.accept_message("message-1", "Hello", cursor=7), first)
        self.assertEqual(j.state["sequence"], sequence)
        self.assertEqual(j.state["input_revision"], 1)
        with self.assertRaises(JournalError):
            j.accept_message("message-1", "Changed", cursor=7)
        with self.assertRaises(JournalError):
            j.accept_message("message-1", "Hello", cursor=8)

    def test_cursor_monotonicity_does_not_require_global_sequence_contiguity(self):
        j = self.open()
        j.accept_message("m1", "One", cursor=10)
        j.accept_message("m2", "Two", cursor=27)
        with self.assertRaises(JournalError):
            j.accept_message("m3", "Three", cursor=26)
        self.assertEqual(j.state["message_cursor"], 27)

    def test_unknown_delivery_is_never_resent_without_positive_absence(self):
        j = self.start()
        j.accept_message("m1", "One")
        j.begin_delivery("m1", "rpc1", "thread-1", "turn-1")
        j.reconcile_message("m1", outcome="unknown", evidence="Thread receipt unavailable")
        self.assertEqual(j.pending_messages(), [])
        with self.assertRaises(JournalError):
            j.begin_delivery("m1", "rpc2", "thread-1")
        j.reconcile_message("m1", outcome="not_received", evidence="Protocol rejected request before acceptance")
        self.assertEqual([m["id"] for m in j.pending_messages()], ["m1"])
        j.begin_delivery("m1", "rpc2", "thread-1")
        j.reconcile_message("m1", outcome="accepted", evidence="Matching client message marker in thread items")
        self.assertEqual(j.pending_messages(), [])
        self.assertEqual(j.state["inbox"]["m1"]["state"], "acknowledged")

    def test_acknowledgement_must_match_delivery_request(self):
        j = self.open()
        j.accept_message("m1", "One")
        with self.assertRaises(JournalError):
            j.acknowledge_message("m1")
        j.begin_delivery("m1", "rpc1", "thread-1")
        with self.assertRaises(JournalError):
            j.acknowledge_message("m1", request_id="rpc2")
        j.acknowledge_message("m1", request_id="rpc1")
        seq = j.state["sequence"]
        j.acknowledge_message("m1", request_id="rpc1")
        self.assertEqual(j.state["sequence"], seq)

    def test_applied_requires_acknowledgement_and_artifact_evidence(self):
        j = self.start()
        j.accept_message("m1", "One")
        with self.assertRaises(JournalError):
            j.mark_applied(["m1"], self.job, artifacts=["deck.json"])
        j.begin_delivery("m1", "rpc1", "thread-1")
        j.acknowledge_message("m1")
        with self.assertRaises(JournalError):
            j.mark_applied(["m1"], self.job, artifacts=[])
        j.mark_applied(["m1"], self.job, artifacts=["deck.json"])
        self.assertEqual(j.public_status()["applied_message_cursor"], 1)

    def test_applied_cursor_never_skips_unapplied_message(self):
        j = self.start()
        self.acknowledge("m1", cursor=3)
        self.acknowledge("m2", cursor=10)
        j.mark_applied(["m2"], self.job, artifacts=["deck.json"])
        self.assertEqual(j.state["applied_message_cursor"], 0)
        j.mark_applied(["m1"], self.job, artifacts=["deck.json"])
        self.assertEqual(j.state["applied_message_cursor"], 10)

    def test_chat_does_not_invalidate_artifacts_and_can_finish_without_artifact(self):
        j = self.start()
        j.complete_phase("author", self.job, artifacts=["deck.json"], next_phase="review")
        self.acknowledge(changes_input=False)
        j.mark_applied(["message-1"], self.job, artifacts=[])
        self.assertEqual(j.state["input_revision"], 0)
        self.assertTrue(j.can_reuse("author", self.job))

    def test_restore_before_applied_edit_requires_reapplication_without_resending_message(self):
        j = self.start()
        j.checkpoint(self.job)
        self.acknowledge()
        (self.job / "deck.json").write_text('{"slides": ["corrected"]}')
        j.mark_applied(["message-1"], self.job, artifacts=["deck.json"])
        plan = j.recover(self.base / "older-checkpoint", plugin_version="0.2.0")
        self.assertEqual(plan["requires_reapplication_message_ids"], ["message-1"])
        self.assertEqual(plan["acknowledged_message_ids"], ["message-1"])
        self.assertEqual(j.state["applied_message_cursor"], 0)
        self.assertEqual(j.pending_messages(), [])

    def test_attachment_metadata_is_bounded_and_paths_are_scoped(self):
        j = self.open()
        attachment = {"id": "file-1", "path": "attachments/a.txt", "sha256": "0" * 64, "bytes": 10}
        j.accept_message("m1", "", attachments=[attachment])
        with self.assertRaises(ValueError):
            j.accept_message("m2", "", attachments=[{**attachment, "path": "../../secret"}])
        with self.assertRaises(ValueError):
            j.accept_message("m3", "", attachments=[{**attachment, "password": "do not accept arbitrary metadata"}])

    def test_corrupt_blob_rejected_before_creating_recovery_directory(self):
        j = self.start()
        snapshot = j.checkpoint(self.job)
        blob = j.root / "blobs" / snapshot["files"]["deck.json"]["sha256"]
        blob.write_bytes(b"corrupted")
        out = self.base / "refused"
        with self.assertRaises(CorruptJournal):
            j.recover(out, plugin_version="0.2.0")
        self.assertFalse(out.exists())

    def test_corrupt_snapshot_manifest_is_rejected(self):
        j = self.start()
        snapshot = j.checkpoint(self.job)
        path = j.root / "snapshots" / (snapshot["id"] + ".json")
        changed = copy.deepcopy(snapshot)
        changed["reason"] = "tampered"
        path.write_text(json.dumps(changed))
        with self.assertRaises(CorruptJournal):
            j.recover(self.base / "refused", plugin_version="0.2.0")

    def test_corrupt_event_hash_is_rejected(self):
        j = self.open()
        root = j.root
        j.close()
        path = sorted((root / "events").glob("*.json"))[0]
        event = json.loads(path.read_text())
        event["state"]["input_revision"] = 99
        path.write_text(json.dumps(event))
        with self.assertRaises(CorruptJournal):
            self.open()

    def test_missing_event_is_rejected(self):
        j = self.start()
        root = j.root
        j.close()
        paths = sorted((root / "events").glob("*.json"))
        # Renaming retains the source while simulating a missing committed event.
        paths[1].rename(root / "retained-missing-event.json")
        with self.assertRaises(CorruptJournal):
            self.open()

    def test_uncommitted_pending_event_does_not_replay(self):
        j = self.open()
        seq = j.state["sequence"]
        root = j.root
        j.close()
        (root / "events" / ".pending-crashed-write").write_bytes(b'{"partial":')
        j = self.open()
        self.assertEqual(j.state["sequence"], seq)
        self.assertTrue((root / "events" / ".pending-crashed-write").exists())

    def test_corrupt_projection_cannot_override_valid_events(self):
        j = self.open()
        root = j.root
        j.close()
        saved = json.loads((root / "state.json").read_text())
        saved["state"]["input_revision"] = 99
        (root / "state.json").write_text(json.dumps(saved))
        with self.assertRaises(CorruptJournal):
            self.open()

    def test_paths_reject_traversal_and_cross_platform_escapes(self):
        for path in ("", ".", "..", "../x", "/tmp/x", "a//b", "a/./b", "a/../b", "C:/x", "a\\b", "x\0"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_relative(path)
        self.assertEqual(str(safe_relative("a/说明.json")), "a/说明.json")

    def test_symlink_file_is_not_captured_or_hashed(self):
        j = self.open()
        (self.job / "link").symlink_to(self.job / "deck.json")
        with self.assertRaises((OSError, CorruptJournal)):
            j.checkpoint(self.job)
        with self.assertRaises((OSError, CorruptJournal)):
            j.artifacts(self.job, ["link"])
        self.assertIsNone(j.state["snapshot_id"])

    def test_symlink_directory_and_symlink_workspace_are_rejected(self):
        j = self.open()
        (self.job / "linked").symlink_to(self.base, target_is_directory=True)
        with self.assertRaises((ValueError, CorruptJournal)):
            j.checkpoint(self.job)
        (self.base / "linked-job").symlink_to(self.job, target_is_directory=True)
        with self.assertRaises(ValueError):
            j.begin_phase("author", self.base / "linked-job")

    def test_artifact_ancestor_symlink_is_rejected(self):
        j = self.open()
        (self.job / "linked").symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(OSError):
            j.artifacts(self.job, ["linked/attempt-original/deck.json"])

    def test_symlink_blob_is_rejected(self):
        j = self.start()
        snapshot = j.checkpoint(self.job)
        blob = j.root / "blobs" / snapshot["files"]["deck.json"]["sha256"]
        blob.rename(j.root / "retained-blob")
        blob.symlink_to(j.root / "retained-blob")
        with self.assertRaises(CorruptJournal):
            j.recover(self.base / "refused", plugin_version="0.2.0")

    def test_unsafe_manifest_paths_and_case_collisions_are_rejected(self):
        j = self.open()
        snapshot = j.checkpoint(self.job)
        malicious = copy.deepcopy(snapshot)
        malicious["files"]["../escape"] = malicious["files"].pop("deck.json")
        with self.assertRaises(CorruptJournal):
            j._validate_snapshot(malicious)
        malicious = copy.deepcopy(snapshot)
        malicious["files"]["DECK.JSON"] = malicious["files"]["deck.json"]
        with self.assertRaises(CorruptJournal):
            j._validate_snapshot(malicious)

    def test_file_and_total_limits_are_enforced(self):
        j = self.open(limits=Limits(file_bytes=8))
        with self.assertRaises(CorruptJournal):
            j.checkpoint(self.job)
        j.close()
        j = self.open(limits=Limits(file_bytes=1024, total_bytes=14))
        (self.job / "second").write_bytes(b"more")
        with self.assertRaises(CorruptJournal):
            j.checkpoint(self.job)

    def test_count_and_message_limits_are_enforced(self):
        j = self.open(limits=Limits(files=1, messages=1, message_bytes=10))
        (self.job / "second").write_bytes(b"more")
        with self.assertRaises(CorruptJournal):
            j.checkpoint(self.job)
        with self.assertRaises(ValueError):
            j.accept_message("m1", "a" * 11)
        j.accept_message("m1", "ok")
        with self.assertRaises(JournalError):
            j.accept_message("m2", "ok")

    def test_different_plugin_requires_explicit_migration_and_fresh_context(self):
        j = self.start()
        j.checkpoint(self.job)
        with self.assertRaises(VersionMismatch):
            j.recover(self.base / "refused", plugin_version="0.3.0")
        self.assertFalse((self.base / "refused").exists())
        plan = j.recover(self.base / "upgraded", plugin_version="0.3.0", allow_plugin_upgrade=True)
        self.assertTrue(plan["context_rebuild_required"])
        self.assertIsNone(plan["preferred_thread_id"])
        self.assertEqual(plan["input_revision"], 1)
        j.close()
        with self.assertRaises(VersionMismatch):
            self.open()
        self.journal = Journal(self.host, "task-123", plugin_version="0.3.0")

    def test_recovery_never_overwrites_existing_destination(self):
        j = self.start()
        j.checkpoint(self.job)
        out = self.base / "already-there"
        out.mkdir()
        sentinel = out / "keep.txt"
        sentinel.write_text("Keep existing user content")
        with self.assertRaises(FileExistsError):
            j.recover(out, plugin_version="0.2.0")
        self.assertEqual(sentinel.read_text(), "Keep existing user content")

    def test_recovery_request_id_is_idempotent_and_retains_original_attempt(self):
        j = self.start()
        j.checkpoint(self.job)
        first = self.base / "first"
        j.recover(first, plugin_version="0.2.0", recovery_id="resume-1")
        with self.assertRaises(AlreadyRecovered):
            j.recover(self.base / "duplicate", plugin_version="0.2.0", recovery_id="resume-1")
        self.assertFalse((self.base / "duplicate").exists())
        self.assertTrue((first / "deck.json").exists())
        self.assertTrue((self.job / "deck.json").exists())

    def test_public_status_contains_no_text_credentials_paths_or_private_thread_data(self):
        j = self.start(secrets=("host-secret-value",))
        j.accept_message("m1", "password=host-secret-value /Users/rick/private hidden reasoning")
        j.checkpoint(self.job)
        text = json.dumps(j.public_status())
        for secret in ("host-secret-value", "password", "/Users", str(self.job), "thread-1", "turn-1", "reasoning", "sha256"):
            self.assertNotIn(secret, text)
        j.begin_phase("host-secret-value", self.job)
        self.assertEqual(j.public_status()["phase"], "[redacted]")

    def test_state_property_is_a_copy_and_closed_journal_cannot_write(self):
        j = self.open()
        state = j.state
        state["input_revision"] = 999
        self.assertEqual(j.state["input_revision"], 0)
        j.close()
        with self.assertRaises(JournalError):
            j.accept_message("m1", "hello")

    def test_journal_cannot_be_captured_inside_workspace(self):
        self.journal = Journal(self.job / "host-journal", "task-123", plugin_version="0.2.0")
        with self.assertRaises(ValueError):
            self.journal.checkpoint(self.job)
        with self.assertRaises(ValueError):
            self.journal.begin_phase("author", self.job)

    def test_artifact_change_during_checkpoint_prevents_completion(self):
        j = self.start()
        checkpoint = j.checkpoint

        def changed(*args, **kwargs):
            (self.job / "deck.json").write_text("Changed during checkpoint")
            return checkpoint(*args, **kwargs)

        with patch.object(j, "checkpoint", changed), self.assertRaises(JournalError):
            j.complete_phase("author", self.job, artifacts=["deck.json"])
        self.assertNotIn("author", j.state["completed_stages"])


if __name__ == "__main__":
    unittest.main()
