"""Offline: stale temporary task folders are removed, recent and unrelated ones are kept."""
import os
import tempfile
import time
import unittest
from pathlib import Path

import runner


class SweepTests(unittest.TestCase):
    def test_only_old_task_folders_are_removed(self):
        with tempfile.TemporaryDirectory() as base:
            base = Path(base); now = time.time()
            old = base / 'pptx-lab-job-old'; old.mkdir(); (old / 'x').write_text('x')
            recent = base / 'pptx-lab-job-new'; recent.mkdir()
            preflight = base / 'pptx-journal-preflight-old'; preflight.mkdir()
            other = base / 'someone-else-old'; other.mkdir()
            for path in (old, preflight, other):
                os.utime(path, (now - 30 * 3600, now - 30 * 3600))
            removed = runner.sweep_stale_job_dirs({}, now=now, base=base)
            self.assertEqual(sorted(removed), ['pptx-journal-preflight-old', 'pptx-lab-job-old'])
            self.assertTrue(recent.is_dir()); self.assertTrue(other.is_dir())
            self.assertEqual(runner.sweep_stale_job_dirs({'temp_retention_hours': 0}, now=now, base=base), [])


if __name__ == '__main__': unittest.main()
