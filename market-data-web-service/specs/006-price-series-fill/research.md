# Research: Price Series Gap Fill

**Branch**: `006-price-series-fill` | **Date**: 2026-05-17

---

## Decision 1: Gap-Fill Algorithm Implementation

**Decision**: Implement gap-fill as a single-pass linear scan over the Mon–Fri business day grid using Python stdlib `datetime` only.

**Algorithm**:
1. Build a `dict[date, float]` lookup from raw observations.
2. Record the price from the earliest observation (for back-fill).
3. Walk the business day grid (`current.weekday() < 5`) from `from_date` to `to_date`:
   - If `current` has an observation → use it; update `last_known_price`.
   - If `current` precedes the first observation (`last_known_price` is `None`) → back-fill with first observation price.
   - Otherwise → forward-fill with `last_known_price`.
4. Return the result list.

**Rationale**: The single-pass design is O(n) in the number of business days, simple to test, and has no external dependencies. Alternatives like pandas `resample()`/`ffill()` were considered but pandas is not in the project's dependency set — introducing it solely for gap-fill would violate Constitution Principle II (prefer stdlib where an established approach exists).

**Alternatives considered**:
- *pandas `ffill()` after `reindex()`*: Elegant but adds a heavy dependency not currently in the project.
- *Two-pass algorithm (back-fill, then forward-fill)*: Equivalent correctness; single-pass is marginally cleaner.
- *Recursive fill*: No advantage; iterative is more readable.

---

## Decision 2: Insertion Point — Security Price History

**Decision**: Apply gap-fill inside `PricingService.get_price_history()`, after the raw `list[tuple[date, float]]` is returned from the provider and before `PriceHistoryResponse` is constructed.

**Rationale**: The service layer is the correct boundary — it knows the requested `from_date`/`to_date`, owns the business logic, and sits above the caching/provider layer. Inserting gap-fill here satisfies FR-005 (gap-fill before FX conversion) because `CurrencyService` is called after `PricingService` returns its response.

**Alternatives considered**:
- *Inside `CachedPricingProvider`*: Provider should not have business logic — its concern is fetch-and-cache, not series completeness.
- *Decorator `GapFillingPricingProvider`*: Would require changing the `PricingProvider` return type or adding a new interface method, unnecessary complexity.
- *Inside `securities.py` endpoint*: Thin router should not perform business logic.

---

## Decision 3: Insertion Point — FX Rate Series (Public Endpoint)

**Decision**: Apply gap-fill in `fx.py` after `fx_provider.get_price_history()` returns raw records and before building `FxHistoryResponse`. Inject `GapFillService` as a FastAPI dependency.

**Rationale**: The FX router currently constructs the response directly (no dedicated `FxService`). Adding a `get_gap_fill_service` dependency matches the existing thin-router pattern and avoids introducing a new service class whose only job would be wrapping a function call.

**Alternatives considered**:
- *Create `FxService`*: Overengineered for a feature that changes two lines in the router; would require new DI wiring with no other benefit.
- *Inject `GapFillService` into `CachedPricingProvider`*: Violates separation of concerns (provider = fetch/cache only).

---

## Decision 4: Insertion Point — FX Rates for Internal Currency Conversion

**Decision**: Apply gap-fill in `CurrencyService.translate_history()` after the raw FX series is fetched and before it is passed to `FxAligner.align_rates()`.

**Rationale**: This satisfies FR-010: gap-filled FX rates prevent missing rates from producing artificial spikes in the converted price series. After gap-fill, every security date will find an exact match in the FX map — `FxAligner` degrades gracefully to returning `"exact"` matches throughout, and the existing code path is preserved.

**Alternatives considered**:
- *Remove `FxAligner` after gap-fill*: `FxAligner` provides the fallback for cases where the security date grid and FX grid don't perfectly overlap due to different holiday calendars. Retaining it as a last-resort fallback is prudent even after gap-fill.
- *Gap-fill inside `FxAligner`*: `FxAligner`'s single responsibility is date alignment, not series completeness.

---

## Decision 5: Dependency Injection Strategy for `GapFillService`

**Decision**: `GapFillService` is a lightweight, stateless class injected via constructor DI into `PricingService` and `CurrencyService`, and via FastAPI's `Depends()` into the FX endpoint.

**Rationale**: Constitution Principle I (Dependency Inversion) requires dependencies to be injected. `GapFillService` has no external I/O or state; it is the fill-algorithm owner and its interface could be extended (e.g., with a holiday calendar) without modifying callers.

**Impact on existing fixtures**: `client_with_cache` and `client_with_fx` in `tests/conftest.py` construct `PricingService` and `CurrencyService` directly. These fixtures must be updated to pass `GapFillService()` when those service constructors are modified. Existing BDD tests are unaffected beyond the conftest.py update.

---

## Decision 6: Empty Series Handling

**Decision**: `GapFillService.fill()` returns `[]` for empty input. The caller (`PricingService`) raises `DataNotFoundError` when the provider returns no observations — this existing behaviour is unchanged. Gap-fill is not called for empty series.

**Rationale**: FR-008 ("no observations → 404") is already satisfied by the provider raising `DataNotFoundError` before gap-fill is ever invoked. Gap-fill returning `[]` for empty input is a safe no-op fallback, not the primary enforcement mechanism.

---

## Decision 7: Logging Strategy

**Decision**: Log a single `INFO` entry per gap-fill operation with fields: `ticker_or_pair`, `from_date`, `to_date`, `raw_observations`, `filled_count`, `gaps_filled`.

**Rationale**: Operators need to see gap-fill activity for debugging data quality issues, but per-entry logging would be prohibitively verbose for long date ranges.

---

## Decision 8: OpenAPI Contract

**Decision**: No new endpoints or schema changes. Update description fields on `GET /securities/{ticker}/history` and `GET /fx/{pair}/history` to document the gap-fill guarantee.

**Rationale**: The response schema is unchanged (same `PriceHistoryResponse` and `FxHistoryResponse`). Only the completeness guarantee changes. Description-only updates are not breaking changes and do not require a version bump.

---

## Decision 9: BDD Test Feature Files

**Decision**: Three feature files:

| File | Covers |
|------|--------|
| `tests/features/price_gap_fill.feature` | US1 (forward-fill mid-range + end-of-range), US2 (back-fill), US3 (fill to today) |
| `tests/features/fx_gap_fill.feature` | FR-009: same fill logic on `/fx/{pair}/history` |
| `tests/features/gap_fill_fx_conversion.feature` | FR-010 + SC-005: gap-filled FX rates used in currency conversion — no spikes |

**Test fixture strategy**: Reuse the existing `mock_inner_provider` + `mock_fx_provider` pattern from `client_with_fx`. New `client_with_gap_fill` fixture wires real `GapFillService` into `PricingService` and `CurrencyService` with mocked raw providers returning controlled data with intentional gaps.
