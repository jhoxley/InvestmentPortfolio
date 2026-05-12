# Feature Specification: Identifier-to-Ticker Lookup

**Feature Branch**: `005-identifier-to-ticker`
**Created**: 2026-05-12
**Status**: Draft
**Input**: User description: "Add a new service and endpoint that translates common, public identifiers (such as ISIN, Cusip or SEDOL) to the Reuters Ticker identifier used by YFinance and currently accepted for current and historical pricing."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Translate a Security Identifier to a Ticker (Priority: P1)

A client holds a known security identifier (ISIN, CUSIP, or SEDOL) and needs the corresponding ticker symbol before they can request price data. They call a single lookup endpoint with the identifier, and the service returns the resolved ticker along with the security name and exchange — giving them enough context to confirm it is the correct security before proceeding.

**Why this priority**: This is the core value of the feature. Without it, clients with ISINs or CUSIPs cannot use the existing pricing endpoints at all. Every other story depends on this lookup working correctly.

**Independent Test**: Can be fully tested by submitting a known ISIN (e.g., the ISIN for Apple Inc.) and asserting that the response contains the expected ticker, a recognisable security name, and an exchange code. Delivers immediate value as a standalone lookup service.

**Acceptance Scenarios**:

```gherkin
Scenario: ISIN resolves to a ticker
  Given the identifier "US0378331005" is the ISIN for Apple Inc.
  When a client requests the ticker for identifier "US0378331005"
  Then the response status is 200
  And the response contains a ticker field with a non-empty value
  And the response contains a security_name field identifying the security
  And the response contains an exchange field

Scenario: CUSIP resolves to a ticker
  Given the identifier "037833100" is the CUSIP for Apple Inc.
  When a client requests the ticker for identifier "037833100"
  Then the response status is 200
  And the response contains a ticker field with a non-empty value

Scenario: SEDOL resolves to a ticker
  Given the identifier "B020QX2" is the SEDOL for Barclays PLC
  When a client requests the ticker for identifier "B020QX2"
  Then the response status is 200
  And the response contains a ticker field with a non-empty value

Scenario: Resolved ticker works with the existing price endpoint
  Given a client has resolved ISIN "US0378331005" to a ticker
  When the client requests the current price using the resolved ticker
  Then the response status is 200
  And a price is returned
```

---

### User Story 2 — Graceful Rejection of Invalid or Unresolvable Identifiers (Priority: P2)

A client submits an identifier that is either malformed, not in the expected format for any supported type, or cannot be found by the underlying data source. The service responds with a clear, descriptive error rather than silently returning wrong data or an opaque failure.

**Why this priority**: Without clear errors, clients cannot distinguish between a valid lookup that returned no result and a bug in their own code (e.g., a mistyped ISIN). Good error messages reduce integration friction significantly.

**Independent Test**: Can be fully tested by submitting known-bad identifiers and asserting the correct HTTP status code and a human-readable error message. Does not require Story 1 to be complete.

**Acceptance Scenarios**:

```gherkin
Scenario: Identifier with invalid format is rejected
  When a client requests the ticker for identifier "NOT-VALID-FORMAT"
  Then the response status is 422
  And the response contains a descriptive error message

Scenario: Valid-format identifier that cannot be resolved returns not-found
  When a client requests the ticker for identifier "US0000000000"
  Then the response status is 404
  And the response contains an error indicating the identifier was not found
```

---

### Edge Cases

- What happens when an ISIN maps to the same security listed on multiple exchanges (e.g., a US primary listing and a London ADR)? The service returns only the single primary/most-liquid listing. Callers who need a specific exchange must use that exchange's ticker directly with the pricing endpoints.
- What happens when the data source is temporarily unavailable? The service should return a 503 with a descriptive message, consistent with the existing pricing endpoints.
- What if a client submits a well-formed ISIN that exists but has been delisted? The service should return whatever the data source provides; if nothing is found, a 404 is returned.
- What if a CUSIP and a SEDOL happen to share the same character sequence? The client may optionally specify the identifier type to disambiguate; otherwise the service applies format-based auto-detection (ISIN: 12 chars starting with a 2-letter country code; CUSIP: 9 alphanumeric chars; SEDOL: 6–7 alphanumeric chars).

---

## Clarifications

### Session 2026-05-12

- Q: What format should the exchange field in the response use? → A: Pass through the exchange identifier exactly as returned by the data source — no normalisation required.
- Q: Should ISIN format validation include Luhn check digit verification, or structural shape only? → A: Structural shape only — 12 chars, 2-letter country code prefix, 9 alphanumeric, 1 alphanumeric check digit character; no Luhn computation required.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST accept a security identifier (ISIN, CUSIP, or SEDOL) as input and return the corresponding ticker symbol.
- **FR-002**: The service MUST support ISIN identifiers with structural format validation only: 12 characters total, beginning with a 2-letter ISO 3166-1 country code, followed by 9 alphanumeric characters, and 1 alphanumeric check digit character. No Luhn check digit computation is performed.
- **FR-003**: The service MUST support CUSIP identifiers (9-character alphanumeric codes used in the US and Canada).
- **FR-004**: The service MUST support SEDOL identifiers (6–7 character alphanumeric codes used primarily for UK and international securities).
- **FR-005**: The service MUST validate the identifier format and return a 422 error with a descriptive message if the submitted value does not match any supported format.
- **FR-006**: The service MUST return a 404 error with a descriptive message if a validly-formatted identifier cannot be resolved to a ticker by the underlying data source.
- **FR-007**: The response MUST include the resolved ticker symbol, the security name, and the exchange on which it is primarily listed. The exchange value MUST be passed through exactly as returned by the underlying data source, with no normalisation to MIC codes or common names.
- **FR-008**: The service MUST accept an optional identifier-type hint (ISIN, CUSIP, or SEDOL) from the caller. If not provided, the service MUST auto-detect the type based on the identifier's format.
- **FR-009**: When a lookup fails due to the underlying data source being unavailable, the service MUST return a 503 error, consistent with the existing pricing endpoints.
- **FR-010**: When an identifier maps to the same security on multiple exchanges, the service MUST return only the single primary/most-liquid listing. Multiple results and exchange-filtering are out of scope.

### Key Entities

- **IdentifierLookupRequest**: The input submitted by the caller — the identifier value (string) and an optional type hint (ISIN, CUSIP, or SEDOL).
- **TickerResolution**: The result returned — resolved ticker symbol, security name, exchange identifier (passed through from the data source as-is), identifier value, and detected/confirmed identifier type.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A client who knows only an ISIN can obtain the corresponding ticker and successfully retrieve a price in two API calls or fewer.
- **SC-002**: All three supported identifier types (ISIN, CUSIP, SEDOL) resolve correctly for at least the 10 most commonly used securities in each category.
- **SC-003**: Invalid identifier formats are rejected within the same response-time envelope as successful lookups — no additional latency for error paths.
- **SC-004**: 100% of error responses include a human-readable message that clearly describes whether the failure was a format problem, a lookup failure, or a data source outage.

---

## Assumptions

- The underlying data source (the same one used for pricing) is capable of resolving identifiers to tickers for at least ISIN, CUSIP, and SEDOL — no additional external service is required.
- Ticker symbols returned are in the format already accepted by the existing current-price and historical-price endpoints (no additional transformation needed).
- Identifier lookup results are not cached between requests in the initial implementation; freshness guarantees match those of the underlying data source.
- Mobile or browser-based clients are out of scope; this is a programmatic API consumed by other services or scripts.
- Authentication and authorisation requirements are the same as the existing pricing endpoints (none, for this local deployment).
- A CUSIP and a SEDOL will not share an identical character sequence in practice; format-based auto-detection is therefore reliable.
- Raw ticker symbols (e.g., "AAPL") are out of scope for this endpoint. Callers who already have a ticker use the existing pricing endpoints directly.
- When an identifier resolves to multiple exchange listings, the service returns only the primary/most-liquid listing; multi-exchange selection is out of scope.
