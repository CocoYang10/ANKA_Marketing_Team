"""Generate a Basecamp-copyable weekly report from the reviewed Agent snapshot.

The output deliberately uses inline-styled text and tables only. It contains no
SVG, canvas, external assets, credentials, customer identifiers, or publishing
integration. Vanessa remains the human review and copy/paste gate.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = ROOT / "demo" / "data" / "marketing_snapshot.json"
DEFAULT_REPORTS = ROOT / "working" / "reports"
AGENT_URL = "https://cocoyang10.github.io/ANKA_Marketing_Team/marketing/demo/"

CELL = "border:1px solid #aeb8b2;padding:7px 9px;text-align:left;font-size:13px;vertical-align:top;"
NUM_CELL = CELL + "text-align:right;font-variant-numeric:tabular-nums;"
HEAD = CELL + "background:#edf3ef;color:#24372c;font-weight:700;"
SECTION = "font-size:18px;margin:30px 0 8px;border-bottom:2px solid #245c3b;padding-bottom:4px;color:#1f4f35;"
LIST = "margin:5px 0 12px;padding-left:24px;"
ITEM = "margin-bottom:7px;line-height:1.5;"


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else "—"), quote=True)


def number(value: object) -> str:
    if value is None:
        return "—"
    numeric = float(value)
    if abs(numeric) >= 1_000_000:
        return f"{numeric / 1_000_000:.1f}M"
    if abs(numeric) >= 10_000:
        return f"{numeric / 1_000:.1f}K"
    return f"{numeric:,.0f}"


def decimal(value: object) -> str:
    return "—" if value is None else f"{float(value):,.2f}"


def percent(value: object, *, signed: bool = False) -> str:
    if value is None:
        return "—"
    numeric = float(value)
    return f"{'+' if signed and numeric > 0 else ''}{numeric:.1f}%"


def table(headers: list[str], rows: list[list[tuple[object, bool]]]) -> str:
    header = "".join(f'<th style="{HEAD}">{esc(label)}</th>' for label in headers)
    body = []
    for row in rows:
        cells = "".join(
            f'<td style="{NUM_CELL if numeric else CELL}">{value}</td>'
            for value, numeric in row
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        '<table style="border-collapse:collapse;width:100%;margin:10px 0 17px;">'
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def badge(label: str, status: str) -> str:
    key = status.lower()
    if key in {"connected", "ready", "available", "pass", "verified"}:
        style = "background:#eaf6ee;color:#1d693f;"
    elif key in {"not_connected", "missing", "blocked", "failed", "unreliable"}:
        style = "background:#fdebea;color:#9a382f;"
    else:
        style = "background:#fff4d8;color:#845a00;"
    return f'<span style="{style}font-weight:700;padding:3px 7px;border-radius:999px;">{esc(label)}</span>'


def native_summary(channel: dict) -> str:
    native = channel.get("native") or {}
    if not native:
        return "Native metrics unavailable"
    return " · ".join(f"{esc(key.replace('_', ' '))} {number(value)}" for key, value in native.items())


def report_period(snapshot: dict) -> tuple[date, date]:
    period = snapshot["meta"]["period"]
    return date.fromisoformat(period["since"]), date.fromisoformat(period["until"])


def build_report(snapshot: dict) -> str:
    since, until = report_period(snapshot)
    week = until.isocalendar().week
    kpis = snapshot["kpis"]
    comparison = snapshot.get("comparison", {})
    actions = snapshot.get("action_center", {}).get("actions", [])
    attribution = float(kpis.get("transaction_attribution_coverage") or 0)
    funnel = {row["step"]: row for row in snapshot.get("funnel", [])}
    product_view = funnel.get("Product view", {})
    add_cart = funnel.get("Add to cart", {})
    checkout = funnel.get("Begin checkout", {})
    purchase_users = funnel.get("Purchase users", {})
    known_change = comparison.get("change_pct")
    current_known = comparison.get("current", {}).get("value")
    previous_known = comparison.get("previous", {}).get("value")

    if attribution < 95:
        attribution_summary = (
            f"<strong>Revenue is visible, but channel attribution remains blocked.</strong> "
            f"GA4 reports {number(kpis.get('transactions'))} transactions and {decimal(kpis.get('revenue'))} "
            f"of reported revenue, while only {percent(attribution)} of transactions retain a usable source. "
            "Do not use this report for CAC, ROAS, or budget allocation by channel."
        )
    else:
        attribution_summary = (
            f"<strong>Purchase attribution coverage is decision-ready.</strong> "
            f"{percent(attribution)} of transactions retain a usable source; backend reconciliation still applies."
        )

    summary_items = [
        attribution_summary,
        (
            f"<strong>Known-channel traffic moved {percent(known_change, signed=True)} week over week.</strong> "
            f"Sessions assigned to non-Direct, non-Unknown channels changed from {number(previous_known)} "
            f"to {number(current_known)}. This is an acquisition-quality signal, not proof of caused orders."
        ),
        (
            "<strong>The commerce funnel is still a measurement funnel.</strong> "
            f"Product views are {'missing' if product_view.get('status') == 'missing' else 'available'}, "
            f"while {number(add_cart.get('users'))} users added to cart, {number(checkout.get('users'))} began checkout, "
            f"and {number(purchase_users.get('users'))} purchase-event users map to {number(kpis.get('transactions'))} transactions."
        ),
        (
            "<strong>The operating priority is measurement reliability before optimization.</strong> "
            f"The Action Center has {number(len(actions))} auditable proposals with owners and completion tests; "
            "all execution remains subject to human approval."
        ),
    ]

    channel_rows = []
    for channel in snapshot.get("channels", []):
        website = channel.get("website", {})
        status_key = channel.get("native_status", "review")
        channel_rows.append(
            [
                (f"<b>{esc(channel.get('channel'))}</b>", False),
                (native_summary(channel), False),
                (number(website.get("sessions")), True),
                (f"{number(website.get('transactions'))} / {decimal(website.get('revenue'))}", True),
                (badge(status_key.replace("_", " ").title(), status_key), False),
                (esc(channel.get("blocker") or "No current blocker recorded"), False),
            ]
        )

    funnel_rows = []
    for row in snapshot.get("funnel", []):
        label = "Unavailable" if row.get("status") == "missing" else number(row.get("users"))
        read = {
            "missing": "Tracking is missing; do not treat as zero performance.",
            "review": "Recorded, but requires reconciliation before conversion claims.",
            "available": "Observed aggregate stage volume.",
        }.get(row.get("status"), "Review metric definition.")
        funnel_rows.append(
            [
                (esc(row.get("step")), False),
                (label, True),
                (badge(row.get("status", "review").title(), row.get("status", "review")), False),
                (esc(read), False),
            ]
        )

    source_rows = []
    for source in snapshot.get("data_sources", []):
        source_rows.append(
            [
                (f"<b>{esc(source.get('source'))}</b>", False),
                (badge(source.get("status", "review").replace("_", " ").title(), source.get("status", "review")), False),
                (esc(source.get("provides") or "Unavailable"), False),
                (esc(source.get("missing") or "No material gap recorded"), False),
            ]
        )

    action_rows = []
    for index, action in enumerate(actions[:8], start=1):
        done = action.get("acceptance_criteria") or []
        action_rows.append(
            [
                (esc(index), True),
                (f"<b>{esc(action.get('title'))}</b><br>{esc(action.get('decision'))}", False),
                (esc(action.get("assigned_to") or action.get("owner_role")), False),
                (esc(done[0] if done else "Completion test not recorded"), False),
                (badge(action.get("status", "PROPOSED").title(), action.get("status", "PROPOSED")), False),
            ]
        )

    questions = [
        "Who owns the GTM container and will confirm the view_item forwarding and empty or duplicate Purchase tag?",
        "When will the client-side purchase and GTM fixes be released, and what seven-day window should Marketing use for validation?",
        "Which backend order source will reconcile paid orders, refunds, currency and net revenue against GA4?",
        "Who can provide seller account, catalog and order aggregates so buyer demand and seller performance can be analyzed separately?",
        "Which Eventbrite event should be used for the first event × channel tracking-link pilot?",
        "When will Meta Page insights and TikTok analytics become available through a repeatable API or reviewed export?",
    ]

    caveats = snapshot.get("quality", {}).get("decision_rules", {}).get("not_safe_yet", [])
    period_label = f"{since.strftime('%B %-d')}–{until.strftime('%-d, %Y')}"
    generated = datetime.fromisoformat(snapshot["meta"]["generated_at"].replace("Z", "+00:00"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Basecamp Copy — Marketing report Week {week}</title>
  <style>
    body{{font-family:Arial,Helvetica,sans-serif;color:#17211b;background:#f5f7f6;margin:0;padding:24px 12px 48px}}
    .toolbar{{max-width:900px;margin:0 auto 14px;background:#173e2a;color:#fff;padding:14px 16px;border-radius:8px;display:flex;gap:12px;align-items:center;justify-content:space-between;position:sticky;top:8px;z-index:3;box-shadow:0 4px 18px rgba(0,0,0,.14)}}
    .toolbar p{{margin:0;line-height:1.4;font-size:13px}}button{{background:#fff;color:#173e2a;border:0;border-radius:6px;padding:10px 15px;font-weight:700;cursor:pointer;white-space:nowrap}}
    #report{{max-width:900px;margin:0 auto;background:#fff;padding:24px 18px 40px;box-shadow:0 4px 20px rgba(0,0,0,.08)}}
    @media(max-width:700px){{.toolbar{{position:static;display:block}}.toolbar button{{margin-top:10px;width:100%}}#report{{padding:18px 10px;overflow-x:auto}}}}
    @media print{{.toolbar{{display:none}}body{{background:#fff;padding:0}}#report{{box-shadow:none}}}}
  </style>
</head>
<body>
  <div class="toolbar"><p><strong>Basecamp version:</strong> Review once, click Copy report, and paste into the Basecamp editor. This version contains copyable text and tables only.</p><button id="copyButton" type="button" onclick="copyReport()">Copy report</button></div>
  <main id="report">
    <p style="margin:0;font-size:12px;font-weight:700;letter-spacing:.07em;color:#527060;">ANKA AFRICA — MARKETING PERFORMANCE REPORT</p>
    <h1 style="font-size:22px;margin:4px 0;color:#17211b;">Marketing report Week {week} ({esc(period_label)})</h1>
    <p style="font-style:italic;font-size:12.75px;color:#4f5e55;line-height:1.45;">Latest complete reporting week. Generated from the reviewed aggregate Agent snapshot; unavailable data is shown as unavailable, never as zero.</p>
    <div style="background:#f2f8f4;border-left:4px solid #2c7a50;padding:10px 12px;margin:10px 0 18px;line-height:1.7;"><strong>Marketing Decision Agent:</strong> <a style="color:#126e45;font-weight:700;text-decoration:underline;" href="{AGENT_URL}">Open the current demo</a></div>

    <h2 style="{SECTION}">Executive Summary</h2>
    <ul style="{LIST}">{''.join(f'<li style="{ITEM}">{item}</li>' for item in summary_items)}</ul>

    <h2 style="{SECTION}">Channel Scorecard</h2>
    <p style="line-height:1.52;margin:7px 0 12px;"><strong>Read:</strong> native platform performance and GA4 website activity are shown side by side, but they are not treated as one attribution chain until purchase-source coverage is repaired.</p>
    {table(['Channel', 'Native evidence', 'Website sessions', 'Orders / revenue', 'Data status', 'Current blocker'], channel_rows)}

    <h2 style="{SECTION}">Website &amp; Commerce</h2>
    <div style="border:1px solid #c4cec8;border-left:4px solid #d59b1a;padding:9px 11px;margin:11px 0;background:#fff9eb;line-height:1.5;"><strong>Attribution limitation:</strong> transaction attribution coverage is {percent(attribution)}. Channel conversion, CAC, ROAS and channel-revenue contribution remain unavailable.</div>
    {table(['Tracked stage', 'Users', 'Status', 'Business read'], funnel_rows)}

    <h2 style="{SECTION}">Data Health</h2>
    <p style="line-height:1.52;margin:7px 0 12px;"><strong>Connected does not automatically mean decision-ready.</strong> The gaps below determine which recommendations the Agent blocks.</p>
    {table(['Source', 'Status', 'Usable now', 'Missing / next'], source_rows)}

    <h2 style="{SECTION}">Recommended Actions</h2>
    <p style="line-height:1.52;margin:7px 0 12px;">Actions come from the reviewed Action Center. Vanessa approves, rejects or reassigns them before execution.</p>
    {table(['Priority', 'Action', 'Owner', 'Done when', 'Status'], action_rows)}

    <h2 style="{SECTION}">Questions to Close</h2>
    <ol style="{LIST}">{''.join(f'<li style="{ITEM}">{esc(item)}</li>' for item in questions)}</ol>

    <h2 style="{SECTION}">Caveats &amp; Assumptions</h2>
    <ul style="{LIST}">{''.join(f'<li style="{ITEM}">{esc(item)}</li>' for item in caveats)}</ul>
    <p style="margin-top:26px;color:#657068;font-size:11px;">Snapshot generated {generated.strftime('%B %-d, %Y at %H:%M UTC')}. Aggregate evidence only; no credentials, customer identifiers or transaction IDs are included.</p>
  </main>
  <script>
    async function copyReport(){{
      const report=document.getElementById('report'),button=document.getElementById('copyButton'),html=report.innerHTML,text=report.innerText;
      try{{
        if(navigator.clipboard&&window.ClipboardItem){{await navigator.clipboard.write([new ClipboardItem({{'text/html':new Blob([html],{{type:'text/html'}}),'text/plain':new Blob([text],{{type:'text/plain'}})}})])}}
        else{{const range=document.createRange();range.selectNode(report);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);document.execCommand('copy');selection.removeAllRanges()}}
        button.textContent='Copied — paste into Basecamp';
      }}catch(error){{button.textContent='Select the report and copy manually'}}
    }}
  </script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Basecamp-ready ANKA weekly report")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    since, until = report_period(snapshot)
    week = until.isocalendar().week
    report_date = until + timedelta(days=1)
    output = args.output or DEFAULT_REPORTS / f"{report_date.isoformat()}_Marketing-Report-Week-{week}_Basecamp.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_report(snapshot), encoding="utf-8")
    print(f"Basecamp report: {output}")


if __name__ == "__main__":
    main()
