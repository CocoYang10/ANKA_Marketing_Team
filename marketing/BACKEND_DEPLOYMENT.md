# ANKA private marketing backend deployment

## Architecture

```text
GA4 / Meta / MailerLite / TikTok
                ↓
       scheduled private pulls
                ↓
  reviewed aggregate snapshot + quality gate
                ↓
      authenticated private API
                ↓
       ANKA internal dashboard
```

GitHub Pages remains a static public host. It must not receive Meta, TikTok,
GA4 service-account, AI-provider, dashboard API, or order-system secrets.

## Runtime

The included Dockerfile is designed for a private HTTPS container runtime such
as Google Cloud Run. Build context must be `marketing/`:

```bash
docker build -f backend/Dockerfile -t anka-marketing-api .
```

Required runtime secrets:

- `ANKA_DASHBOARD_API_KEY`
- `TIKTOK_BUSINESS_APP_ID`
- `TIKTOK_BUSINESS_SECRET`
- `TIKTOK_REDIRECT_URI`
- source API secrets needed by scheduled pulls

Runtime configuration:

- `ANKA_PUBLIC_BASE_URL=https://marketing-api.YOUR_DOMAIN`
- `ANKA_ALLOWED_ORIGINS=https://YOUR_INTERNAL_DASHBOARD`
- `ANKA_TOKEN_STORE=/private/tiktok_tokens.json`
- `ANKA_SNAPSHOT_PATH=/data/marketing_snapshot.json`

The reviewed snapshot must be delivered to `/data` by the scheduled pipeline or
a private object-store sync. It is deliberately excluded from the container
image so an old data snapshot cannot be baked into a release unnoticed.

## Important production boundary

The current API-key gate is for a controlled internal demo. Do not embed the
key in public JavaScript. Before wider staff access, put Google Workspace SSO
or an identity-aware proxy in front of the service and authorize users by
company identity.

OAuth state is single-use and stored in process memory, so the supplied
container deliberately runs one worker. If the backend is scaled to multiple
instances, move OAuth state and refresh-token storage to a shared encrypted
store such as Redis plus Secret Manager.

## Release gate

Before deployment:

1. Run `python build_dashboard_snapshot.py`.
2. Run `python -m unittest discover -s tests -v`.
3. Confirm the public snapshot contains no secrets or customer identifiers.
4. Confirm the exact allowed origin and HTTPS callback.
5. Confirm server logs never print authorization codes or tokens.
6. Confirm source dates and dashboard dates are visible.
7. Have Vanessa review the dashboard before broader sharing.
