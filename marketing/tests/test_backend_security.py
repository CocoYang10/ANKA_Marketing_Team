import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import app as backend
from action_agent.registry import connect, get_action, sync_run, transition


class BackendSecurityTests(unittest.TestCase):
    def test_api_key_is_required(self):
        with patch.object(backend, "API_KEY", "expected"):
            with self.assertRaises(HTTPException) as error:
                backend.require_api_key(None)
            self.assertEqual(error.exception.status_code, 401)

    def test_api_key_comparison_accepts_exact_value(self):
        with patch.object(backend, "API_KEY", "expected"):
            self.assertIsNone(backend.require_api_key("expected"))

    def test_oauth_state_is_single_use(self):
        with patch.object(backend, "TIKTOK_APP_SECRET", "test-secret"):
            state = backend.create_state()
            backend.verify_state(state)
            with self.assertRaises(HTTPException) as error:
                backend.verify_state(state)
            self.assertEqual(error.exception.status_code, 400)

    def test_tampered_oauth_state_is_rejected(self):
        with patch.object(backend, "TIKTOK_APP_SECRET", "test-secret"):
            state = backend.create_state()
            with self.assertRaises(HTTPException) as error:
                backend.verify_state(state + "tampered")
            self.assertEqual(error.exception.status_code, 400)

    def test_action_transition_uses_audited_registry(self):
        run = {
            "run": {"evidence_period": {"since": "2026-07-27", "until": "2026-08-02"}},
            "actions": [{
                "action_id": "safe-demo",
                "title": "Test action",
                "priority": "P1",
                "workstream": "measurement",
                "owner_role": "Analyst",
                "confidence": "HIGH",
                "evidence": [{"code": "TEST"}],
                "acceptance_criteria": ["Verified"],
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            db = connect(Path(tmp) / "actions.sqlite3")
            sync_run(db, run)
            with patch.object(backend, "registry_connect", return_value=db):
                result = backend.transition_action(
                    "safe-demo",
                    backend.ActionTransition(to_status="APPROVED", actor="Vanessa"),
                )
            self.assertEqual(result["status"], "APPROVED")
            db.close()

    def test_approved_action_creates_one_external_task(self):
        run = {
            "run": {"evidence_period": {"since": "2026-08-03", "until": "2026-08-09"}},
            "actions": [{
                "action_id": "external-demo",
                "title": "Repair tracking",
                "priority": "P0",
                "workstream": "measurement_reliability",
                "owner_role": "Engineer",
                "confidence": "HIGH",
                "evidence": [{"code": "TEST"}],
                "acceptance_criteria": ["Counts reconcile"],
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            db = connect(Path(tmp) / "actions.sqlite3")
            sync_run(db, run)
            transition(db, "external-demo", "APPROVED", "Coco")
            task = {
                "system": "github",
                "external_id": "42",
                "url": "https://github.com/o/r/issues/42",
            }
            with (
                patch.object(backend, "registry_connect", return_value=db),
                patch.object(backend, "create_external_task", return_value=task) as create,
            ):
                first = backend.create_action_task(
                    "external-demo",
                    backend.ExternalTaskRequest(system="github", actor="Coco"),
                )
                replay = backend.create_action_task(
                    "external-demo",
                    backend.ExternalTaskRequest(system="github", actor="Coco"),
                )
            self.assertTrue(first["created"])
            self.assertFalse(replay["created"])
            self.assertEqual(create.call_count, 1)
            detail = get_action(db, "external-demo")
            self.assertEqual(detail["status"], "IN_PROGRESS")
            self.assertEqual(detail["external_id"], "42")
            db.close()


if __name__ == "__main__":
    unittest.main()
