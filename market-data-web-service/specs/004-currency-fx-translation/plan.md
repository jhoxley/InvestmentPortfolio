# Implementation Plan: Currency Translation & FX Pair Endpoint

**Branch**: `004-currency-fx-translation` | **Date**: 2026-05-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/004-currency-fx-translation/spec.md`

## Summary

Add optional `currency` query parameter to the existing current-price and historical-price endpoints to translate returned prices from the security's native currency to any requested ISO 4217 target currency. FX rates are fetched from the same data source as security prices and stored in the existing file-based cache. A new `GET /fx/{pair}/history` endpoint exposes raw FX rate time series for diagnostic and cash-analysis use cases. Calendar alignment between security and FX market trading days is handled by a forward-fill (then backward-fill) strategy using stdlib `bisect`. All FX pairs are treated as directionally independent (no auto-inversion).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.115.x, Pydantic 2.x, structlog ≥24.0, yfinance 0.2.x, pyyaml ≥6.0 (all existing — no new production dependencies)
**Storage**: File-based CSV cache (existing `CacheRepository`); FX data stored as `{pair}.csv` alongside security price files
**Testing**: pytest 8.x, pytest-bdd 8.x (existing), ruff, mypy strict (existing)
**Target Platform**: Local Windows/Linux server (same as existing service)
**Project Type**: Web service (FastAPI REST API)
**Performance Goals**: Same as existing service; FX fetch + alignment adds negligible overhead on cache hit
**Constraints**: No new production dependencies; reuse existing caching and provider infrastructure unchanged
**Scale/Scope**: Same as existing service (single-user local deployment)

## Constitution Check

| Principle | Check | Notes |
|-----------|-------|-------|
| I. SOLID Design | ✅ | `FxInnerProvider` (ticker translation), `CurrencyService` (translation logic), `FxAligner` (alignment) each have single responsibility; no existing classes modified |
| II. Standard Dependencies | ✅ | No new production deps; `bisect` (stdlib) for alignment; static frozenset for ISO 4217 validation |
| III. BDD Test-First | ✅ | `.feature` files for US1/US2/US3 written and confirmed failing before implementation begins |
| IV. Code Quality Standards | ✅ | Same ruff + mypy strict config; all new modules fully type-annotated |
| V. Observability & Logging | ✅ | Structured log events: `fx_fetch`, `fx_cache_hit`, `fx_align_fill`, `currency_translation`, `fx_align_error` |
| VI. OpenAPI-First | ✅ | `contracts/openapi-additions.yaml` written; merged into `openapi.yaml` before any endpoint implementation |

## Project Structure

### Documentation (this feature)

```text
specs/004-currency-fx-translation/
├── plan.md                         # This file
├── research.md                     # Phase 0 decisions
├── data-model.md                   # Entity definitions and relationships
├── quickstart.md                   # Integration scenarios and test fixtures
├── contracts/
│   └── openapi-additions.yaml      # New endpoint + updated schema contracts
└── tasks.md                        # /speckit-tasks output (not yet generated)
```

### Source Code Changes

```text
app/
├── api/
│   ├── cache.py                    (unchanged)
│   ├── fx.py                       (NEW — GET /fx/{pair}/history endpoint)
│   └── securities.py               (updated — add optional currency param to both endpoints)
├── cache/
│   ├── __init__.py                 (unchanged)
│   └── repository.py               (unchanged)
├── config.py                       (unchanged)
├── exceptions.py                   (updated — add FxAlignmentError, CurrencyUnavailableError)
├── logging_config.py               (unchanged)
├── main.py                         (updated — include fx router; register new exception handlers)
├── models/
│   └── pricing.py                  (updated — add FxRateEntry, FxHistoryResponse;
│                                              add fx_rate field to PricePoint, PriceResponse)
├── providers/
│   ├── __init__.py                 (unchanged)
│   ├── cached_provider.py          (unchanged)
│   ├── fx_provider.py              (NEW — FxInnerProvider: maps pair → pair=X for yfinance)
│   └── yfinance_provider.py        (unchanged)
├── services/
│   ├── currency_service.py         (NEW — CurrencyService: orchestrates translation)
│   ├── fx_aligner.py               (NEW — FxAligner: bisect-based forward/backward fill)
│   └── pricing_service.py          (unchanged)
└── validators/
    ├── __init__.py                  (NEW)
    └── currency.py                  (NEW — ISO 4217 frozenset + validate_currency_code())

tests/
├── conftest.py                     (updated — add mock_fx_provider, client_with_fx fixtures)
├── features/
│   ├── currency_translation_current.feature   (NEW — US1 scenarios)
│   ├── currency_translation_history.feature   (NEW — US2 scenarios)
│   └── fx_history.feature                     (NEW — US3 scenarios)
└── steps/
    ├── currency_translation_current_steps.py  (NEW — US1 step definitions)
    ├── currency_translation_history_steps.py  (NEW — US2 step definitions)
    └── fx_history_steps.py                    (NEW — US3 step definitions)
```

## Implementation Notes

### FxInnerProvider (`app/providers/fx_provider.py`)

```python
class FxInnerProvider(PricingProvider):
    """Translates pair codes (e.g., USDGBP) to yfinance FX tickers (USDGBP=X)."""
    def __init__(self, inner: PricingProvider) -> None:
        self._inner = inner

    def get_current_price(self, ticker: str) -> dict[str, object]:
        raise NotImplementedError("FxInnerProvider does not support current price")

    def get_price_history(self, pair: str, from_date: date, to_date: date) -> list[tuple[date, float]]:
        fx_ticker = f"{pair}=X"
        return self._inner.get_price_history(fx_ticker, from_date, to_date)
```

Usage: `CachedPricingProvider(FxInnerProvider(YFinanceProvider()), repo)`

### FxAligner (`app/services/fx_aligner.py`)

```python
class FxAligner:
    def align_rates(
        self,
        security_dates: list[date],
        fx_series: list[tuple[date, float]],
    ) -> dict[date, float]:
        """Map each security date to the nearest applicable FX rate.
        Forward-fill first; backward-fill if no prior rate exists.
        Raises FxAlignmentError if neither is possible.
        """
        fx_map = dict(fx_series)
        sorted_fx_dates = sorted(fx_map.keys())
        result: dict[date, float] = {}
        for sec_date in security_dates:
            idx = bisect_right(sorted_fx_dates, sec_date) - 1
            if idx >= 0:
                result[sec_date] = fx_map[sorted_fx_dates[idx]]  # forward-fill
                continue
            idx = bisect_left(sorted_fx_dates, sec_date)
            if idx < len(sorted_fx_dates):
                result[sec_date] = fx_map[sorted_fx_dates[idx]]  # backward-fill
                continue
            raise FxAlignmentError(...)
        return result
```

### CurrencyService (`app/services/currency_service.py`)

Responsibilities:
- Determine if translation is needed (`native_currency != target_currency`)
- Fetch native currency via `security_provider.get_current_price(ticker)["currency"]`
- Fetch FX time series via `fx_provider.get_price_history(pair, from_date, to_date)` 
- Delegate alignment to `FxAligner.align_rates()`
- Apply aligned rates to price records and return enriched structures
- Structured log events: `currency_translation`, `fx_align_fill`, `fx_align_error`

### Securities API Changes (`app/api/securities.py`)

Add `currency: str | None = Query(default=None)` to both endpoint signatures. Validate the code via `validate_currency_code()` before calling the service. Inject `CurrencyService` via `Depends(get_currency_service)`.

Pattern:
```python
@router.get("/{ticker}/price", response_model=PriceResponse)
async def get_current_price(
    ticker: str = Path(...),
    currency: str | None = Query(default=None),
    service: PricingService = Depends(get_pricing_service),
    currency_svc: CurrencyService | None = Depends(get_currency_service_optional),
) -> PriceResponse:
    if currency:
        validate_currency_code(currency)  # raises InvalidTickerError → 422 if invalid
    response = service.get_current_price(ticker)
    if currency and currency != response.currency and currency_svc:
        response = currency_svc.translate_current(ticker, response, currency)
    return response
```

### FX Endpoint (`app/api/fx.py`)

```python
_PAIR_PATTERN = r"^[A-Za-z]{6}$"

@router.get("/{pair}/history", response_model=FxHistoryResponse)
async def get_fx_history(
    pair: str = Path(..., min_length=6, max_length=6, pattern=_PAIR_PATTERN),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    settings: Settings = Depends(get_settings),
) -> FxHistoryResponse:
    base = pair[:3].upper()
    quote = pair[3:].upper()
    validate_currency_code(base)  # → 422 if invalid
    validate_currency_code(quote)  # → 422 if invalid
    if base == quote:
        raise InvalidCurrencyPairError(pair)
    ...
```

### ISO 4217 Validator (`app/validators/currency.py`)

```python
_ISO_4217_CODES: frozenset[str] = frozenset({
    "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN",
    "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL",
    "BSD", "BTN", "BWP", "BYN", "BZD", "CAD", "CDF", "CHF", "CLP", "CNY",
    "COP", "CRC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD", "EGP",
    "ERN", "ETB", "EUR", "FJD", "FKP", "GBP", "GEL", "GHS", "GIP", "GMD",
    "GNF", "GTQ", "GYD", "HKD", "HNL", "HRK", "HTG", "HUF", "IDR", "ILS",
    "INR", "IQD", "IRR", "ISK", "JMD", "JOD", "JPY", "KES", "KGS", "KHR",
    "KMF", "KPW", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD",
    "LSL", "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", "MRU",
    "MUR", "MVR", "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK",
    "NPR", "NZD", "OMR", "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG",
    "QAR", "RON", "RSD", "RUB", "RWF", "SAR", "SBD", "SCR", "SDG", "SEK",
    "SGD", "SHP", "SLE", "SLL", "SOS", "SRD", "STN", "SVC", "SYP", "SZL",
    "THB", "TJS", "TMT", "TND", "TOP", "TRY", "TTD", "TVD", "TWD", "TZS",
    "UAH", "UGX", "USD", "UYU", "UZS", "VES", "VND", "VUV", "WST", "XAF",
    "XCD", "XOF", "XPF", "YER", "ZAR", "ZMW", "ZWL",
})

def validate_currency_code(code: str) -> None:
    """Raise InvalidCurrencyError if code is not a recognised ISO 4217 code."""
    if code.upper() not in _ISO_4217_CODES:
        raise InvalidCurrencyError(code)
```

### New Exception Types

```python
class FxAlignmentError(Exception):
    def __init__(self, pair: str, security_date: date, message: str | None = None) -> None: ...
    # HTTP 404

class CurrencyUnavailableError(Exception):
    def __init__(self, ticker: str, message: str | None = None) -> None: ...
    # HTTP 404

class InvalidCurrencyError(Exception):
    def __init__(self, code: str, message: str | None = None) -> None: ...
    # HTTP 422

class InvalidCurrencyPairError(Exception):
    def __init__(self, pair: str, message: str | None = None) -> None: ...
    # HTTP 422
```

### Structured Log Events

| Event | Level | Fields |
|-------|-------|--------|
| `fx_fetch` | INFO | pair, from_date, to_date, source (cache/provider) |
| `fx_cache_hit` | INFO | pair, from_date, to_date |
| `fx_align_fill` | INFO | pair, security_date, fx_date_used, fill_direction (forward/backward) |
| `fx_align_error` | ERROR | pair, security_date, error |
| `currency_translation` | INFO | ticker, native_currency, target_currency, rate_applied (current price) |
| `fx_align_no_translation` | INFO | ticker, currency (when native == target) |

## Complexity Tracking

No constitution violations. All new components follow SOLID, use stdlib only, and are independently testable.

## Phase Summary

| Phase | Tasks | Deliverable |
|-------|-------|-------------|
| Setup | Update openapi.yaml, add new exceptions | Contract-first foundation |
| Foundational | Validators, FxInnerProvider, FxAligner, CurrencyService, model updates | Core infrastructure |
| US1 (P1) | BDD + current price translation endpoint | Translated current price |
| US2 (P2) | BDD + historical translation + alignment | Translated history with per-entry fx_rate |
| US3 (P3) | BDD + FX history endpoint | Dedicated FX endpoint |
| Polish | ruff, mypy, full pytest suite | Quality gate |
