# TikTok Business API setup for ANKA

## Portal configuration

1. In TikTok for Business, create or select the ANKA developer app.
2. Add the exact OAuth redirect URL:
   `https://YOUR-PRIVATE-API.example.com/oauth/tiktok/callback`.
3. Request the read-only scopes used by the connector:
   `user.info.basic`, `user.insights`, `video.list`, `video.insights`.
4. Copy the app ID and app secret into the private backend environment as
   `TIKTOK_BUSINESS_APP_ID` and `TIKTOK_BUSINESS_SECRET`.
5. Never put the app secret or tokens in GitHub Pages, HTML, screenshots,
   reviewer notes or chat.

## Local demo

```bash
cd marketing
cp .env.example .env
# Fill the private values in .env
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/oauth/tiktok/start`, sign in with the ANKA-owned
TikTok account, and authorize access. The callback validates a signed,
10-minute OAuth state and stores returned tokens in a mode-600 private file
under `working/private/`.

## Production requirements

- Deploy `marketing/backend`, not the `.env` file, to a private API runtime
  such as Google Cloud Run.
- Store app secrets and refresh tokens in the platform secret manager.
- Use an HTTPS callback on an ANKA-controlled domain.
- Put staff authentication in front of the dashboard API. The included API-key
  gate is suitable for a controlled demo, not the final multi-user login.
- Schedule refresh-token rotation and source pulls server-side.
- Log access and connector failures, but never token values or customer PII.

## Validation gate

TikTok remains marked **OAuth pending** until all of the following pass:

- account identity endpoint returns the expected ANKA account;
- analytics endpoints return non-empty, correctly dated metrics;
- pagination and timezone behavior are verified;
- dashboard totals reconcile to TikTok's native UI for one fixed period;
- a token refresh succeeds without manual reauthorization.
