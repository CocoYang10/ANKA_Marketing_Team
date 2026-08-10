"""Server-side adapters that turn an approved Agent action into one real task.

Credentials are read only at request time from the private server environment.
The public dashboard never receives these values.
"""

from __future__ import annotations

import os
from typing import Any

import requests


def integration_status() -> dict:
    github_repo = os.getenv("GITHUB_ISSUES_REPOSITORY", "").strip()
    return {
        "github": {
            "configured": bool(
                os.getenv("GITHUB_ISSUES_TOKEN", "").strip() and github_repo
            ),
            "destination": github_repo or None,
            "needs": []
            if os.getenv("GITHUB_ISSUES_TOKEN", "").strip() and github_repo
            else ["GITHUB_ISSUES_TOKEN", "GITHUB_ISSUES_REPOSITORY"],
        }
    }


def task_body(action: dict) -> str:
    evidence = "\n".join(
        f"- {row.get('metric', row.get('code', 'Evidence'))}: {row.get('value', '')}"
        f" ({row.get('source', 'source unavailable')})"
        for row in action.get("evidence", [])
    )
    work = "\n".join(f"- [ ] {row}" for row in action.get("next_steps", []))
    acceptance = "\n".join(
        f"- [ ] {row}" for row in action.get("acceptance_criteria", [])
    )
    return "\n\n".join(
        part
        for part in [
            f"## Decision\n\n{action.get('decision') or action['title']}",
            f"## Why it matters\n\n{action.get('why_it_matters') or 'See evidence below.'}",
            f"## Evidence\n\n{evidence or '- No evidence rows supplied'}",
            f"## Proposed work\n\n{work or '- [ ] Review the approved action'}",
            f"## Done means\n\n{acceptance or '- [ ] Acceptance criteria required'}",
            f"Agent action ID: `{action['action_id']}`",
        ]
        if part
    )


def _response_json(response: requests.Response, system: str) -> dict[str, Any]:
    try:
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"{system} task creation failed with HTTP {response.status_code}") from exc
    except ValueError as exc:
        raise RuntimeError(f"{system} returned an invalid response") from exc


def create_github_issue(action: dict, http=requests) -> dict:
    token = os.getenv("GITHUB_ISSUES_TOKEN", "").strip()
    repository = os.getenv("GITHUB_ISSUES_REPOSITORY", "").strip()
    if not token or not repository or "/" not in repository:
        raise RuntimeError(
            "GitHub is not configured. Add a fine-grained Issues token and OWNER/REPO destination."
        )
    payload: dict[str, Any] = {
        "title": f"[{action['priority']}] {action['title']}",
        "body": task_body(action),
    }
    assignee = os.getenv("GITHUB_DEFAULT_ASSIGNEE", "").strip()
    if assignee:
        payload["assignees"] = [assignee]
    response = http.post(
        f"https://api.github.com/repos/{repository}/issues",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        json=payload,
        timeout=30,
    )
    body = _response_json(response, "GitHub")
    return {
        "system": "github",
        "external_id": str(body["number"]),
        "url": body["html_url"],
    }


def create_external_task(system: str, action: dict, http=requests) -> dict:
    normalized = system.lower()
    if normalized == "github":
        return create_github_issue(action, http=http)
    raise ValueError("system must be github")
