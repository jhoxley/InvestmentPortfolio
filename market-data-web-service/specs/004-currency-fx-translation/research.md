# Research: Currency Translation & FX Pair Endpoint

## Decision 1: FX Pair Ticker Format for yfinance

**Decision**: FX pairs use the `{BASE}{QUOTE}=X` ticker format in yfinance (e.g., `USDGBP=X` returns the rate of 1 USD expressed in GBP). This convention is already referenced in the spec Assumptions and confirmed as yfinance's standard format for currency pairs.

**Rationale**: yfinance exposes currency pairs via Yahoo Finance's FX feed. The `=X` suffix is the standard Yahoo Finance convention for spot exchange rates. Removing it causes the ticker to be interpreted as a stock symbol.

**Cache key strategy**: The cache key for FX data will be the pair code without the suffix (e.g., `USDGBP`), not the full yfinance ticker (`USDGBP=X`). The `FxInnerProvider` translates `USDGBP` → `USDGBP=X` before delegating to `YFinanceProvider`. This keeps the `CacheRepository` ignorant of FX-specific ticker conventions and prevents filesystem ambiguity (no `=` in the filename).

**Alternatives considered**:
- Store under `USDGBP=X.csv` — rejected because `=` in filenames is unusual; `CacheRepository._filename()` currently does not sanitise `=`.
- Modify `CacheRepository` to strip `=X` — rejected because that couples the repository to FX-specific business logic.

---

## Decision 2: ISO 4217 Currency Code Validation

**Decision**: Use a hardcoded static `frozenset` of recognised 3-letter alphabetic ISO 4217 currency codes in `app/validators/currency.py`. No new runtime dependency is introduced.

**Rationale**: The spec requires "fixed list of recognised alphabetic codes." A static set is sufficient, requires zero new dependencies, and is the simplest correct implementation. The constitution mandates standard deps over bespoke utilities, but here the stdlib `frozenset` literal *is* the standard — no established library is needed for a static membership check.

**The set will include all actively traded ISO 4217 codes** (~170 codes including USD, GBP, EUR, JPY, CHF, AUD, CAD, HKD, SGD, NOK, SEK, DKK, NZD, MXN, ZAR, BRL, INR, CNY, KRW, and others). The list will be sourced from the ISO 4217 maintenance agency published table.

**Alternatives considered**:
- `pycountry` library — rejected; adds a non-trivial dependency (~10 MB) for a 170-element membership check. Constitution principle II: don't introduce dependencies for trivially solvable problems.
- Regex `^[A-Z]{3}$` only — rejected; would accept invalid codes like `ZZZ`.

---

## Decision 3: Calendar Alignment Algorithm (Forward/Backward Fill)

**Decision**: Use Python stdlib `bisect` module for O(log n) rate lookup. `FxAligner.align_rates(security_dates, fx_series)` returns a `dict[date, float]` mapping each security date to its applicable FX rate.

**Algorithm**:
```
sorted_fx_dates = sorted(fx_series.keys())
For each security_date in security_dates:
    # Forward-fill: find the latest fx_date <= security_date
    idx = bisect_right(sorted_fx_dates, security_date) - 1
    if idx >= 0:
        return fx_series[sorted_fx_dates[idx]]  # forward-fill hit
    # Backward-fill: find the earliest fx_date > security_date
    idx = bisect_left(sorted_fx_dates, security_date)
    if idx < len(sorted_fx_dates):
        return fx_series[sorted_fx_dates[idx]]  # backward-fill hit
    raise FxAlignmentError(...)
```

**Rationale**: Pure stdlib, no pandas/numpy dependency needed for this operation. Bisect gives correct forward-fill semantics in O(log n) per lookup.

**Alternatives considered**:
- `pandas.Series.reindex(fill_method='ffill')` — rejected; introduces pandas as a new dependency for a single utility. The existing codebase uses stdlib-only data structures for pricing records.
- Linear scan — rejected; O(n²) for large date ranges (e.g., 10 years of history).

---

## Decision 4: FxInnerProvider Architecture

**Decision**: Create `app/providers/fx_provider.py` containing `FxInnerProvider(PricingProvider)` — a thin adapter that translates a pair code (e.g., `USDGBP`) to its yfinance ticker (`USDGBP=X`) and delegates to an injected `YFinanceProvider`. This adapter is then wrapped by the existing `CachedPricingProvider` to add caching.

**Rationale**: The existing `CachedPricingProvider` is closed to modification (Open/Closed Principle). By creating a new inner provider that handles ticker translation, we compose the full FX pipeline as `CachedPricingProvider(FxInnerProvider(YFinanceProvider()), repo)`. No existing class is modified.

**Alternatives considered**:
- Modify `YFinanceProvider` to detect FX tickers — rejected; violates Single Responsibility (security + FX in one class).
- Modify `CachedPricingProvider` to handle FX ticker mapping — rejected; violates Open/Closed.
- Reuse `CachedPricingProvider(YFinanceProvider(), repo)` with `USDGBP=X` as the ticker passed from the caller — rejected; leaks the yfinance ticker convention into the service/API layer.

---

## Decision 5: Native Currency Resolution for History Endpoint

**Decision**: The `CurrencyService` calls `provider.get_current_price(ticker)` to obtain the native currency before fetching history. This reuses the already-implemented metadata lookup in `YFinanceProvider.get_current_price()` which reads `t.fast_info.currency`.

**Rationale**: `PricingService.get_price_history()` currently contains an inline `yf.Ticker(ticker)` call (pricing_service.py:44–51) to fetch the currency — a direct dependency violation. For the new feature, the `CurrencyService` will call the existing `provider.get_current_price()` (which goes through the cache provider's passthrough for `get_current_price`) to obtain the currency without duplicating the lookup logic.

The inline yfinance call in `PricingService.get_price_history()` will be preserved as-is for now (not in scope to fix in this feature). The `CurrencyService` path does not use it.

**Alternatives considered**:
- Add `get_currency(ticker) -> str` to `PricingProvider` interface — rejected; would require updating all existing implementations.
- Pass currency as an explicit parameter from the API layer — rejected; the API layer should not know how to resolve native currency.

---

## Decision 6: New Exceptions

**Decision**: Add two new exception types to `app/exceptions.py`:
- `FxAlignmentError(ticker, message)` — raised when no FX rate can be resolved for a security trading date (maps to HTTP 404 by the main exception handler).
- `CurrencyUnavailableError(currency, message)` — raised when the native currency of a security cannot be determined (maps to HTTP 404).

**Rationale**: Reusing `DataNotFoundError` for alignment failures would conflate two distinct failure modes. Separate exception types allow the main exception handler to map them independently if needed in future (currently both map to 404, consistent with FR-009).

---

## Decision 7: Response Model Changes

**Decision**: Extend existing Pydantic models minimally:
- `PricePoint` → add `fx_rate: float | None = None` (None when no translation applied; populated when translation used)
- `PriceResponse` → add `fx_rate: float | None = None` (the FX rate used for the current price translation, if any)
- New: `FxRateEntry(date, rate)` for the FX history response
- New: `FxHistoryResponse(pair, base_currency, quote_currency, rates)` for `GET /fx/{pair}/history`

**Rationale**: Adding `fx_rate` as an optional field on existing models preserves backward compatibility — existing consumers of `/securities/{ticker}/price` and `/securities/{ticker}/history` without the `currency` parameter receive `fx_rate: null` (or field omitted via `exclude_none`), which is non-breaking.

**Alternatives considered**:
- Separate `TranslatedPricePoint` and `TranslatedPriceHistoryResponse` models — rejected; doubles model count for the same wire format, complicates OpenAPI schema with union types.
- Envelope-style response wrapping — rejected; over-engineered for this change.
