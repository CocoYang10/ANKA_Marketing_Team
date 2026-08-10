import os
import unittest
from unittest.mock import patch

from backend.task_adapters import (
    create_github_issue,
    integration_status,
)


ACTION = {
    "action_id": "abc123",
    "priority": "P0",
    "title": "Repair purchase tracking",
    "decision": "Repair before budget analysis.",
    "why_it_matters": "Duplicate events overstate conversion.",
    "evidence": [{"metric": "events vs transactions", "value": "36 vs 24", "source": "GA4"}],
    "next_steps": ["Remove the residual tag."],
    "acceptance_criteria": ["Counts reconcile for seven days."],
    "due_date": "2026-08-13",
}


class FakeResponse:
    status_code = 201

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeHttp:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.body)


class TaskAdapterTests(unittest.TestCase):
    def test_status_never_returns_credentials(self):
        env = {
            "GITHUB_ISSUES_TOKEN": "secret-github",
            "GITHUB_ISSUES_REPOSITORY": "owner/repo",
        }
        with patch.dict(os.environ, env, clear=True):
            result = integration_status()
        self.assertTrue(result["github"]["configured"])
        self.assertNotIn("secret", str(result))

    def test_github_issue_payload_contains_done_means(self):
        http = FakeHttp({"number": 42, "html_url": "https://github.com/o/r/issues/42"})
        with patch.dict(
            os.environ,
            {"GITHUB_ISSUES_TOKEN": "token", "GITHUB_ISSUES_REPOSITORY": "o/r"},
            clear=True,
        ):
            result = create_github_issue(ACTION, http=http)
        self.assertEqual(result["external_id"], "42")
        payload = http.calls[0][1]["json"]
        self.assertIn("## Done means", payload["body"])
        self.assertNotIn("token", str(payload))

if __name__ == "__main__":
    unittest.main()
