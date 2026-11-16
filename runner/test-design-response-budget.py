import time
from types import SimpleNamespace
import unittest

from repair_inputs import StageDeadline
from workflow import (DESIGN_RESPONSE_MIN_SECONDS, DESIGN_RESPONSE_SECONDS,
                      DESIGN_REVIEW_RESERVE_SECONDS, design_response_timeout, rollback_reason)


class DesignResponseBudgetTest(unittest.TestCase):
    def test_full_budget_when_task_time_allows_response_and_review(self):
        run = SimpleNamespace(deadline=time.monotonic() + 5400)
        self.assertEqual(design_response_timeout(run), DESIGN_RESPONSE_SECONDS)

    def test_reserves_time_for_the_re_review(self):
        run = SimpleNamespace(deadline=time.monotonic() + DESIGN_REVIEW_RESERVE_SECONDS + 900)
        self.assertTrue(895 <= design_response_timeout(run) <= 900)

    def test_never_below_previous_minimum(self):
        run = SimpleNamespace(deadline=time.monotonic() + 100)
        self.assertEqual(design_response_timeout(run), DESIGN_RESPONSE_MIN_SECONDS)

    def test_missing_deadline_uses_default(self):
        self.assertEqual(design_response_timeout(SimpleNamespace()), DESIGN_RESPONSE_SECONDS)
        self.assertEqual(design_response_timeout(SimpleNamespace(deadline=True)), DESIGN_RESPONSE_SECONDS)

    def test_rollback_reason_separates_timeout_from_other_failures(self):
        self.assertEqual(rollback_reason('repair_failed', StageDeadline('x')), 'repair_timeout')
        self.assertEqual(rollback_reason('repair_failed', TimeoutError()), 'repair_timeout')
        self.assertEqual(rollback_reason('repair_failed', ValueError()), 'repair_failed:ValueError')
        self.assertEqual(rollback_reason('verification_failed', TimeoutError()), 'verification_failed:timeout')


if __name__ == '__main__':
    unittest.main()
