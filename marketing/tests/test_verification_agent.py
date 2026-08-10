import tempfile
import unittest
from pathlib import Path

from action_agent.registry import connect, schedule_verification, sync_run, transition
from action_agent.verify_actions import evaluate, run_due_verifications


def run_with_code(code):
    return {
        "run": {"evidence_period": {"since": "2026-08-03", "until": "2026-08-09"}},
        "actions": [{
            "action_id": "verify-demo",
            "title": "Verify the repair",
            "priority": "P0",
            "workstream": "measurement_reliability",
            "owner_role": "Engineer",
            "confidence": "HIGH",
            "evidence": [{"code": code}],
            "acceptance_criteria": ["Pass the deterministic check"],
        }],
    }


class VerificationAgentTests(unittest.TestCase):
    def test_purchase_repair_passes_only_when_counts_and_ids_reconcile(self):
        action = run_with_code("PURCHASE_EVENT_MISMATCH")["actions"][0]
        snapshot = {
            "quality": {
                "purchase_events": 24,
                "transactions": 24,
                "transaction_id_audit": {
                    "missing_transaction_id_rows": 0,
                    "duplicate_transaction_id_rows": 0,
                },
            }
        }
        self.assertEqual(evaluate(action, snapshot)[0], "VERIFIED")
        snapshot["quality"]["purchase_events"] = 36
        self.assertEqual(evaluate(action, snapshot)[0], "FAILED")

    def test_due_verification_updates_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = connect(Path(tmp) / "actions.sqlite3")
            sync_run(db, run_with_code("VIEW_ITEM_EVENT_MISSING"))
            transition(db, "verify-demo", "APPROVED", "Coco")
            transition(db, "verify-demo", "IN_PROGRESS", "agent")
            transition(db, "verify-demo", "VERIFY_PENDING", "agent")
            schedule_verification(
                db,
                "verify-demo",
                "2026-08-13",
                "Product views are non-zero and exceed add-to-cart users.",
            )
            snapshot = {
                "funnel": [
                    {"step": "Product view", "users": 300},
                    {"step": "Add to cart", "users": 251},
                ]
            }
            results = run_due_verifications(db, snapshot, "2026-08-13")
            self.assertEqual(results[0]["outcome"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
