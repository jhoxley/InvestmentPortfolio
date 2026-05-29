# Feature Specification: Local Price File Fallback

**Feature Branch**: `007-local-price-fallback`  
**Created**: 2026-05-17  
**Status**: Draft  
**Input**: User description: "Not all tickers or isin are supported by the YFinance data source and will resolve to no data. Add a feature to catch all cases where the price history or current price request to YFinance resolves to missing or no data and add a look-up to a local configuration file. If the configuration file contains a mapping from that identifier to a local time series then read the response from that configured file instead. Bypass any caching behavior if data read from a local file. Apply all standard gap-filling or FX conversion logic to the substituted data read from the file. The configuration should indicate the currency of the returned prices, and a mapping to the two columns in a CSV-format file that have a date and price. The date format should be assumed as the same format across all rows, but parse the first observation to determine the exact date format."

## Clarifications

### Session 2026-05-20

- Q: Should the fallback trigger on both empty observation lists AND provider-level "no data"/"ticker not found" exceptions, or only on empty lists? → A: Both — fallback activates on empty observations AND provider-level ticker-not-found exceptions; infrastructure errors (network failures, timeouts) still propagate.
- Q: Should the fallback config support ISIN/CUSIP/SEDOL keys, and should the identifier-resolution endpoint also check the fallback config when YFinance has no translation? → A: Yes — any identifier type (ticker, ISIN, CUSIP, SEDOL) is a valid config key; the identifier-resolution endpoint checks the fallback config and returns the identifier itself as a pseudo-ticker when YFinance has no translation.
- Q: Should the fallback config support an explicit "bypass primary source" flag per entry? → A: Yes — an optional `use_local_only` flag per config entry; when set, the primary source is skipped entirely and the local file is served immediately without attempting YFinance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Price History from Local File When Primary Source Has No Data (Priority: P1)

A consumer requests price history for a ticker that the primary market data source does not support. Without a fallback, this would result in a not-found or empty response. With the fallback configured, the service transparently reads from a local CSV file and returns a complete, gap-filled price series as if data had come from the primary source.

**Why this priority**: This is the core value of the feature — unlocking coverage for tickers that would otherwise be unavailable. All other stories build on top of this capability.

**Independent Test**: Can be fully tested by configuring a fallback mapping for a ticker, requesting its price history, and verifying the response contains prices from the local file with gap-fill applied.

**Acceptance Scenarios** *(MANDATORY — Gherkin format; these become `.feature` file scenarios)*:

```gherkin
Scenario: Price history served from local fallback file when primary source returns no data
  Given the primary data source returns no price history for ticker "PRIV01"
  And a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"
  And the local CSV file contains prices for "2025-01-02" and "2025-01-06"
  When a consumer requests price history for "PRIV01" from "2025-01-02" to "2025-01-06"
  Then the response status is 200
  And the response currency is "GBP"
  And the response contains 3 price entries (gap-filled Mon-Fri series)
  And the response does not come from the price cache

Scenario: Price history from local fallback with gap-fill applied
  Given the primary data source returns no price history for ticker "PRIV01"
  And a fallback configuration maps "PRIV01" to a local CSV file with 2 observations spanning 5 business days
  When a consumer requests price history for "PRIV01" over that 5-day range
  Then the response contains entries for all 5 business days
  And the gaps are filled by forward carry of the nearest observation

Scenario: Ticker with no primary data and no fallback configuration returns not-found error
  Given the primary data source returns no price history for ticker "UNKNOWN"
  And no fallback configuration exists for "UNKNOWN"
  When a consumer requests price history for "UNKNOWN"
  Then the response status is 404

Scenario: Price history for an ISIN-keyed fallback entry served via pseudo-ticker
  Given the primary data source has no ticker translation for ISIN "GB00B0PRVT01"
  And a fallback configuration maps "GB00B0PRVT01" to a local CSV file with currency "GBP"
  And the identifier-resolution endpoint is called for "GB00B0PRVT01"
  Then the resolution response returns "GB00B0PRVT01" as the ticker
  When a consumer requests price history for "GB00B0PRVT01"
  Then the response status is 200
  And the response contains prices from the local file

Scenario: use_local_only flag bypasses primary source entirely
  Given a fallback configuration maps "PRIV01" to a local CSV file with use_local_only set
  When a consumer requests price history for "PRIV01"
  Then the primary data source is never queried
  And the response status is 200 with prices from the local file
```

---

### User Story 2 - Current Price from Local File When Primary Source Has No Data (Priority: P2)

A consumer requests the current price for a ticker the primary source does not support. The service detects the absence of data and serves the most recent price from the configured local file, presenting it as the current price.

**Why this priority**: Current price is the most common single-value query; completing this story alongside history gives full coverage of both pricing endpoints.

**Independent Test**: Configure a fallback ticker, request its current price, and verify the response returns the most recent price in the local file with the correct currency.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Current price served from local fallback file
  Given the primary data source returns no current price for ticker "PRIV01"
  And a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"
  And the most recent entry in the local file is "2025-01-06" at 150.00
  When a consumer requests the current price for "PRIV01"
  Then the response status is 200
  And the response price is 150.00
  And the response currency is "GBP"
  And the response as-of date is "2025-01-06"
  And the response market status is "closed"

Scenario: Current price fallback ticker with no configuration returns not-found error
  Given the primary data source returns no current price for ticker "UNKNOWN"
  And no fallback configuration exists for "UNKNOWN"
  When a consumer requests the current price for "UNKNOWN"
  Then the response status is 404
```

---

### User Story 3 - FX Currency Conversion Applied to Local File Prices (Priority: P3)

A consumer requests prices from a local fallback source in a different currency than the file's native currency. The service applies the same FX conversion pipeline used for primary-source prices to the local file data, including gap-fill of FX rates.

**Why this priority**: Without currency conversion, consumers of multi-currency portfolios would receive raw prices in the file's native currency regardless of their request. This story completes the feature parity with primary-source data.

**Independent Test**: Configure a fallback ticker with currency GBP, request price history with target currency USD, verify the response prices reflect the GBP→USD conversion.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Local fallback prices are converted to the requested target currency
  Given the primary data source returns no price history for ticker "PRIV01"
  And a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"
  And the local file contains a price of 100.00 on "2025-01-02"
  And the FX rate for GBPUSD on "2025-01-02" is 1.25
  When a consumer requests price history for "PRIV01" from "2025-01-02" to "2025-01-02" with currency "USD"
  Then the response price for "2025-01-02" is 125.00
  And the response currency is "USD"
```

---

### Edge Cases

- What happens when the fallback CSV file is referenced in the config but the file does not exist? → Return a 503 (service unavailable) error with a descriptive message.
- What happens when the fallback CSV file exists but contains no data rows (headers only)? → Treat as no data; return 404 as if no fallback were configured.
- What happens when the fallback CSV file has extra columns beyond date and price? → Ignore extra columns; use only the configured date and price columns.
- What happens when the requested date range is entirely outside the dates in the local file? → Return a gap-filled series using the available prices (forward/backward carry to cover the full range, same as primary data).
- What happens when the primary source returns a network or infrastructure error rather than a "no data" signal? → The fallback is NOT triggered; the original error is surfaced to the consumer. The fallback activates only on zero-observation responses or provider-level ticker-not-found exceptions.
- What happens when an ISIN pseudo-ticker is passed directly to the pricing endpoint without going through identifier resolution first? → The pricing endpoint looks up the ISIN in the fallback config directly; if found, it serves from the local file. The identifier-resolution step is optional for consumers who already know their identifier is a fallback key.
- What happens when the same identifier appears in both the fallback config AND YFinance (e.g., a previously private asset that gains exchange listing) and `use_local_only` is false? → Primary source is tried first; if data is returned, the local file is not used. Operators should set `use_local_only` deliberately to prevent this.
- What happens when the local file's date format is inconsistent after the first row? → Undefined — the specification assumes a consistent format across all rows; the system parses the first observation to determine the format and applies it universally.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the primary market data source returns zero price observations for a ticker, or raises a provider-level "no data" / "ticker not found" signal, the system MUST check the local fallback configuration for a matching entry. Network errors, timeouts, and other infrastructure exceptions MUST NOT trigger the fallback.
- **FR-002**: If the fallback configuration contains an entry for the requested ticker, the system MUST read price data from the configured local CSV file and return it as the response.
- **FR-003**: Data read from a local fallback file MUST NOT be written to or served from the price cache; each request reads directly from the file.
- **FR-004**: The fallback configuration MUST specify the currency of the prices in the local file.
- **FR-005**: The fallback configuration MUST specify which column contains the date values and which column contains the price values (by column name or index).
- **FR-006**: The system MUST auto-detect the date format by parsing the first data row of the CSV; the same format is applied to all subsequent rows.
- **FR-007**: Gap-fill logic (forward-fill and back-fill) MUST be applied to local file data in the same way it is applied to primary-source data.
- **FR-008**: FX currency conversion MUST be applicable to local file prices using the currency declared in the fallback configuration.
- **FR-009**: When a ticker is absent from the fallback configuration and the primary source returns no data, the system MUST return the same not-found error as it does today.
- **FR-010**: When the primary source returns an infrastructure error (e.g., network failure, timeout, authentication error), the fallback MUST NOT be triggered; the original error MUST be surfaced to the consumer. Only provider-level "no data" signals (empty observation list or ticker-not-found exception) activate the fallback.
- **FR-011**: When the fallback file is configured but cannot be read (file missing, permission error), the system MUST return a service error with a descriptive message.
- **FR-012**: The identifier-resolution endpoint MUST consult the fallback configuration when the primary source returns no ticker translation for a requested ISIN, CUSIP, or SEDOL. If a matching entry is found, the endpoint MUST return the original identifier as a pseudo-ticker, enabling subsequent pricing requests to route to the local file.
- **FR-013**: When a fallback configuration entry has `use_local_only` set to true, the service MUST bypass the primary data source entirely and serve data from the local file immediately, without attempting a primary-source lookup.

### Key Entities *(include if feature involves data)*

- **FallbackConfiguration**: A persistent mapping of identifiers (ticker, ISIN, CUSIP, or SEDOL) to local price sources. Contains: identifier, path to the local CSV file, currency code, date column name/index, price column name/index, and an optional `use_local_only` flag (default false). When `use_local_only` is true, the primary source is never consulted for that identifier.
- **LocalPriceFile**: A CSV file on the filesystem containing at minimum a date column and a price column, with one row per observation. Dates are assumed to follow a consistent format parseable from the first row.
- **FallbackPriceObservation**: A single date-price pair read from a local CSV file, semantically equivalent to an observation from the primary data source.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Price history and current price requests for any configured fallback ticker succeed with a 200 response and correctly populated price data, regardless of the primary source returning no data.
- **SC-002**: All gap-fill and FX conversion behaviors that apply to primary-source prices apply identically to local fallback prices — verified by identical test coverage paths.
- **SC-003**: No fallback data appears in the price cache; repeated requests for a fallback ticker each read directly from the local file without cache pollution.
- **SC-004**: Tickers absent from both the primary source and the fallback configuration continue to return a 404 error with no change in behavior.
- **SC-005**: Operators can add a new fallback ticker by editing the configuration file without restarting the service or modifying application code.
- **SC-006**: Misconfigured fallback entries (missing file, empty file) produce clear, actionable error messages that allow the operator to diagnose and fix the issue.

## Assumptions

- The fallback configuration is a JSON file on the local filesystem whose path is specified in the application settings (environment variable or config). Its contents are read on each request, or cached in memory with a short TTL, to support SC-005 (no restart required).
- Fallback configuration keys may be any identifier type: ticker symbols, ISINs, CUSIPs, or SEDOLs. Matching is case-insensitive to avoid operator errors (e.g., "aapl" matches "AAPL"). When an ISIN, CUSIP, or SEDOL is used as a config key, the identifier-resolution endpoint returns it as a pseudo-ticker; subsequent pricing requests use that pseudo-ticker to look up the fallback config.
- The fallback is triggered by either a zero-observation response OR a provider-level "ticker not found" / "no data" exception from the primary source. Infrastructure errors (network failures, timeouts, authentication errors) do NOT trigger the fallback — they propagate as-is to preserve fail-fast behavior for infrastructure problems.
- The local CSV file may contain any number of columns; only the two configured columns (date and price) are used.
- The date format in the CSV is consistent across all rows; the format is inferred from the first data row using standard date-parsing heuristics and applied to all subsequent rows.
- "Current price" from a local file is defined as the most recent date's price in the CSV. The market status is always returned as "closed" since local files represent static historical data.
- The feature applies to the securities pricing endpoints (`/securities/{ticker}/price` and `/securities/{ticker}/history`). The FX pair history endpoint (`/fx/{pair}/history`) is out of scope, as FX pairs are managed separately and all major pairs are supported by the primary source.
- Caching bypass means the service does not write fallback data to the cache AND does not read from the cache for fallback tickers; the cache remains clean for primary-source data.
