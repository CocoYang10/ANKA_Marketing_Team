"""Private ANKA dashboard API and TikTok OAuth callback.

This service is intentionally separate from GitHub Pages. Secrets stay in the
server environment; the browser receives only sanitized aggregate metrics.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from action_agent.registry import (
    connect as registry_connect,
    list_actions as registry_list_actions,
    transition as registry_transition,
)


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SNAPSHOT = Path(
    os.getenv("ANKA_SNAPSHOT_PATH", ROOT / "demo" / "data" / "marketing_snapshot.json")
)
TOKEN_STORE = Path(os.getenv("ANKA_TOKEN_STORE", ROOT / "working/private/tiktok_tokens.json"))
API_KEY = os.getenv("ANKA_DASHBOARD_API_KEY", "").strip()
PUBLIC_BASE_URL = os.getenv("ANKA_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
TIKTOK_APP_ID = os.getenv("TIKTOK_BUSINESS_APP_ID", "").strip()
TIKTOK_APP_SECRET = os.getenv("TIKTOK_BUSINESS_SECRET", "").strip()
TIKTOK_REDIRECT_URI = os.getenv(
    "TIKTOK_REDIRECT_URI", f"{PUBLIC_BASE_URL}/oauth/tiktok/callback"
).strip()
SCOPES = ["user.info.basic", "user.insights", "video.list", "video.insights"]
STATE_TTL_SECONDS = 600
_issued_states: set[str] = set()
_state_lock = threading.Lock()

app = FastAPI(title="ANKA Private Marketing API", docs_url=None, redoc_url=None)
origins = [x.strip() for x in os.getenv("ANKA_ALLOWED_ORIGINS", "").split(",") if x.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "X-ANKA-Key"],
    )


class ActionTransition(BaseModel):
    to_status: str = Field(min_length=3, max_length=32)
    actor: str = Field(min_length=2, max_length=120)
    note: str = Field(default="", max_length=1000)


def require_api_key(x_anka_key: str | None = Header(default=None)) -> None:
    if not API_KEY:
        raise HTTPException(503, "Server API key is not configured")
    if not x_anka_key or not hmac.compare_digest(x_anka_key, API_KEY):
        raise HTTPException(401, "Unauthorized")


def oauth_sign(payload: str) -> str:
    if not TIKTOK_APP_SECRET:
        raise HTTPException(503, "TikTok app secret is not configured")
    return hmac.new(
        TIKTOK_APP_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def create_state() -> str:
    payload = f"{int(time.time())}.{secrets.token_urlsafe(24)}"
    state = f"{payload}.{oauth_sign(payload)}"
    with _state_lock:
        _issued_states.add(state)
    return state


def verify_state(state: str) -> None:
    try:
        issued, nonce, signature = state.split(".", 2)
        payload = f"{issued}.{nonce}"
        fresh = 0 <= int(time.time()) - int(issued) <= STATE_TTL_SECONDS
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid OAuth state") from None
    if not fresh or not hmac.compare_digest(signature, oauth_sign(payload)):
        raise HTTPException(400, "Expired or invalid OAuth state")
    with _state_lock:
        if state not in _issued_states:
            raise HTTPException(400, "OAuth state was not issued or was already used")
        _issued_states.remove(state)


def save_tiktok_tokens(data: dict) -> None:
    allowed = {
        key: data[key]
        for key in ("access_token", "refresh_token", "open_id", "expires_in", "refresh_token_expires_in")
        if data.get(key) not in (None, "")
    }
    allowed["saved_at"] = int(time.time())
    TOKEN_STORE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_STORE.write_text(json.dumps(allowed), encoding="utf-8")
    TOKEN_STORE.chmod(0o600)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "snapshot_available": SNAPSHOT.exists(),
        "tiktok_configured": bool(TIKTOK_APP_ID and TIKTOK_APP_SECRET),
    }


@app.get("/api/v1/dashboard", dependencies=[Depends(require_api_key)])
def dashboard() -> dict:
    if not SNAPSHOT.exists():
        raise HTTPException(503, "Run build_dashboard_snapshot.py first")
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@app.get("/api/v1/actions", dependencies=[Depends(require_api_key)])
def actions() -> dict:
    """Return the private lifecycle state used by the Action Center."""
    return {"actions": registry_list_actions(registry_connect())}


@app.post("/api/v1/actions/{action_id}/transition", dependencies=[Depends(require_api_key)])
def transition_action(action_id: str, request: ActionTransition) -> dict:
    """Record a human-controlled, audited action lifecycle transition."""
    try:
        registry_transition(
            registry_connect(),
            action_id,
            request.to_status,
            request.actor,
            request.note,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"action_id": action_id, "status": request.to_status.upper()}


@app.get("/oauth/tiktok/start")
def tiktok_start() -> RedirectResponse:
    if not TIKTOK_APP_ID:
        raise HTTPException(503, "TikTok app ID is not configured")
    params = {
        "app_id": TIKTOK_APP_ID,
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": create_state(),
        "scope": ",".join(SCOPES),
    }
    return RedirectResponse(
        "https://business-api.tiktok.com/portal/auth?" + urlencode(params),
        status_code=302,
    )


@app.get("/oauth/tiktok/callback", response_class=HTMLResponse)
def tiktok_callback(auth_code: str = "", state: str = "") -> str:
    verify_state(state)
    if not auth_code:
        raise HTTPException(400, "TikTok did not return auth_code")
    response = requests.post(
        "https://business-api.tiktok.com/open_api/v1.3/tt_user/oauth2/token/",
        json={
            "client_id": TIKTOK_APP_ID,
            "client_secret": TIKTOK_APP_SECRET,
            "grant_type": "authorization_code",
            "auth_code": auth_code,
            "redirect_uri": TIKTOK_REDIRECT_URI,
        },
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("code") != 0:
        raise HTTPException(502, f"TikTok token exchange failed: {body.get('message', 'unknown error')}")
    save_tiktok_tokens(body.get("data", {}))
    return "<h1>TikTok connected</h1><p>Tokens were stored server-side. You may close this tab.</p>"
