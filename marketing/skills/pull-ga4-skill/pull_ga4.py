"""
Pull GA4 acquisition, funnel, purchase, and revenue health for ANKA.

This script deliberately separates "the API responded" from "the data is safe
to use". It writes aggregated diagnostics only; raw transaction IDs are never
written to output files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    Metric,
    OrderBy,
    RunReportRequest,
)
from google.api_core.exceptions import GoogleAPICallError


MARKETING_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(MARKETING_ROOT / ".env")

PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "").strip()
TRUSTED_FROM_RAW = os.getenv("GA4_TRUSTED_FROM", "2026-07-23").strip()
OUTPUT_DIR = MARKETING_ROOT / "working" / "reports"

FUNNEL_EVENTS = [
    "view_item",
    "add_to_cart",
    "view_cart",
    "begin_checkout",
    "add_shipping_info",
    "add_payment_info",
    "purchase",
    "refund",
]

FUNNEL_FIELDS = [
    "id", "week", "dateRange", "section", "channel", "metric", "value", "unit",
    "previousWeek", "previousValue", "changeValue", "changePct", "status",
    "sourceReport", "notes",
]


@dataclass
class QualityIssue:
    severity: str
    code: str
    message: str


def parse_iso(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}; use YYYY-MM-DD") from exc


def completed_week() -> tuple[str, str]:
    """Return the latest completed Monday-Sunday period."""
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    end = current_monday - timedelta(days=1)
    start = end - timedelta(days=6)
    return start.isoformat(), end.isoformat()


def previous_period(start: str, end: str) -> tuple[str, str]:
    start_date = parse_iso(start)
    end_date = parse_iso(end)
    span = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=span - 1)
    return previous_start.isoformat(), previous_end.isoformat()


def week_label(start: str) -> str:
    return f"W{parse_iso(start).isocalendar().week}"


def date_range_label(start: str, end: str) -> str:
    start_date, end_date = parse_iso(start), parse_iso(end)
    return f"{start_date.strftime('%b')} {start_date.day}-{end_date.strftime('%b')} {end_date.day}, {end_date.year}"


def number(value: str) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def integer(value: str) -> int:
    return int(round(number(value)))


def pct_change(current: float, previous: float | None) -> float | None:
    if previous in (None, 0):
        return None
    return (current - previous) / previous


def quality_status(issues: list[QualityIssue]) -> str:
    severities = {issue.severity for issue in issues}
    if "blocked" in severities:
        return "BLOCKED"
    if "review" in severities:
        return "REVIEW"
    return "TRUSTED"


class GA4Connector:
    def __init__(self, property_id: str):
        if not property_id:
            raise RuntimeError("GA4_PROPERTY_ID is missing from .env")
        self.property_id = property_id
        self.client = BetaAnalyticsDataClient()

    def run(
        self,
        start: str,
        end: str,
        metrics: list[str],
        dimensions: list[str] | None = None,
        *,
        event_names: list[str] | None = None,
        limit: int = 10000,
        order_metric: str | None = None,
    ):
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start, end_date=end)],
            metrics=[Metric(name=name) for name in metrics],
            dimensions=[Dimension(name=name) for name in (dimensions or [])],
            limit=limit,
        )
        if event_names:
            request.dimension_filter = FilterExpression(
                filter=Filter(
                    field_name="eventName",
                    in_list_filter=Filter.InListFilter(values=event_names),
                )
            )
        if order_metric:
            request.order_bys = [
                OrderBy(
                    metric=OrderBy.MetricOrderBy(metric_name=order_metric),
                    desc=True,
                )
            ]
        return self.client.run_report(request)

    def traffic(self, start: str, end: str) -> dict[str, Any]:
        response = self.run(
            start,
            end,
            [
                "sessions",
                "activeUsers",
                "engagedSessions",
                "averageSessionDuration",
                "transactions",
                "purchaseRevenue",
            ],
            ["sessionSourceMedium"],
            limit=1000,
            order_metric="sessions",
        )
        sources = []
        totals = {"sessions": 0, "active_users": 0, "engaged_sessions": 0}
        weighted_duration = 0.0
        for row in response.rows:
            sessions = integer(row.metric_values[0].value)
            active_users = integer(row.metric_values[1].value)
            engaged_sessions = integer(row.metric_values[2].value)
            duration = number(row.metric_values[3].value)
            transactions = integer(row.metric_values[4].value)
            purchase_revenue = number(row.metric_values[5].value)
            source = row.dimension_values[0].value or "(not set)"
            sources.append(
                {
                    "source_medium": source,
                    "sessions": sessions,
                    "active_users": active_users,
                    "engaged_sessions": engaged_sessions,
                    "average_session_duration": round(duration, 1),
                    "transactions": transactions,
                    "purchase_revenue": round(purchase_revenue, 2),
                }
            )
            totals["sessions"] += sessions
            totals["active_users"] += active_users
            totals["engaged_sessions"] += engaged_sessions
            weighted_duration += sessions * duration
        total_sessions = totals["sessions"]
        return {
            **totals,
            "engagement_rate": (
                round(totals["engaged_sessions"] / total_sessions, 4) if total_sessions else 0
            ),
            "average_session_duration": (
                round(weighted_duration / total_sessions, 1) if total_sessions else 0
            ),
            "sources": sources,
        }

    def _audience_cut(
        self,
        start: str,
        end: str,
        dimension: str,
        label: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Pull one privacy-safe aggregate audience cut without failing GA4."""
        try:
            response = self.run(
                start,
                end,
                ["activeUsers", "sessions", "transactions", "purchaseRevenue"],
                [dimension],
                limit=limit,
                order_metric="activeUsers",
            )
        except GoogleAPICallError as exc:
            return {
                "status": "UNAVAILABLE",
                "dimension": dimension,
                "label": label,
                "rows": [],
                "reason": type(exc).__name__,
            }
        rows = []
        for row in response.rows:
            rows.append(
                {
                    "segment": row.dimension_values[0].value or "(not set)",
                    "active_users": integer(row.metric_values[0].value),
                    "sessions": integer(row.metric_values[1].value),
                    "transactions": integer(row.metric_values[2].value),
                    "purchase_revenue": round(number(row.metric_values[3].value), 2),
                }
            )
        return {
            "status": "AVAILABLE" if rows else "NO_DATA",
            "dimension": dimension,
            "label": label,
            "rows": rows,
            "reason": None if rows else "GA4 returned no rows for this period.",
        }

    def audience(self, start: str, end: str) -> dict[str, Any]:
        return {
            "country": self._audience_cut(start, end, "country", "Country", 100),
            "age": self._audience_cut(start, end, "userAgeBracket", "Age", 20),
            "interests": self._audience_cut(
                start, end, "brandingInterest", "Interests", 100
            ),
        }

    def commerce(self, start: str, end: str) -> dict[str, Any]:
        response = self.run(
            start,
            end,
            ["checkouts", "transactions", "purchaseRevenue", "totalRevenue"],
        )
        if not response.rows:
            return {"checkouts": 0, "transactions": 0, "purchase_revenue": 0.0, "total_revenue": 0.0}
        values = response.rows[0].metric_values
        return {
            "checkouts": integer(values[0].value),
            "transactions": integer(values[1].value),
            "purchase_revenue": round(number(values[2].value), 2),
            "total_revenue": round(number(values[3].value), 2),
        }

    def event_funnel(self, start: str, end: str) -> dict[str, dict[str, int]]:
        response = self.run(
            start,
            end,
            ["eventCount", "totalUsers"],
            ["eventName"],
            event_names=FUNNEL_EVENTS,
        )
        result = {name: {"event_count": 0, "users": 0} for name in FUNNEL_EVENTS}
        for row in response.rows:
            event_name = row.dimension_values[0].value
            if event_name in result:
                result[event_name] = {
                    "event_count": integer(row.metric_values[0].value),
                    "users": integer(row.metric_values[1].value),
                }
        return result

    def transaction_audit(self, start: str, end: str) -> dict[str, Any]:
        response = self.run(
            start,
            end,
            ["transactions", "purchaseRevenue"],
            ["transactionId"],
            limit=10000,
        )
        unique_ids = 0
        missing_id_rows = 0
        zero_revenue_rows = 0
        duplicate_id_rows = 0
        audited_transactions = 0
        audited_revenue = 0.0
        for row in response.rows:
            transaction_id = row.dimension_values[0].value.strip()
            transactions = integer(row.metric_values[0].value)
            revenue = number(row.metric_values[1].value)
            audited_transactions += transactions
            audited_revenue += revenue
            if not transaction_id or transaction_id == "(not set)":
                missing_id_rows += 1
            else:
                unique_ids += 1
            if revenue == 0:
                zero_revenue_rows += 1
            if transactions > 1:
                duplicate_id_rows += 1
        return {
            "unique_transaction_ids": unique_ids,
            "audited_transactions": audited_transactions,
            "audited_purchase_revenue": round(audited_revenue, 2),
            "missing_transaction_id_rows": missing_id_rows,
            "zero_revenue_rows": zero_revenue_rows,
            "duplicate_transaction_id_rows": duplicate_id_rows,
        }

    def item_summary(self, start: str, end: str) -> dict[str, Any]:
        response = self.run(
            start,
            end,
            ["itemsPurchased", "itemRevenue"],
            ["itemId", "itemName"],
            limit=100,
            order_metric="itemRevenue",
        )
        items = []
        for row in response.rows:
            item_id = row.dimension_values[0].value
            item_name = row.dimension_values[1].value
            items.append(
                {
                    "item_id": item_id,
                    "item_name": item_name,
                    "items_purchased": integer(row.metric_values[0].value),
                    "item_revenue": round(number(row.metric_values[1].value), 2),
                }
            )
        return {
            "item_rows": len(items),
            "missing_item_id_rows": sum(
                1 for item in items if not item["item_id"] or item["item_id"] == "(not set)"
            ),
            "top_items": items[:20],
        }


def evaluate_quality(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    start: str,
    end: str,
) -> dict[str, Any]:
    issues: list[QualityIssue] = []
    traffic = current["traffic"]
    commerce = current["commerce"]
    audit = current["transaction_audit"]
    funnel = current["funnel"]

    sessions = traffic["sessions"]
    direct_sessions = next(
        (row["sessions"] for row in traffic["sources"] if row["source_medium"] == "(direct) / (none)"),
        0,
    )
    not_set_sessions = sum(
        row["sessions"] for row in traffic["sources"] if "(not set)" in row["source_medium"].lower()
    )
    direct_share = direct_sessions / sessions if sessions else 0
    not_set_share = not_set_sessions / sessions if sessions else 0

    if direct_share > 0.70 and sessions >= 1000:
        issues.append(
            QualityIssue("review", "HIGH_DIRECT_SHARE", f"Direct accounts for {direct_share:.1%} of sessions.")
        )
    if not_set_share > 0.05:
        issues.append(
            QualityIssue("review", "HIGH_NOT_SET_SHARE", f"(not set) accounts for {not_set_share:.1%} of sessions.")
        )

    if previous and previous["traffic"]["sessions"]:
        ratio = sessions / previous["traffic"]["sessions"]
        if ratio >= 3 or ratio <= 1 / 3:
            issues.append(
                QualityIssue(
                    "review",
                    "SESSION_STEP_CHANGE",
                    f"Sessions changed {ratio:.2f}x versus the preceding period; investigate bots, tagging, consent, or deployment changes.",
                )
            )

    if commerce["checkouts"] and not commerce["transactions"]:
        issues.append(
            QualityIssue("blocked", "PURCHASE_MISSING", "Checkouts exist but transactions are zero.")
        )
    if commerce["transactions"] and commerce["purchase_revenue"] <= 0:
        issues.append(
            QualityIssue("blocked", "REVENUE_MISSING", "Transactions exist but purchase revenue is zero.")
        )
    if audit["missing_transaction_id_rows"]:
        issues.append(
            QualityIssue(
                "blocked",
                "MISSING_TRANSACTION_ID",
                f"{audit['missing_transaction_id_rows']} transaction row(s) have a missing transaction ID.",
            )
        )
    if audit["zero_revenue_rows"]:
        issues.append(
            QualityIssue(
                "review",
                "ZERO_REVENUE_PURCHASE",
                f"{audit['zero_revenue_rows']} transaction row(s) have zero purchase revenue.",
            )
        )
    if audit["duplicate_transaction_id_rows"]:
        issues.append(
            QualityIssue(
                "blocked",
                "DUPLICATE_TRANSACTION_ID",
                f"{audit['duplicate_transaction_id_rows']} transaction ID row(s) contain more than one transaction.",
            )
        )

    trusted_from = parse_iso(TRUSTED_FROM_RAW)
    if parse_iso(start) < trusted_from:
        issues.append(
            QualityIssue(
                "review",
                "PRE_REPAIR_PERIOD",
                f"The period includes dates before the purchase-tracking repair boundary ({trusted_from.isoformat()}).",
            )
        )

    begin_users = funnel["begin_checkout"]["users"]
    view_item_users = funnel["view_item"]["users"]
    add_to_cart_users = funnel["add_to_cart"]["users"]
    shipping_users = funnel["add_shipping_info"]["users"]
    payment_users = funnel["add_payment_info"]["users"]
    purchase_users = funnel["purchase"]["users"]
    purchase_event_count = funnel["purchase"]["event_count"]
    if add_to_cart_users and view_item_users == 0:
        issues.append(
            QualityIssue(
                "review",
                "VIEW_ITEM_EVENT_MISSING",
                "Add-to-cart users exist but view_item is zero; the top of the product funnel is not measurable.",
            )
        )
    if begin_users and shipping_users > begin_users:
        issues.append(
            QualityIssue("review", "SHIPPING_SEQUENCE", "Shipping users exceed begin-checkout users.")
        )
    if begin_users and payment_users == 0:
        issues.append(
            QualityIssue("review", "PAYMENT_EVENT_MISSING", "Begin checkout exists but add_payment_info is zero.")
        )
    if purchase_users and commerce["transactions"] == 0:
        issues.append(
            QualityIssue("blocked", "FUNNEL_TRANSACTION_MISMATCH", "Purchase users exist but transactions are zero.")
        )
    if commerce["transactions"] and purchase_event_count > commerce["transactions"] * 1.10:
        issues.append(
            QualityIssue(
                "review",
                "PURCHASE_EVENT_MISMATCH",
                f"GA4 recorded {purchase_event_count} purchase events but {commerce['transactions']} transactions; investigate the residual client-side/GTM purchase tag.",
            )
        )

    return {
        "status": quality_status(issues),
        "issues": [asdict(issue) for issue in issues],
        "diagnostics": {
            "direct_session_share": round(direct_share, 4),
            "not_set_session_share": round(not_set_share, 4),
            "checkout_to_transaction_rate": (
                round(commerce["transactions"] / commerce["checkouts"], 4)
                if commerce["checkouts"]
                else None
            ),
        },
        "meaning": "API success only confirms access. This status evaluates whether the period is safe for marketing decisions.",
    }


def pull_period(connector: GA4Connector, start: str, end: str) -> dict[str, Any]:
    return {
        "start_date": start,
        "end_date": end,
        "traffic": connector.traffic(start, end),
        "audience": connector.audience(start, end),
        "commerce": connector.commerce(start, end),
        "funnel": connector.event_funnel(start, end),
        "transaction_audit": connector.transaction_audit(start, end),
        "items": connector.item_summary(start, end),
    }


def add_row(
    rows: list[dict[str, Any]],
    *,
    week: str,
    period_label: str,
    section: str,
    channel: str,
    metric: str,
    value: float,
    previous_week: str = "",
    previous_value: float | None = None,
    unit: str = "count",
    notes: str = "",
):
    change = pct_change(value, previous_value)
    status = ""
    if change is not None:
        status = "green" if change > 0.05 else "red" if change < -0.05 else "amber"
    safe_channel = re.sub(r"[^a-z0-9]+", "_", channel.lower()).strip("_")
    rows.append(
        {
            "id": f"{week.lower()}_{safe_channel}_{metric}",
            "week": week,
            "dateRange": period_label,
            "section": section,
            "channel": channel,
            "metric": metric,
            "value": value,
            "unit": unit,
            "previousWeek": previous_week,
            "previousValue": "" if previous_value is None else previous_value,
            "changeValue": "" if previous_value is None else value - previous_value,
            "changePct": "" if change is None else change,
            "status": status,
            "sourceReport": "ga4",
            "notes": notes,
        }
    )


def build_funnel_rows(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    quality: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    week = week_label(current["start_date"])
    previous_week = week_label(previous["start_date"]) if previous else ""
    label = date_range_label(current["start_date"], current["end_date"])

    current_metrics = {
        "sessions": current["traffic"]["sessions"],
        "active_users": current["traffic"]["active_users"],
        "engaged_sessions": current["traffic"]["engaged_sessions"],
        "average_session_duration": current["traffic"]["average_session_duration"],
        "checkouts": current["commerce"]["checkouts"],
        "transactions": current["commerce"]["transactions"],
        "purchase_revenue": current["commerce"]["purchase_revenue"],
        "total_revenue": current["commerce"]["total_revenue"],
    }
    previous_metrics = {}
    if previous:
        previous_metrics = {
            "sessions": previous["traffic"]["sessions"],
            "active_users": previous["traffic"]["active_users"],
            "engaged_sessions": previous["traffic"]["engaged_sessions"],
            "average_session_duration": previous["traffic"]["average_session_duration"],
            "checkouts": previous["commerce"]["checkouts"],
            "transactions": previous["commerce"]["transactions"],
            "purchase_revenue": previous["commerce"]["purchase_revenue"],
            "total_revenue": previous["commerce"]["total_revenue"],
        }

    for metric, value in current_metrics.items():
        section = "GA4 Website Traffic" if metric in {
            "sessions", "active_users", "engaged_sessions", "average_session_duration"
        } else "GA4 Commerce"
        unit = "currency" if "revenue" in metric else "seconds" if "duration" in metric else "count"
        add_row(
            rows,
            week=week,
            period_label=label,
            section=section,
            channel="Website",
            metric=metric,
            value=value,
            previous_week=previous_week,
            previous_value=previous_metrics.get(metric),
            unit=unit,
            notes=f"GA4 quality status: {quality['status']}.",
        )

    previous_sources = {
        row["source_medium"]: row for row in previous["traffic"]["sources"]
    } if previous else {}
    for source in current["traffic"]["sources"][:50]:
        previous_source = previous_sources.get(source["source_medium"], {})
        add_row(
            rows,
            week=week,
            period_label=label,
            section="GA4 Traffic Source",
            channel=source["source_medium"],
            metric="sessions",
            value=source["sessions"],
            previous_week=previous_week,
            previous_value=previous_source.get("sessions"),
            notes=f"Source/medium row; GA4 quality status: {quality['status']}.",
        )

    for event_name, values in current["funnel"].items():
        add_row(
            rows,
            week=week,
            period_label=label,
            section="GA4 Ecommerce Funnel",
            channel="Website",
            metric=f"{event_name}_users",
            value=values["users"],
            previous_week=previous_week,
            previous_value=(
                previous["funnel"].get(event_name, {}).get("users") if previous else None
            ),
            notes=f"Users triggering {event_name}; validate event semantics before decision use.",
        )
    return rows


def save_outputs(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    quality: dict[str, Any],
):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    payload = {
        "api_status": "CONNECTED",
        "property_id": PROPERTY_ID,
        "current": current,
        "previous": previous,
        "quality": quality,
    }
    json_path = OUTPUT_DIR / f"ga4_raw_{stamp}.json"
    csv_path = OUTPUT_DIR / f"ga4_funnel_metrics_{stamp}.csv"
    md_path = OUTPUT_DIR / f"ga4_summary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = build_funnel_rows(current, previous, quality)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FUNNEL_FIELDS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in FUNNEL_FIELDS} for row in rows)

    commerce = current["commerce"]
    lines = [
        "# GA4 Data Summary",
        "",
        f"- API status: CONNECTED",
        f"- Data quality: {quality['status']}",
        f"- Period: {current['start_date']} to {current['end_date']}",
        "",
        "## Core metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Sessions | {current['traffic']['sessions']:,} |",
        f"| Active users | {current['traffic']['active_users']:,} |",
        f"| Checkouts | {commerce['checkouts']:,} |",
        f"| Transactions | {commerce['transactions']:,} |",
        f"| Purchase revenue | {commerce['purchase_revenue']:,.2f} |",
        f"| Total revenue | {commerce['total_revenue']:,.2f} |",
        "",
        "## Data-quality findings",
        "",
    ]
    if quality["issues"]:
        lines.extend(
            f"- **{issue['severity'].upper()} — {issue['code']}**: {issue['message']}"
            for issue in quality["issues"]
        )
    else:
        lines.append("- No automated quality issues detected. Backend-order reconciliation is still required.")
    lines += [
        "",
        "## Transaction audit",
        "",
        *[
            f"- {key.replace('_', ' ').title()}: {value}"
            for key, value in current["transaction_audit"].items()
        ],
        "",
        "## Funnel users",
        "",
        "| Event | Users | Event count |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {event} | {values['users']:,} | {values['event_count']:,} |"
        for event, values in current["funnel"].items()
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, csv_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Pull and audit ANKA GA4 data")
    parser.add_argument("--weeks", type=int, choices=[1, 2], default=2)
    parser.add_argument("--since", type=parse_iso)
    parser.add_argument("--until", type=parse_iso)
    args = parser.parse_args()
    if bool(args.since) != bool(args.until):
        parser.error("--since and --until must be provided together")

    if args.since:
        start, end = args.since.isoformat(), args.until.isoformat()
    else:
        start, end = completed_week()
    if parse_iso(end) < parse_iso(start):
        parser.error("--until must be on or after --since")

    print(f"Connecting to GA4 property {PROPERTY_ID}...")
    connector = GA4Connector(PROPERTY_ID)
    current = pull_period(connector, start, end)
    previous = None
    if args.weeks == 2:
        previous_start, previous_end = previous_period(start, end)
        previous = pull_period(connector, previous_start, previous_end)
    quality = evaluate_quality(current, previous, start, end)
    paths = save_outputs(current, previous, quality)

    print(f"API status: CONNECTED")
    print(f"Data quality: {quality['status']}")
    print(f"Period: {start} to {end}")
    print(f"Sessions: {current['traffic']['sessions']:,}")
    print(f"Checkouts: {current['commerce']['checkouts']:,}")
    print(f"Transactions: {current['commerce']['transactions']:,}")
    print(f"Purchase revenue: {current['commerce']['purchase_revenue']:,.2f}")
    for issue in quality["issues"]:
        print(f"- {issue['severity'].upper()} {issue['code']}: {issue['message']}")
    for path in paths:
        print(f"Saved: {path.relative_to(MARKETING_ROOT)}")


if __name__ == "__main__":
    main()
