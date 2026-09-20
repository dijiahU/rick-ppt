"""Codex 0.155.1 ErrorNotification shapes, privacy and turn lifecycle regression.

Fixtures follow the locally generated v2/ErrorNotification.json: willRetry is
top-level, error is TurnError, and four single-key CodexErrorInfo variants contain
httpStatusCode. No local protocol file, live Codex process or credentials needed.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from app_server import AppServer


SECRET = "PRIVATE_ERROR_SENTINEL_never_archive_8791"
GENERIC = "Codex reported an execution error"
STRING_CODES = (
    "contextWindowExceeded", "sessionBudgetExceeded", "usageLimitExceeded",
    "rateLimitExceeded", "serverOverloaded", "cyberPolicy",
    "misalignmentPolicyViolation", "internalServerError", "unauthorized",
    "badRequest", "threadRollbackFailed", "sandboxError", "other",
)
HTTP_CODES = (
    "httpConnectionFailed", "responseStreamConnectionFailed",
    "responseStreamDisconnected", "responseTooManyFailedAttempts",
)


class ErrorNotificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="appserver-error-projection-")
        self.addCleanup(self.temporary.cleanup)
        self.events, self.public = [], []
        self.server = AppServer(cwd=Path(self.temporary.name), config={},
                                on_event=self.events.append, on_public=self.public.append,
                                secrets=(SECRET,))
        self.addCleanup(self.server.close)

    def deliver(self, method, params):
        # Exercise the actual JSON-RPC queue/normalizer, without a live worker.
        self.server._queue.put(json.loads(json.dumps({"method": method, "params": params})))
        return self.server.pump()[-1]

    def notice(self, code, *, retry=True, **extras):
        return {"threadId": "thread-fixture", "turnId": "turn-fixture", "willRetry": retry,
                "error": {"message": SECRET, "codexErrorInfo": code}, **extras}

    def assert_private_fields_absent(self):
        persisted = json.dumps([list(self.server.events), self.events, self.public,
                                list(self.server.completed_turns.values())])
        self.assertNotIn(SECRET, persisted)
        self.assertNotIn("Bearer", persisted)
        self.assertNotIn("https://", persisted)
        self.assertNotIn("PRIVATE_REASONING", persisted)
        self.assertEqual(self.public, [], "Error metadata remains in the existing host event stream")

    def test_retryable_nested_schema_preserves_only_allowed_metadata(self):
        payload = self.notice({"responseStreamDisconnected": {"httpStatusCode": 502}})
        original = copy.deepcopy(payload)
        event = self.deliver("error", payload)
        self.assertEqual(event, {"type": "error", "thread_id": "thread-fixture", "turn_id": "turn-fixture",
                                 "message": GENERIC, "error": {"code": "responseStreamDisconnected",
                                                               "http_status_code": 502, "will_retry": True}})
        self.assertEqual(payload, original)
        self.assert_private_fields_absent()

    def test_every_schema_string_and_object_code_has_a_fixed_projection(self):
        for code in STRING_CODES:
            with self.subTest(code=code):
                event = self.deliver("error", self.notice(code, retry=False))
                self.assertEqual(event["error"], {"code": code, "will_retry": False})
        for code in HTTP_CODES:
            with self.subTest(code=code):
                event = self.deliver("error", self.notice({code: {"httpStatusCode": 503}}))
                self.assertEqual(event["error"], {"code": code, "http_status_code": 503, "will_retry": True})
        for kind in ("review", "compact"):
            with self.subTest(turnKind=kind):
                event = self.deliver("error", self.notice({"activeTurnNotSteerable": {"turnKind": kind}}))
                self.assertEqual(event["error"], {"code": "activeTurnNotSteerable", "will_retry": True})
        self.assert_private_fields_absent()

    def test_http_status_has_strict_integer_type_and_legal_range(self):
        for status in (100, 199, 200, 301, 401, 429, 500, 599):
            with self.subTest(valid=status):
                event = self.deliver("error", self.notice({"httpConnectionFailed": {"httpStatusCode": status}}))
                self.assertEqual(event["error"]["http_status_code"], status)
        for status in (None, True, False, -1, 0, 99, 600, 65535, "503", 503.0, [], {}, SECRET):
            with self.subTest(invalid=repr(status)):
                event = self.deliver("error", self.notice({"httpConnectionFailed": {"httpStatusCode": status}}))
                self.assertEqual(event["error"], {"code": "httpConnectionFailed", "will_retry": True})
        # Nullable and absent status are valid schema shapes, but not HTTP codes.
        event = self.deliver("error", self.notice({"responseTooManyFailedAttempts": {}}))
        self.assertEqual(event["error"], {"code": "responseTooManyFailedAttempts", "will_retry": True})
        self.assert_private_fields_absent()

    def test_retry_is_only_a_top_level_boolean(self):
        for retry in (None, 0, 1, "true", "false", [], {}, SECRET):
            with self.subTest(retry=repr(retry)):
                event = self.deliver("error", self.notice("other", retry=retry))
                self.assertEqual(event["error"], {"code": "other"})
        payload = self.notice("other")
        del payload["willRetry"]
        payload["error"]["willRetry"] = True
        event = self.deliver("error", payload)
        self.assertEqual(event["error"], {"code": "other"})

    def test_unknown_codes_and_malformed_union_shapes_cannot_be_archived(self):
        malformed = [None, SECRET, "ContextWindowExceeded", "responseStreamDisconnected", [], 1, True,
                     {SECRET: {}}, {"httpConnectionFailed": SECRET}, {"httpConnectionFailed": None},
                     {"httpConnectionFailed": {"httpStatusCode": 502}, "extra": SECRET},
                     {"responseStreamDisconnected": {}, "httpConnectionFailed": {}},
                     {"activeTurnNotSteerable": {}}, {"activeTurnNotSteerable": {"turnKind": SECRET}}]
        for code in malformed:
            with self.subTest(code=repr(code)):
                event = self.deliver("error", self.notice(code))
                self.assertEqual(event["error"], {"will_retry": True})
        self.assert_private_fields_absent()

    def test_extra_error_material_and_misplaced_status_are_never_copied(self):
        material = {"message": SECRET, "stack": SECRET, "stderr": SECRET,
                    "headers": {"Authorization": "Bearer " + SECRET},
                    "url": "https://example.invalid/" + SECRET, "reasoning": "PRIVATE_REASONING " + SECRET,
                    "additionalDetails": SECRET,
                    "misalignment": {"errorType": SECRET, "detailedExplanation": SECRET, "steer": {"message": SECRET}}}
        payload = self.notice({"responseStreamConnectionFailed": {"httpStatusCode": 429, **material}}, **material)
        payload["error"].update(material)
        event = self.deliver("error", payload)
        self.assertEqual(event["error"], {"code": "responseStreamConnectionFailed", "http_status_code": 429, "will_retry": True})
        payload = self.notice("rateLimitExceeded", httpStatusCode=599)
        payload["error"]["httpStatusCode"] = 503
        self.assertEqual(self.deliver("error", payload)["error"], {"code": "rateLimitExceeded", "will_retry": True})
        self.assert_private_fields_absent()

    def test_malformed_notification_and_turn_error_keep_legacy_generic_event(self):
        for params in (None, SECRET, [SECRET], 1, True, {}, {"error": SECRET}, {"error": [SECRET]},
                       {"threadId": {"message": SECRET}, "turnId": [SECRET]}):
            with self.subTest(params=repr(params)):
                event = self.deliver("error", params)
                self.assertEqual(event, {"type": "error", "thread_id": None, "turn_id": None, "message": GENERIC})
        self.assert_private_fields_absent()

    def test_retry_notice_does_not_end_turn_before_successful_completion(self):
        self.deliver("turn/started", {"threadId": "thread-fixture", "turn": {"id": "turn-fixture", "status": "inProgress"}})
        self.deliver("error", self.notice({"responseStreamDisconnected": {"httpStatusCode": None}}))
        self.assertEqual(self.server.active_turns, {"thread-fixture": "turn-fixture"})
        self.assertFalse(self.server.completed_turns)
        event = self.deliver("turn/completed", {"threadId": "thread-fixture", "turn": {
            "id": "turn-fixture", "status": "completed", "items": [{"type": "reasoning", "text": SECRET}]}})
        self.assertEqual(event["type"], "turn.completed")
        self.assertFalse(self.server.active_turns)
        self.assertEqual(self.server.completed_turns[("thread-fixture", "turn-fixture")]["status"], "completed")
        self.assert_private_fields_absent()

    def test_fatal_notice_also_waits_for_completion_and_sanitizes_its_error(self):
        self.deliver("turn/started", {"threadId": "thread-fixture", "turn": {"id": "turn-fixture", "status": "inProgress"}})
        self.deliver("error", self.notice("contextWindowExceeded", retry=False))
        self.assertEqual(self.server.active_turns, {"thread-fixture": "turn-fixture"})
        self.assertFalse(self.server.completed_turns)
        error = {"message": SECRET, "additionalDetails": SECRET,
                 "codexErrorInfo": {"responseTooManyFailedAttempts": {"httpStatusCode": 503, "headers": {"Authorization": "Bearer " + SECRET}}}}
        event = self.deliver("turn/completed", {"threadId": "thread-fixture", "turn": {
            "id": "turn-fixture", "status": "failed", "items": [], "error": error}})
        self.assertEqual(event["type"], "turn.failed")
        self.assertEqual(event["error"], {"message": "Codex turn failed", "code": "responseTooManyFailedAttempts", "http_status_code": 503})
        self.assertFalse(self.server.active_turns)
        self.assert_private_fields_absent()

    def test_completed_turn_error_string_codes_remain_compatible_and_unknowns_are_omitted(self):
        for index, info in enumerate(("contextWindowExceeded", {"futureVariant": {"message": SECRET}}, SECRET)):
            event = self.deliver("turn/completed", {"threadId": "thread-fixture", "turn": {
                "id": "finished-" + str(index), "status": "failed", "items": [],
                "error": {"message": SECRET, "codexErrorInfo": info}}})
            expected = {"message": "Codex turn failed"}
            if index == 0:
                expected["code"] = "contextWindowExceeded"
            self.assertEqual(event["error"], expected)
        event = self.deliver("turn/completed", {"threadId": "thread-fixture", "turn": {
            "id": "malformed-error", "status": "failed", "items": [], "error": SECRET}})
        self.assertEqual(event["error"], {"message": "Codex turn failed"})
        self.assert_private_fields_absent()


if __name__ == "__main__":
    unittest.main()
