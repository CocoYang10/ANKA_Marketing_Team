import tempfile
import unittest
from pathlib import Path

from action_agent.registry import (
    assign,
    connect,
    get_action,
    schedule_verification,
    sync_run,
    transition,
)
from action_agent.verify_actions import run_due_verifications
from build_dashboard_snapshot import build_snapshot, read_json


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "working" / "reports"
BRIEF = ROOT / "working" / "agent_runs" / "2026-08-10_action_brief.json"


class V1AcceptanceTests(unittest.TestCase):
    def test_evidence_to_action_to_verification_without_external_task(self):
        snapshot = build_snapshot(
            read_json(sorted(REPORTS.glob("ga4_raw_*.json"))[-1]),
            read_json(sorted(REPORTS.glob("meta_raw_*.json"))[-1]),
            read_json(sorted(REPORTS.glob("mailerlite_raw_*.json"))[-1]),
        )
        brief = read_json(BRIEF)

        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / "acceptance.sqlite3")
            result = sync_run(db, brief, actor="acceptance-agent")
            self.assertGreater(result["inserted"], 0)

            action_id = brief["actions"][0]["action_id"]
            assign(
                db,
                action_id,
                "Analytics Engineering",
                "acceptance-reviewer",
                "V1 local acceptance assignment",
                "2026-08-13",
            )
            transition(db, action_id, "APPROVED", "acceptance-reviewer", "Evidence reviewed")
            transition(
                db,
                action_id,
                "IN_PROGRESS",
                "acceptance-reviewer",
                "Started without an external task",
            )
            transition(
                db,
                action_id,
                "VERIFY_PENDING",
                "acceptance-reviewer",
                "Implementation reported complete; outcome not yet proven",
            )
            schedule_verification(
                db,
                action_id,
                "2026-08-12",
                "Purchase event count must equal the unique transaction count.",
                "acceptance-reviewer",
            )

            results = run_due_verifications(db, snapshot, "2026-08-12")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["outcome"], "FAILED")

            action = get_action(db, action_id)
            self.assertEqual(action["status"], "FAILED")
            self.assertIsNone(action["external_id"])
            self.assertEqual(action["assigned_to"], "Analytics Engineering")
            self.assertGreaterEqual(len(action["history"]), 6)


if __name__ == "__main__":
    unittest.main()
