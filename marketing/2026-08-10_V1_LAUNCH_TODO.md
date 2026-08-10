# ANKA Marketing Decision Agent V1 launch todo

Target: **Thursday, 2026-08-13**

Status on **Monday, 2026-08-10**: implementation and local QA are complete on
branch `agent/v1-action-workflow`. The remaining V1 gates are external access,
one controlled end-to-end task, private deployment and engineering data fixes.

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

- [x] Public GitHub Pages remains read-only and contains no credentials or PII.
- [x] The private/internal Action Center reads persisted Action Registry state.
- [x] Approve, reject and assign record actor, timestamp and note.
- [x] Reject creates no external task.
- [x] Approval creates no more than one external task for the action.
- [x] Engineering actions can create a GitHub Issue when server credentials are configured.
- [x] Marketing actions can create a Basecamp To-do when OAuth and destination IDs are configured.
- [x] Missing credentials disable the integration safely and explain what is needed.
- [x] Every action shows its history, current owner, external-task link and next verification date.
- [x] Manually closing a task moves it to verification pending; it does not prove the business outcome.
- [x] At least one deterministic verification rule can return verified, failed or inconclusive.
- [x] The exact weekly pipeline can be run in one command and has a deployable schedule definition.
- [x] Connector failure is shown as missing data, never zero performance.
- [x] Automated tests and desktop/mobile QA pass.
- [ ] Create one controlled GitHub Issue and, if approved by Vanessa, one Basecamp To-do.
- [ ] Deploy the private API/UI and run the acceptance test with real authorized users.

## Roles

### Codex / implementation

- [x] Extend the Action Registry for owner, due date, verification and external-task identity.
- [x] Extend the private API for action detail, timeline, assignment and controlled transitions.
- [x] Wire the internal Action Center to those endpoints.
- [x] Implement GitHub and Basecamp adapter boundaries with idempotency and dry-run tests.
- [x] Implement verification scheduling and result recording.
- [x] Prepare the weekly scheduled-job configuration and runbook.
- [x] Add tests, QA, docs, commit and push an isolated branch.
- [ ] Open/merge a PR after GitHub CLI access or manual PR review is available.

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

- [x] Freeze scope and engineering request.
- [x] Extend registry and API contract.
- [x] Complete the first interactive approval/assignment UI.

### Tuesday, Aug 11

- [x] Finish approval, rejection, assignment and timeline.
- [x] Complete GitHub adapter.
- [ ] Test one controlled GitHub Issue when authorized.
- [x] Complete Basecamp adapter contract.
- [ ] Complete Basecamp OAuth only if Vanessa approves this workflow.

### Wednesday, Aug 12

- [x] Add manual task-complete and verification-pending behavior.
- [ ] Add automatic GitHub/Basecamp task-status polling after V1 if it proves useful.
- [x] Add weekly-job configuration and failure handling.
- [x] Run backend, security, desktop and mobile QA.

### Thursday, Aug 13

- [ ] Run one complete evidence-to-action workflow.
- [ ] Create one approved engineering task and one approved marketing task when credentials are ready.
- [ ] Confirm refresh-safe history and idempotency.
- [ ] Merge, deploy and freeze V1; record credential-dependent exceptions explicitly.
