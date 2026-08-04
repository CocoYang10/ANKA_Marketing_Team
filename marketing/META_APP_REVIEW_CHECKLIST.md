# Meta App Review — ANKA completion checklist

Snapshot reviewed: 2026-07-29.

## What the screenshot says

- `read_insights`: description, required API calls and policy agreement are done.
  The end-to-end screencast is still missing.
- Instagram insights bundle: the screencast appears done, but the required API
  call is not recognized yet.
- The submission must contain both `instagram_business_basic` and
  `instagram_business_manage_insights`.
- `email`, `pages_show_list`, `business_management`,
  `pages_read_engagement`, `public_profile`, `instagram_manage_insights`, and
  `instagram_basic` show completed descriptions.

## Required API evidence

Run from `marketing/`:

```bash
.venv/bin/python skills/pull-meta-skill/meta_token_audit.py \
  --label "App Review required calls"
```

The reviewer evidence should show successful, read-only calls for:

1. `GET /me?fields=id,name`
2. `GET /{page-id}?fields=id,name,instagram_business_account`
3. `GET /{page-id}/insights?...` for `read_insights`
4. `GET /{ig-user-id}/insights?metric=reach...` for Instagram insights

Do not show an access token in the screencast or reviewer notes.

## Screencast script (2–3 minutes)

1. Show the ANKA internal marketing dashboard login/start screen.
2. Explain that only ANKA staff use it to read performance of assets owned by
   ANKA; the app does not manage third-party Pages.
3. Select Facebook and show Page-level reach/engagement reporting.
4. Select Instagram and show account reach, views, profile views and
   interactions.
5. Change the reporting dates and refresh.
6. Explain why each requested permission is needed.
7. Show that no posting, messaging or customer-profile workflow exists.
8. Log out/end the workflow.

If Facebook metrics are still zero, do not record a fake result. First run the
required calls and resolve the failing metric/version/permission combination.

## Reviewer notes template

ANKA uses these permissions only for an internal, read-only marketing analytics
dashboard operated by ANKA employees. The app reads insights for Facebook Pages
and Instagram professional accounts owned and managed by ANKA. It uses the data
to compare reach, content interactions and traffic contribution across ANKA's
marketing channels. It does not publish content, message users, sell or share
data, or access Pages owned by customers.

Reviewer path:

1. Sign in with the provided test user.
2. Open **Channel Performance**.
3. Select **Facebook** to view Page insights.
4. Select **Instagram** to view professional-account insights.
5. Change the date range to confirm read-only reporting.

Add the exact test-user credentials only inside Meta's protected reviewer
credential fields, never in this file or GitHub.

## Before clicking Submit

- Confirm Privacy Policy URL, Terms URL, data deletion instructions, app icon,
  contact email and authorized domains are live.
- Confirm the app is in Live mode and the provided test user can complete the
  recorded flow.
- Confirm the screencast matches the current UI exactly.
- Confirm the required API-call indicators turn green.
- Confirm the submission includes the new Instagram business permissions Meta
  explicitly requests in the review screen.
- Vanessa reviews the final submission before it is sent.
