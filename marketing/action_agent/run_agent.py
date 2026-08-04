"""Convert reviewed marketing evidence into auditable proposed work items.

The agent is intentionally hybrid:
- deterministic code owns facts, quality gates, priority and guardrails;
- a language model may later improve wording or generate hypotheses;
- humans approve every external action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_dashboard_snapshot import validate_snapshot
from action_agent.registry import connect as registry_connect, sync_run


DEFAULT_SNAPSHOT = ROOT / "demo" / "data" / "marketing_snapshot.json"
DEFAULT_OUTPUT = ROOT / "working" / "agent_runs"
MAX_ACTIONS = 6


def fingerprint(title: str, evidence_codes: list[str]) -> str:
    raw = f"{title}|{'|'.join(sorted(evidence_codes))}".encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def action(
    *,
    title: str,
    workstream: str,
    priority: str,
    owner_role: str,
    decision: str,
    evidence: list[dict],
    confidence: str,
    why_it_matters: str,
    next_steps: list[str],
    acceptance_criteria: list[str],
    limitations: list[str],
    approval: str = "Vanessa",
) -> dict:
    codes = [row["code"] for row in evidence]
    return {
        "action_id": fingerprint(title, codes),
        "status": "PROPOSED",
        "title": title,
        "workstream": workstream,
        "priority": priority,
        "owner_role": owner_role,
        "decision": decision,
        "evidence": evidence,
        "confidence": confidence,
        "why_it_matters": why_it_matters,
        "next_steps": next_steps,
        "acceptance_criteria": acceptance_criteria,
        "limitations": limitations,
        "approval_required_from": approval,
    }


def engineering_actions(snapshot: dict) -> list[dict]:
    quality = snapshot["quality"]
    period = snapshot["meta"]["period"]
    actions: list[dict] = []
    issue_codes = {row["code"] for row in quality["issues"]}

    if "PURCHASE_EVENT_MISMATCH" in issue_codes:
        actions.append(
            action(
                title="Remove the duplicate client-side purchase signal",
                workstream="measurement_reliability",
                priority="P0",
                owner_role="Checkout / Analytics Engineer",
                decision="Prioritize this before using GA4 revenue for channel or experiment decisions.",
                evidence=[
                    {
                        "code": "PURCHASE_EVENT_MISMATCH",
                        "metric": "purchase events vs transactions",
                        "value": f"{quality['purchase_events']} vs {quality['transactions']}",
                        "source": "GA4 Data API",
                        "period": period,
                    }
                ],
                confidence="HIGH",
                why_it_matters=(
                    "Duplicate purchase signals can overstate conversion and revenue, "
                    "which contaminates attribution, experiments and finance reconciliation."
                ),
                next_steps=[
                    "Inventory every purchase tag in GTM and application code.",
                    "Disable the empty/residual browser purchase tag in a controlled release.",
                    "Keep the idempotent server-side purchase event as the canonical GA4 signal.",
                ],
                acceptance_criteria=[
                    "Daily purchase event count equals unique transaction ID count for 7 consecutive complete days.",
                    "No purchase row has a missing transaction ID or zero revenue.",
                    "Release date and tag change are recorded in the measurement changelog.",
                ],
                limitations=["Backend paid orders are still needed to prove financial completeness."],
            )
        )

    if "VIEW_ITEM_EVENT_MISSING" in issue_codes:
        actions.append(
            action(
                title="Instrument product-detail views before optimizing the product funnel",
                workstream="measurement_reliability",
                priority="P0",
                owner_role="Marketplace Frontend Engineer",
                decision="Implement and validate view_item before reporting product-view conversion.",
                evidence=[
                    {
                        "code": "VIEW_ITEM_EVENT_MISSING",
                        "metric": "view_item users vs add_to_cart users",
                        "value": (
                            f"{next(x['users'] for x in snapshot['funnel'] if x['step']=='Product view')} "
                            f"vs {next(x['users'] for x in snapshot['funnel'] if x['step']=='Add to cart')}"
                        ),
                        "source": "GA4 Data API",
                        "period": period,
                    }
                ],
                confidence="HIGH",
                why_it_matters=(
                    "Without product views, ANKA cannot separate discovery problems from "
                    "product-page, pricing or merchandising problems."
                ),
                next_steps=[
                    "Fire view_item once when a product detail view is rendered.",
                    "Include item_id, item_name, item_category, currency and displayed price.",
                    "QA event order and item fields in GA4 DebugView and the Data API.",
                ],
                acceptance_criteria=[
                    "view_item appears on tested product-detail pages with required item fields.",
                    "view_item users are non-zero and logically exceed or equal add-to-cart users.",
                    "Test orders preserve the same item_id from view through purchase.",
                ],
                limitations=["Product profitability remains unavailable until order and seller data are connected."],
            )
        )

    if "PAYMENT_EVENT_MISSING" in issue_codes:
        actions.append(
            action(
                title="Instrument the payment-information checkout step",
                workstream="measurement_reliability",
                priority="P0",
                owner_role="Checkout Engineer",
                decision="Add add_payment_info at one agreed, user-visible checkout milestone.",
                evidence=[
                    {
                        "code": "PAYMENT_EVENT_MISSING",
                        "metric": "begin_checkout users vs add_payment_info users",
                        "value": (
                            f"{next(x['users'] for x in snapshot['funnel'] if x['step']=='Begin checkout')} "
                            f"vs {next(x['users'] for x in snapshot['funnel'] if x['step']=='Payment info')}"
                        ),
                        "source": "GA4 Data API",
                        "period": period,
                    }
                ],
                confidence="HIGH",
                why_it_matters=(
                    "The missing step prevents the team from separating form, shipping, "
                    "payment-method and payment-provider abandonment."
                ),
                next_steps=[
                    "Agree on the exact payment-step trigger with checkout engineering.",
                    "Fire the event once per checkout attempt, not on every field change.",
                    "Pass currency, value, coupon and payment_type when available and consented.",
                ],
                acceptance_criteria=[
                    "add_payment_info appears once at the agreed milestone in a test checkout.",
                    "Event users are non-zero and do not systematically exceed begin_checkout users.",
                    "The step is documented in the event specification.",
                ],
                limitations=["Payment failures still require a separate sanitized operational event or backend log."],
            )
        )

    if quality["direct_share"] >= 0.5:
        actions.append(
            action(
                title="Create one acquisition naming contract and payment-referral audit",
                workstream="attribution",
                priority="P1",
                owner_role="Marketing Operations + Analytics Engineer",
                decision="Do not allocate channel budget from GA4 until campaign identity coverage improves.",
                evidence=[
                    {
                        "code": "HIGH_DIRECT_SHARE",
                        "metric": "sessions classified as Direct",
                        "value": f"{quality['direct_share'] * 100:.1f}%",
                        "source": "GA4 Data API",
                        "period": period,
                    }
                ],
                confidence="HIGH",
                why_it_matters=(
                    "When most sessions have no attributable campaign, real channel winners "
                    "are hidden and paid/email/social performance can be credited to Direct."
                ),
                next_steps=[
                    "Define controlled source, medium, campaign and content values.",
                    "Audit the top active email, Meta, TikTok and partner links against the contract.",
                    "Audit payment-provider and marketplace domains for unwanted referrals.",
                ],
                acceptance_criteria=[
                    "At least 95% of audited active campaign links match the approved UTM contract.",
                    "Payment-provider domains are documented and handled without overwriting original acquisition.",
                    "A weekly unknown/direct share trend is reviewed for four complete weeks.",
                ],
                limitations=[
                    "A high Direct share can include legitimate direct visits; the agent does not assume all Direct traffic is broken."
                ],
            )
        )

    return actions


def growth_actions(snapshot: dict) -> list[dict]:
    period = snapshot["meta"]["source_periods"]["mailerlite"]
    campaigns = snapshot.get("email_campaigns", [])
    if not campaigns:
        return []

    candidates: list[tuple[float, dict, dict]] = []
    segments = sorted({row["segment"] for row in campaigns if row["segment"] != "Other"})
    for segment in segments:
        rows = [
            row for row in campaigns
            if row["segment"] == segment and int(row["sent"] or 0) >= 1_000
        ]
        if len(rows) < 3:
            continue
        median_open = statistics.median(row["open_rate"] for row in rows)
        benchmark = max(rows, key=lambda row: row["click_rate"])
        for row in rows:
            if (
                row["open_rate"] >= median_open
                and row["click_rate"] <= benchmark["click_rate"] * 0.65
            ):
                candidates.append((benchmark["click_rate"] - row["click_rate"], row, benchmark))
    if not candidates:
        return []
    _, strong_open, strongest_click = max(candidates, key=lambda item: item[0])

    return [
        action(
            title=f"Test the post-open email proposition in {strong_open['segment']}",
            workstream="growth_experiment",
            priority="P1",
            owner_role="CRM / Lifecycle Marketing",
            decision=(
                "Prepare a same-segment CTA/content test; do not interpret opens alone as commercial success."
            ),
            evidence=[
                {
                    "code": "OPEN_CLICK_GAP",
                    "metric": "same-segment high-open campaign",
                    "value": (
                        f"{strong_open['name']}: {strong_open['open_rate']:.2f}% open, "
                        f"{strong_open['click_rate']:.2f}% click, {strong_open['sent']:,} sent"
                    ),
                    "source": "MailerLite API",
                    "period": period,
                },
                {
                    "code": "CLICK_BENCHMARK",
                    "metric": "best same-segment campaign click rate",
                    "value": (
                        f"{strongest_click['name']}: {strongest_click['click_rate']:.2f}%, "
                        f"{strongest_click['sent']:,} sent"
                    ),
                    "source": "MailerLite API",
                    "period": period,
                },
            ],
            confidence="MEDIUM",
            why_it_matters=(
                "A strong subject-line response with weaker clicks suggests a possible "
                "message, offer or CTA handoff problem worth testing."
            ),
            next_steps=[
                f"Use the {strong_open['segment']} segment and hold audience/timing constant.",
                "Test one CTA or offer-framing change against the current email.",
                "Pre-register the primary metric as unique clicks per delivered email.",
            ],
            acceptance_criteria=[
                "The test changes one main variable and uses a pre-defined sample split.",
                "Unique click rate and unsubscribe rate are reported by variant.",
                "No revenue winner is declared until campaign-to-order attribution exists.",
            ],
            limitations=[
                "Campaigns differ by audience and creative, so the current comparison is hypothesis-generating, not causal."
            ],
        )
    ]


def content_actions(meta_raw: dict | None) -> list[dict]:
    if not meta_raw:
        return []
    week = meta_raw.get("this_week", {})
    posts = week.get("instagram", {}).get("posts", [])
    reaches = [int(row.get("reach") or 0) for row in posts if int(row.get("reach") or 0) > 0]
    if len(reaches) < 3:
        return []
    top = max(posts, key=lambda row: int(row.get("reach") or 0))
    median = statistics.median(reaches)
    if int(top.get("reach") or 0) < median * 1.5:
        return []
    return [
        action(
            title="Deconstruct the strongest Instagram post into a repeatable content hypothesis",
            workstream="content_learning",
            priority="P2",
            owner_role="Social Content Lead",
            decision="Create two follow-up posts that reuse one identifiable creative mechanism, not the full post.",
            evidence=[
                {
                    "code": "INSTAGRAM_REACH_OUTLIER",
                    "metric": "top post reach vs median post reach",
                    "value": f"{int(top.get('reach') or 0):,} vs {median:,.0f}",
                    "source": "Meta Graph API",
                    "period": week.get("period", {}),
                }
            ],
            confidence="MEDIUM",
            why_it_matters=(
                "A materially stronger post is useful as a hypothesis source, but repeating it "
                "without isolating the mechanism will not create transferable learning."
            ),
            next_steps=[
                "Code the post for hook, format, subject, creator presence and call to action.",
                "Reuse one mechanism in two posts while varying the creative execution.",
                "Add campaign-tagged link or profile-action measurement where possible.",
            ],
            acceptance_criteria=[
                "The hypothesized mechanism is written before publishing follow-ups.",
                "Follow-up reach and profile intent are compared with the account median.",
                "The result is recorded as supported, unsupported or inconclusive.",
            ],
            limitations=[
                "Post-level engagement fields are currently incomplete, and reach alone is not revenue."
            ],
        )
    ]


def event_integration_actions(snapshot: dict) -> list[dict]:
    events = snapshot.get("events", {})
    if events.get("status") != "not_connected":
        return []
    period = snapshot["meta"]["period"]
    return [
        action(
            title="Connect the website-to-Eventbrite registration and attendance funnel",
            workstream="event_measurement",
            priority="P1",
            owner_role="Marketing Engineer + Events Operations",
            decision=(
                "Instrument one upcoming event end to end before using event traffic or "
                "city-interest polls to choose locations."
            ),
            evidence=[
                {
                    "code": "EVENTBRITE_FUNNEL_NOT_CONNECTED",
                    "metric": "measurable Eventbrite funnel stages",
                    "value": "0 of 5 stages connected",
                    "source": "ANKA integration inventory",
                    "period": period,
                }
            ],
            confidence="HIGH",
            why_it_matters=(
                "Without a shared event identity, ANKA cannot tell which platform or city "
                "campaign produces registrations, attendance, or post-event commercial value."
            ),
            next_steps=[
                "Assign a stable event_id and approved UTMs to the ANKA event page and every Eventbrite link.",
                "Track the outbound Eventbrite click with event_id before redirecting.",
                "Pull privacy-safe event, order, registration and check-in aggregates through the backend.",
            ],
            acceptance_criteria=[
                "A test journey preserves event_id and campaign identity from ANKA to Eventbrite.",
                "Registrations, paid/free orders and check-ins load daily without attendee PII in the dashboard.",
                "One completed event reconciles Eventbrite registrations and check-ins to the reported dashboard totals.",
            ],
            limitations=[
                "Post-event marketplace lift requires a separate consented, privacy-safe customer or campaign join."
            ],
        )
    ]


def priority_key(row: dict) -> tuple[int, int]:
    p = {"P0": 0, "P1": 1, "P2": 2}.get(row["priority"], 9)
    confidence = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(row["confidence"], 9)
    return p, confidence


def build_run(snapshot: dict, meta_raw: dict | None = None) -> dict:
    errors = validate_snapshot(snapshot)
    if errors:
        raise ValueError("Invalid snapshot: " + "; ".join(errors))
    proposed = (
        engineering_actions(snapshot)
        + event_integration_actions(snapshot)
        + growth_actions(snapshot)
        + content_actions(meta_raw)
    )
    proposed = sorted(proposed, key=priority_key)[:MAX_ACTIONS]
    return {
        "run": {
            "agent": "ANKA Evidence-to-Action Agent",
            "version": "0.1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evidence_period": snapshot["meta"]["period"],
            "mode": "PROPOSE_ONLY",
            "action_count": len(proposed),
        },
        "operating_summary": {
            "decision": (
                "Prioritize measurement reliability before channel budget optimization; "
                "run only low-risk learning work in parallel."
            ),
            "business_reason": (
                "The current bottleneck is not a lack of charts. It is that engineering and "
                "marketing cannot safely act on attribution, product-funnel or revenue signals yet."
            ),
            "human_gate": "Vanessa reviews proposed actions before any ticket, campaign or experiment is created.",
        },
        "actions": proposed,
        "not_authorized": [
            "Change campaign budgets",
            "Publish content",
            "Declare an A/B-test winner",
            "Close an engineering issue",
            "Expose customer or credential data",
        ],
    }


def issue_markdown(row: dict) -> str:
    evidence = "\n".join(
        f"- **{x['metric']}:** {x['value']} ({x['source']})" for x in row["evidence"]
    )
    steps = "\n".join(f"- [ ] {x}" for x in row["next_steps"])
    acceptance = "\n".join(f"- [ ] {x}" for x in row["acceptance_criteria"])
    limits = "\n".join(f"- {x}" for x in row["limitations"])
    return f"""## Decision

{row['decision']}

## Why this matters

{row['why_it_matters']}

## Evidence

{evidence}

Confidence: **{row['confidence']}**

## Proposed work

{steps}

## Acceptance criteria

{acceptance}

## Limitations

{limits}

Owner role: **{row['owner_role']}**
Approval required from: **{row['approval_required_from']}**
Agent action ID: `{row['action_id']}`
"""


def run_markdown(run: dict) -> str:
    sections = [
        "# ANKA Evidence-to-Action Brief",
        "",
        f"**Decision:** {run['operating_summary']['decision']}",
        "",
        run["operating_summary"]["business_reason"],
        "",
        f"Human gate: {run['operating_summary']['human_gate']}",
        "",
    ]
    for index, row in enumerate(run["actions"], 1):
        sections.extend(
            [
                f"## {index}. [{row['priority']}] {row['title']}",
                "",
                issue_markdown(row),
            ]
        )
    sections.extend(
        [
            "## Agent boundary",
            "",
            *[f"- {item}" for item in run["not_authorized"]],
            "",
        ]
    )
    return "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--meta-raw", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-registry", action="store_true")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    meta_raw = (
        json.loads(args.meta_raw.read_text(encoding="utf-8"))
        if args.meta_raw
        else None
    )
    result = build_run(snapshot, meta_raw)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    json_path = args.output_dir / f"{stamp}_action_brief.json"
    md_path = args.output_dir / f"{stamp}_action_brief.md"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    md_path.write_text(run_markdown(result), encoding="utf-8")
    issues = args.output_dir / f"{stamp}_issue_drafts"
    issues.mkdir(exist_ok=True)
    for row in result["actions"]:
        (issues / f"{row['priority']}_{row['action_id']}.md").write_text(
            f"# {row['title']}\n\n{issue_markdown(row)}",
            encoding="utf-8",
        )
    if not args.no_registry:
        registry_result = sync_run(registry_connect(), result)
        print(
            f"Registry: {registry_result['inserted']} new, "
            f"{registry_result['updated']} seen again"
        )
    print(result["operating_summary"]["decision"])
    for row in result["actions"]:
        print(f"{row['priority']} · {row['confidence']} · {row['owner_role']} · {row['title']}")
    print(f"Brief: {md_path}")


if __name__ == "__main__":
    main()
