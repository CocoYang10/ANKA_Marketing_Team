import json
import tempfile
import unittest
from pathlib import Path

from action_agent.registry import connect, list_actions, sync_run, transition
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


if __name__ == "__main__":
    unittest.main()
