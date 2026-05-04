# Feature Specification: Security Pricing API

**Feature Branch**: `001-security-pricing-api`
**Created**: 2026-05-04
**Status**: Draft
**Input**: User description: "Create a locally hosted Python FastAPI web API to return security pricing data for single, standard financial identifiers via a standards-compliant RESTful API. The back-end should utilize the 'yfinance' package to get underlying data from Yahoo Finance web API."

## User Scenarios & Testing *(mandatory)*

<!--
  User stories are prioritized as user journeys ordered by importance.
  Each story is independently testable and delivers standalone value.
-->

### User Story 1 - Retrieve Current Price for a Security (Priority: P1)

A consumer of the API provides a single standard financial identifier (e.g. ticker symbol such as `AAPL` or `TSLA.L`) and receives the current or most-recently available price for that security, along with key metadata such as currency and market status.

**Why this priority**: This is the core value proposition of the service. Without this, no other story can deliver value.

**Independent Test**: A client application sends a GET request with a valid ticker and receives a well-formed JSON response containing a price figure and supporting fields. Can be demonstrated with a single `curl` or HTTP client call.

**Acceptance Scenarios**:

```gherkin
Feature: Retrieve current security price

  Scenario: Valid ticker returns current price
    Given the API service is running locally
    And the ticker "AAPL" is a valid security listed on a supported exchange
    When a client sends a GET request to /securities/{ticker}/price
    Then the response status code is 200
    And the response body contains a numeric field "price"
    And the response body contains a field "currency" with a valid ISO 4217 currency code
    And the response body contains a field "ticker" matching the requested identifier
    And the response body contains a field "timestamp" in ISO 8601 format

  Scenario: Valid London Stock Exchange ticker returns price in GBP
    Given the API service is running locally
    And the ticker "BARC.L" is a valid security on the London Stock Exchange
    When a client sends a GET request to /securities/BARC.L/price
    Then the response status code is 200
    And the field "currency" in the response body is "GBp" or "GBP"

  Scenario: Price field is never zero or negative
    Given the API service is running locally
    When a client requests the price for any valid ticker
    Then the returned "price" field is a positive numeric value
```

---

### User Story 2 - Retrieve Historical Price Series for a Security (Priority: P2)

A consumer provides a financial identifier plus optional start and end dates, and receives an ordered time series of daily closing prices for that security over the requested period.

**Why this priority**: Historical data enables trend analysis, performance calculations, and backtesting — the primary use case for this service within a portfolio tool.

**Independent Test**: A client sends a GET request with a ticker and a date range, and receives an ordered list of date-price pairs covering the requested window.

**Acceptance Scenarios**:

```gherkin
Feature: Retrieve historical price series

  Scenario: Valid ticker with date range returns daily price series
    Given the API service is running locally
    And the ticker "MSFT" is valid
    When a client sends a GET request to /securities/{ticker}/history?from=2024-01-01&to=2024-03-31
    Then the response status code is 200
    And the response body contains a list field "prices"
    And each entry in "prices" contains a "date" in YYYY-MM-DD format and a numeric "close" field
    And the entries are ordered chronologically ascending

  Scenario: Default date range is applied when no dates provided
    Given the API service is running locally
    When a client sends a GET request to /securities/MSFT/history with no date parameters
    Then the response status code is 200
    And the response contains at least one price entry

  Scenario: Start date after end date returns a validation error
    Given the API service is running locally
    When a client sends GET /securities/MSFT/history?from=2024-06-01&to=2024-01-01
    Then the response status code is 422
    And the response body contains a field "detail" describing the validation error
```

---

### User Story 3 - Graceful Handling of Invalid or Unknown Identifiers (Priority: P3)

When a consumer provides an identifier that does not correspond to a known or retrievable security, the API returns a clear, standards-compliant error response rather than an unhandled exception or misleading data.

**Why this priority**: Robustness and predictable error contracts are essential for consumer trust and integration reliability. Directly supports the API-first and observability principles.

**Independent Test**: A client sends a request with an invalid ticker and receives a 404 or 422 JSON error response with a human-readable message.

**Acceptance Scenarios**:

```gherkin
Feature: Invalid identifier error handling

  Scenario: Unknown ticker returns 404
    Given the API service is running locally
    When a client sends a GET request to /securities/INVALIDXYZ99/price
    Then the response status code is 404
    And the response body contains a field "detail" with a descriptive error message

  Scenario: Malformed ticker (special characters) returns 422
    Given the API service is running locally
    When a client sends a GET request to /securities/$/price
    Then the response status code is 422
    And the response body contains a field "detail"

  Scenario: Data source unavailable returns 503
    Given the API service is running locally
    And the upstream data provider is unreachable
    When a client sends a GET request to any valid ticker endpoint
    Then the response status code is 503
    And the response body contains a field "detail" indicating the upstream dependency is unavailable
```

---

### Edge Cases

- What happens when the market is closed and no intraday price exists? → Return the most recent available closing price with a `market_status: closed` indicator.
- What happens when Yahoo Finance returns a zero or null price? → Filter out zero prices and return 404 if no valid price can be resolved.
- What happens when a ticker is valid but delisted? → Return 404 with a descriptive message indicating the security may be delisted.
- What happens when a very large date range is requested for history? → Return results for the requested range; no hard server-side cap, but document practical limits in the API spec.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a RESTful HTTP endpoint to retrieve the current (or most recently available) price for a single security identified by a standard ticker symbol.
- **FR-002**: The system MUST expose a RESTful HTTP endpoint to retrieve a daily historical closing price series for a single security over a caller-specified date range.
- **FR-003**: The system MUST return pricing data sourced from Yahoo Finance via the `yfinance` package.
- **FR-004**: All API responses MUST conform to a documented OpenAPI schema, returning structured JSON.
- **FR-005**: The system MUST return appropriate HTTP status codes: 200 for success, 404 for unknown identifiers, 422 for invalid request parameters, 503 when the upstream data source is unavailable.
- **FR-006**: All price values returned MUST be positive; zero or null prices from the data source MUST be filtered and treated as data unavailability errors.
- **FR-007**: Current price responses MUST include: ticker, price, currency (ISO 4217), timestamp of the price, and market status.
- **FR-008**: Historical price responses MUST include: ticker, a chronologically ordered list of `{date, close}` entries, and currency.
- **FR-009**: The API MUST be hosted locally (on localhost) and accessible without authentication by default.
- **FR-010**: An interactive API documentation interface (Swagger UI) MUST be served at `/docs`.
- **FR-011**: All API requests and responses MUST be logged with structured output including timestamp, endpoint, status code, ticker, and response time.

### Key Entities

- **Security**: A financial instrument identified by a ticker symbol (e.g. `AAPL`, `VOD.L`). Has a currency, exchange, and pricing history.
- **PricePoint**: A single price observation — contains a date/timestamp and a numeric close/current price.
- **PriceSeries**: An ordered collection of `PricePoint` records for a given security over a date range.
- **ErrorResponse**: A structured error payload containing `detail` (human-readable message) and optionally a `code` field.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A consumer can retrieve the current price for any valid, actively-traded ticker in under 3 seconds under normal network conditions.
- **SC-002**: A consumer can retrieve up to 12 months of daily historical price data in under 5 seconds.
- **SC-003**: Invalid or unknown tickers always receive a descriptive error response — never an unhandled exception or empty body.
- **SC-004**: 100% of API endpoints are described in the OpenAPI contract and browsable via the interactive documentation interface.
- **SC-005**: All API requests generate a corresponding structured log entry with no gaps.
- **SC-006**: The service starts successfully on a local machine with a single command and requires no external infrastructure beyond internet access.

## Assumptions

- The service is for local/personal use; no authentication or rate-limiting is required for v1.
- Ticker symbols follow Yahoo Finance conventions (e.g. `AAPL` for US equities, `VOD.L` for LSE).
- "Current price" means the most recent closing price available from Yahoo Finance when the market is closed, or the latest intraday price when the market is open.
- The default historical date range (when none is specified) is the trailing 30 calendar days.
- The service runs on `localhost` at a configurable port (default `8000`).
- No local caching is required for v1; all data is fetched live from Yahoo Finance on each request.
- Mobile or browser-based UI consumption is out of scope; the API is consumed programmatically or via Swagger UI.
