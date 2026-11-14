"""Pure conversion retries are bounded; lease/deadline guards stay in parent."""
import io
from contextlib import redirect_stderr
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from linux_render import convert,fresh_profile,render_parallelism


class CpuBudgetTests(unittest.TestCase):
    def test_fractional_container_does_not_inherit_eighty_host_workers(self):
        self.assertEqual(render_parallelism(cpu_limit='50000 100000',affinity=80),1)

    def test_pool_respects_both_quota_and_allowed_cpus(self):
        self.assertEqual(render_parallelism(cpu_limit='250000 100000',affinity=80),3)
        self.assertEqual(render_parallelism(cpu_limit='250000 100000',affinity=2),2)
        self.assertEqual(render_parallelism(cpu_limit='max 100000',affinity=2),2)

    def test_missing_or_invalid_quota_retains_affinity_bound(self):
        for value in ('invalid','0 100000','100000 0'):
            self.assertEqual(render_parallelism(cpu_limit=value,affinity=2),2)
        with patch('linux_render.Path.read_text',side_effect=OSError('Unavailable')):
            self.assertEqual(render_parallelism(affinity=1),1)


class ConversionTests(unittest.TestCase):
    def run_codes(self,codes):
        calls=[]
        def run(command):
            calls.append(command)
            return SimpleNamespace(returncode=codes[len(calls)-1])
        with patch('linux_render.subprocess.run',side_effect=run),redirect_stderr(io.StringIO()):
            result=convert(['fixed','immutable-input.pptx'])
        self.assertTrue(all(command==calls[0] for command in calls))
        return result.returncode,len(calls)

    def test_interrupted_conversion_recovers_once(self):
        self.assertEqual(self.run_codes([-9,0]),(0,2))

    def test_repeated_interrupt_is_not_an_unbounded_loop(self):
        self.assertEqual(self.run_codes([-9,-9,0]),(-9,2))
        self.assertEqual(self.run_codes([247,0]),(0,2))
        self.assertEqual(self.run_codes([247,247,0]),(247,2))

    def test_bootstrap_retries_remain_bounded(self):
        self.assertEqual(self.run_codes([81,81,0]),(0,3))
        self.assertEqual(self.run_codes([81]*4),(81,3))

    def test_bootstrap_and_interrupt_have_independent_budgets(self):
        self.assertEqual(self.run_codes([81,-9,81,0]),(0,4))

    def test_other_failures_are_returned_without_replay(self):
        for code in (1,126,-11):
            with self.subTest(code=code):self.assertEqual(self.run_codes([code,0]),(code,1))

    def test_interrupted_retry_keeps_input_and_output_but_uses_clean_profile(self):
        command=['office','-env:UserInstallation=file:///tmp/pptx-r-test/profile','--outdir','output','immutable.pptx']
        calls=[]
        def run(args):
            calls.append(list(args))
            return SimpleNamespace(returncode=-9 if len(calls)==1 else 0)
        with patch('linux_render.subprocess.run',side_effect=run),redirect_stderr(io.StringIO()):
            self.assertEqual(convert(command,interrupted_retry=fresh_profile).returncode,0)
        self.assertEqual(calls[0],command)
        self.assertNotEqual(calls[0][1],calls[1][1])
        self.assertEqual(calls[0][:1]+calls[0][2:],calls[1][:1]+calls[1][2:])
        self.assertEqual(command[1],'-env:UserInstallation=file:///tmp/pptx-r-test/profile')


if __name__=='__main__':unittest.main()
