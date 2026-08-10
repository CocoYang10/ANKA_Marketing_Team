# ANKA V1 access setup — beginner guide for Coco

Do not paste tokens, passwords or client secrets into chat, Basecamp messages,
screenshots or GitHub. Put them only in `marketing/.env` or the approved cloud
secret manager.

## 1. GitHub Issue: what it is and why ANKA needs it

A GitHub Issue is an engineering task attached to a code repository. It is not a
code change and it is not the same as a pull request. ANKA uses it so an approved
tracking problem has a real owner, discussion, status and link.

Example:

```text
[P0] Remove duplicate purchase tracking
Owner: Checkout Engineer
Evidence: 36 purchase events vs 24 transactions
Done means: counts reconcile for seven complete days
```

### First ask engineering

Send:

> Which GitHub repository should receive GA4/GTM/checkout measurement Issues,
> and what is the GitHub username of the person who should initially receive
> them?

Do not create the token until the destination repository is confirmed.

### Create a fine-grained token

1. Open GitHub profile settings.
2. Open **Developer settings**.
3. Open **Personal access tokens → Fine-grained tokens**.
4. Choose **Generate new token**.
5. Name it `ANKA Marketing Action Agent` and choose a short expiration date.
6. Under Repository access, choose **Only select repositories** and select the
   engineering-approved repository.
7. Under Repository permissions, set **Issues** to **Read and write**. Do not add
   code, administration or organization permissions.
8. Generate and copy the token once.
9. Put it in `marketing/.env`:

```text
GITHUB_ISSUES_TOKEN=the-token-you-copied
GITHUB_ISSUES_REPOSITORY=OWNER/REPOSITORY
GITHUB_DEFAULT_ASSIGNEE=optional-github-username
```

Official permission reference:
https://docs.github.com/en/rest/issues/issues

## 2. Basecamp: why it is optional

Basecamp is not being connected to upload every weekly report. The current
weekly-report copy/paste process can stay unchanged.

The proposed Basecamp connection has one purpose: an approved Marketing action
such as “run the French CTA test” becomes a real Basecamp To-do with an owner,
due date, evidence and Done Means.

Before doing OAuth, ask Vanessa:

> Should approved Marketing Agent actions become Basecamp To-dos? If yes, which
> Basecamp project and To-do List should receive them?

If the answer is no, V1 keeps **Copy brief** and Basecamp remains disabled.

If yes, the integration needs:

- Basecamp OAuth approval;
- Account ID;
- To-do List ID;
- optional Basecamp person IDs for assignment.

The implementation code is already prepared; authorization is the only account
step. Official API reference: https://github.com/basecamp/bc-api

## 3. Private API: what it is

The ANKA Private API is our own security door between the internal Dashboard and
the Action Registry. It is not the TikTok API and not the Meta API.

It allows the internal page to:

- read current action status and history;
- save approval/rejection and the human actor;
- assign an owner and due date;
- create an approved GitHub/Basecamp task;
- schedule and record verification.

TikTok, Meta, GA4 and MailerLite are upstream data sources. They feed evidence
into the Agent; they do not save Action Center approvals.

## 4. What Coco must do today

- [ ] Send `2026-08-10_ENGINEERING_TRACKING_REQUEST.md` to engineering.
- [ ] Ask for an owner and Wednesday release expectation for each P0 fix.
- [ ] Ask which GitHub repository receives measurement Issues.
- [ ] Ask Vanessa whether Marketing Agent actions should become Basecamp To-dos.
- [ ] Do not work on Google Cloud until the company confirms which project/owner
  is appropriate.
