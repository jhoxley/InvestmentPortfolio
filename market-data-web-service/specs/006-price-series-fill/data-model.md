# Data Model: Price Series Gap Fill

**Branch**: `006-price-series-fill` | **Date**: 2026-05-17

---

## Overview

This feature introduces no new persistent storage. All entities are in-memory computational objects produced and consumed within the request lifecycle.

---

## Entities

### GapFillService

**File**: `app/services/gap_fill.py` (new)  
**Type**: Stateless service class

| Method | Signature | Description |
|--------|-----------|-------------|
| `fill` | `(observations: list[tuple[date, float]], from_date: date, to_date: date) -> list[tuple[date, float]]` | Returns a complete Mon–Fri series for the requested range. Returns `[]` if `observations` is empty. Applies back-fill before first observation, forward-fill through gaps and after last observation. |

**Invariants**:
- Output contains exactly the set of Mon–Fri dates in `[from_date, to_date]` that are business days.
- No date appears more than once in output.
- Output is sorted ascending by date.
- No output entry has a zero or negative price (inherited from the original observation).
- Weekend days (weekday ≥ 5) never appear in output.

---

### BusinessDaySeries (conceptual)

**Type**: `list[tuple[date, float]]`  
**Description**: The authoritative output of gap-fill processing. A contiguous, sorted sequence of `(date, price_or_rate)` pairs covering every Mon–Fri in the requested date range, with no gaps.

Applies to both:
- Security price series (price in native currency)
- FX rate series (exchange rate for the pair)

---

### MarketObservation (conceptual)

**Type**: `tuple[date, float]` element within `list[tuple[date, float]]`  
**Description**: A single `(date, price)` pair sourced directly from the data provider or cache for a specific trading day. The raw input to gap-fill for security price series.

---

### FXRateObservation (conceptual)

**Type**: `tuple[date, float]` element within `list[tuple[date, float]]`  
**Description**: A single `(date, rate)` pair sourced directly from the data provider or cache for a specific trading day. The raw input to gap-fill for FX rate series.

---

## Modified Service Interfaces

### PricingService (modified)

**File**: `app/services/pricing_service.py`

```
PricingService
  __init__(provider: PricingProvider, gap_fill: GapFillService)
  get_price_history(ticker, from_date, to_date) -> PriceHistoryResponse
    │
    ├── calls provider.get_price_history() → raw list[tuple[date, float]]
    ├── calls gap_fill.fill(raw, resolved_from, resolved_to) → filled list
    └── builds PriceHistoryResponse from filled list
```

**Change**: `GapFillService` added as constructor parameter; `get_price_history()` applies gap-fill between provider call and response construction.

---

### CurrencyService (modified)

**File**: `app/services/currency_service.py`

```
CurrencyService
  __init__(fx_provider: PricingProvider, aligner: FxAligner, gap_fill: GapFillService)
  translate_history(ticker, records, native_currency, target_currency, from_date, to_date)
    │
    ├── calls _fx_provider.get_price_history() → raw FX list
    ├── calls gap_fill.fill(raw_fx, from_date, to_date) → filled FX list  ← NEW
    ├── calls aligner.align_rates(pair, security_dates, filled_fx)
    └── applies rates to each PricePoint
```

**Change**: `GapFillService` added as constructor parameter; raw FX series gap-filled before `align_rates()` call.

---

### FX Router (modified)

**File**: `app/api/fx.py`

```
GET /fx/{pair}/history
  │
  ├── fx_provider.get_price_history() → raw list[tuple[date, float]]
  ├── gap_fill.fill(raw, resolved_from, resolved_to) → filled list  ← NEW
  └── FxHistoryResponse(rates=[FxRateEntry(d, r) for d, r in filled])
```

**Change**: `GapFillService` injected via `Depends(get_gap_fill_service)`; applied after provider call.

---

## Data Flow Diagram

```
Client Request
      │
      ▼
GET /securities/{ticker}/history
      │
      ├── PricingService.get_price_history()
      │       ├── CachedPricingProvider.get_price_history()   [raw obs only]
      │       ├── GapFillService.fill()                       [← NEW: Mon-Fri grid]
      │       └── PriceHistoryResponse(prices=filled)
      │
      └── [if currency conversion]
              CurrencyService.build_translated_history()
                  ├── _fx_provider.get_price_history()        [raw FX obs only]
                  ├── GapFillService.fill()                   [← NEW: Mon-Fri FX grid]
                  ├── FxAligner.align_rates()                 [now always exact match]
                  └── PriceHistoryResponse(prices=translated)

GET /fx/{pair}/history
      ├── CachedPricingProvider.get_price_history()           [raw obs only]
      ├── GapFillService.fill()                               [← NEW: Mon-Fri grid]
      └── FxHistoryResponse(rates=filled)
```

---

## Response Model Changes

No response model changes. `PriceHistoryResponse`, `FxHistoryResponse`, `PricePoint`, and `FxRateEntry` are unchanged. The gap-fill guarantee is a behavioral contract, not a schema change.

---

## Test Fixture Changes

| Fixture | Change Required |
|---------|----------------|
| `client_with_cache` | Add `gap_fill=GapFillService()` to `PricingService()` constructor call |
| `client_with_fx` | Add `gap_fill=GapFillService()` to both `PricingService()` and `CurrencyService()` constructor calls |
| `client_with_gap_fill` (new) | Wire mock providers + real `GapFillService()` for gap-fill BDD scenarios |
