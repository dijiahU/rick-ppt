"""Host conversation integration tests; no live queue, credentials or model calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import uuid

from conversation import Conversation, RevisionPending, _publish_task_file
from durable import Journal, JournalError, RPCError, TransportError
from resilience import WorkerHTTPError, request


def http2_failure(cfg, path, body, lease, raw):
    # Exercise the real HTTP classifier; no network call or live credential.
    with patch('resilience.subprocess.run', return_value=subprocess.CompletedProcess([], 16, b'200', b'HTTP2 framing error')):
        return request(cfg, path, body, lease, raw)


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now
    def advance(self, seconds=5): self.now += seconds


class Website:
    def __init__(self, task):
        self.task = task
        self.rows, self.calls = [], []
        self.attachments, self.assistant = {}, {}
        self.acks, self.applied, self.checkpoints = [], [], []
        self.failures = {}

    def send(self, cfg, path, body=b"{}", lease=None, raw=False):
        route = urlsplit(path)
        query = parse_qs(route.query)
        action = query["action"][0]
        value = json.loads(body)
        if route.path != f'/api/worker/{self.task["id"]}/conversation' or lease != self.task["lease"]:
            raise WorkerHTTPError(action, status=403, reason="Stale or foreign task lease")
        self.calls.append((action, value, query, raw))
        failures = self.failures.get(action, [])
        failure = failures.pop(0) if failures else None
        if failure == "retryable":
            raise WorkerHTTPError(action, status=503, retryable=True)
        if failure == "fatal":
            raise WorkerHTTPError(action, status=403, retryable=False)
        if failure == "http2":
            return http2_failure(cfg, path, body, lease, raw)
        if action == "poll":
            return {"messages": copy.deepcopy(self.rows), "revision": max((r["seq"] for r in self.rows if r["kind"] == "revision"), default=0)}
        if action == "attachment":
            key = (query["message"][0], query["file"][0])
            if key not in self.attachments:
                raise WorkerHTTPError(action, status=403, reason="Attachment belongs to a different message")
            return self.attachments[key]
        if action == "assistant":
            previous = self.assistant.setdefault(value["id"], value["body"])
            if previous != value["body"]:
                raise WorkerHTTPError(action, status=409, reason="Idempotency conflict")
        elif action == "ack":
            self.acks.append(value["ids"])
        elif action == "applied":
            self.applied.append(value)
        elif action == "checkpoint":
            self.checkpoints.append(value)
        else:
            raise AssertionError("Unexpected test action")
        if failure == "lost":
            raise WorkerHTTPError(action, curl=28, reason="Response lost after commit", retryable=True)
        if failure == "http2-lost":
            return http2_failure(cfg, path, body, lease, raw)
        return {"ok": True}


class Server:
    """Protocol fake with real Journal transitions, including uncertain writes."""
    def __init__(self):
        self.active_turns = {"thread-1": "turn-1"}
        self.completed_turns = {}
        self.deliveries, self.received = [], {}
        self.behavior = []
        self.reconciliations = []

    def deliver(self, journal, message_id, thread_id, active_turn_id=None):
        request_id = str(uuid.uuid4())
        journal.begin_delivery(message_id, request_id, thread_id, active_turn_id)
        behavior = self.behavior.pop(0) if self.behavior else "accepted"
        self.deliveries.append(message_id)
        if behavior == "late_rejected":
            self.active_turns.pop(thread_id, None)
            journal.reconcile_message(message_id, outcome="not_received", evidence="no active turn to steer")
            raise RPCError("turn/steer", {"code": -32600, "message": "no active turn to steer"})
        if behavior == "invalid_params":
            journal.reconcile_message(message_id, outcome="not_received", evidence="invalid params")
            raise RPCError("turn/steer", {"code": -32602, "message": "expectedTurnId mismatch"})
        turn_id = active_turn_id or "turn-next"
        self.received[message_id] = turn_id
        if behavior == "lost":
            journal.reconcile_message(message_id, outcome="unknown", evidence="Lost transport response")
            raise TransportError("Lost response")
        journal.acknowledge_message(message_id, request_id=request_id, turn_id=turn_id)
        return {"acknowledged": True, "turn_id": turn_id}

    def reconcile_delivery(self, journal, message_id):
        self.reconciliations.append(message_id)
        return journal.reconcile_message(message_id,
            outcome="accepted" if message_id in self.received else "unknown",
            evidence="Matching clientId" if message_id in self.received else "History unavailable")


class Reporter:
    def __init__(self): self.events, self.reviews = [], []
    def event(self, *args, **kwargs): self.events.append((args, kwargs))
    def review_state(self, kind, state): self.reviews.append((kind, state))


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pptx-conversation-test-")
        self.base = Path(self.temporary.name).resolve()
        self.job = self.base / "task"
        self.job.mkdir()
        (self.job / "deck.json").write_text('{"validated": true}')
        self.task = {"id": str(uuid.uuid4()), "lease": "synthetic-private-lease"}
        self.cfg = {"token": "synthetic-private-token", "site": "https://example.invalid"}
        self.journal = Journal(self.base / "host", self.task["id"], plugin_version="0.2.0")
        self.journal.begin_phase("author", self.job)
        self.clock, self.reporter = Clock(), Reporter()
        self.website, self.server = Website(self.task), Server()
        self.conversation = self.new_conversation()

    def tearDown(self):
        self.journal.close()
        self.temporary.cleanup()

    def new_conversation(self, job=None):
        return Conversation(self.cfg, self.task, job or self.job, self.journal,
                            self.website.send, reporter=self.reporter, clock=self.clock)

    def row(self, *, kind="revision", body="Make the convolution window visible", seq=1, attachments=None):
        return {"id": str(uuid.uuid4()), "seq": seq, "kind": kind, "body": body,
                "attachments": attachments or [], "role": "user", "status": "accepted"}

    def attachment(self, data=b"An untrusted reference.", *, name="reference.txt"):
        return {"id": str(uuid.uuid4()), "name": name, "ext": name.rsplit(".", 1)[-1],
                "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def poll(self, **kwargs):
        return self.conversation.poll(server=self.server, thread_id="thread-1", force=True, **kwargs)

    def test_accept_acknowledge_and_applied_are_distinct_durable_states(self):
        row = self.row(seq=11)
        self.website.rows = [row]
        self.conversation.poll(force=True)
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "accepted")
        self.assertFalse(self.website.acks)
        self.poll()
        self.conversation.flush(force=True)
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "acknowledged")
        self.assertTrue(any(row["id"] in ids for ids in self.website.acks))
        self.assertFalse(self.website.applied)
        self.conversation.validated(["deck.json"])
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "applied")
        self.assertEqual(self.website.applied[-1], {"ids": [row["id"]], "revision": 11})

    def test_repeated_poll_deduplicates_messages_revisions_and_runtime_delivery(self):
        row = self.row()
        self.website.rows = [row]
        self.poll()
        first_revision = self.journal.state["input_revision"]
        self.poll()
        self.assertEqual(self.journal.state["input_revision"], first_revision)
        self.assertEqual(self.server.deliveries, [row["id"]])

    def test_changed_content_under_same_id_is_rejected(self):
        row = self.row()
        self.website.rows = [row]
        self.poll()
        self.website.rows[0]["body"] = "Different content with the old ID"
        with self.assertRaises(JournalError): self.poll()
        self.assertEqual(self.server.deliveries, [row["id"]])

    def test_chat_does_not_advance_requirement_revision_and_completes_after_answer(self):
        row = self.row(kind="chat", body="How is progress?", seq=7)
        self.website.rows = [row]
        self.poll()
        self.assertEqual(self.journal.state["input_revision"], 0)
        self.assertEqual(self.conversation.server_revision, 0)
        self.conversation.complete_chats({})
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "acknowledged")
        self.conversation.complete_chats({("thread-1", "turn-1"): {"status": "completed"}})
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "applied")
        self.assertEqual(self.journal.state["inbox"][row["id"]]["artifacts"], {})

    def test_interrupted_or_failed_chat_turn_is_not_marked_answered(self):
        row = self.row(kind="chat", body="How is progress?")
        self.website.rows = [row]
        self.poll()
        for status in ("interrupted", "failed"):
            with self.subTest(status=status):
                self.conversation.complete_chats({("thread-1", "turn-1"): {"status": status}})
                self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "acknowledged")
        self.assertFalse(self.website.applied)

    def test_new_user_input_interrupts_review_before_transport_delivery(self):
        row = self.row()
        self.website.rows = [row]
        with self.assertRaises(RevisionPending): self.poll(allow_steer=False)
        self.assertEqual(self.server.deliveries, [])
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "accepted")

    def test_previously_accepted_input_cannot_be_steered_into_a_reviewer(self):
        row = self.row()
        self.website.rows = [row]
        self.conversation.accept(row)
        with self.assertRaises(RevisionPending): self.poll(allow_steer=False)
        self.assertEqual(self.server.deliveries, [])

    def test_reviewer_isolation_also_preserves_uncertain_inbox_without_replaying(self):
        row = self.row()
        self.website.rows = [row]
        self.conversation.accept(row)
        self.journal.begin_delivery(row["id"], "rpc-before-review", "thread-1", "turn-1")
        self.journal.reconcile_message(row["id"], outcome="unknown", evidence="Lost receipt")
        with self.assertRaises(RevisionPending): self.poll(allow_steer=False)
        self.assertEqual(self.server.deliveries, [])
        self.assertEqual(self.server.reconciliations, [])

    def test_actual_idle_steer_rejection_can_be_retried_once_on_next_poll(self):
        row = self.row()
        self.website.rows = [row]
        self.server.behavior = ["late_rejected", "accepted"]
        self.poll()
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "accepted")
        self.poll()
        self.assertEqual(self.server.deliveries, [row["id"], row["id"]])
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "acknowledged")

    def test_invalid_params_rejection_does_not_mark_applied(self):
        row = self.row()
        self.website.rows = [row]
        self.server.behavior = ["invalid_params"]
        self.poll()
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "accepted")
        self.assertFalse(self.website.applied)

    def test_lost_runtime_reply_reconciles_without_resending_instruction(self):
        row = self.row()
        self.website.rows = [row]
        self.server.behavior = ["lost"]
        with self.assertRaises(TransportError): self.poll()
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "uncertain")
        self.poll()
        self.assertEqual(self.server.deliveries, [row["id"]])
        self.assertEqual(self.server.reconciliations, [row["id"]])
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "acknowledged")

    def test_unresolved_receipt_prevents_silent_replay_or_application(self):
        row = self.row()
        self.website.rows = [row]
        self.conversation.accept(row)
        self.journal.begin_delivery(row["id"], "rpc1", "thread-1", "turn-1")
        with self.assertRaises(RuntimeError): self.poll()
        self.assertEqual(self.server.deliveries, [])
        with self.assertRaises(RevisionPending): self.conversation.validated(["deck.json"])

    def test_attachment_is_bound_to_message_task_and_lease_then_hashed(self):
        data = b"Reference: convolution uses a shared kernel."
        item = self.attachment(data)
        row = self.row(attachments=[item])
        self.website.attachments[(row["id"], item["id"])] = data
        self.website.rows = [row]
        self.poll()
        attached = self.journal.state["inbox"][row["id"]]["attachments"][0]
        self.assertEqual((self.job / attached["path"]).read_bytes(), data)
        call = next(call for call in self.website.calls if call[0] == "attachment")
        self.assertEqual(call[2]["message"], [row["id"]])
        self.assertEqual(call[2]["file"], [item["id"]])
        self.assertTrue(call[3])
        self.assertEqual(attached["sha256"], hashlib.sha256(data).hexdigest())

    def test_foreign_message_attachment_is_not_accepted(self):
        data = b"private reference"
        item = self.attachment(data)
        row = self.row(attachments=[item])
        self.website.attachments[(str(uuid.uuid4()), item["id"])] = data
        self.website.rows = [row]
        with self.assertRaises(WorkerHTTPError): self.poll()
        self.assertNotIn(row["id"], self.journal.state["inbox"])

    def test_wrong_task_lease_is_fatal_and_does_not_accept_input(self):
        self.conversation.task = {**self.task, "lease": "wrong-lease"}
        self.website.rows = [self.row()]
        with self.assertRaises(WorkerHTTPError): self.poll()
        self.assertFalse(self.journal.state["inbox"])

    def test_bad_attachment_hash_or_length_is_rejected_before_model_delivery(self):
        data = b"reference"
        item = self.attachment(data)
        row = self.row(attachments=[item])
        self.website.rows = [row]
        self.website.attachments[(row["id"], item["id"])] = b"different"
        with self.assertRaises(ValueError): self.poll()
        self.assertFalse(self.server.deliveries)
        self.assertNotIn(row["id"], self.journal.state["inbox"])

    def test_attachment_filename_is_display_data_never_a_path(self):
        data = b"reference"
        item = self.attachment(data, name="../../outside.txt")
        row = self.row(attachments=[item])
        self.website.rows = [row]
        self.website.attachments[(row["id"], item["id"])] = data
        self.poll()
        attached = self.journal.state["inbox"][row["id"]]["attachments"][0]
        self.assertEqual(attached["path"], f'conversation-assets/{row["id"]}/{item["id"]}.txt')
        self.assertFalse((self.base / "outside.txt").exists())

    def test_attachment_parent_symlink_cannot_escape_task(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.job / "conversation-assets").symlink_to(outside, target_is_directory=True)
        data = b"reference"
        item = self.attachment(data)
        row = self.row(attachments=[item])
        self.website.rows = [row]
        self.website.attachments[(row["id"], item["id"])] = data
        with self.assertRaises((ValueError, OSError)): self.poll()
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(self.journal.state["inbox"])

    def test_attachment_leaf_symlink_is_not_followed_or_replaced(self):
        data = b"reference"
        item = self.attachment(data)
        row = self.row(attachments=[item])
        parent = self.job / "conversation-assets" / row["id"]
        parent.mkdir(parents=True)
        outside = self.base / "outside.txt"
        outside.write_bytes(data)
        leaf = parent / (item["id"] + ".txt")
        leaf.symlink_to(outside)
        self.website.rows = [row]
        self.website.attachments[(row["id"], item["id"])] = data
        with self.assertRaises((ValueError, OSError)): self.poll()
        self.assertTrue(leaf.is_symlink())
        self.assertEqual(outside.read_bytes(), data)

    def test_existing_verified_attachment_is_reused_and_never_redownloaded(self):
        data = b"reference"
        item = self.attachment(data)
        row = self.row(attachments=[item])
        self.website.rows = [row]
        self.website.attachments[(row["id"], item["id"])] = data
        self.poll()
        self.poll()
        self.assertEqual(len([c for c in self.website.calls if c[0] == "attachment"]), 1)

    def test_lost_assistant_response_retries_same_id_after_reconnect(self):
        event = {"type": "assistant.message", "id": "assistant-1", "body": "The kernel animation is ready.", "complete": True}
        self.conversation.assistant(event, scope="author")
        identifier = next(iter(self.conversation.pending_public))
        self.website.failures["assistant"] = ["lost"]
        self.conversation.flush(force=True)
        self.assertIn(identifier, self.conversation.pending_public)
        self.assertEqual(len(self.website.assistant), 1)
        reconnected = self.new_conversation()
        self.assertIn(identifier, reconnected.pending_public)
        reconnected.flush(force=True)
        self.assertEqual(len(self.website.assistant), 1)
        calls = [c[1]["id"] for c in self.website.calls if c[0] == "assistant"]
        self.assertEqual(calls, [identifier, identifier])
        self.assertTrue((reconnected.outbox / (identifier + ".sent")).exists())
        self.assertFalse(self.new_conversation().pending_public)

    def test_partial_assistant_is_not_mistaken_for_completed_reply(self):
        self.conversation.assistant({"type": "assistant.message", "id": "i", "body": "Still working", "complete": False}, scope="author")
        self.conversation.flush(force=True)
        self.assertFalse(self.website.assistant)

    def test_http2_lost_assistant_response_keeps_durable_id_for_reconnect(self):
        self.conversation.assistant({"type":"assistant.message", "id":"http2-reply", "body":"The scene is ready.", "complete":True}, scope="author")
        identifier = next(iter(self.conversation.pending_public))
        self.website.failures["assistant"] = ["http2-lost"]
        self.conversation.flush(force=True)
        self.assertIn(identifier, self.conversation.pending_public)
        self.assertFalse((self.conversation.outbox / (identifier + ".sent")).exists())
        self.assertEqual(len(self.website.assistant), 1)
        reconnected = self.new_conversation()
        reconnected.flush(force=True)
        self.assertFalse(reconnected.pending_public)
        self.assertEqual(len(self.website.assistant), 1)
        self.assertEqual([call[1]["id"] for call in self.website.calls if call[0]=="assistant"], [identifier, identifier])
        self.assertTrue((reconnected.outbox / (identifier + ".sent")).exists())

    def test_public_assistant_redacts_credentials_paths_and_controls(self):
        body = "Here is " + self.cfg["token"] + " " + self.task["lease"] + " " + str(self.job) + "/private.txt\x00"
        self.conversation.assistant({"type": "assistant.message", "id": "i", "body": body, "complete": True}, scope="author")
        self.conversation.flush(force=True)
        published = " ".join(self.website.assistant.values())
        for secret in (self.cfg["token"], self.task["lease"], str(self.job), "\x00"):
            self.assertNotIn(secret, published)

    def test_context_regenerates_on_status_change_without_overwriting_old_file(self):
        row = self.row()
        self.conversation.accept(row)
        path = self.conversation.context()
        original = (self.job / path).read_bytes()
        cursor = self.journal.state["message_cursor"]
        self.server.deliver(self.journal, row["id"], "thread-1", "turn-1")
        updated = self.conversation.context()
        self.assertNotEqual(updated, path)
        self.assertEqual((self.job / path).read_bytes(), original)
        self.assertEqual(json.loads(original)["requests"][0]["status"], "accepted")
        self.assertEqual(json.loads((self.job / updated).read_bytes())["requests"][0]["status"], "acknowledged")
        self.assertEqual(self.journal.state["message_cursor"], cursor)

    def test_context_includes_outstanding_chat_and_keeps_revision_history(self):
        revision = self.row(seq=2)
        chat = self.row(kind="chat", seq=9, body="Explain progress")
        self.conversation.accept(revision)
        self.conversation.accept(chat)
        self.server.deliver(self.journal, revision["id"], "thread-1", "turn-1")
        self.server.deliver(self.journal, chat["id"], "thread-1", "turn-1")
        path = self.conversation.context()
        requests = json.loads((self.job / path).read_bytes())["requests"]
        self.assertEqual([r["id"] for r in requests], [revision["id"], chat["id"]])
        self.assertEqual([r["kind"] for r in requests], ["revision", "chat"])
        self.conversation.complete_chats({("thread-1", "turn-1"): {"status": "completed"}})
        self.conversation.validated(["deck.json"])
        updated = self.conversation.context()
        self.assertEqual([r["id"] for r in json.loads((self.job / updated).read_bytes())["requests"]], [revision["id"]])
        self.assertTrue((self.job / path).exists())

    def test_resumed_context_turn_completes_only_its_acknowledged_chat_ids(self):
        included = self.row(kind="chat", seq=1, body="Previous interrupted question")
        other = self.row(kind="chat", seq=2, body="Another outstanding question")
        for row in (included, other):
            self.conversation.accept(row)
            self.server.deliver(self.journal, row["id"], "thread-1", "turn-old")
        self.conversation.complete_chats({("thread-new", "turn-new"): {"status": "completed"}},
            context_message_ids=[included["id"]], context_turn=("thread-new", "turn-new"))
        self.assertEqual(self.journal.state["inbox"][included["id"]]["state"], "applied")
        self.assertEqual(self.journal.state["inbox"][other["id"]]["state"], "acknowledged")

    def test_interrupted_context_turn_cannot_claim_recovered_chat_answered(self):
        row = self.row(kind="chat", body="Previous interrupted question")
        self.conversation.accept(row)
        self.server.deliver(self.journal, row["id"], "thread-1", "turn-old")
        self.conversation.complete_chats({("thread-new", "turn-new"): {"status": "interrupted"}},
            context_message_ids=[row["id"]], context_turn=("thread-new", "turn-new"))
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "acknowledged")

    def test_deck_validation_does_not_substitute_for_answering_a_chat(self):
        row = self.row(kind="chat", body="How far along are you?")
        self.website.rows = [row]
        self.poll()
        with self.assertRaises(RevisionPending): self.conversation.validated(["deck.json"])
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "acknowledged")
        self.assertFalse(self.website.applied)

    def test_checkpoint_status_contains_only_host_receipts_without_credentials(self):
        self.journal.checkpoint(self.job)
        self.conversation.checkpoint()
        self.conversation.checkpoint()
        self.assertEqual(len(self.website.checkpoints), 1)
        value = self.website.checkpoints[0]
        self.assertTrue(value["resumable"])
        self.assertEqual(set(value), {"checkpointId", "runId", "phase", "pluginVersion", "revision", "lastMessageSeq", "resumable"})
        self.assertNotIn(self.task["lease"], json.dumps(value))
        self.assertNotIn(str(self.job), json.dumps(value))

    def test_http2_checkpoint_keeps_running_journal_and_retries_after_reopen(self):
        self.journal.checkpoint(self.job)
        before = copy.deepcopy(self.journal.state)
        self.website.failures["checkpoint"] = ["http2"]
        self.conversation.checkpoint(phase="author")
        self.assertIsNone(self.conversation.last_checkpoint)
        self.assertEqual(self.journal.state, before)
        self.assertEqual(self.journal.state["phase"]["status"], "running")
        self.assertFalse(self.website.checkpoints)
        self.journal.close()
        self.journal = Journal(self.base / "host", self.task["id"])
        self.assertEqual(self.journal.state["snapshot_id"], before["snapshot_id"])
        reconnected = self.new_conversation()
        reconnected.checkpoint(phase="author")
        reconnected.checkpoint(phase="author")
        calls = [call[1] for call in self.website.calls if call[0]=="checkpoint"]
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(len(self.website.checkpoints), 1)
        self.assertIsNotNone(reconnected.last_checkpoint)

    def test_checkpoint_auth_lease_and_programming_errors_still_propagate(self):
        self.journal.checkpoint(self.job)
        self.conversation.send = request
        for status in (401,403,409):
            with self.subTest(status=status), patch('resilience.subprocess.run', return_value=subprocess.CompletedProcess([],16,str(status).encode(),b'')):
                with self.assertRaises(WorkerHTTPError) as caught:self.conversation.checkpoint()
                self.assertEqual(caught.exception.status, status)
                self.assertFalse(caught.exception.retryable)
        with patch('resilience.subprocess.run', side_effect=ValueError('Invalid local adapter')):
            with self.assertRaisesRegex(ValueError, 'Invalid local adapter'):self.conversation.checkpoint()
        self.assertIsNone(self.conversation.last_checkpoint)

    def test_journal_recovery_reconciles_delivery_and_preserves_source_attachment(self):
        data = b"reference"
        item = self.attachment(data)
        row = self.row(attachments=[item])
        self.website.rows = [row]
        self.website.attachments[(row["id"], item["id"])] = data
        self.conversation.accept(row)
        self.conversation.context()
        self.journal.checkpoint(self.job)
        self.server.behavior = ["lost"]
        with self.assertRaises(TransportError): self.server.deliver(self.journal, row["id"], "thread-1", "turn-1")
        original = self.journal.state["inbox"][row["id"]]["attachments"][0]["path"]
        recovered_job = self.base / "attempt-two"
        plan = self.journal.recover(recovered_job, plugin_version="0.2.0")
        self.assertEqual(plan["uncertain_message_ids"], [row["id"]])
        recovered = self.new_conversation(recovered_job)
        recovered.poll(server=self.server, thread_id="thread-1", force=True)
        self.assertEqual(self.server.deliveries, [row["id"]])
        self.assertEqual(self.journal.state["inbox"][row["id"]]["state"], "acknowledged")
        self.assertEqual((self.job / original).read_bytes(), data)
        self.assertEqual((recovered_job / original).read_bytes(), data)

    def test_retryable_poll_outage_retains_inbox_and_recovers(self):
        row = self.row()
        self.website.rows = [row]
        self.website.failures["poll"] = ["retryable", "http2"]
        self.assertFalse(self.poll())
        self.assertFalse(self.poll())
        self.assertFalse(self.journal.state["inbox"])
        self.assertTrue(self.poll())
        self.assertIn(row["id"], self.journal.state["inbox"])

    def test_lost_website_ack_retries_ack_not_model_instruction(self):
        row = self.row()
        self.website.rows = [row]
        self.website.failures["ack"] = ["lost"]
        self.poll()
        self.assertNotIn(row["id"], self.conversation.website_acked)
        self.conversation.flush(force=True)
        self.assertIn(row["id"], self.conversation.website_acked)
        self.assertEqual(self.server.deliveries, [row["id"]])
        self.assertEqual(self.website.acks, [[row["id"]], [row["id"]]])

    def test_publish_task_file_preserves_existing_different_bytes(self):
        _publish_task_file(self.job, "keep.txt", b"original")
        with self.assertRaises(ValueError): _publish_task_file(self.job, "keep.txt", b"different")
        self.assertEqual((self.job / "keep.txt").read_bytes(), b"original")

    def test_host_outbox_symlink_is_rejected(self):
        outbox = self.conversation.outbox
        outbox.rename(self.journal.root / "retained-outbox")
        outside = self.base / "outside-outbox"
        outside.mkdir()
        outbox.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError): self.new_conversation()
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
