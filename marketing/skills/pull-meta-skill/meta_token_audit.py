"""
meta_token_audit.py
-------------------
One-time Meta token checker for ANKA.

This script does not save or print the token. It asks for a token at runtime,
then checks whether it can:
- identify the token owner via /me
- read the configured Facebook Page
- obtain a Page access token
- call Page insights, which is the important read_insights test
- find the linked Instagram Business account

Usage:
    python meta_token_audit.py
    python meta_token_audit.py --label "system-user-token"
"""

import argparse
import getpass
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv


load_dotenv()

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v19.0")
BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
DEFAULT_PAGE_ID = os.getenv("META_PAGE_ID", "").strip()


def call_graph(path, token, params=None):
    params = dict(params or {})
    params["access_token"] = token
    resp = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=30)
    try:
        data = resp.json()
    except ValueError:
        return False, {"error": {"message": resp.text[:300], "code": resp.status_code}}
    if "error" in data:
        return False, data
    return True, data


def short_error(data):
    err = data.get("error", data)
    message = err.get("message", str(err))
    message = re.sub(r"EA[A-Za-z0-9_-]{20,}", "[REDACTED_META_TOKEN]", message)
    code = err.get("code")
    subcode = err.get("error_subcode")
    suffix = []
    if code is not None:
        suffix.append(f"code={code}")
    if subcode is not None:
        suffix.append(f"subcode={subcode}")
    return f"{message}" + (f" ({', '.join(suffix)})" if suffix else "")


def status_line(ok, label, detail=""):
    mark = "OK" if ok else "FAIL"
    print(f"{mark:4} {label}{': ' + detail if detail else ''}")


def last_7_days():
    until = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since = until - timedelta(days=7)
    return int(since.timestamp()), int(until.timestamp())


def maybe_debug_token(token):
    app_id = os.getenv("META_APP_ID") or os.getenv("FACEBOOK_APP_ID")
    app_secret = os.getenv("META_APP_SECRET") or os.getenv("FACEBOOK_APP_SECRET")
    if not app_id or not app_secret:
        status_line(False, "debug_token metadata", "META_APP_ID/META_APP_SECRET not set; skipping expiry/scope check")
        return

    app_access_token = f"{app_id}|{app_secret}"
    ok, data = call_graph("debug_token", app_access_token, {"input_token": token})
    if not ok:
        status_line(False, "debug_token metadata", short_error(data))
        return

    info = data.get("data", {})
    is_valid = info.get("is_valid")
    expires_at = info.get("expires_at")
    scopes = info.get("scopes") or []
    expires_text = "never/unknown"
    if expires_at:
        expires_text = datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status_line(bool(is_valid), "token validity", f"expires {expires_text}")
    if scopes:
        print("     scopes:", ", ".join(sorted(scopes)))


def audit_token(token, page_id):
    print(f"\nGraph API: {GRAPH_VERSION}")
    print(f"Page ID:   {page_id or '(missing)'}")

    maybe_debug_token(token)

    ok, me = call_graph("me", token, {"fields": "id,name"})
    status_line(ok, "/me", f"{me.get('name', 'unnamed')} ({me.get('id', 'no id')})" if ok else short_error(me))

    if not page_id:
        print("\nAdd META_PAGE_ID to .env or pass --page-id before checking Page/Insights access.")
        return

    ok, page = call_graph(
        page_id,
        token,
        {"fields": "id,name,fan_count,followers_count,instagram_business_account,access_token"},
    )
    status_line(ok, "Page read", f"{page.get('name', 'unnamed page')} ({page.get('id')})" if ok else short_error(page))
    if not ok:
        return

    page_token = page.get("access_token") or token
    status_line(bool(page.get("access_token")), "Page access token", "returned by /PAGE_ID" if page.get("access_token") else "not returned; using original token")

    since, until = last_7_days()
    page_metric_candidates = [
        "page_post_engagements",
        "page_video_views",
        "page_actions_post_reactions_total",
        "page_views_total",
    ]
    working_page_metrics = []
    failing_page_metrics = []
    for metric in page_metric_candidates:
        ok, metric_data = call_graph(
            f"{page_id}/insights",
            page_token,
            {
                "metric": metric,
                "period": "day",
                "since": since,
                "until": until,
            },
        )
        if ok:
            working_page_metrics.append(metric)
        else:
            failing_page_metrics.append((metric, short_error(metric_data)))

    if working_page_metrics:
        status_line(True, "read_insights Page test", ", ".join(working_page_metrics))
    else:
        status_line(False, "read_insights Page test", "no candidate Page metrics worked")
    if failing_page_metrics:
        print("     failed Page metrics:")
        for metric, error in failing_page_metrics:
            print(f"     - {metric}: {error}")

    ig = page.get("instagram_business_account") or {}
    ig_id = ig.get("id")
    status_line(bool(ig_id), "Instagram linked account", ig_id or "not linked/visible")
    if not ig_id:
        return

    ok, ig_data = call_graph(
        f"{ig_id}/insights",
        token,
        {
            "metric": "reach",
            "period": "day",
            "since": since,
            "until": until,
        },
    )
    status_line(ok, "Instagram insights test", "reach returned" if ok else short_error(ig_data))


def main():
    parser = argparse.ArgumentParser(description="Audit a Meta access token without saving it.")
    parser.add_argument("--label", default="", help="Human label for your notes; token is never printed")
    parser.add_argument("--page-id", default=DEFAULT_PAGE_ID, help="Facebook Page ID; defaults to META_PAGE_ID from .env")
    args = parser.parse_args()

    if args.label:
        print(f"Auditing: {args.label}")
    token = getpass.getpass("Paste Meta access token (hidden): ").strip()
    if not token:
        raise SystemExit("No token provided.")

    started = time.time()
    audit_token(token, args.page_id.strip())
    print(f"\nDone in {time.time() - started:.1f}s. Token was not saved.")


if __name__ == "__main__":
    main()
