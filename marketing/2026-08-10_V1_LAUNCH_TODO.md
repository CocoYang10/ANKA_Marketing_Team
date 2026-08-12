# ANKA Marketing Decision Agent V1 launch todo

Target: **Thursday, 2026-08-13**

Status on **Monday, 2026-08-10**: implementation and local QA are complete on
branch `agent/v1-action-workflow`. The remaining V1 gates are one controlled
local end-to-end workflow, Basecamp-report output, TikTok access and engineering
data validation. Company GitHub migration and private deployment are later.

## V1 scope

V1 is complete when a reviewed data snapshot can produce an auditable action,
an authorized user can approve or reject it, the Agent can generate a copyable
handoff, and the system records what must be checked before the action can be
called verified. Automatic external task creation is optional.

V1 does not require every external source to be connected. Missing TikTok,
Facebook Page insight, order, spend or experiment data must be visible and must
block only the decisions that depend on that data.

## Done means

`Done means` is the acceptance test for a task. It replaces subjective statements
such as “tracking looks fixed” with a check that another person can repeat.

V1 is done when:

- [x] Public GitHub Pages remains read-only and contains no credentials or PII.
- [x] The private/internal Action Center reads persisted Action Registry state.
- [x] Approve, reject and assign record actor, timestamp and note.
- [x] Reject creates no external task.
- [x] Approval works without any external integration.
- [x] Engineering Actions can optionally create one GitHub Issue after company migration.
- [x] Missing GitHub credentials disable Issue creation safely and explain what is needed.
- [x] Every action shows its history, current owner, external-task link and next verification date.
- [x] Manually closing a task moves it to verification pending; it does not prove the business outcome.
- [x] At least one deterministic verification rule can return verified, failed or inconclusive.
- [x] The exact weekly pipeline can be run in one command and has a deployable schedule definition.
- [x] Connector failure is shown as missing data, never zero performance.
- [x] Automated tests and desktop/mobile QA pass.
- [x] Generate a Basecamp-ready weekly report from the locked decision-first structure.
- [x] Run an isolated local acceptance workflow using current data; final human walkthrough with Coco remains.

## Roles

### Codex / implementation

- [x] Extend the Action Registry for owner, due date, verification and external-task identity.
- [x] Extend the private API for action detail, timeline, assignment and controlled transitions.
- [x] Wire the internal Action Center to those endpoints.
- [x] Implement an optional GitHub adapter boundary with idempotency and dry-run tests.
- [x] Implement verification scheduling and result recording.
- [x] Prepare the weekly scheduled-job configuration and runbook.
- [x] Add tests, QA, docs, commit and push an isolated branch.
- [ ] Open/merge a PR after the current V1 changes are reviewed.

### Coco / access and coordination

- [ ] Send `2026-08-10_JF_GA4_VALIDATION_FOLLOWUP.md` to JF/engineering today.
- [ ] Ask engineering for an owner and expected release date for each remaining P0 item.
- [ ] Try TikTok Web Business Suite and identify the Business Center Admin if linking is required.
- [x] Confirm Basecamp is copy/paste report output only; no API or OAuth.
- [x] Defer GitHub token, company repository migration and cloud hosting until local V1 is accepted.
- [ ] Continue Meta App Review in the existing Meta project; it does not block the Action workflow code.

### Engineering / data owners

- [ ] Remove the residual/duplicate purchase emitter.
- [ ] Implement and validate `view_item`.
- [ ] Preserve browser/session acquisition on the canonical purchase.
- [ ] Confirm the payment-step contract.
- [ ] Identify the backend order source and provide a privacy-safe feed.

## Schedule

### Monday, Aug 10

- [x] Freeze scope and engineering request.
- [x] Extend registry and API contract.
- [x] Complete the first interactive approval/assignment UI.

### Tuesday, Aug 11

- [x] Finish approval, rejection, assignment and timeline.
- [x] Complete GitHub adapter.
- [x] Defer controlled GitHub Issue creation until the company repository is selected.
- [x] Remove Basecamp task integration from V1.
- [x] Lock the Basecamp copy/paste report template.

### Wednesday, Aug 12

- [x] Add manual task-complete and verification-pending behavior.
- [ ] Add automatic GitHub task-status polling after migration if it proves useful.
- [x] Add weekly-job configuration and failure handling.
- [x] Run backend, security, desktop and mobile QA.
- [x] Separate buyer and seller evidence, add 7/14/28-day traffic context, and redesign Events around one tracking link per event × channel.

### Thursday, Aug 13

- [x] Run one complete isolated evidence-to-action workflow through verification.
- [x] Generate one engineering handoff and one Basecamp-ready weekly report.
- [x] Confirm refresh-safe history and idempotency through automated tests.
- [ ] Merge and freeze the local V1; record source-access exceptions explicitly.
