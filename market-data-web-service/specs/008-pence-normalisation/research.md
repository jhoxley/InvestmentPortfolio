# Research: Pence Unit Normalisation

**Feature**: 008-pence-normalisation  
**Date**: 2026-05-26

---

## Decision 1: Where to apply normalisation in the call chain

**Decision**: Apply normalisation inside `PricingService`, after receiving raw data from the provider chain and before constructing `PriceResponse` / `PriceHistoryResponse`.

**Rationale**:
- The provider contract (`PricingProvider`) returns raw tuples `(date, float)` for history — there is no currency metadata attached to each tuple. Currency is only available via `get_current_price()`. A provider-level decorator would therefore need to call `get_current_price()` a second time to discover the currency, doubling network/cache traffic.
- `PricingService` already calls `get_current_price()` as part of building `PriceHistoryResponse` (to populate the `currency` field). Reusing that result for normalisation avoids the double-call problem.
- Placing normalisation at the service layer keeps the provider abstraction focused solely on data retrieval. Normalisation is a business-rule concern, not a transport concern.

**Alternatives considered**:
- *Provider-level decorator (`NormalisingPricingProvider`)*: Clean OCP pattern, but requires a redundant `get_current_price()` call for history normalisation and introduces state (currency caching) or inefficiency.
- *API layer (`securities.py`)*: Too late — FX translation in `currency_service` uses `response.currency` to build the FX pair string. If normalisation hasn't happened yet, the pair would be `GBpUSD` (invalid).
- *YFinance provider directly*: Tightly couples a business rule to a specific data source; violates abstraction.

---

## Decision 2: Architecture — SubUnitNormaliser injected into PricingService

**Decision**: Create a new `SubUnitNormaliser` class in `app/services/minor_unit.py`, injected into `PricingService` as a constructor dependency (alongside the existing `GapFillService`).

**Rationale**:
- Satisfies SRP: `SubUnitNormaliser` owns only the "is this a minor-unit currency, and what is the conversion factor?" concern.
- Satisfies DI: `PricingService` receives it as an abstraction; tests can substitute a no-op normaliser.
- Satisfies OCP: all logic lives in the new class; `PricingService` gains only two call sites (one in `get_current_price`, one in `get_price_history`). No existing stable logic is deleted or restructured.
- Consistent with how `GapFillService` was previously introduced.

**Alternatives considered**:
- *Module-level functions only (no class)*: Simpler, but not injectable or mockable as a unit in tests.
- *Inline dict lookup in PricingService*: Violates SRP; hard-codes business data inside the orchestrator.

---

## Decision 3: Sub-unit map and case-insensitive matching

**Decision**: Store mappings in a module-level dict keyed by the exact mixed-case codes used by yfinance (`"GBp"`, `"USd"`). Perform lookup with a case-fold on the trailing character only: the first two characters must be uppercase ASCII letters (the ISO 4217 base), and the third character is the minor-unit indicator (lowercase for yfinance sub-units). Implement lookup by normalising the input to title-case of the third character before comparing.

In practice, since yfinance consistently returns `"GBp"` and `"USd"`, an exact-match dict lookup (with a `.lower()` normalisation step) is sufficient and explicit.

**Map (initial scope)**:

| Sub-unit code | Major code | Divisor |
|---------------|------------|---------|
| `GBp`         | `GBP`      | 100     |
| `USd`         | `USD`      | 100     |

**Rationale**: Exact enumeration of known codes is safe and auditable. A pattern-match approach (e.g., "any three-letter code with lowercase third character") would silently normalise hypothetical future codes that might not be genuine sub-units.

**Alternatives considered**:
- *Pattern-based detection (lowercase 3rd char = minor unit)*: Fragile; future ISO currency codes could inadvertently match.
- *External configuration file*: Over-engineered for two known codes; adds deployment complexity.

---

## Decision 4: Cache stores raw sub-unit values; normalisation at response time

**Decision**: The cache layer (`CachedPricingProvider`) is untouched. It stores whatever the upstream provider returns — pence values for GBp-denominated securities. Normalisation is applied in `PricingService` after reading from the cache (or provider).

**Rationale**:
- No cache invalidation required. Existing cached data remains valid.
- Changing cache-write behaviour would require purging all existing cached entries for affected tickers on deployment.
- Normalisation at read time is idempotent with respect to the cache.

**Alternatives considered**:
- *Normalise before writing to cache*: Would require cache purge on deployment; complicates `CachedPricingProvider` (it would need to know about currency codes). Rejected.

---

## Decision 5: FX ordering is automatic with service-layer normalisation

**Decision**: No explicit ordering logic is needed in the API layer. Because normalisation occurs inside `PricingService.get_price_history()` before returning `PriceHistoryResponse`, the `response.currency` field is already `"GBP"` when control reaches the FX conversion check in `securities.py`. The FX pair string (`"GBPUSD"`) is therefore correct without any additional plumbing.

**Rationale**: The existing API layer logic is unchanged; the correct ordering is a free consequence of where normalisation sits.

---

## Decision 6: No OpenAPI schema changes; add behavior description

**Decision**: The existing `PriceResponse` and `PriceHistoryResponse` schemas are unchanged (both already have `currency: str` and `price/close: float`). A description clause is added to the relevant endpoint and schema fields documenting that prices in sub-unit currencies (GBp, USd) are automatically normalised to the major unit.

**Rationale**: The API surface is the same; only the values that appear in existing fields change. A description update keeps the contract accurate without breaking any consumer.
