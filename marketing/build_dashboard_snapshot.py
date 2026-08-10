"""Build the public-safe decision workspace used by the ANKA Agent demo.

The snapshot contains aggregate marketing evidence only. It deliberately keeps
data availability separate from zero performance so the UI cannot imply that a
missing connector, privacy threshold, or attribution key is a real zero.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "working" / "reports"
AGENT_RUNS = ROOT / "working" / "agent_runs"
ACTION_DB = ROOT / "working" / "agent_state" / "actions.sqlite3"
DEFAULT_OUTPUT = ROOT / "demo" / "data" / "marketing_snapshot.json"


def latest(pattern: str, directory: Path = REPORTS) -> Path:
    matches = sorted(directory.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No report matches {pattern}")
    return matches[-1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def percent(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator * 100, 2) if denominator else None


def channel_group(source_medium: str) -> str:
    text = source_medium.lower()
    if "not set" in text:
        return "Unknown / not set"
    if "direct" in text:
        return "Direct"
    if "mail" in text or "newsletter" in text:
        return "Email"
    if "pinterest" in text:
        return "Pinterest"
    if "tiktok" in text:
        return "TikTok"
    if "instagram" in text or text.startswith("ig /") or "igshopping" in text:
        return "Instagram"
    if "facebook" in text or text.startswith("fb /"):
        return "Facebook"
    if "organic" in text and any(x in text for x in ("google", "bing", "search")):
        return "Organic search"
    if "paid" in text:
        return "Paid social"
    if "referral" in text:
        return "Referral"
    return "Other"


def aggregate_sources(rows: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row in rows:
        channel = channel_group(row["source_medium"])
        bucket = grouped.setdefault(
            channel,
            {"channel": channel, "sessions": 0, "active_users": 0, "transactions": 0, "revenue": 0.0},
        )
        bucket["sessions"] += int(row.get("sessions") or 0)
        bucket["active_users"] += int(row.get("active_users") or 0)
        bucket["transactions"] += int(row.get("transactions") or 0)
        bucket["revenue"] += float(row.get("purchase_revenue") or 0)
    for row in grouped.values():
        row["revenue"] = round(row["revenue"], 2)
        row["session_conversion_rate"] = percent(row["transactions"], row["sessions"])
        row["revenue_per_session"] = round(row["revenue"] / row["sessions"], 2) if row["sessions"] else None
    return sorted(grouped.values(), key=lambda row: row["sessions"], reverse=True)


def audience_cut(cut: dict | None, *, buyer_dimension: bool = False) -> dict:
    if not cut:
        return {"status": "not_collected", "reason": "Run the current GA4 connector.", "rows": []}
    rows = []
    for row in cut.get("rows", []):
        item = dict(row)
        item["session_conversion_rate"] = percent(item.get("transactions", 0), item.get("sessions", 0))
        rows.append(item)
    known_purchase_rows = [
        row for row in rows
        if row.get("transactions", 0) and str(row.get("segment", "")).lower() not in {"unknown", "(not set)"}
    ]
    status = str(cut.get("status", "UNAVAILABLE")).lower()
    reason = cut.get("reason")
    if buyer_dimension and status == "available" and not known_purchase_rows:
        status = "traffic_only"
        reason = "Traffic demographics are available, but all purchases are in the unknown bucket."
    return {"status": status, "reason": reason, "rows": rows}


def campaign_segment(name: str) -> str:
    if "North America" in name:
        return "North America"
    if "Europe" in name:
        return "Europe & Africa"
    if "French" in name:
        return "French"
    if "Latin America" in name:
        return "Latin America"
    if "Australia" in name:
        return "Australia"
    return "Other"


def action_center(brief: dict | None, db_path: Path = ACTION_DB) -> dict:
    if not brief:
        return {
            "status": "not_generated",
            "summary": "Run the evidence-to-action agent to generate proposals.",
            "human_gate": "Every external action requires human approval.",
            "actions": [],
            "not_authorized": [],
        }
    registry: dict[str, dict] = {}
    if db_path.exists():
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        try:
            registry = {
                row["action_id"]: dict(row)
                for row in db.execute(
                    "SELECT action_id, status, occurrence_count, first_seen_at, last_seen_at FROM actions"
                )
            }
        finally:
            db.close()
    actions = []
    for source in brief.get("actions", []):
        row = dict(source)
        state = registry.get(row["action_id"], {})
        row["status"] = state.get("status", row.get("status", "PROPOSED"))
        row["occurrence_count"] = state.get("occurrence_count", 1)
        row["first_seen_at"] = state.get("first_seen_at")
        row["last_seen_at"] = state.get("last_seen_at")
        actions.append(row)
    return {
        "status": "ready",
        "summary": brief.get("operating_summary", {}).get("decision"),
        "business_reason": brief.get("operating_summary", {}).get("business_reason"),
        "human_gate": brief.get("operating_summary", {}).get("human_gate"),
        "actions": actions,
        "not_authorized": brief.get("not_authorized", []),
    }


def build_snapshot(ga4: dict, meta: dict, mailer: dict, agent_brief: dict | None = None) -> dict:
    current = ga4["current"]
    previous = ga4.get("previous")
    traffic = current["traffic"]
    commerce = current["commerce"]
    funnel = current["funnel"]
    audit = current["transaction_audit"]
    quality = ga4["quality"]
    meta_week = meta["this_week"]
    instagram = meta_week["instagram"]["insights"]
    facebook = meta_week["facebook"]["insights"]
    email = mailer["summary"]
    grouped_sources = aggregate_sources(traffic["sources"])
    previous_sources = aggregate_sources(previous["traffic"]["sources"]) if previous else []

    def clean_sessions(rows: list[dict]) -> int:
        return sum(
            int(row.get("sessions") or 0)
            for row in rows
            if row.get("channel") not in {"Direct", "Unknown / not set"}
        )

    current_clean_sessions = clean_sessions(grouped_sources)
    previous_clean_sessions = clean_sessions(previous_sources)

    for row in grouped_sources:
        row["share"] = percent(row["sessions"], traffic["sessions"])
    by_channel = {row["channel"]: row for row in grouped_sources}
    unknown = by_channel.get("Unknown / not set", {})
    attributed_transactions = commerce["transactions"] - int(unknown.get("transactions") or 0)
    attributed_revenue = commerce["purchase_revenue"] - float(unknown.get("revenue") or 0)

    def channel(name: str, *, native: dict | None, native_status: str, blocker: str | None = None) -> dict:
        website = by_channel.get(name, {})
        return {
            "channel": name,
            "native": native,
            "website": {
                "sessions": int(website.get("sessions") or 0),
                "transactions": int(website.get("transactions") or 0),
                "revenue": round(float(website.get("revenue") or 0), 2),
                "session_conversion_rate": website.get("session_conversion_rate"),
            },
            "native_status": native_status,
            "revenue_attribution_status": (
                "unreliable" if commerce["transactions"] and not attributed_transactions else "directional"
            ),
            "blocker": blocker,
        }

    channels = [
        channel(
            "Instagram",
            native={
                "reach": instagram.get("reach"),
                "views": instagram.get("views"),
                "profile_views": instagram.get("profile_views"),
                "interactions": instagram.get("total_interactions"),
            },
            native_status="connected",
            blocker="Purchases are not retaining acquisition source.",
        ),
        channel(
            "TikTok",
            native=None,
            native_status="not_connected",
            blocker="Complete TikTok Business OAuth and confirm account scope.",
        ),
        channel(
            "Facebook",
            native={"followers": facebook.get("followers_count")},
            native_status="partial",
            blocker="Meta App Review blocks Page insight metrics; follower context only.",
        ),
        channel(
            "Pinterest",
            native=None,
            native_status="ga4_traffic_only",
            blocker="Pinterest native analytics/API is not connected; GA4 sessions are available.",
        ),
        channel(
            "Email",
            native={
                "sent": email.get("total_sent"),
                "opens": email.get("total_opens"),
                "clicks": email.get("total_clicks"),
            },
            native_status="connected",
            blocker="Campaign clicks are not connected to orders.",
        ),
    ]

    funnel_rows = [
        {"step": "Sessions", "users": traffic["sessions"], "status": "available"},
        {"step": "Product view", "users": funnel["view_item"]["users"], "status": "available" if funnel["view_item"]["users"] else "missing"},
        {"step": "Add to cart", "users": funnel["add_to_cart"]["users"], "status": "available"},
        {"step": "Begin checkout", "users": funnel["begin_checkout"]["users"], "status": "available"},
        {"step": "Payment info", "users": funnel["add_payment_info"]["users"], "status": "available" if funnel["add_payment_info"]["users"] else "missing"},
        {"step": "Purchase users", "users": funnel["purchase"]["users"], "status": "review"},
        {"step": "Transactions", "users": commerce["transactions"], "status": "available"},
    ]

    campaigns = [
        {
            "name": row["name"],
            "segment": campaign_segment(row["name"]),
            "sent": row["sent"],
            "opens": row["opens"],
            "clicks": row["clicks"],
            "open_rate": row["open_rate"],
            "click_rate": row["click_rate"],
        }
        for row in mailer["campaigns"]
    ]
    campaign_dates = sorted(row.get("sent_at") for row in mailer["campaigns"] if row.get("sent_at"))
    audience = current.get("audience", {})
    country_rows = audience.get("country", {}).get("rows", [])
    age_rows = audience.get("age", {}).get("rows", [])
    interest_rows = audience.get("interests", {}).get("rows", [])
    country_transactions = sum(int(row.get("transactions") or 0) for row in country_rows)
    country_revenue = round(sum(float(row.get("purchase_revenue") or 0) for row in country_rows), 2)
    known_age_transactions = sum(
        int(row.get("transactions") or 0)
        for row in age_rows
        if str(row.get("segment", "")).lower() not in {"unknown", "(not set)"}
    )
    interest_transactions = sum(int(row.get("transactions") or 0) for row in interest_rows)
    eventbrite_sessions = sum(
        int(row.get("sessions") or 0)
        for row in traffic["sources"]
        if "eventbrite" in row["source_medium"].lower()
    )
    top_items = [
        {
            "item_id": row.get("item_id"),
            "item_name": row.get("item_name"),
            "items_purchased": row.get("items_purchased"),
            "item_revenue": row.get("item_revenue"),
        }
        for row in current.get("items", {}).get("top_items", [])[:12]
    ]

    issues = list(quality["issues"])
    if commerce["transactions"] and attributed_transactions == 0:
        issues.append(
            {
                "severity": "blocked",
                "code": "PURCHASE_SOURCE_NOT_SET",
                "message": (
                    f"All {commerce['transactions']} transactions and {commerce['purchase_revenue']:,.2f} "
                    "of GA4 purchase revenue are assigned to (not set), so channel revenue attribution is unusable."
                ),
            }
        )

    return {
        "meta": {
            "title": "ANKA Marketing Decision Workspace",
            "schema_version": "2.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {"since": current["start_date"], "until": current["end_date"]},
            "source_periods": {
                "ga4": {"since": current["start_date"], "until": current["end_date"]},
                "meta": meta_week["period"],
                "mailerlite": {
                    "since": campaign_dates[0] if campaign_dates else None,
                    "until": campaign_dates[-1] if campaign_dates else None,
                },
            },
            "snapshot_type": "sanitized aggregate decision snapshot",
        },
        "executive_summary": {
            "decision": "Fix acquisition identity before changing channel budgets; use country and product purchase data for directional merchandising decisions in parallel.",
            "why": (
                f"GA4 reports {commerce['transactions']} transactions and {commerce['purchase_revenue']:,.2f} revenue "
                "in the GA4 property currency, "
                "but the transactions are not connected to a usable marketing source."
            ),
            "can_do_now": [
                "Monitor website, checkout, transaction and reported GA4 revenue trends.",
                "Compare native Instagram attention and MailerLite campaign engagement.",
                "Compare country-level sessions, transactions and reported revenue directionally.",
                "Review purchased products and prioritize measurement fixes through the Action Center.",
            ],
            "cannot_do_yet": [
                "Move budget based on channel revenue, CAC or ROAS.",
                "Know whether TikTok, Instagram, Pinterest or email caused an order.",
                "Analyze purchaser age or interests reliably.",
                "Measure website-to-Eventbrite registration or attendance conversion.",
                "Calculate net revenue, refunds, margin or customer lifetime value without the order ledger.",
            ],
        },
        "kpis": {
            "sessions": traffic["sessions"],
            "active_users": traffic["active_users"],
            "transactions": commerce["transactions"],
            "revenue": commerce["purchase_revenue"],
            "revenue_per_session": round(commerce["purchase_revenue"] / traffic["sessions"], 2) if traffic["sessions"] else None,
            "checkout_to_transaction_rate": percent(commerce["transactions"], commerce["checkouts"]),
            "session_to_transaction_rate": percent(commerce["transactions"], traffic["sessions"]),
            "instagram_reach": instagram["reach"],
            "instagram_views": instagram["views"],
            "email_sends": email["total_sent"],
            "email_clicks": email["total_clicks"],
            "attributed_transactions": attributed_transactions,
            "attributed_revenue": round(attributed_revenue, 2),
            "transaction_attribution_coverage": percent(attributed_transactions, commerce["transactions"]),
        },
        "comparison": {
            "metric": "known_channel_sessions",
            "definition": "GA4 sessions assigned to a non-Direct, non-Unknown channel group",
            "previous": {
                "label": "Previous week",
                "since": previous["start_date"] if previous else None,
                "until": previous["end_date"] if previous else None,
                "value": previous_clean_sessions if previous else None,
            },
            "current": {
                "label": "Current week",
                "since": current["start_date"],
                "until": current["end_date"],
                "value": current_clean_sessions,
            },
            "change_pct": percent(
                current_clean_sessions - previous_clean_sessions,
                previous_clean_sessions,
            ) if previous else None,
        },
        "action_center": action_center(agent_brief),
        "traffic_sources": grouped_sources,
        "source_detail": [
            {
                "source_medium": row["source_medium"],
                "sessions": row["sessions"],
                "transactions": row.get("transactions", 0),
                "revenue": row.get("purchase_revenue", 0),
            }
            for row in traffic["sources"][:30]
        ],
        "channels": channels,
        "funnel": funnel_rows,
        "audience": {
            "country": audience_cut(audience.get("country"), buyer_dimension=False),
            "age": audience_cut(audience.get("age"), buyer_dimension=True),
            "interests": audience_cut(audience.get("interests"), buyer_dimension=True),
            "buyer_identity_warning": "Country has purchase signal; age and interest purchases are currently all unknown.",
        },
        "products": {
            "status": "purchase_only",
            "reason": "Purchased-item revenue is available, but view_item is missing and backend margin/refund data is not connected.",
            "top_items": top_items,
            "not_yet_measurable": [
                "product view-to-cart rate",
                "product view-to-purchase rate",
                "product margin and return rate",
                "frequently purchased-together baskets",
                "coupon incrementality",
            ],
        },
        "events": {
            "status": "not_connected",
            "eventbrite_referral_sessions": eventbrite_sessions,
            "funnel": [
                {"step": "Website event-page visitors", "value": None, "status": "needs tagged event page"},
                {"step": "Eventbrite outbound clicks", "value": None, "status": "needs select_content / click event"},
                {"step": "Eventbrite registrations", "value": None, "status": "needs Eventbrite API or webhook"},
                {"step": "Paid / free orders", "value": None, "status": "needs Eventbrite order data"},
                {"step": "Attendees checked in", "value": None, "status": "needs attendee/check-in access"},
            ],
            "next_build": [
                "Give every event and outbound Eventbrite link a stable event_id plus UTMs.",
                "Connect Eventbrite private token and organization/event IDs on the backend.",
                "Join click, registration and attendance on event_id; do not expose attendee PII.",
            ],
        },
        "email_campaigns": campaigns,
        "quality": {
            "overall": "BLOCKED" if any(row["severity"] == "blocked" for row in issues) else quality["status"],
            "direct_share": quality["diagnostics"]["direct_session_share"],
            "purchase_events": funnel["purchase"]["event_count"],
            "transactions": commerce["transactions"],
            "transaction_id_audit": audit,
            "issues": issues,
            "reconciliation_checks": [
                {
                    "check": "Source sessions reconcile to GA4 total",
                    "status": "pass" if sum(row["sessions"] for row in grouped_sources) == traffic["sessions"] else "fail",
                    "evidence": f"{sum(row['sessions'] for row in grouped_sources):,} vs {traffic['sessions']:,}",
                },
                {
                    "check": "Source transactions reconcile to GA4 total",
                    "status": "pass" if sum(row["transactions"] for row in grouped_sources) == commerce["transactions"] else "fail",
                    "evidence": f"{sum(row['transactions'] for row in grouped_sources):,} vs {commerce['transactions']:,}",
                },
                {
                    "check": "Transaction IDs are usable at transaction grain",
                    "status": "pass" if audit["unique_transaction_ids"] == commerce["transactions"] and not audit["duplicate_transaction_id_rows"] else "fail",
                    "evidence": f"{audit['unique_transaction_ids']} unique IDs / {commerce['transactions']} transactions",
                },
                {
                    "check": "Country purchases reconcile",
                    "status": "pass" if country_transactions == commerce["transactions"] and abs(country_revenue - commerce["purchase_revenue"]) <= 0.05 else "fail",
                    "evidence": f"{country_transactions} transactions; {country_revenue:.2f} vs {commerce['purchase_revenue']:.2f} revenue",
                },
                {
                    "check": "Known-age purchaser coverage",
                    "status": "fail" if commerce["transactions"] and not known_age_transactions else "pass",
                    "evidence": f"{known_age_transactions} of {commerce['transactions']} transactions have a known age bucket",
                },
                {
                    "check": "Interest purchaser coverage",
                    "status": "fail" if commerce["transactions"] and not interest_transactions else "pass",
                    "evidence": f"{interest_transactions} of {commerce['transactions']} transactions appear in interest rows",
                },
                {
                    "check": "Cross-source reporting periods align",
                    "status": "fail" if meta_week["period"] != {"since": current["start_date"], "until": current["end_date"]} else "pass",
                    "evidence": f"GA4 {current['start_date']}–{current['end_date']}; Meta {meta_week['period']['since']}–{meta_week['period']['until']}",
                },
            ],
            "decision_rules": {
                "safe_now": [
                    "Monitor sessions, checkout, transactions and reported GA4 revenue.",
                    "Use country purchase and purchased-item rankings directionally.",
                    "Compare Instagram and email attention/engagement within their own platform definitions.",
                ],
                "not_safe_yet": [
                    "Channel ROAS, CAC or revenue contribution while purchases are (not set).",
                    "Net revenue, refunds, margin or LTV without the backend order ledger.",
                    "Product-view conversion while view_item is missing.",
                    "Payment-step abandonment while add_payment_info is missing.",
                    "Causal A/B-test conclusions without assignment and exposure data.",
                ],
            },
        },
        "data_sources": [
            {"source": "GA4", "period": f"{current['start_date']}–{current['end_date']}", "status": "connected_review", "provides": "traffic, funnel, transactions, reported revenue, country and purchased items", "missing": "usable purchase source; view_item; backend reconciliation"},
            {"source": "Instagram", "period": f"{meta_week['period']['since']}–{meta_week['period']['until']}", "status": "connected", "provides": "reach, views, profile views and interactions", "missing": "current-week refresh and reliable order attribution"},
            {"source": "Facebook", "period": f"{meta_week['period']['since']}–{meta_week['period']['until']}", "status": "partial", "provides": "follower context", "missing": "insights permission through Meta App Review"},
            {"source": "TikTok", "period": None, "status": "not_connected", "provides": "GA4-tagged website sessions only", "missing": "Business OAuth, account scope and API validation"},
            {"source": "Pinterest", "period": f"{current['start_date']}–{current['end_date']}", "status": "ga4_traffic_only", "provides": "GA4-tagged website sessions", "missing": "native analytics connector and order attribution"},
            {"source": "MailerLite", "period": f"{campaign_dates[0]}–{campaign_dates[-1]}" if campaign_dates else None, "status": "connected", "provides": "campaign sends, opens and clicks", "missing": "current-week refresh and campaign-to-order identity"},
            {"source": "Eventbrite", "period": None, "status": "not_connected", "provides": None, "missing": "event, registration, order and check-in integration"},
            {"source": "Backend orders", "period": None, "status": "not_connected", "provides": None, "missing": "paid/refunded status, net revenue, fees, margin, customer/order joins"},
        ],
        "experimentation": {
            "status": "NOT_READY",
            "available": ["GA4 sessions and commerce outcomes", "Aggregate channel and campaign engagement"],
            "missing": [
                "experiment_id", "variant_id", "assignment timestamp", "first exposure timestamp",
                "stable anonymous user or session key", "primary metric and guardrail definitions",
                "sample-size plan and minimum detectable effect",
            ],
            "first_demo": {
                "candidate": "Landing-page message test",
                "primary_metric": "begin_checkout users / exposed users",
                "guardrails": ["transactions / exposed users", "revenue / exposed user", "page error rate"],
                "warning": "Do not launch until exposure assignment is persisted and purchase duplication is fixed.",
            },
        },
        "ceo_feedback_coverage": [
            {"request": "Separate Instagram, TikTok, Facebook and Pinterest", "status": "implemented_with_availability"},
            {"request": "Country, age and interests", "status": "implemented_with_privacy_and_buyer_warnings"},
            {"request": "Traffic source to purchases", "status": "visible_but_blocked_by_not_set"},
            {"request": "Website to Eventbrite", "status": "integration_blueprint_ready_data_not_connected"},
            {"request": "Customer and product segments", "status": "product_purchase_view_available_customer_join_pending"},
        ],
    }


def validate_snapshot(snapshot: dict) -> list[str]:
    """Return human-readable contract errors; an empty list means valid."""
    errors: list[str] = []
    required_kpis = {"sessions", "transactions", "revenue", "revenue_per_session", "instagram_reach", "email_clicks"}
    if snapshot.get("meta", {}).get("schema_version") != "2.0.0":
        errors.append("unsupported or missing schema_version")
    missing = sorted(required_kpis - set(snapshot.get("kpis", {})))
    if missing:
        errors.append("missing KPI fields: " + ", ".join(missing))
    kpis = snapshot.get("kpis", {})
    if any((kpis.get(key) or 0) < 0 for key in ("sessions", "transactions", "revenue")):
        errors.append("sessions, transactions and revenue must be non-negative")
    source_total = sum(int(row.get("sessions") or 0) for row in snapshot.get("traffic_sources", []))
    if source_total != kpis.get("sessions"):
        errors.append(f"traffic source sessions {source_total} do not equal KPI sessions {kpis.get('sessions')}")
    if snapshot.get("quality", {}).get("transactions") != kpis.get("transactions"):
        errors.append("quality transaction count does not reconcile to KPI transactions")

    forbidden = {"access_token", "refresh_token", "api_key", "email", "phone", "address", "transaction_id", "customer_id", "ip_address", "user_agent"}

    def inspect(value: object, path: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in forbidden:
                    errors.append(f"forbidden field in public snapshot: {path}{key}")
                inspect(child, f"{path}{key}.")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                inspect(child, f"{path}{index}.")

    inspect(snapshot)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ga4", type=Path)
    parser.add_argument("--meta", type=Path)
    parser.add_argument("--mailerlite", type=Path)
    parser.add_argument("--agent-brief", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--public-demo-output",
        type=Path,
        help="Also write a validated aggregate fallback snapshot for the public static demo.",
    )
    args = parser.parse_args()

    ga4_path = args.ga4 or latest("ga4_raw_*.json")
    meta_path = args.meta or latest("meta_raw_*.json")
    mailer_path = args.mailerlite or latest("mailerlite_raw_*.json")
    if args.agent_brief:
        agent_brief_path = args.agent_brief
    else:
        briefs = sorted(AGENT_RUNS.glob("*_action_brief.json"))
        agent_brief_path = briefs[-1] if briefs else None
    snapshot = build_snapshot(
        read_json(ga4_path),
        read_json(meta_path),
        read_json(mailer_path),
        read_json(agent_brief_path) if agent_brief_path else None,
    )
    errors = validate_snapshot(snapshot)
    if errors:
        raise SystemExit("Snapshot validation failed:\n- " + "\n- ".join(errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Snapshot: {args.output}")
    if args.public_demo_output:
        public_demo = json.loads(json.dumps(snapshot))
        public_demo["meta"]["snapshot_type"] = "reviewed aggregate public demo snapshot"
        public_demo["meta"]["demo_mode"] = True
        args.public_demo_output.parent.mkdir(parents=True, exist_ok=True)
        args.public_demo_output.write_text(
            json.dumps(public_demo, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Public demo snapshot: {args.public_demo_output}")
    print(f"GA4: {ga4_path.name}; Meta: {meta_path.name}; MailerLite: {mailer_path.name}")
    print(f"Agent: {agent_brief_path.name if agent_brief_path else 'not generated'}")


if __name__ == "__main__":
    main()
