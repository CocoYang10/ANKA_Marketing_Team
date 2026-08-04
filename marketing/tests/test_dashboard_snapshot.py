import json
import tempfile
import unittest
from pathlib import Path

from build_dashboard_snapshot import build_snapshot, read_json, validate_snapshot


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "working" / "reports"


class DashboardSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = build_snapshot(
            read_json(sorted(REPORTS.glob("ga4_raw_*.json"))[-1]),
            read_json(sorted(REPORTS.glob("meta_raw_*.json"))[-1]),
            read_json(sorted(REPORTS.glob("mailerlite_raw_*.json"))[-1]),
        )

    def test_current_snapshot_contract(self):
        self.assertEqual(validate_snapshot(self.snapshot), [])

    def test_traffic_reconciles(self):
        total = sum(row["sessions"] for row in self.snapshot["traffic_sources"])
        self.assertEqual(total, self.snapshot["kpis"]["sessions"])

    def test_transaction_counts_reconcile(self):
        self.assertEqual(
            self.snapshot["kpis"]["transactions"],
            self.snapshot["quality"]["transactions"],
        )

    def test_public_snapshot_has_no_forbidden_identifier_fields(self):
        text = json.dumps(self.snapshot).lower()
        for forbidden in (
            "access_token",
            "refresh_token",
            "transaction_id",
            "customer_id",
            "ip_address",
            "user_agent",
        ):
            self.assertNotIn(f'"{forbidden}"', text)

    def test_validator_rejects_secret_field(self):
        copied = json.loads(json.dumps(self.snapshot))
        copied["access_token"] = "never-public"
        self.assertIn(
            "forbidden field in public snapshot: access_token",
            validate_snapshot(copied),
        )

    def test_unattributed_orders_are_not_presented_as_channel_performance(self):
        self.assertGreater(self.snapshot["kpis"]["transactions"], 0)
        self.assertEqual(self.snapshot["kpis"]["transaction_attribution_coverage"], 0)
        self.assertIn(
            "PURCHASE_SOURCE_NOT_SET",
            {row["code"] for row in self.snapshot["quality"]["issues"]},
        )

    def test_buyer_demographic_gaps_are_explicit(self):
        self.assertEqual(self.snapshot["audience"]["age"]["status"], "traffic_only")
        self.assertEqual(self.snapshot["audience"]["interests"]["status"], "traffic_only")

    def test_current_payment_step_is_not_labeled_missing(self):
        payment = next(row for row in self.snapshot["funnel"] if row["step"] == "Payment info")
        self.assertGreater(payment["users"], 0)
        self.assertEqual(payment["status"], "available")

    def test_known_channel_comparison_excludes_direct_and_unknown(self):
        comparison = self.snapshot["comparison"]
        excluded = {"Direct", "Unknown / not set"}
        expected = sum(
            row["sessions"]
            for row in self.snapshot["traffic_sources"]
            if row["channel"] not in excluded
        )
        self.assertEqual(comparison["current"]["value"], expected)
        self.assertEqual(comparison["metric"], "known_channel_sessions")
        self.assertIn("non-Direct, non-Unknown", comparison["definition"])


if __name__ == "__main__":
    unittest.main()
