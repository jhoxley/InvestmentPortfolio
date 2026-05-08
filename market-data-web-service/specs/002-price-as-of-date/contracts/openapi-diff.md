# OpenAPI Contract Change: Add as_of_date to PriceResponse

**Feature**: 002-price-as-of-date
**Affected schema**: `PriceResponse`
**Change type**: Additive (new required property) — non-breaking for existing consumers

---

## Schema Diff — PriceResponse

Add the following property to the `PriceResponse` component in `openapi.yaml`:

```yaml
# In components/schemas/PriceResponse/properties — ADD:
as_of_date:
  type: string
  format: date
  description: >
    The trading date (YYYY-MM-DD) that the returned price observation is sourced from.
    This date equals the most recent date in the historical price series for the same
    ticker, guaranteeing consistency between the /price and /history endpoints.
  example: "2026-05-06"
```

Also add `as_of_date` to the `required` list of `PriceResponse`:

```yaml
# In components/schemas/PriceResponse/required — ADD entry:
required:
  - ticker
  - price
  - currency
  - timestamp
  - market_status
  - as_of_date    # NEW
```

Update the example response for `GET /securities/{ticker}/price` (200 response):

```yaml
# In paths//securities/{ticker}/price/get/responses/200/content/application/json/example — ADD field:
example:
  ticker: AAPL
  price: 286.77
  currency: USD
  timestamp: "2026-05-06T14:30:00Z"
  market_status: closed
  as_of_date: "2026-05-06"    # NEW
```

---

## Reconciliation Guarantee

After this change, for any valid ticker, the following relationship holds:

```
GET /securities/{ticker}/price   →  as_of_date == "2026-05-06"
GET /securities/{ticker}/history →  prices[-1].date == "2026-05-06"
```

Both endpoints now derive their data from `Ticker.history()` making this guarantee structural rather than coincidental.
