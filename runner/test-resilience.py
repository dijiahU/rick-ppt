"""Offline transport faults and execution-lifecycle regressions; no real jobs."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from resilience import request,WorkerHTTPError,HeartbeatLost,LeaseKeeper
import runner

class TransportTests(unittest.TestCase):
    def invoke(self,action,replies,*,raw=False):
        calls=[]
        def curl(command,**kwargs):
            calls.append((command,kwargs))
            reply=replies.pop(0)
            if isinstance(reply,Exception):raise reply
            status,code,body=reply
            Path(command[command.index('--output')+1]).write_bytes(body)
            return subprocess.CompletedProcess(command,code,str(status).encode(),b'private response details')
        with patch('resilience.subprocess.run',side_effect=curl),patch('resilience.time.sleep'),redirect_stdout(io.StringIO()):
            result=request({'site':'https://local.test','token':'LOCAL_TEST_SECRET'},'/api/worker/test?action='+action,
                           lease=None if action in ('claim','retry') else 'test-lease',raw=raw)
        return result,calls

    def test_transient_upload_and_lost_success_response(self):
        result,calls=self.invoke('complete',[(503,22,b'private'),(200,28,b'{'),(200,0,b'{"ok":true}')])
        self.assertEqual(result,{'ok':True});self.assertEqual(len(calls),3)
        for command,kwargs in calls:
            self.assertNotIn('LOCAL_TEST_SECRET',' '.join(command))
            self.assertIn(b'LOCAL_TEST_SECRET',kwargs['input'])
            self.assertIn('--max-time',command)

    def test_attachment_retry_returns_original_bytes(self):
        result,calls=self.invoke('attachment',[(0,7,b''),(200,0,b'original\x00bytes')],raw=True)
        self.assertEqual(result,b'original\x00bytes');self.assertEqual(len(calls),2)

    def test_claim_and_operator_retry_never_reissued_automatically(self):
        for action in ('claim','retry','heartbeat'):
            replies=[(0,28,b''),(200,0,b'{"ok":true}')]
            with self.assertRaises(WorkerHTTPError):self.invoke(action,replies)
            self.assertEqual(len(replies),1)

    def test_terminal_status_and_certificate_errors_not_retried(self):
        for status,code in ((401,22),(403,22),(409,22),(413,22),(0,60)):
            replies=[(status,code,b'LOCAL_TEST_SECRET'),(200,0,b'{}')]
            with self.assertRaises(WorkerHTTPError) as caught:self.invoke('complete',replies)
            self.assertFalse(caught.exception.retryable);self.assertEqual(len(replies),1)
            self.assertNotIn('LOCAL_TEST_SECRET',str(caught.exception))
            self.assertNotIn('private',str(caught.exception))

    def test_invalid_json_and_subprocess_timeout_can_recover(self):
        result,calls=self.invoke('fail',[(200,0,b'incomplete'),subprocess.TimeoutExpired('curl',50),(200,0,b'{"ok":true}')])
        self.assertTrue(result['ok']);self.assertEqual(len(calls),3)

    def test_retry_budget_is_bounded(self):
        replies=[(503,22,b'')]*4
        with self.assertRaises(WorkerHTTPError):self.invoke('complete',replies)
        self.assertEqual(len(replies),1)

class LeaseTests(unittest.TestCase):
    def test_outage_budget_and_recovery_reset(self):
        now=[0.0];responses=[WorkerHTTPError('heartbeat',curl=28,retryable=True),{'ok':True}]
        def send():
            value=responses.pop(0)
            if isinstance(value,Exception):raise value
            return value
        lease=LeaseKeeper(send,clock=lambda:now[0],log=lambda _:None)
        self.assertFalse(lease.pulse());now[0]=149;lease.check()
        self.assertTrue(lease.pulse());now[0]=298;lease.check()
        now[0]=299
        with self.assertRaises(HeartbeatLost):lease.check()

    def test_rejected_lease_stops_without_waiting_for_timeout(self):
        for status in (401,403,409):
            def send():raise WorkerHTTPError('heartbeat',status=status)
            lease=LeaseKeeper(send,log=lambda _:None);lease.pulse()
            with self.assertRaises(WorkerHTTPError):lease.check()

    def test_closed_execution_ignores_inflight_lease_rejection(self):
        messages=[]
        def send():
            lease.finish()  # Completion committed before this response arrived.
            raise WorkerHTTPError('heartbeat',status=409)
        lease=LeaseKeeper(send,log=messages.append)
        self.assertFalse(lease.pulse());self.assertIsNone(lease.fatal)
        self.assertEqual(messages,[])

    def test_transient_heartbeat_does_not_end_work_or_render(self):
        # Exercise the actual run_job wrapper and execute_task failure boundary.
        calls=[];recovered=threading.Event()
        def send(*args,**kwargs):
            calls.append(args[1])
            if len(calls)==1:raise WorkerHTTPError('heartbeat',curl=28,retryable=True)
            recovered.set();return {'ok':True}
        def work(cfg,task,lease):
            self.assertTrue(recovered.wait(2),'heartbeat never recovered')
            lease.check()
            # Simulated blocking render: heartbeat must continue independently.
            before=len(calls);time.sleep(.06);lease.check()
            self.assertGreater(len(calls),before)
            return 'delivered'
        def fast_keeper(send,**kwargs):return LeaseKeeper(send,interval=.01,retry_interval=.01,**kwargs)
        with patch.object(runner,'request',side_effect=send),patch.object(runner,'_run_job',side_effect=work),patch.object(runner,'LeaseKeeper',side_effect=fast_keeper),redirect_stdout(io.StringIO()):
            self.assertEqual(runner.execute_task({}, {'id':'ed06d395-ecdd-4601-a5f5-9aadf0545621','lease':'synthetic'}),'delivered')
        count=len(calls);time.sleep(.03);self.assertEqual(len(calls),count)
        self.assertTrue(all('action=heartbeat' in call for call in calls))

    def test_rejected_attempt_records_reason_without_failing_another_attempt(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(runner,'ROOT',Path(temp)),patch.object(runner,'run_job',side_effect=WorkerHTTPError('heartbeat',status=409)),patch.object(runner,'request') as send,redirect_stdout(io.StringIO()):
            runner.execute_task({}, {'id':'synthetic','lease':'old-lease'})
            send.assert_not_called()
            record=next((Path(temp)/'failures').glob('*.json'))
            self.assertEqual(record.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(record.read_text())['httpStatus'],409)

if __name__=='__main__':unittest.main()
