# ANKA Agent operating model

## The problem

A dashboard informs only when someone opens it, trusts it, interprets it
correctly and decides to act. ANKA currently needs a system that turns weak or
strong evidence into owned work, then verifies whether the work changed the
business.

The Agent is not the dashboard. The dashboard is one optional view of the
Agent's evidence and history.

## The operating loop

```text
Sense → Validate → Diagnose → Propose → Approve → Act → Verify → Learn
```

1. **Sense:** pull exact-period data and implementation changes.
2. **Validate:** block conclusions when freshness, identity, grain or
   reconciliation fails.
3. **Diagnose:** distinguish a business movement from a measurement failure.
4. **Propose:** produce a bounded action with evidence, owner and acceptance
   criteria.
5. **Approve:** Vanessa approves external or decision-changing actions.
6. **Act:** create a ticket, experiment brief or campaign draft in the system
   where the team already works.
7. **Verify:** rerun the acceptance test after the change.
8. **Learn:** close, revise or escalate the action and preserve the evidence.

## Initial jobs, ordered by company value

### 1. Measurement Reliability Agent

Primary customer: engineering and marketing operations.

It detects broken events, duplicate purchases, attribution loss, stale
connectors and reconciliation gaps. Its output is an engineering-ready ticket,
not a chart.

Success:

- time from tracking regression to owned ticket;
- percentage of P0 events meeting the data contract;
- GA4-to-order reconciliation coverage;
- time to close measurement blockers.

### 2. Growth Experiment Agent

Primary customer: marketing lead and product/engineering.

It turns a supported opportunity into a pre-registered experiment brief,
checks assignment and exposure instrumentation, calculates readiness, and
refuses to declare a winner when causal evidence is absent.

Success:

- decision-quality experiments launched;
- time from hypothesis to approved design;
- percentage of experiments with valid assignment/exposure;
- incremental conversion or net revenue, not number of tests.

### 3. Campaign Operations Agent

Primary customer: lifecycle and social teams.

It audits campaign links, naming, dates, segments and required assets; drafts
briefs and QA checklists; and verifies post-launch tagging. Publishing and
budget changes remain human-approved.

Success:

- campaign QA defects caught before launch;
- UTM contract coverage;
- campaign-to-session and campaign-to-order match coverage;
- hours of manual reporting or QA removed.

### 4. Decision Memory Agent

Primary customer: Vanessa and leadership.

It records what was believed, what action was approved, who owned it, what
result followed and whether the original hypothesis survived.

Success:

- approved actions with recorded outcomes;
- repeated work or repeated mistakes avoided;
- decisions traceable to evidence and implementation dates.

## System components

| Component | Role |
|---|---|
| Source connectors | GA4, order ledger, Meta, TikTok, MailerLite, ad spend |
| Evidence store | Versioned aggregate facts, dates, lineage and quality status |
| Policy engine | Deterministic trust gates, permissions and prohibited actions |
| Reasoning layer | Diagnoses and hypotheses grounded in accepted evidence |
| Action registry | Proposed, approved, in-progress, verified, rejected |
| Tool adapters | GitHub/Jira ticket, Slack/Teams approval, experiment brief |
| Evaluator | Checks recommendation quality, action completion and business result |
| Dashboard | Optional history, status and evidence view |

## Rules for usefulness

1. No recommendation without cited evidence and a comparison or denominator.
2. No action without an owner and acceptance criteria.
3. No causal claim without assignment and exposure evidence.
4. No budget recommendation without spend and backend paid-order evidence.
5. No automated external write before the specific action class is approved.
6. Every action must be rechecked after its implementation window.
7. Agent success is measured by resolved problems and business outcomes, not
   prompts, messages, charts or recommendations generated.

## Implementation order

1. Evidence-to-action brief and local issue drafts.
2. Human-reviewed action registry with lifecycle status. **Implemented locally.**
3. GitHub/Jira ticket creation after approval.
4. Slack/Teams notification and approval.
5. Automatic verification against acceptance criteria.
6. Experiment design and analysis.
7. Only then consider bounded campaign execution.
