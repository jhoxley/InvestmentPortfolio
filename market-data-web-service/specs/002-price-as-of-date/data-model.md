# Data Model: Add As-Of Date to Current Price Response

**Feature**: 002-price-as-of-date
**Date**: 2026-05-06

---

## Changed Entity: PriceResponse

The `PriceResponse` model gains one new required field. All existing fields are unchanged.

| Field | Type | Required | Change | Description |
|-------|------|----------|--------|-------------|
| ticker | str | ✅ | Unchanged | Requested ticker symbol |
| price | float | ✅ | Unchanged | Most recent daily closing price (always > 0) |
| currency | str | ✅ | Unchanged | ISO 4217 currency code |
| timestamp | datetime | ✅ | Unchanged | ISO 8601 datetime of when the response was generated |
| market_status | str | ✅ | Unchanged (bug fix to source) | `"open"` or `"closed"` based on current market state |
| **as_of_date** | **date** | **✅ NEW** | **Added** | **The trading date (YYYY-MM-DD) the `price` observation is sourced from** |

### as_of_date field rules

- Always a valid calendar date in YYYY-MM-DD format
- Always ≤ today's date (never a future date)
- Always a trading day on the relevant exchange (weekdays when the exchange was open)
- Equals the `date` field of the most recent `PricePoint` returned by `GET /securities/{ticker}/history` for the same ticker and any date range that includes the present day

---

## Unchanged Entities

The following entities are unchanged by this feature:

- **PricePoint** (`date`, `close`) — no modifications; `date` field is the reconciliation reference
- **PriceHistoryResponse** (`ticker`, `currency`, `prices`) — no modifications
- **ErrorResponse** (`detail`, `code`) — no modifications

---

## Internal Data Flow Change

### Provider layer (`yfinance_provider.py` — `get_current_price`)

| Field | Before | After |
|-------|--------|-------|
| `price` | `fast_info.last_price` | `history(period="5d")` last row `Close` |
| `as_of_date` | Not present | `history(period="5d")` last row index `.date()` |
| `currency` | `fast_info.currency` | `fast_info.currency` (unchanged) |
| `market_state` | `getattr(fast_info, "market_state", None)` → always `None` | `t.info.get("marketState")` → correct value |

### Service layer (`pricing_service.py` — `get_current_price`)

The service assembles `PriceResponse` from the provider dict. The provider now returns `as_of_date` as a `date` object; the service passes it through directly:

```
provider dict key "as_of_date"  →  PriceResponse.as_of_date
```

No business logic change is required in the service layer for this field — it is a direct pass-through from provider to response.

---

## Validation Rules

- `as_of_date` must be > 0 prices only (same zero-price filter as `price`)
- If `history(period="5d")` returns no rows after zero-price filtering, `DataNotFoundError` is raised (same behaviour as the existing provider)
- The service does not independently validate the date against a trading calendar — the date is always sourced from yfinance which only returns actual trading days in its history output
