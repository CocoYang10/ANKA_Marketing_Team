# ANKA Marketing Decision Agent — progress brief

## One-sentence update

The project has moved from a reporting dashboard to a working local decision-agent foundation: it validates evidence, generates ranked actions with owners and completion tests, and exposes them in a five-part workspace; authenticated execution and full revenue attribution are the next integration phase.

## What works today

- GA4 extraction covers traffic, funnel events, transactions, reported revenue, country and purchased items.
- Instagram and MailerLite provide aggregate evidence; Facebook is partial and TikTok is awaiting OAuth/API completion.
- Data-quality rules stop unsupported CAC, ROAS, channel-revenue and causal experiment claims.
- The Action Center generates stable proposals with priority, evidence, owner, confidence, limitations and acceptance criteria.
- An audited local registry supports the lifecycle from `PROPOSED` through approval, implementation, verification and closure.
- The workspace contains Action Center, Growth & Revenue, Audience & Products, Events and Data Health views.
- Growth & Revenue now includes source-mix and attribution donuts, a clean-session week comparison and a visual commerce-stage path.
- A reviewed aggregate fallback snapshot allows the static public demo to load safely after the branch is merged.

## What the Action Center does

1. Observe source evidence for an exact period.
2. Validate whether the evidence is decision-safe.
3. Diagnose a measurement failure or growth opportunity.
4. Produce a bounded proposal with an accountable owner and a measurable definition of done.
5. Require human approval before external work is created or assigned.
6. Preserve status and evidence so the result can be checked after implementation.

Today, steps 1–4 and the audited status foundation are working locally. The static approval button is intentionally a preview. Ticket creation, team notification and automatic verification still need authenticated company integrations.

## Why the public URL returns 404

The demo exists on the draft branch `agent/marketing-decision-workspace`, while GitHub Pages publishes the `main` branch. The stable `/marketing/demo/` URL will exist only after Draft PR #1 is merged and Pages redeploys.

## Next delivery sequence

1. Merge the reviewed draft branch so the public demo URL exists.
2. Connect backend paid/refunded orders and reconcile them to GA4 transaction IDs.
3. Repair purchase source retention, `view_item`, residual purchase duplication and UTM coverage.
4. Complete Meta review and TikTok Business OAuth.
5. Decide the company system of record for approved actions: GitHub/Jira plus Slack/Teams notification.
6. Add 8–12 weeks of canonical trend history and experiment assignment/exposure data.
7. Run one real action through approval → implementation → verification and report its business result.

## Suggested 90-second talk track

“The project is no longer just a prettier dashboard. We now have a local Marketing Decision Agent foundation that pulls evidence, checks whether it is trustworthy, diagnoses the most important gap, and produces an auditable action with an owner and a measurable completion test. The interface is organized into five workspaces, with the Action Center as the operating layer and the other tabs providing evidence. GA4 revenue and transactions are now visible, but attribution is still blocked, so the system correctly refuses to recommend budget changes. This week I also strengthened the visual layer with source-mix, clean-traffic, attribution and funnel visuals. The next milestone is to connect the backend order source and an authenticated work system so one approved recommendation can move all the way through execution and verified business impact.”
