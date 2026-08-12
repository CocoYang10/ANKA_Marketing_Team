# TikTok organic analytics access for ANKA

Date checked: **2026-08-10**

ANKA needs organic account and post performance, not only advertising data.
TikTok Studio, Web Business Suite, Business Center and API for Business are
different surfaces.

## Route 1 — use Web Business Suite now

This is the fastest way to stop relying on mobile screenshots.

1. Go to https://www.tiktok.com in a desktop browser.
2. Log in as the exact ANKA brand TikTok account.
3. Click the profile picture.
4. Select **Business Suite**.
5. Open **Analytics**.
6. Export the same fixed completed-week range from:
   - Overview;
   - Audience;
   - Video.

TikTok's current Web Business Suite supports Reach, Engagement, Conversion,
Followers, audience profile and video views for custom date ranges. Official
instructions:

- https://ads.tiktok.com/help/article/how-to-access-web-business-suite
- https://ads.tiktok.com/help/article/navigate-web-business-suite

If **Business Suite** is missing, do not change the account type immediately.
First confirm with the account owner whether this is a Business Account and
whether Coco is logged into the correct profile.

### Temporary V1 ingestion

Until API review is complete, export the three files weekly and place them in a
private input folder. The Agent should mark the source `MANUAL_EXPORT`, preserve
the selected date range and reconcile totals to the native Analytics screen.

This is acceptable for V1 because the evidence is real and repeatable even
though the retrieval is manual.

## Route 2 — link the account to Business Center for team access

Use this only if ANKA wants multiple people to see/manage the account.

The person doing these steps must be a **Business Center Admin**:

1. Go to https://business.tiktok.com.
2. Open **Accounts → TikTok accounts**.
3. Select **Add a TikTok account**.
4. Choose **Link an existing TikTok account** and **Send a QR code**.
5. Select **Manage account**. Do not select only **Deliver ads**; that permission
   is insufficient for the organic-management workflow.
6. The person logged into the ANKA TikTok mobile account scans the QR code:
   **Profile → menu → Your QR code → Scan**.
7. Approve the requested Business Center access.
8. Back in Business Center, verify that the permission column says
   **Manage account** and that Analytics is visible.

Official instructions:
https://ads.tiktok.com/help/article/how-to-integrate-your-business-account-with-business-center

Common reasons this route appears not to work:

- Coco is not a Business Center Admin;
- the wrong TikTok profile is logged in on the phone;
- the request selected **Deliver ads** instead of **Manage account**;
- the TikTok profile is not a Business Account;
- the QR request has not been approved by the account owner;
- a region-specific business-verification requirement is incomplete.

## Route 3 — connect the Organic API after native access works

Portal: https://business-api.tiktok.com/portal

Do not use the Research API for this project. Research API eligibility is for
qualified independent researchers and it is not the correct product for a
brand's own operating dashboard. Do not use only the Marketing API either;
Marketing API mainly serves advertising accounts and paid-campaign reporting.

For ANKA's organic data, use **API for Business → Organic API → Accounts API**.

### App permissions required by the current connector

Request the smallest read-only account permissions that cover:

- **TikTok Accounts → Account User** for `/business/get/`;
- **TikTok Accounts → Get Account Media** for `/business/video/list/`.

The returned OAuth token should include the corresponding read scopes used by
the current connector, including `user.info.basic`, `user.insights`,
`video.list` and `video.insights`.

The connector does not need permission to publish posts, manage comments,
change ads or send messages.

### Data the Agent needs

Account/profile snapshot:

- account ID, display name and username;
- total followers and total likes;
- profile views and account video views when returned for the authorized
  account/date grain;
- audience country and gender breakdown where available.

Post-level data:

- post ID, caption and create time;
- video views and reach;
- likes, comments and shares;
- total/average watch time and full-watch rate;
- impression sources and audience countries where available.

Official endpoint inventory:
https://business-api.tiktok.com/gateway/docs/index?doc_id=1735713875563521

TikTok's official Postman collection shows the profile and post field shapes:
https://www.postman.com/tiktok/tiktok-api-for-business/documentation/efqhadc/tiktok-business-api-v1-3

### Portal and OAuth sequence

1. Register/select the ANKA developer organization in API for Business.
2. Create a developer app.
3. Add the two Accounts API read permissions above.
4. Configure the exact private callback URL:
   `https://YOUR-PRIVATE-API.example.com/oauth/tiktok/callback`.
5. Put the App ID and Secret in the private server environment as
   `TIKTOK_BUSINESS_APP_ID` and `TIKTOK_BUSINESS_SECRET`.
6. Open `/oauth/tiktok/start` on ANKA's private backend.
7. Log in as the ANKA-owned TikTok account and authorize the read scopes.
8. Exchange the one-use `auth_code` immediately; TikTok documents a ten-minute
   validity window.
9. Store the access/refresh tokens only on the private server.
10. Pull one fixed week and reconcile it to Web Business Suite before using it
    for decisions.

## Current recommendation

1. **Today:** try Route 1. It may solve weekly reporting without any developer
   approval.
2. **If Route 1 is missing:** identify the actual account owner and Business
   Center Admin, then use Route 2 with **Manage account**.
3. **After the native account is confirmed:** apply for Route 3 and connect the
   existing `pull_tiktok.py` connector.

TikTok remains `NOT_CONNECTED` in the Agent until a fixed-week API result or
native export reconciles to the source UI. Missing TikTok data blocks TikTok
recommendations only; it does not block GA4, MailerLite or the Action workflow.
