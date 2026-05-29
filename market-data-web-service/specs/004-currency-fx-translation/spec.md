# Feature Specification: Currency Translation & FX Pair Endpoint

**Feature Branch**: `004-currency-fx-translation`
**Created**: 2026-05-10
**Status**: Draft
**Input**: User description: "support the ability to translate returned market data to a different base currency..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Currency Translation on Current Price (Priority: P1)

A consumer requests the current price of a security and optionally specifies a target currency (e.g., `?currency=EUR`). When the security is already priced in the requested currency, the price is returned as-is. When the security is priced in a different currency, the service converts the price using the most recent available FX rate between the native currency and the requested currency, then returns the converted price alongside the target currency code and the FX rate applied.

**Why this priority**: Currency translation on current price is the simplest, highest-value slice — consumers working with a multi-currency portfolio need prices in a single base currency without performing conversions themselves. Delivers immediate value with minimal FX complexity (single rate, no date-alignment).

**Independent Test**: Call the current price endpoint without a `currency` parameter and verify the native price is returned unchanged. Then call with `?currency=GBP` (or another currency) for a non-GBP security and verify the response contains a translated price, the target currency code, and the FX rate used.

**Acceptance Scenarios** *(MANDATORY — Gherkin format; these become `.feature` file scenarios)*:

```gherkin
Scenario: Current price returned in native currency when no target currency specified
  Given a valid ticker "AAPL" priced in USD
  When a consumer calls GET /securities/AAPL/price
  Then the response status code is 200
  And the response contains the price in USD
  And no currency translation is applied

Scenario: Current price translated to requested target currency
  Given a valid ticker "AAPL" priced in USD
  And the FX rate from USD to GBP is available
  When a consumer calls GET /securities/AAPL/price?currency=GBP
  Then the response status code is 200
  And the response contains the price converted to GBP
  And the response includes the FX rate applied and the target currency code

Scenario: No translation applied when requested currency matches native currency
  Given a valid ticker "BARC.L" priced in GBP
  When a consumer calls GET /securities/BARC.L/price?currency=GBP
  Then the response status code is 200
  And the response contains the original price unchanged
  And no FX fetch is performed

Scenario: Invalid currency code returns a validation error
  Given a valid ticker "AAPL"
  When a consumer calls GET /securities/AAPL/price?currency=INVALID
  Then the response status code is 422
  And the response body describes the validation error
```

---

### User Story 2 — Currency Translation on Historical Prices (Priority: P2)

A consumer requests a historical price series for a security with an optional `currency` parameter. When translation is required, the service fetches the corresponding FX pair time series for the same date range, aligns trading-day calendars between the security market and the FX market, applies forward-fill (and as a fallback backward-fill) to ensure every security trading date has an applicable FX rate, then returns the translated daily price series.

**Why this priority**: Historical translation is the core analytical capability — portfolio performance requires prices in a common base currency across the full date range. The calendar alignment logic (different market holidays between the security and FX markets) is the most complex part of this feature.

**Independent Test**: Seed mocked security price data and mocked FX time-series data (with deliberately different trading-day calendars). Call the history endpoint with a target currency and verify every date in the response has a translated price, that the FX rate applied is the nearest available rate (forward-fill first, then backward-fill), and that the translated values are arithmetically correct.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Historical prices translated across the full requested date range
  Given a cached price series for "AAPL" from "2025-01-02" to "2025-03-31" in USD
  And an FX time series for USDGBP is available for the same period
  When a consumer calls GET /securities/AAPL/history?from=2025-01-02&to=2025-03-31&currency=GBP
  Then the response status code is 200
  And every price entry contains a translated "close" and the "fx_rate" applied on that date
  And the response indicates the target currency is GBP

Scenario: FX rate forward-filled when FX market is closed on a security trading day
  Given a price entry exists for "AAPL" on "2025-01-20" (US market open)
  And no FX rate exists for "2025-01-20" (FX market closed — US holiday)
  And the most recent prior FX rate is from "2025-01-17"
  When a consumer calls GET /securities/AAPL/history?from=2025-01-17&to=2025-01-20&currency=GBP
  Then the response status code is 200
  And the price on "2025-01-20" is translated using the FX rate from "2025-01-17"
  And the "fx_rate" field on the "2025-01-20" entry equals the rate from "2025-01-17"

Scenario: FX rate backward-filled when no prior rate exists
  Given a price entry exists for "2025-01-02" with no prior FX rate available
  And the next available FX rate is from "2025-01-03"
  When a consumer calls GET /securities/AAPL/history?from=2025-01-02&to=2025-01-03&currency=GBP
  Then the response status code is 200
  And the price on "2025-01-02" is translated using the FX rate from "2025-01-03"
  And the "fx_rate" field on the "2025-01-02" entry equals the rate from "2025-01-03"

Scenario: No translation applied when native currency matches requested currency
  Given a cached price series for "BARC.L" in GBP
  When a consumer calls GET /securities/BARC.L/history?from=2025-01-02&to=2025-03-31&currency=GBP
  Then the response status code is 200
  And the prices are returned unchanged
  And no FX data is fetched
```

---

### User Story 3 — FX Pair History Endpoint (Priority: P3)

A consumer retrieves the raw historical FX exchange rate time series between two 3-letter ISO 4217 currency codes (e.g., `GET /fx/USDGBP/history?from=2025-01-01&to=2025-03-31`) for diagnostic purposes or cash-position analysis. The endpoint accepts a base currency and a quote currency, validates both codes are known ISO 4217 codes, fetches the time series via the same data source used for securities (with full caching applied), and returns the dated rate series.

**Why this priority**: The FX endpoint is valuable for diagnostics and explicit cash analysis, but it is not required for the core currency translation of securities data. It is safely delivered after the translation infrastructure is in place.

**Independent Test**: Call `GET /fx/{pair}/history` with valid ISO codes and date range; verify the response contains a dated list of FX rates. Call with an invalid currency code; verify 422. Verify that repeat calls for the same pair use the cache (mock the data source and assert call count on cache hit).

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: FX pair history returned for a valid currency pair and date range
  Given the FX time series for "USDGBP" is available from "2025-01-02" to "2025-03-31"
  When a consumer calls GET /fx/USDGBP/history?from=2025-01-02&to=2025-03-31
  Then the response status code is 200
  And the response contains a list of dated FX rates
  And each entry has a "date" in YYYY-MM-DD format and a numeric "rate" field
  And the entries are ordered chronologically ascending

Scenario: FX pair history served from cache on repeated request
  Given the FX time series for "USDGBP" is already cached
  When a consumer calls GET /fx/USDGBP/history?from=2025-01-02&to=2025-03-31
  Then the response status code is 200
  And no external data source call is made

Scenario: Invalid ISO currency code returns a validation error
  Given an unrecognised currency code "ZZZ"
  When a consumer calls GET /fx/USDZZ/history?from=2025-01-02&to=2025-03-31
  Then the response status code is 422
  And the response body describes the invalid currency code

Scenario: Start date after end date returns a validation error
  When a consumer calls GET /fx/USDGBP/history?from=2025-03-31&to=2025-01-02
  Then the response status code is 422
```

---

### Edge Cases

- What happens when FX data is completely unavailable for the entire requested date range? → Return an error for the entire request; no partial translated data is returned. The HTTP status code mirrors the underlying cause: 503 if the data source is unreachable, 404 if the FX pair or data does not exist for the period.
- What if the security's native currency cannot be determined from the data source? → Return a clear error indicating the currency is unknown; do not attempt translation.
- What if the requested target currency is not supported as a tradable FX pair by the data source? → Return a clear error indicating the pair is unavailable.
- What if the FX series contains gaps longer than 7 calendar days (e.g., during market disruptions)? → Continue applying forward-fill/backward-fill regardless of gap length; no special handling for long gaps.
- What if the security price series and FX series have no overlapping dates at all? → Return an error indicating an alignment failure.
- What about rounding of translated prices? → Translated prices are returned with the same numeric precision as the source data (no forced rounding).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The current price endpoint MUST accept an optional `currency` query parameter containing a 3-letter ISO 4217 currency code.
- **FR-002**: The historical price endpoint MUST accept an optional `currency` query parameter containing a 3-letter ISO 4217 currency code.
- **FR-003**: When `currency` is not provided, the service MUST return prices in the security's native currency, unchanged.
- **FR-004**: When `currency` is provided and matches the security's native currency, the service MUST return prices unchanged with no external FX fetch.
- **FR-005**: When `currency` is provided and differs from the security's native currency, the service MUST fetch the FX rate time series for the native-to-target currency pair using the same caching infrastructure used for security price data.
- **FR-006**: For current price translation, the service MUST apply the most recent available FX rate to the native price.
- **FR-007**: For historical price translation, the service MUST align FX dates to security trading dates using forward-fill (nearest prior FX rate) as the primary strategy.
- **FR-008**: When no prior FX rate exists for a given security trading date, the service MUST apply backward-fill (nearest subsequent FX rate) as a fallback.
- **FR-009**: When no FX rate can be resolved (neither forward nor backward fill is possible), the service MUST return an error for the entire request. The HTTP status code MUST mirror the underlying failure: 503 when the data source is unreachable, 404 when the FX pair or data does not exist for the requested period.
- **FR-010**: The translated price response MUST include the target currency code. For current price, the response MUST include the FX rate applied. For historical prices, each individual price entry MUST include the FX rate applied to that date (e.g., `date`, translated `close`, and `fx_rate` per entry).
- **FR-011**: The service MUST expose a new `GET /fx/{pair}/history` endpoint accepting two concatenated 3-letter ISO currency codes (e.g., `USDGBP`) and `from`/`to` date parameters.
- **FR-012**: The FX history endpoint MUST validate that both currency codes in the pair are recognised ISO 4217 codes; an unrecognised code MUST return a 422 response.
- **FR-013**: The FX history endpoint MUST validate that `from` is not after `to`; a reversed range MUST return a 422 response.
- **FR-014**: The FX history endpoint MUST use the same caching infrastructure as the security endpoints (cache hit, partial hit, and miss logic all apply).
- **FR-015**: Both `currency` query parameters MUST be validated as 3-letter alphabetic ISO codes; any other value MUST return a 422 response.
- **FR-016**: `USDGBP` and `GBPUSD` are treated as independent, distinct currency pairs — the service MUST NOT auto-invert or cross-reference one from the other; each pair is fetched and cached independently.

### Key Entities *(include if feature involves data)*

- **FX Rate**: A single exchange rate between two currencies on a given date. Attributes: base currency (ISO code), quote currency (ISO code), date, rate (numeric).
- **FX Time Series**: An ordered collection of FX Rates spanning a date range for a specific currency pair.
- **Currency-Translated Price**: A security price after applying an FX rate. Attributes: date, translated close price, applied FX rate (included on every entry for both current and historical responses), target currency code (at response level).
- **Currency Pair**: A combination of base currency and quote currency, identified by their concatenated ISO codes (e.g., `USDGBP` = 1 USD expressed in GBP). Pairs are directional — `USDGBP` and `GBPUSD` are distinct pairs stored independently.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Consumers can obtain security prices in any supported target currency without performing manual conversion; the conversion is transparent and auditable via the response fields.
- **SC-002**: All historical price entries in a translated response have an FX rate applied — no untranslated entries are returned in a successful response.
- **SC-003**: Repeated requests for the same FX pair over the same date range are served from cache, with no additional calls to the external data source.
- **SC-004**: Requests with invalid currency codes or reversed date ranges are rejected within the same response-time budget as all other validation errors.
- **SC-005**: The FX history endpoint returns a correctly ordered, dated rate series covering the full requested range when data is available.
- **SC-006**: Calendar mismatches between security and FX markets (different holiday schedules) are handled automatically — consumers receive a fully aligned translated series without needing to specify alignment behaviour.

## Assumptions

- The security's native currency is deterministic and returned as metadata from the same data source that provides prices. No manual currency mapping table is required.
- FX pair tickers follow the convention `{BASE}{QUOTE}=X` in the underlying data source (e.g., `USDGBP=X` for USD→GBP). This convention is encapsulated internally and not exposed to consumers.
- The caching infrastructure implemented in Feature 003 (file-based CSV cache) is already in place and will be reused without modification for FX time series storage.
- Forward-fill (last known FX rate carried forward) is always applied first; backward-fill (next known FX rate carried back) is only used when no prior rate exists. This is consistent with standard market data alignment practice.
- The FX history endpoint is intended for diagnostic and cash-analysis use cases; it does not need to support currency translation of its own output (i.e., no nested translation).
- ISO 4217 validation uses a fixed list of recognised alphabetic codes; dynamic lookup from an external registry is out of scope.
- Partial FX data (cache miss during translation) is handled by the existing caching logic; no new partial-response behaviour is introduced.
- FX pairs are always expressed as `{BASE}{QUOTE}` with the base being the security's native currency and the quote being the consumer's requested target currency (e.g., a USD security translated to GBP uses `USDGBP`).

## Clarifications

### Session 2026-05-10

- Q: What gap-fill strategy should be used when an FX rate is missing for a security trading date? → A: Forward-fill first (nearest prior FX rate); backward-fill as fallback when no prior rate exists; error when neither is possible.
- Q: How should FX tickers be constructed? → A: Assumed `{BASE}{QUOTE}=X` convention (e.g., `USDGBP=X`), encapsulated internally.
- Q: Are `USDGBP` and `GBPUSD` treated as the same pair or as independent pairs? → A: Independent pairs — each is fetched and cached separately; no auto-inversion or cross-referencing.
- Q: What HTTP status code should be returned when FX data cannot be fetched during translation? → A: Mirror the underlying error — 503 if the data source is unreachable, 404 if the FX pair or data is not found for the period.
- Q: Should each historical price entry include the FX rate applied to it, or only a top-level currency code? → A: Per-entry FX rate — every historical price entry includes the `fx_rate` applied on that date, enabling full auditability of the translation.
