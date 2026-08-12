# ANKA GA4 and order-data repair request

Requested by: Marketing Data / AI
Requested completion for initial validation: **Wednesday, 2026-08-12**
Validation window: the first seven complete days after release

## Why this is urgent

ANKA can now read GA4 transactions and reported revenue, but it cannot safely
attribute orders to marketing channels or measure the complete product funnel.
This blocks channel revenue, CAC, ROAS, product-view conversion and trustworthy
A/B-test analysis.

Latest complete period: **2026-08-03 through 2026-08-09**

| Finding | Current evidence | Business impact |
|---|---:|---|
| Duplicate/residual purchase signal | 36 purchase events vs 24 transactions | Conversion and revenue event counts can be overstated |
| Product view missing | 0 `view_item` users vs 251 add-to-cart users | Product-view-to-cart conversion cannot be calculated |
| Purchase acquisition missing | 24/24 transactions and 2,974.81 revenue are `(not set)` | Channel revenue, CAC and ROAS are blocked |
| Payment step requires QA | 57 payment-info users vs 68 checkout users | Available, but trigger timing and one-fire behavior still need confirmation |

## P0 requests

### 1. Make one purchase event canonical

Please identify every place that can emit `purchase`, including application
code, server/Measurement Protocol, Google Tag Manager and residual browser tags.

Required result:

- one `purchase` per completed order;
- a stable, non-empty `transaction_id` matching the order-system ID;
- retries are idempotent and do not produce another logical purchase;
- `currency`, `value`, coupon and item fields use the agreed order values;
- the release date and disabled/replaced tags are recorded.

Acceptance test:

- daily purchase event count equals the unique valid transaction-ID count for
  seven consecutive complete days;
- zero duplicate transaction IDs, zero missing IDs and zero-revenue rows are
  explained or corrected;
- test order reconciles between the browser/server implementation, GA4 and the
  order system.

### 2. Implement `view_item` on product-detail pages

Fire `view_item` once after a product detail page has rendered the product being
viewed. Include at least:

- `item_id` or `item_name`;
- item name, category, displayed price and currency;
- seller/store identifier only if it is approved as a non-PII business field.

Acceptance test:

- a test product detail page produces one valid `view_item`;
- `view_item` users are non-zero and logically precede/exceed add-to-cart users;
- the same `item_id` survives view, add-to-cart, checkout and purchase.

Google's current ecommerce event reference requires at least `item_id` or
`item_name` in the item payload:
https://developers.google.com/analytics/devguides/collection/protocol/ga4/reference/events

### 3. Preserve session acquisition on the canonical purchase

Please trace how the canonical purchase is generated. If it is sent through
GA4 Measurement Protocol/server-side tracking, confirm that the purchase uses
the matching browser `client_id` and the originating `session_id`, and is sent
inside Google's session-attribution timing requirement.

Please also confirm:

- original `utm_source`, `utm_medium`, `utm_campaign` and `utm_content` are
  captured on entry and are available through checkout/order creation;
- payment providers and marketplace redirects do not replace the original
  source with a referral or unknown value;
- consent behavior is preserved;
- campaign identity is tested for Email, Meta, TikTok and one partner link.

Acceptance test:

- test orders from controlled tagged links retain the expected acquisition
  source/medium/campaign;
- transactions no longer collect entirely under `(not set)`;
- source-level transactions reconcile to the GA4 transaction total;
- the test record documents the URL, expected values, transaction ID and actual
  GA4 output.

Google's current Measurement Protocol guidance says session attribution needs
the matching `session_id`, and the request must arrive within 24 hours of the
session start:
https://developers.google.com/analytics/devguides/collection/protocol/ga4/use-cases

## P1 requests

### 4. Confirm the payment-step contract

`add_payment_info` is present, so this is QA rather than a new implementation.
Please document its exact trigger and confirm it fires once per checkout attempt
at the agreed visible payment milestone. It should stay below or equal to
`begin_checkout` users under normal conditions.

### 5. Provide a privacy-safe backend order feed

Please identify the order system and provide either a read-only API, warehouse
view or scheduled CSV with:

- order ID / GA4 transaction ID;
- created, paid, cancelled and refunded timestamps;
- payment status;
- gross revenue, discount/coupon, refund, fees if available, net revenue and
  currency;
- product/SKU, quantity and approved seller/store business ID;
- no customer name, email, phone, address, IP or payment details.

Acceptance test:

- the 24 GA4 transactions for 2026-08-03 through 2026-08-09 can be reconciled to
  paid/refunded backend orders;
- differences are classified rather than silently dropped;
- refund and net-revenue totals can be reproduced.

## Questions we need engineering to answer

1. Which service or tag currently owns the canonical `purchase` event?
2. Is purchase emitted client-side, server-side, through GTM, or by more than one?
3. Where can Marketing see or request changes to the GTM container?
4. Are GA4 `client_id` and `session_id` available when the server sends purchase?
5. Where are first-touch and session UTMs stored through checkout?
6. Which payment/checkout domains can overwrite referrals?
7. Which system is the financial source of truth for paid and refunded orders?
8. Who owns each fix, and what release date can we validate?

## Copy/paste message to engineering

> Hi team — the new ANKA marketing data checks found three P0 measurement
> blockers in the completed Aug 3–9 period: GA4 has 36 purchase events but only
> 24 transactions, `view_item` is zero despite 251 add-to-cart users, and all 24
> transactions / 2,974.81 revenue are attributed to `(not set)`. This prevents
> reliable channel revenue, CAC/ROAS and product-funnel analysis. Could you please
> review the attached repair request, identify an owner for the purchase event,
> product-detail tracking and session-attribution fixes, and tell us what can be
> released by Wed Aug 12? We also need the owner/source for a privacy-safe paid
> and refunded order export. Marketing will validate the release in GA4 and will
> not request customer PII.
