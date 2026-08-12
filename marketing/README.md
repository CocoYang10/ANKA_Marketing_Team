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
each proposed action. Growth & Revenue includes a 28-day GA4 trend with the NYC
pop-up period and the July 23 tracking-repair boundary marked explicitly. Data
Health contains the source, definition, reporting period and freshness date for
every headline metric.

The private `demo/data/marketing_snapshot.json` is ignored by Git. The reviewed,
sanitized `demo/data/demo_snapshot.json` is the public fallback used by GitHub
Pages; rebuild and inspect it explicitly before committing it.

## Private API and TikTok OAuth

```bash
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

The private API owns OAuth secrets and exposes the sanitized dashboard payload
and audited action-lifecycle endpoints only to callers with `X-ANKA-Key`.
Static approval controls stay disabled because GitHub Pages cannot safely hold
that key. See `TIKTOK_API_SETUP.md` before production deployment.

Open `http://127.0.0.1:8000/internal/` after starting the API to use the
controlled internal V1. Choose **Connect private workspace** and enter the local
API URL and dashboard key. The key is held only for that browser tab; it is
never added to the public snapshot. The internal Action Center supports audited
approval, rejection, assignment, external-task links and verification plans.

Approved engineering actions can create GitHub Issues when the server has
`GITHUB_ISSUES_TOKEN` and `GITHUB_ISSUES_REPOSITORY`. This is optional until the
project moves to the company-owned repository. Basecamp is intentionally not an
API integration: the Agent will generate a Basecamp-ready weekly report for
Vanessa to review and copy/paste. Missing GitHub credentials disable Issue
creation safely.

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
engineering/marketing issue drafts under `working/agent_runs/`. It also writes
a dated, Basecamp-copyable HTML report under `working/reports/`; the report is
reviewed and pasted manually rather than published through the Basecamp API. Use
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

It also stores a daily 28-day trend so week-over-week changes can be read without
mixing pre-repair and post-repair traffic. Connector failures are fail-closed:
the pipeline must report `DATA MISSING` instead of replacing an unreachable
source with zero performance.

`CLEAN` or `TRUSTED` must never be inferred only from a successful API request.

## Security

- Never put API secrets in `index.html` or any GitHub Pages asset.
- The dashboard should read sanitized, aggregated data from an authenticated
  backend.
- Rotate any credential that appears in terminal output, browser code, or a
  committed file.
- Do not publish raw order IDs, customer identifiers, IPs, or user agents.
