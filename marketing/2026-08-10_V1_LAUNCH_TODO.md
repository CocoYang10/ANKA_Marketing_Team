# ANKA Marketing Decision Agent V1 launch todo

Target: **Thursday, 2026-08-13**

## V1 scope

V1 is complete when a reviewed data snapshot can produce an auditable action,
an authorized user can approve or reject it, approval can create exactly one
real task, and the system records what must be checked before the action can be
called verified.

V1 does not require every external source to be connected. Missing TikTok,
Facebook Page insight, order, spend or experiment data must be visible and must
block only the decisions that depend on that data.

## Done means

`Done means` is the acceptance test for a task. It replaces subjective statements
such as “tracking looks fixed” with a check that another person can repeat.

V1 is done when:

- [ ] Public GitHub Pages remains read-only and contains no credentials or PII.
- [ ] The private/internal Action Center reads persisted Action Registry state.
- [ ] Approve, reject and assign record actor, timestamp and note.
- [ ] Reject creates no external task.
- [ ] Approval creates no more than one external task for the action.
- [ ] Engineering actions can create a GitHub Issue when server credentials are configured.
- [ ] Marketing actions can create a Basecamp To-do when OAuth and destination IDs are configured.
- [ ] Missing credentials disable the integration safely and explain what is needed.
- [ ] Every action shows its history, current owner, external-task link and next verification date.
- [ ] Closing a task moves it to verification pending; it does not prove the business outcome.
- [ ] At least one deterministic verification rule can return verified, failed or inconclusive.
- [ ] The exact weekly pipeline can be run in one command and has a deployable schedule definition.
- [ ] Connector failure is shown as missing data, never zero performance.
- [ ] Automated tests and desktop/mobile QA pass.

## Roles

### Codex / implementation

- [ ] Extend the Action Registry for owner, due date, verification and external-task identity.
- [ ] Extend the private API for action detail, timeline, assignment and controlled transitions.
- [ ] Wire the internal Action Center to those endpoints.
- [ ] Implement GitHub and Basecamp adapter boundaries with idempotency and dry-run tests.
- [ ] Implement verification scheduling and result recording.
- [ ] Prepare the weekly scheduled-job configuration and runbook.
- [ ] Add tests, QA, docs, commit and PR.

### Coco / access and coordination

- [ ] Send `2026-08-10_ENGINEERING_TRACKING_REQUEST.md` to engineering today.
- [ ] Ask engineering for an owner and expected release date for each P0 item.
- [ ] Create or provide a GitHub fine-grained token limited to the task repository with Issues write permission.
- [ ] Complete Basecamp OAuth and provide account, project and To-do List IDs.
- [ ] Confirm whether a Google Cloud project is available for the private API and scheduler.
- [ ] Continue TikTok Business OAuth and Meta App Review separately; these do not block the Action workflow code.

### Engineering / data owners

- [ ] Remove the residual/duplicate purchase emitter.
- [ ] Implement and validate `view_item`.
- [ ] Preserve browser/session acquisition on the canonical purchase.
- [ ] Confirm the payment-step contract.
- [ ] Identify the backend order source and provide a privacy-safe feed.

## Schedule

### Monday, Aug 10

- [ ] Freeze scope and engineering request.
- [ ] Extend registry and API contract.
- [ ] Start interactive approval/assignment UI.

### Tuesday, Aug 11

- [ ] Finish approval, rejection, assignment and timeline.
- [ ] Complete GitHub adapter and test one controlled issue when authorized.
- [ ] Complete Basecamp adapter contract and OAuth readiness.

### Wednesday, Aug 12

- [ ] Add task-status sync and verification-pending behavior.
- [ ] Add weekly-job configuration, failure state and run history.
- [ ] Run backend, security, desktop and mobile QA.

### Thursday, Aug 13

- [ ] Run one complete evidence-to-action workflow.
- [ ] Create one approved engineering task and one approved marketing task when credentials are ready.
- [ ] Confirm refresh-safe history and idempotency.
- [ ] Merge, deploy and freeze V1; record credential-dependent exceptions explicitly.
