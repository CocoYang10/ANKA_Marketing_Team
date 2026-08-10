# GA4 tracking validation follow-up for JF / Engineering

Date: **2026-08-10**

## What the July 30 engineering update establishes

The update says that engineering restored revenue, added purchase coverage
across payment methods, implemented the checkout journey and improved tracking
for visitors who accept analytics cookies.

The completed Aug 3–9 GA4 pull confirms meaningful progress:

- 24 transactions now have non-empty transaction IDs;
- GA4 reports 2,974.81 in purchase revenue instead of zero;
- `begin_checkout`, `add_shipping_info`, `add_payment_info` and `purchase` are
  present;
- the 24 audited transaction rows have no missing ID, duplicate ID or
  zero-revenue row.

This means **sales and checkout data now exist**. It does not yet establish
that every payment method is financially complete, that the product funnel is
complete, or that marketing attribution is usable.

## What remains unresolved in Aug 3–9 data

| Finding | Evidence | Why Marketing still needs Engineering |
|---|---:|---|
| Purchase signal does not reconcile | 36 purchase events vs 24 transactions | Engineering must identify every client, GTM and server emitter and declare one canonical purchase |
| Product-detail stage is missing | 0 `view_item` users vs 251 add-to-cart users | Only product/frontend engineering can fire a valid item-level event on product pages |
| Purchase attribution is unusable | all 24 transactions and 2,974.81 revenue appear under `(not set)` | Checkout/server tracking must preserve the originating client/session and campaign context |
| “All payment methods” is not independently proven | no backend paid/refunded order comparison is available | The order/payment source of truth is required to test completeness by payment method |
| Consent improvement is not quantified | no consent acceptance/measurement coverage table was supplied | Engineering must provide the implementation date and a repeatable consent test matrix |

Current analytical status:

- **Safe:** GA4 contains directional transaction and reported revenue totals.
- **Not safe:** channel revenue, CAC, ROAS, product-view conversion, payment-
  method completeness and A/B-test revenue outcomes.

## Questions for JF / Engineering

1. What exact date and time did each tracking fix go live?
2. Which component is now the canonical `purchase` emitter: application code,
   server/Measurement Protocol or GTM?
3. Are any old browser or GTM purchase tags still active? How do we explain 36
   purchase events versus 24 unique transactions for Aug 3–9?
4. Does the canonical purchase include the original browser `client_id` and
   `session_id`? Where are UTMs stored while the user moves through checkout?
5. Why do all 24 transactions and all 2,974.81 revenue appear under `(not set)`?
6. Is `view_item` implemented on product-detail pages? If yes, what event name
   and page trigger should Marketing query? If not, who owns it?
7. Which backend system is the financial source of truth for paid, cancelled
   and refunded orders?
8. Can Marketing receive a privacy-safe weekly export/API containing order ID,
   paid/refunded status, gross revenue, discount, refund, net revenue, currency
   and product/SKU, with no customer PII?
9. How was “all payment methods” validated against that order source?
10. What repeatable test proves the analytics-cookie change increased measured
    coverage without violating consent?

## Copy/paste message

> Hi JF — thank you for the July 30 GA4 work. Our Aug 3–9 pull confirms that the
> core improvement is real: GA4 now contains 24 transactions with valid IDs and
> 2,974.81 in purchase revenue, and the checkout-stage events are present. Before
> Marketing uses this for channel allocation and funnel decisions, could you
> help us validate three remaining gaps? We still see 36 purchase events versus
> 24 transactions, `view_item` is zero while 251 users add to cart, and all 24
> transactions / all revenue are attributed to `(not set)`. Could you confirm
> the canonical purchase emitter, whether client/session acquisition is carried
> into the purchase, and who owns product-detail `view_item`? We also need the
> backend paid/refunded order source or a privacy-safe weekly export so we can
> verify the “all payment methods” claim against financial records. The attached
> note has the exact evidence and acceptance questions; no customer PII is
> requested.

## Validation after Engineering responds

Marketing will not call a fix verified on the release date. For the first seven
complete days after release, the Agent will check:

- purchase event count equals unique transaction ID count;
- `view_item` is non-zero and uses a stable item ID through purchase;
- controlled UTM test orders retain the expected source/medium/campaign;
- GA4 paid/refunded orders reconcile to the approved backend source;
- material differences are classified rather than silently removed.
