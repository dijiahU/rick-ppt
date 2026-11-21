"""Offline: a failed job's fail notice is retried, and a rejected lease is not retried."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runner


class FailNotifyTests(unittest.TestCase):
    def run_failure(self, outcomes):
        calls = []
        def fake_request(cfg, path, **kw):
            calls.append(path)
            result = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
            if isinstance(result, Exception): raise result
        cfg = {'fail_notify_backoff': (0, 0, 0)}
        with tempfile.TemporaryDirectory() as root, \
             patch.object(runner, 'ROOT', Path(root)), \
             patch.object(runner, 'run_job', side_effect=OSError('No space left on device')), \
             patch.object(runner, 'request', side_effect=fake_request):
            runner.execute_task(cfg, {'id': 'job-1', 'lease': 'L'})
        return calls

    def test_retries_until_sent(self):
        self.assertEqual(len(self.run_failure([OSError('disk'), OSError('disk'), None])), 3)

    def test_gives_up_after_four(self):
        self.assertEqual(len(self.run_failure([OSError('disk')])), 4)

    def test_rejected_lease_not_retried(self):
        self.assertEqual(len(self.run_failure([runner.WorkerHTTPError('fail', status=409)])), 1)


if __name__ == '__main__':
    unittest.main()
