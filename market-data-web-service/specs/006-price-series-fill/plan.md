# Implementation Plan: Price Series Gap Fill

**Branch**: `006-price-series-fill` | **Date**: 2026-05-17 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/006-price-series-fill/spec.md`

## Summary

Post-process all security and FX price history responses to guarantee a complete Mon–Fri business day series for the requested date range. Missing trading days (market holidays, data outages, stale source data) are filled by forward-carry of the most recent prior observation, with backward-carry applied when the first available observation follows the requested start date. Gap-fill runs on raw data before FX conversion; both the security price series and the FX rate series used for currency conversion are gap-filled. No new API endpoints, no schema changes — this is a pure behavioural enhancement to existing history endpoints.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI 0.115.x, pydantic 2.x, structlog 24.x, yfinance 0.2.x, pytest 8.x, pytest-bdd 7.x, ruff, mypy — all existing, no new packages  
**Storage**: None — gap-fill is a stateless in-memory post-processing step  
**Testing**: pytest + pytest-bdd (Gherkin `.feature` files); ruff + mypy in strict mode  
**Target Platform**: Linux/Windows local server (existing FastAPI application)  
**Project Type**: web-service (extending existing FastAPI application)  
**Performance Goals**: No new SLA; gap-fill is O(n) in business days — negligible overhead for typical 30–365 day ranges  
**Constraints**: No new external services; pure Python stdlib `datetime` for business day generation; no pandas or other new dependencies  
**Scale/Scope**: Low-volume local deployment; no caching or rate-limit concerns

## Constitution Check

| Principle | Check | Notes |
|-----------|-------|-------|
| I. SOLID Design | ✓ Pass | `GapFillService` has single responsibility (fill algorithm). Injected into `PricingService` and `CurrencyService` constructors; injected into `fx.py` via `Depends()`. No modifications to existing providers (`CachedPricingProvider`, `YFinanceProvider`, `FxAligner`). |
| II. Standard Dependencies | ✓ Pass | Only Python stdlib `datetime` needed for Mon–Fri grid generation. No new packages. |
| III. BDD Test-First | ✓ Pass | Three `.feature` files authored and confirmed failing before any implementation tasks begin. |
| IV. Code Quality Standards | ✓ Pass | Existing `ruff` and `mypy --strict` config applies unchanged to all new and modified modules. |
| V. Observability & Logging | ✓ Pass | `structlog` INFO entries per gap-fill call: `ticker_or_pair`, `from_date`, `to_date`, `raw_observations`, `filled_count`, `gaps_filled`. |
| VI. OpenAPI-First | ✓ Pass | No new endpoints. Description fields on existing `/securities/{ticker}/history` and `/fx/{pair}/history` paths updated in `openapi.yaml` before implementation begins. |

No constitution violations — Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/006-price-series-fill/
├── plan.md                          # This file
├── research.md                      # Phase 0 output
├── data-model.md                    # Phase 1 output
├── quickstart.md                    # Phase 1 output
├── contracts/
│   └── gap_fill_behavior.md         # Phase 1 output
├── checklists/
│   └── requirements.md              # Spec quality checklist
└── tasks.md                         # Phase 2 output (/speckit-tasks)
```

### Source Code

```text
app/
├── services/
│   ├── gap_fill.py                  # NEW: GapFillService (fill algorithm)
│   ├── pricing_service.py           # MODIFIED: inject GapFillService; apply fill after raw fetch
│   ├── currency_service.py          # MODIFIED: inject GapFillService; fill FX series before align
│   └── fx_aligner.py                # UNCHANGED
├── api/
│   ├── fx.py                        # MODIFIED: inject GapFillService; fill before FxHistoryResponse
│   └── securities.py                # MODIFIED: factory fns add GapFillService() to constructors
├── providers/                       # UNCHANGED (all providers)
├── models/
│   └── pricing.py                   # UNCHANGED (no schema changes)
├── validators/                      # UNCHANGED
├── exceptions.py                    # UNCHANGED
└── main.py                          # UNCHANGED

tests/
├── features/
│   ├── price_gap_fill.feature       # NEW: US1, US2, US3 scenarios
│   ├── fx_gap_fill.feature          # NEW: FR-009 (FX history gap-fill)
│   └── gap_fill_fx_conversion.feature  # NEW: FR-010, SC-005 (no spikes in converted prices)
├── steps/
│   ├── price_gap_fill_steps.py      # NEW
│   ├── fx_gap_fill_steps.py         # NEW
│   └── gap_fill_fx_conversion_steps.py  # NEW
└── conftest.py                      # MODIFIED: add GapFillService to existing fixtures;
                                     #           add client_with_gap_fill fixture

openapi.yaml                         # MODIFIED: description updates on history endpoints
```

## Key Implementation Details

### GapFillService Algorithm

```python
# app/services/gap_fill.py
from datetime import date, timedelta

class GapFillService:
    def fill(
        self,
        observations: list[tuple[date, float]],
        from_date: date,
        to_date: date,
    ) -> list[tuple[date, float]]:
        if not observations:
            return []
        obs_map = dict(observations)
        first_obs_price = min(observations, key=lambda x: x[0])[1]
        result: list[tuple[date, float]] = []
        last_price: float | None = None
        current = from_date
        while current <= to_date:
            if current.weekday() < 5:          # Mon–Fri only
                if current in obs_map:
                    last_price = obs_map[current]
                    result.append((current, last_price))
                elif last_price is None:       # before first observation → back-fill
                    result.append((current, first_obs_price))
                else:                          # after last observation or mid-gap → forward-fill
                    result.append((current, last_price))
            current += timedelta(days=1)
        return result
```

### PricingService Change

In `get_price_history()`, after the provider call:
```python
raw = self._provider.get_price_history(ticker, resolved_from, resolved_to)
filled = self._gap_fill.fill(raw, resolved_from, resolved_to)
prices = [PricePoint(date=d, close=v) for d, v in filled]
```

### CurrencyService Change

In `translate_history()`, after fetching raw FX series:
```python
fx_series = self._fx_provider.get_price_history(pair, from_date, to_date)
filled_fx = self._gap_fill.fill(fx_series, from_date, to_date)
aligned = self._aligner.align_rates(pair, security_dates, filled_fx)
```

### FX Endpoint Change

In `get_fx_history()`, after provider call:
```python
records = fx_provider.get_price_history(pair_upper, resolved_from, resolved_to)
filled = gap_fill.fill(records, resolved_from, resolved_to)
return FxHistoryResponse(
    pair=pair_upper,
    base_currency=base,
    quote_currency=quote,
    rates=[FxRateEntry(date=d, rate=r) for d, r in filled],
)
```

### Conftest Changes

`client_with_cache` — update `override_service()`:
```python
from app.services.gap_fill import GapFillService
return PricingService(provider=provider, gap_fill=GapFillService())
```

`client_with_fx` — update `override_service()` and `override_currency_service()`:
```python
return PricingService(provider=provider, gap_fill=GapFillService())
return CurrencyService(fx_provider=fx_prov, aligner=FxAligner(), gap_fill=GapFillService())
```

New `client_with_gap_fill` fixture — mocks raw providers returning data with intentional gaps; wires real `GapFillService` for all gap-fill BDD scenarios.

## BDD Test Strategy

### price_gap_fill.feature scenarios

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Mid-series forward-fill | Provider returns prices for 2025-01-02 and 2025-01-06 only | GET history 2025-01-02 to 2025-01-06 | 3 entries; 2025-01-03 carries 2025-01-02 price |
| Multi-gap forward-fill | Provider returns prices for 2025-01-02 and 2025-01-07 only | GET history 2025-01-02 to 2025-01-07 | 4 entries; 2025-01-03 and 2025-01-06 carry 2025-01-02 price |
| End-of-range forward-fill | Provider returns prices up to 2025-01-03 | GET history 2025-01-02 to 2025-01-07 | 4 entries; 2025-01-06 and 2025-01-07 carry 2025-01-03 price |
| Back-fill from start | Provider has no price for 2025-01-02/03; first obs is 2025-01-06 | GET history 2025-01-02 to 2025-01-07 | 4 entries; 2025-01-02 and 2025-01-03 carry 2025-01-06 price |
| Fill to today (T-1 data) | Provider returns yesterday's price only | GET history ending today | Entry for today carries yesterday's price |
| Fill to today (T-2 data) | Provider returns T-2 price; no T-1 or today | GET history ending today | Entries for T-1 and today carry T-2 price |

### fx_gap_fill.feature scenarios

| Scenario | Given | When | Then |
|----------|-------|------|------|
| FX mid-series gap | FX provider returns rates for pair on 2025-01-02 and 2025-01-06 only | GET /fx/{pair}/history 2025-01-02 to 2025-01-06 | 3 rate entries; 2025-01-03 carries 2025-01-02 rate |

### gap_fill_fx_conversion.feature scenarios

| Scenario | Given | When | Then |
|----------|-------|------|------|
| No spikes from FX gap | Security prices complete Mon-Fri; FX rates missing 2025-01-03 | GET history with currency conversion 2025-01-02 to 2025-01-06 | Entry for 2025-01-03 uses gap-filled FX rate; no zero/spike |

## Complexity Tracking

> No constitution violations — this section is not required.
