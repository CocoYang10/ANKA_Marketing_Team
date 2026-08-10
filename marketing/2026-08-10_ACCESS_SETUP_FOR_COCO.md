# ANKA V1 access setup — beginner guide for Coco

Do not paste tokens, passwords or client secrets into chat, screenshots,
Basecamp or GitHub. Put them only in `marketing/.env` or an approved company
secret manager.

## What does not block V1 development

- The project may remain in Coco's GitHub while V1 is being built.
- GitHub Issue automation can stay disabled until the project is moved to the
  company-owned repository.
- Basecamp needs no API, OAuth or token. The Agent will generate a formatted
  weekly report for Vanessa to review and copy/paste.
- A company cloud project and internal URL can be decided after the local V1
  workflow is complete.

## 1. GitHub repository and Issue automation — later

A GitHub Issue is an engineering task attached to a code repository. It is not
a code change and it is not required for GA4, TikTok, Meta, the Dashboard or the
Action Registry to work.

The current V1 supports two valid workflows:

1. **Now:** approve an Action and use **Copy brief** to send it to engineering.
2. **Later:** after the project moves to the company GitHub, let an approved
   engineering Action create one Issue automatically.

Only ask for the company repository when ANKA decides to enable workflow 2. At
that point, ask:

> Which company-owned GitHub repository should contain the Marketing Decision
> Agent, and should approved measurement Actions create Issues in that same
> repository or a separate engineering repository?

Then ask for the GitHub username of the person or team that should initially
receive those Issues.

### Fine-grained token — create only after the destination is confirmed

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
9. Put it in the private environment:

```text
GITHUB_ISSUES_TOKEN=the-token-you-copied
GITHUB_ISSUES_REPOSITORY=OWNER/REPOSITORY
GITHUB_DEFAULT_ASSIGNEE=optional-github-username
```

Official permission reference:
https://docs.github.com/en/rest/issues/issues

## 2. Basecamp — report output only

There is no Basecamp integration in V1.

The Agent's Basecamp responsibility is:

1. generate one weekly Marketing Report using the approved structure and
   styling;
2. show a reviewable HTML version;
3. produce content that Vanessa can copy/paste into Basecamp;
4. never post automatically or require Basecamp OAuth.

The current reference format is:

`/Users/cocoyang/Downloads/2026-07-20_Marketing-Report-Week-29 (1).html`

The final report template will be locked after Coco confirms which sections,
colors and comparison rules must be retained.

## 3. Private API — part of ANKA, not TikTok or Meta

The ANKA Private API is the security door between the internal Dashboard and
the Action Registry. It lets the internal page:

- read current Action status and history;
- save approval/rejection and the human actor;
- assign an owner and due date;
- optionally create a GitHub Issue after company migration;
- schedule and record verification.

TikTok, Meta, GA4 and MailerLite are upstream data sources. They feed evidence
into the Agent; they do not store Action Center approvals.

## 4. Company cloud and internal access — later

The local V1 can be completed before selecting a company cloud project.

Cloud hosting becomes necessary only when another person needs to open the
private Action Center from their own computer. The company Cloud Owner is the
person who can approve where the private backend runs, who may access it and
where its secrets are stored. This is usually an engineering, infrastructure or
IT responsibility—not a new data source.

Do not request cloud access yet. When the local V1 is accepted, ask engineering:

> Which company-approved environment should host a small private internal API
> and weekly scheduled job, and who owns deployment and secret management?

## What Coco must do now

- [ ] Send the GA4 validation follow-up to JF/engineering.
- [ ] Try the TikTok Web Business Suite route in the TikTok access guide.
- [ ] Identify the TikTok Business Center Admin only if account linking is
  required.
- [ ] Continue Meta App Review in the existing Meta conversation/project.
- [ ] Do not create GitHub, Basecamp or cloud credentials yet.
