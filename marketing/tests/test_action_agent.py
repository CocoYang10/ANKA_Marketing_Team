import json
import unittest
from pathlib import Path

from action_agent.run_agent import MAX_ACTIONS, build_run


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "demo" / "data" / "marketing_snapshot.json"
META = ROOT / "working" / "reports" / "meta_raw_2026-07-29.json"


class ActionAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        meta = json.loads(META.read_text(encoding="utf-8"))
        cls.agent_run = build_run(snapshot, meta)

    def test_actions_are_bounded(self):
        self.assertLessEqual(len(self.agent_run["actions"]), MAX_ACTIONS)

    def test_each_action_is_auditable(self):
        for row in self.agent_run["actions"]:
            self.assertTrue(row["evidence"])
            self.assertTrue(row["acceptance_criteria"])
            self.assertTrue(row["owner_role"])
            self.assertIn(row["confidence"], {"HIGH", "MEDIUM", "LOW"})
            self.assertEqual(row["status"], "PROPOSED")

    def test_measurement_blocker_is_first(self):
        first = self.agent_run["actions"][0]
        self.assertEqual(first["priority"], "P0")
        self.assertEqual(first["workstream"], "measurement_reliability")

    def test_no_budget_change_is_recommended(self):
        text = json.dumps(self.agent_run).lower()
        self.assertNotIn("increase budget", text)
        self.assertIn("change campaign budgets", text)

    def test_growth_comparison_uses_same_segment_and_material_samples(self):
        growth = [
            row for row in self.agent_run["actions"]
            if row["workstream"] == "growth_experiment"
        ]
        self.assertEqual(len(growth), 1)
        evidence = growth[0]["evidence"]
        self.assertTrue(all("sent" in row["value"] for row in evidence))
        self.assertIn("French", growth[0]["title"])

    def test_actions_are_stable_for_same_evidence(self):
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        meta = json.loads(META.read_text(encoding="utf-8"))
        second = build_run(snapshot, meta)
        self.assertEqual(
            [row["action_id"] for row in self.agent_run["actions"]],
            [row["action_id"] for row in second["actions"]],
        )


if __name__ == "__main__":
    unittest.main()
