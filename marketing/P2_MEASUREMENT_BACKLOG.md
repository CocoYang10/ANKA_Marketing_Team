# P2 measurement backlog

## Ready now

- GA4 session, checkout, transaction and directional revenue monitoring.
- Instagram account reach, views, interactions and profile intent.
- MailerLite campaign sends, opens, clicks and segment comparison.
- Funnel instrumentation health and purchase-event reconciliation warnings.
- Country-level purchase/revenue and purchased-item direction.
- Sanitized Action Center plus Growth, Audience, Events and Data Health views.

## Engineering work that does not require new API approval

| Priority | Work | Acceptance test |
|---|---|---|
| P0 | Remove residual client/GTM purchase tag | purchase event count reconciles to unique transaction IDs for seven consecutive days |
| P0 | Implement `view_item` | product-detail views appear with valid item ID/name and precede add-to-cart |
| P1 | Continue validating `add_payment_info` | payment users remain non-zero, stay below checkout users and fire once at the agreed step for seven days |
| P0 | Persist acquisition source through purchase | transactions no longer collect under `(not set)` and reconcile by source to GA4 totals |
| P0 | UTM naming contract | paid, email and social campaigns use controlled source/medium/campaign values |
| P1 | Referral exclusions | payment providers do not overwrite the original acquisition source |
| P1 | Backend order export | paid orders reconcile to GA4 transaction IDs; refunds and net revenue are available |
| P1 | Ad-spend extracts | Meta/TikTok spend, campaign ID and currency are available at daily grain |
| P1 | Eventbrite event funnel | stable event ID joins ANKA click, registration, order and check-in aggregates without attendee PII |
| P2 | Experiment assignment table | unique experiment + unit assignment, timestamp and variant are persisted |
| P2 | Exposure event | exposure occurs once after the tested experience is actually rendered |
| P2 | KPI registry | each primary metric and guardrail has an owner, formula, grain and source |

## First analysis sequence

1. Stabilize tracking and pass the quality gate.
2. Reconcile GA4 purchases to backend paid orders.
3. Standardize UTMs and clean Direct / payment referral attribution.
4. Add ad spend and calculate channel-level CAC and ROAS.
5. Add product/seller/order dimensions for merchandising analysis.
6. Instrument experiment assignment and exposure.
7. Run the first landing-page message test.

## First A/B test design

Candidate: landing-page value proposition.

- Randomization unit: stable anonymous user ID.
- Variants: current message versus one focused alternative.
- Primary metric: exposed users who reach `begin_checkout`.
- Secondary outcome: transactions per exposed user.
- Value outcome: backend net revenue per exposed user.
- Guardrails: page error rate, checkout error rate, refund rate.
- Required segmentation: device category, new/returning user, country group.

Do not use session-only assignment if the same user may enter multiple variants.
Do not stop the test merely when an early p-value becomes favorable; define
sample size, duration and decision rules before launch.
