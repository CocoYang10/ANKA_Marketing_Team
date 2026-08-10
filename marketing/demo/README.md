# Decision Workspace maintenance guide

The demo intentionally has no frontend build step. It is a static shell that
reads one sanitized JSON contract, so it can be reviewed locally without
installing a JavaScript toolchain.

## Where to make changes

| Change | Primary file |
|---|---|
| Add or change a KPI/data field | `../build_dashboard_snapshot.py` |
| Change Action Center recommendations | `../action_agent/run_agent.py` |
| Change action lifecycle rules | `../action_agent/registry.py` |
| Change tabs, copy, layout or interactions | `index.html` |
| Change private approval endpoints | `../backend/app.py` |
| Change weekly source execution | `../run_weekly_pipeline.py` |
| Change GA4 extraction | `../skills/pull-ga4-skill/pull_ga4.py` |

## Frontend map

`index.html` uses one render function per tab:

- `renderActions()` — Agent queue, evidence and approval preview
- `renderGrowth()` — platform, acquisition, revenue and funnel
- `renderAudience()` — country, age, interest and purchased products
- `renderEvents()` — website-to-Eventbrite measurement design
- `renderHealth()` — source availability, quality issues and reconciliation

Shared formatting and layout helpers live above those functions. Navigation
state is kept in `currentView`; no framework or hidden router is involved.

## Data contract

The browser reads `data/marketing_snapshot.json`. That file is generated
locally and ignored by Git. Never hand-edit it. Change the builder and rerun:

```bash
.venv/bin/python build_dashboard_snapshot.py
```

Missing source data must be represented with a status and `null`, not a fake
zero. Public snapshots may contain aggregate metrics only; credentials,
customer identifiers and transaction IDs are rejected by validation.

## Safe change loop

```bash
.venv/bin/python build_dashboard_snapshot.py
.venv/bin/python -m unittest discover -s tests -v
cd demo
python3 -m http.server 8001
```

Then inspect `http://127.0.0.1:8001/` at desktop and mobile widths. When a new
field is decision-sensitive, add a contract or regression test in
`../tests/test_dashboard_snapshot.py`.

## Deployment boundary

GitHub Pages may host the static UI, but it cannot safely approve actions or
hold API credentials. Real approvals use the authenticated private backend.
The static approval button therefore remains a preview until company identity
or another authenticated gateway is deployed.
