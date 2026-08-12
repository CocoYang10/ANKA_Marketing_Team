"""Persistent lifecycle and audit log for Agent-proposed actions."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(
    os.getenv("ANKA_ACTION_DB", ROOT / "working" / "agent_state" / "actions.sqlite3")
)
ALLOWED_TRANSITIONS = {
    "PROPOSED": {"APPROVED", "REJECTED"},
    "APPROVED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"VERIFY_PENDING", "BLOCKED", "CANCELLED"},
    "BLOCKED": {"IN_PROGRESS", "CANCELLED"},
    "VERIFY_PENDING": {"VERIFIED", "FAILED", "INCONCLUSIVE"},
    "INCONCLUSIVE": {"IN_PROGRESS", "VERIFY_PENDING", "CANCELLED"},
    "FAILED": {"IN_PROGRESS", "CANCELLED"},
    "VERIFIED": {"CLOSED"},
    "REJECTED": set(),
    "CANCELLED": set(),
    "CLOSED": set(),
}


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS actions (
            action_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            priority TEXT NOT NULL,
            workstream TEXT NOT NULL,
            owner_role TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            acceptance_json TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            last_evidence_period TEXT NOT NULL,
            occurrence_count INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS action_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id TEXT NOT NULL REFERENCES actions(action_id),
            event_type TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            actor TEXT NOT NULL,
            note TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    action_columns = {
        "decision": "TEXT",
        "why_it_matters": "TEXT",
        "next_steps_json": "TEXT",
        "limitations_json": "TEXT",
        "assigned_to": "TEXT",
        "due_date": "TEXT",
        "verification_due_at": "TEXT",
        "verification_rule": "TEXT",
        "verification_result": "TEXT",
        "external_system": "TEXT",
        "external_id": "TEXT",
        "external_url": "TEXT",
    }
    existing_action_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(actions)")
    }
    for name, definition in action_columns.items():
        if name not in existing_action_columns:
            db.execute(f"ALTER TABLE actions ADD COLUMN {name} {definition}")
    existing_event_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(action_events)")
    }
    if "metadata_json" not in existing_event_columns:
        db.execute("ALTER TABLE action_events ADD COLUMN metadata_json TEXT")
    db.commit()
    return db


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_run(db: sqlite3.Connection, run: dict, actor: str = "agent") -> dict:
    timestamp = now()
    inserted = 0
    updated = 0
    period = json.dumps(run["run"]["evidence_period"], sort_keys=True)
    for row in run["actions"]:
        existing = db.execute(
            "SELECT status, occurrence_count, last_evidence_period FROM actions WHERE action_id = ?",
            (row["action_id"],),
        ).fetchone()
        if existing:
            new_evidence_period = existing["last_evidence_period"] != period
            db.execute(
                """
                UPDATE actions
                   SET title = ?, priority = ?, workstream = ?, owner_role = ?,
                       confidence = ?, decision = ?, why_it_matters = ?,
                       next_steps_json = ?, limitations_json = ?,
                       evidence_json = ?, acceptance_json = ?,
                       last_seen_at = ?, last_evidence_period = ?,
                       occurrence_count = occurrence_count + ?
                 WHERE action_id = ?
                """,
                (
                    row["title"],
                    row["priority"],
                    row["workstream"],
                    row["owner_role"],
                    row["confidence"],
                    row.get("decision"),
                    row.get("why_it_matters"),
                    json.dumps(row.get("next_steps", [])),
                    json.dumps(row.get("limitations", [])),
                    json.dumps(row["evidence"]),
                    json.dumps(row["acceptance_criteria"]),
                    timestamp,
                    period,
                    1 if new_evidence_period else 0,
                    row["action_id"],
                ),
            )
            if new_evidence_period:
                db.execute(
                    """
                    INSERT INTO action_events
                    (action_id, event_type, from_status, to_status, actor, note, created_at)
                    VALUES (?, 'SEEN_AGAIN', ?, ?, ?, ?, ?)
                    """,
                    (
                        row["action_id"],
                        existing["status"],
                        existing["status"],
                        actor,
                        "Action remained present in the latest evidence run.",
                        timestamp,
                    ),
                )
            updated += 1
        else:
            db.execute(
                """
                INSERT INTO actions
                (action_id, title, priority, workstream, owner_role, status,
                 confidence, evidence_json, acceptance_json, first_seen_at,
                 last_seen_at, last_evidence_period, occurrence_count,
                 decision, why_it_matters, next_steps_json, limitations_json)
                VALUES (?, ?, ?, ?, ?, 'PROPOSED', ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    row["action_id"],
                    row["title"],
                    row["priority"],
                    row["workstream"],
                    row["owner_role"],
                    row["confidence"],
                    json.dumps(row["evidence"]),
                    json.dumps(row["acceptance_criteria"]),
                    timestamp,
                    timestamp,
                    period,
                    row.get("decision"),
                    row.get("why_it_matters"),
                    json.dumps(row.get("next_steps", [])),
                    json.dumps(row.get("limitations", [])),
                ),
            )
            db.execute(
                """
                INSERT INTO action_events
                (action_id, event_type, from_status, to_status, actor, note, created_at)
                VALUES (?, 'CREATED', NULL, 'PROPOSED', ?, ?, ?)
                """,
                (
                    row["action_id"],
                    actor,
                    "Created from evidence-to-action run.",
                    timestamp,
                ),
            )
            inserted += 1
    db.commit()
    return {"inserted": inserted, "updated": updated}


def transition(
    db: sqlite3.Connection,
    action_id: str,
    to_status: str,
    actor: str,
    note: str = "",
) -> None:
    row = db.execute(
        "SELECT status FROM actions WHERE action_id = ?", (action_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown action_id: {action_id}")
    current = row["status"]
    target = to_status.upper()
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition: {current} -> {target}")
    timestamp = now()
    db.execute(
        "UPDATE actions SET status = ? WHERE action_id = ?",
        (target, action_id),
    )
    db.execute(
        """
        INSERT INTO action_events
        (action_id, event_type, from_status, to_status, actor, note, created_at)
        VALUES (?, 'STATUS_CHANGED', ?, ?, ?, ?, ?)
        """,
        (action_id, current, target, actor, note, timestamp),
    )
    db.commit()


def assign(
    db: sqlite3.Connection,
    action_id: str,
    assigned_to: str,
    actor: str,
    note: str = "",
    due_date: str | None = None,
) -> None:
    if not assigned_to.strip():
        raise ValueError("assigned_to is required")
    row = db.execute(
        "SELECT status FROM actions WHERE action_id = ?", (action_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown action_id: {action_id}")
    timestamp = now()
    db.execute(
        "UPDATE actions SET assigned_to = ?, due_date = ? WHERE action_id = ?",
        (assigned_to.strip(), due_date, action_id),
    )
    db.execute(
        """
        INSERT INTO action_events
        (action_id, event_type, from_status, to_status, actor, note,
         metadata_json, created_at)
        VALUES (?, 'ASSIGNED', ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id,
            row["status"],
            row["status"],
            actor,
            note,
            json.dumps({"assigned_to": assigned_to.strip(), "due_date": due_date}),
            timestamp,
        ),
    )
    db.commit()


def attach_external_task(
    db: sqlite3.Connection,
    action_id: str,
    system: str,
    external_id: str,
    external_url: str,
    actor: str = "agent",
) -> bool:
    """Attach exactly one external task; return False for an idempotent replay."""
    row = db.execute(
        "SELECT status, external_system, external_id, external_url FROM actions WHERE action_id = ?",
        (action_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown action_id: {action_id}")
    if row["status"] not in {"APPROVED", "IN_PROGRESS"}:
        raise ValueError("External tasks may only be attached after approval")
    if row["external_id"]:
        same_task = (
            row["external_system"] == system
            and row["external_id"] == str(external_id)
            and row["external_url"] == external_url
        )
        if same_task:
            return False
        raise ValueError("This action already has a different external task")
    timestamp = now()
    db.execute(
        """
        UPDATE actions
           SET external_system = ?, external_id = ?, external_url = ?
         WHERE action_id = ?
        """,
        (system, str(external_id), external_url, action_id),
    )
    db.execute(
        """
        INSERT INTO action_events
        (action_id, event_type, from_status, to_status, actor, note,
         metadata_json, created_at)
        VALUES (?, 'EXTERNAL_TASK_CREATED', ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id,
            row["status"],
            row["status"],
            actor,
            f"Created {system} task {external_id}",
            json.dumps(
                {"system": system, "external_id": str(external_id), "url": external_url}
            ),
            timestamp,
        ),
    )
    db.commit()
    return True


def schedule_verification(
    db: sqlite3.Connection,
    action_id: str,
    due_at: str,
    rule: str,
    actor: str = "agent",
) -> None:
    if not due_at or not rule.strip():
        raise ValueError("Verification due date and rule are required")
    row = db.execute(
        "SELECT status FROM actions WHERE action_id = ?", (action_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown action_id: {action_id}")
    timestamp = now()
    db.execute(
        """
        UPDATE actions
           SET verification_due_at = ?, verification_rule = ?, verification_result = NULL
         WHERE action_id = ?
        """,
        (due_at, rule.strip(), action_id),
    )
    db.execute(
        """
        INSERT INTO action_events
        (action_id, event_type, from_status, to_status, actor, note,
         metadata_json, created_at)
        VALUES (?, 'VERIFICATION_SCHEDULED', ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id,
            row["status"],
            row["status"],
            actor,
            "Verification check scheduled",
            json.dumps({"due_at": due_at, "rule": rule.strip()}),
            timestamp,
        ),
    )
    db.commit()


def record_verification(
    db: sqlite3.Connection,
    action_id: str,
    outcome: str,
    actor: str,
    evidence: str,
) -> None:
    target = outcome.upper()
    if target not in {"VERIFIED", "FAILED", "INCONCLUSIVE"}:
        raise ValueError("Verification outcome must be VERIFIED, FAILED or INCONCLUSIVE")
    row = db.execute(
        "SELECT status FROM actions WHERE action_id = ?", (action_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown action_id: {action_id}")
    if row["status"] != "VERIFY_PENDING":
        raise ValueError("Action must be VERIFY_PENDING before recording an outcome")
    timestamp = now()
    result = json.dumps(
        {"outcome": target, "evidence": evidence, "recorded_at": timestamp}
    )
    db.execute(
        "UPDATE actions SET status = ?, verification_result = ? WHERE action_id = ?",
        (target, result, action_id),
    )
    db.execute(
        """
        INSERT INTO action_events
        (action_id, event_type, from_status, to_status, actor, note,
         metadata_json, created_at)
        VALUES (?, 'VERIFICATION_RECORDED', 'VERIFY_PENDING', ?, ?, ?, ?, ?)
        """,
        (action_id, target, actor, evidence, result, timestamp),
    )
    db.commit()


def action_history(db: sqlite3.Connection, action_id: str) -> list[dict]:
    rows = db.execute(
        """
        SELECT event_id, event_type, from_status, to_status, actor, note,
               metadata_json, created_at
          FROM action_events
         WHERE action_id = ?
         ORDER BY event_id
        """,
        (action_id,),
    ).fetchall()
    history = []
    for row in rows:
        item = dict(row)
        item["metadata"] = (
            json.loads(item.pop("metadata_json")) if item.get("metadata_json") else None
        )
        history.append(item)
    return history


def get_action(db: sqlite3.Connection, action_id: str) -> dict:
    row = db.execute("SELECT * FROM actions WHERE action_id = ?", (action_id,)).fetchone()
    if not row:
        raise ValueError(f"Unknown action_id: {action_id}")
    item = dict(row)
    item["evidence"] = json.loads(item.pop("evidence_json"))
    item["acceptance_criteria"] = json.loads(item.pop("acceptance_json"))
    next_steps = item.pop("next_steps_json", None)
    limitations = item.pop("limitations_json", None)
    item["next_steps"] = json.loads(next_steps) if next_steps else []
    item["limitations"] = json.loads(limitations) if limitations else []
    item["verification_result"] = (
        json.loads(item["verification_result"]) if item.get("verification_result") else None
    )
    item["history"] = action_history(db, action_id)
    return item


def list_actions(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        """
        SELECT action_id, priority, status, confidence, owner_role, title,
               occurrence_count, first_seen_at, last_seen_at, assigned_to,
               due_date, verification_due_at, external_system, external_id,
               external_url
          FROM actions
         ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,
                  first_seen_at
        """
    ).fetchall()
    return [dict(row) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("brief", type=Path)
    sync.add_argument("--actor", default="agent")
    sub.add_parser("list")
    move = sub.add_parser("transition")
    move.add_argument("action_id")
    move.add_argument("to_status", choices=sorted(ALLOWED_TRANSITIONS))
    move.add_argument("--actor", required=True)
    move.add_argument("--note", default="")
    args = parser.parse_args()
    db = connect(args.db)
    if args.command == "sync":
        result = sync_run(
            db,
            json.loads(args.brief.read_text(encoding="utf-8")),
            args.actor,
        )
        print(json.dumps(result))
    elif args.command == "list":
        print(json.dumps(list_actions(db), indent=2))
    else:
        transition(db, args.action_id, args.to_status, args.actor, args.note)
        print(f"{args.action_id}: {args.to_status}")


if __name__ == "__main__":
    main()
