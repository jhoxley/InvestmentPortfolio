# Data Model: Currency Translation & FX Pair Endpoint

## Entities

### FxRateEntry

A single exchange rate observation for a currency pair on a given date.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| date | date | Required, ISO 8601 | Trading date of the FX observation |
| rate | float | > 0.0 | Rate of 1 BASE expressed in QUOTE (e.g., 1 USD = 0.79 GBP) |

**Identity**: `(pair, date)` — unique within a given currency pair series.

---

### FxHistoryResponse

Response payload for `GET /fx/{pair}/history`.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| pair | str | 6 alpha chars | Concatenated ISO codes, e.g., `USDGBP` |
| base_currency | str | 3 alpha chars, ISO 4217 | First 3 chars of `pair` |
| quote_currency | str | 3 alpha chars, ISO 4217 | Last 3 chars of `pair` |
| rates | list[FxRateEntry] | Non-empty on success | Chronologically ascending |

---

### PricePoint (updated)

Existing model extended with optional FX rate field.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| date | date | Required | Security trading date |
| close | float | > 0.0 | Close price in target currency (if translated) or native currency |
| fx_rate | float \| None | > 0.0 or null | FX rate applied on this date; `null` when no translation was performed |

**Backward compatibility**: `fx_rate` is `None` for all responses without the `currency` query parameter.

---

### PriceResponse (updated)

Existing model extended with optional FX rate field for current price.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| ticker | str | Required | |
| price | float | > 0.0 | Price in target currency (if translated) or native currency |
| currency | str | 3 alpha chars | Native currency if no translation; target currency if translated |
| timestamp | datetime | UTC | Response timestamp |
| market_status | Literal["open","closed"] | Required | |
| as_of_date | date | Required | |
| fx_rate | float \| None | > 0.0 or null | FX rate applied to the current price; `null` when no translation |

---

### PriceHistoryResponse (updated)

Existing model — field `prices` now contains `PricePoint` entries that may include `fx_rate`.

| Field | Type | Notes |
|-------|------|-------|
| ticker | str | |
| currency | str | Target currency if translated; native currency otherwise |
| prices | list[PricePoint] | Each entry includes `fx_rate` when translation applied |

---

### FxAlignmentError (exception)

Raised when no FX rate (forward or backward fill) can be resolved for a security trading date.

| Attribute | Type | Notes |
|-----------|------|-------|
| pair | str | The currency pair that failed alignment |
| security_date | date | The security trading date with no resolvable FX rate |
| message | str | Human-readable description |

**HTTP mapping**: 404 Not Found.

---

### CurrencyUnavailableError (exception)

Raised when the native currency of a security cannot be determined from the data source.

| Attribute | Type | Notes |
|-----------|------|-------|
| ticker | str | The security whose currency is unknown |
| message | str | Human-readable description |

**HTTP mapping**: 404 Not Found.

---

## Cache Storage

FX time series are stored using the **same `CacheRepository`** as security prices, using the pair code (e.g., `USDGBP`) as the cache key. This produces the file `{cache_dir}/USDGBP.csv` with the same `date,close` CSV schema. The `rate` field maps to the `close` column for storage purposes (reuses existing schema).

`USDGBP` and `GBPUSD` produce **separate** cache files: `USDGBP.csv` and `GBPUSD.csv`. No cross-reference or inversion is performed.

---

## Validation Rules

### ISO 4217 Currency Code Validation

Applied to:
- `currency` query parameter on security endpoints
- Both components of the `pair` path parameter on the FX endpoint

Rules:
- Must be exactly 3 uppercase alphabetic characters
- Must be a member of the supported ISO 4217 code set (static frozenset in `app/validators/currency.py`)
- Validation failure → HTTP 422 with descriptive error message

### FX Pair Format Validation

Applied to the `{pair}` path segment in `GET /fx/{pair}/history`:
- Must be exactly 6 alphabetic characters
- Characters 1–3 must be a valid ISO 4217 code (base currency)
- Characters 4–6 must be a valid ISO 4217 code (quote currency)
- Base and quote must not be the same code (e.g., `USDUSD` is invalid)

---

## Relationships

```
PriceHistoryResponse
  └── prices: list[PricePoint]
        └── fx_rate: float | None  (populated iff currency translation applied)

FxHistoryResponse
  └── rates: list[FxRateEntry]

CacheRepository
  └── stores both security prices and FX rates (same CSV schema, different filenames)
        ├── AAPL.csv       (security price history)
        └── USDGBP.csv     (FX rate history, stored as close=rate)

FxInnerProvider
  └── wraps YFinanceProvider
  └── translates "USDGBP" → "USDGBP=X" for yfinance API call

CachedPricingProvider (for FX)
  └── wraps FxInnerProvider
  └── uses CacheRepository with pair code as cache key
```
