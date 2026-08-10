"""Persistent lifecycle and audit log for Agent-proposed actions."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "working" / "agent_state" / "actions.sqlite3"
ALLOWED_TRANSITIONS = {
    "PROPOSED": {"APPROVED", "REJECTED"},
    "APPROVED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"VERIFY_PENDING", "BLOCKED", "CANCELLED"},
    "BLOCKED": {"IN_PROGRESS", "CANCELLED"},
    "VERIFY_PENDING": {"VERIFIED", "FAILED"},
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
            created_at TEXT NOT NULL
        );
        """
    )
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
            "SELECT status, occurrence_count FROM actions WHERE action_id = ?",
            (row["action_id"],),
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE actions
                   SET title = ?, priority = ?, workstream = ?, owner_role = ?,
                       confidence = ?, evidence_json = ?, acceptance_json = ?,
                       last_seen_at = ?, last_evidence_period = ?,
                       occurrence_count = occurrence_count + 1
                 WHERE action_id = ?
                """,
                (
                    row["title"],
                    row["priority"],
                    row["workstream"],
                    row["owner_role"],
                    row["confidence"],
                    json.dumps(row["evidence"]),
                    json.dumps(row["acceptance_criteria"]),
                    timestamp,
                    period,
                    row["action_id"],
                ),
            )
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
                 last_seen_at, last_evidence_period, occurrence_count)
                VALUES (?, ?, ?, ?, ?, 'PROPOSED', ?, ?, ?, ?, ?, ?, 1)
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


def list_actions(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        """
        SELECT action_id, priority, status, confidence, owner_role, title,
               occurrence_count, first_seen_at, last_seen_at
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
