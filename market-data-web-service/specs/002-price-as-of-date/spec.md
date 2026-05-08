# Feature Specification: Add As-Of Date to Current Price Response

**Feature Branch**: `002-price-as-of-date`
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description: "the 'securities/{ticker}/price' endpoint needs to include the 'as of' date in the response payload indicating what business date the observed price is for. This should reconcile with the response for 'securities/{ticker}/history' where the most recent observed price and date are the same."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know What Date a Price Is For (Priority: P1)

A consumer of the current price endpoint receives a price figure but currently has no way to know which trading date that price corresponds to. When markets are closed (weekends, public holidays, after-hours), the most recent price is the prior session's close — and without an "as of" date the caller cannot tell whether the price is from today, yesterday, or several days ago.

By including an `as_of_date` field in the price response, the consumer knows exactly which business date the returned price represents, without needing to make a separate call to the history endpoint.

**Why this priority**: This is the only user story for this feature and it directly addresses a data integrity gap. Without it, consumers of the price endpoint may silently use a stale price believing it to be current. It is also a prerequisite for any downstream calculation that timestamps a position value against a specific trading date.

**Independent Test**: A client calls `GET /securities/{ticker}/price` and receives a response containing `as_of_date`. The client then calls `GET /securities/{ticker}/history` with a date range that includes the present day. The `as_of_date` in the price response must equal the `date` on the last entry in the history `prices` list.

**Acceptance Scenarios**:

```gherkin
Feature: As-of date on current price response

  Scenario: Current price response includes an as-of date
    Given the API service is running locally
    And the ticker "AAPL" is a valid security listed on a supported exchange
    When a client sends a GET request to /securities/AAPL/price
    Then the response status code is 200
    And the response body contains a field "as_of_date" in YYYY-MM-DD format

  Scenario: As-of date is a valid past or current trading date
    Given the API service is running locally
    When a client sends a GET request to /securities/AAPL/price
    Then the response status code is 200
    And the "as_of_date" field is not a future date
    And the "as_of_date" field is not a Saturday or Sunday

  Scenario: As-of date reconciles with the history endpoint
    Given the API service is running locally
    And the ticker "MSFT" is a valid security
    When a client sends a GET request to /securities/MSFT/price
    And a client also sends a GET request to /securities/MSFT/history with no date parameters
    Then the "as_of_date" in the price response matches the "date" of the last entry in the history "prices" list
```

---

### Edge Cases

- What happens when the market has been closed for several days (e.g. an extended holiday)? → The `as_of_date` reflects the last actual trading session with a valid closing price, which may be several calendar days in the past.
- What happens if the history endpoint returns no prices for the default 30-day range? → The reconciliation guarantee applies only when the history endpoint returns at least one price entry for the same ticker; the `as_of_date` field is still required and must be present in all successful price responses.
- What happens when the market is currently open intraday? → The `as_of_date` reflects the current session's calendar date if an intraday price is returned, or the prior session's date if yfinance falls back to the previous close.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The current price response MUST include a new field `as_of_date` in YYYY-MM-DD format, representing the trading date that the returned `price` value is sourced from.
- **FR-002**: The `as_of_date` MUST be consistent with the `date` on the most recent `PricePoint` returned by `GET /securities/{ticker}/history` for the same ticker, for any date range that includes the present day.
- **FR-003**: The `as_of_date` MUST be derived from the same underlying price observation as the `price` field — both values MUST refer to the same trading session.
- **FR-004**: The `as_of_date` MUST NOT be a future date and MUST NOT be a calendar day on which no trading occurred (e.g. a weekend or market holiday with no closing price available).
- **FR-005**: The change MUST be backward-compatible — all existing fields in the current price response (`ticker`, `price`, `currency`, `timestamp`, `market_status`) MUST remain present and unmodified.
- **FR-006**: The OpenAPI contract MUST be updated to document the `as_of_date` field with its type (`string`), format (`date`, YYYY-MM-DD), and a description of what it represents.

### Key Entities

- **PriceResponse**: Existing current price response model. Gains one new required field: `as_of_date` (date string, YYYY-MM-DD) — the trading date the `price` observation is sourced from.
- **PricePoint**: Existing historical price entry (`date`, `close`). Unchanged — its `date` field is the authoritative reference for reconciliation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every successful response from the current price endpoint includes an `as_of_date` field — 100% of responses, for any valid ticker.
- **SC-002**: For any valid ticker, the `as_of_date` in the price response equals the `date` of the last entry in the history response (when the history range includes the present day) — the two endpoints agree on 100% of tested cases.
- **SC-003**: The `as_of_date` is never a future date and never falls on a Saturday or Sunday — verified across all responses in the test suite.
- **SC-004**: All existing consumers of the price endpoint receive their previously documented fields unchanged — zero breaking changes.

## Assumptions

- The underlying data source (Yahoo Finance) provides the trading date of the last observed price as part of the same data fetch used to retrieve the price itself, so no additional network call is required to populate `as_of_date`.
- The `as_of_date` field is additive to the existing price response schema and is always required (not optional) — every successful 200 response must include it.
- No change is required to the history endpoint or its response schema; the `date` field on each `PricePoint` already provides trading dates correctly and is the reference point for consistency testing.
- The reconciliation guarantee (SC-002) is validated using the default 30-day history range. For tickers with infrequent trading, the guarantee still holds for whatever the most recent available price date is.
