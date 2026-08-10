"""Evaluate due Agent actions against deterministic, source-backed rules."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from action_agent.registry import (
    DEFAULT_DB,
    connect,
    get_action,
    list_actions,
    record_verification,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "demo" / "data" / "marketing_snapshot.json"


def evaluate(action: dict, snapshot: dict) -> tuple[str, str]:
    codes = {row.get("code") for row in action.get("evidence", [])}
    quality = snapshot.get("quality", {})
    if "PURCHASE_EVENT_MISMATCH" in codes:
        audit = quality.get("transaction_id_audit", {})
        passed = (
            quality.get("purchase_events") == quality.get("transactions")
            and audit.get("missing_transaction_id_rows", 1) == 0
            and audit.get("duplicate_transaction_id_rows", 1) == 0
        )
        evidence = (
            f"Latest complete period has {quality.get('purchase_events')} purchase events, "
            f"{quality.get('transactions')} transactions, "
            f"{audit.get('missing_transaction_id_rows')} missing IDs and "
            f"{audit.get('duplicate_transaction_id_rows')} duplicate IDs."
        )
        return ("VERIFIED" if passed else "FAILED", evidence)

    if "VIEW_ITEM_EVENT_MISSING" in codes:
        funnel = {row.get("step"): int(row.get("users") or 0) for row in snapshot.get("funnel", [])}
        views = funnel.get("Product view", 0)
        carts = funnel.get("Add to cart", 0)
        passed = views > 0 and views >= carts
        return (
            "VERIFIED" if passed else "FAILED",
            f"Latest complete period has {views} product-view users and {carts} add-to-cart users.",
        )

    if "HIGH_DIRECT_SHARE" in codes or "PURCHASE_SOURCE_NOT_SET" in codes:
        coverage = float(snapshot.get("kpis", {}).get("transaction_attribution_coverage") or 0)
        passed = coverage >= 95
        return (
            "VERIFIED" if passed else "FAILED",
            f"Usable transaction attribution coverage is {coverage:.2f}%; V1 threshold is 95%."
        )

    if "EVENTBRITE_FUNNEL_NOT_CONNECTED" in codes:
        state = snapshot.get("events", {}).get("status", "not_connected")
        return (
            "VERIFIED" if state == "connected" else "FAILED",
            f"Eventbrite integration status is {state}.",
        )

    return (
        "INCONCLUSIVE",
        "No deterministic result rule is available for this action; human or experiment evidence is required.",
    )


def run_due_verifications(db, snapshot: dict, as_of: str | None = None) -> list[dict]:
    today = as_of or date.today().isoformat()
    results = []
    for summary in list_actions(db):
        due = summary.get("verification_due_at")
        if summary["status"] != "VERIFY_PENDING" or not due or due[:10] > today[:10]:
            continue
        action = get_action(db, summary["action_id"])
        outcome, evidence = evaluate(action, snapshot)
        record_verification(db, action["action_id"], outcome, "verification-agent", evidence)
        results.append(
            {"action_id": action["action_id"], "outcome": outcome, "evidence": evidence}
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify due ANKA Agent actions")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--as-of", help="Override evaluation date YYYY-MM-DD")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    results = run_due_verifications(connect(args.db), snapshot, args.as_of)
    print(json.dumps({"evaluated": len(results), "results": results}, indent=2))


if __name__ == "__main__":
    main()
