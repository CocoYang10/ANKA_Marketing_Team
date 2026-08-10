import importlib.util
import os
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "pull-ga4-skill"
    / "pull_ga4.py"
)
SPEC = importlib.util.spec_from_file_location("pull_ga4", MODULE_PATH)
ga4 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ga4
SPEC.loader.exec_module(ga4)


def sample_period(
    *,
    sessions=1000,
    direct_sessions=400,
    checkouts=100,
    transactions=10,
    purchase_revenue=1000,
):
    return {
        "traffic": {
            "sessions": sessions,
            "active_users": 800,
            "engaged_sessions": 500,
            "average_session_duration": 100,
            "sources": [
                {
                    "source_medium": "(direct) / (none)",
                    "sessions": direct_sessions,
                },
                {
                    "source_medium": "google / organic",
                    "sessions": sessions - direct_sessions,
                },
            ],
        },
        "commerce": {
            "checkouts": checkouts,
            "transactions": transactions,
            "purchase_revenue": purchase_revenue,
            "total_revenue": purchase_revenue,
        },
        "transaction_audit": {
            "unique_transaction_ids": transactions,
            "audited_transactions": transactions,
            "audited_purchase_revenue": purchase_revenue,
            "missing_transaction_id_rows": 0,
            "zero_revenue_rows": 0,
            "duplicate_transaction_id_rows": 0,
        },
        "funnel": {
            name: {"event_count": 10, "users": 10}
            for name in ga4.FUNNEL_EVENTS
        },
    }


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.original_trusted_from = ga4.TRUSTED_FROM_RAW
        ga4.TRUSTED_FROM_RAW = "2026-07-23"

    def tearDown(self):
        ga4.TRUSTED_FROM_RAW = self.original_trusted_from

    def test_reasonable_period_is_trusted(self):
        current = sample_period()
        previous = sample_period(sessions=1100)
        result = ga4.evaluate_quality(
            current, previous, "2026-07-23", "2026-07-29"
        )
        self.assertEqual(result["status"], "TRUSTED")

    def test_revenue_missing_blocks_decision_use(self):
        current = sample_period(purchase_revenue=0)
        result = ga4.evaluate_quality(
            current, None, "2026-07-23", "2026-07-29"
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "REVENUE_MISSING",
            {issue["code"] for issue in result["issues"]},
        )

    def test_large_session_change_requires_review(self):
        current = sample_period(sessions=1000)
        previous = sample_period(sessions=10000)
        result = ga4.evaluate_quality(
            current, previous, "2026-07-23", "2026-07-29"
        )
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn(
            "SESSION_STEP_CHANGE",
            {issue["code"] for issue in result["issues"]},
        )

    def test_high_direct_share_requires_review(self):
        current = sample_period(sessions=1000, direct_sessions=900)
        result = ga4.evaluate_quality(
            current, None, "2026-07-23", "2026-07-29"
        )
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn(
            "HIGH_DIRECT_SHARE",
            {issue["code"] for issue in result["issues"]},
        )

    def test_pre_repair_period_requires_review(self):
        current = sample_period()
        result = ga4.evaluate_quality(
            current, None, "2026-07-20", "2026-07-26"
        )
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn(
            "PRE_REPAIR_PERIOD",
            {issue["code"] for issue in result["issues"]},
        )

    def test_extra_purchase_events_require_review(self):
        current = sample_period(transactions=10)
        current["funnel"]["purchase"]["event_count"] = 20
        result = ga4.evaluate_quality(
            current, None, "2026-07-23", "2026-07-29"
        )
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn(
            "PURCHASE_EVENT_MISMATCH",
            {issue["code"] for issue in result["issues"]},
        )


if __name__ == "__main__":
    unittest.main()
