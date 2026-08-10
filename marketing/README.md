# ANKA Marketing Data System

This directory contains the private-to-company, source-controlled code for the
ANKA marketing measurement pipeline. Credentials and generated reports remain
local and are ignored by Git.

Start with [`PROPOSAL.md`](PROPOSAL.md) for the product direction, delivery
phases and visible approval workflow. The durable Agent rules live in
[`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md).

## Current connector status

| Source | Connection | Decision use |
|---|---|---|
| GA4 | Connected / blocked for attribution | Traffic, funnel, transactions, reported revenue, country and purchased items are available; current purchases are `(not set)` by source |
| Instagram / Meta | Connected | Aggregate Instagram metrics are usable |
| Facebook / Meta | Partial | Authentication works; Page insights still require API/permission repair |
| MailerLite | Connected | Campaign and segment reporting is usable |
| TikTok | Pending | OAuth helper exists; access token and analytics pull are still missing |
| Pinterest | GA4 traffic only | Tagged website sessions are available; native analytics is not connected |
| Eventbrite | Missing | Required for registration, order and attendance conversion |
| Order backend | Missing | Required as revenue ground truth |

## P2 measurement demo

Build a sanitized aggregate snapshot and preview it locally:

```bash
.venv/bin/python build_dashboard_snapshot.py
cd demo
python3 -m http.server 8001
```

Open `http://127.0.0.1:8001`. The default view is the Action Center. Growth &
Revenue, Audience & Products, Events and Data Health expose the evidence behind
each proposed action. The generated JSON is ignored by Git because it is a
local snapshot. Review it before intentionally publishing any aggregate
snapshot.

## Private API and TikTok OAuth

```bash
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

The private API owns OAuth secrets and exposes the sanitized dashboard payload
and audited action-lifecycle endpoints only to callers with `X-ANKA-Key`.
Static approval controls stay disabled because GitHub Pages cannot safely hold
that key. See `TIKTOK_API_SETUP.md` before production deployment.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Store the GA4 service-account JSON under `credentials/` and update
`GOOGLE_APPLICATION_CREDENTIALS` in `.env`.

## Weekly evidence-to-action run

```bash
.venv/bin/python run_weekly_pipeline.py
```

The default run pulls the connected sources, validates and rebuilds the
sanitized snapshot, then creates an evidence-to-action brief and individual
engineering/marketing issue drafts under `working/agent_runs/`. Use
`--skip-agent` only when a source-only diagnostic is needed.

## GA4

Pull the most recently completed Monday-Sunday week:

```bash
.venv/bin/python skills/pull-ga4-skill/pull_ga4.py
```

Pull an exact report period and its preceding comparison period:

```bash
.venv/bin/python skills/pull-ga4-skill/pull_ga4.py \
  --since 2026-07-20 --until 2026-07-26 --weeks 2
```

The GA4 output distinguishes:

- API connectivity
- traffic quality
- purchase/revenue and acquisition-source quality
- funnel completeness
- country, age and interest availability/coverage

`CLEAN` or `TRUSTED` must never be inferred only from a successful API request.

## Security

- Never put API secrets in `index.html` or any GitHub Pages asset.
- The dashboard should read sanitized, aggregated data from an authenticated
  backend.
- Rotate any credential that appears in terminal output, browser code, or a
  committed file.
- Do not publish raw order IDs, customer identifiers, IPs, or user agents.
