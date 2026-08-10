# Weekly Data Pull SOP

Use one exact, completed Monday-Sunday period across every connector. Never mix a
rolling seven-day source with a calendar-week source.

## 1. Run connectors

```bash
.venv/bin/python run_weekly_pipeline.py \
  --since YYYY-MM-DD \
  --until YYYY-MM-DD
```

The pipeline currently runs GA4, Meta, and MailerLite. TikTok remains manual.

## 2. Review connector status

For every source record both:

- connection status
- data-quality/decision-use status

If a connector fails, label its metrics `DATA MISSING`; do not substitute zeros.

## 3. GA4 checks

Before reporting:

- review Direct and `(not set)` shares
- check session step changes against the preceding period
- confirm purchase revenue is non-zero when transactions exist
- confirm no missing or duplicate transaction IDs
- compare purchase event count with transactions
- verify `view_item`, `add_to_cart`, `begin_checkout`,
  `add_shipping_info`, `add_payment_info`, and `purchase`
- reconcile GA4 transactions/revenue to paid backend orders

Periods before 2026-07-23 are pre-repair and must be clearly separated.

## 4. Meta checks

- Instagram aggregate data may be used after a Business Suite spot check.
- Facebook Page insights remain unavailable until API version, metrics, and
  permissions are repaired.

## 5. MailerLite checks

- confirm every campaign falls within the exact period
- review campaigns by language/region
- report Delivered, unique opens, unique clicks, CTOR, unsubscribe, and
  downstream GA4 sessions when available

## 6. TikTok

Enter Studio values manually and label the source `Manual TikTok Studio` until
OAuth and analytics endpoints are validated.

## 7. Approval

Send the completed report and proposed actions to Vanessa before external or
executive distribution.
