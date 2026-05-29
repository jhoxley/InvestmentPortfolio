# Feature Specification: YFinance Price Data Cache

**Feature Branch**: `003-yfinance-cache`  
**Created**: 2026-05-08  
**Status**: Draft  
**Input**: User description: "Create a caching feature in front of the YFinance API. Have a path in the web service configuration file to determine where the cache files can be stored. When processing a request for any historical range the cache should be checked and if the dates match then the cached data is used and no external calls to yfinance made. If the cached range is a subset of the requested range, identify the missing sections and only request those from yfinance. There should be an API method exposed that allows for a single ticker's cache to be deleted or all entries in the cache removed."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Full Cache Hit (Priority: P1)

A consumer requests historical price data for a ticker and date range that is entirely covered by the local cache. The service returns the cached data immediately without making any external network call to YFinance.

**Why this priority**: This is the primary value of caching — eliminating redundant external calls for data already held locally. It directly reduces latency and external API dependency.

**Independent Test**: Can be fully tested by seeding a cache file for a ticker, requesting that same ticker and date range via the API, and verifying the response is correct and that no external network call was made.

**Acceptance Scenarios** *(MANDATORY — Gherkin format; these become `.feature` file scenarios)*:

```gherkin
Scenario: Request is fully satisfied by cached data
  Given a cache file exists for ticker "AAPL" covering dates "2025-01-01" to "2025-03-31"
  When a consumer requests price history for "AAPL" from "2025-01-01" to "2025-03-31"
  Then the response contains the correct price data for the full requested range
  And no external call to YFinance is made

Scenario: Request for a sub-range of cached data uses cache only
  Given a cache file exists for ticker "AAPL" covering dates "2025-01-01" to "2025-12-31"
  When a consumer requests price history for "AAPL" from "2025-03-01" to "2025-06-30"
  Then the response contains the correct price data for the requested sub-range
  And no external call to YFinance is made
```

---

### User Story 2 - Partial Cache Hit (Priority: P2)

A consumer requests historical price data for a ticker and date range where part of the range is already cached but one or more date segments fall outside the cached range. The service fetches only the missing segments from YFinance, merges the results with the cached data, and returns the complete response.

**Why this priority**: Partial caching maximises cache utility — avoiding unnecessary refetching of data already held — while still satisfying requests that span beyond the cached window.

**Independent Test**: Can be fully tested by seeding a cache file with a partial date range, requesting a wider range, and verifying: the response covers the full requested range, and only the uncached date segments were fetched from YFinance.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Request extends beyond the start of cached data
  Given a cache file exists for ticker "MSFT" covering dates "2025-03-01" to "2025-06-30"
  When a consumer requests price history for "MSFT" from "2025-01-01" to "2025-06-30"
  Then only dates "2025-01-01" to "2025-02-28" are fetched from YFinance
  And the response contains the correct price data for the full range "2025-01-01" to "2025-06-30"
  And the cache is updated to include the newly fetched data

Scenario: Request extends beyond the end of cached data
  Given a cache file exists for ticker "MSFT" covering dates "2025-01-01" to "2025-06-30"
  When a consumer requests price history for "MSFT" from "2025-01-01" to "2025-09-30"
  Then only dates "2025-07-01" to "2025-09-30" are fetched from YFinance
  And the response contains the correct price data for the full range "2025-01-01" to "2025-09-30"
  And the cache is updated to include the newly fetched data

Scenario: Request extends beyond both ends of cached data
  Given a cache file exists for ticker "TSLA" covering dates "2025-04-01" to "2025-06-30"
  When a consumer requests price history for "TSLA" from "2025-01-01" to "2025-09-30"
  Then the dates "2025-01-01" to "2025-03-31" and "2025-07-01" to "2025-09-30" are fetched from YFinance
  And the response contains the correct price data for the full range "2025-01-01" to "2025-09-30"
  And the cache is updated to cover the full range

Scenario: YFinance fails when fetching a missing segment
  Given a cache file exists for ticker "MSFT" covering dates "2025-01-01" to "2025-06-30"
  And YFinance is unavailable
  When a consumer requests price history for "MSFT" from "2025-01-01" to "2025-09-30"
  Then the service returns an error response
  And no partial data is returned
  And the existing cache entry for "MSFT" is unchanged
```

---

### User Story 3 - Cache Miss (Priority: P3)

A consumer requests historical price data for a ticker that has no cache entry. The service fetches the full requested range from YFinance, stores the result in the cache, and returns the data to the consumer.

**Why this priority**: This is the cache population path — required for the cache to bootstrap itself on first access for any ticker.

**Independent Test**: Can be fully tested by ensuring no cache entry exists for a ticker, requesting it, verifying the data comes from YFinance, and confirming a cache file is created with the correct content.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: No cache exists for requested ticker
  Given no cache file exists for ticker "GOOG"
  When a consumer requests price history for "GOOG" from "2025-01-01" to "2025-03-31"
  Then the full date range is fetched from YFinance
  And the response contains the correct price data
  And a cache file is created for "GOOG" covering "2025-01-01" to "2025-03-31"
```

---

### User Story 4 - Delete Single Ticker Cache (Priority: P4)

An operator calls a dedicated API endpoint to remove the cached price data for a specific ticker. After deletion, the next request for that ticker fetches fresh data from YFinance.

**Why this priority**: Operators need targeted cache invalidation to refresh stale or incorrect data for a single ticker without disturbing the rest of the cache.

**Independent Test**: Can be fully tested by creating a cache entry, calling the delete endpoint for that ticker, confirming the cache file is removed, and verifying the next price request goes to YFinance.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Delete cache for an existing ticker
  Given a cache file exists for ticker "AAPL"
  When an operator calls DELETE /cache/AAPL
  Then the cache file for "AAPL" is removed
  And the response confirms successful deletion

Scenario: Delete cache for a ticker with no existing cache
  Given no cache file exists for ticker "XYZ"
  When an operator calls DELETE /cache/XYZ
  Then the response indicates no cache was found for "XYZ"
  And no error is raised
```

---

### User Story 5 - Clear Entire Cache (Priority: P5)

An operator calls a dedicated API endpoint to remove all cached price data for all tickers. After clearing, all subsequent price requests fetch fresh data from YFinance.

**Why this priority**: Full cache invalidation is needed when the cache storage location changes, data corruption is suspected, or a bulk refresh is required.

**Independent Test**: Can be fully tested by creating cache entries for multiple tickers, calling the clear-all endpoint, and verifying all cache files are removed and subsequent requests fetch from YFinance.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Clear all cache entries when cache contains data
  Given cache files exist for tickers "AAPL", "MSFT", and "TSLA"
  When an operator calls DELETE /cache
  Then all cache files are removed
  And the response confirms the number of entries deleted

Scenario: Clear all cache entries when cache is empty
  Given no cache files exist
  When an operator calls DELETE /cache
  Then the response confirms zero entries were deleted
  And no error is raised
```

---

### Edge Cases

- What happens when the cache directory does not exist or is inaccessible at startup?
- How does the system handle a corrupted or unreadable cache file for a ticker?
- If YFinance fails or returns no data for a required missing segment, the service returns an error for the entire request (see FR-012). No partial response is returned.
- How does the system handle concurrent requests for the same ticker when the cache is being written?
- What if the configured cache path is read-only?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST read the cache storage directory path from the web service configuration file at startup.
- **FR-002**: The service MUST check the cache before making any request to YFinance for historical price data.
- **FR-003**: If the cache fully covers the requested date range for a ticker, the service MUST return cached data and MUST NOT call YFinance.
- **FR-004**: If the cache partially covers the requested date range for a ticker, the service MUST identify the uncovered date segment(s) and fetch only those from YFinance.
- **FR-005**: If no cache entry exists for a ticker, the service MUST fetch the full requested range from YFinance.
- **FR-006**: After fetching data from YFinance, the service MUST write the result to the cache (merging with existing cached data if a partial hit occurred).
- **FR-007**: The service MUST expose a DELETE endpoint that removes the cache entry for a single specified ticker.
- **FR-008**: The service MUST expose a DELETE endpoint that removes all cache entries for all tickers.
- **FR-009**: The DELETE endpoints MUST return a confirmation response indicating what was deleted (ticker name, or count of deleted entries).
- **FR-010**: If the cache file for a ticker is missing or unreadable, the service MUST treat it as a cache miss and fetch from YFinance without raising an unhandled error.
- **FR-011**: If the cache directory does not exist, the service MUST attempt to create it on startup and log an appropriate message.
- **FR-012**: If YFinance is unavailable, returns an error, or returns no data for a required missing date segment, the service MUST return an error response to the caller for the entire request; partial data MUST NOT be returned silently.
- **FR-013**: When writing a cache entry, the service MUST record the covered date range as the actual first and last dates present in the fetched data (trading days), not the calendar dates originally requested.

### Key Entities *(include if feature involves data)*

- **Cache Entry**: Represents stored price data for a single ticker; contains the ticker symbol, the date range covered, and the price records (date, open, high, low, close, volume).
- **Cache Directory**: The filesystem location (path) where all cache entries are stored; configured via the service configuration file.
- **Missing Segment**: A contiguous date range within a consumer's request that is not covered by the existing cache entry for that ticker; one or two segments may exist (before the cached window, after it, or both).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Requests for data fully covered by the cache are served without any external network call to YFinance, reducing response time for repeated queries.
- **SC-002**: Requests for a date range that partially overlaps the cache result in no more external calls than the number of missing date segments (maximum two calls per request).
- **SC-003**: The cache storage path can be changed via configuration without code changes, and the service correctly reads from and writes to the new location after restart.
- **SC-004**: The single-ticker DELETE endpoint removes only the targeted ticker's cache entry, leaving all other entries intact.
- **SC-005**: The full-cache DELETE endpoint removes all cache entries; zero cache files remain after the operation completes.
- **SC-006**: A corrupted or missing cache file for one ticker does not prevent the service from fulfilling price requests for other tickers.

## Clarifications

### Session 2026-05-08

- Q: What should the service return when YFinance fails or returns no data for a missing date segment during a partial or full cache miss fetch? → A: Return an error response for the entire request; the caller must retry. Partial data MUST NOT be returned silently (FR-012).
- Q: When storing a cache entry's covered date range, should the bounds be the calendar dates originally requested or the actual first/last trading-day dates in the fetched data? → A: Store the actual first and last dates present in the fetched data (trading days only). This prevents false partial hits on non-trading-day boundaries (FR-013, Assumptions updated).

## Assumptions

- The cache is stored as one file per ticker on the local filesystem; each file contains all historical data for that ticker.
- Cache coverage is determined by comparing the requested dates against the actual first and last trading-day dates stored in the cache entry, not the calendar dates originally used when the cache was written. Intra-day precision is not required.
- The cache is treated as eventually consistent — no distributed locking is applied for concurrent writes; last-write-wins is acceptable for this service's usage pattern.
- Cache invalidation based on data staleness (e.g., TTL, time-based expiry) is out of scope for this feature; deletion is manual via the provided API endpoints.
- The web service configuration file already exists and supports key-value pairs or equivalent structure; only a new key for the cache path is added.
- Authentication or authorisation on the cache management DELETE endpoints is out of scope for this feature.
