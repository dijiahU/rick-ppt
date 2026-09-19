"""Mock protocol tests by default; --live --out PATH runs the opt-in real smoke."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

from app_server import (AppServer, RPCError, RPCTimeout, TransportError,
                        child_environment, command_for, mcp_server_names,
                        normalize_item, redact_text, task_configuration)
from journal import Journal


FAKE_SERVER = r'''
import json,os,sys
thread="thread-1";counter=0;active=None;users=[];pending={}
def send(v): print(json.dumps(v),flush=True)
def event(m,p): send({"method":m,"params":p})
def reply(i,r): send({"id":i,"result":r})
def error(i,c=-32602,message="Synthetic protocol rejection"): send({"id":i,"error":{"code":c,"message":message}})
def complete(turn,text="OK",status="completed"):
 global active
 event("thread/tokenUsage/updated",{"threadId":thread,"turnId":turn,"tokenUsage":{"last":{"inputTokens":10,"cachedInputTokens":2,"outputTokens":5,"reasoningOutputTokens":1},"total":{"inputTokens":10,"cachedInputTokens":2,"outputTokens":5,"reasoningOutputTokens":1}}})
 item={"type":"agentMessage","id":"answer-"+turn,"text":text,"phase":"final_answer"}
 event("item/started",{"threadId":thread,"turnId":turn,"item":{**item,"text":""}})
 event("item/agentMessage/delta",{"threadId":thread,"turnId":turn,"itemId":item["id"],"delta":text})
 event("item/completed",{"threadId":thread,"turnId":turn,"item":item})
 event("turn/completed",{"threadId":thread,"turn":{"id":turn,"items":[item],"status":status}})
 active=None
for line in sys.stdin:
 q=json.loads(line);m=q.get("method");p=q.get("params",{});i=q.get("id")
 if m is None:
  if i in pending: reply(pending.pop(i),q.get("result",q.get("error")))
  continue
 if m=="initialize":reply(i,{"userAgent":"fake/0.155.1"})
 elif m=="initialized":pass
 elif m=="config/read":reply(i,{"config":{"mcp_servers":{"fake":{"command":"private","env":{"TOKEN":"never-public"}}}}})
 elif m in ("thread/start","thread/resume"):
  reply(i,{"thread":{"id":thread,"turns":[]},"approvalPolicy":"never","cwd":os.getcwd(),"sandbox":{"type":"workspaceWrite"},"config":p.get("config",{})})
  if m=="thread/start":event("thread/started",{"thread":{"id":thread}})
 elif m=="turn/start":
  counter+=1;active="turn-"+str(counter);text=p["input"][0]["text"]
  if text=="REJECT":error(i);continue
  if text=="INTERNAL":error(i,-32603);continue
  users.append({"turnId":active,"item":{"type":"userMessage","id":"user-"+active,"clientId":p.get("clientUserMessageId"),"content":p["input"]}})
  if text=="TIMEOUT":continue
  turn={"id":active,"status":"inProgress","items":[]}
  reply(i,{"turn":turn});event("turn/started",{"threadId":thread,"turn":turn})
  if text!="WAIT":complete(active,text)
 elif m=="turn/steer":
  text=p["input"][0]["text"]
  if active is None:error(i,-32600,"no active turn to steer");continue
  if p["expectedTurnId"]!=active or text=="REJECT":error(i);continue
  users.append({"turnId":active,"item":{"type":"userMessage","id":"steered-"+str(len(users)),"clientId":p.get("clientUserMessageId"),"content":p["input"]}})
  if text=="TIMEOUT":continue
  reply(i,{"turnId":active});complete(active,text)
 elif m=="turn/interrupt":
  if p["turnId"]!=active:error(i);continue
  reply(i,{});complete(active,"",status="interrupted")
 elif m=="thread/items/list":reply(i,{"data":list(reversed(users)),"nextCursor":None})
 elif m=="test/approval":
  pending["host-request"]=i;send({"id":"host-request","method":p["method"],"params":{}})
 elif m=="test/reasoning":
  event("item/reasoning/textDelta",{"delta":"HIDDEN_REASONING"})
  event("item/completed",{"threadId":thread,"turnId":"turn-x","item":{"id":"reasoning-x","type":"reasoning","text":"HIDDEN_REASONING"}})
  reply(i,{})
 elif m=="test/badframe":send(["not a JSON-RPC object"])
 elif m=="test/oversize":event("huge",{"value":"x"*100000})
 elif m=="test/echo":reply(i,p)
 else:error(i,-32601)
'''


class AppServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pptx-appserver-test-")
        self.base = Path(self.temporary.name).resolve()
        self.job = self.base / "job"
        self.job.mkdir()
        (self.job / "tmp").mkdir()
        self.config = task_configuration(self.job, config_paths=[], web_search="disabled")
        self.events, self.public, self.ticks = [], [], 0
        self.server = None
        self.journal = None

    def tearDown(self):
        if self.server:
            self.server.close()
        if self.journal:
            self.journal.close()
        self.temporary.cleanup()

    def tick(self):
        self.ticks += 1

    def start(self, **kwargs):
        self.server = AppServer(cwd=self.job, config=self.config,
            command=[sys.executable, "-u", "-c", FAKE_SERVER], on_event=self.events.append,
            on_public=self.public.append, tick=self.tick, **kwargs)
        self.server.start()
        return self.server

    def inbox(self, text="Correction"):
        self.journal = Journal(self.base / "host", "task-1", plugin_version="0.2.0")
        self.journal.begin_phase("author", self.job)
        self.journal.accept_message("message-1", text)
        return self.journal

    def test_handshake_and_effective_mcp_servers_are_disabled(self):
        s = self.start()
        response = s.start_thread()
        self.assertTrue(s.initialized)
        self.assertEqual(response["config"]["mcp_servers.fake.enabled"], False)
        self.assertNotIn("never-public", json.dumps(self.public))
        self.assertGreater(self.ticks, 0)

    def test_turn_receipts_final_answer_and_exec_jsonl_normalization(self):
        s = self.start()
        thread = s.start_thread()["thread"]["id"]
        turn = s.start_turn(thread, "Exact answer")
        completed = s.wait_turn(thread, turn["id"], timeout=2)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(s.result_text(thread, turn["id"]), "Exact answer")
        self.assertNotIn(thread, s.active_turns)
        result = [e for e in self.events if e["type"] == "turn.completed"][-1]
        self.assertEqual(result["usage"]["input_tokens"], 10)
        self.assertTrue(any(e.get("item", {}).get("type") == "agent_message" for e in self.events))
        self.assertTrue(any(e.get("body") == "Exact answer" and e["complete"] for e in self.public))

    def test_active_turn_steering_reuses_turn_and_persists_client_message_id(self):
        s = self.start()
        thread = s.start_thread()["thread"]["id"]
        turn = s.start_turn(thread, "WAIT")
        j = self.inbox()
        receipt = s.deliver(j, "message-1", thread, turn["id"])
        self.assertEqual(receipt["turn_id"], turn["id"])
        self.assertEqual(j.state["inbox"]["message-1"]["state"], "acknowledged")
        s.wait_turn(thread, turn["id"], timeout=2)
        self.assertEqual(s.result_text(thread, turn["id"]), "Correction")
        self.assertEqual(s.find_client_message(thread, "message-1")["turn_id"], turn["id"])

    def test_idle_delivery_starts_one_turn(self):
        s = self.start()
        thread = s.start_thread()["thread"]["id"]
        j = self.inbox()
        receipt = s.deliver(j, "message-1", thread)
        s.wait_turn(thread, receipt["turn_id"], timeout=2)
        self.assertEqual(j.state["inbox"]["message-1"]["state"], "acknowledged")
        with self.assertRaises(Exception):
            s.deliver(j, "message-1", thread)

    def test_definitive_turn_race_rejection_allows_explicit_resend(self):
        s = self.start()
        thread = s.start_thread()["thread"]["id"]
        j = self.inbox()
        with self.assertRaises(RPCError):
            s.deliver(j, "message-1", thread, "finished-turn")
        self.assertEqual(j.state["inbox"]["message-1"]["state"], "accepted")
        receipt = s.deliver(j, "message-1", thread)
        s.wait_turn(thread, receipt["turn_id"], timeout=2)

    def test_lost_response_stays_uncertain_then_reconciles_from_client_id(self):
        s = self.start(request_timeout=.2)
        thread = s.start_thread()["thread"]["id"]
        j = self.inbox("TIMEOUT")
        with self.assertRaises(RPCTimeout):
            s.deliver(j, "message-1", thread)
        self.assertEqual(j.state["inbox"]["message-1"]["state"], "uncertain")
        self.assertEqual(j.pending_messages(), [])
        s.reconcile_delivery(j, "message-1")
        self.assertEqual(j.state["inbox"]["message-1"]["state"], "acknowledged")

    def test_internal_error_is_not_treated_as_proven_non_delivery(self):
        s = self.start()
        thread = s.start_thread()["thread"]["id"]
        j = self.inbox("INTERNAL")
        with self.assertRaises(RPCError):
            s.deliver(j, "message-1", thread)
        self.assertEqual(j.state["inbox"]["message-1"]["state"], "uncertain")
        s.reconcile_delivery(j, "message-1")
        self.assertEqual(j.state["inbox"]["message-1"]["state"], "uncertain")

    def test_interrupt_reports_interrupted_and_resume_preserves_thread(self):
        s = self.start()
        thread = s.start_thread()["thread"]["id"]
        turn = s.start_turn(thread, "WAIT")
        s.interrupt(thread, turn["id"])
        self.assertEqual(s.wait_turn(thread, turn["id"], timeout=2)["status"], "interrupted")
        self.assertTrue(any(e["type"] == "turn.interrupted" for e in self.events))
        self.assertEqual(s.resume_thread(thread)["thread"]["id"], thread)

    def test_reasoning_is_never_public_or_normalized(self):
        s = self.start()
        s.request("test/reasoning", {})
        self.assertNotIn("HIDDEN_REASONING", json.dumps(self.public + self.events))

    def test_approval_and_permission_requests_are_denied_without_user_prompt(self):
        s = self.start()
        for method, field, expected in [
            ("item/commandExecution/requestApproval", "decision", "decline"),
            ("item/fileChange/requestApproval", "decision", "decline"),
            ("item/permissions/requestApproval", "permissions", {}),
            ("item/tool/requestUserInput", "answers", {}),
            ("mcpServer/elicitation/request", "action", "decline"),
        ]:
            with self.subTest(method=method):
                result = s.request("test/approval", {"method": method})
                self.assertEqual(result[field], expected)

    def test_unsupported_host_auth_callbacks_are_not_filled_with_credentials(self):
        s = self.start()
        result = s.request("test/approval", {"method": "account/chatgptAuthTokens/refresh"})
        self.assertEqual(result["code"], -32601)

    def test_bad_frame_and_oversize_frames_fail_closed(self):
        s = self.start(max_line=8192)
        with self.assertRaises(TransportError):
            s.request("test/badframe", {})
        s.close()
        s = self.start(max_line=8192)
        with self.assertRaises(TransportError):
            s.request("test/oversize", {})

    def test_output_schema_and_client_id_are_exact_protocol_fields(self):
        s = self.start()
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        captured = []
        original = s.request

        def request(method, params, **kwargs):
            captured.append((method, params))
            return original(method, params, **kwargs)

        s.request = request
        s.start_turn("thread-1", "answer", client_message_id="message-1", output_schema=schema)
        self.assertEqual(captured[0][1]["clientUserMessageId"], "message-1")
        self.assertEqual(captured[0][1]["outputSchema"], schema)

    def test_tool_env_and_child_env_do_not_inherit_host_credentials(self):
        env = child_environment(self.job, {"PATH": "/usr/bin", "TOKEN": "secret", "API_KEY": "key", "HOME": "/bad", "CODEX_HOME": "/bad", "LANG": "en_US.UTF-8"})
        self.assertEqual(set(env), {"PATH", "TMPDIR", "LANG"})
        config = task_configuration(self.job, config_paths=[], tool_env={**env, "TOKEN": "secret", "HTTPS_PROXY": "sensitive"})
        self.assertNotIn("TOKEN", config["shell_environment_policy"]["set"])
        self.assertNotIn("HTTPS_PROXY", config["shell_environment_policy"]["set"])
        self.assertEqual(config["permissions"]["pptx_job"]["filesystem"][":root"], "deny")
        self.assertFalse(config["permissions"]["pptx_job"]["network"]["enabled"])

    def test_read_grants_cannot_cover_private_home_or_other_task_roots(self):
        for root in ("/", str(self.base), str(Path.home())):
            with self.assertRaises(ValueError):
                task_configuration(self.job, read_roots=[root], config_paths=[])

    def test_mcp_configuration_extracts_only_names_and_emits_individual_disable_flags(self):
        config_file = self.base / "config.toml"
        config_file.write_text('[mcp_servers.fake]\ncommand="private"\n[mcp_servers.fake.env]\nTOKEN="sensitive"\n')
        self.assertEqual(mcp_server_names([config_file]), {"fake"})
        config = task_configuration(self.job, config_paths=[config_file])
        self.assertFalse(config["mcp_servers.fake.enabled"])
        self.assertNotIn("mcp_servers", config, "An empty map would remove transports before per-name overrides")
        command = command_for(config)
        self.assertIn("mcp_servers.fake.enabled=false", command)
        self.assertNotIn("sensitive", " ".join(command))
        self.assertNotIn("--ignore-user-config", command)

    def test_public_redaction_across_chunk_boundaries(self):
        secret = "host-secret-" + "X" * 40
        s = self.start(secrets=(secret,))
        params = {"threadId": "t", "turnId": "u", "itemId": "i"}
        s._assistant({**params, "delta": "Normal content " * 30 + "authorization=" + secret[:20]})
        s._assistant({**params, "delta": secret[20:] + " local /Users/rick/private/token.json"})
        full = s._messages[("t", "u", "i")]["text"]
        s._assistant(params, {"id": "i", "text": full}, completed=True)
        text = json.dumps(self.public)
        self.assertNotIn(secret, text)
        self.assertNotIn("/Users/rick", text)
        self.assertNotIn(secret[:20], text)
        self.assertIn("redacted", text)

    def test_usage_repeated_notifications_are_deduplicated(self):
        s = self.start()
        first = {"threadId": "t", "turnId": "u", "tokenUsage": {"last": {"inputTokens": 10, "outputTokens": 5}, "total": {"inputTokens": 100, "outputTokens": 20}}}
        s._notification("thread/tokenUsage/updated", first)
        s._notification("thread/tokenUsage/updated", first)
        second = {"threadId": "t", "turnId": "u", "tokenUsage": {"last": {"inputTokens": 20, "outputTokens": 6}, "total": {"inputTokens": 120, "outputTokens": 26}}}
        s._notification("thread/tokenUsage/updated", second)
        self.assertEqual(s.usage[("t", "u")]["input_tokens"], 30)
        self.assertEqual(s.usage[("t", "u")]["output_tokens"], 11)

    def test_normalize_commands_fields_without_reasoning(self):
        item = normalize_item({"id": "i", "type": "commandExecution", "command": "pwd", "aggregatedOutput": "/task", "exitCode": 0, "status": "completed"})
        self.assertEqual(item["type"], "command_execution")
        self.assertEqual(item["exit_code"], 0)
        self.assertIsNone(normalize_item({"type": "reasoning", "text": "hidden"}))

    def test_closed_instance_cannot_be_reused(self):
        s = self.start()
        s.close()
        with self.assertRaises(TransportError):
            s.start()
        with self.assertRaises(TransportError):
            s.request("test/echo", {})


def live_smoke(out: Path):
    """Real local Codex test. Retain its new isolated files; emit no full sessions."""
    out = out.absolute()
    if out.exists():
        raise FileExistsError("Live proof output already exists")
    out.parent.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix="app-server-live-", dir=out.parent)).resolve()
    job = base / "task"
    job.mkdir()
    (job / "tmp").mkdir()
    outside = base / "outside"
    outside.mkdir()
    canary = outside / "read-canary.txt"
    canary.write_text("SYNTHETIC NONSECRET ISOLATION CANARY")
    script = '''import json,pathlib,socket,time
result={"outside_read_denied":False,"outside_write_denied":False,"network_denied":False}
try:pathlib.Path(READ).read_bytes()
except PermissionError:result["outside_read_denied"]=True
try:pathlib.Path(WRITE).write_text("unexpected sandbox escape")
except PermissionError:result["outside_write_denied"]=True
s=socket.socket();s.settimeout(2)
try:s.connect(("1.1.1.1",443))
except PermissionError:result["network_denied"]=True
except OSError:pass
finally:s.close()
pathlib.Path("isolation.json").write_text(json.dumps(result))
pathlib.Path("started.txt").write_text("started")
time.sleep(8)
print("ISOLATION_CHECK_COMPLETE")
'''.replace("READ", repr(str(canary))).replace("WRITE", repr(str(outside / "write-canary.txt")))
    (job / "isolation_check.py").write_text(script)
    env = child_environment(job)
    config = task_configuration(job, read_roots=["/opt/homebrew"], tool_env=env, web_search="disabled")
    events, public = [], []
    proof = {"schema": "pptx-app-server-smoke/v1", "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "cli_version": subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=10).stdout.strip(),
             "passed": False}
    journal = Journal(base / "host", str(uuid.uuid4()), plugin_version="0.2.0")
    server = None
    try:
        journal.begin_phase("transport-smoke", job)
        journal.checkpoint(job)
        server = AppServer(cwd=job, config=config, env=env, on_event=events.append, on_public=public.append)
        server.start()
        started = server.start_thread(developer_instructions="This is an isolated transport smoke. Follow the user's exact instructions, use only task-scoped files, and never request broader access.")
        thread_id = started["thread"]["id"]
        turn = server.start_turn(thread_id, "Run /opt/homebrew/bin/python3.11 isolation_check.py in the current directory. The script tests synthetic canaries only. While it sleeps, a correction will arrive. After the script exits follow the correction. Do not inspect any other files, browse, or use other tools.")
        journal.bind_session(thread_id, turn["id"])
        deadline = time.monotonic() + 120
        while not (job / "started.txt").exists():
            if time.monotonic() > deadline or (thread_id, turn["id"]) in server.completed_turns:
                raise RuntimeError("Initial live command did not reach the steering window")
            server.pump(.1)
        message_id = str(uuid.uuid4())
        journal.accept_message(message_id, "Live correction: after the script returns, create corrected.txt containing exactly STEER_RECEIVED and reply exactly STEER_RECEIVED. Do not read any other files.")
        receipt = server.deliver(journal, message_id, thread_id, turn["id"])
        completed = server.wait_turn(thread_id, turn["id"], timeout=150)
        proof["steered_same_turn"] = receipt["turn_id"] == turn["id"]
        proof["first_turn_completed"] = completed["status"] == "completed"
        proof["correction_applied"] = (job / "corrected.txt").is_file() and (job / "corrected.txt").read_text().strip() == "STEER_RECEIVED"
        proof["persisted_client_message_id"] = server.find_client_message(thread_id, message_id) is not None
        proof.update(json.loads((job / "isolation.json").read_text()))
        journal.mark_applied([message_id], job, artifacts=["corrected.txt", "isolation.json"])
        journal.checkpoint(job)
        interrupted = server.start_turn(thread_id, "Run /bin/sleep 20 once. Do not do anything else before or after it; this turn will be interrupted by the host.")
        journal.bind_session(thread_id, interrupted["id"])
        deadline = time.monotonic() + 100
        while not any(e.get("turn_id") == interrupted["id"] and e.get("type") == "item.started" and e.get("item", {}).get("type") == "command_execution" for e in events):
            if time.monotonic() > deadline or (thread_id, interrupted["id"]) in server.completed_turns:
                raise RuntimeError("Second live turn did not enter an interruptible command")
            server.pump(.1)
        server.interrupt(thread_id, interrupted["id"])
        proof["interrupted"] = server.wait_turn(thread_id, interrupted["id"], timeout=30)["status"] == "interrupted"
        journal.interrupt()
        server.close()
        server = AppServer(cwd=job, config=config, env=env, on_event=events.append, on_public=public.append)
        server.start()
        resumed = server.resume_thread(thread_id)
        proof["same_thread_resumed_after_process_restart"] = resumed["thread"]["id"] == thread_id
        last = server.start_turn(thread_id, "Resume after the host interruption. Do not use tools. Reply RESUME_OK followed by the exact marker you wrote in corrected.txt in the earlier turn, using your conversation context only.")
        proof["resumed_turn_completed"] = server.wait_turn(thread_id, last["id"], timeout=120)["status"] == "completed"
        response = server.result_text(thread_id, last["id"])
        proof["context_retained"] = "RESUME_OK" in response and "STEER_RECEIVED" in response
        proof["assistant_public_messages"] = len([e for e in public if e.get("type") == "assistant.message" and e.get("complete")])
        proof["reasoning_excluded"] = not any(e.get("item", {}).get("type") == "reasoning" for e in events)
        proof["approval_policy_never"] = started["approvalPolicy"] == resumed["approvalPolicy"] == "never"
        required = ("steered_same_turn", "first_turn_completed", "correction_applied", "persisted_client_message_id",
                    "outside_read_denied", "outside_write_denied", "network_denied", "interrupted",
                    "same_thread_resumed_after_process_restart", "resumed_turn_completed", "context_retained",
                    "reasoning_excluded", "approval_policy_never")
        proof["passed"] = all(proof.get(key) is True for key in required)
    except Exception as error:
        proof["error_type"] = type(error).__name__
        proof["error"] = str(error) if isinstance(error, (TransportError, RuntimeError)) else "Live smoke could not complete"
        if server:
            proof["transport_diagnostics"] = server.diagnostics()
    finally:
        if server:
            server.close()
        journal.close()
        proof["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with out.open("x") as stream:
            json.dump(proof, stream, indent=2)
        print(json.dumps(proof, indent=2))
    return proof["passed"]


if __name__ == "__main__":
    if "--live" in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument("--live", action="store_true")
        parser.add_argument("--out", required=True, type=Path)
        args = parser.parse_args()
        sys.exit(0 if live_smoke(args.out) else 1)
    unittest.main()
