import json
import tempfile
import unittest
from pathlib import Path

from action_agent.registry import (
    assign,
    attach_external_task,
    connect,
    get_action,
    list_actions,
    record_verification,
    schedule_verification,
    sync_run,
    transition,
)
from action_agent.run_agent import build_run


ROOT = Path(__file__).resolve().parents[1]


class ActionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.temp.name) / "actions.sqlite3")
        snapshot = json.loads(
            (ROOT / "demo/data/marketing_snapshot.json").read_text(encoding="utf-8")
        )
        meta = json.loads(
            (ROOT / "working/reports/meta_raw_2026-07-29.json").read_text(encoding="utf-8")
        )
        self.run = build_run(snapshot, meta)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_sync_is_idempotent_and_counts_occurrences(self):
        first = sync_run(self.db, self.run)
        second = sync_run(self.db, self.run)
        self.assertEqual(first["inserted"], len(self.run["actions"]))
        self.assertEqual(second["inserted"], 0)
        self.assertTrue(all(row["occurrence_count"] == 1 for row in list_actions(self.db)))
        self.run["run"]["evidence_period"] = {
            "since": "2026-08-10",
            "until": "2026-08-16",
        }
        sync_run(self.db, self.run)
        self.assertTrue(all(row["occurrence_count"] == 2 for row in list_actions(self.db)))

    def test_valid_lifecycle_transition_is_audited(self):
        sync_run(self.db, self.run)
        action_id = self.run["actions"][0]["action_id"]
        transition(self.db, action_id, "APPROVED", "Vanessa", "Approved for engineering")
        row = next(row for row in list_actions(self.db) if row["action_id"] == action_id)
        self.assertEqual(row["status"], "APPROVED")
        event = self.db.execute(
            "SELECT actor, to_status FROM action_events WHERE action_id=? ORDER BY event_id DESC",
            (action_id,),
        ).fetchone()
        self.assertEqual(event["actor"], "Vanessa")
        self.assertEqual(event["to_status"], "APPROVED")

    def test_invalid_transition_is_blocked(self):
        sync_run(self.db, self.run)
        action_id = self.run["actions"][0]["action_id"]
        with self.assertRaises(ValueError):
            transition(self.db, action_id, "CLOSED", "agent")

    def test_assignment_and_timeline_are_persisted(self):
        sync_run(self.db, self.run)
        action_id = self.run["actions"][0]["action_id"]
        assign(
            self.db,
            action_id,
            "Checkout Engineer",
            "Coco",
            "Assigned after review",
            "2026-08-13",
        )
        detail = get_action(self.db, action_id)
        self.assertEqual(detail["assigned_to"], "Checkout Engineer")
        self.assertEqual(detail["due_date"], "2026-08-13")
        self.assertEqual(detail["history"][-1]["event_type"], "ASSIGNED")

    def test_external_task_attachment_is_idempotent(self):
        sync_run(self.db, self.run)
        action_id = self.run["actions"][0]["action_id"]
        transition(self.db, action_id, "APPROVED", "Coco")
        first = attach_external_task(
            self.db,
            action_id,
            "github",
            "42",
            "https://github.com/example/repo/issues/42",
            "Coco",
        )
        replay = attach_external_task(
            self.db,
            action_id,
            "github",
            "42",
            "https://github.com/example/repo/issues/42",
            "Coco",
        )
        self.assertTrue(first)
        self.assertFalse(replay)
        self.assertEqual(get_action(self.db, action_id)["external_id"], "42")

    def test_verification_requires_pending_state_and_records_outcome(self):
        sync_run(self.db, self.run)
        action_id = self.run["actions"][0]["action_id"]
        schedule_verification(
            self.db,
            action_id,
            "2026-08-20T12:00:00Z",
            "Purchase events equal unique transaction IDs for seven days.",
        )
        transition(self.db, action_id, "APPROVED", "Coco")
        transition(self.db, action_id, "IN_PROGRESS", "agent")
        transition(self.db, action_id, "VERIFY_PENDING", "agent")
        record_verification(
            self.db,
            action_id,
            "INCONCLUSIVE",
            "agent",
            "Only three complete post-release days are available.",
        )
        detail = get_action(self.db, action_id)
        self.assertEqual(detail["status"], "INCONCLUSIVE")
        self.assertEqual(detail["verification_result"]["outcome"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
