"""Pull read-only TikTok Business Account profile and organic video insights."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "working" / "reports"
BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"
load_dotenv(ROOT / ".env")
TOKEN_STORE = Path(os.getenv("ANKA_TOKEN_STORE", ROOT / "working/private/tiktok_tokens.json"))

PROFILE_FIELDS = [
    "display_name",
    "username",
    "followers_count",
    "likes",
    "profile_views",
    "video_views",
]
VIDEO_FIELDS = [
    "caption",
    "create_time",
    "item_id",
    "likes",
    "comments",
    "shares",
    "reach",
    "video_views",
    "average_time_watched",
    "full_video_watched_rate",
    "video_duration",
]


def completed_week() -> tuple[str, str]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    until = monday - timedelta(days=1)
    return (until - timedelta(days=6)).isoformat(), until.isoformat()


def credentials() -> tuple[str, str]:
    token = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
    business_id = os.getenv("TIKTOK_OPEN_ID", "").strip()
    if TOKEN_STORE.exists():
        private = json.loads(TOKEN_STORE.read_text(encoding="utf-8"))
        token = private.get("access_token") or token
        business_id = private.get("open_id") or business_id
    return token, business_id


def refresh_if_needed() -> None:
    """Refresh a server-stored short-term token before it expires."""
    if not TOKEN_STORE.exists():
        return
    private = json.loads(TOKEN_STORE.read_text(encoding="utf-8"))
    saved_at = int(private.get("saved_at") or 0)
    expires_in = int(private.get("expires_in") or 0)
    if not expires_in or time.time() < saved_at + expires_in - 300:
        return

    refresh_token = private.get("refresh_token")
    app_id = os.getenv("TIKTOK_BUSINESS_APP_ID", "").strip()
    app_secret = os.getenv("TIKTOK_BUSINESS_SECRET", "").strip()
    if not all((refresh_token, app_id, app_secret)):
        raise RuntimeError("TikTok access token expired and refresh configuration is incomplete")
    response = requests.post(
        f"{BASE_URL}/tt_user/oauth2/refresh_token/",
        json={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("code") != 0:
        raise RuntimeError(f"TikTok token refresh failed: {body.get('message', 'unknown error')}")
    refreshed = body.get("data", {})
    allowed = {
        key: refreshed.get(key, private.get(key))
        for key in (
            "access_token",
            "refresh_token",
            "open_id",
            "expires_in",
            "refresh_token_expires_in",
        )
    }
    allowed["saved_at"] = int(time.time())
    TOKEN_STORE.write_text(json.dumps(allowed), encoding="utf-8")
    TOKEN_STORE.chmod(0o600)


def connection_status() -> dict:
    token, business_id = credentials()
    missing = []
    if not token:
        missing.append("TIKTOK_ACCESS_TOKEN")
    if not business_id:
        missing.append("TIKTOK_OPEN_ID")
    return {
        "source": "tiktok",
        "connection": "NOT_CONNECTED" if missing else "CREDENTIALS_PRESENT_NOT_VALIDATED",
        "missing": missing,
        "decision_use": False,
        "next_action": (
            "Open the private backend /oauth/tiktok/start URL."
            if missing
            else "Run this connector and reconcile one fixed period to TikTok's native UI."
        ),
    }


def api_get(path: str, token: str, params: dict) -> dict:
    response = requests.get(
        f"{BASE_URL}/{path.lstrip('/')}",
        headers={"Access-Token": token},
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("code") != 0:
        raise RuntimeError(f"TikTok API failed: {body.get('message', 'unknown error')}")
    return body.get("data", {})


def pull(token: str, business_id: str, since: str, until: str) -> dict:
    profile = api_get(
        "business/get/",
        token,
        {"business_id": business_id, "fields": json.dumps(PROFILE_FIELDS)},
    )
    videos: list[dict] = []
    cursor = None
    while True:
        params = {
            "business_id": business_id,
            "fields": json.dumps(VIDEO_FIELDS),
            "max_count": 100,
        }
        if cursor:
            params["cursor"] = cursor
        page = api_get("business/video/list/", token, params)
        rows = page.get("videos") or page.get("list") or []
        videos.extend(rows)
        cursor = page.get("cursor")
        if not page.get("has_more") or not cursor:
            break

    start_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(until).replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    )
    selected = []
    for row in videos:
        raw = row.get("create_time")
        try:
            created = (
                datetime.fromtimestamp(int(raw), tz=timezone.utc)
                if str(raw).isdigit()
                else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            )
        except (ValueError, TypeError):
            continue
        if start_dt <= created <= end_dt:
            selected.append(row)

    def total(field: str) -> int:
        return sum(int(row.get(field) or 0) for row in selected)

    return {
        "period": {"since": since, "until": until},
        "profile": {
            key: profile.get(key)
            for key in PROFILE_FIELDS
            if key not in {"username", "display_name"} or profile.get(key)
        },
        "summary": {
            "posts": len(selected),
            "video_views": total("video_views"),
            "reach": total("reach"),
            "likes": total("likes"),
            "comments": total("comments"),
            "shares": total("shares"),
        },
        "videos": selected,
        "quality": {
            "status": "REVIEW",
            "meaning": "Reconcile this exact period to TikTok's native analytics before decision use.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()
    if bool(args.since) != bool(args.until):
        parser.error("--since and --until must be supplied together")

    status = connection_status()
    if args.status_only or status["missing"]:
        print(json.dumps(status, indent=2))
        raise SystemExit(0 if not status["missing"] else 2)

    since, until = (args.since, args.until) if args.since else completed_week()
    refresh_if_needed()
    token, business_id = credentials()
    data = pull(token, business_id, since, until)
    REPORTS.mkdir(parents=True, exist_ok=True)
    output = REPORTS / f"tiktok_raw_{date.today().isoformat()}.json"
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"TikTok: {data['summary']['posts']} posts, {data['summary']['video_views']} views")
    print(f"Output: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
