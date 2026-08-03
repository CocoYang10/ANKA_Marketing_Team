# ANKA Marketing Decision Agent proposal

Status: **Foundation implemented; integrations and authenticated execution in progress**

## Executive proposition

ANKA should not build another reporting dashboard. It should build a controlled
decision system that turns marketing and commerce evidence into owned work,
requires human approval, and verifies whether the work changed the business.

The product is useful when it shortens the distance between a data problem or
growth opportunity and a verified business outcome. Charts are supporting
evidence, not the final output.

## User experience

The workspace is organized around five questions:

| Workspace | User question | Current output |
|---|---|---|
| Action Center | What should we do next, who owns it, and what proves completion? | Ranked proposals with evidence, owner, confidence, limitations and acceptance criteria |
| Growth & Revenue | Which channels create traffic, transactions and revenue? | Platform and GA4 evidence with attribution blockers shown explicitly |
| Audience & Products | Who visits and buys, and which products create value? | Country, demographic availability and purchased-item direction |
| Events | Which campaigns create registrations and attendance? | Website-to-Eventbrite measurement design and integration status |
| Data Health | Which conclusions are safe to use? | Source freshness, reconciliation, missing coverage and decision gates |

The Agent operates as:

```text
Observe → Validate → Diagnose → Propose → Human approval → Execute → Verify
```

It is not authorized to change spend, publish content, declare an experiment
winner, or close engineering work without human approval.

## What is implemented

- GA4 traffic, checkout, transaction, reported revenue and item extraction.
- Source/medium sessions, transactions and revenue in the same acquisition cut.
- Country, age and interest availability with purchaser-coverage warnings.
- Automated reconciliation and data-quality gates.
- Instagram and MailerLite aggregate evidence; partial Facebook support.
- Evidence-to-action rules and a persistent audited action registry.
- A static decision workspace with desktop and mobile layouts.
- A private API boundary for dashboard reads, TikTok OAuth and action status
  transitions.
- A weekly pipeline that refreshes evidence, proposals and the dashboard
  contract.
- Automated tests for security, action lifecycle, snapshot integrity and GA4
  quality.

## Current decision boundary

As of the latest reviewed implementation, GA4 transactions and reported
revenue are present, but purchase acquisition source is not usable. Product
views are also missing and purchase events exceed transaction count.

Therefore the system may support monitoring, country-level direction,
purchased-item review and measurement repair. It must not yet recommend channel
budget allocation, CAC, ROAS or causal campaign winners.

## Delivery roadmap

### Phase 1 — trusted evidence and Action Center

Status: **implemented locally**

- Keep source periods and availability visible.
- Refuse unsupported conclusions.
- Produce bounded proposals with an owner and acceptance criteria.
- Preserve action history across weekly runs.

### Phase 2 — complete the commercial chain

Status: **next**

1. Preserve acquisition source through purchase and reduce Direct/unknown loss.
2. Remove residual duplicate purchase tracking and implement `view_item`.
3. Reconcile GA4 transaction IDs with paid/refunded backend orders.
4. Add daily ad spend, campaign IDs and currency.
5. Complete Meta review and TikTok Business OAuth.
6. Connect Eventbrite registration, order and check-in aggregates through a
   stable `event_id` without attendee PII.

Exit criteria:

- GA4 transactions reconcile to paid backend orders within the agreed tolerance.
- Active campaign links meet the UTM contract.
- Channel spend, sessions, paid orders and net revenue can be joined at a defined
  daily grain.
- One event reconciles website clicks, Eventbrite registrations and check-ins.

### Phase 3 — authenticated workflow execution

Status: **designed; private API foundation implemented**

- Put company identity/SSO in front of the private backend.
- Allow authorized users to approve, reject, assign and comment on proposals.
- Create engineering tickets or experiment briefs only after approval.
- Notify owners in the company system of record.
- Recheck acceptance criteria after the implementation window.

### Phase 4 — experiments and optimization

Status: **blocked by assignment/exposure data**

- Persist experiment, variant, assignment and first-exposure data.
- Pre-register primary metrics, guardrails, sample size and duration.
- Analyze incremental conversion and backend net revenue.
- Expand to product, seller, audience and event segments only after identity and
  denominator quality pass.

## Governance

Every proposed action must contain:

- a decision, not merely an observation;
- dated and named evidence;
- a confidence level and known limitations;
- one accountable owner role;
- concrete proposed work;
- measurable acceptance criteria;
- a human approval record before external execution;
- a verification result before closure.

Credentials, customer identifiers, attendee PII, raw transaction IDs and live
order records must never enter the public repository or static dashboard.

## How progress stays visible

- This proposal records product direction and delivery phases.
- [`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md) defines permanent
  decision and safety rules.
- [`P2_MEASUREMENT_BACKLOG.md`](P2_MEASUREMENT_BACKLOG.md) tracks measurement
  prerequisites and acceptance tests.
- [`demo/README.md`](demo/README.md) maps UI changes to the correct files.
- Draft pull requests show proposed code, test results and unresolved decisions
  before changes reach the public site.

The proposal should be updated when a phase exits, a data source becomes
decision-ready, or a major decision boundary changes. Weekly metric values stay
in reviewed private snapshots rather than in this document.
