"""
pull_meta.py
------------
Pulls Facebook Page and Instagram insights from the Meta Graph API.
Outputs raw JSON and a formatted markdown summary for the weekly report.

Usage:
    python pull_meta.py                  # pulls last 2 weeks (for W-on-W comparison)
    python pull_meta.py --weeks 1        # current week only

Output files:
    working/reports/meta_raw_[date].json
    working/reports/meta_summary_[date].md
"""

import os
import json
import csv
import argparse
import re
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# ── Load environment variables ─────────────────────────────────────────────────
MARKETING_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(MARKETING_ROOT / ".env")
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
PAGE_ID      = os.getenv("META_PAGE_ID", "").strip()
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v19.0").strip()
OUTPUT_DIR = MARKETING_ROOT / "working" / "reports"

if not ACCESS_TOKEN:
    raise SystemExit("❌ META_ACCESS_TOKEN not found — check your .env file")
if not PAGE_ID:
    raise SystemExit("❌ META_PAGE_ID not found — check your .env file")

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_URL   = f"https://graph.facebook.com/{GRAPH_VERSION}"
BASE_PARAMS = {"access_token": ACCESS_TOKEN}
FUNNEL_FIELDS = [
    "id", "week", "dateRange", "section", "channel", "metric", "value", "unit",
    "previousWeek", "previousValue", "changeValue", "changePct", "status",
    "sourceReport", "notes",
]


def redact_secret(text):
    """Remove token-like values from exception strings before printing."""
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"access_token=[^&\s)]+", "access_token=[REDACTED]", text)
    text = re.sub(r"EA[A-Za-z0-9_-]{20,}", "[REDACTED_META_TOKEN]", text)
    return text


def get_page_access_token():
    """Exchange system user token for a page-specific access token.
    The /PAGE_ID/posts endpoint requires a Page Access Token, not a system user token."""
    data = api_get(f"{BASE_URL}/{PAGE_ID}", {
        "fields": "access_token",
        "access_token": ACCESS_TOKEN,
    })
    if not data:
        return ACCESS_TOKEN
    if "access_token" in data:
        print("   ✓ Page Access Token obtained")
        return data["access_token"]
    print(f"   ⚠️  Could not get Page Access Token: {data.get('error', {}).get('message', data)}")
    return ACCESS_TOKEN  # fall back to system user token


# ── Helpers ────────────────────────────────────────────────────────────────────
def week_range(weeks_ago=0):
    """
    Return (since, until) Unix timestamps for a given week.
    weeks_ago=0 → this week (Mon–Sun)
    weeks_ago=1 → last week
    """
    today = datetime.now(timezone.utc)
    # Start of current week (Monday)
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    until = start_of_week - timedelta(weeks=weeks_ago)
    since = until - timedelta(weeks=1)

    return int(since.timestamp()), int(until.timestamp())


def completed_week():
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    end = monday - timedelta(days=1)
    start = end - timedelta(days=6)
    return start.isoformat(), end.isoformat()


def timestamp_range(since_date, until_date):
    """Convert inclusive ISO dates to Meta's [since, until) Unix timestamps."""
    since = datetime.fromisoformat(since_date).replace(tzinfo=timezone.utc)
    until = (
        datetime.fromisoformat(until_date).replace(tzinfo=timezone.utc)
        + timedelta(days=1)
    )
    return int(since.timestamp()), int(until.timestamp())


def api_get(url, params):
    """Make a GET request and return JSON data, with error handling."""
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
    except requests.RequestException as exc:
        print(f"   ⚠️  Network error: {redact_secret(exc)}")
        return None
    except ValueError:
        print(f"   ⚠️  API returned a non-JSON response from {url}")
        return None
    if "error" in data:
        print(f"   ⚠️  API error: {redact_secret(data['error'].get('message', data['error']))}")
        return None
    return data


def insight_value(item):
    """Return an insight value whether Meta returns values[] or total_value."""
    if "total_value" in item:
        return item.get("total_value", {}).get("value", 0) or 0
    values = item.get("values", [])
    if not values:
        return 0
    vals = []
    for value in values:
        raw = value.get("value", 0) or 0
        vals.append(raw if isinstance(raw, (int, float)) else 0)
    return sum(vals)


def get_insight_metric(object_id, metric, since, until, token, period="day", extra=None):
    """Fetch one insight metric at a time so one deprecated metric does not break the pull."""
    params = {
        **BASE_PARAMS,
        "access_token": token,
        "metric": metric,
        "period": period,
        "since": since,
        "until": until,
    }
    if extra:
        params.update(extra)
    data = api_get(f"{BASE_URL}/{object_id}/insights", params)
    if not data:
        return None
    for item in data.get("data", []):
        if item.get("name") == metric:
            return insight_value(item)
    return 0


# ── Facebook Page insights ─────────────────────────────────────────────────────
def get_facebook_insights(since, until, token=None):
    """
    Fetch Facebook Page summary and weekly insight metrics.
    Uses /PAGE/insights for aggregated weekly stats (impressions, reach, engagements).
    """
    result = {}
    tok = token or ACCESS_TOKEN

    # Followers from page object
    url = f"{BASE_URL}/{PAGE_ID}"
    params = {**BASE_PARAMS, "access_token": tok, "fields": "fan_count,followers_count,name"}
    data = api_get(url, params)
    if data:
        result["page_fans"]       = data.get("fan_count", 0)
        result["followers_count"] = data.get("followers_count", 0)
        print(f"      ✓ Followers: {result['page_fans']:,}")

    page_metrics = [
        "page_post_engagements",
        "page_video_views",
        "page_actions_post_reactions_total",
        "page_views_total",
    ]
    got_insights = False
    for metric in page_metrics:
        value = get_insight_metric(PAGE_ID, metric, since, until, tok)
        if value is not None:
            result[metric] = value
            got_insights = True
            print(f"      ✓ {metric}: {value:,}")

    # Fallback: count posts if every Page insight metric is unavailable.
    if not got_insights:
        posts_url = f"{BASE_URL}/{PAGE_ID}/posts"
        posts_params = {
            **BASE_PARAMS,
            "access_token": tok,
            "fields": "id,message,created_time",
            "since": since,
            "until": until,
            "limit": 50,
        }
        posts_data = api_get(posts_url, posts_params)
        if posts_data:
            posts_count = len(posts_data.get("data", []))
            result["posts_count"] = posts_count
            print(f"      ✓ Posts: {posts_count} (insights unavailable)")

    return result


def get_facebook_posts(since, until, limit=10, token=None):
    """Fetch recent posts. Includes per-post insights only if read_insights is in the token."""
    tok = token or ACCESS_TOKEN
    url = f"{BASE_URL}/{PAGE_ID}/posts"

    # Try with post-level insights first (requires read_insights)
    params = {
        **BASE_PARAMS,
        "access_token": tok,
        "fields": "id,message,created_time,insights.metric(post_impressions,post_impressions_unique,post_engagements)",
        "since": since,
        "until": until,
        "limit": limit,
    }
    data = api_get(url, params)

    # Fall back to basic fields if insights aren't available
    if not data:
        params["fields"] = "id,message,created_time"
        data = api_get(url, params)
    if not data:
        return []

    posts = []
    for post in data.get("data", []):
        insights = {}
        for item in post.get("insights", {}).get("data", []):
            insights[item["name"]] = item.get("values", [{}])[0].get("value", 0)

        posts.append({
            "id":           post.get("id"),
            "message":      (post.get("message") or "")[:80],
            "created_time": post.get("created_time", "")[:10],
            "impressions":  insights.get("post_impressions", 0),
            "reach":        insights.get("post_impressions_unique", 0),
            "engaged_users": insights.get("post_engagements", 0),
        })

    posts.sort(key=lambda x: x["impressions"], reverse=True)
    return posts


# ── Instagram insights ─────────────────────────────────────────────────────────
def get_instagram_account_id():
    """Get the Instagram Business Account ID linked to this Facebook Page."""
    url = f"{BASE_URL}/{PAGE_ID}"
    params = {
        **BASE_PARAMS,
        "fields": "instagram_business_account",
    }
    data = api_get(url, params)
    if not data:
        return None
    ig = data.get("instagram_business_account", {})
    return ig.get("id")


def get_instagram_insights(ig_id, since, until):
    """
    Fetch Instagram account-level insights.
    Uses two separate calls:
    - time_series metrics (reach, follower_count) with period=week
    - total_value metrics (profile_views, accounts_engaged etc.) with metric_type=total_value
    """
    result = {}

    url = f"{BASE_URL}/{ig_id}/insights"

    # Group 1a — reach (week period)
    params = {
        **BASE_PARAMS,
        "metric": "reach",
        "period": "week",
        "since": since,
        "until": until,
    }
    data = api_get(url, params)
    if data:
        for item in data.get("data", []):
            name   = item.get("name")
            values = item.get("values", [])
            if values:
                result[name] = values[0].get("value", 0)
                print(f"      ✓ {name}: {result[name]:,}")

    # Group 1b — follower_count (day period, take latest value)
    params_fc = {
        **BASE_PARAMS,
        "metric": "follower_count",
        "period": "day",
        "since": since,
        "until": until,
    }
    data_fc = api_get(url, params_fc)
    if data_fc:
        for item in data_fc.get("data", []):
            if item.get("name") == "follower_count":
                values = item.get("values", [])
                if values:
                    result["follower_count"] = values[-1].get("value", 0)
                    print(f"      ✓ follower_count: {result['follower_count']:,}")

    # Group 2 — total_value metrics (need metric_type param)
    params2 = {
        **BASE_PARAMS,
        "metric": "profile_views,accounts_engaged,total_interactions,views",
        "period": "day",
        "metric_type": "total_value",
        "since": since,
        "until": until,
    }
    data2 = api_get(url, params2)
    if data2:
        for item in data2.get("data", []):
            name = item.get("name")
            # total_value metrics return value differently
            val = item.get("total_value", {}).get("value", 0)
            if val:
                result[name] = val
                print(f"      ✓ {name}: {val:,}")

    return result


def get_instagram_posts(ig_id, since, until, limit=10):
    """Fetch recent Instagram feed posts with engagement stats."""
    url = f"{BASE_URL}/{ig_id}/media"
    params = {
        **BASE_PARAMS,
        "fields": "id,caption,timestamp,media_type,insights.metric(impressions,reach,total_interactions,likes,comments,shares,saved)",
        "since": since,
        "until": until,
        "limit": limit,
    }
    data = api_get(url, params)
    if not data:
        return []

    posts = []
    for post in data.get("data", []):
        insights = {}
        for item in post.get("insights", {}).get("data", []):
            insights[item["name"]] = item.get("values", [{}])[0].get("value", 0)

        posts.append({
            "id":           post.get("id"),
            "caption":      (post.get("caption") or "")[:80],
            "timestamp":    post.get("timestamp", "")[:10],
            "media_type":   post.get("media_type", ""),
            "impressions":  insights.get("impressions", 0),
            "reach":        insights.get("reach", 0),
            "engagement":   insights.get("engagement", 0),
        })

    posts.sort(key=lambda x: x["impressions"], reverse=True)
    return posts


# ── Output ─────────────────────────────────────────────────────────────────────
def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved JSON → {path}")


def save_markdown(data, path):
    """Generate markdown summary matching the weekly report template."""
    today = datetime.now().strftime("%Y-%m-%d")

    this_w  = data.get("this_week", {})
    last_w  = data.get("last_week", {})

    def fb(key):
        return this_w.get("facebook", {}).get("insights", {}).get(key, 0)

    def fb_prev(key):
        return last_w.get("facebook", {}).get("insights", {}).get(key, 0)

    def ig(key):
        return this_w.get("instagram", {}).get("insights", {}).get(key, 0)

    def ig_prev(key):
        return last_w.get("instagram", {}).get("insights", {}).get(key, 0)

    def change(curr, prev):
        if prev == 0:
            return "—"
        pct = ((curr - prev) / prev) * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    lines = [
        "# Meta Insights Summary",
        f"Pulled: {today}",
        "",
        "---",
        "",
        "## Facebook Page",
        "",
        "| Metric | This week | Last week | W-on-W |",
        "|--------|-----------|-----------|--------|",
        f"| Impressions (views) | {fb('page_impressions'):,} | {fb_prev('page_impressions'):,} | {change(fb('page_impressions'), fb_prev('page_impressions'))} |",
        f"| Reach (unique) | {fb('page_impressions_unique'):,} | {fb_prev('page_impressions_unique'):,} | {change(fb('page_impressions_unique'), fb_prev('page_impressions_unique'))} |",
        f"| Interactions | {fb('page_post_engagements'):,} | {fb_prev('page_post_engagements'):,} | {change(fb('page_post_engagements'), fb_prev('page_post_engagements'))} |",
        f"| Video views | {fb('page_video_views'):,} | {fb_prev('page_video_views'):,} | {change(fb('page_video_views'), fb_prev('page_video_views'))} |",
        f"| Followers | {fb('page_fans'):,} | {fb_prev('page_fans'):,} | {change(fb('page_fans'), fb_prev('page_fans'))} |",
    ]

    # Facebook top posts
    fb_posts = this_w.get("facebook", {}).get("posts", [])
    if fb_posts:
        top = fb_posts[0]
        lines += [
            "",
            f"**Top post:** {top['created_time']} — {top['message'][:60]}",
            f"Impressions: {top['impressions']:,} | Reach: {top['reach']:,} | Engaged: {top['engaged_users']:,}",
        ]

    lines += [
        "",
        "---",
        "",
        "## Instagram Feed",
        "",
        "| Metric | This week | Last week | W-on-W |",
        "|--------|-----------|-----------|--------|",
        f"| Impressions (views) | {ig('views'):,} | {ig_prev('views'):,} | {change(ig('views'), ig_prev('views'))} |",
        f"| Reach | {ig('reach'):,} | {ig_prev('reach'):,} | {change(ig('reach'), ig_prev('reach'))} |",
        f"| Profile views | {ig('profile_views'):,} | {ig_prev('profile_views'):,} | {change(ig('profile_views'), ig_prev('profile_views'))} |",
        f"| Followers | {ig('follower_count'):,} | {ig_prev('follower_count'):,} | {change(ig('follower_count'), ig_prev('follower_count'))} |",
    ]

    # Instagram top posts
    ig_posts = this_w.get("instagram", {}).get("posts", [])
    if ig_posts:
        top = ig_posts[0]
        lines += [
            "",
            f"**Top post:** {top['timestamp']} — {top['media_type']} — {top['caption'][:60]}",
            f"Impressions: {top['impressions']:,} | Reach: {top['reach']:,} | Engagement: {top['engagement']:,}",
        ]

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ Saved Markdown → {path}")


def week_label(period):
    since = period.get("since", "")
    try:
        return "W" + datetime.strptime(since, "%Y-%m-%d").strftime("%V").lstrip("0")
    except Exception:
        return "W?"


def date_range_label(period):
    since = period.get("since", "")
    until = period.get("until", "")
    try:
        start = datetime.strptime(since, "%Y-%m-%d")
        end = datetime.strptime(until, "%Y-%m-%d")
        if start.month == end.month:
            return f"{start.strftime('%B')} {start.day}-{end.day}, {end.year}"
        return f"{start.strftime('%B')} {start.day}-{end.strftime('%B')} {end.day}, {end.year}"
    except Exception:
        return f"{since} - {until}".strip(" -")


def change_pct(value, previous):
    if previous in (None, "", 0):
        return ""
    try:
        return round((float(value) - float(previous)) / float(previous), 4)
    except Exception:
        return ""


def status_from_change(change):
    if change == "":
        return ""
    if change > 0.05:
        return "green"
    if change < -0.05:
        return "red"
    return "amber"


def add_funnel_row(rows, period, section, channel, metric, value, unit="count",
                   previous_period=None, previous_value=None, notes=""):
    if value in (None, ""):
        return
    week = week_label(period)
    previous_week = week_label(previous_period) if previous_period else ""
    change = change_pct(value, previous_value)
    clean_channel = channel.lower().replace(" / ", "_").replace(" ", "_")
    clean_metric = metric.lower().replace(" ", "_")
    rows.append({
        "id": f"{week.lower()}_{clean_channel}_{clean_metric}",
        "week": week,
        "dateRange": date_range_label(period),
        "section": section,
        "channel": channel,
        "metric": metric,
        "value": value,
        "unit": unit,
        "previousWeek": previous_week,
        "previousValue": "" if previous_value is None else previous_value,
        "changeValue": "",
        "changePct": change,
        "status": status_from_change(change),
        "sourceReport": f"Meta API {week}",
        "notes": notes,
    })


def metric(data, label, source, key):
    return data.get(label, {}).get(source, {}).get("insights", {}).get(key)


def build_funnel_rows(data):
    rows = []
    labels = ["this_week", "last_week"]
    metric_map = [
        ("facebook", "Social Media", "Facebook", "page_post_engagements", "interactions", "count", ""),
        ("facebook", "Social Media", "Facebook", "page_video_views", "video_views", "count", ""),
        ("facebook", "Social Media", "Facebook", "page_views_total", "profile_visits", "count", "Page views, not identical to Business Suite profile visits."),
        ("facebook", "Social Media", "Facebook", "page_fans", "followers", "count", "Current Page fan count."),
        ("instagram", "Social Media", "Instagram Feed", "views", "views", "count", ""),
        ("instagram", "Social Media", "Instagram Feed", "reach", "reach", "count", ""),
        ("instagram", "Social Media", "Instagram Feed", "total_interactions", "interactions", "count", ""),
        ("instagram", "Social Media", "Instagram Feed", "profile_views", "profile_visits", "count", ""),
        ("instagram", "Social Media", "Instagram Feed", "follower_count", "followers", "count", "API returns follower_count as a period metric; verify against Business Suite if needed."),
    ]

    for index, label in enumerate(labels):
        current = data.get(label)
        if not current:
            continue
        previous_label = labels[index + 1] if index + 1 < len(labels) else None
        previous = data.get(previous_label) if previous_label else None
        for source, section, channel, source_key, out_metric, unit, notes in metric_map:
            value = metric(data, label, source, source_key)
            if value is None:
                continue
            previous_value = metric(data, previous_label, source, source_key) if previous else None
            add_funnel_row(
                rows,
                current.get("period", {}),
                section,
                channel,
                out_metric,
                value,
                unit,
                previous.get("period", {}) if previous else None,
                previous_value,
                notes,
            )
    return rows


def save_funnel_csv(data, path):
    rows = build_funnel_rows(data)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FUNNEL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Saved FunnelMetrics CSV → {path}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pull Meta (Facebook + Instagram) insights")
    parser.add_argument("--weeks", type=int, choices=[1, 2], default=2,
                        help="Number of weeks to pull (default: 2, for W-on-W comparison)")
    parser.add_argument("--since", help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--until", help="Inclusive end date YYYY-MM-DD")
    args = parser.parse_args()
    if bool(args.since) != bool(args.until):
        parser.error("--since and --until must be provided together")

    today = datetime.now().strftime("%Y-%m-%d")
    output = {}
    if args.since:
        current_since, current_until = args.since, args.until
    else:
        current_since, current_until = completed_week()

    # Exchange system user token for page access token (required for /posts endpoint)
    print(f"\n🔑 Getting Page Access Token...")
    page_token = get_page_access_token()

    # Get Instagram account ID
    print(f"\n🔍 Looking up Instagram account...")
    ig_id = get_instagram_account_id()
    if ig_id:
        print(f"   ✓ Instagram account ID: {ig_id}")
    else:
        print(f"   ⚠️  No Instagram account linked — will pull Facebook only")

    week_labels = ["this_week", "last_week"]

    for i, label in enumerate(week_labels[:args.weeks]):
        start_date = datetime.fromisoformat(current_since).date() - timedelta(weeks=i)
        end_date = datetime.fromisoformat(current_until).date() - timedelta(weeks=i)
        since_str, until_str = start_date.isoformat(), end_date.isoformat()
        since, until = timestamp_range(since_str, until_str)
        print(f"\n📅 {label.replace('_', ' ').title()}: {since_str} → {until_str}")

        # Facebook (uses page_token, not system user token)
        print(f"   📘 Fetching Facebook insights...")
        fb_insights = get_facebook_insights(since, until, token=page_token)
        fb_posts    = get_facebook_posts(since, until, token=page_token)
        print(f"      Impressions: {fb_insights.get('page_impressions', 0):,}")
        print(f"      Interactions: {fb_insights.get('page_post_engagements', 0):,}")
        print(f"      Posts found: {len(fb_posts)}")

        # Instagram
        ig_insights = {}
        ig_posts    = []
        if ig_id:
            print(f"   📸 Fetching Instagram insights...")
            ig_insights = get_instagram_insights(ig_id, since, until)
            ig_posts    = get_instagram_posts(ig_id, since, until)
            print(f"      Impressions: {ig_insights.get('views', 0):,}")
            print(f"      Reach: {ig_insights.get('reach', 0):,}")
            print(f"      Posts found: {len(ig_posts)}")

        output[label] = {
            "period": {"since": since_str, "until": until_str},
            "facebook":  {"insights": fb_insights, "posts": fb_posts},
            "instagram": {"insights": ig_insights, "posts": ig_posts},
        }

    # Save files
    print(f"\n💾 Saving files...")
    json_path = OUTPUT_DIR / f"meta_raw_{today}.json"
    md_path   = OUTPUT_DIR / f"meta_summary_{today}.md"
    csv_path  = OUTPUT_DIR / f"meta_funnel_metrics_{today}.csv"

    save_json(output, json_path)
    save_markdown(output, md_path)
    save_funnel_csv(output, csv_path)

    # Print summary
    print(f"\n{'='*50}")
    print(f"📊 Meta Summary — This Week")
    print(f"{'='*50}")
    tw = output.get("this_week", {})
    print(f"Facebook impressions: {tw.get('facebook', {}).get('insights', {}).get('page_impressions', 0):,}")
    print(f"Facebook interactions: {tw.get('facebook', {}).get('insights', {}).get('page_post_engagements', 0):,}")
    if ig_id:
        print(f"Instagram impressions: {tw.get('instagram', {}).get('insights', {}).get('views', 0):,}")
        print(f"Instagram reach:       {tw.get('instagram', {}).get('insights', {}).get('reach', 0):,}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
