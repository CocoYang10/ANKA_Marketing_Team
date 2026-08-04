import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import app as backend
from action_agent.registry import connect, sync_run


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


if __name__ == "__main__":
    unittest.main()
