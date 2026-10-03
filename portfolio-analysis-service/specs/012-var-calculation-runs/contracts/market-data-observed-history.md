# Consumed contract: market-data-web-service observed-only history (feature 009)

This feature **consumes** the following. It is delivered by market-data-web-service
`009-observed-price-history`. Until then, runs fail with reason `observed_history_unsupported`.

## Request

```
GET /securities/{identifier}/history?from=YYYY-MM-DD&to=YYYY-MM-DD&currency=GBP&fill=none
```

## Response (200)

```json
{
  "ticker": "IE00BJSPMJ28",
  "currency": "GBP",
  "first_observed_date": "2014-01-02",
  "last_observed_date": "2026-09-22",
  "prices": [
    {"date": "2026-09-01", "close": 3.912},
    {"date": "2026-09-02", "close": 3.927}
  ]
}
```

* `prices` holds **only** dates with a real observation, never forward- or back-filled.
* `first_observed_date` / `last_observed_date` cover the instrument's whole known history, not just
  the requested range. They may be `null` if nothing is known.

## How this service interprets it

| Market-data behaviour | Interpretation in this feature |
|---|---|
| 200 **without** a `first_observed_date` key | Old service ignoring `fill=none` → `ObservedHistoryUnsupportedError` → run fails `observed_history_unsupported` |
| 200 with an empty `prices` | No observations in range; returns NaN |
| 404 for a held instrument | `instrument_not_found` warning; the instrument has no history (rescale) |
| 404 for a proxy | `proxy_unresolved` warning; treated as having no proxy |
| Other non-2xx, timeout, connection error | `MarketDataServiceError` → run fails `market_data_unavailable` |
