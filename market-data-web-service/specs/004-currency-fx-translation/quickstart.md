# Quickstart: Currency Translation & FX Pair Endpoint

## Integration Scenarios

These scenarios describe the complete request/response lifecycle for each user story.
They serve as the basis for BDD step definitions.

---

## US1 — Current Price Translation

### Scenario A: No translation (no `currency` param)

```
GET /securities/AAPL/price
→ 200
{
  "ticker": "AAPL",
  "price": 185.50,
  "currency": "USD",
  "timestamp": "2025-01-15T10:00:00Z",
  "market_status": "open",
  "as_of_date": "2025-01-14",
  "fx_rate": null
}
```

### Scenario B: Translation to GBP (AAPL is USD-native)

```
GET /securities/AAPL/price?currency=GBP
→ 200
{
  "ticker": "AAPL",
  "price": 146.72,            ← 185.50 × 0.7912
  "currency": "GBP",
  "timestamp": "2025-01-15T10:00:00Z",
  "market_status": "open",
  "as_of_date": "2025-01-14",
  "fx_rate": 0.7912
}
```

### Scenario C: No-op translation (BARC.L is GBP-native, currency=GBP)

```
GET /securities/BARC.L/price?currency=GBP
→ 200
{
  "ticker": "BARC.L",
  "price": 2.18,
  "currency": "GBP",
  "timestamp": "2025-01-15T10:00:00Z",
  "market_status": "closed",
  "as_of_date": "2025-01-14",
  "fx_rate": null
}
```

### Scenario D: Invalid currency code

```
GET /securities/AAPL/price?currency=INVALID
→ 422
{ "detail": "Invalid currency code: 'INVALID'. Must be a 3-letter ISO 4217 code.", "code": "INVALID_CURRENCY" }
```

---

## US2 — Historical Price Translation

### Scenario A: Full translation across date range

```
GET /securities/AAPL/history?from=2025-01-02&to=2025-01-03&currency=GBP
→ 200
{
  "ticker": "AAPL",
  "currency": "GBP",
  "prices": [
    { "date": "2025-01-02", "close": 146.22, "fx_rate": 0.7884 },
    { "date": "2025-01-03", "close": 147.01, "fx_rate": 0.7902 }
  ]
}
```

### Scenario B: Forward-fill — FX market closed on a security trading day

```
Security data:   2025-01-17 (open), 2025-01-20 (US market open — MLK Day for FX)
FX data:         2025-01-17: 0.7900  (2025-01-20 missing — FX market closed)

GET /securities/AAPL/history?from=2025-01-17&to=2025-01-20&currency=GBP
→ 200
{
  "ticker": "AAPL",
  "currency": "GBP",
  "prices": [
    { "date": "2025-01-17", "close": 143.10, "fx_rate": 0.7900 },
    { "date": "2025-01-20", "close": 144.50, "fx_rate": 0.7900 }  ← forward-filled
  ]
}
```

### Scenario C: Backward-fill — first security date precedes any FX data

```
Security data:   2025-01-02 (open)
FX data:         earliest available = 2025-01-03: 0.7895

GET /securities/AAPL/history?from=2025-01-02&to=2025-01-03&currency=GBP
→ 200
{
  "ticker": "AAPL",
  "currency": "GBP",
  "prices": [
    { "date": "2025-01-02", "close": 145.88, "fx_rate": 0.7895 },  ← backward-filled
    { "date": "2025-01-03", "close": 146.22, "fx_rate": 0.7895 }
  ]
}
```

### Scenario D: No translation when currency matches native

```
GET /securities/BARC.L/history?from=2025-01-02&to=2025-01-03&currency=GBP
→ 200
{
  "ticker": "BARC.L",
  "currency": "GBP",
  "prices": [
    { "date": "2025-01-02", "close": 2.18, "fx_rate": null },
    { "date": "2025-01-03", "close": 2.20, "fx_rate": null }
  ]
}
```

---

## US3 — FX Pair History Endpoint

### Scenario A: Valid pair, cache miss (first fetch)

```
GET /fx/USDGBP/history?from=2025-01-02&to=2025-01-03
→ 200
{
  "pair": "USDGBP",
  "base_currency": "USD",
  "quote_currency": "GBP",
  "rates": [
    { "date": "2025-01-02", "rate": 0.7884 },
    { "date": "2025-01-03", "rate": 0.7902 }
  ]
}
```

### Scenario B: Cache hit (repeat request)

```
GET /fx/USDGBP/history?from=2025-01-02&to=2025-01-03
→ 200 (served from cache — no external call)
```

### Scenario C: Invalid currency code in pair

```
GET /fx/USDZZ/history?from=2025-01-02&to=2025-01-03
→ 422
{ "detail": "Invalid FX pair 'USDZZ': 'ZZ' is not a recognised ISO 4217 currency code.", "code": "INVALID_CURRENCY" }
```

### Scenario D: Reversed date range

```
GET /fx/USDGBP/history?from=2025-03-31&to=2025-01-02
→ 422
{ "detail": "'from' date (2025-03-31) must not be after 'to' date (2025-01-02).", "code": "INVALID_DATE_RANGE" }
```

---

## Key Test Fixtures

| Fixture | Description |
|---------|-------------|
| `mock_fx_provider` | `MagicMock(spec=PricingProvider)` pre-configured to return FX rate series |
| `client_with_cache` | Existing fixture; reused with `get_currency_service` override added |
| `tmp_cache_dir` | Existing fixture; FX CSVs stored alongside security CSVs |
| `seed_fx_cache(pair, rates)` | Helper: writes `{pair}.csv` to `tmp_cache_dir` |

## Dependency Injection Override Pattern

For BDD tests, override both `get_pricing_service` and `get_currency_service`:

```python
app.dependency_overrides[get_pricing_service] = lambda: PricingService(mock_security_provider)
app.dependency_overrides[get_currency_service] = lambda: CurrencyService(
    fx_provider=CachedPricingProvider(mock_fx_provider, CacheRepository(tmp_cache_dir)),
    aligner=FxAligner(),
)
```
