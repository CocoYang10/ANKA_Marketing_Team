"""
pull_mailerlite.py
------------------
Pulls recent MailerLite campaign data and outputs files for the weekly report.

Usage:
    python pull_mailerlite.py
    python pull_mailerlite.py --weeks 2     # pull last 2 weeks of data

Output files:
    working/reports/mailerlite_raw_[date].json
    working/reports/mailerlite_summary_[date].md
"""

import os
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# ── Load environment variables ─────────────────────────────────────────────────
MARKETING_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(MARKETING_ROOT / ".env")
API_KEY = os.getenv("MAILERLITE_API_KEY")
OUTPUT_DIR = MARKETING_ROOT / "working" / "reports"

if not API_KEY:
    raise SystemExit("❌ MAILERLITE_API_KEY not found — check your .env file")

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_URL = "https://connect.mailerlite.com/api"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Segment label mapping — update if Anka's actual segment names differ
SEGMENT_LABELS = {
    "french":        "French",
    "english_eu":    "English — Europe & Africa",
    "english_na":    "English — North America",
    "english_au":    "English — Australia",
    "latin_america": "Latin America",
}


# ── API calls ──────────────────────────────────────────────────────────────────
def get_campaigns(oldest_needed=None, max_pages=100):
    """Fetch newest-first pages and stop after passing the requested period."""
    url = f"{BASE_URL}/campaigns"
    campaigns = []
    oldest_needed_dt = (
        datetime.fromisoformat(oldest_needed).replace(tzinfo=timezone.utc)
        if oldest_needed
        else None
    )
    for page in range(1, max_pages + 1):
        params = {
            "filter[status]": "sent",
            "limit": 25,
            "page": page,
        }
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        page_campaigns = payload.get("data", [])
        campaigns.extend(page_campaigns)
        last_page = int(payload.get("meta", {}).get("last_page", page) or page)
        if page >= last_page:
            break
        page_dates = [
            parsed
            for parsed in (campaign_datetime(row) for row in page_campaigns)
            if parsed is not None
        ]
        if oldest_needed_dt and page_dates and min(page_dates) < oldest_needed_dt:
            break
    return campaigns


def get_campaign_stats(campaign_id):
    """Fetch detailed stats for a single campaign."""
    url = f"{BASE_URL}/campaigns/{campaign_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", {})


# ── Data processing ────────────────────────────────────────────────────────────
def campaign_datetime(campaign):
    raw = (
        campaign.get("started_at")
        or campaign.get("sent_at")
        or campaign.get("scheduled_for")
        or ""
    )
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def filter_by_range(campaigns, since, until):
    """Keep campaigns whose actual start time falls within an inclusive UTC range."""
    since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    until_dt = (
        datetime.fromisoformat(until).replace(tzinfo=timezone.utc)
        + timedelta(days=1)
    )
    result = []
    for c in campaigns:
        started = campaign_datetime(c)
        if started and since_dt <= started < until_dt:
            result.append(c)
    return result


def completed_week():
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    end = monday - timedelta(days=1)
    start = end - timedelta(days=6)
    return start.isoformat(), end.isoformat()


def parse_campaign(c):
    """Parse a campaign API response into a clean dict."""
    stats = c.get("stats", {})

    sent       = stats.get("sent", 0) or 0
    opens      = stats.get("opens_count", 0) or 0
    clicks     = stats.get("clicks_count", 0) or 0

    # open_rate and click_rate can be a float or a dict depending on API version
    open_rate  = (
        round(stats.get("open_rate", {}).get("float", 0) * 100, 2)
        if isinstance(stats.get("open_rate"), dict)
        else round((stats.get("open_rate") or 0) * 100, 2)
    )
    click_rate = (
        round(stats.get("click_rate", {}).get("float", 0) * 100, 2)
        if isinstance(stats.get("click_rate"), dict)
        else round((stats.get("click_rate") or 0) * 100, 2)
    )

    # Normalise sent_at to YYYY-MM-DD
    sent_at_raw = c.get("started_at") or c.get("sent_at") or c.get("scheduled_for") or ""
    try:
        sent_at_raw = sent_at_raw.replace("Z", "+00:00")
        sent_dt = datetime.fromisoformat(sent_at_raw)
        sent_at = sent_dt.strftime("%Y-%m-%d")
    except Exception:
        sent_at = sent_at_raw[:10]

    return {
        "id":         c.get("id"),
        "name":       c.get("name", ""),
        "subject":    c.get("emails", [{}])[0].get("subject", "") if c.get("emails") else "",
        "sent_at":    sent_at,
        "sent":       sent,
        "opens":      opens,
        "clicks":     clicks,
        "open_rate":  open_rate,   # e.g. 41.9 (percent)
        "click_rate": click_rate,  # e.g. 3.2  (percent)
        "status":     c.get("status", ""),
    }


def detect_segment(name):
    """Infer the audience segment from the campaign name."""
    n = name.lower()
    if "french" in n or "fr " in n or n.startswith("fr_") or "français" in n:
        return "French"
    if "latin" in n or "latam" in n or "amérique" in n:
        return "Latin America"
    if "australia" in n or "au " in n:
        return "English — Australia"
    if "north america" in n or "na " in n or "usa" in n:
        return "English — North America"
    return "English — Europe & Africa"  # default


def build_summary(campaigns_parsed):
    """Aggregate top-line metrics, matching the weekly report Top-Line section."""
    total_opens  = sum(c["opens"]  for c in campaigns_parsed)
    total_clicks = sum(c["clicks"] for c in campaigns_parsed)
    total_sent   = sum(c["sent"]   for c in campaigns_parsed)

    by_segment = {}
    for c in campaigns_parsed:
        seg = detect_segment(c["name"])
        if seg not in by_segment:
            by_segment[seg] = {"opens": 0, "clicks": 0, "campaigns": []}
        by_segment[seg]["opens"]  += c["opens"]
        by_segment[seg]["clicks"] += c["clicks"]
        by_segment[seg]["campaigns"].append(c["name"])

    return {
        "total_sent":   total_sent,
        "total_opens":  total_opens,
        "total_clicks": total_clicks,
        "by_segment":   by_segment,
    }


# ── Output ─────────────────────────────────────────────────────────────────────
def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved JSON → {path}")


def save_markdown(campaigns_parsed, summary, path):
    """Generate a markdown summary matching the weekly report template format."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# MailerLite Data Summary",
        f"Pulled: {today}",
        f"Campaigns: {len(campaigns_parsed)}",
        "",
        "---",
        "",
        "## Top-Line",
        "",
        "| Metric | This week |",
        "|--------|-----------|",
        f"| Total sends  | {summary['total_sent']:,} |",
        f"| Total opens  | {summary['total_opens']:,} |",
        f"| Total clicks | {summary['total_clicks']:,} |",
        "",
        "## By Segment",
        "",
        "| Segment | Opens | Clicks |",
        "|---------|-------|--------|",
    ]
    for seg, data in summary["by_segment"].items():
        lines.append(f"| {seg} | {data['opens']:,} | {data['clicks']:,} |")

    lines += [
        "",
        "---",
        "",
        "## Campaign Detail",
        "",
        "| Campaign | Sent date | Sends | Open rate | Click rate | Clicks |",
        "|----------|-----------|-------|-----------|------------|--------|",
    ]
    for c in campaigns_parsed:
        lines.append(
            f"| {c['name']} | {c['sent_at']} | {c['sent']:,} "
            f"| {c['open_rate']}% | {c['click_rate']}% | {c['clicks']:,} |"
        )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ Saved Markdown → {path}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pull MailerLite campaign data")
    parser.add_argument("--weeks", type=int, default=1,
                        help="Completed weeks to include when exact dates are omitted")
    parser.add_argument("--since", help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--until", help="Inclusive end date YYYY-MM-DD")
    args = parser.parse_args()
    if bool(args.since) != bool(args.until):
        parser.error("--since and --until must be provided together")

    today = datetime.now().strftime("%Y-%m-%d")
    if args.since:
        since, until = args.since, args.until
    else:
        current_start, until = completed_week()
        since = (
            datetime.fromisoformat(current_start).date()
            - timedelta(weeks=max(args.weeks - 1, 0))
        ).isoformat()

    print(f"\n🔄 Connecting to MailerLite API...")
    all_campaigns = get_campaigns(oldest_needed=since)
    print(f"   Found {len(all_campaigns)} sent campaigns total")

    recent = filter_by_range(all_campaigns, since, until)
    print(f"   Campaigns from {since} to {until}: {len(recent)}")

    if not recent:
        print("⚠️  No campaigns found — try --weeks 2 or --weeks 4")
        return

    # Fetch detailed stats for each campaign
    print(f"\n📊 Fetching detailed stats...")
    campaigns_parsed = []
    for c in recent:
        try:
            detail = get_campaign_stats(c["id"])
            parsed = parse_campaign(detail)
            campaigns_parsed.append(parsed)
            print(f"   ✓ {parsed['name'][:50]} | open: {parsed['open_rate']}% | clicks: {parsed['clicks']}")
        except Exception as e:
            print(f"   ✗ {c.get('name', c['id'])} — error: {e}")

    summary = build_summary(campaigns_parsed)

    # Save output files
    print(f"\n💾 Saving files...")
    json_path = OUTPUT_DIR / f"mailerlite_raw_{today}.json"
    md_path   = OUTPUT_DIR / f"mailerlite_summary_{today}.md"

    save_json({"campaigns": campaigns_parsed, "summary": summary}, json_path)
    save_markdown(campaigns_parsed, summary, md_path)

    # Print summary to terminal
    print(f"\n{'='*50}")
    print(f"📬 MailerLite Summary — This Week")
    print(f"{'='*50}")
    print(f"Total sends:  {summary['total_sent']:,}")
    print(f"Total opens:  {summary['total_opens']:,}")
    print(f"Total clicks: {summary['total_clicks']:,}")
    print(f"\nBy segment:")
    for seg, data in summary["by_segment"].items():
        print(f"  {seg:<30} opens: {data['opens']:>6,}  clicks: {data['clicks']:>4,}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
