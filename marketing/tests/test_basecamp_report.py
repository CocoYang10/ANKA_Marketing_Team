import tempfile
import unittest
from pathlib import Path

from generate_basecamp_report import build_report
from build_dashboard_snapshot import build_snapshot, read_json


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "working" / "reports"
BRIEF = ROOT / "working" / "agent_runs" / "2026-08-10_action_brief.json"


class BasecampReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = build_snapshot(
            read_json(sorted(REPORTS.glob("ga4_raw_*.json"))[-1]),
            read_json(sorted(REPORTS.glob("meta_raw_*.json"))[-1]),
            read_json(sorted(REPORTS.glob("mailerlite_raw_*.json"))[-1]),
            read_json(BRIEF),
        )
        cls.report = build_report(cls.snapshot)

    def test_report_has_required_basecamp_sections(self):
        for heading in (
            "Executive Summary",
            "Channel Scorecard",
            "Website &amp; Commerce",
            "Data Health",
            "Recommended Actions",
            "Questions to Close",
            "Caveats &amp; Assumptions",
        ):
            self.assertIn(heading, self.report)

    def test_report_uses_copyable_tables_not_chart_surfaces(self):
        self.assertIn("Copy report", self.report)
        self.assertIn("<table", self.report)
        self.assertNotIn("<canvas", self.report)
        self.assertNotIn("<svg", self.report)

    def test_missing_sources_are_not_reported_as_zero(self):
        self.assertIn("TikTok", self.report)
        self.assertIn("Native metrics unavailable", self.report)
        self.assertIn("Unavailable", self.report)

    def test_report_keeps_attribution_guardrail(self):
        self.assertIn("Do not use this report for CAC, ROAS", self.report)
        self.assertIn("transaction attribution coverage is 0.0%", self.report)


if __name__ == "__main__":
    unittest.main()
