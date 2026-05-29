# Feature Specification: Pence Unit Normalisation

**Feature Branch**: `008-pence-normalisation`  
**Created**: 2026-05-26  
**Status**: Draft  
**Input**: User description: "some time series are quoted in pence rather than whole amounts; for example GBp or USd. In these cases the return value should be multiplied by the correct ratio (e.g. GBp x 0.01 = GBP) and the reported currency output as the whole unit. For example the ticker "CNKY.L" returns currency of GBp and price today of 31140. After this feature it should return GBP currency and a price of 311.40. This behavior must be consistent across endpoints (e.g. current vs historical)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Current Price Returns Whole-Unit Amount (Priority: P1)

A consumer requests the current price of a security that is quoted in a sub-unit currency (e.g. GBp — British pence). The service detects the sub-unit designation and automatically scales the price to the major unit (GBP) and reports the corrected currency code, so that consumers always receive values in major currency units without any knowledge of sub-unit quirks.

**Why this priority**: This is the most visible consumer-facing correctness issue. A raw pence price of 31140 for a security labelled as GBP will cause downstream valuation errors for any consumer. Fixing the current-price endpoint is the highest-value increment.

**Independent Test**: Can be fully tested by requesting the current price of a known pence-denominated security (e.g. CNKY.L) and asserting the returned currency is `GBP` and the price is the raw value divided by 100.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Current price for pence-denominated security is normalised to pounds
  Given the pricing source returns a price of 31140 in currency "GBp" for ticker "CNKY.L"
  When a consumer requests the current price for "CNKY.L"
  Then the response currency is "GBP"
  And the response price is 311.40

Scenario: Current price for a non-sub-unit currency is returned unchanged
  Given the pricing source returns a price of 150.00 in currency "USD" for ticker "AAPL"
  When a consumer requests the current price for "AAPL"
  Then the response currency is "USD"
  And the response price is 150.00

Scenario: Current price for US cent-denominated security is normalised to dollars
  Given the pricing source returns a price of 15000 in currency "USd" for a ticker
  When a consumer requests the current price for that ticker
  Then the response currency is "USD"
  And the response price is 150.00

Scenario: Current price in major-unit GBP is not normalised
  Given the pricing source returns a price of 311.40 in currency "GBP" for a ticker
  When a consumer requests the current price for that ticker
  Then the response currency is "GBP"
  And the response price is 311.40

Scenario: Variant casing of sub-unit currency code is still normalised
  Given the pricing source returns a price of 31140 in currency "gBp" for a ticker
  When a consumer requests the current price for that ticker
  Then the response currency is "GBP"
  And the response price is 311.40
```

---

### User Story 2 - Price History Returns Whole-Unit Amounts (Priority: P2)

A consumer requests a date range of historical prices for a pence-quoted security. All price points in the series are divided by the appropriate sub-unit ratio, and the reported currency in the response is the corresponding major currency code, so that historical analysis produces correctly-scaled values.

**Why this priority**: Historical price series are the primary data consumed for portfolio valuation and performance calculations. Incorrect scaling across a date range would silently corrupt every calculation that depends on it.

**Independent Test**: Can be fully tested by requesting a historical series for a known pence-denominated ticker and asserting every price point is scaled down by 100 and the currency field reports the major unit.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Historical prices for pence-denominated security are normalised
  Given the pricing source returns prices in currency "GBp" for ticker "CNKY.L"
  When a consumer requests price history for "CNKY.L" over a date range
  Then the response currency is "GBP"
  And every price in the series equals the raw source price divided by 100

Scenario: Historical prices for a standard currency are returned unchanged
  Given the pricing source returns prices in currency "EUR" for a ticker
  When a consumer requests price history for that ticker
  Then the response currency is "EUR"
  And price values are unchanged
```

---

### User Story 3 - FX-Converted Price History Applies Normalisation Before Conversion (Priority: P3)

A consumer requests historical prices for a pence-quoted security with FX conversion to a target currency (e.g. GBP → USD). The sub-unit normalisation is applied first (GBp → GBP), and then the FX conversion is applied to the normalised values, producing a correctly-scaled result in the target currency.

**Why this priority**: FX translation is an optional overlay; normalisation must occur first to produce a correct base value. Without correct ordering the FX rate would be applied to a 100x-inflated pence value, giving a wildly wrong result.

**Independent Test**: Can be fully tested by requesting a pence-quoted ticker with currency conversion and verifying the resulting prices reflect both the sub-unit scaling and the FX rate.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Pence-quoted history converted to a third currency applies normalisation first
  Given the pricing source returns prices in currency "GBp" for a ticker
  And an FX rate of 1.25 from GBP to USD exists
  When a consumer requests price history for that ticker with currency "USD"
  Then each price equals the raw pence price divided by 100, multiplied by the GBP-to-USD rate

Scenario: Current price for pence-quoted ticker with currency conversion
  Given the pricing source returns a price of 31140 in currency "GBp"
  And an FX rate of 1.25 from GBP to USD exists
  When a consumer requests the current price with currency "USD"
  Then the response currency is "USD"
  And the response price is 389.25
```

---

### Edge Cases

- What if the source currency code uses unexpected casing (e.g. `gbp`, `GBP`, `gBp`)? Normalisation detection must be case-insensitive to the sub-unit indicator.
- What if the ratio between sub-unit and major unit is not 100 (e.g. a hypothetical 1000:1 minor unit)? The feature should be extensible, but the initial implementation covers 100:1 (pence, cents).
- What if a price of zero is returned in a sub-unit currency? Zero scaled by any ratio is still zero; this should not be treated as an error.
- What happens when the source reports a currency that partially matches a known sub-unit code but is not one (e.g. a future new currency code starting with a lowercase letter)? Only explicitly mapped sub-unit codes are normalised; unrecognised codes pass through unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST detect when a source returns prices in a recognised sub-unit currency (e.g. `GBp`, `USd`) and automatically convert both the price values and the reported currency to the corresponding major-unit equivalent.
- **FR-002**: The conversion MUST apply the correct scaling ratio for each known sub-unit: `GBp` → `GBP` at ÷100; `USd` → `USD` at ÷100.
- **FR-003**: Normalisation MUST be applied consistently across all pricing endpoints: current price and price history.
- **FR-004**: When FX currency conversion is also requested, sub-unit normalisation MUST be applied before the FX conversion step.
- **FR-005**: The reported `currency` field in every response MUST reflect the major-unit code after normalisation (e.g. `GBP`, not `GBp`).
- **FR-006**: Prices denominated in major-unit currencies (e.g. `USD`, `GBP`, `EUR`) MUST pass through unchanged.
- **FR-007**: Sub-unit detection MUST be case-insensitive on the minor-unit indicator character so that variant casings from different data sources are handled correctly.
- **FR-008**: The set of recognised sub-unit currencies MUST be configurable or enumerable within the service so that new mappings can be added without structural changes.

### Key Entities

- **Sub-unit Currency Mapping**: A mapping from a sub-unit currency code (e.g. `GBp`) to its major-unit code (`GBP`) and scaling divisor (100). This mapping drives all normalisation decisions.
- **Price Point**: A single price observation (date + value + currency). After normalisation, its value and currency reflect the major unit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A security known to be quoted in pence (e.g. CNKY.L) returns a price within the expected major-unit range (e.g. ~311 GBP rather than ~31100 GBp) across both current-price and history endpoints.
- **SC-002**: 100% of price responses for sub-unit currencies carry the major-unit currency code — no response ever exposes a sub-unit code such as `GBp` to a consumer.
- **SC-003**: FX-converted prices for pence-quoted securities match the value obtained by first dividing the raw pence price by 100 and then applying the FX rate, with no floating-point drift beyond two decimal places.
- **SC-004**: All existing passing tests for non-sub-unit tickers continue to pass unchanged, confirming zero regression on standard currency behaviour.

## Assumptions

- The initial scope covers only 100:1 sub-unit ratios (`GBp` → `GBP`, `USd` → `USD`). Other ratios (e.g. 1000:1) are out of scope for this version.
- Sub-unit detection is based on the currency string returned directly by the upstream data source; the service does not independently re-derive the currency from the ticker symbol.
- Cached price data stores values as returned by the source (i.e. in sub-unit form if that is what the source provides). Normalisation is applied at response time, not at cache-write time, to avoid cache invalidation issues.
- The feature applies to the market data service layer only; any client-side multiplier logic in consuming applications (e.g. the portfolio analysis tool) remains the responsibility of that application and is not changed by this feature.
